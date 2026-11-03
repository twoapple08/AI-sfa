"""전신 검출이 없는 단일 종아리 구도를 영상에서 측정한다(명시 구도 태그 필요).

사람/사물/다리 종류를 자동 분류하는 모델이 아니다. 위에서 들어오는 종아리와
신발이 보이는 구도를 확인한 뒤 쓴다. 가시 종아리 축과 신발 쪽 폭 변화만 재며,
무릎/골반/머리 등 틀 밖 위치와 해부학적 발목 정답은 복원했다고 주장하지 않는다.
"""
import cv2
import numpy as np
from scipy.ndimage import median_filter


def measure_single_shin(image, color, top, bottom):
    from rtmw_validate import color_masks
    _, blue, red = color_masks(image)
    mask = (blue if color == 'blue' else red).astype('uint8')
    mask[:int(np.ceil(top))] = 0
    mask[int(bottom):] = 0
    width = image.shape[1]
    kernel = max(3, round(width/160)) | 1
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((kernel, kernel), 'uint8'))
    count, labels, stats, centers = cv2.connectedComponentsWithStats(mask, 8)
    candidates = [i for i in range(1, count)
                  if stats[i, cv2.CC_STAT_AREA] >= .0006*image.shape[0]*width
                  and stats[i, cv2.CC_STAT_TOP] <= top+kernel]
    candidates.sort(key=lambda i: stats[i, cv2.CC_STAT_AREA], reverse=True)
    if not candidates or (len(candidates) > 1 and stats[candidates[1], 4] > .5*stats[candidates[0], 4]):
        raise ValueError('위 경계의 단일 다리 색 영역이 없거나 여러 영역이 모호하다')
    entry_rows = np.nonzero(labels[int(np.ceil(top)):int(np.ceil(top))+kernel+1] == candidates[0])[1]
    if not len(entry_rows):
        raise ValueError('다리가 위 경계로 들어오는 위치를 잴 수 없다')
    entry_x = float(np.median(entry_rows))
    # 스미어의 흰 간격이 종아리와 신발을 끊기도 한다. 명시한 단일 가시 다리 구도에서
    # 같은 색의 아래 조각을 함께 재며, 연결 성분 하나만 남겨 신발을 버리지 않는다.
    allowed = [i for i in range(1, count) if stats[i, 4] >= max(8, width*.01)
               and abs(centers[i, 0]-entry_x) < .9*(bottom-top)]
    selected = np.isin(labels, allowed)
    ys, xs = [], []
    for y in range(int(np.ceil(top)), min(int(bottom), image.shape[0])):
        row = np.flatnonzero(selected[y])
        if len(row) >= max(3, round(width*.004)):
            ys.append(y)
            xs.append(np.median(row))
    if len(ys) < 20:
        raise ValueError('종아리 축을 잴 세로 표본이 부족하다')
    ys = np.asarray(ys, float)
    xs = median_filter(np.asarray(xs), size=max(3, round(len(xs)*.025)) | 1, mode='nearest')
    t = ys-ys[0]
    fits = []
    for q in range(max(3, int(len(t)*.3)), int(len(t)*.85)):
        design = np.c_[np.ones(len(t)), t, np.maximum(t-t[q], 0)]
        coefficients = np.linalg.lstsq(design, xs, rcond=None)[0]
        fits.append((float(np.mean((design@coefficients-xs)**2)), q, coefficients))
    mse, q, coef = min(fits, key=lambda value: value[0])
    straight = np.c_[np.ones(len(t)), t]
    straight_mse = float(np.mean((straight@np.linalg.lstsq(straight, xs, rcond=None)[0]-xs)**2))
    method = '신발 쪽 폭 변화의 축 꺾임'
    gaps = np.flatnonzero(np.diff(ys) > max(kernel*2, .08*(ys[-1]-ys[0])))
    truncated_shaft = len(gaps) and q <= gaps[-1]
    if straight_mse <= 0 or mse > .8*straight_mse or abs(coef[2]) < .2 or truncated_shaft:
        # 폭 꺾임이 흐릿하면 신발/가시 하단 색 조각의 중심까지 잇는 표시 추론이다.
        # 이 점을 해부학적 발목 관측으로 저장하지 않는다.
        lower = ys >= ys[0]+.8*(ys[-1]-ys[0])
        end = np.array([np.median(xs[lower]), np.median(ys[lower])])
        entry = np.array([entry_x, ys[0]])
        method = '분리된 하단 색 영역 중심; 끝점 해석 추론'
    else:
        entry = np.array([coef[0], ys[0]])
        end = np.array([coef[0]+coef[1]*t[q], ys[q]])
    return entry, end, dict(shaft_fit_rms_px=float(np.sqrt(mse)),
        component_area=int(stats[candidates[0], 4]),
        end_method=method,
        interpretation='색 영역 중앙의 축/신발 쪽 변화점; 해부학적 발목 정답 아님')


