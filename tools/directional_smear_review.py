"""사용자 정정: 팔꿈치에서 넓어지는 형태와 이동 방향에 따른 공중 흔적의 검토판."""
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET
import zipfile

import numpy as np
import event_context as C
import no_glow_smear_review as BASE


def ribbon(tail, head, width, bend=0):
    tail, head = np.asarray(tail,float), np.asarray(head,float)
    d = head-tail
    length = float(np.linalg.norm(d))
    if length < 1e-6 or not np.isfinite([*tail,*head,width,bend]).all() or width <= 0:
        raise ValueError('유한한 양수 크기의 스미어가 필요하다')
    normal = np.array([-d[1],d[0]])/length
    left, right = head+normal*width/2, head-normal*width/2
    mid = tail+d*.48+normal*bend
    # 시작 폭0, 끝으로 갈수록 넓어지는 두 경계와 둥근 끝. 픽셀 윤곽/손가락 복제 아님.
    return np.array([[tail,mid+normal*width*.17,left],
                     [left,head+d*.08,right],
                     [right,mid-normal*width*.17,tail]])


def trajectory(annotation, index):
    points = [np.asarray(r['points_px'][2],float) for r in annotation['frames']]
    current = points[index]
    previous = next((p for p in reversed(points[:index]) if np.linalg.norm(current-p)>1e-6),None)
    following = next((p for p in points[index+1:] if np.linalg.norm(current-p)>1e-6),None)
    delta = current-previous if previous is not None else following-current if following is not None else None
    if delta is None or np.linalg.norm(delta)<1e-6:
        raise ValueError('공중 스미어 방향의 근거가 없다')
    direction = delta/np.linalg.norm(delta)
    # 전후 이동 방향의 회전 성분을 사용. 원본 전체 궤적의 자동 정답이라는 뜻은 아니다.
    bend_sign = 0.
    if previous is not None and following is not None:
        after = following-current
        bend_sign = float(np.sign(delta[0]*after[1]-delta[1]*after[0]))
    return direction, bend_sign


def geometry(annotation, index):
    row = annotation['frames'][index]
    elbow, wrist = np.asarray(row['points_px'][1],float),np.asarray(row['points_px'][2],float)
    arm = ribbon(elbow,wrist,np.linalg.norm(wrist-elbow)*.45)
    direction, bend_sign = trajectory(annotation,index)
    floating = []
    for area in row['smears']:
        center = np.asarray(area['center_px'],float)
        width, extent = np.asarray(area['size_px'],float)
        floating.append(ribbon(center-direction*extent/2,center+direction*extent/2,
                               width*.7,bend_sign*width*.2))
    return [arm]+floating, direction


def visibility(row):
    wrist=np.asarray(row['points_px'][2],float)
    return [bool(row['smear_active'])]+[
        bool(bool(row['smear_active']) and np.linalg.norm(np.asarray(a['center_px'],float)-wrist)>np.linalg.norm(a['size_px'])*.5)
        for a in row['smears']]


def build(annotation):
    root = BASE.build(annotation,False)
    root.set('Name','directional_smear_review')
    w,h = annotation['image_size']
    records = []
    for n,(frame,row) in enumerate(zip(root.findall('Frame'),annotation['frames'])):
        ET.SubElement(frame,'LayerDef',ID='1',Name='directional_smear',Visible='true',Locked='false')
        shapes,direction = geometry(annotation,n)
        enabled=visibility(row)
        records.append(dict(source_index=row['source_index'],floating_direction=direction.tolist(),
                            active=row['smear_active'],shape_visibility=enabled,direction_status='전후 손 중심 위치에서 추론'))
        for g,curves in enumerate(shapes):
            ids = [str(9800000+g*10+k) for k in range(3)]
            pbase = 40000000+n*1000+g*100
            for k,curve in enumerate(curves):
                ao=ET.SubElement(frame,'AO',ID=ids[k],TypeId='3',LayerId='1',DrawOrder=ids[k],Color='0',
                    ThicknessScale='.2',ObjectScale='1',GlowRadius='0',GlowThickness='0',GlowColor='0',GlowAlpha='0')
                for j,point in enumerate(curve):
                    pid=pbase+k*3+j
                    ap=ET.SubElement(ao,'AP',ID=str(pid),Index=str(j),Flags='5' if j==1 else '4',
                        X=f'{point[0]/w*100:.6f}',Y=f'{point[1]/h*100:.6f}')
                    if j==0:ET.SubElement(ap,'AC',ConnPtId=str(pbase+((k-1)%3)*3+2))
                    if j==2:ET.SubElement(ap,'AC',ConnPtId=str(pbase+((k+1)%3)*3))
                    if g==0 and (k,j) in [(0,0),(2,2)]:
                        joint=frame.findall('AO')[1].find('AP')
                        ET.SubElement(ap,'AC',ConnPtId=joint.get('ID'));ET.SubElement(joint,'AC',ConnPtId=str(pid))
            fill=ET.SubElement(frame,'FR',ID=str(7900000+n*10+g),Color=str((0x880000ff if g==0 else 0x660000ff) if enabled[g] else 0))
            for oid in ids:ET.SubElement(fill,'FS',Kind='0',ObjId=oid,StartT='0',EndT='1',Contour='0')
    for r in records:r['direction_status']='전후 손 중심 위치에서 추론; 실제 잔상의 시간 대응 미확정'
    return root,records


