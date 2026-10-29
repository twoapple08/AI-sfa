#!/usr/bin/env python3
"""영상 속 색 스틱맨 → 뼈대(머리 원 + 몸통 + 팔 2 + 다리 2, 팔다리 두 마디) 장마다 맞추고 장 사이에 이어 붙이기 (2026-10-29).

동기(사용자 10-29): 영상 → SFA 변환이 픽셀 덧그리기에 머물러 아쉬움 → '이해 + 정밀' 분리. 스틱맨은 정해진 틀로 맞춘다.
정답 4711_2 `4.7.1.1_2_7`: 스틱맨-장 109 중 103이 이 틀(팔다리 각 관절 3점), 주인공 노랑 + 초록·자홍(검정은 배경선과 섞여 뒤로 미룸).
방법(장마다):
1. 스틱맨 색과 Lab 거리 --col-thr 안 + 먹 → 그 색 마스크. 머리 = 마스크에서 원 찾기(video_to_sfa.find_circles).
2. 마스크 뼈대 → 조각(trace) → 끝점을 마디로 묶은 그래프(가지 짝짓기 없음).
3. 목 = 머리 원 둘레에 가장 가까운 마디. 목에서 나가는 조각 중 반대쪽 마디에 가지가 가장 많은 것 = 몸통, 그 끝 = 엉덩이.
   팔 = 목에서 나가는 나머지 조각(길이순 2개), 다리 = 엉덩이에서 나가는 조각(2개). 가지 2개짜리 마디는 그대로 따라감.
4. 팔다리 선 → (뿌리, 꺾인 점, 끝): 꺾인 점 = 현에서 가장 먼 점(길이 8% 미만이면 가운데).
5. 장 사이: 팔0/팔1·다리0/다리1을 앞 장 끝점과 거리 합이 작은 쪽으로 짝지음. 못 찾은 장은 앞 장 뼈대를 유지(held=True).
출력: 장마다 dict(head=[cx,cy,r], neck, hip, arms=[[3점],[3점]], legs=[...], held). 좌표는 입력 영상 장 픽셀.
"""
import os
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from effect_vectorize import trace  # noqa: E402
from video_to_sfa import find_circles  # noqa: E402


def color_mask(img, col_bgr, up=2, col_thr=45.0):
    big = cv2.resize(img, None, fx=up, fy=up, interpolation=cv2.INTER_CUBIC)
    lab = cv2.cvtColor(big, cv2.COLOR_BGR2LAB).astype(np.float32)
    c = cv2.cvtColor(np.uint8([[col_bgr]]), cv2.COLOR_BGR2LAB)[0, 0].astype(np.float32)
    m = (np.linalg.norm(lab - c, axis=2) < col_thr).astype(np.uint8)
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    return big, m


def graph(paths, node_r, short=0.0):
    """뼈대 조각 → (조각 점열 목록, 조각 양 끝 마디 번호, 마디 중심)."""
    P = [np.array([(x, y) for y, x in p], np.float64) for p in paths if len(p) >= 2]
    ends = np.array([q for a in P for q in (a[0], a[-1])]) if P else np.zeros((0, 2))
    lab = -np.ones(len(ends), int)
    nid = 0
    for i in range(len(ends)):
        if lab[i] >= 0:
            continue
        st = [i]
        lab[i] = nid
        while st:
            j = st.pop()
            for k in np.where((np.linalg.norm(ends - ends[j], axis=1) <= node_r) & (lab < 0))[0]:
                lab[k] = nid
                st.append(k)
        nid += 1
    # 짧은 조각(갈림점 사이 찌꺼기, short 미만)으로 이어진 마디는 하나로 합치고 그 조각은 버린다
    par = list(range(nid))

    def f(a):
        while par[a] != a:
            par[a] = par[par[a]]
            a = par[a]
        return a
    keep = []
    for i, a in enumerate(P):
        if length(a) < short and lab[2 * i] != lab[2 * i + 1]:
            par[f(lab[2 * i])] = f(lab[2 * i + 1])
        else:
            keep.append(i)
    roots = sorted({f(n) for n in range(nid)})
    ren = {r: j for j, r in enumerate(roots)}
    lab = np.array([ren[f(n)] for n in lab])
    # 제자리 고리 버리고, 같은 두 마디 사이 중복 조각은 가장 긴 것만
    best = {}
    for i in keep:
        a, b = lab[2 * i], lab[2 * i + 1]
        if a == b:
            continue
        k = (min(a, b), max(a, b))
        if k not in best or length(P[i]) > length(P[best[k]]):
            best[k] = i
    keep = sorted(best.values())
    E = [(lab[2 * i], lab[2 * i + 1]) for i in keep]
    P = [P[i] for i in keep]
    C = np.array([ends[lab == n].mean(0) for n in range(len(roots))]) if roots else np.zeros((0, 2))
    return P, E, C


