"""관측 가능한 2D 투영 길이를 키별로 보존한다. 가려진 축은 기존 풀이를 유지한다."""
import numpy as np
from scipy.interpolate import PchipInterpolator
from rtmw_to_stickman_2d import OBS


def interpolate(x, y, t):
    return np.full(len(t), y[0]) if len(x) == 1 else PchipInterpolator(x, y)(np.clip(t, x[0], x[-1]))


def constrain_head_contact(neck, head_t, head_b):
    """머리 원이 허브를 덮도록 중심만 최소 이동한다(사용자 A안).

    이미 겹친 고개 숙임과 원 지름·몸통·팔은 유지한다. 단일 점과 장별 배열 모두 지원한다.
    원 내부의 편집용 연결선은 별개이며, 이 함수가 점 공유 접합으로 바꾸지는 않는다.
    """
    neck, head_t, head_b = (np.asarray(p, dtype=float) for p in (neck, head_t, head_b))
    center = (head_t + head_b) / 2
    radius = np.linalg.norm(head_t - head_b, axis=-1, keepdims=True) / 2
    offset = neck - center
    distance = np.linalg.norm(offset, axis=-1, keepdims=True)
    shift = offset * (np.maximum(distance - radius, 0) / np.maximum(distance, 1e-12))
    return head_t + shift, head_b + shift, shift


def guard_hidden_chains(joints, half):
    """부모 마디가 틀 밖이고 자식 관측을 완전히 버렸다면, 추정 자식이 안쪽으로 접혀 나오지 않게 한다."""
    if half is None:
        return []
    wax, side, _ = half
    changes = []
    for parent, child in [('elb_l', 'wri_l'), ('elb_r', 'wri_r'), ('kne_l', 'ank_l'), ('kne_r', 'ank_r')]:
        p, c = OBS[parent], OBS[child]
        unobserved = ~(wax[:, c] > 0).any(1)
        for code, axis, sign in ((1, 1, 1), (2, 1, -1), (3, 0, -1), (4, 0, 1)):
            hidden = unobserved & (side[:, p] == code)
            delta = joints[child][:, axis] - joints[parent][:, axis]
            bad = hidden & (sign * delta < 0)
            joints[child][bad, axis] = joints[parent][bad, axis] + sign * np.abs(delta[bad])
            changes.extend({'index': int(t), 'joint': child, 'axis': axis, 'reason': '틀 밖 부모의 완전 결측 자식'}
                           for t in np.flatnonzero(bad))
    return changes


def projected_joints(K, W, half, frames, segments, fallback, S, direct_keys=False, track_pairs=True):
    """완전/반쪽 관측의 키 평균 보정량을 보간한다. 결측 축에 새 관측을 만들지 않는다.

    어깨·골반은 중점 허브로 합치되 팔꿈치·손목·무릎·발목의 화면 위치를 보존한다.
    거의 직선인 관측 사슬은 새 허브를 지나는 직선 위에 중간점을 배치한다.
    원시 관측이 틀린 곳을 고치는 모델은 아니다. 그런 곳은 별도 검토가 필요하다.
    direct_keys=True는 선택 모드다. 관측 키 좌표를 직접 잇되 틀 밖 축은 기존 잔차 방식으로
    보호하고, 완전 관측 사슬만2D 가지로 대응한다. 고정 리그의 관측 불가 축을 끌어들이지 않는다.
    """
    T = len(K)
    tt = np.arange(T)
    wax = half[0] if half is not None else np.repeat(W[..., None], 2, axis=2)
    spans = [(frames.index(a), frames.index(b)) for a, b in segments]
    pair_events = []
    protected = set()
    allowed_parts = ['arm', 'leg']
    if direct_keys and half is not None:
        side = half[1]
        for name, j in OBS.items():
            for axis, codes in ((0, (3, 4)), (1, (1, 2))):
                if np.isin(side[:, j], codes).any():
                    protected.add((name, axis))
        # 반쪽 관측을 가진 사슬은 기존 좌우 이름·추정 축을 함께 보존한다.
        allowed_parts = [part for part, js in [('arm', [5, 6, 7, 8, 9, 10]), ('leg', [11, 12, 13, 14, 15, 16])]
                         if not (side[:, js] > 0).any()]
    if direct_keys and track_pairs:
        from stickman_image_keys import align_limb_pairs
        K, wax, pair_events = align_limb_pairs(K, wax, spans, S, allowed_parts)
    J = {n: v.copy() for n, v in fallback.items()}
    log = []
    for name, j in OBS.items():
        for axis in (0, 1):
            use_direct = direct_keys and (name, axis) not in protected
            times, deltas = [], []
            for a, b in spans:
                weights = wax[a:b + 1, j, axis]
                if weights.sum() == 0:
                    continue
                center = (a + b) / 2
                obs = np.average(K[a:b + 1, j, axis], weights=weights)
                reference = np.interp(center, tt, fallback[name][:, axis])
                times.append(center)
                deltas.append(obs if use_direct else obs - reference)
            if times:
                # 유효 키 사이만 보정한다. 관측 범위 밖은 기존 추정으로 남긴다.
                delta = interpolate(times, deltas, tt)
                valid_range = (tt >= np.floor(times[0])) & (tt <= np.ceil(times[-1]))
                if use_direct:
                    J[name][valid_range, axis] = delta[valid_range]
                else:
                    delta[~valid_range] = 0
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
            if direct_keys and (a, axis) not in protected and (b, axis) not in protected:
                times, values = [], []
                for start, end in spans:
                    paired = np.minimum(wax[start:end + 1, OBS[a], axis], wax[start:end + 1, OBS[b], axis])
                    if paired.sum() > 0:
                        midpoint = (K[start:end + 1, OBS[a], axis] + K[start:end + 1, OBS[b], axis]) / 2
                        times.append((start + end) / 2)
                        values.append(np.average(midpoint, weights=paired))
                if times:
                    # 양쪽을 따로 PCHIP한 뒤 평균하면 좌우 이름 교환만으로도 허브가 흔들릴 수 있다.
                    inside = (tt >= np.floor(times[0])) & (tt <= np.ceil(times[-1]))
                    J[hub][inside, axis] = interpolate(times, values, tt)[inside]
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
    hidden_chain_changes = guard_hidden_chains(out, half)
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
    out['head_t'], out['head_b'], shift = constrain_head_contact(out['neck'], out['head_t'], out['head_b'])
    moved = np.linalg.norm(shift, axis=-1)
    return out, {'axis_observations': log, 'face_observed_keys': face_keys,
                 'hidden_chain_changes': [dict(frame=frames[e['index']], **e) for e in hidden_chain_changes],
                 'direct_observation_keys': direct_keys,
                 'protected_edge_axes': [{'joint': n, 'axis': a} for n, a in sorted(protected)],
                 'pair_tracking_allowed_parts': allowed_parts if direct_keys and track_pairs else [],
                 'pair_tracking': [dict(frame=frames[e['index']], **e) for e in pair_events],
                 'head_contact': {'method': '사용자 A안: 머리 중심만 최소 이동, 기존 겹침 유지',
                                  'moved_frames': int((moved > 1e-7).sum()), 'max_shift_px': float(moved.max())},
                 'method': '관측 키별 화면 좌표·투영 길이 보존, 직선 사슬의 허브 보정, 결측 축 기존 풀이'}
