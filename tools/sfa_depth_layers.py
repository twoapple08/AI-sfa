"""깊이 칸 레이어: 장마다 부위의 앞뒤를 원본에서 재고, 칸마다 '테두리→몸→스미어' 레이어로 쌓는다.

문제(사용자 11-08): 몸 레이어 위에 스미어 레이어를 쌓으면 한 인물 팔의 스미어가, 원본에서 앞에 있는
다른 인물의 팔을 덮는다. 레이어는 모든 장이 공유하고(앱 번호순), 객체 ID 하나는 한 레이어에만 속한다.
그래서 인물과 상관없는 깊이 칸 z0<z1<…을 만들고, 장마다 부위를 칸에 배정한다. 다른 칸에 들어간 객체는
칸 전용 ID로 바꿔 쓴다(복제 아님: 한 장에서 객체는 한 칸에만 있다). 사람 편집은 고려하지 않는다(사용자 11-08).

부위: 인물(slot)마다 core(머리·몸통·부속·채움), armA(3,4), armB(5,6), legA(7,8), legB(9,10).
스미어 묶음(선 ID//10000, 색으로 인물)은 가장 가까운 팔다리에, 테두리 복제본은 같은 좌표의 원래 객체에 딸린다.
앞뒤 증거(원본 프레임, 인물색 마스크):
- 몸-몸: 두 인물의 선이 (굵기 안에서) 만나는 점. 넓은 창에 두 색이 다 있고, 작은 창에서 한 색이 1.5배 이상이면 그 인물이 앞.
- 스미어-몸: 스미어 볼록 껍질 안의 다른 인물 선 표본. 그 인물 색이 스미어 인물 색보다 1.5배 이상이면 그 부위가 스미어 앞.
제약: 기본(같은 칸)은 레이어 안 파일 순서(slot1이 slot0 위)와 스미어>몸. 기본과 다른 측정만 칸을 가른다.
겹치는 쌍만 제약한다(겹치지 않으면 순서가 안 보이므로). 순환이 생기면 증거가 가장 약한 측정을 뺀다.
이 측정은 근사다(스틱맨 교차점이 원본 교차점과 다를 수 있음). 결과는 시트로 사용자 판정을 받는다.
"""
import argparse,copy,json,zipfile
from pathlib import Path
import xml.etree.ElementTree as E
import numpy as np

BASE=4560000
GROUPS={'core':(1,2),'armA':(3,4),'armB':(5,6),'legA':(7,8),'legB':(9,10)}
LIMB_END={'armA':(3,4),'armB':(5,6),'legA':(7,8),'legB':(9,10)}
CANVAS=(1152,648)


def pts(a,canvas=CANVAS):
    return np.array([[float(p.get('X'))*canvas[0]/100,float(p.get('Y'))*canvas[1]/100] for p in a.findall('AP')])


def width_px(a,canvas=CANVAS):
    return 8*1.14*float(a.get('ThicknessScale','1'))*canvas[0]/1920


def seg_closest(p1,p2,q1,q2,n=24):
    """두 선분의 가장 가까운 점 쌍(표본 근사)."""
    t=np.linspace(0,1,n)[:,None];A=p1+t*(p2-p1);B=q1+t*(q2-q1)
    d=np.linalg.norm(A[:,None]-B[None],axis=2);i,j=np.unravel_index(np.argmin(d),d.shape)
    return float(d[i,j]),(A[i]+B[j])/2


def layer_role(frame):
    roles={}
    for l in frame.findall('LayerDef'):
        n=(l.get('Name') or '').lower()
        roles[l.get('ID')]='outline' if n.startswith('outline') else ('smear' if n.startswith('smear') else 'body')
    return roles


def part_of_body(oid):
    """몸 객체 ID → (slot, 부위). 부속(4570xxx)은 slot0 core."""
    if BASE<oid<BASE+200:
        slot,k=divmod(oid-BASE,100)
        for g,ks in GROUPS.items():
            if k in ks:return slot,g
        return slot,'core'
    if 4570000<=oid<4580000:return 0,'core'
    return None


