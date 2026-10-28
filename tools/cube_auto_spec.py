#!/usr/bin/env python3
"""그림에서 면이 평평한 블록(유타폰 큐브 등)의 꼭짓점·면 구조를 자동으로 찾아 cube_hand_sfa.py용 구조 JSON을 만든다 (2026-10-28).

cube_hand_sfa.py는 사람이 적은 대략 구조를 먹선에 붙인다. 이 도구는 그 '대략 구조'를 그림에서 찾는다.
1. 먹선(밝기 < --ink-max)으로 나뉜 영역을 찾는다. 먹선이 끊겨 두 면이 붙었으면 영역 안 색을 두 무리로 나눠
   (Lab 중심 거리 > 40) 둘로 쪼갠다 — 그림 전체 색 무리로 나누면 명암 있는 면이 잘게 쪼개져 실패했다.
2. 면 = 그림 가장자리에 닿지 않고, 둘레(5x5 고리)의 60% 이상이 먹선인 영역. 줄무늬 바탕 같은 영역은 둘레가 먹선이 아니라 빠진다.
3. 면 윤곽을 다각형으로 줄이고(둘레 1.2%), 거의 일직선(꺾임 < 20도)·아주 짧은 변의 점은 뺀다.
4. 면 꼭짓점들을 --radius px 안에서 묶어 공유 꼭짓점으로, 꼭짓점을 공유하는 면끼리 덩어리(블록) 하나.
확인(272715 프레임 1441, 영역 625,175,800,330): 면 6개·블록 2개, 손 지정과 꼭짓점 수 같음(7·7).
작은 블록 옆면의 꺾인 점은 손 지정이 틀렸고 자동이 맞았다(확대 확인). cube_hand_sfa.py --band 3.5에서 모서리 18개 모두 먹선에 맞춤.
사용: python tools/cube_auto_spec.py <그림> <x0,y0,x1,y1> <out.json> [--vis 확인.png]
"""
import argparse
import json

import cv2
import numpy as np


def regions(c, ink, lab, min_area):
    n0, L0, st0, _ = cv2.connectedComponentsWithStats((ink == 0).astype(np.uint8), 4)
    out = []
    for k in range(1, n0):
        comp = L0 == k
        parts = [comp]
        if st0[k, 4] >= min_area:
            X = lab[comp].astype(np.float32)
            _, lb, cen = cv2.kmeans(X, 2, None, (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 0.5), 3,
                                    cv2.KMEANS_PP_CENTERS)
            if np.linalg.norm(cen[0] - cen[1]) > 40 and min((lb == 0).sum(), (lb == 1).sum()) >= min_area:
                Q = np.zeros(ink.shape, int)
                Q[comp] = lb.ravel() + 1
                parts = [cv2.morphologyEx((Q == q).astype(np.uint8), cv2.MORPH_OPEN, np.ones((3, 3), np.uint8)) > 0 for q in (1, 2)]
        for p in parts:
            nq, Lq, sq, _ = cv2.connectedComponentsWithStats(p.astype(np.uint8), 4)
            out += [(Lq == j, sq[j]) for j in range(1, nq)]
    return out


def simplify(cnt):
    poly = cv2.approxPolyDP(cnt, max(1.5, 0.012 * cv2.arcLength(cnt, True)), True).reshape(-1, 2).astype(float)
    ch = True
    while ch and len(poly) > 3:
        ch = False
        for i in range(len(poly)):
            u, v = poly[i] - poly[i - 1], poly[(i + 1) % len(poly)] - poly[i]
            ang = np.degrees(np.arccos(np.clip(u @ v / (np.linalg.norm(u) * np.linalg.norm(v) + 1e-9), -1, 1)))
            if ang < 20 or min(np.linalg.norm(u), np.linalg.norm(v)) < 2.5:
                poly = np.delete(poly, i, 0)
                ch = True
                break
    return poly


