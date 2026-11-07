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