def length(a):
    return float(np.linalg.norm(np.diff(a, axis=0), axis=1).sum())


def bend3(a):
    """선 → (뿌리, 꺾인 점, 끝)."""
    p0, p1 = a[0], a[-1]
    ch = p1 - p0
    cl = max(np.linalg.norm(ch), 1e-9)
    dev = np.abs(ch[0] * (a[:, 1] - p0[1]) - ch[1] * (a[:, 0] - p0[0])) / cl
    k = int(dev.argmax())
    if dev[k] < 0.08 * length(a) or k in (0, len(a) - 1):
        L = np.r_[0, np.cumsum(np.linalg.norm(np.diff(a, axis=0), axis=1))]
        k = int(np.searchsorted(L, L[-1] / 2))
    return [p0, a[k], p1]


def fit_pose(img, col_bgr, up=2, col_thr=45.0, min_r=4.0):
    from skimage.morphology import skeletonize
    big, m = color_mask(img, col_bgr, up, col_thr)
    if m.sum() < 50:
        return None
    circles, m2 = find_circles(big, m, up, min_r=min_r, on_ring=0.75, inside_empty=0.5)
    if not circles:
        return None
    (_, (a, b), _) = circles[0][0][0]
    head_c, head_r = (a + b) / 2 * up, np.linalg.norm(b - a) / 2 * up
    dt = cv2.distanceTransform(m, cv2.DIST_L2, 3)
    sk = skeletonize(m2 > 0)
    mw = 2 * float(np.median(dt[sk])) if sk.any() else 4.0 * up
    P, E, C = graph(trace(sk), node_r=0.8 * mw, short=max(1.5 * mw, 0.7 * head_r))  # 머리 반지름 0.7배보다 짧은 뼈는 없다(흐린 갈림점 찌꺼기)
    if not len(C):
        return None
    deg = np.bincount([n for e in E for n in e], minlength=len(C))
    # 목: 머리 원 둘레(반지름 + 선 폭) 근처 마디 중 원에서 가장 가까운 것
    dr = np.abs(np.linalg.norm(C - head_c, axis=1) - head_r)
    neck = int(dr.argmin())
    if dr[neck] > head_r * 0.8 + mw:
        return None
    neck_xy = head_c + (C[neck] - head_c) / max(np.linalg.norm(C[neck] - head_c), 1e-9) * head_r  # 목 = 원 둘레 위 점

    def walk(n0, i0):
        """마디 n0에서 조각 i0로 출발해 가지 2개짜리 마디는 그대로 지나가며 이은 점열과 끝 마디."""
        seq, n, i, used = [], n0, i0, {i0}
        while True:
            a = P[i] if E[i][0] == n else P[i][::-1]
            seq.append(a if not seq else a[1:])
            n = E[i][1] if E[i][0] == n else E[i][0]
            nxt = [j for j, e in enumerate(E) if n in e and j not in used]
            if deg[n] != 2 or len(nxt) != 1:
                break
            i = nxt[0]
            used.add(i)
        return np.vstack(seq), n, used

    out_neck = [i for i, e in enumerate(E) if neck in e and e[0] != e[1]]
    if not out_neck:
        return None
    cand = [walk(neck, i) for i in out_neck]
    torso = max(cand, key=lambda w: (deg[w[1]] >= 3, length(w[0])))  # 끝에 다리 둘 + 몸통이 모이는 것 중 가장 긴 것
    hip = torso[1]
    used = set(torso[2])
    arms = sorted([w for w in cand if w is not torso], key=lambda w: -length(w[0]))[:2]
    for w in arms:
        used |= w[2]
    legs = [walk(hip, i) for i, e in enumerate(E) if hip in e and i not in used and e[0] != e[1]]
    legs = sorted(legs, key=lambda w: -length(w[0]))[:2]
    if len(legs) < 1:
        return None
    s = 1.0 / up
    return dict(head=[*(head_c * s), head_r * s], neck=neck_xy * s, hip=C[hip] * s,
                arms=[[p * s for p in bend3(w[0])] for w in arms], legs=[[p * s for p in bend3(w[0])] for w in legs], held=False)