def classify_frame(frame,color_slot,canvas=CANVAS):
    """장 안 객체 → 부위 키 (slot, group). 반환: {id: key}, 스미어 묶음 {키: 점}, 몸 선 {key: [(p1,p2,w,id)]}, 머리 {slot: (중심,반지름)}."""
    roles=layer_role(frame);owner={};lines={};heads={};smear_pts={}
    aos=frame.findall('AO');byid={a.get('ID'):a for a in aos}
    for a in aos:
        if roles.get(a.get('LayerId'))!='body':continue
        k=part_of_body(int(a.get('ID')))
        if k is None:continue
        owner[a.get('ID')]=k
        if BASE<int(a.get('ID'))<BASE+200 and int(a.get('Color','0'))&0xff000000:
            p=pts(a,canvas)
            if (int(a.get('ID'))-BASE)%100==1 and len(p)>=2:heads[k[0]]=((p[0]+p[1])/2,np.linalg.norm(p[0]-p[1])/2+width_px(a,canvas)/2)
            elif a.get('TypeId')=='1' and len(p)>=2:lines.setdefault(k,[]).append((p[0],p[1],width_px(a,canvas),a.get('ID')))
    # 스미어 묶음 → 그 인물의 가장 가까운 팔다리 끝
    groups={}
    for a in aos:
        if roles.get(a.get('LayerId'))=='smear':
            groups.setdefault((int(a.get('ID'))//10000,a.get('Color')),[]).append(a)
    for (gid,col),objs in groups.items():
        slot=color_slot.get(int(col)) if col is not None else None
        P=np.concatenate([pts(a,canvas) for a in objs]);best=None
        cand=[slot] if slot is not None else [0,1]
        for s in cand:
            for g,(o1,o2) in LIMB_END.items():
                a2=byid.get(str(BASE+s*100+o2))
                if a2 is None:continue
                q=pts(a2,canvas);a1=byid.get(str(BASE+s*100+o1));up=pts(a1,canvas) if a1 is not None else q
                end=q[0] if min(np.linalg.norm(q[0]-up[0]),np.linalg.norm(q[0]-up[1]))>min(np.linalg.norm(q[1]-up[0]),np.linalg.norm(q[1]-up[1])) else q[1]
                d=float(np.min(np.linalg.norm(P-end,axis=1)))
                if best is None or d<best[0]:best=(d,(s,g))
        key=best[1] if best else ((slot or 0),'core')
        for a in objs:owner[a.get('ID')]=key
        smear_pts.setdefault(key,[]).append(P)
    # 테두리 복제본 → 같은 종류·좌표의 원래 객체
    sig={}
    for a in aos:
        if a.get('ID') in owner:sig[(a.get('TypeId'),tuple(np.round(pts(a,canvas),3).ravel()))]=owner[a.get('ID')]
    for a in aos:
        if roles.get(a.get('LayerId'))=='outline':
            k=sig.get((a.get('TypeId'),tuple(np.round(pts(a,canvas),3).ravel())))
            if k is not None:owner[a.get('ID')]=k
    return owner,smear_pts,lines,heads


def color_count(masks,slot_color,slot,p,r):
    m=masks[slot_color[slot]];H,W=m.shape;x,y=int(round(p[0])),int(round(p[1]))
    if not(0<=x<W and 0<=y<H):return 0
    return int(m[max(0,y-r):y+r+1,max(0,x-r):x+r+1].sum())


def relations(frame,rgb,slot_color,color_slot,canvas=CANVAS,ratio=1.5,one_sided=True):
    """원본에서 잰 앞뒤. 반환: 겹치는 쌍(기본 제약용), 측정 [(front, back, kind, strength)]."""
    import cv2
    import smear_limb_scan as V
    owner,smear_pts,lines,heads=classify_frame(frame,color_slot,canvas)
    masks={c:(m>0) for c,m in V.color_masks(rgb).items()}
    overlap=set();meas=[]
    keys=sorted({k for k in lines}|{(s,'core') for s in heads})
    def segs(k):
        out=list(lines.get(k,[]))
        return out
    # 몸-몸(다른 인물)
    for ka in [k for k in keys if k[0]==0]:
        for kb in [k for k in keys if k[0]==1]:
            pts_=[]
            for p1,p2,wa,_ in segs(ka):
                for q1,q2,wb,_ in segs(kb):
                    d,c=seg_closest(p1,p2,q1,q2)
                    if d<(wa+wb)/2:pts_.append(c)
            for s,kk,other in ((0,ka,kb),(1,kb,ka)):
                if kk[1]=='core' and kk[0] in heads:
                    cen,rad=heads[kk[0]]
                    for q1,q2,wb,_ in segs(other):
                        u=q2-q1;t=np.clip((cen-q1)@u/max(u@u,1e-9),0,1);c=q1+t*u
                        if np.linalg.norm(c-cen)<rad+wb/2:pts_.append(c)
            if not pts_:continue
            overlap.add((ka,kb))
            na=nb=0
            for c in pts_:
                if color_count(masks,slot_color,0,c,15)>20 and color_count(masks,slot_color,1,c,15)>20:
                    na+=color_count(masks,slot_color,0,c,4);nb+=color_count(masks,slot_color,1,c,4)
            if na+nb>=10:
                if na>ratio*nb:meas.append((ka,kb,'body',na/(nb+1)))
                elif nb>ratio*na:meas.append((kb,ka,'body',nb/(na+1)))
            elif one_sided:
                # 가림 근거(11-10): 뒤로 보낼 부위가 자기 선 전체에서 자기 색이 거의 안 보이고(<20%, 실제로 가려짐),
                # 겹치는 지점에는 앞 인물색만 보일 때만 앞뒤를 정한다. 겹침 지점 색만 보면 뼈대가 조금 어긋나도
                # 틀린다(승인 10초 1197 빨강 머리). 경계 측정보다 약하게(세기 상한 1) 넣는다.
                def own_support(k):
                    hits=tot=0
                    for q1,q2,_,_ in segs(k):
                        for t in np.linspace(0,1,12):
                            c=q1+t*(q2-q1);x,y=int(round(c[0])),int(round(c[1]))
                            m=masks[slot_color[k[0]]]
                            if 0<=x<m.shape[1] and 0<=y<m.shape[0]:
                                tot+=1;hits+=color_count(masks,slot_color,k[0],c,6)>0
                    if k[1]=='core' and k[0] in heads:
                        cen=heads[k[0]][0];tot+=3;hits+=3*(color_count(masks,slot_color,k[0],cen,8)>0)
                    return hits/tot if tot>=6 else None
                dense=[]  # 겹치는 구간을 따라 여러 점(가장 가까운 한 점만 보면 쌍마다 1~2점뿐이라 근거가 모이지 않는다)
                for p1,p2,wa,_ in segs(ka):
                    for q1,q2,wb,_ in segs(kb):
                        lim=(wa+wb)/2
                        for a1,a2,b1,b2 in ((p1,p2,q1,q2),(q1,q2,p1,p2)):
                            u=b2-b1
                            for t in np.linspace(0,1,16):
                                c=a1+t*(a2-a1);w=np.clip((c-b1)@u/max(u@u,1e-9),0,1)
                                if np.linalg.norm(c-(b1+w*u))<lim:dense.append(c)
                oa=ob=0
                for c in dense:
                    ca,cb=color_count(masks,slot_color,0,c,6),color_count(masks,slot_color,1,c,6)
                    if ca>20 and cb==0:oa+=1
                    elif cb>20 and ca==0:ob+=1
                sa,sb=own_support(ka),own_support(kb)
                torso=lambda sl:max([np.linalg.norm(q2-q1) for q1,q2,_,_ in lines.get((sl,'core'),[])] or [0])
                if min(torso(0),torso(1))<80:sa=sb=None  # 먼 작은 인물은 색 영역이 가늘어 근거로 쓰지 않는다(승인 10초 1236)
                if ob>=3 and sa is not None and sa<0.2 and (sb is None or sb>=0.2):meas.append((kb,ka,'body',min(1.,ob/10)))
                elif oa>=3 and sb is not None and sb<0.2 and (sa is None or sa>=0.2):meas.append((ka,kb,'body',min(1.,oa/10)))
    # 같은 인물 안 겹침: 원래 순서 유지(측정하지 않음)
    for s in (0,1):
        ks_=[k for k in keys if k[0]==s]
        for i,ka in enumerate(ks_):
            for kb in ks_[i+1:]:
                hit=any(seg_closest(p1,p2,q1,q2)[0]<(wa+wb)/2 for p1,p2,wa,_ in segs(ka) for q1,q2,wb,_ in segs(kb))
                if hit:overlap.add((ka,kb))
    # 스미어-몸(다른 인물)
    for ks,plist in smear_pts.items():
        P=np.concatenate(plist).astype(np.float32)
        if len(P)<3:continue
        hull=cv2.convexHull(P)
        for kb in [k for k in keys if k[0]!=ks[0]]:
            samples=[]
            for q1,q2,wb,_ in segs(kb):
                L=np.linalg.norm(q2-q1);n=max(2,int(L/3))
                for t in np.linspace(0,1,n):
                    c=q1+t*(q2-q1)
                    if cv2.pointPolygonTest(hull,(float(c[0]),float(c[1])),False)>=0:samples.append(c)
            if kb[1]=='core' and kb[0] in heads:
                cen,rad=heads[kb[0]]
                if cv2.pointPolygonTest(hull,(float(cen[0]),float(cen[1])),True)>-rad:samples.append(cen)
            if len(samples)<3:continue
            overlap.add(('smear',ks,kb))
            nq=sum(color_count(masks,slot_color,kb[0],c,3) for c in samples);ns=sum(color_count(masks,slot_color,ks[0],c,3) for c in samples)
            if nq+ns>=10 and nq>ratio*ns:meas.append((kb,ks,'over_smear',nq/(ns+1)))
    return overlap,meas


def _levels(cons):
    nodes={x for c in cons for x in c[:2]};level={n:0 for n in nodes}
    for _ in range(len(nodes)+2):
        changed=False
        for u,v,w in cons:
            if level[v]<level[u]+w:level[v]=level[u]+w;changed=True
        if not changed:return level
    return None  # 양의 순환


def assign_levels(overlap,meas,file_order):
    """제약 level(v)>=level(u)+w 를 우선순위대로 하나씩 넣고, 순환을 만드는 제약은 버린다.
    우선순위: 측정(강한 것부터) > 같은 인물 원래 순서 > 인물 사이 기본 순서(파일 순서) > 스미어 기본.
    '부위 Q가 P의 스미어 위'는 Q가 P보다 위 칸이다(같은 칸이면 스미어 층이 몸 층 위라서).
    측정이 있는 쌍에는 기본 제약을 걸지 않는다."""
    ordered=[];front_of={}
    for front,back,kind,st in sorted(meas,key=lambda m:-m[3]):
        key=frozenset((front,back))
        if key in front_of:continue
        front_of[key]=(front,back,kind,st)
        lower,upper=sorted((front,back),key=file_order)
        ordered.append(((back,front,1 if kind in ('over_smear','over_head') or front!=upper else 0),('measured',front,back,kind,st)))
    intra=[];inter=[];smear=[]
    for o in sorted(overlap,key=str):
        pair=frozenset(o[1:]) if o[0]=='smear' else frozenset(o)
        if pair in front_of:continue
        if o[0]=='smear':_,ks,kb=o;smear.append(((kb,ks,0),('smear_default',)))
        else:
            lower,upper=sorted(o,key=file_order)
            (intra if o[0][0]==o[1][0] else inter).append(((lower,upper,0),('default',)))
    cons=[];dropped=[]
    for c,why in ordered+intra+inter+smear:
        if _levels(cons+[c]) is None:dropped.append(why)
        else:cons.append(c)
    return _levels(cons) or {},dropped


def user_depth(meas,scene,frame):
    """사용자 앞뒤 판정(장면 설정 depth_user)을 측정보다 강한 제약으로 넣는다. 같은 쌍의 측정은 버린다.
    측정이 없거나 틀린 장을 사람이 지정한다(11-09 1176: 검은 팔이 빨강 팔 스미어 앞)."""
    out=list(meas)
    for u in scene.get('depth_user',[]):
        if int(u['frame'])!=frame:continue
        fs,fg=u['front'].split(':');bs,bg=u['back'].split(':');f,b=(int(fs),fg),(int(bs),bg)
        out=[m for m in out if frozenset((m[0],m[1]))!=frozenset((f,b))]
        out.append((f,b,u.get('kind','over_smear'),1e9))
    return out


GROUP_JOINTS={'core':('head_t','head_b','neck','pelvis'),'armA':('elb_r','wri_r'),'armB':('elb_l','wri_l'),
              'legA':('kne_r','ank_r'),'legB':('kne_l','ank_l')}


def color_slot_name(actors):
    return {name:v['slot'] for name,v in actors.items()}


def hidden_groups(hidden,frame,name_slot):
    """추출 보고서의 추론 관절(stickman_scene inferred_joints) → 보이지 않아 추론한 부위 묶음 {(slot, 묶음)}.
    묶음 관절의 절반 이상이 추론이면 그 묶음은 가려진 부위로 본다."""
    out=set()
    for x in (hidden or {}).get(frame,[]):
        slot=name_slot.get(x['actor'])
        if slot is None:continue
        for g,js in GROUP_JOINTS.items():
            if sum(j in x['joints'] for j in js)*2>=len(js):out.add((slot,g))
    return out


def hidden_back(overlap,meas,hidden):
    """추론으로 만든(보이지 않는) 부위는 정의상 가려진 부위다(11-10 사용자: 그 자리에 원본 빨강이 없는데 빨강 부위가
    파랑 위로 온다). 그런 부위를 앞에 두는 측정은 버리고, 겹치는 다른 인물 부위 뒤에 둔다."""
    if not hidden:return meas
    out=[m for m in meas if m[0] not in hidden]
    have={frozenset((m[0],m[1])) for m in out}
    for o in overlap:
        if o[0]=='smear':continue
        a,b=o
        if a[0]==b[0]:continue
        for back,front in ((a,b),(b,a)):
            if back in hidden and front not in hidden and frozenset((a,b)) not in have:
                out.append((front,back,'body',0.5));have.add(frozenset((a,b)))
    return out


def head_crossed(geom,limb):
    """limb(slot,묶음)의 아래 마디(LIMB_END 두 번째 조각)가 같은 인물 머리 원을 지나는가."""
    lines,heads=geom
    if limb[0] not in heads:return False
    cen,rad=heads[limb[0]]
    segs=lines.get(limb,[])
    if len(segs)<2:return False
    q1,q2=segs[-1][0],segs[-1][1]
    u=q2-q1;t=np.clip((cen-q1)@u/max(u@u,1e-9),0,1)
    return bool(np.linalg.norm(q1+t*u-cen)<0.8*rad)


def front_order(overlap,meas,fronts,name_slot,strength=0.8,geom=None):
    """같은 인물 안 앞뒤(11-10 사용자: 든 팔이 앞 팔, 내린 팔이 뒤 팔). 추출 보고서 front(검출 점수 또는 원본 판독)로
    뒤쪽 팔다리 < 몸통·머리 < 앞쪽 팔다리. 실제로 겹치는 묶음끼리만 넣는다. 인물 사이 측정보다 약하게(세기 0.8)."""
    pairs={frozenset(o) for o in overlap if o[0]!='smear'}
    have={frozenset((m[0],m[1])) for m in meas}
    out=list(meas)
    for x in fronts:
        sl=name_slot.get(x['actor'])
        if sl is None:continue
        for part,groups in (('arm',('armA','armB')),('leg',('legA','legB'))):
            if x.get(part) not in ('r','l'):continue
            fr,bk=((sl,groups[0]),(sl,groups[1])) if x[part]=='r' else ((sl,groups[1]),(sl,groups[0]))
            core=(sl,'core')
            # 앞쪽 팔다리를 머리보다 위에 두는 것은 팔꿈치·무릎 너머(아래 마디)가 실제로 머리 원을 가로지를 때만.
            # 스틱맨 팔은 머리 원 안 목점에서 시작해 위 마디가 늘 머리를 지나므로, 무조건 올리면 팔이 얼굴을 긋는다(승인 10초 1151 등).
            over=head_crossed(geom,fr) if geom else True
            for front,back,kind in ((fr,core,'over_head' if over else 'body'),(core,bk,'body'),(fr,bk,'body')):
                k=frozenset((front,back))
                if k in pairs and k not in have:
                    # 앞쪽 팔다리 > 몸통 묶음: 같은 칸이면 머리가 팔다리보다 나중에 그려지므로 반드시 한 칸 위(over_head)
                    out.append((front,back,kind,strength));have.add(k)
    return out


def app_inversions(frames,key):
    """앱 순서(파일 전체 첫 등장)로 그렸을 때 같은 장·같은 레이어 안에서 의도 순서와 뒤집히는 객체 ID들."""
    app={}
    for f in frames:
        for a in f.findall('AO'):app.setdefault(a.get('ID'),len(app))
    bad=set()
    for f in frames:
        by={}
        for a in f.findall('AO'):by.setdefault(a.get('LayerId'),[]).append(a.get('ID'))
        for ids in by.values():
            byk=sorted(ids,key=key)
            bya=sorted(ids,key=app.get)
            for x,y in zip(byk,bya):
                if x!=y:bad.update((x,y))
    return bad


def register_order(out,src,newid):
    """앱은 DrawOrder를 읽지 않고 같은 레이어 안을 객체 ID의 파일 전체 첫 등장 순서로 그린다(docs/FORMAT.md).
    칸을 옮긴 복사본 ID는 여러 장에서 따로 처음 나와 순서가 뒤섞인다(11-10 사용자: 팔이 머리·가면 위로).
    첫 장의 AO를 원래 순서(원본 첫 등장, 복사본은 원래 ID 기준)로 다시 적고, 첫 장에 없는 ID는 보이지 않는
    등록용 복사본(Color 0, 연결 없음)으로 같은 자리에 넣어 모든 레이어의 순서를 고정한다.
    한 장에만 나오는 객체(스미어 조각 등)는 대개 그 장에서 순서대로 처음 나오므로, 뒤집힘이 남는 것만 등록한다."""
    base={}
    for f in src.findall('Frame'):
        for a in f.findall('AO'):base.setdefault(a.get('ID'),len(base))
    rev={str(v):str(o) for (o,k),v in newid.items()}
    key=lambda i:(base.get(rev.get(i,i),10**9),i)
    frames=out.findall('Frame')
    first=frames[0]
    proto={};seen={}
    for f in frames:
        for a in f.findall('AO'):
            proto.setdefault(a.get('ID'),a);seen[a.get('ID')]=seen.get(a.get('ID'),0)+1
    cur=[max(int(p.get('ID')) for f in frames for p in f.iter('AP'))+1]  # 파일 전체 점 ID와 겹치지 않게
    want={i for i in proto if seen[i]>1}
    regs=[]
    for _ in range(4):
        present={a.get('ID') for a in first.findall('AO')}
        add=[i for i in proto if i in want and i not in present]
        for i in add:
            r=copy.deepcopy(proto[i]);r.set('Color','0');r.set('GlowAlpha','0')
            for p in r.findall('AP'):
                for c in list(p):p.remove(c)
                p.set('ID',str(cur[0]));cur[0]+=1
            regs.append(r);first.append(r)
        aos=first.findall('AO')
        for a in aos:first.remove(a)
        nlay=len(first.findall('LayerDef'))
        for j,a in enumerate(sorted(aos,key=lambda a:key(a.get('ID')))):first.insert(nlay+j,a)
        bad=app_inversions(frames,key)
        if not bad-present-set(add):break
        want|=bad
    return dict(registered_hidden=len(regs),first_frame_objects=len(first.findall('AO')),remaining_inversion_ids=len(app_inversions(frames,key)))


def build(root,frames_dir,scene,frame_base,canvas=CANVAS,hidden=None,fronts=None):
    import cv2
    actors=scene['actors'];slot_color={v['slot']:k for k,v in actors.items()};color_slot={int(v['smear_color']):v['slot'] for v in actors.values()}
    out=copy.deepcopy(root);frames=out.findall('Frame')
    order_cache={}
    def file_order(k):
        return (k[0],list(GROUPS).index(k[1]))
    per_frame=[];maxlevel=0
    for n,f in enumerate(frames):
        rgb=cv2.cvtColor(cv2.imread(str(Path(frames_dir)/f'{n+frame_base}.png')),cv2.COLOR_BGR2RGB)
        overlap,meas=relations(f,rgb,slot_color,color_slot,canvas)
        meas=hidden_back(overlap,meas,hidden_groups(hidden,n+frame_base,color_slot_name(actors)))
        _,_,lines_,heads_=classify_frame(f,color_slot,canvas)
        meas=front_order(overlap,meas,(fronts or {}).get(n+frame_base,[]),color_slot_name(actors),geom=(lines_,heads_))
        meas=user_depth(meas,scene,n+frame_base)
        level,dropped=assign_levels(overlap,meas,file_order)
        if n+frame_base in set(scene.get('depth_flat',[])):level={k:0 for k in level}  # 사용자 판정: 기존(한 칸)이 맞음
        maxlevel=max(maxlevel,max(level.values(),default=0))
        per_frame.append(dict(level=level,meas=meas,dropped=dropped))
    K=maxlevel+1
    # 레이어 정의: 칸마다 테두리→몸→스미어, 번호=아래→위
    roles_names={'outline':'outline_glow','body':'Layer 1','smear':'smear'}
    used_ids={int(a.get('ID')) for a in out.iter('AO')}|{int(p.get('ID')) for p in out.iter('AP')}
    newid={};cursor=[600000000]
    def remap(oid,k):
        if k==0:return oid
        key=(oid,k)
        if key not in newid:
            while cursor[0] in used_ids:cursor[0]+=1
            newid[key]=cursor[0];used_ids.add(cursor[0]);cursor[0]+=1
        return newid[key]
    lay=lambda k,role:str(3*k+['outline','body','smear'].index(role))
    report=[]
    for n,f in enumerate(frames):
        info=per_frame[n];roles=layer_role(f);owner,_,_,_=classify_frame(f,color_slot,canvas)
        present={roles[l.get('ID')] for l in f.findall('LayerDef')}
        for l in f.findall('LayerDef'):f.remove(l)
        moved={}
        for a in f.findall('AO'):
            role=roles.get(a.get('LayerId'),'body');key=owner.get(a.get('ID'));k=info['level'].get(key,0) if key else 0
            nid=remap(int(a.get('ID')),k)
            if nid!=int(a.get('ID')):moved[a.get('ID')]=str(nid);a.set('ID',str(nid))
            a.set('LayerId',lay(k,role))
        for fs in f.iter('FS'):
            if fs.get('ObjId') in moved:fs.set('ObjId',moved[fs.get('ObjId')])
        defs=[E.Element('LayerDef',ID=lay(k,r),Name=f'z{k}_{roles_names[r]}',Visible='true',Locked='false') for k in range(K) for r in ('outline','body','smear')]
        for i,d in enumerate(defs):f.insert(i,d)
        lv={f'{s}:{g}':v for (s,g),v in info['level'].items() if v>0}
        report.append(dict(frame=n+frame_base,raised=lv,measured=[(f'{a[0]}:{a[1]}',f'{b[0]}:{b[1]}',kind,round(st,2)) for a,b,kind,st in info['meas']],dropped_measured=[(f'{d[1][0]}:{d[1][1]}',f'{d[2][0]}:{d[2][1]}',d[3]) for d in info['dropped'] if d[0]=='measured'],dropped_defaults=sum(1 for d in info['dropped'] if d[0]!='measured')))
    reg=register_order(out,root,newid)
    return out,dict(levels=K,order_registration=reg,layers=3*K,frames=report,renamed_objects=len(newid),id_map=[[o,k,v] for (o,k),v in sorted(newid.items())])


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--sfa',required=True);ap.add_argument('--frames',required=True);ap.add_argument('--scene',required=True)
    ap.add_argument('--out',required=True);ap.add_argument('--report')
    ap.add_argument('--hidden-report',help='stickman_clip 보고서: scene.inferred_joints(보이지 않아 추론한 관절)를 뒤에 둔다')
    a=ap.parse_args()
    with zipfile.ZipFile(a.sfa) as z:root=E.fromstring(z.read(z.namelist()[0]))
    scene=json.loads(Path(a.scene).read_text())
    hidden=None
    if a.hidden_report:
        hidden={}
        for x in json.load(open(a.hidden_report)).get('scene',{}).get('inferred_joints',[]):hidden.setdefault(int(x['frame']),[]).append(x)
    fronts=None
    if a.hidden_report:
        fronts={}
        for x in json.load(open(a.hidden_report)).get('front',[]):fronts.setdefault(int(x['frame']),[]).append(x)
    out,rep=build(root,a.frames,scene,int(scene.get('frame_base',1)),hidden=hidden,fronts=fronts)
    import sfa_layer_order as LO
    rep['layer_check']=LO.check(out)
    with zipfile.ZipFile(a.out,'w',zipfile.ZIP_DEFLATED) as z:z.writestr('review.xml',E.tostring(out,encoding='utf-8',xml_declaration=True))
    if a.report:Path(a.report).write_text(json.dumps(rep,ensure_ascii=False,indent=1))
    print(json.dumps(dict(levels=rep['levels'],raised_frames=sum(1 for r in rep['frames'] if r['raised']),layer_check=rep['layer_check']),ensure_ascii=False))


if __name__=='__main__':
    main()
