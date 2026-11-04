"""잘린 인물의 보이는 부분을 별도 관측으로 복구하는 선택 처리.

고정 리그/AC는 바꾸지 않는다. 원영상 색 지지와 독립 얼굴 관측을 함께 쓰며,
화면 밖 위치는 추론이라고 기록한다. 얼굴 미검출만으로 인물을 삭제하지 않는다.
"""
import cv2
import numpy as np
from scipy.interpolate import PchipInterpolator


def match_face(rows, keypoints, own, other, minimum_score=.6):
    """다른 곳의 얼굴/병 무늬를 대상 머리의 증거로 쓰지 않는다."""
    points = keypoints[:5]
    points = points[points[:, 2] >= 1.5, :2]
    if not len(points):
        return None
    center = np.median(points, axis=0)
    candidates = []
    for row in rows:
        # 보조 모델의 약한 얼굴 후보를 머리 확대의 근거로 승격하지 않는다.
        # 낮은 점수의 진짜 얼굴도 있으므로 이 문턱은 인물 존재/삭제 판정에는 쓰지 않는다.
        if row['score'] < minimum_score:
            continue
        x, y, w, h = row['box']
        face_center = np.array([x+w/2, y+h/2])
        diameter = float(np.hypot(w, h))
        if np.linalg.norm(face_center-center) > .75*diameter:
            continue
        x0, x1 = max(0, int(x)), min(own.shape[1], int(np.ceil(x+w)))
        y0, y1 = max(0, int(y)), min(own.shape[0], int(np.ceil(y+h)))
        if x1 <= x0 or y1 <= y0:
            continue
        a, b = own[y0:y1, x0:x1].mean(), other[y0:y1, x0:x1].mean()
        if a < .01 or a <= b:
            continue
        candidates.append((np.linalg.norm(face_center-center)/diameter, [*face_center, diameter]))
    return np.array(min(candidates, key=lambda t: t[0])[1]) if candidates else None


def image_support(video, frames, K, color, faces, face_score_floor=.6):
    from rtmw_validate import color_masks
    cap = cv2.VideoCapture(video)
    support = np.zeros(K.shape[:2])
    matched = np.full((len(K), 3), np.nan)
    next_frame = None
    for t, f in enumerate(frames):
        if f != next_frame:
            cap.set(cv2.CAP_PROP_POS_FRAMES, f)
        ok, image = cap.read()
        if not ok:
            raise ValueError(f'원영상 {f}장을 읽을 수 없다')
        next_frame = f + 1
        _, blue, red = color_masks(image)
        own, other = (blue, red) if color == 'blue' else (red, blue)
        face = match_face((faces or {}).get('frames', {}).get(str(f), []), K[t], own, other, face_score_floor)
        if face is not None:
            matched[t] = face
        for j, point in enumerate(K[t]):
            x, y = point[:2]
            if not 0 <= x < image.shape[1] or not 0 <= y < image.shape[0]:
                continue
            x, y = int(x), int(y)
            region = (slice(max(0, y-4), y+5), slice(max(0, x-4), x+5))
            support[t, j] = max(float(own[region].mean()-other[region].mean()), 0.)
    cap.release()
    return support, matched


def transfer_face_box(anchor, current, face):
    """같은 컷의 독립 얼굴을5개 얼굴점의2D 닮음 변환으로 옮긴다. 손의 가짜 얼굴 단독은 못 쓴다."""
    valid = (anchor[:5, 2] >= 1.5) & (current[:5, 2] >= 1.5)
    if valid.sum() < 3:
        return None
    old, new = anchor[:5, :2][valid], current[:5, :2][valid]
    a, b = old-old.mean(0), new-new.mean(0)
    if np.linalg.matrix_rank(a) < 2 or (a*a).sum() < 1:
        return None
    u, singular, vt = np.linalg.svd(a.T@b)
    parity = np.array([1., np.sign(np.linalg.det(u@vt))])
    rotation = u@np.diag(parity)@vt
    scale = (singular*parity).sum()/(a*a).sum()
    if not .4 <= scale <= 2.5:
        return None
    error = np.sqrt(np.mean(np.sum((a@rotation*scale-b)**2, axis=1)))
    if error > .06*face[2]*scale:
        return None
    center = (face[:2]-old.mean(0))@rotation*scale+new.mean(0)
    return np.array([*center, face[2]*scale])


