#!/usr/bin/env python3
"""흑백 선화 → potrace 윤곽 → SFA 채우기 모양(2차 베지어) (2026-10-25).

사용자: "어디 잡프로그램 시켜도 너보다는 잘 뽑겠다". 직접 짠 뼈대 붓선(effect_layers.brush_shapes)은 굵은 선을 두 줄로 만들고
잔선을 남겼다. potrace(일러스트레이터 이미지 추적·Inkscape가 쓰는 방식)는 흑백 그림의 테두리를 적은 수의 매끄러운 3차 곡선으로
바꾼다 — 사용자 시연처럼 '곡선 몇 개로 둘러싼 채우기 면'. SFA는 2차 곡선(TypeId 3)이라 3차 하나를 반으로 갈라 2차 두 개로 바꾼다.
반환 모양은 effect_vectorize.outline_mask와 같은 꼴({'hole','segs','cid','parent'})이라 effect_clip_sfa가 그대로 FR로 쓴다.
필요: pip install potracer (순수 파이썬 potrace)
"""
import cv2
import numpy as np
import potrace


def pt(v):
    """potracer 점(_Point: .x .y) 또는 순서쌍 → numpy"""
    return np.array([v.x, v.y], float) if hasattr(v, "x") else np.asarray(v, float)


def cubic_to_quads(p0, c1, c2, p3):
    """3차 베지어 → 2차 두 개(t=0.5에서 가름, 각 반쪽의 2차 제어점 = (3(c1+c2) - (p0+p3)) / 4)."""
    p0, c1, c2, p3 = (pt(v) for v in (p0, c1, c2, p3))
    m01, m12, m23 = (p0 + c1) / 2, (c1 + c2) / 2, (c2 + p3) / 2
    a, b = (m01 + m12) / 2, (m12 + m23) / 2
    mid = (a + b) / 2
    out = []
    for q0, q1, q2, q3 in ((p0, m01, a, mid), (mid, b, m23, p3)):
        c = (3 * (q1 + q2) - (q0 + q3)) / 4
        out.append([*q0, *c, *q3])
    return out


def trace_shapes(line_map, thr=200, turdsize=4, alphamax=1.0, opttolerance=0.4):
    """line_map: 흰 바탕 검은 선(0–255). thr보다 어두운 곳이 선. turdsize 이하 넓이 점은 버림.
    alphamax: 모서리 판단(클수록 매끄럽게), opttolerance: 곡선 합치기 허용(클수록 곡선 수 적음)."""
    bm = potrace.Bitmap(line_map >= thr)  # True = 흰 바탕 → 내부에서 뒤집어 선을 딴다
    path = bm.trace(turdsize=turdsize, alphamax=alphamax, opticurve=True, opttolerance=opttolerance)
    curves = []
    for cv in path:
        segs, prev = [], pt(cv.start_point)
        for s in cv.segments:
            end = pt(s.end_point)
            if s.is_corner:
                c = pt(s.c)
                segs.append([*prev, *((prev + c) / 2), *c])
                segs.append([*c, *((c + end) / 2), *end])
            else:
                segs += cubic_to_quads(prev, s.c1, s.c2, end)
            prev = end
        t = np.linspace(0, 1, 8, endpoint=False)[:, None]  # 곡선을 촘촘히 펴서 포함 판정(조절점 꺾은선은 곡선 안쪽을 잘라 구멍을 놓쳤다)
        poly = np.vstack([(1 - t) ** 2 * g[0:2] + 2 * t * (1 - t) * np.array(g[2:4]) + t ** 2 * np.array(g[4:6]) for g in segs]).astype(np.float32)
        sg = cv._path.sign
        curves.append((sg == "+" if isinstance(sg, str) else bool(sg), segs, poly))  # potracer는 부호를 True/False로 둔다
    # 구멍(sign '-')을 감싸는 바깥 윤곽에 붙인다(SFA 채우기 = 바깥 하나 + 그 구멍들). potracer는 트리를 주지 않아 점 포함으로 찾는다
    shapes = []
    outers = [i for i, (o, _, _) in enumerate(curves) if o]
    for i, (outer, segs, poly) in enumerate(curves):
        parent = -1
        if not outer:
            best = None
            for j in outers:
                pj = curves[j][2]
                if cv2.pointPolygonTest(pj, (float(poly[0][0]), float(poly[0][1])), False) >= 0:
                    a = abs(cv2.contourArea(pj))
                    if best is None or a < best[0]:
                        best = (a, j)
            if best is None:  # 경계에 걸친 구멍: 가장 가까운 바깥 윤곽
                d = [(-cv2.pointPolygonTest(curves[j][2], (float(poly[0][0]), float(poly[0][1])), True), j) for j in outers]
                best = min(d) if d else None
            if best is None:
                continue
            parent = best[1]
        shapes.append({"hole": not outer, "segs": segs, "cid": i, "parent": parent})
    return shapes
