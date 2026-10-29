#!/usr/bin/env python3
"""영상 → SFA 선화 변환기 1판 (2026-10-29).

대상: 스틱파이터로 만든 영상처럼 '균일한 굵기 선 + 단색 바탕' 선화. 4711_2 합작 원본 SFA(정답)는
장당 오브젝트 30–80개, 굵기 전부 1.0, 채우기·반투명·글로우 없음, 흰 바탕 + 검은 선 위주(docs/VIDEO-TO-SFA-2026-10-29.md).
방법(장마다):
1. 자르기(--crop) 후 --up 배 확대, 바탕색 = 가장 흔한 색. 바탕과 Lab 거리 --ink-thr 이상이면 먹.
2. 먹 → 가운데선(뼈대) → 끝점·갈림점 사이 선(effect_vectorize.trace), 짧은 가지(선 폭 1.5배 미만)는 버림.
3. 선마다 꺾임(--corner 도 이상)으로 나누고 직선(텐션 0)/2차 곡선으로 맞춤(cube_vector_sfa.fit_run).
4. 색 = 선 위 원본 픽셀 중앙값, 채도 낮고 어두우면 검정으로 맞춤. 굵기 = 장 전체 먹 폭 중앙값 하나(원본처럼 균일).
5. 이어진 조각 끝점은 AC로 잇는다(한 획).
영상 원본·결과 SFA(다른 작가 그림)는 저장소에 넣지 않는다.
사용: python tools/video_to_sfa.py <영상> <out.sfa> --frames 19380,19383,... | --start 초 --end 초 --fps 24
"""
import argparse
import os
import subprocess
import sys
import zipfile

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cube_vector_sfa import contour_segs, corners_open, fit_quad, fit_run, join_lines  # noqa: E402
from effect_vectorize import trace  # noqa: E402

BASE_PX = 1.14 * 8  # 렌더러 기준: 화면 폭 1920에서 굵기 1.0 선 폭(px)
# 측정 굵기 보정: 4711_2 영상(앱 출력, 정답 굵기 전부 1.0)에서 이 측정이 1.82로 나옴 → × 0.55 (근거 영상 1개, 2026-10-29)
TS_CAL = 0.55


def read_frames(video, idxs, crop):
    """영상 장 번호 목록 → BGR 배열들(자르기 적용)."""
    w, h = (int(v) for v in subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=width,height',
                                            '-of', 'csv=p=0', video], capture_output=True, text=True).stdout.split(','))
    want = sorted(set(idxs))
    sel = '+'.join(f'eq(n\\,{i})' for i in want)
    vf = f"select='{sel}'" + (f',crop={crop}' if crop else '')
    p = subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-i', video, '-vf', vf, '-vsync', '0', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-'],
                       capture_output=True)
    cw, ch = (int(crop.split(':')[0]), int(crop.split(':')[1])) if crop else (w, h)
    a = np.frombuffer(p.stdout, np.uint8)
    n = a.size // (cw * ch * 3)
    got = dict(zip(want, a[:n * cw * ch * 3].reshape(n, ch, cw, 3)))
    return [got[i] for i in idxs if i in got]


def fit_rel(S, rel=0.04, abs_tol=1.5, out=None, depth=0):
    """두 점(시작·끝) 사이 = 오브젝트 하나: 텐션이 거의 0이면 직선, 아니면 곡선 하나(제어점 = 텐션 점).
    허용 오차는 선 길이에 비례(사람 선도 픽셀과 정확히 겹치지 않음). 곡선 하나로 안 될 때만(S자 등) 가장 먼 점에 점을 하나 더 찍는다."""
    out = [] if out is None else out
    p0, p2 = S[0], S[-1]
    cl = max(float(np.linalg.norm(p2 - p0)), 1e-9)
    tol = max(abs_tol, rel * cl)
    c, err = fit_quad(S) if len(S) >= 3 else ((p0 + p2) / 2, 0.0)
    if err <= tol or depth >= 3 or len(S) < 8:
        tension = float(np.linalg.norm(c - (p0 + p2) / 2)) / cl
        out.append((1, (p0, p2), 0.0) if tension < 0.04 else (3, (p0, c, p2), tension))
        return out
    t = np.linspace(0, 1, len(S))[:, None]
    B = (1 - t) ** 2 * p0 + 2 * (1 - t) * t * c + t ** 2 * p2
    k = int(np.clip(np.linalg.norm(B - S, axis=1).argmax(), 3, len(S) - 4))
    fit_rel(S[:k + 1], rel, abs_tol, out, depth + 1)
    fit_rel(S[k:], rel, abs_tol, out, depth + 1)
    return out