def partial_pose(entry, end, scale, segment=8):
    """같은11객체용12점. 가시 종아리 이외 점은 화면 밖 편집망을 위한 추론이다."""
    if segment not in (8, 10) or not np.isfinite(scale) or scale <= 0:
        raise ValueError('종아리 조각8/10과 양수 기준 척도가 필요하다')
    entry, end = np.asarray(entry, float), np.asarray(end, float)
    direction = end-entry
    length = np.linalg.norm(direction)
    if length <= 1 or direction[1] <= 0:
        raise ValueError('위 경계에서 아래로 들어오는 유한한 다리 축이 필요하다')
    direction /= length
    knee = entry-direction*max(8., .08*scale)
    pelvis, neck = knee-direction*scale, knee-direction*scale*2
    pose = dict(pelvis=pelvis, neck=neck, head_b=neck, head_t=neck-direction*scale*.75)
    for side in ('l', 'r'):
        pose.update({f'kne_{side}': pelvis-direction*scale*.3,
                     f'ank_{side}': pelvis-direction*scale*.6,
                     f'elb_{side}': neck-direction*scale*.3,
                     f'wri_{side}': neck-direction*scale*.6})
    side = 'r' if segment == 8 else 'l'
    pose[f'kne_{side}'], pose[f'ank_{side}'] = knee, end
    return pose


def generate_partial(video, actor, start, end, top, bottom, scale, segment=8):
    """명시한 부분 구도 → 기존 장면 형식의partials. 좌표는 매 장 영상 측정으로 만든다."""
    if actor not in ('blue', 'red') or start > end:
        raise ValueError('인물/범위 오류')
    cap = cv2.VideoCapture(str(video))
    cap.set(cv2.CAP_PROP_POS_FRAMES, start)
    keys, measurements = {}, []
    try:
        for frame in range(start, end+1):
            ok, image = cap.read()
            if not ok:
                raise ValueError(f'원영상 {frame}장 읽기 실패')
            entry, tip, evidence = measure_single_shin(image, actor, top, bottom)
            keys[str(frame)] = {name: value.tolist() for name, value in partial_pose(entry, tip, scale, segment).items()}
            measurements.append(dict(frame=frame, entry=entry.tolist(), end=tip.tolist(), **evidence))
    finally:
        cap.release()
    partial = dict(actor=actor, start=start, end=end, visible_segments=[segment], keys=keys,
        evidence='구도 태그: 위에서 들어오는 단일 종아리. 가시 축은 원영상 색 영역 CPU 측정. '
                 '숨긴12점의 편집용 배치/가지 이름/차용 척도와 신발 변화점의 발목 해석은 추론. '
                 '스미어의 좌우 가장자리를 추가 다리로 세지 않음. 자동 구도 분류 아님.')
    return partial, measurements


def associate_two_shins(measurements):
    """보이는 축은 모두 보존하며2D 가지 이름만 대응한다. 해부학적 좌우 판정/속도 제한 아님."""
    values = np.array([[*row['entry'], *row['end']] for row in measurements])
    if len(values) < 2:
        return [0]*len(values)
    initial = max(float(np.median(np.sum(np.diff(values, axis=0)**2, axis=1)))*.1, 1.)
    states = {(-1, -1): (0., ())}
    # 마지막 관측의 쌍을 상태로 대응을 비교한다. 길이/속도 상한은 두지 않는다.
    for i in range(len(values)):
        following = {}
        for last, (cost, assignment) in states.items():
            for branch in ((0,) if i == 0 else (0, 1)):
                previous = last[branch]
                extra = initial if previous < 0 else float(np.sum((values[i]-values[previous])**2))/(i-previous)**2
                updated = list(last)
                updated[branch] = i
                key = tuple(updated)
                candidate = cost+extra, (*assignment, branch)
                if key not in following or candidate[0] < following[key][0]:
                    following[key] = candidate
        states = following
    return list(min(states.values(), key=lambda value: value[0])[1])


