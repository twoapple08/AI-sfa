"""직진(팔 축 방향) 스미어: 팔 끝이 바깥쪽으로 팔 굵기 폭의 갈래 지그재그로 늘어난다.

GPT 표시 테이퍼판(sfa_flow_smear)의 휘두르기 계열은 그대로 두고, 그 판이 '축방향 후보'로
분류한 효과만 다시 그린다. 2026-11-08 사용자 선택: 후보 B(폭=팔 굵기×2.1, 길이=팔뚝×1.2).

분류(회전각 = 이전→현재 팔뚝 2D 각도 변화):
- |각| <= 15°  : 직진 갈래
- |각| >= 40°  : 휘두르기형(관절 쪽이 반대로 움직이는 안쪽 구간은 뺀다)
- 그 사이      : 사람 판정 필요. 장면 설정 overrides{장: straight|rotation}가 없으면 직진으로 두고
                 report['needs_review']에 남긴다. 회전각만으로는 나뉘지 않았다(1158 21° 회전, 1181 31° 직진).
원본 영상 입력 없음. 앱 확인 전.
"""
import json
from pathlib import Path
import numpy as np
import sfa_swept_smear as SW
import sfa_flow_smear as F

WIDTH=2.1      # 갈래 폭 / 팔 선 굵기(px)
LENGTH=1.2     # 갈래 전체 길이 / 팔뚝 길이(속도가 크면 최대 1.4배까지)
GAP=2.0        # 가닥 사이 간격 / 스미어 선 굵기 → 굵을수록 가닥 수 감소(3–6)
STRAIGHT_MAX=15.;ROTATION_MIN=40.
PX=8*1.14*1152/1920  # ThicknessScale 1의 1152 캔버스 선 폭(sfa_render 기준)


def is_axial(motion):
    """GPT 판의 축방향 후보 조건(국소 이동이 팔 축과 거의 나란함)."""
    now=motion['now'];v=now['tip']-now['hub']
    mean=F.local_motion(motion,np.array(.65));mean/=max(np.linalg.norm(mean),1e-9)
    return abs(float(mean@v)/max(motion['length'],1e-9))>.88


def classify(motion,overrides=None):
    """'straight' | 'rotation' 와 판정 근거('angle'|'override'|'needs_review')."""
    frame=motion.get('frame');o=(overrides or {}).get(str(frame)) or (overrides or {}).get(frame)
    if o in ('straight','rotation'):return o,'override'
    a=abs(np.degrees(motion['angle']))
    if a<=STRAIGHT_MAX:return 'straight','angle'
    if a>=ROTATION_MIN:return 'rotation','angle'
    return 'straight','needs_review'


def stretch_direction(motion):
    """갈래가 늘어지는 방향. 원본에서 잰 방향(motion['stretch_dir'])이 있으면 그것, 없으면 팔꿈치→손 바깥쪽."""
    if motion.get('stretch_dir') is not None:
        d=np.asarray(motion['stretch_dir'],float);return d/max(np.linalg.norm(d),1e-9)
    v=motion['now']['tip']-motion['now']['hub'];return v/max(np.linalg.norm(v),1e-9)


def streak_geometry(motion):
    now=motion['now'];length=motion['length']
    # 기본: 내지르기·거둬들이기 모두 팔꿈치→손 바깥쪽(원본 1173/1181/1230 관찰).
    # 사용자 11-08: 원본에서 가닥이 늘어진 방향이 있으면 그 방향을 따른다(예: 1160 팔은 위, 가닥은 오른쪽).
    d=stretch_direction(motion);n=np.array([-d[1],d[0]])
    speed=float(F.motion_extent(motion,np.array(1.)))
    total=max(LENGTH*length,min(speed,1.4*LENGTH*length))
    span=WIDTH*motion['limb_px'];k=int(np.clip(np.floor(span/(GAP*motion['smear_px']))+1,3,6))
    r=np.linspace(0,1,k);valleys=np.linspace(-.5/(k-1),1+.5/(k-1),k+1)
    prof=1-.30*(2*r-1)**2  # 가운데 가닥이 조금 길다
    cen=lambda x:now['tip']+((x-.5)*span)[:,None]*n
    front=cen(r)+(total*F.FRONT_SHARE*F.FORWARD[:k]*prof)[:,None]*d
    back=cen(valleys)-(total*F.BACK_SHARE*F.TRAIL[:k+1])[:,None]*d
    base=np.empty((2*k+1,2));base[::2]=back;base[1::2]=front
    return 'flow_axial_streak',base,[]