def chain_paths(paths, cols, node_r, spur, max_turn=45.0, col_de=40.0):
    """뼈대 조각들 → 끝에서 끝까지 이어진 획. 갈림점(반경 node_r 안 끝점들)에서 방향이 가장 곧게 이어지는 가지끼리 붙이고(꺾임 max_turn도 이하, 색 비슷),
    한쪽이 열린 짧은 가지(spur 미만)는 버린다. 반환: [(점 배열(x,y), 색)]."""
    P = [np.array([(x, y) for y, x in p], np.float64) for p in paths]
    ends = np.array([q for a in P for q in (a[0], a[-1])])
    if not len(ends):
        return []
    # 끝점 무리 = 마디
    lab = -np.ones(len(ends), int)
    nid = 0
    for i in range(len(ends)):
        if lab[i] >= 0:
            continue
        stack = [i]
        lab[i] = nid
        while stack:
            j = stack.pop()
            for k in np.where((np.linalg.norm(ends - ends[j], axis=1) <= node_r) & (lab < 0))[0]:
                lab[k] = nid
                stack.append(k)
        nid += 1
    deg = np.bincount(lab, minlength=nid)
    center = np.array([ends[lab == n].mean(0) for n in range(nid)])
    keep = []
    for i, a in enumerate(P):
        L = float(np.linalg.norm(np.diff(a, axis=0), axis=1).sum())
        if (deg[lab[2 * i]] == 1 or deg[lab[2 * i + 1]] == 1) and L < spur and not (deg[lab[2 * i]] == 1 and deg[lab[2 * i + 1]] == 1):
            continue  # 갈림점에 붙은 짧은 가시
        if lab[2 * i] == lab[2 * i + 1] and L < spur:
            continue
        keep.append(i)
    # 마디마다 가지 짝짓기
    def leave_dir(a, at_start):
        q = a if at_start else a[::-1]
        L = np.r_[0, np.cumsum(np.linalg.norm(np.diff(q, axis=0), axis=1))]
        j = min(int(np.searchsorted(L, spur)), len(q) - 1)
        v = q[j] - q[0]
        return v / max(np.linalg.norm(v), 1e-9)
    at = {}
    for i in keep:
        if lab[2 * i] == lab[2 * i + 1]:
            continue  # 제자리로 돌아오는 고리(머리 원 등)는 혼자 한 획
        for e in (0, 1):
            at.setdefault(lab[2 * i + e], []).append((i, e))
    nxt = {}
    for n, br in at.items():
        if len(br) < 2:
            continue
        cand = []
        for x in range(len(br)):
            for y in range(x + 1, len(br)):
                (i, ei), (j, ej) = br[x], br[y]
                if i == j:
                    continue
                di, dj = leave_dir(P[i], ei == 0), leave_dir(P[j], ej == 0)
                turn = 180 - np.degrees(np.arccos(np.clip(np.dot(di, dj), -1, 1)))
                if turn <= max_turn and np.linalg.norm(np.asarray(cols[i], float) - np.asarray(cols[j], float)) <= col_de:
                    cand.append((turn, br[x], br[y]))
        used = set()
        for turn, a, b in sorted(cand):
            if a in used or b in used:
                continue
            used |= {a, b}
            nxt[a], nxt[b] = b, a
    done, out = set(), []
    for i in keep:
        if i in done:
            continue
        # 한쪽 끝까지 거슬러 간 뒤 반대쪽으로 이어 붙인다
        cur, e = i, 0
        seen = {i}
        while (cur, e) in nxt:
            j, ej = nxt[(cur, e)]
            if j in seen:
                break
            seen.add(j)
            cur, e = j, 1 - ej
        start = (cur, e)
        seq, (cur, e) = [], start
        while True:
            done.add(cur)
            a = P[cur] if e == 0 else P[cur][::-1]
            seq.append(a if not seq else a[1:])
            nb = nxt.get((cur, 1 - e))
            if nb is None or nb[0] in done:
                break
            cur, e = nb
        pts = np.vstack(seq)
        # 갈림점에 닿은 끝은 갈림점 한가운데로(틈 없이 이어지게)
        n0 = lab[2 * start[0] + start[1]]
        n1 = lab[2 * cur + (1 - e)]
        if deg[n0] >= 2:
            pts[0] = center[n0]
        if deg[n1] >= 2:
            pts[-1] = center[n1]
        col = np.median(np.array([cols[k] for k in seen | {cur}]), axis=0)
        out.append((pts, col))
    return out


