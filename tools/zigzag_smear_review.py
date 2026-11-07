"""불투명 지그재그 선 스미어. 폭은 이동 화살표가 아닌 팔/몸 바깥쪽 기준이다."""
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET
import zipfile
import numpy as np
import event_context as C
import no_glow_smear_review as BASE


def motion(annotation, index):
    points=[np.asarray(r['points_px'][2],float) for r in annotation['frames']]
    current=points[index]
    previous=next((p for p in reversed(points[:index]) if np.linalg.norm(current-p)>1e-6),None)
    following=next((p for p in points[index+1:] if np.linalg.norm(current-p)>1e-6),None)
    delta=current-previous if previous is not None else following-current if following is not None else np.zeros(2)
    distance=float(np.linalg.norm(delta))
    return delta/max(distance,1e-9),distance


def zigzag(near, far, near_width, far_width, segments=14, bend=0):
    near,far=np.asarray(near,float),np.asarray(far,float)
    d=far-near;length=float(np.linalg.norm(d))
    if not isinstance(segments,int) or isinstance(segments,bool) or segments<2 or length<1e-6 or near_width<0 or far_width<=0 or not np.isfinite([*near,*far,near_width,far_width,bend]).all():
        raise ValueError('유효한 지그재그 크기/분할이 필요하다')
    normal=np.array([-d[1],d[0]])/length
    teeth=[1.,.84,1.08,.92,1.12,.88]
    return np.array([near+d*t+normal*(bend*np.sin(np.pi*t)+(-1 if k%2 else 1)*
                       ((1-t)*near_width+t*far_width)*teeth[k%len(teeth)]/2)
                    for k,t in enumerate(np.linspace(0,1,segments+1))])


def geometry(annotation,index,segments=14):
    row=annotation['frames'][index]
    elbow,wrist=np.asarray(row['points_px'][1],float),np.asarray(row['points_px'][2],float)
    direction,distance=motion(annotation,index)
    outer_width=max(4.,distance*.12) # 검토 계수. 실제 물리 속도/작가 스타일을 추정한 값이 아님.
    arm=zigzag(elbow,wrist,0,outer_width,segments)
    floating=[]
    for area in row['smears']:
        center=np.asarray(area['center_px'],float);width,extent=np.asarray(area['size_px'],float)
        radial=center-elbow;norm=float(np.linalg.norm(radial))
        if norm<1e-6 or not np.isfinite([*center,width,extent]).all() or min(width,extent)<=0:
            raise ValueError('공중 영역의 바깥쪽 기준이 필요하다')
        radial/=norm;normal=np.array([-radial[1],radial[0]])
        span=width*.9+distance*.035
        # 팔꿈치에서 먼 경계가 넓다. 운동 방향은 휨에만 관여하고 폭의 극성을 뒤집지 않는다.
        floating.append(zigzag(center-radial*extent/2,center+radial*extent/2,
                               span*.55,span,segments,float(np.dot(direction,normal))*extent*.12))
    return [arm]+floating,dict(display_step_distance_px=distance,outer_arm_span_px=outer_width,
                              expansion_reference='팔꿈치에서 더 먼 부위/경계',motion_role='선의 벌어짐 크기와 휨; 넓은 쪽 선택 기준 아님')


def build(annotation,segments=14):
    root=BASE.build(annotation,False);root.set('Name','opaque_zigzag_smear_review')
    width,height=annotation['image_size'];records=[]
    for n,(frame,row) in enumerate(zip(root.findall('Frame'),annotation['frames'])):
        ET.SubElement(frame,'LayerDef',ID='1',Name='zigzag_smear',Visible='true',Locked='false')
        groups,record=geometry(annotation,n,segments);records.append(record)
        for g,points in enumerate(groups):
            base=50000000+n*(3*2*segments)+g*(2*segments)
            for k in range(segments):
                oid=9900000+g*segments+k
                ao=ET.SubElement(frame,'AO',ID=str(oid),TypeId='1',LayerId='1',DrawOrder=str(oid),
                    Color=str(0xff0000ff if row['smear_active'] else 0),ThicknessScale='.38',ObjectScale='1',
                    GlowRadius='0',GlowThickness='0',GlowColor='0',GlowAlpha='0')
                for j,point in enumerate(points[k:k+2]):
                    pid=base+k*2+j
                    ap=ET.SubElement(ao,'AP',ID=str(pid),Index=str(j),Flags='4' if j==0 and (k>0 or g==0) else '9',
                        X=f'{point[0]/width*100:.6f}',Y=f'{point[1]/height*100:.6f}')
                    if j==0 and k>0:ET.SubElement(ap,'AC',ConnPtId=str(pid-1))
                    if j==1 and k<segments-1:ET.SubElement(ap,'AC',ConnPtId=str(pid+1))
                    if (g,k,j)==(0,0,0):
                        joint=frame.findall('AO')[1].find('AP')
                        ET.SubElement(ap,'AC',ConnPtId=joint.get('ID'));ET.SubElement(joint,'AC',ConnPtId=str(pid))
    return root,records