def rotation_radii(motion,minimum=4):
    """손끝과 같은 쪽으로 움직이는 반경만 남긴다(관절 쪽 역방향 톱니 방지)."""
    tip=F.local_motion(motion,np.array(1.));vel=F.local_motion(motion,F.RADII)
    cos=vel@tip/np.maximum(np.linalg.norm(vel,axis=1)*np.linalg.norm(tip),1e-9)
    # 관절 바로 옆 톱니는 폭이 스미어 선 굵기보다 얕아 방향이 잡히지 않는다(1158: 2px).
    deep=F.display_extent(motion,F.RADII)*F.FRONT_SHARE>=motion.get('smear_px',6.)
    keep=np.flatnonzero((cos>.5)&deep)
    start=keep[0] if len(keep) else len(F.RADII)-minimum
    return F.RADII[min(start,len(F.RADII)-minimum):]


def rotation_geometry(motion):
    now=motion['now'];v=now['tip']-now['hub'];r=rotation_radii(motion);k=len(r)
    valleys=np.r_[r,r[-1]+.03]
    def vec(xs):
        vel=F.local_motion(motion,xs);sp=np.linalg.norm(vel,axis=-1)
        return vel/np.maximum(sp[...,None],1e-9),F.display_extent(motion,xs,taper=True)
    fd,fe=vec(r);bd,be=vec(valleys)
    front=now['hub']+r[:,None]*v+(fe*F.FRONT_SHARE*F.FORWARD[-k:])[:,None]*fd
    back=now['hub']+valleys[:,None]*v-(be*F.BACK_SHARE*F.TRAIL[-k-1:])[:,None]*bd
    base=np.empty((2*k+1,2));base[::2]=back;base[1::2]=front
    return 'flow_axial_rotation',base,[]


def check_streak(motion,density):
    """갈래의 모든 앞 꼭짓점이 팔 바깥쪽을 향하고, 손끝 이동이 팔 축과 나란한지."""
    d=stretch_direction(motion);tipv=F.local_motion(motion,np.array(1.))
    path=np.array(density['points_px']);bis=path[1::2]-(path[:-1:2]+path[2::2])/2
    cos=bis@d/np.maximum(np.linalg.norm(bis,axis=1),1e-9)
    tc=abs(float(tipv@d/max(np.linalg.norm(tipv),1e-9)))
    measured=motion.get('stretch_dir') is not None  # 원본 측정 방향은 이동 추정과 독립이라 이동 일치 조건을 쓰지 않는다
    return dict(passed=float(cos.min())>=.80 and (measured or tc>=.5),measured_direction=measured,min_cosine=float(cos.min()),tip_motion_cosine=tc,
                leading_turns=len(cos),backward_turns=int((cos<0).sum()),rule='axial_outward')


def check_rotation(motion,density):
    """잘라 낸 반경 구간에서 앞 꼭짓점 이등분선이 국소 이동을 향하는지."""
    path=np.array(density['points_px']);r=rotation_radii(motion)
    fi=np.arange(1,len(path),2);fixed=np.flatnonzero(density['fixed_mask'])[1::2]
    vel=F.local_motion(motion,np.interp(fi,fixed,r))
    bis=path[1::2]-(path[:-1:2]+path[2::2])/2
    cos=np.sum(bis*vel,axis=1)/np.maximum(np.linalg.norm(bis,axis=1)*np.linalg.norm(vel,axis=1),1e-9)
    return dict(passed=float(cos.min())>=.80,min_cosine=float(cos.min()),leading_turns=len(cos),
                backward_turns=int((cos<0).sum()),radii_start=float(r[0]),rule='rotation_trimmed')