def match_limbs(prev, cur):
    """앞 장과 끝점 거리 합이 작은 순서로 팔·다리 순서를 맞춘다. 빠진 팔다리는 앞 장 것을 몸에 붙여 유지."""
    for key, root in (('arms', 'neck'), ('legs', 'hip')):
        a, b = prev[key], cur[key]
        if len(b) == 2 and len(a) == 2:
            d0 = np.linalg.norm(a[0][2] - b[0][2]) + np.linalg.norm(a[1][2] - b[1][2])
            d1 = np.linalg.norm(a[0][2] - b[1][2]) + np.linalg.norm(a[1][2] - b[0][2])
            if d1 < d0:
                cur[key] = [b[1], b[0]]
        elif len(b) < len(a):
            off = cur[root] - prev[root]
            have = cur[key]
            for limb in a:
                if len(have) >= len(a):
                    break
                if not have or min(np.linalg.norm(limb[2] - h[2]) for h in have) > 1e-6:
                    have = have + [[p + off for p in limb]]
            cur[key] = have[:2]
    return cur


def track(frames, col_bgr, **kw):
    poses, prev = [], None
    for img in frames:
        p = fit_pose(img, col_bgr, **kw)
        if p is None:
            if prev is not None:
                p = dict(prev, held=True)
        elif prev is not None:
            p = match_limbs(prev, p)
        poses.append(p)
        if p is not None:
            prev = p
    return poses


# ---- 2판: 틀을 영상에 당겨 맞추기(그래프 해석이 흐린 갈림점에서 쉽게 깨짐 → 앞 장 뼈대에서 출발해 관절을 조금씩 옮김) ----
JOINTS = ['neck', 'hip', 'a0e', 'a0h', 'a1e', 'a1h', 'l0k', 'l0f', 'l1k', 'l1f']
BONES = [('neck', 'hip'), ('neck', 'a0e'), ('a0e', 'a0h'), ('neck', 'a1e'), ('a1e', 'a1h'),
         ('hip', 'l0k'), ('l0k', 'l0f'), ('hip', 'l1k'), ('l1k', 'l1f')]


def to_vec(p):
    a = p['arms'] + [p['arms'][-1]] * (2 - len(p['arms'])) if p['arms'] else [[p['neck']] * 3] * 2
    l = p['legs'] + [p['legs'][-1]] * (2 - len(p['legs'])) if p['legs'] else [[p['hip']] * 3] * 2
    return {'neck': np.asarray(p['neck'], float), 'hip': np.asarray(p['hip'], float),
            'a0e': np.asarray(a[0][1], float), 'a0h': np.asarray(a[0][2], float), 'a1e': np.asarray(a[1][1], float), 'a1h': np.asarray(a[1][2], float),
            'l0k': np.asarray(l[0][1], float), 'l0f': np.asarray(l[0][2], float), 'l1k': np.asarray(l[1][1], float), 'l1f': np.asarray(l[1][2], float)}


