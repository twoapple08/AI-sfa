"""명시한 곧게 뻗은 팔다리 스미어의 중심축 측정. 외곽/이펙트는 만들지 않는다."""
import numpy as np


def measure_straight_limb(mask, hub, direction, half_width, minimum_length):
    hub, direction = np.asarray(hub, float), np.asarray(direction, float)
    norm = np.linalg.norm(direction)
    if norm < 1e-8 or half_width <= 0 or minimum_length <= 0:
        raise ValueError('방향/관측 띠 크기 오류')
    direction = direction/norm
    normal = np.array([-direction[1], direction[0]])
    y,x = np.nonzero(mask)
    delta = np.c_[x,y]-hub
    along, cross = delta@direction, delta@normal
    valid = (along > minimum_length/2) & (np.abs(cross) < half_width)
    along, cross = along[valid], cross[valid]
    if len(along) < 30 or np.quantile(along,.98) < minimum_length:
        raise ValueError('뻗은 팔다리를 측정할 색 관측이 부족하다')
    length = float(np.quantile(along,.98))
    bins = np.linspace(minimum_length/2,length,25)
    ts,vs = [],[]
    for a,b in zip(bins,bins[1:]):
        selected = (along >= a)&(along < b)
        if selected.sum() >= 3:
            ts.append(float(np.median(along[selected])))
            vs.append(float(np.median(cross[selected])))
    if len(ts) < 6:
        raise ValueError('중심축을 잴 구간 표본이 부족하다')
    ts,vs=np.array(ts),np.array(vs)
    # 허브에서 시작하는 직선 표시. 끝을 스미어의 뾰족한 픽셀 하나로 결정하지 않는다.
    slope=float(np.sum(ts*vs)/np.sum(ts*ts))
    end=hub+length*(direction+slope*normal)
    residual=float(np.sqrt(np.mean((vs-ts*slope)**2)))
    return end, dict(length_px=length, centerline_rms_px=residual,
                     interpretation='명시한 직선 동작의 색 중심축;스미어 끝의 발목 해석과 숨은 무릎 위치는 추론')
