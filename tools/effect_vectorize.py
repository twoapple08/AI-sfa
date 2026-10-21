#!/usr/bin/env python3
"""이펙트를 '수학 함수로 그린 아이젠' 방식으로 바꾼다: 구간 제한 포물선 조각(= 2차 베지어).

나카무라 임팩트 이펙트는 대부분 채워진 면(가시 섬광·굵은 고리·쐐기)이라 윤곽선 방식이 기본이다.
1. 흑백으로 나눈다(Otsu). 가장자리에 많은 쪽을 바탕으로 보고 나머지를 '그림'으로 둔다.
2. 그림의 윤곽(바깥·구멍)을 따고, 윤곽마다 2차 베지어를 최소제곱으로 맞춘다.
   최대 오차가 tol 픽셀을 넘으면 그 점에서 나눈다(재귀). 날카로운 끝은 먼저 꼭짓점으로 나눈다.
3. 결과: 윤곽 목록 {hole, segs:[[x0,y0,cx,cy,x1,y1],…]} (영상 높이를 1로 둔 좌표), 그림색·바탕색.
   SFA로는 TypeId 3 곡선 사슬 + FR/FS 채우기(구멍은 Contour 1)로 옮긴다.
가는 선만 있는 장면은 --stroke로 중심선 방식(굵기 포함)을 쓴다.

원본 프레임·추출한 형태는 저장소에 넣지 않는다(AGENTS.md 이펙트 그리기 원칙). 이 도구와 통계만 둔다.
사용: python tools/effect_vectorize.py <영상> <프레임번호> <출력.json> [--tol 1.2] [--png 확인.png]
"""
import argparse
import json
import math

import cv2
import numpy as np
from skimage.morphology import skeletonize

N8 = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]


def read_frame(path, idx, height=540):
    v = cv2.VideoCapture(path)
    v.set(cv2.CAP_PROP_POS_FRAMES, idx)
    ok, f = v.read()
    if not ok:
        raise SystemExit(f'프레임 {idx}를 읽지 못함')
    s = height / f.shape[0]
    return cv2.resize(f, (round(f.shape[1] * s), height), interpolation=cv2.INTER_AREA)


def ink(img):
    """그림(선·면) = 1. 바탕은 가장자리에서 많은 쪽으로 본다."""
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, b = cv2.threshold(g, 0, 1, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    edge = np.concatenate([b[0], b[-1], b[:, 0], b[:, -1]])
    if edge.mean() < 0.5:      # 바탕이 검다 → 흰 그림이 잉크
        return b.astype(np.uint8)
    return (1 - b).astype(np.uint8)


def trace(skel):
    """스켈레톤을 끝점·갈림점 사이 선 조각으로 나눈다."""
    h, w = skel.shape
    pts = set(zip(*np.nonzero(skel)))
    def nb(p):
        return [(p[0] + dy, p[1] + dx) for dy, dx in N8 if (p[0] + dy, p[1] + dx) in pts]
    deg = {p: len(nb(p)) for p in pts}
    nodes = {p for p, d in deg.items() if d != 2}
    used = set()
    paths = []
    def walk(a, b):
        path = [a, b]
        used.add((a, b)); used.add((b, a))
        while path[-1] not in nodes:
            nxt = [q for q in nb(path[-1]) if q != path[-2] and (path[-1], q) not in used]
            if not nxt:
                break
            q = nxt[0]
            used.add((path[-1], q)); used.add((q, path[-1]))
            path.append(q)
        return path
    for a in nodes:
        for b in nb(a):
            if (a, b) not in used:
                paths.append(walk(a, b))
    # 고리(끝점 없는 닫힌 선)
    for p in pts:
        if p not in nodes:
            for q in nb(p):
                if (p, q) not in used:
                    paths.append(walk(p, q))
    return paths


def bez_fit(P):
    """끝점 고정, 현 길이 매개변수로 제어점 하나를 최소제곱으로 구한다."""
    P = np.asarray(P, float)
    d = np.r_[0, np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))]
    t = d / d[-1] if d[-1] > 0 else np.linspace(0, 1, len(P))
    a, b = P[0], P[-1]
    w = 2 * t * (1 - t)
    r = P - np.outer((1 - t) ** 2, a) - np.outer(t ** 2, b)
    c = (w[:, None] * r).sum(0) / max((w * w).sum(), 1e-9)
    Q = np.outer((1 - t) ** 2, a) + np.outer(w, c) + np.outer(t ** 2, b)
    err = np.linalg.norm(Q - P, axis=1)
    return c, err


def fit(P, tol, out, depth=0):
    if len(P) < 3:
        out.append((P[0], (np.asarray(P[0]) + np.asarray(P[-1])) / 2, P[-1]))
        return
    c, err = bez_fit(P)
    k = int(err.argmax())
    if err[k] <= tol or depth > 12 or len(P) < 6:
        out.append((P[0], c, P[-1]))
        return
    k = min(max(k, 2), len(P) - 3)
    fit(P[:k + 1], tol, out, depth + 1)
    fit(P[k:], tol, out, depth + 1)


def vectorize(img, tol=1.2, min_len=4):
    m = ink(img)
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
    dist = cv2.distanceTransform(m, cv2.DIST_L2, 3)
    sk = skeletonize(m.astype(bool))
    segs = []
    for path in trace(sk):
        if len(path) < min_len:
            continue
        P = [(x, y) for y, x in path]
        out = []
        fit(P, tol, out)
        for a, c, b in out:
            # 굵기 = 조각을 따라 잰 거리 변환의 중앙값 × 2
            n = max(3, int(math.dist(a, b)))
            ws = [dist[int(round(a[1] + (b[1] - a[1]) * s)), int(round(a[0] + (b[0] - a[0]) * s))] for s in np.linspace(0, 1, n)]
            wdt = max(1.0, 2 * float(np.median(ws)))
            segs.append([*a, *c, *b, wdt])
    return m, segs


