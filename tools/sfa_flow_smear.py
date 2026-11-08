"""v18 스미어의 앞쪽 꺾임을 국소 이동 방향으로 향하게 만드는 시험."""
import numpy as np
import sfa_swept_smear as S

RADII=np.array([.06,.16,.29,.43,.57,.72,.86,1.0])
FORWARD=np.array([.94,1.15,.84,1.12,.90,1.20,.88,1.06])
TRAIL=np.array([.94,1.05,.90,1.12,.96,1.08,.91,1.04,.97])
FRONT_SHARE=.58
BACK_SHARE=.42


def local_motion(motion,radii):
    """이전/현재 부위로 추정한 현재 위치의 2D 속도. 회전 성분은 접선이다."""
    r=np.asarray(radii,float);now=motion['now'];v=now['tip']-now['hub']
    hub_velocity=now['hub']-motion['hub'];angle=np.clip(motion['angle'],-1.48,1.48)
    tangent=np.array([-v[1],v[0]])*angle
    radial=v*(motion['length']-motion['old_length'])/max(motion['length'],1e-9)
    return hub_velocity+r[...,None]*(tangent+radial)


def motion_extent(motion,radii):
    """공통 배율로만 제한한다. 회전 v=rω 비율과 평행이동 성분은 보존한다."""
    r=np.asarray(radii,float)
    # 모든 경계에서 같은 배율을 써 안쪽 하한/바깥쪽 개별 상한의 평탄화를 막는다.
    reference=np.r_[RADII,0.,1.07]
    maximum=float(np.linalg.norm(local_motion(motion,reference),axis=-1).max())
    gain=min(.85,motion['length']*.65/max(maximum,1e-9))
    return np.linalg.norm(local_motion(motion,r),axis=-1)*gain


def display_extent(motion,radii,taper=True):
    """부착된 부위의 표시 외곽: 방향용 실제 속도와 분리한 관절→말단 테이퍼."""
    if not taper:return motion_extent(motion,radii)
    tip=float(motion_extent(motion,np.array(1.)))
    return np.maximum(np.asarray(radii,float),0.)*tip


def geometry(motion,detached=False,source_center=None,source_span=None):
    """반경 방향으로 진행하며 앞/뒤 꺾임을 이동 방향으로 왕복시킨다. 외곽 호 없음."""
    r=RADII
    # 같은 반경에서 앞/뒤 한 쌍을 만든다. 삽입 시 안쪽 꼭짓점의 반경 편향을 막는다.
    valleys=np.r_[r,r[-1]+.03]
    now=motion['now'];v=now['tip']-now['hub'];length=motion['length']
    mean=local_motion(motion,np.array(.65));mean/=max(np.linalg.norm(mean),1e-9)
    normal=np.array([-mean[1],mean[0]])
    axial=abs(float(mean@v)/max(length,1e-9))>.88
    if detached:
        family='flow_detached'
        def centers(xs):return source_center+(xs-.60)[...,None]*float(source_span)*normal
    elif axial:
        family='flow_axial_candidate'
        # 앞뒤 깊이를 확정하지 않고 손목/발목 주변의 작은 폭만 사용한다.
        def centers(xs):return now['tip']+(xs-.60)[...,None]*length*.22*normal
    else:
        family='flow_rotation' if abs(motion['angle'])>=.20 else 'flow_translation'
        def centers(xs):return now['hub']+xs[...,None]*v
    def vectors(xs):
        velocities=local_motion(motion,xs)
        speeds=np.linalg.norm(velocities,axis=-1)
        directions=velocities/np.maximum(speeds[...,None],1e-9)
        directions=np.where((speeds<1e-6)[...,None],mean,directions)
        extent=display_extent(motion,xs,taper=not (detached or axial))
        if detached:extent=np.minimum(extent,float(source_span)*.70)
        return directions,extent
    front_dir,front_extent=vectors(r);back_dir,back_extent=vectors(valleys)
    front=centers(r)+(front_extent*FRONT_SHARE*FORWARD)[:,None]*front_dir
    back=centers(valleys)-(back_extent*BACK_SHARE*TRAIL)[:,None]*back_dir
    base=np.empty((2*len(r)+1,2));base[::2]=back;base[1::2]=front
    return family,base,[]


def check_turns(motion,density):
    """삽입 후의 모든 앞쪽 꼭짓점 이등분선이 추정 이동 방향을 향하는지 검사한다."""
    path=np.array(density['points_px']);front_indices=np.arange(1,len(path),2)
    fixed_front=np.flatnonzero(density['fixed_mask'])[1::2]
    radii=np.interp(front_indices,fixed_front,RADII)
    velocities=local_motion(motion,radii)
    bisectors=path[1::2]-(path[:-1:2]+path[2::2])/2
    norms=np.linalg.norm(bisectors,axis=1)*np.linalg.norm(velocities,axis=1)
    cosines=np.sum(bisectors*velocities,axis=1)/np.maximum(norms,1e-9)
    minimum=float(cosines.min())
    return dict(passed=minimum>=.80,min_cosine=minimum,leading_turns=len(cosines),backward_turns=int((cosines<0).sum()),interpolated_radius=True)


def build(source,profile=None,canvas=S.CANVAS):
    root,report=S.build(source,profile,canvas,geometry_fn=geometry,validator=check_turns)
    root.set('Name',source.get('Name','')+'_flow_turns_trial')
    report['direction_rule']='leading_turn_bisector_aligned_with_local_motion'
    report['outer_curve_accents']=0
    report['front_share']=FRONT_SHARE;report['back_share']=BACK_SHARE
    report['extent_rule']='attached_display_taper_separate_from_local_motion'
    report['taper_scope']='attached_nonaxial_limb_only'
    return root,report
