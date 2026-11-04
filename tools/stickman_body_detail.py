"""명시한 근경 신체 구도의 선택 면 표시층. 동작 뼈대와 원본 판독은 별도로 보존한다."""
import copy
import xml.etree.ElementTree as ET
import cv2
import numpy as np
from stickman_clip import AO0, STYLE, LINE_COLOR


def fit_contour(points, tolerance=4.):
    """픽셀마다 객체를 만들지 않고 오차 기준으로 긴2차 곡선을 적응 분할한다."""
    points=np.asarray(points,float)
    if len(points)<4 or tolerance<=0:
        raise ValueError('닫힌 윤곽/양수 오차가 필요하다')
    curves=[]
    def fit(p):
        if len(p)==2:
            curves.append(np.array([p[0],(p[0]+p[-1])/2,p[-1]]));return
        distance=np.r_[0,np.cumsum(np.linalg.norm(np.diff(p,axis=0),axis=1))]
        if distance[-1]<1e-8:return
        t=distance/distance[-1];w=2*t*(1-t)
        control=np.sum(w[:,None]*(p-(1-t[:,None])**2*p[0]-t[:,None]**2*p[-1]),axis=0)/max(float(w@w),1e-12)
        pred=(1-t[:,None])**2*p[0]+w[:,None]*control+t[:,None]**2*p[-1]
        error=np.linalg.norm(pred-p,axis=1);split=int(error.argmax())
        if error[split]<=tolerance or split in (0,len(p)-1):
            curves.append(np.array([p[0],control,p[-1]]));return
        fit(p[:split+1]);fit(p[split:])
    # 닫힌 선의 같은 시작/끝 때문에 퇴화하지 않게 가장 먼 지점에서 나눈다.
    split=int(np.linalg.norm(points-points[0],axis=1).argmax())
    fit(points[:split+1]);fit(np.vstack([points[split:],points[0]]))
    return curves


def mask_curves(mask, tolerance=4., component_ratio=.03, edge_bounds=None):
    if not 0 < component_ratio <= 1:raise ValueError('영역 비율은0초과1이하여야 한다')
    mask=np.asarray(mask,dtype=np.uint8)
    # 원본의 가는 빨간 작업 메모/화살표를 신체 면으로 옮기지 않는다.
    # 같은 색의 굵은 연출은 이 조건만으로 분리할 수 없으므로 구도 판독이 필요하다.
    mask=cv2.morphologyEx(mask,cv2.MORPH_OPEN,cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(5,5)))
    mask=cv2.morphologyEx(mask,cv2.MORPH_CLOSE,cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(5,5)))
    contours,_=cv2.findContours(mask,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_NONE)
    if not contours:raise ValueError('근경 신체 색 영역이 없다')
    largest=max(cv2.contourArea(c) for c in contours)
    if largest<100:raise ValueError('신체 형태를 잴 영역이 부족하다')
    selected=[c for c in contours if cv2.contourArea(c)>=max(100,largest*component_ratio)]
    if edge_bounds is not None:
        left,right,top,bottom=edge_bounds
        selected=[c for c in selected if any((c[:,0,0]<=left+2)|(c[:,0,0]>=right-2)|
                                            (c[:,0,1]<=top+2)|(c[:,0,1]>=bottom-2))]
    if not selected:raise ValueError('명시한 경계에 연결되는 신체 영역이 없다')
    selected.sort(key=lambda c:tuple(c.reshape(-1,2).min(axis=0)))
    return [fit_contour(c[:,0,:],tolerance) for c in selected]


