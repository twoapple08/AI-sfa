"""검토용: 지그재그 반환 구간을 길게 뻗는 수동 표현 실험. 원본 자동 복원 아님."""
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET
import zipfile
import numpy as np
import joined_zigzag_review as J
import event_context as C


def elongate(points, near, far, attached=False):
    points=np.asarray(points,float);near=np.asarray(near,float);far=np.asarray(far,float)
    axis=far-near;length=float(np.linalg.norm(axis));axis/=length
    t=np.linspace(0,1,len(points));amount=min(30.,length*.38)
    # 획 끝을 번갈아 앞뒤로 뻗는다. 선 개수와 횡폭은 유지하고 가장자리는 길게 뻗는다.
    envelope=t**.8 if attached else np.ones(len(points))
    offset=np.where(np.arange(len(points))%2,1.,-1.)*amount*envelope
    result=points+offset[:,None]*axis
    if attached:result[0]=points[0]
    return result


def build(annotation,segments=38):
    root,capacity,records=J.build(annotation,segments)
    width,height=annotation['image_size']
    for i,(frame,row) in enumerate(zip(root.findall('Frame'),annotation['frames'])):
        shapes,visible,record=J.plan(annotation,i,segments)
        elbow,wrist=np.asarray(row['points_px'][1],float),np.asarray(row['points_px'][2],float)
        for g,points in enumerate(shapes):
            if g==0:
                near,far=elbow,wrist
                if record['merged_group'] is not None:
                    area=row['smears'][record['merged_group']-1];center=np.asarray(area['center_px'],float)
                    radial=center-elbow;radial/=np.linalg.norm(radial)
                    far=center+radial*area['size_px'][1]/2
            else:
                area=row['smears'][g-1];center=np.asarray(area['center_px'],float)
                radial=center-elbow;radial/=np.linalg.norm(radial)
                near,far=center-radial*area['size_px'][1]/2,center+radial*area['size_px'][1]/2
            new=list(elongate(points,near,far,attached=g==0));count=len(new)-1
            while len(new)<capacity[g]+1:new.append(new[count-1] if (len(new)-count-1)%2==0 else new[count])
            nodes=frame.findall('AO')[2+sum(capacity[:g]):2+sum(capacity[:g+1])]
            for k,node in enumerate(nodes):
                for p,xy in zip(node.findall('AP'),new[k:k+2]):
                    p.set('X',f'{xy[0]/width*100:.6f}');p.set('Y',f'{xy[1]/height*100:.6f}')
        records[i]['return_stroke_extension']='축방향 교대 연장, 최대 min(30px,전체길이*.38);검토 계수'
    root.set('Name','elongated_zigzag_review')
    return root,capacity,records


def save(annotation,event,directory,segments=38):
    directory=Path(directory).resolve();repo=Path(__file__).resolve().parents[1]
    if directory==repo or repo in directory.parents:raise ValueError('비공개 출력 필요')
    if annotation['source_sha256']!=event['source']['sha256']:raise ValueError('원본 불일치')
    context=C.create(event,0,[r['source_index'] for r in annotation['frames']])
    root,cap,records=build(annotation,segments);report=J.inspect(root,annotation,context,cap,records)
    directory.mkdir(parents=True,exist_ok=True);path=directory/'elongated_smear.sfa'
    with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as z:z.writestr('review.xml',ET.tostring(root,encoding='utf-8',xml_declaration=True))
    result=dict(asset_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),context=context,records=records,report=report,
                training_ready=False,user_guided_reconstruction=True,app_editing_verified=False)
    (directory/'elongated_smear.binding.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    return result