def from_vec(J, head, held=False):
    return dict(head=list(head), neck=J['neck'], hip=J['hip'], arms=[[J['neck'], J['a0e'], J['a0h']], [J['neck'], J['a1e'], J['a1h']]],
                legs=[[J['hip'], J['l0k'], J['l0f']], [J['hip'], J['l1k'], J['l1f']]], held=held)


def seg_dist(Q, A, B):
    """점들 Q(n,2)에서 선분 AB까지 거리."""
    ab = B - A
    t = np.clip(((Q - A) @ ab) / max(float(ab @ ab), 1e-9), 0, 1)
    return np.linalg.norm(Q - (A + t[:, None] * ab), axis=1)


def cost(J, dt_ink, skp, L0, cap, w_len=0.5):
    """뼈가 먹 위에(뼈 위 표본점의 먹까지 거리) + 먹 뼈대점이 어떤 뼈 가까이(설명됨) + 뼈 길이 유지."""
    H, W = dt_ink.shape
    on = []
    for a, b in BONES:
        t = np.linspace(0, 1, 12)[:, None]
        q = J[a] * (1 - t) + J[b] * t
        xs = np.clip(q[:, 0].astype(int), 0, W - 1)
        ys = np.clip(q[:, 1].astype(int), 0, H - 1)
        on.append(np.minimum(dt_ink[ys, xs], cap))
    c_on = float(np.mean(np.concatenate(on)))
    if len(skp):
        d = np.min([seg_dist(skp, J[a], J[b]) for a, b in BONES], axis=0)
        c_cov = float(np.mean(np.minimum(d, cap)))
    else:
        c_cov = 0.0
    c_len = 0.0
    if L0 is not None:
        for (a, b), l0 in zip(BONES, L0):
            l = np.linalg.norm(J[a] - J[b])
            c_len += abs(l - l0) / max(l0, 1.0)
        c_len /= len(BONES)
    return c_on + c_cov + w_len * cap * c_len


def refine(J, dt_ink, skp, L0, cap, steps=(12, 6, 3, 1.5), iters=2):
    J = {k: v.copy() for k, v in J.items()}
    best = cost(J, dt_ink, skp, L0, cap)
    dirs = np.array([(dx, dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1) if dx or dy], float)
    for s in steps:
        for _ in range(iters):
            for k in JOINTS:
                # 몸통 관절은 딸린 관절을 함께 옮긴다(엉덩이 → 다리, 목 → 팔)
                group = {'hip': ['hip', 'l0k', 'l0f', 'l1k', 'l1f'], 'neck': ['neck', 'a0e', 'a0h', 'a1e', 'a1h'],
                         'a0e': ['a0e', 'a0h'], 'a1e': ['a1e', 'a1h'], 'l0k': ['l0k', 'l0f'], 'l1k': ['l1k', 'l1f']}.get(k, [k])
                for dv in dirs * s:
                    T = dict(J)
                    for g in group:
                        T[g] = J[g] + dv
                    c = cost(T, dt_ink, skp, L0, cap)
                    if c < best - 1e-6:
                        best, J = c, T
    return J, best


