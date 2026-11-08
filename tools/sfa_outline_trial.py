"""SFA 원본을 보존하고 뒤 레이어에 얇은 선/작은 불투명 글로우 테두리를 시험한다."""
import argparse,copy,hashlib,json,zipfile
from pathlib import Path
import xml.etree.ElementTree as E

ROOT=Path(__file__).resolve().parents[1]

def build(source,mode='stroke',edge_ratio=.10,color=0xff7c8896,radius=.35):
    if mode not in ['stroke','glow']:raise ValueError('테두리 방식 오류')
    if not 0<edge_ratio<=.5 or not 0<radius<=5:raise ValueError('테두리 크기 오류')
    root=copy.deepcopy(source);root.set('Name',source.get('Name','')+'_outline_'+mode)
    original_ids={int(a.get('ID')) for a in source.findall('.//AO')};point_ids={int(p.get('ID')) for p in source.findall('.//AP')}
    layerids={int(l.get('ID')) for l in source.findall('.//LayerDef')};layer=max(layerids|{0})+1
    active_ids=sorted({int(a.get('ID')) for a in source.findall('.//AO') if (int(a.get('Color'))>>24)&255})
    idmap={oid:1500000000+i for i,oid in enumerate(active_ids)}
    if original_ids.intersection(idmap.values()):raise ValueError('테두리 객체 ID 충돌')
    cursor=max(2000000000,max(point_ids,default=0)+1);total=0;rows=[]
    for n,(f,old) in enumerate(zip(root.findall('Frame'),source.findall('Frame'))):
        objects=old.findall('AO');byid={a.get('ID'):a for a in objects}
        # 검정/붉은 가면은 레칸, 파랑은 상대. 원본 부위 굵기로 테두리의 얇기를 정한다.
        def reference(a):
            rgb=int(a.get('Color'))&0xffffff;oid='4560102' if rgb==0x0000ff else '4560002'
            return float(byid.get(oid,a).get('ThicknessScale','1'))
        active=[a for a in objects if (int(a.get('Color'))>>24)&255]
        local={p.get('ID'):str(cursor+i) for i,p in enumerate(p for a in active for p in a.findall('AP'))};cursor+=len(local)
        if cursor>=2147483647:raise ValueError('32비트 점 ID 용량 초과')
        outlines=[]
        for a in active:
            b=copy.deepcopy(a);alpha=(int(a.get('Color'))>>24)&255;th=float(a.get('ThicknessScale','1'));edge=edge_ratio*reference(a);target=th+2*edge
            b.set('ID',str(idmap[int(a.get('ID'))]));b.set('LayerId',str(layer));b.set('DrawOrder',str(-100000+len(outlines)));b.set('Color',str((alpha<<24)|(color&0xffffff)))
            if mode=='stroke':
                b.set('ThicknessScale',f'{target:.9g}')
                for key in ['GlowRadius','GlowThickness','GlowAlpha']:b.set(key,'0')
            else:
                b.set('GlowRadius',str(radius));b.set('GlowThickness',f'{10*target/max(th,1e-6):.9g}');b.set('GlowAlpha',str(alpha));b.set('GlowColor',str(color))
            for p in b.findall('AP'):
                p.set('ID',local[p.get('ID')]);p.set('Flags','9')
                for c in list(p):
                    target_id=local.get(c.get('ConnPtId'))
                    if target_id:c.set('ConnPtId',target_id)
                    else:p.remove(c)
            outlines.append(b)
        E0=E.Element('LayerDef',ID=str(layer),Name='outline_'+mode,Visible='true',Locked='false')
        f.insert(0,E0)
        for i,a in enumerate(outlines,1):f.insert(i,a)
        # 원본의 객체/점/연결/면/속성을 일절 수정하지 않는다.
        if [E.tostring(c) for c in list(f)[1+len(outlines):]]!=[E.tostring(c) for c in old]:raise ValueError('원본 노드 변경')
        pts=f.findall('.//AP');by={p.get('ID'):p for p in pts}
        if len(by)!=len(pts):raise ValueError('장내 점 ID 중복')
        for a in outlines:
            for p in a.findall('AP'):
                for c in p.findall('AC'):
                    q=by[c.get('ConnPtId')]
                    if any(p.get(k)!=q.get(k) for k in ['X','Y']):raise ValueError('새 연결 좌표 불일치')
        rows.append(dict(index=n,outline_objects=len(outlines)));total+=len(outlines)
    return root,dict(mode=mode,color=f'#{color&0xffffff:06X}',edge_ratio=edge_ratio,glow_radius=radius if mode=='glow' else 0,frames=len(rows),added_outline_objects=total,source_nodes_identical=True,new_fills=0,outline_layer=layer,original_alpha_preserved=True,app_verified=False,editing_follow_verified=False,rows=rows)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('input',type=Path);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args();dest=args.output.resolve()
    if dest==ROOT or ROOT in dest.parents or dest.exists():parser.error('새 비공개 출력 폴더 필요')
    with zipfile.ZipFile(args.input) as z:source=E.fromstring(z.read(z.namelist()[0]))
    dest.mkdir(parents=True);reports=[]
    for mode in ['stroke','glow']:
        root,report=build(source,mode)
        with zipfile.ZipFile(dest/f'v18_outline_{mode}.sfa','w',zipfile.ZIP_DEFLATED) as z:z.writestr('review.xml',E.tostring(root,encoding='utf-8',xml_declaration=True))
        reports.append(report)
    (dest/'report.private.json').write_text(json.dumps(dict(source_sha256=hashlib.sha256(args.input.read_bytes()).hexdigest(),variants=reports),ensure_ascii=False,indent=2));print([{k:v for k,v in r.items() if k!='rows'} for r in reports])

if __name__=='__main__':main()