def apply_detail(frame, contours, actor, slot, frame_index, width, height, crop_y, fallback_pose=None):
    """11객체는 숨겨 보존하고 곡선 면을 투명 가지로 같은 인물 편집망에 연결한다."""
    frame=copy.deepcopy(frame);base=AO0+slot*100
    objects={int(a.get('ID')):a for a in frame.findall('AO')}
    created_base=False
    if base+1 not in objects and fallback_pose is not None:
        from stickman_clip import person_aos
        fragment=ET.fromstring('<Frame>'+person_aos(frame_index,slot,fallback_pose,
            lambda p:(p[0]/(width/100),(p[1]-crop_y)/(height/100)),actor,1.,[])+'</Frame>')
        frame.extend(list(fragment));objects={int(a.get('ID')):a for a in frame.findall('AO')};created_base=True
    if not all(base+k in objects for k in range(1,12)):
        raise ValueError('상세 표시층의 기본11객체가 필요하다')
    original_colors={str(base+k):objects[base+k].get('Color') for k in range(1,11)}
    original_fills=[]
    for k in range(1,11):objects[base+k].set('Color','0')
    for fill in list(frame.findall('FR')):
        if any(int(s.get('ObjId'))==base+1 for s in fill.findall('FS')):
            original_fills.append(ET.tostring(fill,encoding='unicode'));frame.remove(fill)
    anchor=objects[base+6].findall('AP')[0]
    sx,sy=width/100,height/100
    first_id=90_000_000+slot*100_000
    point_id=200_000_000+frame_index*100_000+slot*10_000
    ids=[];fills=[];cursor=0
    def link(a,b):
        ET.SubElement(a,'AC',ConnPtId=b.get('ID'));ET.SubElement(b,'AC',ConnPtId=a.get('ID'))
    def node(kind,xy,oid=None):
        nonlocal cursor,point_id
        oid=first_id+cursor if oid is None else oid;cursor+=1
        if oid in objects:raise ValueError('상세 객체ID 충돌')
        a=ET.fromstring(f'<AO ID="{oid}" TypeId="{kind}" DrawOrder="{base+5}" '+STYLE.format(c=0,th='.100')+'/>')
        for i,v in enumerate(xy):
            ET.SubElement(a,'AP',ID=str(point_id),Index=str(i),Flags='4',X=f'{v[0]/sx:.4f}',Y=f'{(v[1]-crop_y)/sy:.4f}');point_id+=1
        frame.append(a);ids.append(oid);return a
    for contour_index,curves in enumerate(contours):
        if not curves:raise ValueError('빈 신체 윤곽')
        nodes=[node('3',curve) for curve in curves]
        for i,a in enumerate(nodes):link(a.findall('AP')[-1],nodes[(i+1)%len(nodes)].findall('AP')[0])
        start=nodes[0].findall('AP')[0]
        xy=lambda p:np.array([float(p.get('X'))*sx,float(p.get('Y'))*sy+crop_y])
        spoke=node('1',[xy(anchor),xy(start)],first_id+50_000+contour_index);link(anchor,spoke.findall('AP')[0]);link(start,spoke.findall('AP')[1])
        fill=ET.SubElement(frame,'FR',ID=str(190_000_000+frame_index*10_000+slot*1000+contour_index),Color=str(LINE_COLOR[actor]));fills.append(int(fill.get('ID')))
        for a in nodes:
            pts=a.findall('AP');ET.SubElement(fill,'FS',Kind='0',ObjId=a.get('ID'),StartPtId=pts[0].get('ID'),EndPtId=pts[-1].get('ID'),StartT='0',EndT='1',Contour='0')
    if cursor>=50_000 or len(contours)>=1000 or point_id>=200_000_000+frame_index*100_000+(slot+1)*10_000:
        raise ValueError('상세 표시층ID 예약 공간 초과')
    return frame,dict(actor=actor,slot=slot,added_objects=ids,added_fills=fills,curves=sum(map(len,contours)),original_colors=original_colors,original_fills=original_fills,created_hidden_base=created_base,representation='body-detail-curves-v1')