def corners(P, k=6, ang=55):
    """윤곽에서 꺾인 점(가시 끝 등)의 번호. k점 앞뒤 방향 차이가 ang도 이상이고 그 근처에서 가장 큰 곳."""
    n = len(P)
    if n < 3 * k:
        return []
    A = np.asarray(P, float)
    v1 = A - np.roll(A, k, 0); v2 = np.roll(A, -k, 0) - A
    c = np.degrees(np.arccos(np.clip((v1 * v2).sum(1) / (np.linalg.norm(v1, axis=1) * np.linalg.norm(v2, axis=1) + 1e-9), -1, 1)))
    out = []
    for i in range(n):
        if c[i] >= ang and c[i] == max(c[(i + j) % n] for j in range(-k, k + 1)):
            out.append(i)
    return out


def outline(img, tol=1.0, min_area=12):
    m = ink(img)
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
    return outline_mask(m, tol, min_area)


def outline_mask(m, tol=1.0, min_area=12):
    cs, hier = cv2.findContours(m, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
    shapes = []
    if hier is None:
        return m, shapes
    for i, c in enumerate(cs):
        if cv2.contourArea(c) < min_area:
            continue
        P = c[:, 0, :].astype(float)
        # 계단 모양을 줄이는 가벼운 평활(끝점 위치는 거의 그대로)
        P = (np.roll(P, 1, 0) + 2 * P + np.roll(P, -1, 0)) / 4
        cut = corners(P)
        if len(cut) < 2:   # 꺾인 곳이 없으면 멀리 떨어진 두 점에서 나눈다
            j = int(np.linalg.norm(P - P[0], axis=1).argmax()); cut = sorted({0, j})
        segs = []
        for a, b in zip(cut, cut[1:] + [cut[0] + len(P)]):
            idx = [k % len(P) for k in range(a, b + 1)]
            out = []
            fit(list(map(tuple, P[idx])), tol, out)
            segs += [[*map(float, x), *map(float, y), *map(float, z)] for x, y, z in out]
        shapes.append({'hole': bool(hier[0][i][3] >= 0), 'segs': segs})
    return m, shapes


def render_fill(shapes, shape, scale=1.0):
    canvas = np.zeros((int(shape[0] * scale), int(shape[1] * scale)), np.uint8)
    polys = []
    for sh in shapes:
        pts = []
        for x0, y0, cx, cy, x1, y1 in sh['segs']:
            t = np.linspace(0, 1, 10)[:, None]
            pts.append((1 - t) ** 2 * [x0, y0] + 2 * t * (1 - t) * [cx, cy] + t ** 2 * [x1, y1])
        if pts:
            polys.append(np.round(np.vstack(pts) * scale).astype(np.int32))
    # 짝홀 규칙: 윤곽마다 XOR
    for p in polys:
        layer = np.zeros_like(canvas); cv2.fillPoly(layer, [p], 1, cv2.LINE_AA if False else cv2.LINE_8)
        canvas ^= layer
    return canvas


def render(segs, shape, scale=1.0):
    canvas = np.full((int(shape[0] * scale), int(shape[1] * scale)), 255, np.uint8)
    for x0, y0, cx, cy, x1, y1, w in segs:
        t = np.linspace(0, 1, 12)[:, None]
        Q = (1 - t) ** 2 * [x0, y0] + 2 * t * (1 - t) * [cx, cy] + t ** 2 * [x1, y1]
        cv2.polylines(canvas, [np.round(Q * scale).astype(np.int32)], False, 0, max(1, round(w * scale)), cv2.LINE_AA)
    return canvas


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('video'); ap.add_argument('frame', type=int); ap.add_argument('out')
    ap.add_argument('--tol', type=float, default=1.2)
    ap.add_argument('--png')
    ap.add_argument('--stroke', action='store_true', help='가는 선 장면: 중심선 + 굵기')
    a = ap.parse_args()
    img = read_frame(a.video, a.frame)
    H = img.shape[0]
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    if a.stroke:
        m, segs = vectorize(img, a.tol)
        rec = (render(segs, m.shape) < 128).astype(np.uint8)
        data = {'mode': 'stroke', 'w': img.shape[1] / H, 'segs': [[round(v / H, 5) for v in s] for s in segs]}
        n = len(segs)
    else:
        m, shapes = outline(img, a.tol)
        rec = render_fill(shapes, m.shape)
        data = {'mode': 'fill', 'w': img.shape[1] / H,
                'shapes': [{'hole': sh['hole'], 'segs': [[round(v / H, 5) for v in s] for s in sh['segs']]} for sh in shapes]}
        n = sum(len(sh['segs']) for sh in shapes)
    ink_val = int(np.median(g[m == 1])) if m.any() else 0
    data['ink'] = ink_val; data['bg'] = int(np.median(g[m == 0])) if (m == 0).any() else 255
    with open(a.out, 'w') as fh:
        json.dump(data, fh)
    inter = int((rec & m).sum()); union = int((rec | m).sum())
    print(f'포물선 조각 {n}개, 그림 영역 IoU {inter / max(union, 1):.3f}')
    if a.png:
        cv2.imwrite(a.png, np.hstack([g, (1 - m) * 255, (1 - rec) * 255]))


if __name__ == '__main__':
    main()