def track2(frames, col_bgr, up=2, col_thr=45.0):
    """머리는 원 찾기로, 몸은 앞 장 뼈대에서 출발해 당겨 맞춤. 첫 뼈대 = 그래프 해석(fit_pose)이 처음 성공한 장."""
    from skimage.morphology import skeletonize
    poses = [None] * len(frames)
    prevJ, prev_head, L0 = None, None, None
    order = list(range(len(frames)))
    first = None
    for k in order:
        p = fit_pose(frames[k], col_bgr, up, col_thr)
        if p is not None and len(p['arms']) == 2 and len(p['legs']) == 2:
            first = k
            break
    if first is None:
        return poses, []
    costs = [None] * len(frames)
    start = None
    for direction in (range(first, len(frames)), range(first - 1, -1, -1)):
        prevJ, prev_head, L0 = start if start else (None, None, None)
        for k in direction:
            img = frames[k]
            big, m = color_mask(img, col_bgr, up, col_thr)
            circles, _ = find_circles(big, m, up, min_r=4.0, on_ring=0.75, inside_empty=0.5) if m.sum() else ([], None)
            head = None
            if circles:
                cand = []
                for segs, _ in circles:
                    a, b = segs[0][1]
                    cand.append(((a + b) / 2, np.linalg.norm(b - a) / 2))
                if prev_head is not None:
                    cand.sort(key=lambda c: np.linalg.norm(c[0] - prev_head[:2]))
                c, r = cand[0]
                if prev_head is None or np.linalg.norm(c - prev_head[:2]) < 6 * prev_head[2]:
                    head = np.array([c[0], c[1], r])
            if prevJ is None:
                p = fit_pose(img, col_bgr, up, col_thr) if k == first else None
                if p is None:
                    continue
                J = to_vec(p)
                head = np.array(p['head'])
                L0 = [np.linalg.norm(J[a] - J[b]) for a, b in BONES]
            else:
                J = {kk: v.copy() for kk, v in prevJ.items()}
                if head is not None:  # 머리 이동만큼 몸 전체를 먼저 옮김
                    off = head[:2] - prev_head[:2]
                    for kk in J:
                        J[kk] += off
                else:
                    head = prev_head.copy()
            small = cv2.resize(m, (img.shape[1], img.shape[0]), interpolation=cv2.INTER_NEAREST)
            dt_ink = cv2.distanceTransform((1 - small).astype(np.uint8), cv2.DIST_L2, 3)
            sk = skeletonize(small > 0)
            ys, xs = np.nonzero(sk)
            skp = np.c_[xs, ys].astype(float)
            # 머리 원 둘레 점은 설명 대상에서 뺌, 몸 근처(몸통 길이 3배 안)만
            tl = max(np.linalg.norm(J['neck'] - J['hip']), head[2] * 2)
            dd = np.linalg.norm(skp - head[:2], axis=1)
            skp = skp[(np.abs(dd - head[2]) > 2.5) & (np.linalg.norm(skp - J['hip'], axis=1) < 3 * tl)]
            cap = max(head[2] * 0.6, 4.0)
            J, c = refine(J, dt_ink, skp, L0, cap)
            # 목은 머리 원 둘레에 붙인다
            v = J['neck'] - head[:2]
            J['neck'] = head[:2] + v / max(np.linalg.norm(v), 1e-9) * head[2]
            poses[k] = from_vec(J, head)
            costs[k] = c
            prevJ, prev_head = J, head
            if k == first:
                start = (J, head, L0)
    return poses, costs


# ---- 3판: 자세 사전으로 출발점 고르기 ----
# 사전 = 사용자 SFA 스틱맨 자세(data/stickman_motion/user_sfa_skeletons_*.jsonl)를 목 원점·머리 방향 위(-y)·머리 지름 1로 맞춰 좌우 뒤집기까지 넣고 대표 자세로 묶은 것
# (10관절: 목, 엉덩이, 팔0 팔꿈치·손, 팔1 팔꿈치·손, 다리0 무릎·발, 다리1 무릎·발).


def place(lib, c, r, th):
    """사전 자세들(n,10,2)을 머리 원(c, r)과 머리 방향 각 th(라디안, 0 = 위)에 놓는다 → (n,10,2) 화면 좌표."""
    u = np.array([np.sin(th), -np.cos(th)])  # 목 → 정수리 방향
    R = np.array([[np.cos(th), -np.sin(th)], [np.sin(th), np.cos(th)]])
    neck = np.asarray(c) - u * r
    return neck + 2 * r * np.einsum('ij,nkj->nki', R, lib)