def strip_and_check(root, records):
    """표시층 전체의 연결을 검사한 뒤 원래 뼈대 표시를 복원한다."""
    result=copy.deepcopy(root);seen=set();types={}
    for frame in result.findall('Frame'):
        for a in frame.findall('AO'):
            if a.get('ID') in types and types[a.get('ID')]!=a.get('TypeId'):
                raise ValueError('장간 객체 형식 변화')
            types[a.get('ID')]=a.get('TypeId')
            for p in a.findall('AP'):
                if p.get('ID') in seen:raise ValueError('장간 점ID 중복')
                seen.add(p.get('ID'))
    for record in records:
        frame=result.findall('Frame')[record['frame_index']];base=AO0+record['slot']*100
        ids=set(record['added_objects']);aos=frame.findall('AO')
        nodes=[a for a in aos if int(a.get('ID')) in ids or base<int(a.get('ID'))<base+12]
        if len(nodes)!=11+len(ids):raise ValueError('상세 표시 객체 누락/중복')
        points={p.get('ID'):p for a in nodes for p in a.findall('AP')}
        graph={k:set() for k in points}
        if sum(p.get('Flags')=='3' for p in points.values())!=1:raise ValueError('인물 파란점 수 오류')
        for a in nodes:
            pp=a.findall('AP')
            for x,y in zip(pp,pp[1:]):graph[x.get('ID')].add(y.get('ID'));graph[y.get('ID')].add(x.get('ID'))
        for pid,p in points.items():
            for c in p.findall('AC'):
                q=points.get(c.get('ConnPtId'))
                if q is None or any(p.get(k)!=q.get(k) for k in ('X','Y')) or pid not in [cc.get('ConnPtId') for cc in q.findall('AC')]:
                    raise ValueError('상세 표시 연결 분리/인물 혼입')
                graph[pid].add(q.get('ID'))
        reached=set();pending=[next(iter(points))]
        while pending:
            pid=pending.pop()
            if pid not in reached:reached.add(pid);pending.extend(graph[pid]-reached)
        if len(reached)!=len(points):raise ValueError('상세 표시가 뼈대에서 분리됨')
        by_id={a.get('ID'):a for a in nodes}
        expected_curves={a.get('ID') for a in nodes if int(a.get('ID')) in ids and a.get('TypeId')=='3'}
        actual_curves=[]
        if {int(f.get('ID')) for f in frame.findall('FR') if int(f.get('ID')) in record['added_fills']}!=set(record['added_fills']):
            raise ValueError('상세 채움 누락')
        for fill in frame.findall('FR'):
            if int(fill.get('ID')) not in record['added_fills']:continue
            for fs in fill.findall('FS'):
                a=by_id.get(fs.get('ObjId'))
                if a is None or a.get('TypeId')!='3' or fs.get('Kind')!='0':raise ValueError('상세 채움 객체/종류 오류')
                actual_curves.append(a.get('ID'))
                if fs.get('StartT')!='0' or fs.get('EndT')!='1' or fs.get('Contour')!='0':raise ValueError('상세 채움 구간 오류')
                pp=a.findall('AP')
                if fs.get('StartPtId')!=pp[0].get('ID') or fs.get('EndPtId')!=pp[-1].get('ID'):raise ValueError('상세 채움 끝점 오류')
        if set(actual_curves)!=expected_curves or len(actual_curves)!=len(expected_curves):raise ValueError('상세 채움 경계 누락/중복')
        extra={p.get('ID') for a in nodes if int(a.get('ID')) in ids for p in a.findall('AP')}
        for p in frame.iter('AP'):
            for c in list(p):
                if c.get('ConnPtId') in extra:p.remove(c)
        for a in nodes:
            if int(a.get('ID')) in ids:frame.remove(a)
        for fill in list(frame.findall('FR')):
            if int(fill.get('ID')) in record['added_fills']:frame.remove(fill)
        for a in frame.findall('AO'):
            if a.get('ID') in record['original_colors']:a.set('Color',record['original_colors'][a.get('ID')])
        for xml in record['original_fills']:frame.append(ET.fromstring(xml))
        if record.get('created_hidden_base'):
            for a in list(frame.findall('AO')):
                if base<int(a.get('ID'))<base+12:frame.remove(a)
    return result