def find(img, box, ink_max=70, radius=8.0, min_area=60, ring_ink=0.6):
    x0, y0, x1, y1 = box
    c = img[y0:y1, x0:x1]
    ink = (cv2.cvtColor(c, cv2.COLOR_BGR2GRAY) < ink_max).astype(np.uint8)
    lab = cv2.cvtColor(c, cv2.COLOR_BGR2LAB).astype(float)
    faces = []
    for comp, (x, y, w, h, area) in regions(c, ink, lab, min_area):
        if area < min_area or x == 0 or y == 0 or x + w >= ink.shape[1] or y + h >= ink.shape[0]:
            continue
        m = comp.astype(np.uint8)
        ring = cv2.dilate(m, np.ones((5, 5), np.uint8)) - m
        if ink[ring > 0].mean() < ring_ink:
            continue
        cs, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        faces.append(simplify(max(cs, key=cv2.contourArea)))
    cl = []  # 꼭짓점 묶기
    for fi, f in enumerate(faces):
        for vi, p in enumerate(f):
            for C in cl:
                if np.linalg.norm(np.mean([q for *_, q in C], 0) - p) < radius:
                    C.append((fi, vi, p))
                    break
            else:
                cl.append([(fi, vi, p)])
    V = [np.mean([q for *_, q in C], 0) + [x0, y0] for C in cl]
    idx = {(fi, vi): k for k, C in enumerate(cl) for fi, vi, _ in C}
    F = []
    for fi, f in enumerate(faces):
        r = [idx[(fi, vi)] for vi in range(len(f))]
        F.append([v for i, v in enumerate(r) if v != r[i - 1]])  # 같은 꼭짓점으로 묶인 이웃 점은 하나로
    par = list(range(len(F)))

    def root(a):
        while par[a] != a:
            a = par[a]
        return a
    for i in range(len(F)):
        for j in range(i):
            if set(F[i]) & set(F[j]):
                par[root(i)] = root(j)
    groups = {}
    for i, f in enumerate(F):
        if len(f) >= 3:
            groups.setdefault(root(i), []).append(f)
    cubes = []
    for n, fs in enumerate(groups.values()):
        vs = sorted({v for f in fs for v in f})
        re = {v: i for i, v in enumerate(vs)}
        cubes.append({"name": f"auto{n}", "v": [[round(float(V[v][0]), 1), round(float(V[v][1]), 1)] for v in vs],
                      "faces": [[re[v] for v in f] for f in fs]})
    return cubes, faces


def _line_hit(p, u, q, w):
    """직선 p+su 와 q+tw 의 교점."""
    A = np.array([u, -w]).T
    s = np.linalg.solve(A, q - p)[0]
    return p + s * u


