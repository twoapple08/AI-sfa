#!/usr/bin/env python3
"""이펙트 프레임을 '그림 과정' 층으로 분해한다(AGENTS.md 이펙트 그리기 원칙·그림 과정 그대로 그리기).

층 순서(아래 → 위): 밑색(불투명 채우기 + 같은 색 외곽선) → 명암(반투명 채우기 여러 겹) → 선(어두운 선·밝은 선, 곡선 획).
모든 경계와 선은 포물선 조각(2차 베지어, SFA TypeId 3)이다. 조각 수 상한은 두지 않는다.

1. 선: 회색조 블랙햇(닫힘 - 원본)으로 '주변보다 어두운 가는 선'을 찾고 중심선을 포물선 조각으로 맞춘다(굵기 포함).
2. 밑색: 선을 지운(inpaint) 뒤 평활한 그림을 Lab k-평균으로 묶고, 반투명 덮기로 설명되는 덩어리를 한 밑색으로 합친다.
   묶는 기준: 덩어리 색이 '밑색 + 흰색/어두운 반투명 덮기'로 설명될 때(Lab ΔE < MERGE_DE). 밑색 = 묶음에서 가장 넓은 덩어리의 색.
3. 명암: 밑색 B에서 실제 색 C로 가는 정도를 알파로 본다. 밝은 쪽은 흰색 쪽 S, 어두운 쪽은 B×0.25 쪽 S로
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

LEVELS = [0.12, 0.25, 0.4, 0.55, 0.7, 0.85]
MERGE_DE = 8.0  # 반투명 덮기로 설명되는 색 차이 허용(Lab ΔE). BGR 거리는 갈색을 흰색의 어두운 명암으로 잘못 묶었다
SEAM = 2  # 밑색 채우기에 같은 색 외곽선(px)을 더해 이웃 영역 사이 틈을 막는다(SFA: 채우기 + 같은 색 선)


def line_layer(img, tol, thr=28, min_len=6, light=False):
    """light=False: 주변보다 어두운 가는 선(블랙햇). light=True: 주변보다 밝은 가는 선(톱햇, 불꽃 속 잔결 등)."""
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    op = cv2.MORPH_TOPHAT if light else cv2.MORPH_BLACKHAT
    bh = cv2.morphologyEx(g, op, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7)))
    m = ((bh > thr) & ((g > 110) if light else (g < 140))).astype(np.uint8)
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
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
            segs.append([*map(float, a), *map(float, c), *map(float, b), max(1.0, 2 * float(np.median(ws)))])
    color = np.median(img[m > 0], 0).tolist() if m.any() else [0, 0, 0]
    return m, segs, color


def base_and_shade(img, line_mask, k, tol, min_area):
    clean = cv2.inpaint(img, cv2.dilate(line_mask, np.ones((3, 3), np.uint8)), 3, cv2.INPAINT_TELEA)
    smooth = cv2.bilateralFilter(clean, 7, 30, 7)
    lab = cv2.cvtColor(smooth, cv2.COLOR_BGR2LAB).reshape(-1, 3).astype(np.float32)
    _, lab_idx, cent = cv2.kmeans(lab, k, None, (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.5), 3,
                                  cv2.KMEANS_PP_CENTERS)
    lab_idx = lab_idx.reshape(img.shape[:2])
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
            for S in (np.full(3, 255.0), bgr[i] * 0.25):
                d = S - bgr[i]
                a = np.clip(np.dot(bgr[j] - bgr[i], d) / max(np.dot(d, d), 1e-6), 0, 1)
                pred = np.clip(bgr[i] + a * d, 0, 255).astype(np.uint8).reshape(1, 1, 3)
                if delta_e(pred, bgr[j].astype(np.uint8).reshape(1, 1, 3))[0, 0] < MERGE_DE:
                    group[j] = i
                    break
    gmap = group[lab_idx]
    layers = []
    fimg = smooth.astype(np.float32)
    for gi in np.unique(gmap):
        reg = (gmap == gi).astype(np.uint8)
        if reg.sum() < min_area:
            continue
        B = np.median(fimg[(lab_idx == gi)], 0)
        _, shapes = outline_mask(reg * 255, tol, min_area)
        layers.append({"kind": "base", "color": B.round(1).tolist(), "alpha": 1.0, "stroke": SEAM, "shapes": shapes})
        C = fimg[reg > 0]
        for sign, S in (("light", np.array([255., 255., 255.])), ("dark", B * 0.25)):
            d = S - B
            if np.dot(d, d) < 100:
                continue
            a = np.zeros(img.shape[:2], np.float32)
            a[reg > 0] = np.clip(((C - B) @ d) / np.dot(d, d), 0, 1)
            a = cv2.GaussianBlur(a, (0, 0), 1.0) * reg
            prev = 0.0
            for lv in LEVELS:
                m = (a >= lv).astype(np.uint8)
                m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
                if m.sum() < min_area:
                    break
                _, sh = outline_mask(m * 255, tol, min_area)
                if sh:
                    layers.append({"kind": "shade", "tone": sign, "color": S.round(1).tolist(),
                                   "alpha": round(1 - (1 - lv) / (1 - prev), 4), "level": lv, "shapes": sh})
                prev = lv
    return layers


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
            cv2.polylines(out, [np.round(curve(seg, 12)).astype(np.int32)], False, ln["color"], max(1, round(seg[6])),
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


def decompose(img, k=8, tol=1.0, min_area=20):
    lm, lsegs, lcol = line_layer(img, tol)
    hm, hsegs, hcol = line_layer(img, tol, light=True)
    layers = base_and_shade(img, lm | hm, k, tol, min_area)
    doc = {"size": list(img.shape[:2]), "layers": layers,
           "lines": [{"tone": "dark", "color": lcol, "segs": lsegs}, {"tone": "light", "color": hcol, "segs": hsegs}]}
    rec = render(doc, img.shape[:2])
    de = delta_e(img, rec)
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
