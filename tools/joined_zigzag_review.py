"""겹친 팔/공중 지그재그 두 개를 하나의 길이로 재구성하는 검토 도구."""
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET
import zipfile
import numpy as np
import event_context as C
import no_glow_smear_review as BASE
import zigzag_smear_review as Z


def plan(annotation,index,segments=38):
    row=annotation['frames'][index];shapes,record=Z.geometry(annotation,index,segments)
    elbow,wrist=np.asarray(row['points_px'][1],float),np.asarray(row['points_px'][2],float)
    arm=wrist-elbow;length=float(np.linalg.norm(arm));unit=arm/length
    candidates=[]
    for g,area in enumerate(row['smears'],1):
        center=np.asarray(area['center_px'],float);width,extent=area['size_px']
        radial=center-elbow;r=float(np.linalg.norm(radial));radial/=r
        near,far=center-radial*extent/2,center+radial*extent/2
        lo,hi=float(np.dot(near-elbow,unit)),float(np.dot(far-elbow,unit))
        overlap=min(length,hi)-max(0.,lo)
        if float(np.dot(radial,unit))>=np.cos(np.deg2rad(20)) and overlap>0 and hi>length:
            candidates.append((overlap,g,far,width*.9+record['display_step_distance_px']*.035,extent))
    visible=[bool(row['smear_active'])]*3
    result=dict(merged_group=None,visible_segments=[segments]*3,merge_scope='단일 팔/공중 쌍,근사 방사방향 구간 겹침')
    if candidates and row['smear_active']:
        _,g,far,far_width,extent=max(candidates,key=lambda x:x[0])
        joined_length=float(np.linalg.norm(far-elbow))
        pitch=min(length/segments,extent/segments)
        count=int(np.ceil(joined_length/pitch));count+=count%2
        shapes[0]=Z.zigzag(elbow,far,0,max(record['outer_arm_span_px'],far_width),count)
        visible[g]=False
        result.update(merged_group=g,visible_segments=[count,segments,segments],
                      old_arm_length_px=length,joined_length_px=joined_length,
                      original_pitch_px=pitch,new_pitch_px=joined_length/count)
    return shapes,visible,result


def build(annotation,segments=38):
    plans=[plan(annotation,i,segments) for i in range(len(annotation['frames']))]
    capacity=[max(len(p[0][g])-1 for p in plans) for g in range(3)]
    root=BASE.build(annotation,False);root.set('Name','single_length_zigzag_review')
    width,height=annotation['image_size'];stride=2*sum(capacity)
    for n,(frame,(shapes,visible,record)) in enumerate(zip(root.findall('Frame'),plans)):
        ET.SubElement(frame,'LayerDef',ID='1',Name='joined_smear',Visible='true',Locked='false')
        for g,shape in enumerate(shapes):
            count=len(shape)-1;points=list(shape)
            # 장간 ID를 유지하는 비표시 여분 선. 길이0 대신 마지막 구간 왕복으로 보존한다.
            while len(points)<capacity[g]+1:points.append(shape[-2] if (len(points)-len(shape))%2==0 else shape[-1])
            base=60000000+n*stride+2*sum(capacity[:g]);offset=sum(capacity[:g])
            for k in range(capacity[g]):
                oid=10000000+offset+k;active=visible[g] and k<count
                a=ET.SubElement(frame,'AO',ID=str(oid),TypeId='1',LayerId='1',DrawOrder=str(oid),
                    Color=str(0xff0000ff if active else 0),ThicknessScale='.38',ObjectScale='1',
                    GlowRadius='0',GlowThickness='0',GlowColor='0',GlowAlpha='0')
                for j,point in enumerate(points[k:k+2]):
                    pid=base+k*2+j
                    p=ET.SubElement(a,'AP',ID=str(pid),Index=str(j),Flags='4' if j==0 and (k>0 or g==0) else '9',
                        X=f'{point[0]/width*100:.6f}',Y=f'{point[1]/height*100:.6f}')
                    if j==0 and k>0:ET.SubElement(p,'AC',ConnPtId=str(pid-1))
                    if j==1 and k<capacity[g]-1:ET.SubElement(p,'AC',ConnPtId=str(pid+1))
                    if (g,k,j)==(0,0,0):
                        joint=frame.findall('AO')[1].find('AP');ET.SubElement(p,'AC',ConnPtId=joint.get('ID'));ET.SubElement(joint,'AC',ConnPtId=str(pid))
    return root,capacity,[dict(record,shape_visible=visible) for _,visible,record in plans]


def inspect(root,annotation,context,capacity,records):
    C.validate(context);plain=BASE.build(annotation,False);seen=set();frames=root.findall('Frame')
    if len(frames)!=len(annotation['frames']) or len(frames)!=len(context['source_indices']):raise ValueError('장 수 불일치')
    for n,(f,row,record) in enumerate(zip(frames,annotation['frames'],records)):
        aos=f.findall('AO');points=[p for a in aos for p in a.findall('AP')];by={p.get('ID'):p for p in points}
        if f.findall('FR') or f.findall('.//FS'):raise ValueError('채움 금지')
        if len(aos)!=2+sum(capacity) or len(points)!=4+2*sum(capacity) or len(by)!=len(points) or seen&by.keys():raise ValueError('ID/개수 오류')
        seen.update(by)
        if int(f.get('Position'))!=n or row['source_index']!=context['source_indices'][n]:raise ValueError('장 대응 오류')
        for a,b in zip(plain.findall('Frame')[n].findall('AO'),aos[:2]):
            if a.attrib!=b.attrib or [p.attrib for p in a.findall('AP')]!=[p.attrib for p in b.findall('AP')]:raise ValueError('팔 축 변경')
        for g in range(3):
            nodes=aos[2+sum(capacity[:g]):2+sum(capacity[:g+1])]
            for k,a in enumerate(nodes):
                expected=0xff0000ff if record['shape_visible'][g] and k<record['visible_segments'][g] else 0
                if int(a.get('Color'))!=expected:raise ValueError('겹친 묶음/여분선이 남았거나 불투명 아님')
        for a in aos:
            if any(float(a.get(k,'0')) for k in ['GlowRadius','GlowThickness','GlowAlpha']):raise ValueError('글로우 금지')
        for p in points:
            for c in p.findall('AC'):
                q=by.get(c.get('ConnPtId'))
                if q is None or any(p.get(k)!=q.get(k) for k in ['X','Y']):raise ValueError('연결 오류')
    return dict(frames=len(frames),capacity_per_group=capacity,unique_points=len(seen),
                merged_source_indices=[annotation['frames'][i]['source_index'] for i,r in enumerate(records) if r['merged_group'] is not None],
                fill_count=0,active_alpha=255,axes_preserved=True,app_verified=False)


def save(annotation,event,directory,segments=38):
    directory=directory.resolve();repo=Path(__file__).resolve().parents[1]
    if directory==repo or repo in directory.parents:raise ValueError('비공개 출력 필요')
    if annotation['source_sha256']!=event['source']['sha256']:raise ValueError('원본 불일치')
    context=C.create(event,0,[r['source_index'] for r in annotation['frames']]);root,capacity,records=build(annotation,segments)
    report=inspect(root,annotation,context,capacity,records);directory.mkdir(parents=True,exist_ok=True)
    path=directory/'single_length_smear.sfa'
    with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as z:z.writestr('review.xml',ET.tostring(root,encoding='utf-8',xml_declaration=True))
    result=dict(asset_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),context=context,records=records,report=report,
        training_ready=False,user_guided_reconstruction=True,app_editing_verified=False)
    (directory/'single_length_smear.binding.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    return result