def on_cost(X, dt_ink, cap, ns=8):
    """후보들 X(n,10,2): 뼈 표본점의 먹까지 거리 평균(상한 cap)."""
    H, W = dt_ink.shape
    idx = {k: i for i, k in enumerate(JOINTS)}
    t = np.linspace(0, 1, ns)[None, :, None]
    tot = 0
    for a, b in BONES:
        q = X[:, idx[a], None, :] * (1 - t) + X[:, idx[b], None, :] * t
        xs = np.clip(q[..., 0].astype(int), 0, W - 1)
        ys = np.clip(q[..., 1].astype(int), 0, H - 1)
        tot = tot + np.minimum(dt_ink[ys, xs], cap).mean(1)
    return tot / len(BONES)


def track3(frames, col_bgr, lib, up=2, col_thr=45.0, n_th=24, top=40, w_motion=0.3):
    from skimage.morphology import skeletonize
    poses, costs = [None] * len(frames), [None] * len(frames)
    prevJ, prev_head = None, None
    for k, img in enumerate(frames):
        big, m = color_mask(img, col_bgr, up, col_thr)
        if m.sum() < 80 * up * up:
            prevJ = None
            continue
        circles, _ = find_circles(big, m, up, min_r=4.0, on_ring=0.75, inside_empty=0.5)
        if not circles:
            prevJ = None
            continue
        heads = []
        for segs, _ in circles:
            a, b = segs[0][1]
            heads.append(((a + b) / 2, np.linalg.norm(b - a) / 2))
        if prev_head is not None and prevJ is not None:
            heads.sort(key=lambda h: np.linalg.norm(h[0] - prev_head[:2]))
        else:
            heads.sort(key=lambda h: -h[1])
        c, r = heads[0]
        small = cv2.resize(m, (img.shape[1], img.shape[0]), interpolation=cv2.INTER_NEAREST)
        dt_ink = cv2.distanceTransform((1 - small).astype(np.uint8), cv2.DIST_L2, 3)
        sk = skeletonize(small > 0)
        ys, xs = np.nonzero(sk)
        skp = np.c_[xs, ys].astype(float)
        skp = skp[(np.abs(np.linalg.norm(skp - c, axis=1) - r) > 2.5) & (np.linalg.norm(skp - c, axis=1) < 12 * r)]
        cap = max(r * 0.6, 4.0)
        cands = []
        for th in np.linspace(-np.pi, np.pi, n_th, endpoint=False):
            X = place(lib, c, r, th)
            cands.append(X)
        X = np.concatenate(cands)
        if prevJ is not None:  # 앞 장 자세(머리 이동만큼 옮김)도 후보
            off = c - prev_head[:2]
            X = np.concatenate([X, np.array([[prevJ[j] + off for j in JOINTS]])])
        co = on_cost(X, dt_ink, cap)
        best = None
        for i in np.argsort(co)[:top]:
            J = {j: X[i, n] for n, j in enumerate(JOINTS)}
            cc = cost(J, dt_ink, skp, None, cap)
            if prevJ is not None:
                cc += w_motion * cap * np.mean([min(np.linalg.norm(J[j] - prevJ[j] - (c - prev_head[:2])) / (4 * r), 1.0) for j in JOINTS])
            if best is None or cc < best[0]:
                best = (cc, J)
        L0 = [np.linalg.norm(best[1][a] - best[1][b]) for a, b in BONES]
        J, cc = refine(best[1], dt_ink, skp, L0, cap, steps=(4, 2, 1), iters=1)
        if on_cost(np.array([[J[j] for j in JOINTS]]), dt_ink, cap)[0] > 0.45 * cap:
            prevJ = None  # 잘 맞는 자세가 없음 → 이 장엔 없음
            continue
        v = J['neck'] - c
        J['neck'] = c + v / max(np.linalg.norm(v), 1e-9) * r
        head = np.array([c[0], c[1], r])
        poses[k], costs[k] = from_vec(J, head), cc
        prevJ, prev_head = J, head
    return poses, costs


