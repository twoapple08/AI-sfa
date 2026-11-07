"""검토용 두 경계 키로 연결된 지그재그 사슬을 변형한다. 자동 원본 판독기가 아니다."""
import numpy as np
from scipy.interpolate import PchipInterpolator


def deform_chain(template, rail_a, rail_b, segments=None):
    """템플릿의 양쪽 진행 간격을 재사용한다. 경계 키는 각각 진행 순서의 xy 배열."""
    template=np.asarray(template,float)
    rails=[np.asarray(r,float) for r in (rail_a,rail_b)]
    if template.ndim!=2 or template.shape[1]!=2 or len(template)<5:
        raise ValueError('템플릿에는 적어도 5개 xy 점이 필요하다')
    if any(r.ndim!=2 or r.shape[1]!=2 or len(r)<2 for r in rails):
        raise ValueError('각 경계에 적어도 두 xy 키가 필요하다')
    if not all(np.isfinite(a).all() for a in [template]+rails):
        raise ValueError('유한한 좌표가 필요하다')
    segments=len(template)-1 if segments is None else segments
    if isinstance(segments,bool) or not isinstance(segments,int) or segments<4:
        raise ValueError('선 수는 4 이상의 정수여야 한다')
    axis=np.linalg.svd(template-template.mean(0),full_matrices=False)[2][0]
    if np.dot(template[-1]-template[0],axis)<0:axis=-axis
    projection=template@axis;points=np.empty((segments+1,2))
    for parity,rail in enumerate(rails):
        values=projection[parity::2];extent=np.ptp(values)
        if extent<1e-8:raise ValueError('템플릿 경계의 진행 길이가 필요하다')
        u=(values-values.min())/extent
        u=np.interp(np.linspace(0,len(u)-1,len(points[parity::2])),np.arange(len(u)),u)
        points[parity::2]=PchipInterpolator(np.linspace(0,1,len(rail)),rail,axis=0)(u)
    if (np.linalg.norm(np.diff(points,axis=0),axis=1)<1e-8).any():
        raise ValueError('변형 후 길이가 0인 선이 있다')
    return points


def densify_chain(points, max_gap, relative_gap, min_gap):
    """벌어진 왕복 사이에 새 왕복만 넣는다. 기존 점/경계 꺾임과 순서는 보존한다.

    간격은 같은 방향 획의 평균 축에 수직인 거리의 1/4,1/2,3/4 위치 근사다.
    세 간격 제약은 검토용 입력이며 학습된 보편 임계값이 아니다.
    """
    points=np.asarray(points,float)
    if points.ndim!=2 or points.shape[1]!=2 or len(points)<5 or len(points)%2!=1 or not np.isfinite(points).all():
        raise ValueError('유한한 홀수 개 xy 사슬이 필요하다')
    if not np.isfinite([max_gap,relative_gap,min_gap]).all() or not 0<min_gap<=max_gap or relative_gap<=0:
        raise ValueError('양의 간격 제약이 필요하다')
    strokes=points[:-1].reshape(-1,2,2);result=[];records=[]
    for i,pair in enumerate(strokes):
        result.extend(pair)
        if i==len(strokes)-1:break
        other=strokes[i+1];vectors=np.array([pair[1]-pair[0],other[1]-other[0]])
        axis=vectors.mean(0);norm=np.linalg.norm(axis)
        if norm<1e-8:raise ValueError('상쇄된 획 방향은 수동 확인이 필요하다')
        normal=np.array([-axis[1],axis[0]])/norm
        gaps=[abs(np.dot(((1-t)*other[0]+t*other[1])-((1-t)*pair[0]+t*pair[1]),normal)) for t in [.25,.5,.75]]
        gap=max(gaps);length=min(np.linalg.norm(vectors,axis=1))
        allowed=max(min_gap,min(max_gap,relative_gap*length))
        divisions=max(1,int(np.ceil(gap/allowed)))
        if divisions>64:raise ValueError('지나친 세분화는 수동 확인이 필요하다')
        for j in range(1,divisions):result.extend(pair+(other-pair)*(j/divisions))
        records.append(dict(interval=i,old_gap=float(gap),target_gap=float(allowed),divisions=divisions))
    result.append(points[-1]);result=np.asarray(result)
    if (np.linalg.norm(np.diff(result,axis=0),axis=1)<1e-8).any():raise ValueError('길이 0인 새 연결')
    return result,records


