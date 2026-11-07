"""입력된 원래 지그재그의 거리 기반 밀도 조절과 단일장 SFA 출력. 원본 자동 판독 아님."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET
import zipfile
import numpy as np
from smear_rail_fit import deform_chain, densify_chain, vary_added_turns

ROOT=Path(__file__).resolve().parents[1]
DEFAULT_PROFILE=ROOT/'profiles/smear_density_v1.json'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def validate_profile(profile):
    if profile.get('schema')!='sfa-smear-density-profile/1':raise ValueError('밀도 프로필 스키마가 다르다')
    keys=['reference_width','max_gap','relative_gap','min_gap','thickness','depth_spacing_reference']
    if any(not isinstance(profile.get(k),(int,float)) or isinstance(profile[k],bool) or not np.isfinite(profile[k]) or profile[k]<=0 for k in keys):
        raise ValueError('길이/굵기/비율은 유한한 양수여야 한다')
    if profile['min_gap']>profile['max_gap']:raise ValueError('최소 간격이 최대 간격보다 크다')
    bounds=np.asarray(profile.get('depth_bounds',[]),float)
    depths=np.asarray(profile.get('depths',[]),float);weights=np.asarray(profile.get('spacing_weights',[]),float)
    if bounds.shape!=(2,) or not np.isfinite(bounds).all() or not 0<=bounds[0]<=bounds[1]<.5:raise ValueError('깊이 범위가 잘못됐다')
    if depths.ndim!=1 or not len(depths) or not np.isfinite(depths).all() or ((depths<bounds[0])|(depths>bounds[1])).any():raise ValueError('깊이가 선언 범위를 벗어났다')
    if weights.ndim!=1 or not len(weights) or not np.isfinite(weights).all() or (weights<=0).any():raise ValueError('간격 가중치가 잘못됐다')



def depth_spacing_scales(points,fixed,reference):
    """추가점의 양쪽 같은 경계 이웃 중 가장 좁은 간격으로 양 끝 깊이를 함께 축소."""
    points=np.asarray(points,float);fixed=np.asarray(fixed,bool)
    if not np.isfinite(reference) or reference<=0:raise ValueError('깊이 기준 간격이 양수여야 한다')
    ids=np.flatnonzero(~fixed)
    if len(ids)%2:raise ValueError('추가점 쌍 개수 오류')
    scales=[];gaps=[]
    for i,j in ids.reshape(-1,2):
        if i<2 or j+2>=len(points) or j!=i+1:raise ValueError('경계 이웃이 없는 추가점')
        gap=min(float(np.linalg.norm(points[k]-points[k+d])) for k in [i,j] for d in [-2,2])
        gaps.append(gap);scales.append(min(1.,gap/reference))
    return scales,gaps


def process(points,canvas,profile):
    """원래 점만 입력한다. 이미 추가한 결과를 새 원본으로 재입력하지 않는다."""
    validate_profile(profile);canvas=np.asarray(canvas,float)
    if canvas.shape!=(2,) or not np.isfinite(canvas).all() or (canvas<=0).any():raise ValueError('화면 크기는 양의 너비/높이여야 한다')
    base=np.asarray(points,float);scale=canvas[0]/profile['reference_width']
    dense,intervals=densify_chain(base,profile['max_gap']*scale,profile['relative_gap'],profile['min_gap']*scale)
    unshifted,fixed=vary_added_turns(base,dense,profile['spacing_weights'],[0.])
    scales,local_gaps=depth_spacing_scales(unshifted,fixed,profile['depth_spacing_reference']*scale)
    result,fixed=vary_added_turns(base,dense,profile['spacing_weights'],profile['depths'],scales)
    if not np.array_equal(result[fixed],base):raise ValueError('원래 꺾임점이 바뀌었다')
    records=[];cursor=0;strokes=base[:-1].reshape(-1,2,2)
    for record in intervals:
        item=dict(record);item['added_pairs']=record['divisions']-1
        i=record['interval'];item['turn_distances_px']=np.linalg.norm(strokes[i+1]-strokes[i],axis=1).tolist()
        item['stroke_lengths_px']=[float(np.linalg.norm(strokes[i,1]-strokes[i,0])),float(np.linalg.norm(strokes[i+1,1]-strokes[i+1,0]))]
        item['depth_scales']=scales[cursor:cursor+item['added_pairs']]
        item['local_turn_gaps_px']=local_gaps[cursor:cursor+item['added_pairs']]
        item['effective_depth_bounds']=[[float(v*b) for b in profile['depth_bounds']] for v in item['depth_scales']]
        item['depth_pairs']=[[profile['depths'][(2*(cursor+j))%len(profile['depths'])]*scales[cursor+j],profile['depths'][(2*(cursor+j)+1)%len(profile['depths'])]*scales[cursor+j]] for j in range(item['added_pairs'])]
        records.append(item);cursor+=item['added_pairs']
    return dict(base_points_px=base.tolist(),points_px=result.tolist(),fixed_mask=fixed.tolist(),
                old_segments=len(base)-1,segments=len(result)-1,added_pairs=cursor,intervals=records,
                scale=float(scale),original_vertices_preserved=True)


def export_sfa(result,canvas,profile,point_base=80000000,object_base=18000000):
    width,height=canvas;points=result['points_px'];n=len(points)-1
    root=ET.Element('Sequence',Name='smear_density_v1',HeightWidthRatio=str(height/width),RatioX=str(width),RatioY=str(height),FrameCount='1',BackgroundColor='-1')
    f=ET.SubElement(root,'Frame',ID='9000',Position='0',BackgroundColor='-1');ET.SubElement(f,'LayerDef',ID='0',Name='smear',Visible='true',Locked='false')
    for k in range(n):
        ao=ET.SubElement(f,'AO',ID=str(object_base+k),TypeId='1',Color=str(0xff0000ff),LayerId='0',DrawOrder=str(k),ThicknessScale=str(profile['thickness']),ObjectScale='1',GlowRadius='0',GlowThickness='0',GlowAlpha='0',GlowColor='0')
        for j,xy in enumerate(points[k:k+2]):
            pid=point_base+2*k+j
            p=ET.SubElement(ao,'AP',ID=str(pid),Index=str(j),Flags='4' if j==0 and k else '9',X=f'{xy[0]/width*100:.7f}',Y=f'{xy[1]/height*100:.7f}')
            if j==0 and k:ET.SubElement(p,'AC',ConnPtId=str(pid-1))
            if j==1 and k<n-1:ET.SubElement(p,'AC',ConnPtId=str(pid+1))
    inspect_sfa(root,result,canvas,profile)
    return root


def inspect_sfa(root,result,canvas,profile):
    frames=root.findall('Frame')
    if len(frames)!=1 or frames[0].get('Position')!='0':raise ValueError('단일장 효과 형식 오류')
    f=frames[0];aos=f.findall('AO');n=result['segments'];by={p.get('ID'):p for p in f.findall('.//AP')}
    if len(aos)!=n or len({a.get('ID') for a in aos})!=n or len(by)!=2*n or f.findall('.//FR') or f.findall('.//FS'):raise ValueError('개수/ID/채움 오류')
    width,height=canvas
    for k,ao in enumerate(aos):
        if ao.get('TypeId')!='1' or int(ao.get('Color'))!=0xff0000ff or float(ao.get('ThicknessScale'))!=profile['thickness']:raise ValueError('선 종류/색/굵기 변경')
        if any(float(ao.get(x,'0')) for x in ['GlowRadius','GlowThickness','GlowAlpha']):raise ValueError('글로우 금지')
        aps=ao.findall('AP')
        if len(aps)!=2:raise ValueError('선 끝점 개수 오류')
        for j,p in enumerate(aps):
            xy=result['points_px'][k+j]
            if p.get('X')!=f'{xy[0]/width*100:.7f}' or p.get('Y')!=f'{xy[1]/height*100:.7f}':raise ValueError('출력 좌표 변경')
            expected=[]
            if j==0 and k:expected=[aos[k-1].findall('AP')[1].get('ID')]
            if j==1 and k<n-1:expected=[aos[k+1].findall('AP')[0].get('ID')]
            if [c.get('ConnPtId') for c in p.findall('AC')]!=expected:raise ValueError('사슬 연결 변경')
            for qid in expected:
                q=by[qid]
                if (p.get('X'),p.get('Y'))!=(q.get('X'),q.get('Y')):raise ValueError('연결 좌표 불일치')
    return dict(objects=n,unique_points=len(by),fill=0,alpha=255,glow=0,app_verified=False)


def run(document,profile,output):
    validate_profile(profile)
    if document.get('schema')!='sfa-smear-density-input/1':raise ValueError('원래 사슬 입력 스키마가 필요하다. 결과 JSON을 다시 처리하지 않는다')
    canvas=document.get('canvas');cases=document.get('cases')
    if not isinstance(cases,list) or not cases or not all(isinstance(c,dict) for c in cases):raise ValueError('사례 목록이 비었다')
    ids=[c.get('id') for c in cases]
    if any(not isinstance(i,str) or re.fullmatch(r'[\w-]+',i) is None for i in ids) or len(set(ids))!=len(ids):raise ValueError('사례ID는 고유한 한글/영문/숫자/밑줄/하이픈이어야 한다')
    output=Path(output).resolve()
    if output==ROOT or ROOT in output.parents:raise ValueError('좌표/결과는 저장소 밖 비공개 디렉터리에 출력해야 한다')
    # 실행 전 공통 입력 오류는 전체를 거절한다.
    cv=np.asarray(canvas,float)
    if cv.shape!=(2,) or not np.isfinite(cv).all() or (cv<=0).any():raise ValueError('양의 화면 크기가 필요하다')
    if output.exists() and any(output.iterdir()):raise ValueError('기존 결과 보호를 위해 비어 있는 새 출력 디렉터리가 필요하다')
    output.mkdir(parents=True,exist_ok=True);reports=[];pid=80000000;oid=18000000
    for c in cases:
        temporary=None
        try:
            if ('points_px' in c)==('template_points_px' in c):raise ValueError('원래 점 또는 템플릿+두경계 중 하나가 필요하다')
            base=c['points_px'] if 'points_px' in c else deform_chain(c['template_points_px'],c['rail_a'],c['rail_b'],c.get('segments')).tolist()
            result=process(base,canvas,profile);root=export_sfa(result,canvas,profile,pid,oid);validation=inspect_sfa(root,result,canvas,profile)
            xml=ET.tostring(root,encoding='utf-8',xml_declaration=True);name=c['id']+'.sfa';path=output/name
            temporary=output/(name+'.tmp')
            with zipfile.ZipFile(temporary,'w',zipfile.ZIP_DEFLATED) as z:
                info=zipfile.ZipInfo('review.xml',date_time=(1980,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;z.writestr(info,xml)
            temporary.replace(path);temporary=None
            pid+=2*result['segments'];oid+=result['segments']
            reports.append(dict(id=c['id'],status='ok',file=name,sha256=digest(path.read_bytes()),result=result,validation=validation))
        except (ValueError,KeyError,TypeError,OSError) as exc:
            reports.append(dict(id=c['id'],status='needs_review',reason=str(exc)))
        finally:
            if temporary is not None and temporary.exists():temporary.unlink()
    report=dict(schema='sfa-smear-density-result/1',canvas=canvas,profile=profile,profile_sha256=digest(json.dumps(profile,sort_keys=True,ensure_ascii=False).encode()),input_sha256=digest(json.dumps(document,sort_keys=True,ensure_ascii=False).encode()),cases=reports,fps_condition=[24,24],fps_storage='바인딩 조건,단일장',training_ready=False,held_out=False,app_verified=False)
    (output/'density.binding.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--input',required=True);parser.add_argument('--output',required=True);parser.add_argument('--profile',default=str(DEFAULT_PROFILE));args=parser.parse_args()
    try:
        report=run(json.loads(Path(args.input).read_text()),json.loads(Path(args.profile).read_text()),args.output)
    except (ValueError,TypeError,KeyError,OSError) as exc:parser.exit(2,str(exc)+'\n')
    ok=sum(c['status']=='ok' for c in report['cases']);print(f'출력 {ok}/{len(report["cases"])} 사례: {args.output}')
    return 0 if ok==len(report['cases']) else 2

if __name__=='__main__':raise SystemExit(main())
