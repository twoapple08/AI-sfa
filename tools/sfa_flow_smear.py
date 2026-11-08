"""v18 스미어의 앞쪽 꺾임을 국소 이동 방향으로 향하게 만드는 시험."""
import numpy as np
import sfa_swept_smear as S

RADII=np.array([.20,.29,.40,.51,.63,.75,.88,1.0])
FORWARD=np.array([.94,1.15,.84,1.12,.90,1.20,.88,1.06])
TRAIL=np.array([1.0,.98,1.01,.99,1.0,1.02,.99,1.0,1.0])


def local_motion(motion,radii):
    """이전/현재 부위로 추정한 현재 위치의 2D 속도. 회전 성분은 접선이다."""
    r=np.asarray(radii,float);now=motion['now'];v=now['tip']-now['hub']
    hub_velocity=now['hub']-motion['hub'];angle=np.clip(motion['angle'],-1.48,1.48)
    tangent=np.array([-v[1],v[0]])*angle
    radial=v*(motion['length']-motion['old_length'])/max(motion['length'],1e-9)
    return hub_velocity+r[...,None]*(tangent+radial)


def geometry(motion,detached=False,source_center=None,source_span=None):
    """반경 방향으로 진행하며 앞/뒤 꺾임을 이동 방향으로 왕복시킨다. 외곽 호 없음."""
    r=RADII
    # 앞쪽 꺾임 사이의 중간에 뒤쪽 꺾임을 놓는다.
    valleys=np.r_[r[0]-(r[1]-r[0])/2,(r[:-1]+r[1:])/2,r[-1]+(r[-1]-r[-2])/2]
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
        extent=np.clip(speeds*.85,length*.04,length*.65)
        if detached:extent=np.minimum(extent,float(source_span)*.70)
        return directions,extent
    front_dir,front_extent=vectors(r);back_dir,back_extent=vectors(valleys)
    front=centers(r)+(front_extent*.78*FORWARD)[:,None]*front_dir
    back=centers(valleys)-(back_extent*.22*TRAIL)[:,None]*back_dir
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
    return root,report