def inset_added_turns(original, dense, depth=.25):
    """원래 점은 고정하고 삽입된 왕복쌍의 두 끝만 서로를 향해 안쪽으로 당긴다."""
    original=np.asarray(original,float);dense=np.asarray(dense,float)
    if any(a.ndim!=2 or a.shape[1]!=2 or not np.isfinite(a).all() for a in [original,dense]):
        raise ValueError('유한한 xy 배열이 필요하다')
    if not np.isfinite(depth) or not 0<=depth<.5:raise ValueError('안쪽 깊이는 0 이상 .5 미만이어야 한다')
    fixed=np.zeros(len(dense),bool);cursor=0
    for point in original:
        while cursor<len(dense) and not np.array_equal(dense[cursor],point):cursor+=1
        if cursor==len(dense):raise ValueError('기존 점 또는 순서가 소실됐다')
        fixed[cursor]=True;cursor+=1
    result=dense.copy();indices=np.flatnonzero(~fixed)
    runs=np.split(indices,np.where(np.diff(indices)!=1)[0]+1) if len(indices) else []
    for run in runs:
        if len(run)%2:raise ValueError('추가점은 왕복쌍이어야 한다')
        for i,j in run.reshape(-1,2):
            a,b=dense[i],dense[j]
            result[i]=(1-depth)*a+depth*b
            result[j]=(1-depth)*b+depth*a
    if (np.linalg.norm(np.diff(result,axis=0),axis=1)<1e-8).any():raise ValueError('길이 0인 연결')
    return result,fixed


def vary_added_turns(original, dense, spacing_weights, depths, depth_scales=None):
    """고정된 원래 점 사이에서 추가 왕복의 간격과 양 끝 깊이를 개별 조절한다."""
    result,fixed=inset_added_turns(original,dense,0)
    dense=np.asarray(dense,float);weights=np.asarray(spacing_weights,float);depths=np.asarray(depths,float)
    if weights.ndim!=1 or not len(weights) or not np.isfinite(weights).all() or (weights<=0).any():
        raise ValueError('간격 가중치는 양의 유한한 배열이어야 한다')
    if depths.ndim!=1 or not len(depths) or not np.isfinite(depths).all() or ((depths<0)|(depths>=.5)).any():
        raise ValueError('깊이들은 0 이상 .5 미만이어야 한다')
    indices=np.flatnonzero(~fixed);runs=np.split(indices,np.where(np.diff(indices)!=1)[0]+1) if len(indices) else []
    scales=np.ones(len(indices)//2) if depth_scales is None else np.asarray(depth_scales,float)
    if scales.shape!=(len(indices)//2,) or not np.isfinite(scales).all() or ((scales<0)|(scales>1)).any():raise ValueError('추가 왕복마다 0~1 깊이 배율이 필요하다')
    cursor=0
    for run in runs:
        start,end=run[0],run[-1]
        if len(run)%2 or start<2 or end+2>=len(dense):raise ValueError('추가 왕복 양쪽에 기존 획이 필요하다')
        count=len(run)//2;w=np.array([weights[(cursor+k)%len(weights)] for k in range(count+1)])
        ts=np.cumsum(w)[:-1]/w.sum()
        for pair,t in zip(run.reshape(-1,2),ts):
            a=(1-t)*dense[start-2]+t*dense[end+1]
            b=(1-t)*dense[start-1]+t*dense[end+2]
            da,db=depths[(2*cursor)%len(depths)]*scales[cursor],depths[(2*cursor+1)%len(depths)]*scales[cursor]
            result[pair[0]]=(1-da)*a+da*b;result[pair[1]]=(1-db)*b+db*a;cursor+=1
    if (np.linalg.norm(np.diff(result,axis=0),axis=1)<1e-8).any():raise ValueError('길이 0인 연결')
    return result,fixed
