"""스미어 SFA 전달 전 검사(스미어 단계 4). 파일·코드 검사이며 앱 표시 확인이 아니다.

- tip: 스미어 묶음마다 가장 가까운 팔다리(끝점 40px 이내)의 끝이 스미어 앞끝(팔 방향 투영 최대) 밖으로 나오면 위반
  (사용자 11-08: 팔다리를 줄이지 말고 스미어를 늘린다).
- body: 기준 SFA와 비교해 스미어/테두리 층 밖 노드가 같은지(층 번호·이름은 이름으로 맞춰 비교).
- head: 흰 머리 FS Kind=1 개수.
- layers: 레이어 번호=적은 순서(앱은 번호순), 같은 번호 이름 하나, ID마다 (층, 종류) 하나, 장 안 AP ID 중복 없음.
스미어 층은 이름으로 찾는다('smear'로 시작). 테두리 층은 'outline'으로 시작.
"""
import argparse,json,zipfile
import xml.etree.ElementTree as E
import numpy as np
import sfa_layer_order as LO
from smear_from_labels import LIMBS,BASE,chain,P


def load(path):
    with zipfile.ZipFile(path) as z:return E.fromstring(z.read(z.namelist()[0]))


def layer_ids(frame,prefix):
    return {l.get('ID') for l in frame.findall('LayerDef') if (l.get('Name') or '').startswith(prefix)}


def tip_violations(root,frame_base=1,near=40.):
    out=[];total=0
    for n,f in enumerate(root.findall('Frame')):
        smear=layer_ids(f,'smear');objs={int(a.get('ID'))-BASE:a for a in f.findall('AO') if BASE<int(a.get('ID'))<BASE+200}
        groups={}
        for a in f.findall('AO'):
            if a.get('LayerId') in smear and int(a.get('Color','0'))&0xff000000:
                groups.setdefault((int(a.get('ID'))//10000,a.get('Color')),[]).extend(P(a))
        for pts in groups.values():
            Q=np.array(pts);total+=1;best=None
            for off in (0,100):
                for o1,o2,_ in LIMBS.values():
                    if off+o1 in objs and off+o2 in objs:
                        c=chain(objs,off,o1,o2)
                        if c:
                            d=float(np.min(np.linalg.norm(Q-c[2],axis=1)))
                            if best is None or d<best[0]:best=(d,c[1],c[2])
            if best is None or best[0]>near:continue
            u=(best[2]-best[1])/max(1e-6,np.linalg.norm(best[2]-best[1]))
            m=float(((Q-best[2])@u).max())
            if m<0:out.append(dict(frame=frame_base+n,overshoot_px=round(-m,1)))
    return dict(smear_groups=total,violations=out)


def body_same(ref,cur):
    """스미어·테두리 층 밖 AO/FR가 같은지(층 번호는 이름으로 대응)."""
    diff=[]
    for n,(a,b) in enumerate(zip(ref.findall('Frame'),cur.findall('Frame'))):
        na={l.get('ID'):l.get('Name') for l in a.findall('LayerDef')};nb={l.get('ID'):l.get('Name') for l in b.findall('LayerDef')}
        def body(f,names):
            out=[]
            for x in f:
                if x.tag=='LayerDef':continue
                name=names.get(x.get('LayerId','0'),'') if x.tag=='AO' else ''
                if name.startswith('smear') or name.startswith('outline'):continue
                y=E.fromstring(E.tostring(x))
                if y.tag=='AO':y.set('LayerId',name)
                out.append(E.tostring(y))
            return out
        if body(a,na)!=body(b,nb):diff.append(n)
    return dict(frames_with_body_change=diff)


def run(path,ref=None,frame_base=1):
    root=load(path);res=dict(tip=tip_violations(root,frame_base),layers=LO.check(root))
    res['head_fill_kind1']=sum(1 for f in root.findall('Frame') for s in f.iter('FS') if s.get('Kind')=='1')
    dup=0
    for f in root.findall('Frame'):
        ids=[p.get('ID') for p in f.iter('AP')];dup+=len(ids)-len(set(ids))
    res['duplicate_point_ids']=dup
    if ref:res['body']=body_same(load(ref),root)
    res['passed']=(not res['tip']['violations'] and res['layers']['order_matches_ids'] and res['layers']['layer_ids_with_multiple_names']==0
                   and res['layers']['ids_with_multiple_layer_or_type']==0 and dup==0 and (not ref or not res['body']['frames_with_body_change']))
    return res


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('sfa');ap.add_argument('--reference',help='몸 불변 비교 기준(스미어 전 스틱맨 또는 이전 판)');ap.add_argument('--frame-base',type=int,default=1)
    a=ap.parse_args();res=run(a.sfa,a.reference,a.frame_base)
    print(json.dumps(res,ensure_ascii=False,indent=1))
    raise SystemExit(0 if res['passed'] else 1)


if __name__=='__main__':
    main()