def recover_key_views(K, joints, scale, spans, matched, support, bounds, observed=None, forced_lower=None):
    """큰 얼굴/윗몸 잘림의 명확한 경우만 처리. 모호한 검출은 검토 목록에 남긴다."""
    result = {name: value.copy() for name, value in joints.items()}
    scale = np.asarray(scale, float).copy()
    visible = np.ones((len(K), 10), bool)
    left, right, top, bottom = bounds
    height = bottom-top
    observed = np.ones(len(K), bool) if observed is None else np.asarray(observed, bool)
    forced_lower = np.zeros(len(K), bool) if forced_lower is None else np.asarray(forced_lower, bool)
    key_raw = [np.median(K[a:b+1], axis=0) for a, b in spans]
    key_faces = []
    face_inferred = np.zeros(len(spans), bool)
    for a, b in spans:
        values = matched[a:b+1]
        values = values[np.isfinite(values).all(1)]
        key_faces.append(np.median(values, axis=0) if len(values) else None)
    # 얼굴 검출 누락 한두 키 때문에 큰 머리/작은 머리가 번갈아 나타나지 않게 한다.
    valid_faces = [i for i, value in enumerate(key_faces) if value is not None]
    for key, face in enumerate(key_faces):
        if face is not None:
            continue
        before = next((i for i in reversed(valid_faces) if i < key), None)
        after = next((i for i in valid_faces if i > key), None)
        if before is None or after is None:
            nearest = before if before is not None else after
            if nearest is None or abs(nearest-key) > 1:
                continue
            old = key_raw[nearest][:5]
            new = key_raw[key][:5]
            common = (old[:, 2] >= 1.5) & (new[:, 2] >= 1.5)
            if common.sum() < 3:
                continue
            delta = np.median(new[common, :2]-old[common, :2], axis=0)
            if np.linalg.norm(delta) > .25*key_faces[nearest][2]:
                continue
            guess = key_faces[nearest]+[*delta, 0]
        else:
            if after-before > 3:
                continue
            mix = ((sum(spans[key])/2-sum(spans[before])/2)
                   / (sum(spans[after])/2-sum(spans[before])/2))
            guess = key_faces[before]*(1-mix)+key_faces[after]*mix
        points = key_raw[key][:5]
        points = points[points[:, 2] >= 1.5, :2]
        if len(points) and np.linalg.norm(np.median(points, axis=0)-guess[:2]) <= .75*guess[2]:
            key_faces[key], face_inferred[key] = guess, True
    # 검출기가 여러 키를 놓쳐도,같은 컷의 확인된 얼굴과 얼굴점의 모양이 일치하면
    # 그 독립 관측을 이동/확대한다. 손·몸 일부만 있는 컷에는 독립 기준이 없어 적용되지 않는다.
    for key, face in enumerate(key_faces):
        if face is not None:
            continue
        for anchor in sorted(valid_faces, key=lambda i: abs(sum(spans[i])-sum(spans[key]))):
            guess = transfer_face_box(key_raw[anchor], key_raw[key], key_faces[anchor])
            if guess is not None:
                key_faces[key], face_inferred[key] = guess, True
                break
    face_active = np.zeros(len(spans), bool)
    face_compatible = np.zeros(len(spans), bool)
    for key, (raw, face) in enumerate(zip(key_raw, key_faces)):
        if face is None:
            continue
        neck, pelvis = raw[[5, 6], :2].mean(0), raw[[11, 12], :2].mean(0)
        cropped = pelvis[1] > bottom-.2*face[2]
        face_compatible[key] = face[2] > .2*height and cropped
        face_active[key] = face[2] > .35*height and cropped and np.linalg.norm(neck-pelvis) < .6*face[2]
    # 같은 컷에서 계속 확대되는 얼굴은 한계값을 넘은 장부터 갑자기 커지지 않게,
    # 이어지는 독립 얼굴+잘린 하체 관측으로 같은 표현을 유지한다.
    changed = True
    while changed:
        expanded = face_active.copy()
        for key in range(len(spans)):
            if face_compatible[key] and ((key and face_active[key-1])
                                         or (key+1 < len(spans) and face_active[key+1])):
                expanded[key] = True
        changed = not np.array_equal(expanded, face_active)
        face_active = expanded
    # 몸 일부만 보이는 컷에서 높은 점수의 발목이 그림자/배경에 붙는 경우.
    # 색 지지가 없는 점을 정답으로 고정하지 않고, 같은 컷의 가까운 유효 키로만 잇는다.
    trusted = {}
    for j in (13, 14, 15, 16):
        times, points, ids = [], [], []
        for key, (a, b) in enumerate(spans):
            points_in_key = K[a:b+1, j, :2]
            good = ((K[a:b+1, j, 2] >= 1.5) & (support[a:b+1, j] >= .05)
                    & observed[a:b+1] & (points_in_key[:, 0] > left+8)
                    & (points_in_key[:, 0] < right-8) & (points_in_key[:, 1] > top+8)
                    & (points_in_key[:, 1] < bottom-8))
            if good.any():
                times.append((a+b)/2)
                points.append(np.median(points_in_key[good], axis=0))
                ids.append(key)
        if points:
            for key, (a, b) in enumerate(spans):
                if min(abs(key-i) for i in ids) > 2:
                    continue
                t = np.clip((a+b)/2, times[0], times[-1])
                point = points[0] if len(points) == 1 else PchipInterpolator(times, points)(t)
                trusted[j, key] = np.asarray(point), key not in ids
    targets, modes, report = [], [], []
    for key, (a, b) in enumerate(spans):
        raw = key_raw[key]
        evidence = np.median(support[a:b+1], axis=0)
        pose = {n: np.median(v[a:b+1], axis=0) for n, v in joints.items()}
        current_size = float(np.median(scale[a:b+1]))
        neck = raw[[5, 6], :2].mean(0)
        pelvis = raw[[11, 12], :2].mean(0)
        torso = np.linalg.norm(neck-pelvis)
        face = key_faces[key]
        lengths = [np.linalg.norm(raw[hip, :2]-raw[knee, :2]) + np.linalg.norm(raw[knee, :2]-raw[ankle, :2])
                   for hip, knee, ankle in [(11, 13, 15), (12, 14, 16)]
                   if min(raw[[knee, ankle], 2]) >= 1.5]
        leg = float(np.median(lengths)) if lengths else 0.
        mode = 'unchanged'
        lower_view = bool(forced_lower[a:b+1].all())
        visibility = np.ones(10, bool)
        # 서로 다른 모델의 얼굴 관측 + 아래 경계로 붕괴한 몸통이 동시에 있을 때만 확대 복구.
        if face_active[key] and not lower_view:
            mode = 'large_face_cropped_body'
            center, diameter = face[:2], face[2]
            down = neck-center
            down /= max(np.linalg.norm(down), 1e-9)
            if down[1] <= 0:
                down = np.array([0., 1.])
            pose['head_t'] = center-down*diameter/2
            pose['head_b'] = center+down*diameter/2
            pose['neck'] = pose['head_b'].copy()
            distance = max(diameter/.75, (bottom-pose['neck'][1]+diameter/2)/max(down[1], .1))
            pose['pelvis'] = pose['neck']+down*distance
            current_size = diameter/.75
            # 관측되지 않은 양팔/하체를 화면 아래에서 가짜 전신으로 펼치지 않는다.
            visibility[:] = False
            visibility[:2] = True
            margin = max(8., .06*diameter)
            for side, elbow, wrist, upper, forearm in [('r', 8, 10, 3, 4), ('l', 7, 9, 5, 6)]:
                for name, j, oid in [(f'elb_{side}', elbow, upper), (f'wri_{side}', wrist, forearm)]:
                    x, y = raw[j, :2]
                    valid = (raw[j, 2] >= 1.5 and evidence[j] >= .05
                             and left+margin < x < right-margin and top+margin < y < bottom-margin)
                    if j == wrist:
                        parent=raw[elbow]
                        parent_inside=(left+margin<parent[0]<right-margin and top+margin<parent[1]<bottom-margin
                                       and parent[2]>=1.5 and evidence[elbow]>=.05)
                        parent_outside=(parent[0]<left or parent[0]>right or parent[1]<top or parent[1]>bottom)
                        valid = valid and (parent_inside or parent_outside)
                    if valid:
                        pose[name] = raw[j, :2].copy()
                        visibility[oid-1] = True
        # 잘린 부모가 있다는 이유만으로 화면 안의 진짜 무릎/발목까지 없애지 않는다.
        elif lower_view or (leg > .25*height and torso < .3*leg
              and np.max(raw[[0, 3, 4, 5, 6, 11, 12], 1]) < top+.18*leg
              and (face is None or face[2] < .2*height)
              and sum(raw[j, 2] >= 1.5 and evidence[j] >= .05 for j in [13, 14, 15, 16]) >= 2):
            mode = 'lower_body_top' if lower_view else 'upper_body_outside_top'
            margin = max(8., .06*leg)
            options = []
            inferred = []
            for side, hip, knee, ankle in [('l', 11, 13, 15), ('r', 12, 14, 16)]:
                for name, j in [(f'kne_{side}', knee), (f'ank_{side}', ankle)]:
                    if raw[j, 1] < top+margin:
                        pose[name] = raw[j, :2].copy()
                        pose[name][1] = min(top-margin, pose[name][1])
                    elif (j, key) in trusted:
                        pose[name], filled = trusted[j, key]
                        pose[name] = pose[name].copy()
                        if filled or not (raw[j, 2] >= 1.5 and evidence[j] >= .05):
                            inferred.append(name)
                    else:
                        inferred.append(name+':유효 이웃 없음,기존 추론 유지')
                if raw[knee, 1] > top+margin and raw[knee, 2] >= 1.5 and evidence[knee] >= .05:
                    delta = raw[knee, :2]-raw[hip, :2]
                    if delta[1] > margin:
                        alpha = (top-margin-raw[knee, 1])/delta[1]
                        options.append(raw[knee, :2]+alpha*delta)
            pelvis_visible = (lower_view and (raw[[11, 12], 2] >= 1.5).all()
                              and (evidence[[11, 12]] >= .05).all()
                              and (raw[[11, 12], 1] > top+margin).all())
            if pelvis_visible:
                pose['pelvis'] = pelvis.copy()
            elif options:
                pose['pelvis'] = np.median(options, axis=0)
            else:
                pose['pelvis'] = np.array([pelvis[0], top-margin])
            if not lower_view:
                current_size = max(current_size, leg/2)
            pose['neck'] = pose['pelvis']-[0, current_size]
            if pelvis_visible:
                down = pose['pelvis']-neck
                distance = np.linalg.norm(down)
                if distance > 1e-8 and down[1] > margin:
                    direction = down/distance
                    length = max(current_size, (pose['pelvis'][1]-top+margin)/direction[1])
                    pose['neck'] = pose['pelvis']-direction*length
            pose['neck'][1] = min(pose['neck'][1], top-margin)
            pose['head_b'] = pose['neck'].copy()
            pose['head_t'] = pose['neck']-[0, current_size*.75]
            visibility[:] = False
            visibility[6:10] = True
            visibility[1] = pelvis_visible
            # 위몸 일부가 잘려도 안쪽에서 실제 관측되는 팔까지 통째로 가리지 않는다.
            # 세 점이 모두 경계 안/유효 점수/인물색 지지를 갖는 가지에만 적용한다.
            if lower_view:
                kept = []
                for side, js, ids in [('l', [5, 7, 9], [5, 6]), ('r', [6, 8, 10], [3, 4])]:
                    points = raw[js]
                    good = ((points[:, 2] >= 1.5) & (evidence[js] >= .05)
                            & (points[:, 0] > left+margin) & (points[:, 0] < right-margin)
                            & (points[:, 1] > top+margin) & (points[:, 1] < bottom-margin))
                    if good.all():
                        kept.append(points[0, :2])
                        pose[f'elb_{side}'], pose[f'wri_{side}'] = points[1, :2].copy(), points[2, :2].copy()
                        visibility[np.array(ids)-1] = True
                    elif good[1:].all() and points[0, 1] <= top+margin:
                        # 명시한 위몸 잘림에서 어깨가 경계에 몰려도,안쪽의 두 팔점이
                        # 모두 유효하면 보이는 팔을 잃지 않는다. 목은 틀 밖 추론을 유지한다.
                        pose[f'elb_{side}'], pose[f'wri_{side}'] = points[1, :2].copy(), points[2, :2].copy()
                        visibility[np.array(ids)-1] = True
                if kept:
                    pose['neck'] = np.mean(kept, axis=0)
                    pose['head_b'] = pose['neck'].copy()
                    pose['head_t'] = pose['neck']-[0, current_size*.75]
        elif face is None:
            face_span = np.ptp(raw[:5, :2], axis=0).max()
            output_diameter = np.linalg.norm(pose['head_t']-pose['head_b'])
            if output_diameter > .15*height and face_span < .4*output_diameter:
                report.append(dict(key=key, mode='needs_review', reason='큰 출력 머리와 작은 원관측 불일치,독립 얼굴 확인 없음; 인물 삭제/정답 추정 안함'))
        if mode != 'unchanged':
            report.append(dict(key=key, mode=mode, raw_torso_px=float(torso), raw_leg_px=leg,
                               independent_face_px=None if face is None else float(face[2]),
                               face_box_inferred=bool(face_inferred[key]),
                               visible_segments=(np.flatnonzero(visibility)+1).tolist(),
                               inferred_leg_nodes=inferred if mode in ('upper_body_outside_top', 'lower_body_top') else [],
                               hidden_positions='화면 밖 허브/연결은 추론,독립 얼굴 상자 대각선을 원 지름으로 쓰는 표시 시험'))
        targets.append((pose, current_size, visibility))
        modes.append(mode)
    # 긴 컷의 한 키만 부분 판정이면 표시를 깜박이지 말고 검토로 넘긴다.
    for key in range(len(spans)):
        mode = modes[key]
        if (len(spans) > 1 and mode not in ('unchanged', 'lower_body_top')
                and not (key and modes[key-1] == mode)
                and not (key+1 < len(spans) and modes[key+1] == mode)):
            modes[key] = 'unchanged'
            for event in report:
                if event['key'] == key and event['mode'] == mode:
                    event['mode'] = 'needs_review'
                    event['reason'] = '한 키만의 부분 판정: 깜박임 방지를 위해 자동 교체 보류'
    # 같은 모드의 연속 키만 같은 키 시각으로 보간한다. 컷 경계를 넘어 관측을 빌리지 않는다.
    i = 0
    while i < len(spans):
        if modes[i] == 'unchanged':
            i += 1
            continue
        end = i+1
        while end < len(spans) and modes[end] == modes[i]:
            end += 1
        a, b = spans[i][0], spans[end-1][1]
        times = np.array([(spans[k][0]+spans[k][1])/2 for k in range(i, end)])
        t = np.clip(np.arange(a, b+1), times[0], times[-1])
        def interp(values):
            return np.broadcast_to(values[0], (b-a+1, *np.asarray(values[0]).shape)).copy() if len(times) == 1 else PchipInterpolator(times, values, axis=0)(t)
        for name in result:
            result[name][a:b+1] = interp(np.asarray([targets[k][0][name] for k in range(i, end)]))
        scale[a:b+1] = interp(np.asarray([targets[k][1] for k in range(i, end)]))
        for k in range(i, end):
            ka, kb = spans[k]
            visible[ka:kb+1] = targets[k][2]
        i = end
    return result, scale, visible, report