def thin_faces(img, cubes, ink_max=70, need=0.6):
    """바깥 모서리 바깥쪽에 '먹선 - 무채색 띠 - 먹선'이 이어지면 폭 1–3px의 얇은 면(두께면)으로 보고 추가한다.
    480p에서 쐐기 블록 왼쪽 두께면이 폭 약 1px라 먹선과 붙어 영역으로 잡히지 않았다(10-28 사용자 지적).
    빨간 줄무늬 바탕도 밝기는 먹선만큼 어두워 밝기만으로는 오판 → 사이 봉우리가 무채색(Lab a·b가 128 근처, 채도 < 15)이어야 한다.
    (바깥 먹선은 2px라 주황 바탕과 섞여 채도 약 24 → 두 번째 골짜기는 색을 보지 않는다. 빨간 줄무늬 사이는 채도 58)"""
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32)
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB).astype(np.float32)
    S = np.arange(-2, 9, 0.5)

    def px(a, p):
        return cv2.getRectSubPix(a, (1, 1), (float(p[0]), float(p[1]))).reshape(-1)

    def chroma(p):
        v = px(lab, p)
        return np.hypot(v[1] - 128, v[2] - 128)

    added = 0
    for c in cubes:
        V = [np.array(v, float) for v in c["v"]]
        F = c["faces"]
        own = {}
        for fi, f in enumerate(F):
            for i, j in zip(f, f[1:] + f[:1]):
                own.setdefault(tuple(sorted((i, j))), []).append(fi)
        outer = [e for e, fs in own.items() if len(fs) == 1]
        new_faces = []
        for e in outer:
            a, b = V[e[0]], V[e[1]]
            u = (b - a) / np.linalg.norm(b - a)
            n = np.array([-u[1], u[0]])
            if n @ ((a + b) / 2 - np.mean([V[k] for k in F[own[e][0]]], 0)) < 0:
                n = -n
            hits = []
            for t in np.linspace(0.15, 0.85, 11):
                q = a + (b - a) * t
                pr = np.array([px(g, q + n * s)[0] for s in S])
                mins = [i for i in range(1, len(pr) - 1) if pr[i] <= pr[i - 1] and pr[i] <= pr[i + 1] and pr[i] < ink_max]
                for i in mins:
                    js = [j for j in mins if 3 <= j - i <= 10]
                    if not js:
                        continue
                    j = js[0]
                    k = i + int(np.argmax(pr[i:j + 1]))
                    if pr[k] >= max(pr[i], pr[j]) + 10 and pr[k] < 120 and chroma(q + n * S[k]) < 15:
                        hits.append((S[i], S[j], q + n * S[k]))
                        break
            if len(hits) < need * 11:
                continue
            off = float(np.median([h[1] - h[0] for h in hits]))  # 두 먹선 중심 사이 = 얇은 면 바깥 테두리까지 거리
            # 새 꼭짓점: 평행선(off 바깥)과, 그 꼭짓점의 다른 바깥 모서리 연장선의 교점
            nv = []
            for k in e:
                other = [x for x in outer if k in x and x != e]
                p = V[k] + n * off
                if other:
                    o = other[0]
                    w = V[o[0]] - V[o[1]]
                    w /= np.linalg.norm(w)
                    if abs(w @ u) < 0.95:
                        p = _line_hit(V[k] + n * off, u, V[k], w)
                nv.append(p)
            ia, ib = len(V), len(V) + 1
            V += nv
            col = np.median([px(img.astype(np.float32), h[2]) for h in hits], 0)
            new_faces.append(([e[0], e[1], ib, ia], col))
            added += 1
        c["v"] = [[round(float(x), 1), round(float(y), 1)] for x, y in V]
        for f, col in new_faces:
            c["faces"].append(f)
            c.setdefault("face_bgr", {})[str(len(c["faces"]) - 1)] = [round(float(x)) for x in col]
    return added


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("box", help="x0,y0,x1,y1 (원본 px)")
    ap.add_argument("out")
    ap.add_argument("--ink-max", type=int, default=70)
    ap.add_argument("--radius", type=float, default=8.0, help="면마다 따로 잡힌 꼭짓점을 하나로 묶는 거리(px)")
    ap.add_argument("--thin", action="store_true", help="얇은 면(두께면) 찾기 켜기. 기본은 끔: cube_hand_sfa.py의 볼록 검사가 같은 자리를 빈틈 채움으로 더 간단히 처리했다(10-28, 오브젝트 19 vs 22)")
    ap.add_argument("--vis")
    a = ap.parse_args()
    img = cv2.imread(a.image)
    box = [int(v) for v in a.box.split(",")]
    cubes, faces = find(img, box, a.ink_max, a.radius)
    if a.thin:
        print("얇은 면 추가", thin_faces(img, cubes, a.ink_max))
    json.dump({"cubes": cubes, "ink_max": a.ink_max}, open(a.out, "w", encoding="utf-8"), ensure_ascii=False)
    for c in cubes:
        print(c["name"], "꼭짓점", len(c["v"]), "면", c["faces"])
    if a.vis:
        vis = img[box[1]:box[3], box[0]:box[2]].copy()
        for f in faces:
            cv2.polylines(vis, [np.round(f).astype(np.int32)], True, (255, 0, 0), 1)
        cv2.imwrite(a.vis, cv2.resize(vis, None, fx=4, fy=4, interpolation=cv2.INTER_NEAREST))


if __name__ == "__main__":
    main()
