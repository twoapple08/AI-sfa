#!/usr/bin/env python3
"""이펙트 프레임을 '그림 과정' 층으로 분해한다(AGENTS.md 이펙트 그리기 원칙·그림 과정 그대로 그리기).

층 순서(아래 → 위): 밑색(불투명 채우기 + 같은 색 외곽선) → 명암(반투명 채우기 여러 겹) → 선(어두운 선·밝은 선, 곡선 획).
모든 경계와 선은 포물선 조각(2차 베지어, SFA TypeId 3)이다. 조각 수 상한은 두지 않는다.

1. 선: 회색조 블랙햇(닫힘 - 원본)으로 '주변보다 어두운 가는 선'을 찾고 중심선을 포물선 조각으로 맞춘다(굵기·획별 색 포함).
2. 밑색: 선을 지운(inpaint) 뒤 평활한 그림을 Lab k-평균으로 묶고, 반투명 덮기로 설명되는 덩어리를 한 밑색으로 합친다.
   묶는 기준: 덩어리 색이 '밑색 + 흰색/어두운 반투명 덮기'로 설명될 때(Lab ΔE < MERGE_DE). 밑색 = 묶음에서 가장 넓은 덩어리의 색.
3. 명암: 밑색 B에서 실제 색 C로 가는 정도를 알파로 본다. 밝은 쪽은 흰색 S, 어두운 쪽은 검정 S로
   a = ((C-B)·(S-B)) / |S-B|². 알파를 단계(LEVELS)로 잘라 '알파 ≥ 단계'인 영역을 겹친다.
   바깥(넓고 옅게) → 안쪽(좁고 진하게) 순서이며, n번째 겹의 알파는 누적 알파가 단계값이 되도록 1-(1-ℓn)/(1-ℓn-1).
4. 검증: 층을 다시 그려 원본과 Lab ΔE(평균·95분위)를 낸다.

원본 프레임·추출한 형태는 저장소에 넣지 않는다. 이 도구와 통계만 둔다.
사용: python tools/effect_layers.py <영상> <프레임번호> <출력.json> [--k 8] [--tol 1.0] [--png 비교.png]
"""
import argparse
import json
import math
import os
import sys

import cv2
import numpy as np
from skimage.morphology import skeletonize

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from effect_vectorize import fit, outline_mask, read_frame, trace  # noqa: E402

# 명암 단계 14개(2026-10-22, 이펙트 5장면 평균 ΔE 5.43 → 4.46, 조각 약 2배): 7단계는 그라데이션이 계단처럼 끊겼다
LEVELS = [0.06, 0.12, 0.18, 0.25, 0.32, 0.4, 0.48, 0.55, 0.62, 0.7, 0.78, 0.85, 0.92, 0.97]
LIGHT_KS = (7,)  # 밝은 선 찾는 틀 크기(px). 15px 추가는 표본 4장에서 개선 없음(번개 포함)
MERGE_DE = 5.0  # (2026-10-22 8 → 5: 폭발 ΔE 11.8 → 10.7, 바탕과 비슷한 밝은 구름이 바탕에 묶이던 것 완화)
# 반투명 덮기로 설명되는 색 차이 허용(Lab ΔE). BGR 거리는 갈색을 흰색의 어두운 명암으로 잘못 묶었다
DARK_MAX = 140  # 어두운 선으로 볼 최대 밝기
MERGE_A = 0.6  # 밑색 묶기에서 덮개(흰·검정) 알파 상한
SEAM = 2  # 밑색 채우기에 같은 색 외곽선(px)을 더해 이웃 영역 사이 틈을 막는다(SFA: 채우기 + 같은 색 선)


