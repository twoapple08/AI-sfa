"""영상 무늬로 같은 그림을 묶는다. 관절 흔들림을 새 그림으로 오인하지 않기 위한 선택 모드."""
import cv2
import numpy as np

from rtmw_validate import color_masks


def color_patch(image, points, color):
    """관측 주변 인물색을 템플릿으로 쓴다. 색은 관절 정답 판정에 쓰지 않는다."""
    _, blue, red = color_masks(image)
    mask = blue if color == 'blue' else red
    valid = points[np.isfinite(points).all(1) & (points[:, 2] >= 1.5), :2]
    if len(valid) < 4:
        return None
    height, width = image.shape[:2]
    low, high = valid.min(0), valid.max(0)
    pad = max(20., float(np.max(high - low)) * .15)
    x0, y0 = np.clip((low - pad).astype(int), [0, 0], [width, height])
    x1, y1 = np.clip((high + pad).astype(int), [0, 0], [width, height])
    if x1 <= x0 or y1 <= y0:
        return None
    region = np.zeros(mask.shape, np.uint8)
    region[y0:y1, x0:x1] = mask[y0:y1, x0:x1]
    ys, xs = np.where(region)
    if len(xs) < 30:
        return None
    x0, y0 = max(0, int(xs.min()) - 5), max(0, int(ys.min()) - 5)
    x1, y1 = min(width, int(xs.max()) + 6), min(height, int(ys.max()) + 6)
    local = cv2.dilate(region[y0:y1, x0:x1], np.ones((7, 7), np.uint8))
    return image[y0:y1, x0:x1], local, (x0, y0, x1, y1)


def match_patches(previous, current, image):
    """작은 확대·축소와 위치 이동을 허용한 원본 템플릿 정합. 실패하면 미확정이다."""
    if previous is None or current is None:
        return None
    patch, mask, box = previous
    bb = current[2]
    height, width = image.shape[:2]
    x0, y0 = max(0, bb[0] - 90), max(0, bb[1] - 90)
    x1, y1 = min(width, bb[2] + 90), min(height, bb[3] + 90)
    search = image[y0:y1, x0:x1]
    gray = cv2.cvtColor(search, cv2.COLOR_BGR2GRAY)
    best = None
    for scale in (.98, 1., 1.02):
        template = cv2.resize(patch, None, fx=scale, fy=scale, interpolation=cv2.INTER_LINEAR)
        local = cv2.resize(mask, (template.shape[1], template.shape[0]), interpolation=cv2.INTER_NEAREST)
        if template.shape[0] > gray.shape[0] or template.shape[1] > gray.shape[1]:
            continue
        scores = cv2.matchTemplate(gray, cv2.cvtColor(template, cv2.COLOR_BGR2GRAY), cv2.TM_CCOEFF_NORMED, mask=local)
        if not np.isfinite(scores).any():
            continue
        scores[~np.isfinite(scores)] = -1
        _, corr, _, (xx, yy) = cv2.minMaxLoc(scores)
        actual = search[yy:yy + template.shape[0], xx:xx + template.shape[1]]
        selected = local > 0
        error = float(np.abs(template.astype(float)[selected] - actual.astype(float)[selected]).mean() / 255)
        if best is None or corr > best['ncc']:
            best = dict(ncc=corr, mae=error, scale=scale, translation=[x0 + xx - box[0], y0 + yy - box[1]])
    return best