def build(source,profile=None,canvas=SW.CANVAS,overrides=None,frame_base=1,directions=None):
    """GPT 표시 테이퍼판과 같은 입력(v18 원본)으로, 축방향 후보만 직진/회전으로 다시 그린다.
    frame_base: 0번 장의 원본 장 번호(overrides 키와 보고서 장 번호에 쓴다)."""
    decisions={}
    original=SW.history
    def history(frames,index,slot,code,c=canvas):
        m=original(frames,index,slot,code,c)
        if m is None:return m
        aos=frames[index].findall('AO');objs={a.get('ID'):a for a in aos}
        limb=objs[str(SW.M.BASE+slot*100+code)]
        smear=[a for a in aos if a.get('LayerId')=='1']
        sd=(directions or {}).get(f'{index+frame_base}:{slot}:{code}')
        return dict(m,frame=index+frame_base,stretch_dir=sd,
                    limb_px=float(limb.get('ThicknessScale'))*PX,
                    smear_px=(float(smear[0].get('ThicknessScale')) if smear else 1.35)*PX)
    def geometry(motion,detached=False,center=None,span=None):
        if detached or not is_axial(motion):return F.geometry(motion,detached,center,span)
        kind,why=classify(motion,overrides);decisions[(motion['frame'],round(float(motion['now']['tip'][0]),3))]=(kind,why,motion.get('stretch_dir') is not None)
        # 원본에서 잰 늘어짐 방향이 있으면 회전 판정 장면도 그 방향의 갈래로 그린다(사용자 11-08, 1160).
        return streak_geometry(motion) if kind=='straight' or motion.get('stretch_dir') is not None else rotation_geometry(motion)
    def validator(motion,density):
        if not is_axial(motion):return F.check_turns(motion,density)
        kind,_=classify(motion,overrides)
        return check_streak(motion,density) if kind=='straight' or motion.get('stretch_dir') is not None else check_rotation(motion,density)
    SW.history=history
    try:
        root,report=SW.build(source,profile,canvas,geometry_fn=geometry,validator=validator)
    finally:
        SW.history=original
    root.set('Name',source.get('Name','')+'_flow_axial_streak')
    report.update(axial_rule='straight<=15deg, rotation>=40deg, between=override_or_review',
                  streak=dict(width_per_limb_px=WIDTH,length_per_forearm=LENGTH,gap_per_smear_px=GAP,direction='hub_to_tip_outward'),
                  axial_decisions=[dict(frame=f,kind=k,basis=w,measured_stretch=m) for (f,_),(k,w,m) in sorted(decisions.items())],
                  needs_review=sorted({f for (f,_),(k,w,m) in decisions.items() if w=='needs_review'}))
    return root,report


def load_overrides(path):
    data=json.loads(Path(path).read_text())
    return {str(k):v for k,v in data['axial_overrides'].items()},int(data.get('frame_base',1))


def load_directions(path):
    """scenes/*_axial_smear.json의 stretch_directions(사용 표시된 것만) → {'장:slot:부위': [dx,dy]}."""
    data=json.loads(Path(path).read_text())
    return {k:v['dir'] for k,v in data.get('stretch_directions',{}).items() if v.get('use')}


def main():
    import argparse,zipfile,xml.etree.ElementTree as E
    import sfa_outline_trial as O
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source',required=True,help='v18 원본 SFA(비공개)')
    ap.add_argument('--overrides',help='scenes/*_axial_smear.json')
    ap.add_argument('--out',required=True);ap.add_argument('--report')
    a=ap.parse_args()
    with zipfile.ZipFile(a.source) as z:src=E.fromstring(z.read(z.namelist()[0]))
    ov,fb=load_overrides(a.overrides) if a.overrides else ({},1)
    root,report=build(src,overrides=ov,frame_base=fb,directions=load_directions(a.overrides) if a.overrides else None)
    out=O.build(root,mode='glow',color=0xff303030)[0]  # 기준판과 같은 #303030 글로우 테두리
    import sfa_layer_order as LO
    mapping=LO.renumber_bottom_to_top(out)  # 앱은 레이어를 번호 순으로 그린다: 테두리 0, 몸 1, 스미어 2
    report['layer_renumber']=mapping;report['layer_check']=LO.check(out)
    with zipfile.ZipFile(a.out,'w',zipfile.ZIP_DEFLATED) as z:z.writestr('review.xml',E.tostring(out,encoding='utf-8',xml_declaration=True))
    if a.report:Path(a.report).write_text(json.dumps(report,ensure_ascii=False,indent=1,default=str))
    print(json.dumps(dict(changed=report['changed_effects'],needs_review=report['needs_review']),ensure_ascii=False))


if __name__=='__main__':
    main()