def line_layer(img, tol, thr=28, min_len=6, light=False, dark_max=None, valid=None):
    """light=False: 주변보다 어두운 가는 선(블랙햇). light=True: 주변보다 밝은 가는 선(톱햇, 불꽃 속 잔결 등)."""
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    op = cv2.MORPH_TOPHAT if light else cv2.MORPH_BLACKHAT
    # 어두운 선 15px는 넓은 그림자를 선으로 잡았다. 밝은 선 틀 크기는 LIGHT_KS
    ks = LIGHT_KS if light else (7,)
    bh = np.max([cv2.morphologyEx(g, op, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))) for k in ks], 0)
    m = ((bh > thr) & ((g > 110) if light else (g < (DARK_MAX if dark_max is None else dark_max)))).astype(np.uint8)
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
    if valid is not None:
        # 마스크 경계 3px 안쪽은 선으로 보지 않는다(이펙트와 바깥의 경계가 가는 밝은/어두운 선으로 잡혀 테두리가 생겼다)
        m &= cv2.erode(valid, np.ones((7, 7), np.uint8))
    segs = mask_strokes(img, m, tol, min_len)
    color = np.median(img[m > 0], 0).tolist() if m.any() else [0, 0, 0]
    return m, segs, color


def mask_strokes(img, m, tol=1.0, min_len=6):
    """가는 마스크 m(0/1) → 뼈대를 따라 2차 베지어 획 [x0,y0,cx,cy,x1,y1,굵기,B,G,R](굵기 = 거리변환×2, 색 = 지나는 자리 원본 중앙값)."""
    dist = cv2.distanceTransform(m, cv2.DIST_L2, 3)
    segs = []
    for path in trace(skeletonize(m.astype(bool))):
        if len(path) < min_len:
            continue
        out = []
        fit([(x, y) for y, x in path], tol, out)
        for a, c, b in out:
            n = max(3, int(math.dist(a, b)))
            ws = [dist[int(round(a[1] + (b[1] - a[1]) * s)), int(round(a[0] + (b[0] - a[0]) * s))] for s in np.linspace(0, 1, n)]
            # 획마다 지나는 자리의 원본 색(BGR 중앙값). 한 층 전체에 색 하나를 쓰면 불 속 밝은 선이 덤불 초록으로 칠해졌다
            P = curve([*a, *c, *b], max(3, n))
            cols = img[np.clip(np.round(P[:, 1]).astype(int), 0, img.shape[0] - 1), np.clip(np.round(P[:, 0]).astype(int), 0, img.shape[1] - 1)]
            segs.append([*map(float, a), *map(float, c), *map(float, b), max(1.0, 2 * float(np.median(ws))),
                         *np.median(cols, 0).round(1).tolist()])
    return segs


def join_paths(paths, max_turn=60, look=6):
    """뼈대 조각을 갈림길에서 가장 곧게 이어지는 짝끼리 붙인다. 갈림길마다 획이 끊겨 선화가 점선이 됐다(2026-10-25 광사)."""
    paths = [list(p) for p in paths if len(p) >= 2]
    while True:
        ends = {}
        for i, p in enumerate(paths):
            ends.setdefault(p[0], []).append((i, 0))
            ends.setdefault(p[-1], []).append((i, 1))
        best = None
        for node, lst in ends.items():
            for a in range(len(lst)):
                for b in range(a + 1, len(lst)):
                    (i, ei), (j, ej) = lst[a], lst[b]
                    if i == j:
                        continue
                    pi = paths[i] if ei == 1 else paths[i][::-1]   # node에서 끝나게
                    pj = paths[j] if ej == 0 else paths[j][::-1]   # node에서 시작하게
                    u = np.subtract(pi[-1], pi[max(0, len(pi) - 1 - look)])
                    v = np.subtract(pj[min(len(pj) - 1, look)], pj[0])
                    nu, nv = np.linalg.norm(u), np.linalg.norm(v)
                    if nu == 0 or nv == 0:
                        continue
                    turn = math.degrees(math.acos(np.clip(np.dot(u, v) / (nu * nv), -1, 1)))
                    if turn <= max_turn and (best is None or turn < best[0]):
                        best = (turn, i, j, pi, pj)
        if best is None:
            return paths
        _, i, j, pi, pj = best
        paths = [p for k, p in enumerate(paths) if k not in (i, j)] + [pi + pj[1:]]


