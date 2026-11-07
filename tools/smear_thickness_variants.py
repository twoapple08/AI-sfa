"""기본 폭 스미어의 좌표를 보존하고 해당 부위 굵기의100%/70% 두 경량 SFA를 만든다."""
import argparse,copy,json,zipfile
from pathlib import Path
import xml.etree.ElementTree as E
from smear_density import ROOT


def build(base,source,references,factors=(1.,.7)):
    originals=base.findall('Frame');frames=source.findall('Frame')
    if len(originals)!=len(frames):raise ValueError('기준 장수 불일치')
    outputs={};counts=[]
    for factor in factors:
        if not 0<factor<=1:raise ValueError('굵기 배율 오류')
        root=copy.deepcopy(source);root.set('Name',f'nian41_smear_thickness_{factor:g}')
        removed=active=peak=0
        for n,(frame,original) in enumerate(zip(root.findall('Frame'),originals)):
            baseids={a.get('ID'):a for a in original.findall('AO')};frame_count=0
            for ao in list(frame.findall('AO')):
                if ao.get('ID') in baseids:
                    if E.tostring(ao)!=E.tostring(baseids[ao.get('ID')]):raise ValueError('기존 뼈대 변경')
                    continue
                if ao.get('LayerId')!='1':raise ValueError('알 수 없는 추가 객체')
                if int(ao.get('Color'))==0:
                    frame.remove(ao);removed+=1;continue
                ref=references.get((n,ao.get('ID')))
                refids=baseids
                if isinstance(ref,tuple):
                    source_index,ref=ref
                    if not 0<=source_index<len(originals):raise ValueError('굵기 참조 장 오류')
                    refids={a.get('ID'):a for a in originals[source_index].findall('AO')}
                if ref not in refids:raise ValueError('스미어 발생 부위 굵기 근거 없음')
                thickness=float(refids[ref].get('ThicknessScale'))*factor
                ao.set('ThicknessScale',format(thickness,'.12g'));active+=1;frame_count+=1
            peak=max(peak,frame_count)
            # 제거한 여분 객체를 참조하는 활성 연결이 없어야 한다.
            by={p.get('ID'):p for p in frame.findall('.//AP')}
            for p in by.values():
                for c in p.findall('AC'):
                    q=by.get(c.get('ConnPtId'))
                    if q is None or any(p.get(k)!=q.get(k) for k in ['X','Y']):raise ValueError('경량화 연결 오류')
            # 활성 선은 굵기 외의 좌표/속성/연결 전체가 동일해야 한다.
            kept={a.get('ID'):a for a in frame.findall('AO')}
            for a in frames[n].findall('AO'):
                if a.get('ID') in baseids or int(a.get('Color'))==0:continue
                b=copy.deepcopy(kept[a.get('ID')]);b.set('ThicknessScale',a.get('ThicknessScale'))
                if E.tostring(a)!=E.tostring(b):raise ValueError('스미어 굵기 외 변경')
            if [E.tostring(c) for c in list(frame)[:len(original)]]!=[E.tostring(c) for c in original]:raise ValueError('기존 장 노드 변경')
        outputs[factor]=root;counts.append(dict(factor=factor,active_segments=active,removed_invisible_segments=removed,peak_active_smear_segments=peak))
    return outputs,counts


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ['base','source','references','output']:parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();dest=args.output.resolve()
    if dest==ROOT or ROOT in dest.parents or dest.exists():parser.error('새 비공개 경로가 필요하다')
    def read(path):
        with zipfile.ZipFile(path) as z:return E.fromstring(z.read(z.namelist()[0]))
    rows=json.loads(args.references.read_text());refs={}
    for row in rows:
        key=(row['frame_index'],str(row['smear_object_id']))
        if key in refs:raise ValueError('중복 굵기 대응')
        refs[key]=(row.get('body_frame_index',row['frame_index']),str(row['body_object_id']))
    outputs,counts=build(read(args.base),read(args.source),refs);dest.mkdir(parents=True)
    for factor,root in outputs.items():
        with zipfile.ZipFile(dest/f'기본폭_부위굵기{round(factor*100)}퍼센트_경량.sfa','w',zipfile.ZIP_DEFLATED) as z:z.writestr('review.xml',E.tostring(root,encoding='utf-8',xml_declaration=True))
    (dest/'report.json').write_text(json.dumps(dict(variants=counts,body_preserved=True,smear_coordinates_preserved=True,app_performance_verified=False),ensure_ascii=False,indent=2));print(counts)


if __name__=='__main__':main()
