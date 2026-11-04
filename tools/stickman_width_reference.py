"""근거를 명시한 화면 척도 키로 폭을 정한다. 관측 실패를 고정50px로 채우지 않는다."""
import numpy as np


def reference_radius(frame, keys, factor=1.):
    if not keys or not np.isfinite(factor) or factor<=0:
        raise ValueError('폭 척도 키/양수 비율이 필요하다')
    times=sorted(int(t) for t in keys)
    radii=np.array([keys[str(t)] for t in times],float)
    if not np.isfinite(radii).all() or (radii<=0).any():
        raise ValueError('반지름 키는 유한한 양수여야 한다')
    if frame<times[0] or frame>times[-1]:
        raise ValueError('폭 근거가 없는 구간에 척도를 외삽할 수 없다')
    return float(np.interp(frame,times,radii)*factor)
