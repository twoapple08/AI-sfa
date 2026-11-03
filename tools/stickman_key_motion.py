"""그림 키 단위의 척도·관측과 중복 가지 검사. 장 번호 예외나 속도 상한을 쓰지 않는다."""
import numpy as np
from scipy.interpolate import PchipInterpolator


def keyed_medians(values, spans):
    values = np.asarray(values, float)
    times = np.array([(a+b)/2 for a, b in spans])
    anchors = np.array([np.median(values[a:b+1], axis=0) for a, b in spans])
    if not np.isfinite(anchors).all():
        raise ValueError('키의 척도/위치는 유한해야 한다')
    if len(times) == 1:
        return np.broadcast_to(anchors[0], values.shape).copy()
    return PchipInterpolator(times, anchors, axis=0)(np.clip(np.arange(len(values)), times[0], times[-1]))


def axis_from_keys(observed, weights, fallback, spans, side=None, bounds=None, axis=0, rejected=None):
    """관측은 키 평균,가림은 해당 키의 추정/경계. 한 번의 가림으로 컷 전체를 잠그지 않는다."""
    if not (weights > 0).any():
        return np.asarray(fallback, float).copy(), []
    times, values, inferred = [], [], []
    for key, (a, b) in enumerate(spans):
        w = weights[a:b+1]
        if w.sum():
            value = np.average(observed[a:b+1], weights=w)
        elif rejected is not None and rejected[a:b+1].any():
            # 다른 가지로 중복된 관측을 기존 풀이의 같은 잘못된 값으로 다시 채우지 않는다.
            inferred.append(key)
            continue
        else:
            value = float(np.median(fallback[a:b+1]))
            if side is not None and bounds is not None:
                codes = set(side[a:b+1]) - {0}
                low_code, high_code = (3, 4) if axis == 0 else (2, 1)
                low, high = bounds[:2] if axis == 0 else bounds[2:]
                if low_code in codes and high_code not in codes:
                    value = min(value, low)
                elif high_code in codes and low_code not in codes:
                    value = max(value, high)
            inferred.append(key)
        times.append((a+b)/2)
        values.append(value)
    if not times:
        return np.asarray(fallback, float).copy(), inferred
    if len(times) == 1:
        return np.full(len(fallback), values[0]), inferred
    return PchipInterpolator(times, values)(np.clip(np.arange(len(fallback)), times[0], times[-1])), inferred


def rebase_arm(hub, elbow, wrist, upper, forearm):
    """같은 키에서 잰 투영 길이로 팔꿈치만 재배치한다. 손목과 몸통은 움직이지 않는다."""
    hub, elbow, wrist = (np.asarray(value, float) for value in (hub, elbow, wrist))
    upper, forearm = np.broadcast_arrays(np.asarray(upper, float), np.asarray(forearm, float))
    delta = wrist-hub
    distance = np.linalg.norm(delta, axis=-1)
    feasible = ((distance > 1e-8) & (distance <= upper+forearm+1e-8)
                & (distance >= np.abs(upper-forearm)-1e-8) & (upper > 0) & (forearm > 0))
    direction = delta/np.maximum(distance[..., None], 1e-8)
    along = (upper**2-forearm**2+distance**2)/(2*np.maximum(distance, 1e-8))
    height = np.sqrt(np.maximum(upper**2-along**2, 0))
    normal = np.stack([-direction[..., 1], direction[..., 0]], -1)
    center = hub+along[..., None]*direction
    first, second = center+height[..., None]*normal, center-height[..., None]*normal
    choose = np.sum((first-elbow)**2, axis=-1) <= np.sum((second-elbow)**2, axis=-1)
    target = np.where(choose[..., None], first, second)
    return np.where(feasible[..., None], target, elbow), feasible


