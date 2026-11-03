"""관측 가능한 2D 투영 길이를 키별로 보존한다. 가려진 축은 기존 풀이를 유지한다."""
import numpy as np
from scipy.interpolate import PchipInterpolator
from rtmw_to_stickman_2d import OBS


def interpolate(x, y, t):
    return np.full(len(t), y[0]) if len(x) == 1 else PchipInterpolator(x, y)(np.clip(t, x[0], x[-1]))


def projected_joints(K, W, half, frames, segments, fallback, S):
    """완전/반쪽 관측의 키 평균 보정량을 보간한다. 결측 축에 새 관측을 만들지 않는다.

    어깨·골반은 중점 허브로 합치되 팔꿈치·손목·무릎·발목의 화면 위치를 보존한다.
    거의 직선인 관측 사슬은 새 허브를 지나는 직선 위에 중간점을 배치한다.
    원시 관측이 틀린 곳을 고치는 모델은 아니다. 그런 곳은 별도 검토가 필요하다.
    """
    T = len(K)
    tt = np.arange(T)
    wax = half[0] if half is not None else np.repeat(W[..., None], 2, axis=2)
    spans = [(frames.index(a), frames.index(b)) for a, b in segments]
    J = {n: v.copy() for n, v in fallback.items()}
    log = []
    for name, j in OBS.items():
        for axis in (0, 1):
            times, deltas = [], []
            for a, b in spans:
                weights = wax[a:b + 1, j, axis]
                if weights.sum() == 0:
                    continue
                center = (a + b) / 2
                obs = np.average(K[a:b + 1, j, axis], weights=weights)
                reference = np.interp(center, tt, fallback[name][:, axis])
                times.append(center)
                deltas.append(obs - reference)
            if times:
                # 유효 키 사이만 보정한다. 관측 범위 밖은 기존 추정으로 남긴다.
                delta = interpolate(times, deltas, tt)
                delta[(tt < np.floor(times[0])) | (tt > np.ceil(times[-1]))] = 0
                J[name][:, axis] += delta
            log.append({'joint': name, 'axis': axis, 'observed_keys': len(times)})
    # 허브 중점은 완전히 관측된 경우에만 원본 중점으로 옮긴다.
    for hub, a, b in [('neck', 'sho_l', 'sho_r'), ('pel', 'hip_l', 'hip_r')]:
        for axis in (0, 1):
            valid = (wax[:, OBS[a], axis] > 0) & (wax[:, OBS[b], axis] > 0)
            # 같은 보정량을 양 끝 평균으로 계산하되 관측이 없는 축은 기존 허브를 유지한다.
            correction = ((J[a] + J[b]) / 2 - fallback[hub])[:, axis]
            if valid.any():
                J[hub][:, axis] += correction
    out = {'neck': J['neck'], 'pelvis': J['pel']}
    for side in ('l', 'r'):
        for root, mid, end, hub in [('sho', 'elb', 'wri', 'neck'), ('hip', 'kne', 'ank', 'pelvis')]:
            out[f'{mid}_{side}'] = J[f'{mid}_{side}'].copy()
            out[f'{end}_{side}'] = J[f'{end}_{side}'].copy()
            a, b, c = J[f'{root}_{side}'], J[f'{mid}_{side}'], J[f'{end}_{side}']
            first = np.linalg.norm(b - a, axis=1)
            second = np.linalg.norm(c - b, axis=1)
            straightness = np.linalg.norm(c - a, axis=1) / np.maximum(first + second, 1e-6)
            # 중점 허브로 옮기면서 직선이 꺾이는 것을 막는다. 관측 없는 사슬에는 적용하지 않는다.
            valid = (W[:, [OBS[f'{root}_{side}'], OBS[f'{mid}_{side}'], OBS[f'{end}_{side}']]] > 0).all(1)
            weight = np.clip((straightness - 0.98) / 0.02, 0, 1) * valid
            target = out[hub] + (c - out[hub]) * (first / np.maximum(first + second, 1e-6))[:, None]
            out[f'{mid}_{side}'] += weight[:, None] * (target - b)
    # 원은 크기를 유지하며 중심만 움직인다. 얼굴은 확률이 아닌 점수로 유효성을 확인한다.
    u = out['neck'] - out['pelvis']
    u /= np.maximum(np.linalg.norm(u, axis=1, keepdims=True), 1e-6)
    diameter = S * (8.4 / 11.2)
    center = out['neck'] + u * diameter[:, None] / 2
    face_keys = []
    for axis in (0, 1):
        times, values = [], []
        for a, b in spans:
            points = []
            for t in range(a, b + 1):
                # 결측 장의 이웃 복사값을 얼굴 관측으로 세지 않는다.
                if not W[t].any():
                    continue
                for js in [(3, 4), (1, 2), (0,)]:
                    if all(K[t, j, 2] >= 1.5 and wax[t, j].all() for j in js):
                        points.append(K[t, list(js), axis].mean())
                        break
            if points:
                times.append((a + b) / 2)
                values.append(np.mean(points))
        if times:
            center[:, axis] = interpolate(times, values, tt)
        face_keys.append(len(times))
    out['head_t'] = center + u * diameter[:, None] / 2
    out['head_b'] = center - u * diameter[:, None] / 2
    return out, {'axis_observations': log, 'face_observed_keys': face_keys,
                 'method': '관측 키별 화면 좌표·투영 길이 보존, 직선 사슬의 허브 보정, 결측 축 기존 풀이'}
