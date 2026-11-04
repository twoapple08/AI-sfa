"""스틱맨 중심선의 폭을 연속 면으로 표시한다. 사람 외곽 추적은 사용하지 않는다."""
import copy
import xml.etree.ElementTree as ET
import numpy as np
from stickman_limb_surface import contour
from stickman_clip import AO0, STYLE, LINE_COLOR


def apply_tapered_parts(frame, specs, actor, slot, frame_index, width, height, crop_y):
    result=copy.deepcopy(frame);objects={int(a.get('ID')):a for a in result.findall('AO')}
    sx,sy=width/100,height/100
    xy=lambda p:np.array([float(p.get('X'))*sx,float(p.get('Y'))*sy+crop_y])
    ids=[];fills=[];colors={};seen=set()
    def link(a,b):
        ET.SubElement(a,'AC',ConnPtId=b.get('ID'));ET.SubElement(b,'AC',ConnPtId=a.get('ID'))
    for spec in specs:
        oid,index=spec['object_id'],spec['index'];r=np.array(spec['radii_px'],float)
        if index in seen or not 0<=index<100 or r.shape!=(2,) or not np.isfinite(r).all() or (r<=0).any():
            raise ValueError('면 인덱스/두 양수 반지름 오류')
        seen.add(index);a=objects.get(oid)
        if a is None or a.get('TypeId')!='1' or not int(a.get('Color'))&0xff000000:
            raise ValueError('면을 표시할 가시 직선이 없다')
        source=a.findall('AP');p,q=map(xy,source)
        curves=contour([p,(p+q)/2,q],[r[0],r.mean(),r[1]])
        first=96_000_000+slot*100_000+index*100
        point=700_000_000+frame_index*500_000+slot*200_000+index*1000
        def node(k,typ,points):
            nonlocal point
            identifier=first+k
            if identifier in objects:raise ValueError('연속 면 객체ID 충돌')
            n=ET.fromstring(f'<AO ID="{identifier}" TypeId="{typ}" DrawOrder="{a.get("DrawOrder")}" '+STYLE.format(c=0,th='.100')+'/>')
            for j,v in enumerate(points):
                ET.SubElement(n,'AP',ID=str(point),Index=str(j),Flags='4',X=f'{v[0]/sx:.4f}',Y=f'{(v[1]-crop_y)/sy:.4f}');point+=1
            result.append(n);ids.append(identifier);return n
        nodes=[node(k,'3',c) for k,c in enumerate(curves)]
        for k in range(10):link(nodes[k].findall('AP')[-1],nodes[(k+1)%10].findall('AP')[0])
        for k,(anchor,boundary) in enumerate(zip(source,[nodes[0].findall('AP')[0],nodes[0].findall('AP')[-1]])):
            spoke=node(10+k,'1',[xy(anchor),xy(boundary)])
            link(anchor,spoke.findall('AP')[0]);link(boundary,spoke.findall('AP')[1])
        fid=300_000_000+frame_index*1000+slot*100+index
        fill=ET.SubElement(result,'FR',ID=str(fid),Color=str(LINE_COLOR[actor]));fills.append(fid)
        for n in nodes:
            pp=n.findall('AP');ET.SubElement(fill,'FS',Kind='0',ObjId=n.get('ID'),StartPtId=pp[0].get('ID'),EndPtId=pp[-1].get('ID'),StartT='0',EndT='1',Contour='0')
        colors[str(oid)]=a.get('Color');a.set('Color','0')
    return result,dict(actor=actor,slot=slot,frame_index=frame_index,added_objects=ids,added_fills=fills,
        original_colors=colors,original_fills=[],created_hidden_base=False,representation='tapered-parts-v1',curves=10*len(specs))


def strip_tapered(root,records):
    """단순 부속 등 다른 표시층을 보존하고 이 면의 연결/채움만 검사·제거한다."""
    from stickman_body_detail import strip_and_check
    result=copy.deepcopy(root)
    # 공통 검사기는 기본11객체를 기대하므로 같은 인물의 선 부속도 검사 대상에 포함한다.
    combined=[]
    for record in records:
        r=copy.deepcopy(record);frame=result.findall('Frame')[r['frame_index']];base=AO0+r['slot']*100
        extra=[int(a.get('ID')) for a in frame.findall('AO')
               if 95_000_000+r['slot']*10000<=int(a.get('ID'))<95_000_000+(r['slot']+1)*10000]
        r['added_objects']+=extra;combined.append(r)
    # 원래 선 부속을 별도 복원: 검사 때만 같이 제거하며 면에 붙은 AC는 남기지 않는다.
    saved={}
    for r in records:
        fr=result.findall('Frame')[r['frame_index']]
        saved[r['frame_index']]=copy.deepcopy(fr)
    strip_and_check(result,combined)
    for r in records:
        fr=result.findall('Frame')[r['frame_index']];ids=set(r['added_objects']);extra_points={p.get('ID') for a in fr.findall('AO') if int(a.get('ID')) in ids for p in a.findall('AP')}
        for p in fr.iter('AP'):
            for c in list(p):
                if c.get('ConnPtId') in extra_points:p.remove(c)
        for a in list(fr.findall('AO')):
            if int(a.get('ID')) in ids:fr.remove(a)
            elif a.get('ID') in r['original_colors']:a.set('Color',r['original_colors'][a.get('ID')])
        for f in list(fr.findall('FR')):
            if int(f.get('ID')) in r['added_fills']:fr.remove(f)
    return result