def projected_arm_lengths(K, weights, spans, hub, elbow, wrist, joints):
    """고정 뼈 길이가 아니라 원본 키마다 다른2D 팔 길이를 쓴다. 직선 펀치는 보존한다."""
    times, values, bends = [], [], []
    for a, b in spans:
        points = K[a:b+1, list(joints), :2]
        valid = (weights[a:b+1, list(joints)] > 0).all((1, 2)) & np.isfinite(points).all((1, 2))
        if not valid.any():
            continue
        points = points[valid]
        upper = np.linalg.norm(points[:, 1]-points[:, 0], axis=1)
        forearm = np.linalg.norm(points[:, 2]-points[:, 1], axis=1)
        straightness = np.linalg.norm(points[:, 2]-points[:, 0], axis=1)/np.maximum(upper+forearm, 1e-8)
        times.append((a+b)/2)
        values.append(np.median(np.c_[upper, forearm], axis=0))
        bends.append(float(np.median(np.clip((.98-straightness)/.1, 0, 1))))
    if not times:
        return elbow.copy(), dict(source_keys=0, changed_frames=0, endpoint_shift_px=0.)
    tt = np.arange(len(K))
    desired = (np.broadcast_to(values[0], (len(K), 2)).copy() if len(times) == 1
               else PchipInterpolator(times, values, axis=0)(np.clip(tt, times[0], times[-1])))
    blend = np.interp(tt, times, bends)
    blend[(tt < np.floor(times[0])) | (tt > np.ceil(times[-1]))] = 0
    target, feasible = rebase_arm(hub, elbow, wrist, desired[:, 0], desired[:, 1])
    attempted = blend > 0
    blend *= feasible
    out = elbow+(target-elbow)*blend[:, None]
    changed = np.linalg.norm(out-elbow, axis=1) > 1e-6
    return out, dict(source_keys=len(times), changed_frames=int(changed.sum()),
        infeasible_frames=int((~feasible & attempted).sum()), endpoint_shift_px=0.,
        method='원본 키별 투영 상완/전완 길이,손목·몸통 유지,가능한 팔꿈치 중 관측에 가까운 쪽;직선 보존')


def reject_duplicate_chains(K, weights, spans, scale, max_gap_keys=2):
    """양 중간점과 끝점이 동시에 중복되고 시간 문맥이 한 가지만 지지할 때만 관측을 뺀다.

    손끝만 맞닿는 접촉·두 가지가 실제 교차하는 키·빠른 단독 이동을 제거하지 않는다.
    좌표를 정답으로 만들어 넣지 않고 거부 마스크/추론 기록을 반환한다.
    """
    weights = weights.copy()
    rejected = np.zeros(K.shape[:2], bool)
    events = []
    times = np.array([(a+b)/2 for a, b in spans])
    for part, roots, branches in [('arm', [5, 6], [[7, 9], [8, 10]]),
                                   ('leg', [11, 12], [[13, 15], [14, 16]])]:
        vectors, good, duplicate = [], [], []
        for a, b in spans:
            hub = np.median(K[a:b+1, roots, :2].mean(1), axis=0)
            s = max(float(np.median(scale[a:b+1])), 1e-6)
            points = np.full((2, 2, 2), np.nan)
            for branch, js in enumerate(branches):
                for endpoint, j in enumerate(js):
                    ok = (weights[a:b+1, j] > 0).all(1)
                    if ok.any():
                        points[branch, endpoint] = np.median(K[a:b+1, j, :2][ok], axis=0)
            vector = (points-hub)/s
            eps = max(.025, 1.5/s)
            finite = np.isfinite(vector).all()
            dup = finite and (np.linalg.norm(vector[0]-vector[1], axis=1) <= eps).all()
            vectors.append(vector)
            good.append(finite and not dup)
            duplicate.append((dup, eps))
        for key, (dup, eps) in enumerate(duplicate):
            if not dup:
                continue
            before = next((i for i in range(key-1, max(-1, key-max_gap_keys-2), -1) if good[i]), None)
            after = next((i for i in range(key+1, min(len(spans), key+max_gap_keys+2)) if good[i]), None)
            if before is None and after is None:
                continue
            if before is None:
                predicted = vectors[after]
            elif after is None:
                predicted = vectors[before]
            else:
                mix = (times[key]-times[before])/(times[after]-times[before])
                predicted = vectors[before]*(1-mix)+vectors[after]*mix
            # 실제 교차/접촉으로 양쪽이 모일 수 있는 시간 문맥이면 관측을 유지한다.
            if not (np.linalg.norm(predicted[0]-predicted[1], axis=1) > 4*eps).all():
                continue
            shared = vectors[key].mean(0)
            costs = np.linalg.norm(predicted-shared, axis=(1, 2))
            keep, drop = int(costs.argmin()), int(costs.argmax())
            if costs[keep] >= costs[drop]*.35 or costs[drop] <= 4*eps:
                continue
            a, b = spans[key]
            for t in range(a, b+1):
                if not (weights[t, branches[0]+branches[1]] > 0).all():
                    continue
                if not (np.linalg.norm(K[t, branches[0], :2]-K[t, branches[1], :2], axis=1) <= eps*scale[t]).all():
                    continue
                weights[t, branches[drop]] = 0
                rejected[t, branches[drop]] = True
                events.append(dict(index=t, key=key, part=part, dropped=branches[drop],
                                   reason='양 중간점/끝점 중복,시간 문맥의 다른 가지 관측은 없음'))
    return weights, rejected, events
