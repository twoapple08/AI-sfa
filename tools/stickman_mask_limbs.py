"""부분 구도(팔만 보이는 근접)에서 인물 색 영역으로 팔을 잡는다(11-10 '딸깍' 1번 과제).

배경: 팔만 보이는 근접(새 구간 3221–3241)에서 RTMW는 두 팔을 섞은 화면 크기 검출 하나를 내고,
다리를 팔 위에 접어 놓는다(손목≈발목). 머리·몸통·어깨는 화면 안에 지어낸 자리다. 검출로는 고칠 수 없다.

규칙(공통, 장 번호 없음):
1. 판정(`collapsed_shot`): 한 컷에서 '접힌 검출'(두 손목이 두 발목과 상자 대각선 4% 안에 겹침)이
   컷 장의 40% 이상이면 부분 구도 컷이다. 승인 10초(1032–1271)에는 접힌 검출이 0장이고, 새 구간에서
   팔만 보이는 근접 3221–3241이 0.48, 그다음이 이펙트 근접 3272–3284의 0.31이다(문턱 근거는 이 1컷뿐).
2. 추적(`trace_arm`): 인물 색 마스크에서 화면 가장자리에 닿은 가장 큰 덩어리를 팔로 본다.
   - 어깨 쪽 = 덩어리가 가장자리에 닿은 구간의 가운데(화면 밖으로 이어짐).
   - 끝 = 닿은 구간에서 덩어리 안으로 가장 먼 점(측지 거리). 상대 인물 색에 끊긴 같은 색 조각이
     진행 방향으로 이어지면 끝을 그 조각까지 늘린다(가린 손 너머의 주먹).
   - 팔꿈치 = 어깨 쪽→끝 경로에서 직선으로부터 가장 많이 벗어난 점. 벗어남이 작으면(곧은 팔)
     가장자리(화면 밖으로 나가는 자리)에 둔다.
   - 손목 = 끝에서 경로를 따라 손 길이(끝 부근 팔 굵기의 2배)만큼 되돌린 점.
   - 어깨(목 허브) = 팔꿈치에서 화면 밖 방향으로 위팔 길이(아래팔과 같게)만큼.
3. 그리는 것은 보이는 팔 두 마디(조각 3·4)뿐이다(11-10 사용자: 팔만 있는 장면에 스틱맨을 만들지 않는다).
   화면 밖 머리·몸통·다리는 편집망 좌표만 몸 비율로 두고 선·채움은 그리지 않는다(Color 0).

결과는 판독 키와 같은 형식의 자동 키다(`visible_views` 형식). 추론이며 원본 정답이 아니다.
"""
import numpy as np


HEAD_PER_ARM_R = 3.5   # 머리 지름 ≈ 팔 반지름(뼈대 반지름 75% 분위)×3.5 — 3221–3241 판독 머리 지름(300)에서 잰 비율, 1컷 근거


def collapsed(box, k, frac=0.04, min_score=1.0):
    """접힌 검출: 손목 두 개와 발목 두 개가 상자 대각선 frac 안에서 2쌍 이상 겹친다."""
    diag = float(np.hypot(box[2] - box[0], box[3] - box[1]))
    hits = 0
    for w in (9, 10):
        for a in (15, 16):
            if k[w, 2] >= min_score and k[a, 2] >= min_score and np.linalg.norm(k[w, :2] - k[a, :2]) < frac * diag:
                hits += 1
    return hits >= 2


def collapsed_shot(R, frames, share=0.4):
    """컷 장 가운데 접힌 검출이 있는 장의 비율이 share 이상인가. (판정, 비율)"""
    hit = [any(collapsed(box, k) for box, k in R.get(f, [])) for f in frames]
    ratio = float(np.mean(hit)) if hit else 0.0
    return ratio >= share, ratio


def _border_runs(m):
    """마스크가 화면 가장자리에 닿은 연속 구간들: [(길이, 가운데 (x, y), 안쪽 방향)]"""
    H, W = m.shape
    sides = [(m[0, :], lambda t: (t, 0), (0, 1)), (m[-1, :], lambda t: (t, H - 1), (0, -1)),
             (m[:, 0], lambda t: (0, t), (1, 0)), (m[:, -1], lambda t: (W - 1, t), (-1, 0))]
    runs = []
    for line, at, inward in sides:
        on = np.flatnonzero(line)
        if not len(on):
            continue
        groups = np.split(on, np.flatnonzero(np.diff(on) > 3) + 1)
        for g in groups:
            runs.append((len(g), np.array(at((g[0] + g[-1]) / 2), float), np.array(inward, float), [at(t) for t in g]))
    return runs


