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
    """이름으로 역할 층을 찾는다(깊이 칸 이름 z0_smear 등 포함)."""
    return {l.get('ID') for l in frame.findall('LayerDef') if (l.get('Name') or '').split('_',1)[-1].startswith(prefix) or (l.get('Name') or '').startswith(prefix)}


def smear_chains(aos,with_color=False):
    """점 연결(AC)로 이어진 스미어 객체 묶음(ID에 기대지 않음: 깊이 칸 정리로 ID가 바뀌어도 같다)."""
    owner={p.get('ID'):i for i,a in enumerate(aos) for p in a.findall('AP')};parent=list(range(len(aos)))
    def find(i):
        while parent[i]!=i:parent[i]=parent[parent[i]];i=parent[i]
        return i
    for i,a in enumerate(aos):
        for p in a.findall('AP'):
            for c in p.findall('AC'):
                j=owner.get(c.get('ConnPtId'))
                if j is not None:parent[find(i)]=find(j)
    out={}
    for i,a in enumerate(aos):out.setdefault((find(i),a.get('Color')),[]).extend(P(a))
    return [(k[1],v) for k,v in out.items()] if with_color else list(out.values())


def tip_violations(root,frame_base=1,near=40.,id_map=None,color_slot=None):
    """id_map: 깊이 칸 정리의 {새 ID: 원래 ID}(옮긴 팔다리를 원래 부위로 찾는다)."""
    out=[];total=0;back=id_map or {}
    for n,f in enumerate(root.findall('Frame')):
        smear=layer_ids(f,'smear');objs={}
        for a in f.findall('AO'):
            oid=back.get(int(a.get('ID')),int(a.get('ID')))
            if BASE<oid<BASE+200:objs[oid-BASE]=a
        groups=smear_chains([a for a in f.findall('AO') if a.get('LayerId') in smear and int(a.get('Color','0'))&0xff000000],with_color=True)
        for col,pts in groups:
            Q=np.array(pts);total+=1;best=None
            own=(color_slot or {}).get(int(col)) if col is not None else None
            for off in ((0,100) if own is None else (own*100,)):  # 스미어 색으로 인물을 알면 그 인물 팔다리만
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
                if 'smear' in name or 'outline' in name:continue
                y=E.fromstring(E.tostring(x))
                if y.tag=='AO':y.set('LayerId',name)
                out.append(E.tostring(y))
            return out
        if body(a,na)!=body(b,nb):diff.append(n)
    return dict(frames_with_body_change=diff)


def geometry_same(ref,cur):
    """ID·레이어만 바뀌고 객체 모양(종류·색·굵기·글로우·점 좌표)과 채움은 그대로인지(깊이 칸 정리 검사)."""
    def sig(f):
        aos=sorted(tuple([a.get(k) for k in ('TypeId','Color','ThicknessScale','GlowRadius','GlowThickness','GlowAlpha')]+[(p.get('X'),p.get('Y')) for p in a.findall('AP')]) for a in f.findall('AO'))
        frs=sorted((r.get('Color'),len(r.findall('FS'))) for r in f.findall('FR'))
        return aos,frs
    return dict(frames_with_shape_change=[n for n,(a,b) in enumerate(zip(ref.findall('Frame'),cur.findall('Frame'))) if sig(a)!=sig(b)])


def run(path,ref=None,frame_base=1,id_map=None,color_slot=None,pose_fixes=None):
    root=load(path);res=dict(tip=tip_violations(root,frame_base,id_map=id_map,color_slot=color_slot),layers=LO.check(root))
    res['head_fill_kind1']=sum(1 for f in root.findall('Frame') for s in f.iter('FS') if s.get('Kind')=='1')
    dup=0
    for f in root.findall('Frame'):
        ids=[p.get('ID') for p in f.iter('AP')];dup+=len(ids)-len(set(ids))
    res['duplicate_point_ids']=dup
    if ref:
        base=load(ref)
        if pose_fixes:  # 장면 설정의 사용자 자세 교정을 기준에 먼저 적용: 교정 장도 '기준+교정'과 정확히 같아야 통과
            from smear_from_labels import apply_pose_fixes
            base,_=apply_pose_fixes(base,pose_fixes,frame_base)
        res['body']=body_same(base,root)
        if pose_fixes:res['body']['pose_fixes_applied_to_reference']=len(pose_fixes)
    res['passed']=(not res['tip']['violations'] and res['layers']['order_matches_ids'] and res['layers']['layer_ids_with_multiple_names']==0
                   and res['layers']['ids_with_multiple_layer_or_type']==0 and dup==0 and (not ref or not res['body']['frames_with_body_change']))
    return res


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('sfa');ap.add_argument('--reference',help='몸 불변 비교 기준(스미어 전 스틱맨 또는 이전 판)');ap.add_argument('--frame-base',type=int,default=1)
    ap.add_argument('--same-shapes-as',help='깊이 칸 정리 전 SFA: 모양이 그대로인지 검사')
    ap.add_argument('--scene',help='scenes/*_smear.json: 스미어 색→인물(자기 팔다리와만 비교), frame_base')
    ap.add_argument('--depth-report',help='sfa_depth_layers 보고서(id_map으로 옮긴 부위를 원래 ID로 찾는다)')
    a=ap.parse_args()
    idm={int(v):int(o) for o,k,v in json.load(open(a.depth_report))['id_map']} if a.depth_report else None
    cs=None;pf=None
    if a.scene:
        sc=json.load(open(a.scene));cs={int(v['smear_color']):v['slot'] for v in sc['actors'].values()};a.frame_base=int(sc.get('frame_base',a.frame_base));pf=sc.get('pose_fixes')
    res=run(a.sfa,a.reference,a.frame_base,idm,cs,pf)
    if a.same_shapes_as:
        res['shapes']=geometry_same(load(a.same_shapes_as),load(a.sfa))
        res['passed']=res['passed'] and not res['shapes']['frames_with_shape_change']
    print(json.dumps(res,ensure_ascii=False,indent=1))
    raise SystemExit(0 if res['passed'] else 1)


if __name__=='__main__':
    main()