def figure_colors(frames, up=2, min_frames=5, sample=12):
    """색 스틱맨 후보 색: 장 표본에서 찾은 머리 원(검정 제외)의 색을 색상(H)으로 묶어 min_frames 장 이상 나온 것."""
    from video_to_sfa import frame_strokes
    seen = []
    idx = np.linspace(0, len(frames) - 1, min(sample, len(frames))).astype(int)
    for k in idx:
        (_, st), _, _ = frame_strokes(frames[k])
        for segs, col in st:
            if segs[0][0] == 2 and np.asarray(col).max() > 0:
                seen.append((k, np.asarray(col, float)))
    groups = []
    for k, col in seen:
        h = cv2.cvtColor(np.uint8([[col]]), cv2.COLOR_BGR2HSV)[0, 0].astype(float)
        for g in groups:
            if min(abs(h[0] - g['h']), 180 - abs(h[0] - g['h'])) < 12:
                g['k'].add(k)
                g['cols'].append(col)
                break
        else:
            groups.append(dict(h=h[0], k={k}, cols=[col]))
    need = max(2, int(round(min_frames * len(idx) / max(len(frames), 1))))
    return [np.median(g['cols'], axis=0) for g in groups if len(g['k']) >= need]


def erase_figure(img, pose, col_bgr, bg_bgr, col_thr=45.0):
    """뼈대 근처(머리 반지름 0.6배 + 2px)의 그 색 픽셀을 바탕색으로 칠한다(나머지 변환에서 스틱맨이 두 번 그려지지 않게)."""
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB).astype(np.float32)
    c = cv2.cvtColor(np.uint8([[col_bgr]]), cv2.COLOR_BGR2LAB)[0, 0].astype(np.float32)
    near_col = np.linalg.norm(lab - c, axis=2) < col_thr + 10
    m = np.zeros(img.shape[:2], np.uint8)
    r = float(pose['head'][2])
    w = int(max(r * 0.6, 3) + 2)
    t = lambda q: tuple(int(round(v)) for v in q)
    cv2.circle(m, t(pose['head'][:2]), int(r), 1, 2 * w)
    cv2.line(m, t(pose['neck']), t(pose['hip']), 1, 2 * w)
    for l in pose['arms'] + pose['legs']:
        cv2.polylines(m, [np.int32(np.round(l))], False, 1, 2 * w)
    out = img.copy()
    out[(m > 0) & near_col] = bg_bgr
    return out


def convert_with_figures(video, idxs, out, lib, crop=None, thick_mul=0.7, colors=None, **kw):
    """영상 → SFA: 색 스틱맨은 자세 사전 추적(track3)으로 고정 ID 뼈대, 나머지는 video_to_sfa 2판."""
    import video_to_sfa as V
    imgs = V.read_frames(video, idxs, crop)
    H, W = imgs[0].shape[:2]
    if colors is None:
        colors = figure_colors(imgs)
    tracks = [track3(imgs, col, lib)[0] for col in colors]
    frames, widths, bgs = [], [], []
    for k, im in enumerate(imgs):
        (reg, st), w, bgl = V.frame_strokes(im, **kw)  # 바탕색·굵기 먼저
        bg_bgr = cv2.cvtColor(np.uint8([[bgl]]), cv2.COLOR_LAB2BGR)[0, 0]
        rigs = []
        clean = im
        for fig, (col, tr) in enumerate(zip(colors, tracks)):
            if tr[k] is not None:
                clean = erase_figure(clean, tr[k], col, bg_bgr)
                rigs.append((fig, tr[k], col))
        if rigs:
            (reg, st), w, bgl = V.frame_strokes(clean, **kw)
        frames.append((reg, st, rigs))
        widths.append(w)
        bgs.append(bgl)
    ts = max(0.05, float(np.median(widths)) * (1920 / W) / V.BASE_PX * V.TS_CAL * thick_mul)
    bg_bgr = cv2.cvtColor(np.uint8([[np.median(bgs, axis=0)]]), cv2.COLOR_LAB2BGR)[0, 0]
    n = V.write_sfa(out, frames, W, H, ts, bg=V.argb(bg_bgr))
    return dict(frames=len(frames), objects=n, colors=[np.round(c).tolist() for c in colors],
                tracked=[sum(p is not None for p in tr) for tr in tracks], ts=round(ts, 3))
