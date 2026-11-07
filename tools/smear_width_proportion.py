"""스미어 선 굵기를 고정하고, 외곽 폭을 해당 부위 선 굵기의 배수로 만든다."""
import numpy as np


def scale_width(points,axis,body_thickness,canvas_width,multiple=8.,sequence_scale=1.):
    """native 선폭8×ThicknessScale 기준. 출력 해상도와 무관한 상대 폭이다.

    canvas_width/1920은 SFA 기준 선폭을 입력 좌표 단위로 환산한다.
    모든 점에 같은 수직 배율을 적용하므로 고정점/추가점의 상대 깊이와
    길이 방향 배치가 유지된다. 입력의 절대 고정점은 폭 변경에 따라 이동한다.
    """
    p=np.asarray(points,float);a=np.asarray(axis,float)
    if p.ndim!=2 or p.shape[1]!=2 or not len(p) or not np.isfinite(p).all():raise ValueError('스미어 점 오류')
    if a.shape!=(2,2) or not np.isfinite(a).all() or np.linalg.norm(a[1]-a[0])<1e-8:raise ValueError('축 오류')
    vals=np.asarray([body_thickness,canvas_width,multiple,sequence_scale],float)
    if not np.isfinite(vals).all() or (vals<=0).any():raise ValueError('양의 굵기/폭 비율 필요')
    unit=(a[1]-a[0])/np.linalg.norm(a[1]-a[0]);normal=np.array([-unit[1],unit[0]])
    offsets=(p-a[0])@normal;span=float(np.ptp(offsets))
    if span<1e-8:raise ValueError('스미어 외곽 폭이 0이다')
    body_width=8*sequence_scale*body_thickness*canvas_width/1920
    target=multiple*body_width;factor=target/span
    result=p+(factor-1)*offsets[:,None]*normal
    if not np.allclose((result-a[0])@unit,(p-a[0])@unit):raise ValueError('길이 방향 변경')
    return result,dict(original_width_px=span,body_stroke_width_px=body_width,target_width_px=target,width_factor=factor,width_to_body_ratio=multiple)
