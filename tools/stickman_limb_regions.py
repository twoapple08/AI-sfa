"""명시한 구도의 서로 다른 화면 영역에서 팔 관측을 모은다. 자동 구도 분류 아님."""
import numpy as np
from scipy.interpolate import PchipInterpolator


def regional_arm_tracks(K, support, observed, frames, spans, actor, width, regions):
    """좌우 라벨이 뒤집혀도 영역별 관측을 보존. 키별 대표값·미관측 보간은 별도 기록."""
    K, support, observed = np.asarray(K), np.asarray(support), np.asarray(observed)
    if width <= 0 or K.shape[:2] != support.shape or len(frames) != len(K):
        raise ValueError('관측/영상 범위 오류')
    tracks, report = [], []
    occupied = set()
    for region in regions:
        lo, hi = region['x_range']
        side = region['side']
        if side not in ('l', 'r') or side in occupied or not 0 <= lo < hi <= 1:
            raise ValueError('서로 다른 출력 팔/정규화 영역이 필요하다')
        occupied.add(side)
        times, points, source_frames = [], [], []
        for a, b in spans:
            values, measured = [], []
            for i in range(a, b+1):
                if not observed[i]:
                    continue
                for js in ([7, 9], [8, 10]):
                    p = K[i, js]
                    if ((p[:, 2] >= 2.5).all() and (support[i, js] >= .1).all()
                            and (p[:, 0] >= lo*width).all() and (p[:, 0] < hi*width).all()):
                        values.append(p[:, :2]); measured.append(frames[i])
            if values:
                times.append((a+b)/2)
                points.append(np.median(values, axis=0))
                source_frames.extend(measured)
        if not times:
            raise ValueError('영역 안에 유효한 팔 관측이 없다: '+side)
        t = np.clip(np.arange(len(K)), times[0], times[-1])
        values = (np.broadcast_to(points[0], (len(K),2,2)) if len(times) == 1
                  else PchipInterpolator(times, points, axis=0)(t))
        keys = {str(f): {f'elb_{side}': values[i,0].tolist(), f'wri_{side}': values[i,1].tolist()}
                for i,f in enumerate(frames)}
        tracks.append(dict(actor=actor, start=frames[0], end=frames[-1], feather=0, keys=keys,
                           evidence='명시 화면 영역의 원관측·색 지지,키 대표값 보간. 미관측/끝 유지 추론,실제 해부학적 좌우 아님'))
        report.append(dict(side=side, source_frames=sorted(set(source_frames)), source_keys=len(times),
                           held_before_frame=frames[int(np.floor(times[0]))],
                           held_after_frame=frames[int(np.ceil(times[-1]))]))
    return tracks, report
