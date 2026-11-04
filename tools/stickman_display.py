"""표시 폭·부분 구도·인물 앞뒤 순서. 고정 뼈대/점 연결은 바꾸지 않는다."""
import copy
import numpy as np
from stickman_clip import AO0


def normalize_taper_widths(specs, thickness, radius_per_thickness=2.736):
    """옷 폭을 그대로 면 반지름으로 쓰지 않고 스틱 선과 같은 표시 척도로 맞춘다.

    입력의 부위별 원근 비율은 보존한다. 2.736은 현재 비교 뷰의
    8×1.14×.6 / 2이며,실제3D 거리나 해부학적 두께 추정값이 아니다.
    """
    if not np.isfinite(thickness) or thickness<=0 or not np.isfinite(radius_per_thickness) or radius_per_thickness<=0:
        raise ValueError('양수 표시 굵기/척도가 필요하다')
    result=copy.deepcopy(specs)
    if not result:return result
    values=np.asarray([r for s in result for r in s['radii_px']],float)
    if values.shape!=(2*len(result),) or not np.isfinite(values).all() or (values<=0).any():
        raise ValueError('두 양수 면 반지름이 필요하다')
    factor=float(thickness)*radius_per_thickness/float(np.median(values))
    for s in result:s['radii_px']=(np.asarray(s['radii_px'],float)*factor).tolist()
    return result


def crop_upper_pose(pose,bottom,margin=12.):
    """원본 판독으로 명시한 상체 구도만 처리한다. 머리/팔은 그대로 둔다."""
    result=copy.deepcopy(pose)
    result['_visible_segments']=[o for o in result.get('_visible_segments',range(1,11)) if o<=6]
    if result['pelvis'][1]<=bottom:
        neck,pelvis=np.asarray(result['neck'],float),np.asarray(result['pelvis'],float)
        down=pelvis-neck
        if down[1]>0:result['pelvis']=neck+down*((bottom+margin-neck[1])/down[1])
        else:result['pelvis']=np.array([pelvis[0],bottom+margin])
    return result


def actor_slot(a,colors):
    oid=int(a.get('ID'))
    slot=(oid-AO0)//100
    if 0<=slot<len(colors):return slot
    slot=(oid-96_000_000)//100_000
    if 0<=slot<len(colors):return slot
    raise ValueError('앞뒤 표시 설정이 모르는 객체 ID')


def _key(n):
    return (n.tag,n.get('ID'))


def apply_actor_order(root,events,start,colors=('blue','red')):
    """장면 데이터의 뒤→앞 순서를 DrawOrder와 파일 물리 순서에 함께 적용한다."""
    result=copy.deepcopy(root);frames=result.findall('Frame');used=set();records=[]
    for event in events:
        order=event['back_to_front']
        if sorted(order)!=sorted(colors) or not start<=event['start']<=event['end']<start+len(frames):
            raise ValueError('인물 앞뒤 순서/범위 오류')
        for f in range(event['start'],event['end']+1):
            if f in used:raise ValueError('인물 앞뒤 설정 중복')
            used.add(f);fr=frames[f-start];old_children=[list(_key(n)) for n in fr]
            old={a.get('ID'):a.get('DrawOrder') for a in fr.findall('AO')}
            for a in fr.findall('AO'):
                slot=actor_slot(a,colors);rank=order.index(colors[slot])
                relative=int(a.get('DrawOrder'))-AO0-slot*100
                a.set('DrawOrder',str(AO0+rank*1000+relative))
            objects=sorted(fr.findall('AO'),key=lambda a:int(a.get('DrawOrder')))
            by_id={a.get('ID'):a for a in objects};fills={}
            for fill in fr.findall('FR'):
                owners=[by_id[s.get('ObjId')] for s in fill.findall('FS')]
                key=max(int(a.get('DrawOrder')) for a in owners)
                fills.setdefault(key,[]).append(fill)
            for n in list(fr):
                if n.tag in ('AO','FR'):fr.remove(n)
            for i,a in enumerate(objects):
                fr.append(a);key=int(a.get('DrawOrder'))
                if i+1==len(objects) or int(objects[i+1].get('DrawOrder'))!=key:fr.extend(fills.get(key,[]))
            records.append(dict(frame_index=f-start,frame=f,back_to_front=order,old_orders=old,
                new_orders={a.get('ID'):a.get('DrawOrder') for a in fr.findall('AO')},
                old_children=old_children,new_children=[list(_key(n)) for n in fr]))
    return result,records


def restore_actor_order(root,records):
    """새 표시 순서를 실제 파일과 대조한 뒤 검사/제거용 원래 순서를 복원한다."""
    result=copy.deepcopy(root);frames=result.findall('Frame');used=set()
    for r in records:
        i=r['frame_index']
        if i in used or not 0<=i<len(frames):raise ValueError('앞뒤 표시 기록 중복/범위 오류')
        used.add(i);fr=frames[i]
        if {a.get('ID'):a.get('DrawOrder') for a in fr.findall('AO')}!=r['new_orders']:
            raise ValueError('실제 DrawOrder가 표시 계획과 다르다')
        if [list(_key(n)) for n in fr]!=r['new_children']:
            raise ValueError('실제 파일 물리 순서가 표시 계획과 다르다')
        for a in fr.findall('AO'):a.set('DrawOrder',r['old_orders'][a.get('ID')])
        nodes={_key(n):n for n in fr}
        if len(nodes)!=len(fr) or set(nodes)!=set(map(tuple,r['old_children'])):raise ValueError('표시 순서의 객체/채움 집합 오류')
        for n in list(fr):fr.remove(n)
        fr.extend(nodes[tuple(k)] for k in r['old_children'])
    return result
