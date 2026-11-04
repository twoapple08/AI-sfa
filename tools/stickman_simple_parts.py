"""단순 스틱맨 부속: 명시한 손가락/발바닥 등을 직선 가지로 저장한다."""
import copy
import xml.etree.ElementTree as ET
import numpy as np
from stickman_clip import AO0, STYLE, LINE_COLOR, person_aos


def apply_parts(frame, nodes, edges, actor, slot, frame_index, width, height, crop_y,
                thickness=12., hide_base=False, fallback_pose=None, visible_edges=None):
    """선만 추가한다. nodes는 장면 관측/표시 추론이며 인식 모델의 출력으로 간주하지 않는다."""
    if not nodes or not edges or thickness <= 0:
        raise ValueError('부속 점·선과 양수 굵기가 필요하다')
    nodes={name:np.asarray(value,float) for name,value in nodes.items()}
    if any(v.shape!=(2,) or not np.isfinite(v).all() for v in nodes.values()):
        raise ValueError('부속 좌표는 유한한2D점이어야 한다')
    if any(len(e)!=2 or e[0] not in nodes or e[1] not in nodes for e in edges):
        raise ValueError('부속 가지의 점 이름 오류')
    visible=set(range(len(edges))) if visible_edges is None else set(visible_edges)
    if not visible<=set(range(len(edges))) or len(edges)>400:
        raise ValueError('부속 표시 범위/ID 예약 공간 오류')
    frame=copy.deepcopy(frame);base=AO0+slot*100
    objects={int(a.get('ID')):a for a in frame.findall('AO')};created=False
    if base+1 not in objects and fallback_pose is not None:
        frame.extend(list(ET.fromstring('<Frame>'+person_aos(frame_index,slot,fallback_pose,
            lambda p:(p[0]/(width/100),(p[1]-crop_y)/(height/100)),actor,1.,[])+'</Frame>')))
        objects={int(a.get('ID')):a for a in frame.findall('AO')};created=True
    if not all(base+k in objects for k in range(1,12)):raise ValueError('기본11객체가 필요하다')
    original_colors={str(base+k):objects[base+k].get('Color') for k in range(1,11)}
    original_fills=[]
    if hide_base:
        for k in range(1,11):objects[base+k].set('Color','0')
        for f in list(frame.findall('FR')):
            if any(int(s.get('ObjId'))==base+1 for s in f.findall('FS')):
                original_fills.append(ET.tostring(f,encoding='unicode'));frame.remove(f)
    sx,sy=width/100,height/100;point_id=400_000_000+frame_index*10000+slot*1000
    ids=[];points_by_name={};first=95_000_000+slot*10000
    def link(a,b):
        ET.SubElement(a,'AC',ConnPtId=b.get('ID'));ET.SubElement(b,'AC',ConnPtId=a.get('ID'))
    def make(oid,a,b,color,scale):
        nonlocal point_id
        if oid in objects:raise ValueError('부속 객체ID 충돌')
        obj=ET.fromstring(f'<AO ID="{oid}" TypeId="1" DrawOrder="{base+6}" '+STYLE.format(c=color,th=f'{scale:.3f}')+'/>')
        for k,v in enumerate([a,b]):
            ET.SubElement(obj,'AP',ID=str(point_id),Index=str(k),Flags='4' if k==0 else '5',X=f'{v[0]/sx:.4f}',Y=f'{(v[1]-crop_y)/sy:.4f}');point_id+=1
        frame.append(obj);ids.append(oid);return obj
    # 선 픽셀 굵기와 SFA 저장 굵기를 분리한다(기존 서버 표시 기준).
    for index,(a,b) in enumerate(edges):
        obj=make(first+index,nodes[a],nodes[b],LINE_COLOR[actor] if index in visible else 0,thickness/(8*1.14*.6))
        for name,p in zip((a,b),obj.findall('AP')):
            if name in points_by_name:link(points_by_name[name],p)
            else:points_by_name[name]=p
    # 분리된 발/손 가지도 같은 편집망에 속하도록 투명 연결만 더한다.
    adjacency={k:set() for k in nodes}
    for a,b in edges:adjacency[a].add(b);adjacency[b].add(a)
    remaining=set(points_by_name);component=0
    base_points=[p for k in range(1,12) for p in objects[base+k].findall('AP')]
    xy=lambda p:np.array([float(p.get('X'))*sx,float(p.get('Y'))*sy+crop_y])
    while remaining:
        start=sorted(remaining)[0];pending=[start];visited=set()
        while pending:
            name=pending.pop()
            if name not in visited:visited.add(name);pending.extend(adjacency[name]-visited)
        remaining-=visited
        _,anchor,point=min([(float(np.linalg.norm(xy(a)-xy(points_by_name[n]))),a,points_by_name[n])
                           for n in visited for a in base_points],key=lambda item:item[0])
        if all(anchor.get(k)==point.get(k) for k in ('X','Y')):link(anchor,point)
        else:
            spoke=make(first+5000+component,xy(anchor),xy(point),0,.1);component+=1
            link(anchor,spoke.findall('AP')[0]);link(point,spoke.findall('AP')[1])
    return frame,dict(actor=actor,slot=slot,frame_index=frame_index,added_objects=ids,added_fills=[],
        original_colors=original_colors,original_fills=original_fills,created_hidden_base=created,
        representation='simple-parts-v1',visible_lines=len(visible),curves=0)