def inspect(root,annotation,context):
    C.validate(context)
    plain=BASE.build(annotation,False);seen=set()
    frames=root.findall('Frame')
    if len(frames)!=len(annotation['frames']) or len(frames)!=len(context['source_indices']):raise ValueError('장 수 불일치')
    for n,(frame,row) in enumerate(zip(frames,annotation['frames'])):
        aos=frame.findall('AO');points=[p for a in aos for p in a.findall('AP')];by={p.get('ID'):p for p in points}
        if len(aos)!=11 or len(points)!=31 or len(by)!=31 or seen&by.keys():raise ValueError('객체/점 ID 오류')
        seen.update(by)
        if row['source_index']!=context['source_indices'][n]:raise ValueError('원본 장 대응 불일치')
        for a,b in zip(plain.findall('Frame')[n].findall('AO'),aos[:2]):
            if a.attrib!=b.attrib or [p.attrib for p in a.findall('AP')]!=[p.attrib for p in b.findall('AP')]:raise ValueError('기존 팔 축 변경')
        for p in points:
            for c in p.findall('AC'):
                q=by.get(c.get('ConnPtId'))
                if q is None or any(p.get(k)!=q.get(k) for k in ('X','Y')):raise ValueError('연결 좌표/참조 오류')
        fills=frame.findall('FR')
        if len(fills)!=3:raise ValueError('채움 개수 오류')
        ids={a.get('ID') for a in aos}
        for g,f in enumerate(fills):
            if len(f.findall('FS'))!=3 or any(s.get('ObjId') not in ids for s in f.findall('FS')):raise ValueError('채움 참조 오류')
            if any(s.get('Kind')!='0' or s.get('StartT')!='0' or s.get('EndT')!='1' for s in f.findall('FS')):raise ValueError('채움 경계 구간 오류')
            if not visibility(row)[g] and int(f.get('Color'))>>24:raise ValueError('비표시/손중복 영역 채움 노출')
        if any(float(a.get(k,'0'))!=0 for a in aos for k in ['GlowRadius','GlowThickness','GlowAlpha']):raise ValueError('글로우 혼입')
    return dict(frames=len(frames),objects_per_frame=11,body_objects=2,effect_curves=9,fills_per_frame=3,
                unique_points=len(seen),axes_preserved=True,glow_zero=True,app_verified=False)


def save(annotation,event,directory):
    directory=directory.resolve();repo=Path(__file__).resolve().parents[1]
    if directory==repo or repo in directory.parents:raise ValueError('비공개 출력 경로 필요')
    if annotation['source_sha256']!=event['source']['sha256']:raise ValueError('원본 불일치')
    context=C.create(event,0,[r['source_index'] for r in annotation['frames']])
    root,directions=build(annotation);report=inspect(root,annotation,context);directory.mkdir(parents=True,exist_ok=True)
    path=directory/'directional_smear.sfa'
    with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as z:z.writestr('review.xml',ET.tostring(root,encoding='utf-8',xml_declaration=True))
    binding=dict(asset_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),context=context,directions=directions,report=report,
        training_ready=False,app_editing_verified=False,user_guided_reconstruction=True,
        note='팔꿈치 채움 경계는AC접합,공중형태는이동벡터가설. 자동 리그/시간 대응 성공 아님')
    (directory/'directional_smear.binding.json').write_text(json.dumps(binding,ensure_ascii=False,indent=2)+'\n')
    return binding