def joined_strokes(img, m, tol=1.5, min_len=3, sigma=2.0, dark=None, wrange=(0.8, 3.2), taper=0.55):
    """가는 마스크 → 갈림길을 이어 붙인 긴 획(2차 베지어 [x0,y0,cx,cy,x1,y1,굵기,B,G,R]). 점을 가우스로 다듬어 곡선 하나가 길게 덮게."""
    dist = cv2.distanceTransform(m, cv2.DIST_L2, 3)
    segs = []
    for path in join_paths(trace(skeletonize(m.astype(bool)))):
        if len(path) < min_len:
            continue
        P = np.array([(x, y) for y, x in path], float)
        if sigma > 0 and len(P) > 4:
            r = int(3 * sigma)
            w = np.exp(-0.5 * (np.arange(-r, r + 1) / sigma) ** 2)
            Q = np.pad(P, ((r, r), (0, 0)), mode="edge")
            P = np.stack([np.convolve(Q[:, 0], w / w.sum(), "valid"), np.convolve(Q[:, 1], w / w.sum(), "valid")], 1)
            P[0], P[-1] = path[0][::-1], path[-1][::-1]  # 끝점은 그대로(이웃 선과 맞물림)
        out = []
        fit([tuple(p) for p in P], tol, out)
        for si, (a, c, b) in enumerate(out):
            C = curve([*a, *c, *b], max(3, int(math.dist(a, b))))
            yi = np.clip(np.round(C[:, 1]).astype(int), 0, img.shape[0] - 1)
            xi = np.clip(np.round(C[:, 0]).astype(int), 0, img.shape[1] - 1)
            if dark is None:
                wd = max(1.0, 2 * float(np.median(dist[yi, xi])) - 0.5)  # 거리변환 중심값×2는 실제보다 약 1px 굵었다
            else:
                # 굵기 바리에이션(2026-10-25 사용자): 선화 지도에서 진한 선(외곽·턱선)은 굵게, 옅은 선(머리카락 결)은 가늘게
                v = float(np.median(dark[yi, xi]))
                k = np.clip((215 - v) / 185, 0, 1) ** 0.8
                wd = wrange[0] + (wrange[1] - wrange[0]) * k
                if len(out) > 1 and si in (0, len(out) - 1):
                    wd *= taper  # 선의 양 끝 곡선은 가늘게(끝이 빠지는 느낌)
            segs.append([*map(float, a), *map(float, c), *map(float, b), wd, *np.median(img[yi, xi], 0).round(1).tolist()])
    return segs


def brush_shapes(img, m, tol=1.5, min_len=4, sigma=2.0, taper=0.25, width_scale=1.0):
    """가는 마스크 → 붓선 면: 가운데 줄기(갈림길 이음) 양옆으로 굵기만큼 벌린 왼쪽·오른쪽 변을 긴 곡선으로 맞추고 양 끝을 모아 닫는다.
    2026-10-25 사용자 시연: 곡선 4개 + 채우기로 끝이 빠지는 붓선 하나. 획(굵기 하나)은 끝이 안 빠지고, 픽셀 윤곽 면은 점이 빼곡했다.
    반환: [(shape, BGR)] — shape = {'hole': False, 'segs': [...]} (선마다 색 하나)."""
    dist = cv2.distanceTransform(m, cv2.DIST_L2, 3)
    out = []
    for path in join_paths(trace(skeletonize(m.astype(bool)))):
        if len(path) < min_len:
            continue
        P = np.array([(x, y) for y, x in path], float)
        if sigma > 0 and len(P) > 4:
            r = int(3 * sigma)
            w = np.exp(-0.5 * (np.arange(-r, r + 1) / sigma) ** 2); w /= w.sum()
            Q = np.pad(P, ((r, r), (0, 0)), mode="edge")
            P = np.stack([np.convolve(Q[:, 0], w, "valid"), np.convolve(Q[:, 1], w, "valid")], 1)
        yi = np.clip(np.round(P[:, 1]).astype(int), 0, img.shape[0] - 1)
        xi = np.clip(np.round(P[:, 0]).astype(int), 0, img.shape[1] - 1)
        hw = np.maximum(dist[yi, xi] - 0.25, 0.35) * width_scale  # 반폭(px). 거리변환 중심값은 약 0.5px 크다
        hw = np.convolve(np.pad(hw, 3, mode="edge"), np.ones(7) / 7, "valid")
        n = len(P)
        t = np.linspace(0, 1, n)
        k = max(taper, 1e-3)
        hw = hw * np.clip(np.minimum(t, 1 - t) / k, 0, 1) ** 0.6  # 양 끝으로 갈수록 가늘게(뾰족한 끝)
        d = np.gradient(P, axis=0)
        d /= np.maximum(np.linalg.norm(d, axis=1, keepdims=True), 1e-6)
        nrm = np.stack([-d[:, 1], d[:, 0]], 1)
        Lp, Rp = P + nrm * hw[:, None], P - nrm * hw[:, None]
        segs = []
        for side in (Lp, Rp[::-1]):
            o2 = []
            fit([tuple(p) for p in side], tol, o2)
            segs += [[*map(float, a), *map(float, c), *map(float, b)] for a, c, b in o2]
        col = np.median(img[yi, xi], 0).round(1).tolist()
        out.append(({"hole": False, "segs": segs}, col))
    return out


