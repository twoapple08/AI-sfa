"""비공개 장별 원래 사슬을 기존 SFA 위에 더하고 폭만 다른 두 검토판을 만든다."""
import argparse, copy, hashlib, json, zipfile
from pathlib import Path
import xml.etree.ElementTree as E
import numpy as np
from smear_density import process, export_sfa, ROOT


def build(base, document, profile, narrow=.55):
    if not 0<narrow<1:raise ValueError('좁힌 폭 배율은 0과 1 사이여야 한다')
    if document.get('schema')!='sfa-smear-clip-input/1':raise ValueError('입력 스키마 오류')
    canvas=np.asarray(document['canvas'],float);frames=base.findall('Frame')
    if canvas.shape!=(2,) or not np.isfinite(canvas).all() or (canvas<=0).any():raise ValueError('화면 크기 오류')
    if not np.isclose(canvas[1]/canvas[0],float(base.get('HeightWidthRatio'))):raise ValueError('화면비 불일치')
    if len(document['events'])>=100:raise ValueError('효과 ID 용량 초과')
    if any(l.get('ID')=='1' for f in frames for l in f.findall('LayerDef')):raise ValueError('스미어 레이어1이 이미 있다')
    if len(frames)!=document['frame_count']:raise ValueError('원본 SFA 장수 불일치')
    prepared=[];seen_ids=set()
    for event in document['events']:
        eid=event['id']
        if not isinstance(event['color'],int) or (event['color']>>24)&255!=255:raise ValueError('활성 효과는 불투명 색이어야 한다')
        if eid in seen_ids:raise ValueError('중복 효과 ID')
        seen_ids.add(eid);rows={}
        for row in event['frames']:
            n=row['frame_index']
            if not isinstance(n,int) or not 0<=n<len(frames) or n in rows:raise ValueError('장 번호 오류')
            axis=np.asarray(row['axis_px'],float)
            if axis.shape!=(2,2) or not np.isfinite(axis).all() or np.linalg.norm(axis[1]-axis[0])<1e-8:raise ValueError('폭 중심축 오류')
            rows[n]=(process(row['points_px'],canvas,profile),axis)
        if not rows:raise ValueError('빈 효과')
        capacity=max(r['segments'] for r,a in rows.values())
        if capacity>=5000:raise ValueError('효과별 점 ID 용량 초과')
        prepared.append((event,rows,capacity))
    outputs={};audits=[]
    for label,factor in [('기본폭',1.),('좁힌폭',narrow)]:
        root=copy.deepcopy(base);root.set('Name','nian41_10s_smear_'+label);outframes=root.findall('Frame')
        for n,(original,frame) in enumerate(zip(frames,outframes)):
            expected=[E.tostring(c) for c in original];active=[]
            for ei,(event,rows,capacity) in enumerate(prepared):
                if n not in rows:continue
                result,axis=rows[n];r=copy.deepcopy(result);points=np.array(r['points_px']);unit=(axis[1]-axis[0])/np.linalg.norm(axis[1]-axis[0]);normal=np.array([-unit[1],unit[0]])
                offset=(points-axis[0])@normal;r['points_px']=(points-(1-factor)*offset[:,None]*normal).tolist()
                # 양 판의 길이 방향 좌표·점 수·추가점 깊이비·굵기는 동일하다.
                if not np.allclose(np.array(r['points_px'])@unit,points@unit):raise ValueError('폭 이외 방향 변경')
                r['base_points_px']=(np.array(r['points_px'])[r['fixed_mask']]).tolist()
                pbase=300000000+n*1000000+ei*10000;obase=900000000+ei*10000
                sub=export_sfa(r,canvas,profile,pbase,obase).find('Frame')
                aos=sub.findall('AO');count=len(aos)
                for a in aos:
                    a.set('Color',str(event['color']));a.set('LayerId','1')
                # 활성 구간 안에서 같은 AO ID의 종류/점 수/연결 구조를 유지한다.
                for k in range(count,capacity):
                    a=copy.deepcopy(aos[-1]);a.set('ID',str(obase+k));a.set('DrawOrder',str(k));a.set('Color','0')
                    for j,p in enumerate(a.findall('AP')):
                        p.set('ID',str(pbase+2*k+j));p.set('Flags','9')
                        for c in list(p):p.remove(c)
                    aos.append(a)
                if not active:E.SubElement(frame,'LayerDef',ID='1',Name='smear_review',Visible='true',Locked='false')
                for a in aos:frame.append(a)
                active.append(dict(id=event['id'],segments=count,capacity=capacity,axis_px=axis.tolist(),result=r))
            # 기존 뼈대/머리/면/연결/레이어는 직렬화 전체가 동일해야 한다.
            if [E.tostring(c) for c in list(frame)[:len(expected)]]!=expected:raise ValueError('기존 SFA 변경')
            objects=frame.findall('AO')
            if len({a.get('ID') for a in objects})!=len(objects):raise ValueError('객체 ID 중복')
            pts=frame.findall('.//AP');by={p.get('ID'):p for p in pts}
            if len(by)!=len(pts):raise ValueError('점 ID 중복')
            for p in pts:
                for c in p.findall('AC'):
                    q=by.get(c.get('ConnPtId'))
                    if q is None or any(p.get(k)!=q.get(k) for k in ['X','Y']):raise ValueError('연결 좌표 불일치')
                    if p.get('ID') not in [v.get('ConnPtId') for v in q.findall('AC')]:raise ValueError('연결 상호참조 누락')
            if label=='기본폭':audits.append(dict(frame_index=n,effects=active))
        outputs[label]=root
    # 모든 장의 두 판은 동일한 객체/점/연결 구조, 효과 좌표 중 폭 성분만 다르다.
    a,b=(outputs[k].findall('Frame') for k in ['기본폭','좁힌폭'])
    all_ids=set()
    for fa,fb in zip(a,b):
        pa=fa.findall('.//AP');pb=fb.findall('.//AP')
        if len(pa)!=len(pb):raise ValueError('판별 점수 변경')
        ids={p.get('ID') for p in pa}
        if ids&all_ids:raise ValueError('장간 점 ID 재사용')
        all_ids.update(ids)
        for aa,bb in zip(fa.findall('AO'),fb.findall('AO')):
            if aa.attrib!=bb.attrib:raise ValueError('판별 객체 속성 변경')
            for p,q in zip(aa.findall('AP'),bb.findall('AP')):
                if {k:v for k,v in p.attrib.items() if k not in ['X','Y']}!={k:v for k,v in q.attrib.items() if k not in ['X','Y']}:raise ValueError('판별 점 구조 변경')
                if [c.attrib for c in p]!=[c.attrib for c in q]:raise ValueError('판별 연결 변경')
    return outputs,audits


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ['base','input','profile','output']:parser.add_argument('--'+key,required=True,type=Path)
    parser.add_argument('--narrow',type=float,default=.55);args=parser.parse_args();dest=args.output.resolve()
    if dest==ROOT or ROOT in dest.parents or dest.exists():parser.error('새 비공개 출력 경로가 필요하다')
    with zipfile.ZipFile(args.base) as z:base=E.fromstring(z.read(z.namelist()[0]))
    doc=json.loads(args.input.read_text());profile=json.loads(args.profile.read_text());outputs,audit=build(base,doc,profile,args.narrow);dest.mkdir(parents=True)
    for name,root in outputs.items():
        with zipfile.ZipFile(dest/(name+'.sfa'),'w',zipfile.ZIP_DEFLATED) as z:z.writestr('review.xml',E.tostring(root,encoding='utf-8',xml_declaration=True))
    report=dict(base_sha256=hashlib.sha256(args.base.read_bytes()).hexdigest(),input_sha256=hashlib.sha256(args.input.read_bytes()).hexdigest(),narrow_factor=args.narrow,base_frames_preserved=True,frame_count=len(audit),effect_frames=sum(bool(a['effects']) for a in audit),events=len(doc['events']),app_verified=False,automatic_smear_detection=False,audit=audit)
    (dest/'binding.private.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print({k:v for k,v in report.items() if k!='audit'})


if __name__=='__main__':main()