def segments_from_matches(frames, pose_segments, matches, key_starts=()):
    """확실한 같은/다른 그림만 경계를 수정한다. 중간·실패 값은 기존 경계를 따른다."""
    if not frames or len(matches) != len(frames) - 1 or list(frames) != sorted(set(frames)):
        raise ValueError('오름차순 장 목록과 모든 이웃 정합 결과가 필요하다')
    if not set(key_starts).issubset(frames):
        raise ValueError('명시 키 시작이 처리 구간 밖이다')
    pose_edges = {a for a, _ in pose_segments}
    starts, decisions = {frames[0], *key_starts}, []
    for frame, match in zip(frames[1:], matches):
        boundary, reason = frame in pose_edges, '기존 관절 경계 유지'
        if match is not None:
            if match['ncc'] >= .90 and match['mae'] <= .06:
                boundary, reason = False, '같은 그림 정합'
            elif match['ncc'] <= .65 and match['mae'] >= .08:
                boundary, reason = True, '다른 그림 정합'
        if frame in key_starts:
            boundary, reason = True, '명시 키 시작 유지'
        if boundary:
            starts.add(frame)
        decisions.append(dict(frame=frame, boundary=boundary, reason=reason, match=match))
    indexes = [i for i, f in enumerate(frames) if f in starts]
    segments = [(frames[a], frames[indexes[i + 1] - 1] if i + 1 < len(indexes) else frames[-1]) for i, a in enumerate(indexes)]
    return segments, decisions


def video_segments(video, frames, K, W, color, pose_segments, key_starts=()):
    cap = cv2.VideoCapture(str(video))
    cap.set(cv2.CAP_PROP_POS_FRAMES, frames[0])
    previous, matches = None, []
    try:
        for i, frame in enumerate(frames):
            if i and frame != frames[i - 1] + 1:
                cap.set(cv2.CAP_PROP_POS_FRAMES, frame)
            ok, image = cap.read()
            if not ok:
                raise ValueError(f'원본 {frame}장 읽기 실패')
            current = color_patch(image, K[i], color) if W[i].any() else None
            if i:
                matches.append(match_patches(previous, current, image))
            previous = current
    finally:
        cap.release()
    return segments_from_matches(frames, pose_segments, matches, key_starts)


def align_limb_pairs(K, weights, spans, scale, allow_parts=('arm', 'leg'), preserve_short_gaps=False):
    """완전 관측 사슬만 2D 가지로 추적한다. 해부학적 좌우 복구라는 뜻은 아니다.

    키의 첫 관측을 이전 키와 맞추고, 같은 그림 안에서는 첫 관측과 맞춰 평균 전 교환을 막는다.
    가림·반쪽 관측은 교환하지 않되 짧은 가림 뒤의 관측에 이전 기준을 유지한다.
    팔/다리 전체를 교환해 사슬을 섞지 않는다.
    """
    K, weights = K.copy(), weights.copy()
    events = []
    for label, left, right in [('arm', [5, 7, 9], [6, 8, 10]), ('leg', [11, 13, 15], [12, 14, 16])]:
        if label not in allow_parts:
            continue
        prior, gap = None, 0
        for a, b in spans:
            anchor, values, first_valid = prior, [], True
            for t in range(a, b + 1):
                if not (weights[t, left + right] > 0).all():
                    if not preserve_short_gaps:
                        anchor, prior, values, first_valid = None, None, [], True
                    continue
                hub = (K[t, left[0], :2] + K[t, right[0], :2]) / 2
                vector = (K[t, [left[1:], right[1:]], :2] - hub) / max(float(scale[t]), 1e-6)
                if anchor is not None:
                    same = float(((vector - anchor) ** 2).sum())
                    swap = float(((vector[::-1] - anchor) ** 2).sum())
                    if swap < same * .8 and same - swap > .04:
                        for l, r in zip(left, right):
                            K[t, [l, r]] = K[t, [r, l]]
                            weights[t, [l, r]] = weights[t, [r, l]]
                        vector = vector[::-1]
                        events.append(dict(index=t, part=label, same_cost=same, swap_cost=swap, within_key=t > a))
                if anchor is None or first_valid:
                    anchor = vector
                    first_valid = False
                values.append(vector)
            if not preserve_short_gaps:
                prior = np.mean(values, axis=0) if values and (weights[b, left + right] > 0).all() else None
            elif values:
                prior, gap = np.median(values, axis=0), 0
            else:
                gap += 1
                if gap > 2:
                    prior = None
    return K, weights, events