def base_and_shade(img, line_mask, k, tol, min_area, valid=None, shade_min=None, levels=None, shade_tol=None, sigma=0.0):
    shade_min = min_area if shade_min is None else shade_min
    shade_tol = tol if shade_tol is None else shade_tol
    clean = cv2.inpaint(img, cv2.dilate(line_mask, np.ones((3, 3), np.uint8)), 3, cv2.INPAINT_TELEA)
    smooth = cv2.bilateralFilter(clean, 7, 30, 7)
    lab = cv2.cvtColor(smooth, cv2.COLOR_BGR2LAB).reshape(-1, 3).astype(np.float32)
    cv2.setRNGSeed(0)  # k-평균 시작점 고정(실행마다 ΔE가 ±0.5 흔들렸다)
    vflat = None if valid is None else valid.reshape(-1) > 0
    sample = lab if vflat is None else lab[vflat]
    k = max(1, min(k, len(sample)))
    _, _, cent = cv2.kmeans(sample, k, None, (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.5), 3,
                            cv2.KMEANS_PP_CENTERS)
    # 색 묶음은 이펙트 영역(valid) 안 색만으로 정한다(배경 색이 섞이면 이펙트 색이 틀어졌다). 모든 픽셀은 가장 가까운 중심으로
    lab_idx = np.linalg.norm(lab[:, None, :] - cent[None], axis=2).argmin(1).astype(np.int32).reshape(img.shape[:2])
    lab_idx = cv2.medianBlur(lab_idx.astype(np.uint8), 5).astype(np.int32)
    area = np.bincount(lab_idx.ravel(), minlength=k)
    bgr = cv2.cvtColor(cent.reshape(1, -1, 3).astype(np.uint8), cv2.COLOR_LAB2BGR).reshape(-1, 3).astype(np.float32)
    # 덩어리 j가 밑색 i 위에 흰색 또는 어두운 반투명을 덮어 만들 수 있는 색이면 같은 밑색으로 묶는다(넓은 덩어리부터)
    group = -np.ones(k, int)
    for i in np.argsort(-area):
        if group[i] >= 0:
            continue
        group[i] = i
        for j in range(k):
            if group[j] >= 0:
                continue
            for S in (np.full(3, 255.0), np.zeros(3)):
                d = S - bgr[i]
                a = np.clip(np.dot(bgr[j] - bgr[i], d) / max(np.dot(d, d), 1e-6), 0, 1)
                if a > MERGE_A:  # 거의 검정·거의 흰색을 반대 밑색에 묶으면 밑색이 가장자리에 띠로 드러났다(2026-10-24 020)
                    continue
                pred = np.clip(bgr[i] + a * d, 0, 255).astype(np.uint8).reshape(1, 1, 3)
                if delta_e(pred, bgr[j].astype(np.uint8).reshape(1, 1, 3))[0, 0] < MERGE_DE:
                    group[j] = i
                    break
    gmap = group[lab_idx]
    if valid is not None:
        gmap = np.where(valid > 0, gmap, -1)  # 이펙트 밖은 그리지 않는다
    layers = []
    fimg = smooth.astype(np.float32)
    for gi in np.unique(gmap):
        if gi < 0:
            continue
        reg = (gmap == gi).astype(np.uint8)
        if reg.sum() < min_area:
            continue
        B = np.median(fimg[(lab_idx == gi)], 0)
        _, shapes = outline_mask(reg * 255, tol, min_area, sigma)
        layers.append({"kind": "base", "color": B.round(1).tolist(), "alpha": 1.0, "stroke": SEAM, "shapes": shapes})
        C = fimg[reg > 0]
        reg_out = cv2.dilate(reg, np.ones((3, 3), np.uint8))
        edge_band = reg - cv2.erode(reg, np.ones((5, 5), np.uint8))
        for sign, S in (("light", np.array([255., 255., 255.])), ("dark", np.zeros(3))):
            d = S - B
            if np.dot(d, d) < 100:
                continue
            a = np.zeros(img.shape[:2], np.float32)
            a[reg > 0] = np.clip(((C - B) @ d) / np.dot(d, d), 0, 1)
            # 정규화 흐림: 영역 밖 0과 섞이면 가장자리 알파가 낮아져 가장자리에 밑색 띠(밝은·어두운 테두리)가 생겼다(2026-10-24 020)
            a = cv2.GaussianBlur(a, (0, 0), 1.0) / np.maximum(cv2.GaussianBlur(reg.astype(np.float32), (0, 0), 1.0), 1e-3) * reg
            prev = 0.0
            for lv in (LEVELS if levels is None else levels):
                m0 = (a >= lv).astype(np.uint8)
                m = cv2.morphologyEx(m0, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
                m |= m0 & edge_band  # 영역 가장자리는 열기로 깎지 않는다(계단진 마스크 가장자리마다 밑색이 선처럼 남았다, 020)
                if m.sum() < shade_min:
                    break
                # 1px 넓혀 윤곽을 딴다: 곡선 맞춤이 윤곽을 안으로 당겨 생긴 틈으로 어두운 밑색이 테두리처럼 보였다(2026-10-24 '외곽선 현상').
                # 테두리 선으로 덮으면 반투명이 겹쳐 밝은 선이 생겨서, 면 자체를 넓힌다.
                # 밑색 이음새 선(SEAM 2px)이 영역 밖으로 1px 나가므로 명암도 영역 밖 1px까지 덮는다(안 덮으면 밑색 띠가 테두리로 보였다, 020)
                m = cv2.dilate(m, np.ones((3, 3), np.uint8)) & reg_out
                _, sh = outline_mask(m * 255, shade_tol, shade_min, sigma)
                if sh:
                    layers.append({"kind": "shade", "tone": sign, "color": S.round(1).tolist(),
                                   "alpha": round(1 - (1 - lv) / (1 - prev), 4), "level": lv, "shapes": sh})
                prev = lv
    return layers


def line_fill_layers(img, lm, tol, bands=(0, 90, 150, 256), sigma=0.0):
    """선 마스크 → 밝기 구간별 불투명 채우기 층(위에 얹힘). 구간 색 = 그 구간 선 픽셀의 중앙값."""
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    out = []
    for lo, hi in zip(bands, bands[1:]):
        m = ((lm > 0) & (g >= lo) & (g < hi)).astype(np.uint8)
        if m.sum() < 6:
            continue
        m = cv2.dilate(m, np.ones((2, 2), np.uint8)) & cv2.dilate(lm, np.ones((3, 3), np.uint8))  # 구간 사이 틈 막기
        _, shapes = outline_mask(m * 255, tol, 4, min(sigma, 1.0))  # 선은 가늘어 많이 다듬으면 끊긴다
        if shapes:
            out.append({"kind": "line", "color": np.median(img[m > 0], 0).round(1).tolist(), "alpha": 1.0, "shapes": shapes})
    return out


def fill_mask(shapes, shape):
    canvas = np.zeros(shape, np.uint8)
    for sh in shapes:
        pts = []
        for x0, y0, cx, cy, x1, y1 in sh["segs"]:
            t = np.linspace(0, 1, 10)[:, None]
            pts.append((1 - t) ** 2 * [x0, y0] + 2 * t * (1 - t) * [cx, cy] + t ** 2 * [x1, y1])
        if pts:
            layer = np.zeros(shape, np.uint8)
            cv2.fillPoly(layer, [np.round(np.vstack(pts)).astype(np.int32)], 1)
            canvas ^= layer  # 짝홀 규칙(구멍)
    return canvas


def curve(seg, n=10):
    x0, y0, cx, cy, x1, y1 = seg[:6]
    t = np.linspace(0, 1, n)[:, None]
    return (1 - t) ** 2 * [x0, y0] + 2 * t * (1 - t) * [cx, cy] + t ** 2 * [x1, y1]


def render(doc, shape):
    out = np.zeros((*shape, 3), np.float32)
    for L in doc["layers"]:
        m = fill_mask(L["shapes"], shape)
        if L.get("stroke"):
            for sh in L["shapes"]:
                if sh["segs"]:
                    cv2.polylines(m, [np.round(np.vstack([curve(g) for g in sh["segs"]])).astype(np.int32)], True, 1,
                                  L["stroke"])
        m = m.astype(np.float32)[..., None] * L["alpha"]
        out = out * (1 - m) + np.array(L["color"], np.float32) * m
    for ln in doc["lines"]:
        for seg in ln["segs"]:
            col = seg[7:10] if len(seg) >= 10 else ln["color"]  # 획별 색(없으면 층 색)
            cv2.polylines(out, [np.round(curve(seg, 12)).astype(np.int32)], False, col, max(1, round(seg[6])),
                          cv2.LINE_AA)
    return np.clip(out, 0, 255).astype(np.uint8)


def delta_e(a, b):
    la = cv2.cvtColor(a, cv2.COLOR_BGR2LAB).astype(np.float32)
    lb = cv2.cvtColor(b, cv2.COLOR_BGR2LAB).astype(np.float32)
    la[..., 0] *= 100 / 255
    lb[..., 0] *= 100 / 255
    la[..., 1:] -= 128
    lb[..., 1:] -= 128
    return np.linalg.norm(la - lb, axis=2)


def decompose(img, k=8, tol=1.0, min_area=20, valid=None, shade_min=None, levels=None, shade_tol=None, line_dark=None,
              line_fill=False, sigma=0.0, line_join=False, line_brush=False, lines_only=False, line_map=None):
    """shade_tol: 명암 윤곽만 곡선 오차를 따로(2026-10-25 최적화: 밑색·선까지 2px로 하니 인물 윤곽이 자글자글해짐).
    line_dark: 어두운 선으로 볼 최대 밝기(기본 DARK_MAX 140). 흰 머리 위 회색 선(150–200)이 끊겨 점선이 되던 인물 그림은 200.
    line_fill: 어두운 선을 획 대신 선 모양 그대로의 채우기 면으로(밝기 3단계 색). 획은 갈림길마다 끊기고 굵기가 부풀어
    인물 선화가 점선·덩어리가 됐다(2026-10-25 광사 시험). 면은 붓선 굵기 변화도 그대로 남는다.
    valid(0/1 마스크)가 있으면 그 안만 분해한다(이펙트 분리 결과, tools/kaggle_fx_worker.py). ΔE도 그 안에서만 잰다."""
    if valid is not None and valid.sum() < min_area:  # 이펙트가 없는 프레임: 빈 그림
        doc = {"size": list(img.shape[:2]), "layers": [], "lines": [],
               "stats": {"base": 0, "shade": 0, "line_segs": 0, "light_segs": 0, "segs": 0, "dE_mean": 0.0, "dE_p95": 0.0}}
        return doc, np.zeros_like(img)
    lm, lsegs, lcol = line_layer(img, tol, dark_max=line_dark, valid=valid)
    if line_map is not None:
        # 학습된 선화 추출기 결과(흰 바탕 검은 선, 0–255). 규칙(가는 어두운 선)은 굵은 테·칠한 눈·색 경계를 놓쳤다(2026-10-25 광사:
        # 선글라스·눈·입이 통째로 빠짐) → ControlNet lineart(sk_model) 선화를 그대로 쓴다
        lm = (line_map < 200).astype(np.uint8)  # 열기(2x2)는 1–2px 선을 지워 선화가 거의 사라졌다 — 쓰지 않는다
        lsegs = []
    hm, hsegs, hcol = line_layer(img, tol, light=True, valid=valid)
    # lines_only: 채색 없이 선화만(2026-10-25 사용자: "채색하지 말고 테두리 윤곽을 따라 그려봐")
    layers = [] if lines_only else base_and_shade(img, lm | hm, k, tol, min_area, valid, shade_min, levels, shade_tol, sigma)
    if lines_only:
        hsegs = []
    if line_join and line_map is None:  # 어두운 선: 갈림길을 이은 긴 획(면보다 곡선 수 절반 — 면은 양쪽 테두리가 생긴다)
        lsegs = joined_strokes(img, lm, max(tol, 1.5), sigma=max(sigma, 2.0) if sigma else 2.0)
    if line_map is not None and line_join:
        # 선화 지도 → 가운데 줄기 긴 획(선 객체 = 곡선 + 굵기). 사용자 시연: 어깨선 하나 = 곡선 2개짜리 선. 채우기 면은 양쪽 테두리마다
        # 점이 빼곡해 앱에서 지저분했다(2026-10-25)
        src = cv2.cvtColor(line_map, cv2.COLOR_GRAY2BGR)
        lsegs = [g[:7] + [v * 0.35 for v in g[7:10]] for g in joined_strokes(src, lm, max(tol, 2.5), min_len=8, sigma=max(sigma, 3.0),
                                                                              dark=cv2.erode(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), np.ones((3, 3), np.uint8)),
                                                                              wrange=(0.6, 4.5))]  # 진하기는 원본 그림에서(외곽 검정 / 머리 결 회색). 선화 지도는 선 진하기가 고르다
    elif line_map is not None and not line_brush:
        # 선화 지도 → potrace 윤곽 채우기(사용자: 잡프로그램만도 못하다 → 표준 벡터화 도구로). 선 색 하나(진한 회흑)
        from potrace_lines import trace_shapes
        layers.append({"kind": "line", "color": [30.0, 30.0, 30.0], "alpha": 1.0, "shapes": trace_shapes(line_map)})
        lsegs = []
    if line_brush:  # 어두운 선: 끝이 빠지는 붓선 면(선마다 FR 하나, 색 하나)
        src = img if line_map is None else cv2.cvtColor(line_map, cv2.COLOR_GRAY2BGR)  # 선화 지도면 선 색도 거기서(검정~회색)
        for sh, col in brush_shapes(src, lm, max(tol, 1.5), sigma=1.2 if line_map is not None else 2.0, taper=0.15):
            if line_map is not None:
                col = (np.array(col) * 0.35).round(1).tolist()  # 선화 지도 선은 옅은 회색(약 120) → 원본 선처럼 진하게
            layers.append({"kind": "line", "color": col, "alpha": 1.0, "shapes": [sh]})
        lsegs = []
    if line_fill:
        layers += line_fill_layers(img, lm, tol, sigma=sigma)
        lsegs = []
    doc = {"size": list(img.shape[:2]), "layers": layers,
           "lines": [{"tone": "dark", "color": lcol, "segs": lsegs}, {"tone": "light", "color": hcol, "segs": hsegs}]}
    rec = render(doc, img.shape[:2])
    de = delta_e(img, rec)
    if valid is not None:
        de = de[valid > 0] if valid.any() else np.zeros(1)
    nseg = sum(len(s["segs"]) for L in layers for s in L["shapes"]) + len(lsegs) + len(hsegs)
    doc["stats"] = {"base": sum(L["kind"] == "base" for L in layers), "shade": sum(L["kind"] == "shade" for L in layers),
                    "line_segs": len(lsegs), "light_segs": len(hsegs), "segs": nseg, "dE_mean": round(float(de.mean()), 2),
                    "dE_p95": round(float(np.percentile(de, 95)), 2)}
    return doc, rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("frame", type=int)
    ap.add_argument("out")
    ap.add_argument("--k", type=int, default=8)
    ap.add_argument("--tol", type=float, default=1.0)
    ap.add_argument("--png")
    a = ap.parse_args()
    img = read_frame(a.video, a.frame)
    doc, rec = decompose(img, a.k, a.tol)
    json.dump(doc, open(a.out, "w"))
    print(json.dumps(doc["stats"], ensure_ascii=False))
    if a.png:
        cv2.imwrite(a.png, np.hstack([img, rec]))


if __name__ == "__main__":
    main()
