#!/usr/bin/env python3
"""3D 장면 속 이펙트(조립기용): GPT 판정을 거친 나카무라 이펙트 형태 사전(층 형태)을 3D 위치에 놓고 카메라로 찍어 채우기로 낸다.

- 형태: tools/fx_shapes.py 사전 + tools/fx_gen.load_layered(판정 csv) — 원·직선 대용 없음(AGENTS 이펙트 원칙).
- 놓는 방식 3가지:
  billboard(카메라를 보는 판: 부유 파편), ground(땅에 눕힘: 균열 — 점마다 원근 투영), upright(땅에서 세움: 가시 — 긴 축을 위로).
- 색: 비채색이면 형태의 밝기만 남겨 회색으로, tint를 주면 그 색으로(밝기 유지). 층 알파(반투명 명암)는 그대로.
형태 사전은 다른 작가 그림 유래라 Drive·서버에만 있다(저장소에는 이 도구만).
"""
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import motion_to_sfa as M  # noqa: E402
from fx_gen import axis, load_layered  # noqa: E402


class Shapes:
    def __init__(self, shapes_txt, approved_csv):
        self.d = load_layered(shapes_txt, approved_csv)

    def pick(self, kind, i):
        L = self.d.get(kind) or []
        return L[i % len(L)] if L else None


def recolor(col, tint, gray):
    b, g, r = col
    lum = 0.114 * b + 0.587 * g + 0.299 * r
    if tint is not None:
        k = 0.35 + 0.65 * lum / 255
        return tuple(int(min(255, c * k)) for c in tint)
    if gray:
        v = int(lum)
        return (v, v, v)
    return (b, g, r)


def to_fills(layers, mapper, alpha=1.0, tint=None, gray=True, layer=1):
    """층 형태 → [("FILL", ARGB, 레이어, 윤곽들)]. mapper: (N,2) 형태 좌표(중심 원점·면적 제곱근 1) → (N,2) 화면 px 또는 None(카메라 뒤)."""
    out = []
    for col, a, cs in layers:
        contours = []
        outer = []
        for hole, segs in cs:
            P = mapper(np.asarray(segs, float).reshape(-1, 2))
            if P is None or not np.isfinite(P).all() or np.abs(P).max() > 1e5:
                continue
            sg = P.reshape(-1, 6).tolist()
            (outer if not hole else contours).append(sg)
        if not outer:
            continue
        c = recolor(col, tint, gray)
        aa = max(0.0, min(1.0, a * alpha))
        if aa < 0.02:
            continue
        argb = (int(round(aa * 255)) << 24) | (c[2] << 16) | (c[1] << 8) | c[0]  # BGR → ARGB
        argb = argb - (1 << 32) if argb >= 1 << 31 else argb
        for o in outer:  # 바깥 윤곽마다 하나(구멍은 첫 바깥에만 — 형태 사전은 대개 바깥 1개)
            out.append(("FILL", argb, layer, [o] + (contours if o is outer[0] else [])))
    return out


def billboard(layers, center, size, rot, cam, **kw):
    eye, at, fov = cam
    P2, Z, s = M.project(np.asarray([center], float), eye, at, fov)
    if Z[0] < 0.3:
        return []
    px = size * s / Z[0]
    c, n = math.cos(rot), math.sin(rot)
    R = np.array([[c, -n], [n, c]])
    return to_fills(layers, lambda P: (P @ R.T) * px + P2[0], **kw)


def ground(layers, center, size, rot, cam, **kw):
    eye, at, fov = cam
    c, n = math.cos(rot), math.sin(rot)

    def mp(P):
        Q = P @ np.array([[c, -n], [n, c]]).T * size
        W3 = np.stack([center[0] + Q[:, 0], np.full(len(Q), 0.01), center[2] + Q[:, 1]], 1)
        P2, Z, _ = M.project(W3, eye, at, fov)
        return None if (Z < 0.3).any() else P2
    return to_fills(layers, mp, **kw)


def upright(layers, base, height, cam, **kw):
    """긴 축을 위로 세운 판(카메라를 보는 방향), 아래 끝을 base에 둔다."""
    eye, at, fov = cam
    ang = axis(layers[0][2])
    c, n = math.cos(-ang + math.pi / 2), math.sin(-ang + math.pi / 2)
    R = np.array([[c, -n], [n, c]])
    fwd = (at - eye) * [1, 0, 1]
    fwd /= np.linalg.norm(fwd) + 1e-9
    side = np.cross(fwd, [0, 1, 0])

    def mp(P):
        Q = P @ R.T
        Q = Q - [0, Q[:, 1].max()]          # 아래 끝(화면 아래 = +y)을 0에
        Q = Q / max(1e-6, -Q[:, 1].min()) * height   # 높이를 height(미터)로
        W3 = base + np.outer(Q[:, 0], side) + np.outer(-Q[:, 1], [0, 1, 0])
        P2, Z, _ = M.project(W3, eye, at, fov)
        return None if (Z < 0.3).any() else P2
    return to_fills(layers, mp, **kw)