def fit_circle(P, max_res=0.07, min_cover=300.0):
    """점열이 원(고리)이면 (중심, 반지름), 아니면 None. 최소제곱 원 + 반지름 대비 잔차·각도 범위 검사."""
    if len(P) < 12:
        return None
    A = np.c_[2 * P, np.ones(len(P))]
    b = (P ** 2).sum(1)
    (cx, cy, c), *_ = np.linalg.lstsq(A, b, rcond=None)
    r = float(np.sqrt(max(c + cx * cx + cy * cy, 1e-9)))
    res = np.abs(np.linalg.norm(P - (cx, cy), axis=1) - r)
    ang = np.sort(np.degrees(np.arctan2(P[:, 1] - cy, P[:, 0] - cx)) % 360)
    gap = max(np.max(np.diff(ang)) if len(ang) > 1 else 360, 360 - ang[-1] + ang[0])
    if float(np.percentile(res, 90)) <= max_res * r and 360 - gap >= min_cover:
        return np.array([cx, cy]), r
    return None


def merge_strokes(out, gap, ang=8.0, off=1.5):
    """갈림점에서 끊긴 곧은 선을 같은 색끼리 다시 잇는다(cube_vector_sfa.join_lines, 색은 1/32 단위로 묶음)."""
    groups = {}
    for segs, col in out:
        groups.setdefault(tuple((np.asarray(col) // 32).astype(int)), []).append((segs, 1.0, col))
    res = []
    for g in groups.values():
        res += [(segs, col) for segs, _, col in join_lines(g, gap=gap, ang=ang, off=off)]
    return res


def mass_regions(big, lab, mass, up, corner, line_tol, quad_tol, k=4, merge_de=15.0, min_area=30, closed=False):
    """덩어리 픽셀을 Lab k-평균 색(가까운 색 합침)으로 나눠 색마다 윤곽 → [(넓이, [(hole, segs)...], bgr)]."""
    ys, xs = np.nonzero(mass)
    X = lab[ys, xs]
    k = min(k, len(X))
    _, lb, cen = cv2.kmeans(X, k, None, (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 0.5), 2, cv2.KMEANS_PP_CENTERS)
    lb = lb.ravel()
    for i in range(k):  # 가까운 색 합치기
        for j in range(i):
            if np.linalg.norm(cen[i] - cen[j]) < merge_de:
                lb[lb == i] = j
    out = []
    for c in np.unique(lb):
        mm = np.zeros(mass.shape, np.uint8)
        mm[ys[lb == c], xs[lb == c]] = 1
        mm = cv2.morphologyEx(mm, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
        mm = (cv2.GaussianBlur(mm.astype(np.float32), (0, 0), 1.5 * up) > 0.5).astype(np.uint8)  # 압축 계단 윤곽 다듬기
        bgr = np.median(big[ys[lb == c], xs[lb == c]], axis=0)
        cnts, hier = cv2.findContours(mm, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
        if hier is None:
            continue
        hier = hier[0]
        for i, cn in enumerate(cnts):
            if hier[i][3] != -1 or cv2.contourArea(cn) < min_area * up * up:
                continue
            fitc = (lambda C: closed_segs(C, corner)) if closed else (lambda C: contour_segs(C, 1.5, corner, 2 * line_tol, 2 * quad_tol))
            group = [(False, fitc(cn[:, 0, :].astype(np.float64) / up))]
            j = hier[i][2]
            while j != -1:
                if cv2.contourArea(cnts[j]) >= min_area * up * up:
                    group.append((True, fitc(cnts[j][:, 0, :].astype(np.float64) / up)))
                j = hier[j][0]
            out.append((cv2.contourArea(cn), group, bgr))
    out.sort(key=lambda r: -r[0])
    return [(g, c) for _, g, c in out]


def snap_black(col):
    hsv = cv2.cvtColor(np.uint8([[col]]), cv2.COLOR_BGR2HSV)[0, 0]
    return np.zeros(3) if (hsv[1] < 70 and hsv[2] < 110) else col


def smooth_open(P, sig):
    """열린 선 점열 가우스 다듬기(양 끝 고정) — 압축 계단 때문에 생기는 가짜 모서리 방지."""
    if len(P) < 5:
        return P
    k = np.exp(-0.5 * (np.arange(-3 * int(np.ceil(sig)), 3 * int(np.ceil(sig)) + 1) / sig) ** 2)
    k /= k.sum()
    pad = len(k) // 2
    Q = np.vstack([np.repeat(P[:1], pad, 0), P, np.repeat(P[-1:], pad, 0)])
    R = np.stack([np.convolve(Q[:, j], k, mode='valid') for j in range(2)], 1)
    R[0], R[-1] = P[0], P[-1]
    return R


def closed_segs(C, corner, rel=0.04):
    """닫힌 윤곽 → 모서리(꺾임 corner도 이상) 점만 찍고 점 사이 오브젝트 하나(fit_rel). 모서리가 2개 미만이면 가장 먼 두 점."""
    n = len(C)
    if n < 6:
        return []
    per = cv2.arcLength(C.astype(np.float32).reshape(-1, 1, 2), True)
    ap = cv2.approxPolyDP(C.astype(np.float32).reshape(-1, 1, 2), max(1.5, 0.01 * per), True)[:, 0, :]
    idx = []
    for v in ap:
        idx.append(int(np.linalg.norm(C - v, axis=1).argmin()))
    idx = sorted(set(idx))
    keep = []
    for j, i in enumerate(idx):
        a, b, c = C[idx[j - 1]], C[i], C[idx[(j + 1) % len(idx)]]
        u, v = b - a, c - b
        cosv = float(np.dot(u, v) / max(np.linalg.norm(u) * np.linalg.norm(v), 1e-9))
        if np.degrees(np.arccos(np.clip(cosv, -1, 1))) >= corner:
            keep.append(i)
    if len(keep) < 2:
        i0 = 0
        keep = [i0, int(np.linalg.norm(C - C[i0], axis=1).argmax())]
    keep = sorted(keep)
    segs = []
    for j, i in enumerate(keep):
        k = keep[(j + 1) % len(keep)]
        S = C[i:k + 1] if k > i else np.vstack([C[i:], C[:k + 1]])
        if len(S) >= 2:
            fit_rel(S, rel=rel, out=segs)
    return segs


def find_circles(big, m, up, min_r=4.0, max_r=60.0, on_ring=0.85, inside_empty=0.6):
    """머리 원 찾기: Hough 원 후보 → 둘레 표본점의 on_ring 이상이 먹이고 안쪽(0.5r 원) 표본점의 inside_empty 이상이 바탕이면 원 오브젝트 하나.
    원 위를 다른 선이 지나가도 된다(안쪽 구멍이 쪼개져도 됨). 고리 띠의 먹은 선 따기에서 뺀다. 반환: ([(segs, bgr)], 고리를 지운 먹)."""
    dt_ink = cv2.distanceTransform(m, cv2.DIST_L2, 3)
    mw = 2 * float(np.median(dt_ink[m > 0])) if m.any() else 4.0 * up
    blur = cv2.GaussianBlur((m * 255).astype(np.uint8), (0, 0), 1.0 * up)
    hc = cv2.HoughCircles(blur, cv2.HOUGH_GRADIENT, dp=1, minDist=min_r * up * 2, param1=80, param2=18,
                          minRadius=int(min_r * up), maxRadius=int(max_r * up))
    H, W = m.shape
    out, m2 = [], m.copy()
    if hc is None:
        return out, m2
    th = np.linspace(0, 2 * np.pi, 72, endpoint=False)
    for cx, cy, r in sorted(hc[0], key=lambda c: -c[2]):
        # 반지름 미세 조정: 둘레 먹 비율이 가장 큰 r
        best = None
        for rr in np.arange(max(r - mw, min_r * up), r + mw, 0.5):
            xs = np.clip((cx + rr * np.cos(th)).astype(int), 0, W - 1)
            ys = np.clip((cy + rr * np.sin(th)).astype(int), 0, H - 1)
            f = float((m2[ys, xs] > 0).mean() if best is None else (m[ys, xs] > 0).mean())
            if best is None or f > best[0]:
                best = (f, rr)
        f, rr = best
        if f < on_ring:
            continue
        ri = np.linspace(0, 0.5 * rr, 6)[1:]
        xi = np.clip((cx + np.outer(ri, np.cos(th))).astype(int).ravel(), 0, W - 1)
        yi = np.clip((cy + np.outer(ri, np.sin(th))).astype(int).ravel(), 0, H - 1)
        if (m[yi, xi] == 0).mean() < inside_empty:
            continue
        yy, xx = np.ogrid[:H, :W]
        dd = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
        band = np.abs(dd - rr) <= mw / 2 + 1
        if not (band & (m2 > 0)).any():
            continue
        col = snap_black(np.median(big[band & (m > 0)], axis=0))
        band = np.abs(dd - rr) <= mw + 1.5 * up  # 지울 때는 넉넉히(중심 오차·흐림)
        c = np.array([cx, cy]) / up
        out.append(([(2, (c - (0, rr / up), c + (0, rr / up)), 0.0)], col))
        m2[band] = 0
    return out, m2


def frame_strokes(img, up=2, ink_thr=28.0, corner=35.0, line_tol=1.0, quad_tol=1.4, min_len=6, join=True, mass_px=10.0, mode='points'):
    from skimage.morphology import skeletonize
    big = cv2.resize(img, None, fx=up, fy=up, interpolation=cv2.INTER_CUBIC)
    lab = cv2.cvtColor(big, cv2.COLOR_BGR2LAB).astype(np.float32)
    q = (big // 16).reshape(-1, 3)
    vals, cnt = np.unique(q, axis=0, return_counts=True)
    bgq = vals[cnt.argmax()]
    bg_lab = lab.reshape(-1, 3)[(q == bgq).all(1)].mean(0)
    d = np.linalg.norm(lab - bg_lab, axis=2)
    m = (d > ink_thr).astype(np.uint8)
    e = 2 * up  # 자른 가장자리(검은 띠와 섞인 줄)는 버림
    m[:e], m[-e:], m[:, :e], m[:, -e:] = 0, 0, 0, 0
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
    n, cc, st, _ = cv2.connectedComponentsWithStats(m, 8)
    small = np.where(st[:, cv2.CC_STAT_AREA] < 4 * up * up)[0]
    m[np.isin(cc, small)] = 0
    # 굵은 덩어리(먹 폭 10px@640 이상 — 흐린 360p에선 보통 선도 먹 폭 약 6.5px, 뭉개진 빗금·칠한 면은 14px 이상) → 채우기 면, 나머지 → 선
    R = int(mass_px * up / 2)
    core = (cv2.distanceTransform(m, cv2.DIST_L2, 3) >= R).astype(np.uint8)
    n, cc, st, _ = cv2.connectedComponentsWithStats(core, 8)  # 선이 겹친 갈림점의 작은 핵은 덩어리가 아님
    core[np.isin(cc, np.where(st[:, cv2.CC_STAT_AREA] < 20 * up * up)[0])] = 0
    ker = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * R + 3, 2 * R + 3))
    mass = cv2.dilate(core, ker) & m
    regions = mass_regions(big, lab, mass, up, corner, line_tol, quad_tol, closed=(mode == 'points')) if mass.sum() else []
    m = m & (1 - cv2.dilate(mass, np.ones((3, 3), np.uint8)))
    circles = []
    if mode == 'points':
        circles, m = find_circles(big, m, up)
    dist = cv2.distanceTransform(m, cv2.DIST_L2, 3)
    sk = skeletonize(m > 0)
    paths = trace(sk)
    # 굵기: 흐림은 먹 총량을 바꾸지 않는다 → 선마다 (먹 진하기 합 ÷ 선 대비) ÷ 길이. 대비 = 선 위 거리값 상위 90%
    widths = []
    for pth in paths:
        if len(pth) < 10:
            continue
        ys, xs = np.array(pth).T
        c = float(np.percentile(d[ys, xs], 90))
        box = np.zeros_like(m)
        box[ys, xs] = 1
        box = cv2.dilate(box, np.ones((int(4 * up) | 1, int(4 * up) | 1), np.uint8)) & m
        widths.append(float(np.clip(d[box > 0] / max(c, 1), 0, 1).sum()) / len(pth))
    width = float(np.median(widths)) if widths else 2.0 * up
    if mode == 'pixel':  # 1판(픽셀 따라가기) — 비교용
        out = []
        for pth in paths:
            if len(pth) < max(min_len, int(1.5 * width)):
                continue
            P = np.array([(x, y) for y, x in pth], np.float64) / up
            col = snap_black(np.median(np.array([big[y, x] for y, x in pth]), axis=0))
            cs = corners_open(P, 1.0, corner)
            segs = []
            for i, k in zip(cs[:-1], cs[1:]):
                if k - i >= 1:
                    fit_run(P[i:k + 1], line_tol, quad_tol, segs)
            segs = [sg for sg in segs if np.linalg.norm(np.asarray(sg[1][-1]) - np.asarray(sg[1][0])) >= 0.75 * width / up or len(segs) == 1]
            if segs:
                out.append((segs, col))
        if join:
            out = merge_strokes(out, gap=1.5 * width / up)
        return (regions, out), width / up, bg_lab
    # 2판(점 찍고 선 넣기): 획을 끝에서 끝까지 잇고 → 끝점·모서리만 점으로 → 점 사이 오브젝트 하나
    mask_w = 2 * float(np.median(dist[sk])) if sk.any() else 4.0 * up
    cols = [snap_black(np.median(np.array([big[y, x] for y, x in pth]), axis=0)) for pth in paths]
    out = []
    for pts, col in chain_paths(paths, cols, node_r=0.7 * mask_w, spur=1.2 * mask_w):
        P = pts / up
        if float(np.linalg.norm(np.diff(P, axis=0), axis=1).sum()) < max(min_len / up, 1.5 * width / up):
            continue
        circ = fit_circle(P)
        if circ is not None:  # 머리 같은 고리 = 원 오브젝트 하나(두 점 = 지름 양 끝)
            (cx, cy), r = circ
            out.append(([(2, (np.array([cx, cy - r]), np.array([cx, cy + r])), 0.0)], col))
            continue
        P = smooth_open(P, 1.0)
        cs = corners_open(P, 1.5, corner)
        segs = []
        for i, k in zip(cs[:-1], cs[1:]):
            if k - i >= 1:
                fit_rel(P[i:k + 1], out=segs)
        if segs:
            out.append((segs, col))
    return (regions, circles + out), width / up, bg_lab


def argb(bgr, a=255):
    b, g, r = (int(round(v)) for v in bgr)
    v = (a << 24) | (r << 16) | (g << 8) | b
    return v - (1 << 32) if v >= 1 << 31 else v


RIG_OID, RIG_PID = 5_000_000, 50_000_000  # 스틱맨 뼈대의 고정 ID 시작(다른 오브젝트 번호와 겹치지 않게)


def rig_xml(fig, p, c, ts, W, H):
    """스틱맨 한 명 = 머리 원 + 몸통 + 팔 2×2 + 다리 2×2 (오브젝트 10). ID = 시작 + 사람 번호·뼈 번호(장마다 같음)."""
    hc, r = np.asarray(p['head'][:2], float), float(p['head'][2])
    neck, hip = np.asarray(p['neck'], float), np.asarray(p['hip'], float)
    top = hc + (hc - neck)
    objs = [('2', [neck, top]), ('1', [neck, hip])]
    for a in p['arms']:
        objs += [('1', [a[0], a[1]]), ('1', [a[1], a[2]])]
    for l in p['legs']:
        objs += [('1', [l[0], l[1]]), ('1', [l[1], l[2]])]
    ob = RIG_OID + fig * 16
    pb = RIG_PID + fig * 64
    pid = lambda j, i: pb + 2 * j + i  # 오브젝트 j의 i번째 점
    # 이음: 몸통 목 ↔ 머리 목쪽, 팔 뿌리 ↔ 몸통 목, 다리 뿌리 ↔ 몸통 엉덩이, 아래 마디 뿌리 ↔ 위 마디 끝
    link = {(1, 0): pid(0, 0)}
    for j in range(2, len(objs), 2):
        link[(j, 0)] = pid(1, 0) if j < 6 else pid(1, 1)
        link[(j + 1, 0)] = pid(j, 1)
    out = []
    for j, (kind, pts) in enumerate(objs):
        a = [f'<AO ID="{ob + j}" TypeId="{kind}" Color="{c}" LayerId="0" DrawOrder="{ob + j}" ThicknessScale="{ts:.3f}" ObjectScale="1.0" '
             'GlowRadius="0" GlowThickness="0" GlowColor="4294967295" GlowAlpha="0">']
        for i, (x, y) in enumerate(pts):
            ac = f'<AC ConnPtId="{link[(j, i)]}"/>' if (j, i) in link else ''
            flags = 3 if (j == 1 and i == 1) else (8 if (j, i) in link else 9)
            a.append(f'<AP ID="{pid(j, i)}" Flags="{flags}" Index="{i}" X="{x / W * 100:.3f}" Y="{y / H * 100:.3f}">{ac}</AP>')
        out.append(''.join(a) + '</AO>')
    return ''.join(out)


def write_sfa(path, frames, W, H, ts, bg=-1, name=None):
    """frames: [(regions, strokes[, rigs]), ...] → 여러 장 SFA(레이어 1개). 면(FR)이 아래, 선(굵기 균일)이 위, 스틱맨 뼈대가 맨 위.
    rigs: [(fig 번호, pose dict(video_stickman_track), bgr)] — 오브젝트·점 ID를 장 사이에 고정하고 관절을 AC로 잇는다(사람이 만든 스틱맨처럼)."""
    name = name or os.path.splitext(os.path.basename(path))[0]
    oid = pid = 1
    body = []
    for k, fr in enumerate(frames):
        regions, strokes = fr[0], fr[1]
        rigs = fr[2] if len(fr) > 2 else []
        o = [f'<Frame ID="{k + 1}" Position="{k}" BackgroundColor="{bg}"><LayerDef ID="0" Name="Layer 1" Visible="true" Locked="false"/>']
        for group, col in regions:  # 채우기 면: 윤곽 조각을 AC로 잇고 FS로 묶음(cube_vector_sfa.Writer.region과 같은 형식), 테두리는 같은 색 가는 선
            c = argb(col)
            fs = []
            for ci, (_, segs) in enumerate(group):
                prev = None
                for kind, pts, _ in segs:
                    s = [f'<AO ID="{oid}" TypeId="{kind}" Color="{c}" LayerId="0" DrawOrder="{oid}" ThicknessScale="0.100" ObjectScale="1.0" '
                         'GlowRadius="0" GlowThickness="0" GlowColor="4294967295" GlowAlpha="0">']
                    for i, (x, y) in enumerate(pts):
                        ac = f'<AC ConnPtId="{prev}"/>' if (i == 0 and prev) else ''
                        s.append(f'<AP ID="{pid + i}" Flags="{8 if i == 0 else 9}" Index="{i}" X="{x / W * 100:.3f}" Y="{y / H * 100:.3f}">{ac}</AP>')
                    o.append(''.join(s) + '</AO>')
                    fs.append(f'<FS Kind="0" ObjId="{oid}" StartPtId="{pid}" EndPtId="{pid + len(pts) - 1}" StartT="0.0" EndT="1.0" Contour="{ci}"/>')
                    prev = pid + len(pts) - 1
                    oid += 1
                    pid += len(pts)
            o.append(f'<FR Color="{c}">' + ''.join(fs) + '</FR>')
        for segs, col in strokes:
            prev = None
            c = argb(col)
            for kind, pts, _ in segs:
                s = [f'<AO ID="{oid}" TypeId="{kind}" Color="{c}" LayerId="0" DrawOrder="{oid}" ThicknessScale="{ts:.3f}" ObjectScale="1.0" '
                     'GlowRadius="0" GlowThickness="0" GlowColor="4294967295" GlowAlpha="0">']
                for i, (x, y) in enumerate(pts):
                    ac = f'<AC ConnPtId="{prev}"/>' if (i == 0 and prev) else ''
                    s.append(f'<AP ID="{pid + i}" Flags="{8 if i == 0 else 9}" Index="{i}" X="{x / W * 100:.3f}" Y="{y / H * 100:.3f}">{ac}</AP>')
                o.append(''.join(s) + '</AO>')
                prev = pid + len(pts) - 1
                oid += 1
                pid += len(pts)
        for fig, pose, col in rigs:
            o.append(rig_xml(fig, pose, argb(col), ts, W, H))
        body.append(''.join(o) + '</Frame>')
    xml = (f"<?xml version='1.0' encoding='utf-8'?>\n<Sequence Name=\"{name}\" HeightWidthRatio=\"{H / W:.6f}\" FrameCount=\"{len(frames)}\" "
           f"BackgroundColor=\"{bg}\">\n" + '\n'.join(body) + '\n</Sequence>\n')
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(name + '.xml', xml)
    return oid - 1


def convert(video, idxs, out, crop=None, thick_mul=0.7, **kw):
    imgs = read_frames(video, idxs, crop)
    H, W = imgs[0].shape[:2]
    frames, widths, bgs = [], [], []
    for im in imgs:
        s, w, bgl = frame_strokes(im, **kw)
        frames.append(s)
        widths.append(w)
        bgs.append(bgl)
    ts = max(0.05, float(np.median(widths)) * (1920 / W) / BASE_PX * TS_CAL * thick_mul)  # thick_mul: 사용자 10-29 '두께 좀 더 얇게'
    bg_bgr = cv2.cvtColor(np.uint8([[np.median(bgs, axis=0)]]), cv2.COLOR_LAB2BGR)[0, 0]
    n = write_sfa(out, frames, W, H, ts, bg=argb(bg_bgr))
    return dict(frames=len(frames), objects=n, per_frame=[sum(len(sg) for g, _ in f[0] for _, sg in g) + sum(len(s[0]) for s in f[1]) for f in frames], ts=round(ts, 3))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('video')
    ap.add_argument('out')
    ap.add_argument('--frames', help='영상 장 번호(쉼표)')
    ap.add_argument('--start', type=float)
    ap.add_argument('--end', type=float)
    ap.add_argument('--fps', type=float, default=24)
    ap.add_argument('--crop', help='w:h:x:y')
    ap.add_argument('--ink-thr', type=float, default=28.0)
    ap.add_argument('--corner', type=float, default=50.0)
    ap.add_argument('--line-tol', type=float, default=1.5)
    ap.add_argument('--quad-tol', type=float, default=2.0)
    ap.add_argument('--thick-mul', type=float, default=0.7, help='선 굵기 배율(영상에서 잰 굵기 × 이 값)')
    ap.add_argument('--mode', choices=['points', 'pixel'], default='points', help='points = 점 찍고 선 넣기(2판), pixel = 1판')
    a = ap.parse_args()
    if a.frames:
        idxs = [int(x) for x in a.frames.split(',')]
    else:
        vf = eval(subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=r_frame_rate', '-of', 'csv=p=0', a.video],
                                 capture_output=True, text=True).stdout.strip())
        idxs = [int(round(t * vf)) for t in np.arange(a.start, a.end, 1 / a.fps)]
    r = convert(a.video, idxs, a.out, a.crop, thick_mul=a.thick_mul, ink_thr=a.ink_thr, corner=a.corner, line_tol=a.line_tol, quad_tol=a.quad_tol, mode=a.mode)
    print(r['frames'], '장, 오브젝트', r['objects'], '장당 중앙', int(np.median(r['per_frame'])), '굵기', r['ts'])


if __name__ == '__main__':
    main()