def _geodesic(m, seeds):
    from skimage.graph import MCP_Geometric
    cost = np.where(m, 1.0, np.inf)
    mcp = MCP_Geometric(cost)
    dist, _ = mcp.find_costs([(int(y), int(x)) for x, y in seeds])
    return dist, mcp


def trace_arm(own, other, min_area=0.01, min_run=40, step=2):
    """own/other: bool 마스크(H×W, 위 crop 뺀 화면). 반환 dict(neck, elb, wri, tip, straight, scale) 또는 None.
    좌표는 마스크 좌표(px). 계산을 줄이려 step 배로 줄여 잰다."""
    import cv2
    H, W = own.shape
    small = cv2.resize(own.astype(np.uint8), (W // step, H // step), interpolation=cv2.INTER_NEAREST)
    small = cv2.morphologyEx(small, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    oth = cv2.resize(other.astype(np.uint8), (W // step, H // step), interpolation=cv2.INTER_NEAREST) > 0
    n, lab, stats, _ = cv2.connectedComponentsWithStats(small, connectivity=8)
    best = None
    for i in range(1, n):
        if stats[i, cv2.CC_STAT_AREA] < min_area * small.size:
            continue
        runs = [r for r in _border_runs(lab == i) if r[0] * step >= min_run]
        if not runs:
            continue
        run = max(runs, key=lambda r: r[0])
        if best is None or stats[i, cv2.CC_STAT_AREA] > best[1]:
            best = (i, stats[i, cv2.CC_STAT_AREA], run)
    if best is None:
        return None
    i, _, run = best
    comp = lab == i
    # 팔 굵기: 뼈대 위 반지름의 75% 분위. 손가락처럼 가는 가지는 반지름의 절반 원으로 열어 깎는다(끝이 손바닥·주먹에 오게).
    from skimage.morphology import skeletonize
    dt = cv2.distanceTransform(comp.astype(np.uint8), cv2.DIST_L2, 5)
    sk = dt[skeletonize(comp)]
    arm_r = float(np.percentile(sk[sk > 1], 75)) if (sk > 1).sum() > 5 else 4.0
    rk = max(1, int(round(0.5 * arm_r)))
    opened = cv2.morphologyEx(comp.astype(np.uint8), cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * rk + 1, 2 * rk + 1))) > 0
    seeds = [p for p in run[3] if opened[int(p[1]), int(p[0])]] or run[3]
    core = opened if opened[int(seeds[0][1]), int(seeds[0][0])] else comp
    dist, mcp = _geodesic(core, seeds)
    d = np.where(np.isfinite(dist), dist, -1)
    ty, tx = np.unravel_index(np.argmax(d), d.shape)
    path = np.array([(x, y) for y, x in mcp.traceback((ty, tx))], float)
    root = run[1]
    tip = np.array([tx, ty], float)
    # 가린 손 너머의 같은 색 조각: 끝이 상대 색에 닿고, 진행 방향 앞쪽(±30°)에 같은 색 조각이 있으면 그 조각 끝까지 잇는다.
    near = oth[max(0, ty - rk - 3):ty + rk + 4, max(0, tx - rk - 3):tx + rk + 4]
    if near.any():
        u = tip - path[max(0, len(path) - 1 - max(5, len(path) // 5))]
        u = u / max(np.linalg.norm(u), 1e-9)
        best_j = None
        for j in range(1, n):
            if j == i or stats[j, cv2.CC_STAT_AREA] < 0.1 * min_area * small.size:
                continue
            ys, xs = np.nonzero(lab == j)
            v = np.stack([xs, ys], 1) - tip
            along = v @ u
            side = np.abs(v @ np.array([-u[1], u[0]]))
            gap = float(along.min()) if len(along) else 1e9
            ok = (along > 0) & (side < np.tan(np.radians(30)) * np.maximum(along, 1) + arm_r)
            if ok.mean() > 0.5 and gap < 0.5 * len(path) and (best_j is None or gap < best_j[0]):
                far = int(np.argmax(np.where(ok, along, -1)))
                best_j = (gap, np.array([xs[far], ys[far]], float))
        if best_j is not None:
            tip = best_j[1]
            path = np.vstack([path, np.linspace(path[-1], tip, 10)])
    end_r = arm_r
    # 팔꿈치: 경로가 어깨 쪽→끝 직선에서 가장 많이 벗어난 점
    chord = tip - root
    L = max(np.linalg.norm(chord), 1e-9)
    nrm = np.array([-chord[1], chord[0]]) / L
    dev = np.abs((path - root) @ nrm)
    k = int(np.argmax(dev))
    straight = dev[k] < 0.12 * L
    # 손목: 끝에서 경로를 따라 손 길이(끝 굵기 지름의 1배)만큼 되돌림
    seg = np.linalg.norm(np.diff(path, axis=0), axis=1)
    back = np.concatenate([[0], np.cumsum(seg[::-1])])[::-1]  # 각 점에서 끝까지의 경로 길이
    wri = path[int(np.argmin(np.abs(back - 2.0 * end_r)))]
    elb = root.copy() if straight else path[k]
    fore = max(np.linalg.norm(wri - elb), 1e-9)
    # 위팔 방향: 곧은 팔은 아래팔 연장, 굽은 팔은 팔꿈치→가장자리. 화면 안쪽을 향하면 가장자리 바깥 방향을 쓴다.
    out_dir = (elb - wri) if straight else (root - elb)
    if np.linalg.norm(out_dir) < 1e-6 or (out_dir / np.linalg.norm(out_dir)) @ (-run[2]) < 0.2:
        out_dir = -run[2]
    out_dir = out_dir / np.linalg.norm(out_dir)
    neck = elb + out_dir * fore
    # 팔은 화면 가장자리에서 들어온다: 위팔 끝(어깨 허브)이 화면 안에서 허공에 끝나지 않게 가장자리 밖까지 늘린다.
    Ws, Hs = W // step, H // step
    pad = 0.1 * fore
    exits = [((Ws + pad - elb[ax]) if out_dir[ax] > 0 else (-pad - elb[ax])) / out_dir[ax]
             for ax, Ws_ in ((0, Ws), (1, Hs)) for Ws in [Ws_] if abs(out_dir[ax]) > 1e-6]
    if exits and 0 <= neck[0] < Ws and 0 <= neck[1] < Hs:
        neck = elb + out_dir * max(fore, min(exits))
    s = float(step)
    return dict(neck=neck * s, elb=elb * s, wri=wri * s, tip=tip * s, root=root * s,
                straight=bool(straight), radius=end_r * s, forearm=fore * s)


def auto_views(R, video, shots, colors, crop_y, taken=(), min_frames=4, log=None):
    """부분 구도 컷마다 인물별 자동 visible_views(판독 키와 같은 형식). taken: 이미 사람 판독이 있는 (장, 인물).
    반환 [view], 보고 [dict]."""
    import cv2
    from rtmw_validate import color_masks
    cap = cv2.VideoCapture(video)
    views, report = [], []
    for s, e in shots:
        frames = list(range(s, e + 1))
        hit, ratio = collapsed_shot(R, frames)
        report.append(dict(shot=[s, e], collapsed_ratio=round(ratio, 3), partial=bool(hit and len(frames) >= min_frames)))
        if not report[-1]['partial']:
            continue
        traced = {c: {} for c in colors}
        for f in frames:
            cap.set(cv2.CAP_PROP_POS_FRAMES, f)
            ok, fr = cap.read()
            if not ok:
                continue
            top = int(round(crop_y))
            fr = fr[top:top + int(round(fr.shape[1] * 9 / 16))]
            _, blue, red = color_masks(fr)
            for c in colors:
                if (f, c) in taken:
                    continue
                own, other = (blue, red) if c == 'blue' else (red, blue)
                t = trace_arm(own, other)
                if t is not None:
                    traced[c][f] = t
        for c, tr in traced.items():
            if not tr:
                continue
            hd = float(np.median([t['radius'] for t in tr.values()])) * HEAD_PER_ARM_R
            keys = {str(f): {'neck': [float(t['neck'][0]), float(t['neck'][1] + crop_y)],
                             'elb_r': [float(t['elb'][0]), float(t['elb'][1] + crop_y)],
                             'wri_r': [float(t['wri'][0]), float(t['wri'][1] + crop_y)]} for f, t in sorted(tr.items())}
            fs = sorted(tr)
            views.append(dict(actor=c, start=fs[0], end=fs[-1], visible_segments=[3, 4], keys=keys,
                              head_d={str(fs[0]): round(hd, 1)}, auto='mask_limbs',
                              evidence='자동: 접힌 검출 컷(부분 구도), 인물 색 마스크 팔 추적. 보이는 팔(위팔·아래팔)만 그린다'))
            report[-1].setdefault('traced', {})[c] = dict(frames=len(tr), head_d=round(hd, 1),
                                                          straight=sum(t['straight'] for t in tr.values()))
    cap.release()
    return views, report