def recover_views(video, frames, K, joints, scale, segments, color, bounds, faces, observed=None, body_views=None, face_score_floor=.6):
    if not 0<=face_score_floor<=1:raise ValueError('얼굴 점수 기준 범위 오류')
    support, matched = image_support(video, frames, K, color, faces, face_score_floor)
    forced = np.array([any(view['actor'] == color and view['start'] <= f <= view['end']
                          for view in body_views or []) for f in frames])
    boundaries = {a for a, _ in segments} | {frames[0]}
    boundaries |= {frames[i] for i in range(1, len(frames)) if forced[i] != forced[i-1]}
    indexes = [i for i, f in enumerate(frames) if f in boundaries]
    segments = [(frames[a], frames[indexes[j+1]-1] if j+1 < len(indexes) else frames[-1])
                for j, a in enumerate(indexes)]
    spans = [(frames.index(a), frames.index(b)) for a, b in segments]
    output, scale, visible, report = recover_key_views(K, joints, scale, spans, matched, support, bounds, observed, forced)
    for event in report:
        a, b = segments[event.pop('key')]
        event.update(start=a, end=b)
    return output, scale, visible, dict(events=report,
        face_score_floor=face_score_floor,
        independent_face_frames=int(np.isfinite(matched).all(1).sum()),
        method='선택 시험: 독립 얼굴/색 지지+잘림 형태; 가짜 얼굴/전신 미확정은 검토 목록에 유지')