def generate_running_partials(video, actor, start, end, top, bottom, scale):
    """달리며 번갈아 보이는 종아리 구도. 구도 태그1개 외 장별 좌표/좌우 입력 없음."""
    _, measurements = generate_partial(video, actor, start, end, top, bottom, scale)
    assignments = associate_two_shins(measurements)
    partials = []
    for index, row in enumerate(measurements):
        endpoints = []
        for branch in (0, 1):
            ids = [i for i, value in enumerate(assignments) if value == branch]
            if not ids:
                ids = [index]
            points = np.array([[*measurements[i]['entry'], *measurements[i]['end']] for i in ids])
            endpoints.append(np.array([np.interp(index, ids, points[:, axis]) for axis in range(4)]))
        poses = [partial_pose(pair[:2], pair[2:], scale, 8 if branch == 0 else 10)
                 for branch, pair in enumerate(endpoints)]
        knee_r, knee_l = poses[0]['kne_r'], poses[1]['kne_l']
        pelvis = np.array([(knee_r[0]+knee_l[0])/2, min(knee_r[1], knee_l[1])-scale])
        neck = pelvis-[0, scale]
        pose = dict(poses[0], kne_l=knee_l, ank_l=poses[1]['ank_l'], pelvis=pelvis,
                    neck=neck, head_b=neck.copy(), head_t=neck-[0, scale*.75])
        for side in ('l', 'r'):
            pose[f'elb_{side}'] = neck-[0, scale*.3]
            pose[f'wri_{side}'] = neck-[0, scale*.6]
        frame = row['frame']
        segment = 8 if assignments[index] == 0 else 10
        row.update(branch_2d=assignments[index], visible_segment=segment)
        partials.append(dict(actor=actor, start=frame, end=frame, visible_segments=[segment],
            keys={str(frame): {n: v.tolist() for n, v in pose.items()}},
            evidence='구도 태그1개: 달리며 위에서 들어오는 종아리 일부. 가시 축/끝은 원영상 색 영역 CPU 측정. '
                     '2D 두 가지 이름은 자동 대응하며 해부학적 좌우 정답 아님. 숨긴 마디와 보이지 않는 쪽 궤적, '
                     '차용 척도/신발 변화점의 발목 해석은 추론. 손 입력 장별 좌표 없음. 자동 구도 분류 아님.'))
    return partials, measurements


def main():
    import argparse
    import json
    from pathlib import Path
    from stickman_quality import read_sfa, decode, digest
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('video')
    ap.add_argument('base_sfa')
    ap.add_argument('view_config')
    ap.add_argument('output', help='측정한partials/근거 JSON. 영상·원좌표와 함께 비공개 보관')
    args = ap.parse_args()
    config = json.loads(Path(args.view_config).read_text())
    if config.get('schema') != 1 or config.get('source_sha256') != digest(args.video):
        ap.error('부분 구도 설정과 원영상 지문이 다르다')
    root = read_sfa(args.base_sfa)
    cap = cv2.VideoCapture(args.video)
    width, height = (int(cap.get(k)) for k in (cv2.CAP_PROP_FRAME_WIDTH, cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()
    crop = config['crop_y']
    bottom = crop+width*float(root.get('HeightWidthRatio'))
    poses, _ = decode(root, ['blue', 'red'], width, crop)
    if len(poses) != config['end']-config['start']+1 or not 0 <= crop < bottom <= height:
        ap.error('부분 구도 설정의 장 범위/화면 크기가 SFA·원영상과 다르다')
    result = dict(schema=1, start=config['start'], end=config['end'], source_sha256=config['source_sha256'],
        base_sfa_sha256=digest(args.base_sfa), view_config_sha256=digest(args.view_config),
        partials=[], measurements=[], references=[], automatic_view_classification=False, manual_coordinates=0)
    occupied = set()
    for view in config['views']:
        actor, a, b, ref = view['actor'], view['start'], view['end'], view['reference_frame']
        lo, hi = view['shot']
        if (view['kind'] != 'running_shins_top' or actor not in ('red', 'blue')
                or not config['start'] <= lo <= a <= b <= hi <= config['end'] or not lo <= ref <= hi):
            ap.error('지원하지 않는 구도 또는 컷/장 범위 오류')
        for frame in range(a, b+1):
            if (frame, actor) in occupied or poses[frame-config['start']][actor] is not None:
                ap.error('부분 구도가 겹치거나 기존 인물을 덮어쓰려고 한다')
            occupied.add((frame, actor))
        reference = poses[ref-config['start']][actor]
        if reference is None:
            ap.error('같은 컷의 굵기 차용 기준 인물이 없다')
        scale = float(np.linalg.norm(reference['head_t']-reference['head_b'])/.75)
        parts, measurements = generate_running_partials(args.video, actor, a, b, crop, bottom, scale)
        result['partials'] += parts
        result['measurements'] += measurements
        result['references'].append(dict(actor=actor, start=a, end=b, reference_frame=ref,
                                         borrowed_scale_px=scale, depth_observed=False))
    if len(result['references']) == 1:
        result['borrowed_scale_px'] = result['references'][0]['borrowed_scale_px']
    Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print(f"구도 태그 {len(config['views'])}개 → 부분 관측 {len(result['partials'])}장, 손 입력 좌표0개")


if __name__ == '__main__':
    main()