def inspect(root,annotation,context,segments=14):
    C.validate(context);plain=BASE.build(annotation,False);frames=root.findall('Frame');seen=set()
    if len(frames)!=len(annotation['frames']) or len(frames)!=len(context['source_indices']):raise ValueError('장 수 불일치')
    for n,(f,row) in enumerate(zip(frames,annotation['frames'])):
        aos=f.findall('AO');points=[p for a in aos for p in a.findall('AP')];by={p.get('ID'):p for p in points}
        if f.findall('FR') or f.findall('.//FS'):raise ValueError('채움 금지')
        if len(aos)!=2+3*segments or len(by)!=4+6*segments or len(points)!=len(by) or seen&by.keys():raise ValueError('객체/점 오류')
        seen.update(by)
        if row['source_index']!=context['source_indices'][n] or int(f.get('Position'))!=n:raise ValueError('장 대응 오류')
        for old,new in zip(plain.findall('Frame')[n].findall('AO'),aos[:2]):
            if old.attrib!=new.attrib or [p.attrib for p in old.findall('AP')]!=[p.attrib for p in new.findall('AP')]:raise ValueError('팔축 변경')
        for k,a in enumerate(aos[2:]):
            if a.get('ID')!=str(9900000+k) or a.get('TypeId')!='1':raise ValueError('직선 대상 불일치')
            if int(a.get('Color'))!=(0xff0000ff if row['smear_active'] else 0):raise ValueError('불투명/표시 상태 오류')
        for a in aos:
            if any(float(a.get(k,'0')) for k in ['GlowRadius','GlowThickness','GlowAlpha']):raise ValueError('글로우 금지')
        for p in points:
            for c in p.findall('AC'):
                q=by.get(c.get('ConnPtId'))
                if q is None or any(p.get(k)!=q.get(k) for k in ('X','Y')):raise ValueError('지그재그 연결 오류')
        for g in range(3):
            for k in range(segments-1):
                left=aos[2+g*segments+k].findall('AP')[1];right=aos[3+g*segments+k].find('AP')
                if right.get('ID') not in [c.get('ConnPtId') for c in left.findall('AC')]:raise ValueError('연속 선 사슬 소실')
    return dict(frames=len(frames),body_objects=2,effect_line_objects=3*segments,fill_count=0,
                active_alpha=255,unique_points=len(seen),axes_preserved=True,app_verified=False)


def save(annotation,event,directory,segments=14):
    directory=directory.resolve();repo=Path(__file__).resolve().parents[1]
    if directory==repo or repo in directory.parents:raise ValueError('비공개 출력 필요')
    if annotation['source_sha256']!=event['source']['sha256']:raise ValueError('원본 불일치')
    context=C.create(event,0,[r['source_index'] for r in annotation['frames']])
    root,records=build(annotation,segments);report=inspect(root,annotation,context,segments)
    directory.mkdir(parents=True,exist_ok=True);path=directory/'zigzag_smear.sfa'
    with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as z:z.writestr('review.xml',ET.tostring(root,encoding='utf-8',xml_declaration=True))
    result=dict(asset_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),context=context,shape_records=records,report=report,
                training_ready=False,user_guided_reconstruction=True,segments_per_group=segments,
                note='공중 넓은 쪽은 팔꿈치에서 먼 경계라는 수동 해석. 실제 손 회전축/공중 시간 대응 미확정')
    (directory/'zigzag_smear.binding.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    return result
