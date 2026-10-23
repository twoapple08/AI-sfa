#!/usr/bin/env python3
"""기준 프롬프트 1을 '키 자세 + 타이밍'으로 직접 설계한 정답 예시(2026-10-23, 사용자 승인: "한번해봐").

AI 생성이 아니다. 생성 동작(MoMask)이 평범한 모캡이라 구도·동작의 느낌이 안 나와서, 이 장면이 도달해야 할 수준을
먼저 손으로 잡아 둔다(사용자 애니매틱 docs/storyboards/bench01_user_animatic_2026-10-23.md 시간표를 따름).
- 자세: 2D 관절 각도(골반 위치·몸통·목·팔 2마디·다리 3마디) → 순운동학. 각도 보간이라 팔다리가 호를 그린다.
- 타이밍: 키마다 이징('io' 부드럽게, 'o' 빠르게 시작해 멈춤 = 스냅, 'i', 'lin', 'h' 유지). 키 자세에서 멈추고 사이는 빠르게.
- 구도: 2D 카메라(중심·배율), 장면 전환은 컷. 섬광은 형태 사전 'flash'(원·직선 대용 금지 원칙).
사용: python tools/keyframe_bench.py <출력 폴더> [--shapes fx_shapes.txt]
"""
import argparse
import json
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import motion_to_sfa as M  # noqa: E402

F = 24
THICK = 0.0032  # figure() 굵기 단위: 몸 높이 1m가 화면 s px일 때 굵기 = THICK·s
W, H = M.W, M.H
LEN = dict(torso=0.52, neck=0.09, head=0.16, uarm=0.30, farm=0.28, thigh=0.46, shin=0.46, foot=0.12)


def d(a):
    """각도(도) → 방향. 0 = 아래, 90 = 화면 오른쪽, 180 = 위."""
    r = math.radians(a)
    return np.array([math.sin(r), -math.cos(r)])


def rot(v, a):
    r = math.radians(a)
    c, s = math.cos(r), math.sin(r)
    return np.array([c * v[0] - s * v[1], s * v[0] + c * v[1]])


BASE = dict(x=0.0, y=0.95, rot=0.0, w=1.0, T=180.0, N=0.0,
            uaL=-12.0, eaL=12.0, uaR=12.0, eaR=-12.0,
            thL=-5.0, knL=3.0, ftL=60.0, thR=5.0, knR=-3.0, ftR=-60.0,
            zL=0.0, zR=0.0, ground=True)


def P(**kw):
    p = dict(BASE)
    p.update(kw)
    return p


def fk(p):
    """자세 → 22관절 (x, y) + 깊이 표시(뒤쪽 팔다리 = 1)."""
    J = np.zeros((22, 2))
    z = np.zeros(22)
    pel = np.array([0.0, 0.0])
    chest = pel + LEN["torso"] * d(p["T"])
    sh = rot(np.array([0.17 * p["w"], 0.0]), p["T"] - 180)
    J[16], J[17] = chest - sh, chest + sh
    J[12] = chest + LEN["neck"] * d(p["T"] + p["N"])
    J[15] = J[12] + LEN["head"] * d(p["T"] + p["N"])
    for s, sgn, si in (("L", -1, 16), ("R", 1, 17)):
        e = J[si] + LEN["uarm"] * d(p["ua" + s])
        wr = e + LEN["farm"] * d(p["ua" + s] + p["ea" + s])
        J[18 if s == "L" else 19], J[20 if s == "L" else 21] = e, wr
        hip = pel + rot(np.array([0.09 * p["w"] * sgn, 0.0]), p["T"] - 180)
        k = hip + LEN["thigh"] * d(p["th" + s])
        an = k + LEN["shin"] * d(p["th" + s] + p["kn" + s])
        to = an + LEN["foot"] * d(p["th" + s] + p["kn" + s] + p["ft" + s])
        ki, ai, ti = (4, 7, 10) if s == "L" else (5, 8, 11)
        J[ki], J[ai], J[ti] = k, an, to
        for i in ((18, 20, 4, 7, 10) if s == "L" else (19, 21, 5, 8, 11)):
            z[i] = p["z" + s]
    # 전체 회전(공중제비) — 골반 기준
    if p["rot"]:
        J = np.array([rot(v, p["rot"]) for v in J])
    J += [p["x"], p["y"]]
    if p["ground"]:  # 다리·손 중 가장 낮은 점을 바닥(y=0.03)에
        low = J[[4, 5, 7, 8, 10, 11, 20, 21]][:, 1].min()
        J[:, 1] += 0.03 - low
    return J, z


EASE = {"lin": lambda u: u, "io": lambda u: u * u * (3 - 2 * u), "o": lambda u: 1 - (1 - u) ** 3,
        "i": lambda u: u ** 3, "h": lambda u: 0.0}


def lerp_pose(a, b, u):
    out = {}
    for k in a:
        if isinstance(a[k], bool):
            out[k] = b[k] if u > 0.5 else a[k]
        else:
            out[k] = a[k] + (b[k] - a[k]) * u
    return out


def track(keys, n):
    """keys: [(프레임, 자세, 이 키로 오는 이징)] → 프레임별 자세."""
    out = []
    for t in range(n):
        for (f0, p0, _), (f1, p1, e) in zip(keys, keys[1:]):
            if f0 <= t <= f1:
                u = 0.0 if f1 == f0 else (t - f0) / (f1 - f0)
                out.append(lerp_pose(p0, p1, EASE[e](u)))
                break
        else:
            out.append(dict(keys[-1][1] if t > keys[-1][0] else keys[0][1]))
    return out


# ---- 키 자세 ----
STAND = P()
TUCK = P(w=0.5, T=150, N=25, uaL=120, eaL=70, uaR=140, eaR=60, thL=120, knL=-150, thR=105, knR=-140, ground=False)
SPREAD = P(w=1.0, T=180, N=-10, uaL=-140, eaL=-10, uaR=140, eaR=10, thL=-25, knL=-10, thR=25, knR=10, ground=False)
DIVE = P(w=0.9, T=185, N=-25, uaL=-160, eaL=-5, uaR=165, eaR=5, thL=-12, knL=-35, thR=10, knR=-20, ground=False)
PRE_LAND = P(w=0.6, T=170, N=-15, uaL=-100, eaL=-20, uaR=110, eaR=20, thL=-35, knL=-40, thR=40, knR=-60, ground=False)
# 히어로 착지: 3/4 앞(오른쪽을 봄). 오른 다리 앞으로 세우고, 왼 무릎·오른 주먹이 땅
HERO = P(w=0.55, T=128, N=35, uaL=-115, eaL=-25, uaR=8, eaR=4, thL=-8, knL=-86, ftL=-70, thR=82, knR=-92, ftR=88, zL=1)
HERO_IMPACT = P(w=0.55, T=118, N=42, uaL=-125, eaL=-30, uaR=10, eaR=6, thL=-12, knL=-82, ftL=-70, thR=88, knR=-98, ftR=88, zL=1)
LOOK_UP = P(w=0.55, T=140, N=-5, uaL=-100, eaL=-30, uaR=8, eaR=4, thL=-8, knL=-86, ftL=-70, thR=82, knR=-92, ftR=88, zL=1)
PUSH = P(w=0.7, T=165, N=-5, uaL=-30, eaL=20, uaR=30, eaR=-20, thL=-10, knL=-40, thR=40, knR=-60, zL=1)
WALK_A = P(T=181, N=-4, uaL=-6, eaL=25, uaR=18, eaR=-8, thL=-7, knL=0, thR=10, knR=-35, ftR=-30, zR=1)
WALK_P = P(T=180, N=-4, uaL=-12, eaL=12, uaR=12, eaR=-12, thL=-3, knL=-8, thR=2, knR=-50, ftR=-20, zR=1)
WALK_B = P(T=179, N=-4, uaL=-18, eaL=8, uaR=6, eaR=-25, thL=-10, knL=35, ftL=30, thR=7, knR=0, zL=1)
RUN_A = P(T=181, N=-12, uaL=-20, eaL=100, uaR=35, eaR=-80, thL=-10, knL=0, thR=25, knR=-95, ftR=-40, zR=1)
RUN_B = P(T=179, N=-12, uaL=-35, eaL=80, uaR=20, eaR=-100, thL=-25, knL=95, ftL=40, thR=10, knR=0, zL=1)
# 펀치(옆모습, 오른쪽으로): 당김 → 내지름
WIND = P(w=0.35, T=168, N=8, uaL=60, eaL=110, uaR=-55, eaR=-130, thL=-28, knL=8, thR=30, knR=-25, ftR=80, ftL=80, zR=0, zL=1)
PUNCH = P(w=0.35, T=200, N=-12, uaL=-60, eaL=-60, uaR=92, eaR=0, thL=-38, knL=10, thR=42, knR=-35, ftR=80, ftL=80, zL=1)
PUNCH_OVR = P(w=0.35, T=205, N=-14, uaL=-70, eaL=-55, uaR=96, eaR=0, thL=-40, knL=12, thR=44, knR=-38, ftR=80, ftL=80, zL=1)


def shot_plan():
    """사용자 애니매틱 시간표(24fps): 하늘 1.2초 → 섬광 → 낙하(화면을 가림) → 컷 → 도시: 떨어져 착지·멈춤 → 일어섬 → 걷기 → 달리기
    → 컷: 순간이동 펀치 클로즈업 → 암전."""
    S = []
    # 1) 하늘 + 섬광 + 낙하(공중제비, 카메라 쪽으로 다가와 화면을 가림)
    fall = track([(0, TUCK, "lin"), (10, SPREAD, "io"), (20, TUCK, "io"), (30, SPREAD, "io"), (38, DIVE, "io"), (46, PRE_LAND, "io")], 47)
    for k, p in enumerate(fall):
        p = dict(p)
        p["rot"] = 540 * (1 - (k / 46)) ** 1.5  # 회전하며 내려오다 마지막엔 바로 선다
        p["x"] = p["y"] = 0.0
        S.append(("fall", p, k))
    # 2) 도시: 위에서 떨어져 들어와 히어로 착지 → 멈춤 → 고개 듦 → 일어섬
    land = track([(0, PRE_LAND, "lin"), (4, HERO_IMPACT, "i"), (6, HERO, "o"), (18, HERO, "h"), (24, LOOK_UP, "io"), (30, LOOK_UP, "h"),
                  (40, PUSH, "io"), (48, STAND, "o"), (52, STAND, "h")], 53)
    for k, p in enumerate(land):
        p = dict(p)
        if k < 4:  # 화면 위 밖(6m)에서 4프레임 만에 떨어짐
            p["ground"] = False
            p["y"] = 0.95 + 6.0 * (1 - (k / 4) ** 2)
        S.append(("city", p, k))
    # 3) 걷기(천천히 → 유지) → 빨리 걷기 → 달리기, 카메라 쪽으로(크기 일정)
    cyc = [WALK_A, WALK_P, WALK_B, P(**{**WALK_P, "thL": WALK_P["thR"], "knL": -50, "thR": WALK_P["thL"], "knR": -8, "zL": 1, "zR": 0})]
    t, phase, period, k = 0, 0.0, 28.0, 0
    walk_frames = 96
    for k in range(walk_frames):
        period = 28 - 12 * (k / walk_frames) ** 1.5  # 점점 빨라짐
        phase += 4 / period
        i = int(phase) % 4
        u = phase - int(phase)
        p = lerp_pose(cyc[i], cyc[(i + 1) % 4], EASE["io"](u))
        p["y"] = 0.95 + 0.025 * math.cos(2 * math.pi * phase / 2)
        S.append(("walk", p, k, phase))
    run = [RUN_A, P(**{**RUN_A, **{"thL": 0, "knL": -20, "thR": 0, "knR": -60, "uaL": -28, "uaR": 28}}), RUN_B,
           P(**{**RUN_B, **{"thL": 0, "knL": -60, "thR": 0, "knR": -20, "uaL": -28, "uaR": 28}})]
    for k in range(30):
        phase += 4 / 9
        i = int(phase) % 4
        p = lerp_pose(run[i], run[(i + 1) % 4], EASE["io"](phase - int(phase)))
        p["y"] = 0.92 + 0.05 * abs(math.sin(math.pi * phase / 2))
        S.append(("run", p, k, phase))
    # 4) 순간이동 펀치: 당긴 자세로 나타남(멈춤) → 1프레임에 내지름 → 멈춤 → 임팩트 반전 → 암전
    punch = track([(0, WIND, "lin"), (4, WIND, "h"), (5, PUNCH_OVR, "o"), (6, PUNCH, "o"), (10, PUNCH, "h")], 11)
    for k, p in enumerate(punch):
        S.append(("punch", p, k))
    for k in range(48):
        S.append(("black", None, k))
    return S


def ground_objs(horizon, cam_h, scroll, oid=1000):
    """도시 구도의 땅: 소실점에서 나오는 선 + 다가오는 가로선(걷는 만큼 아래로 흐름)."""
    objs = []
    f = H * 0.9
    vx = W / 2
    for j, x in enumerate((-8, -4, -1.5, 1.5, 4, 8)):
        objs.append((oid + j, 1, (200, 200, 200), 0.35, [[vx, horizon], [vx + x * f / 1.0, horizon + cam_h * f / 1.0]], []))
    for j in range(14):
        dz = 1.0 + ((j * 2.0 - scroll) % 28.0)
        y = horizon + cam_h * f / dz
        if y < H + 5:
            objs.append((oid + 20 + j, 1, (215, 215, 215), 0.35, [[0, y], [W, y]], []))
    return objs


def to_screen(J, cx, cy, s):
    return np.stack([W / 2 + (J[:, 0] - cx) * s, H / 2 - (J[:, 1] - cy) * s], -1)


def render_frames(S, shapes=None):
    frames, bgs = [], []
    sh = None
    if shapes:
        import fx_world as FW
        sh = FW.Shapes(shapes, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "style_kb", "ai_results",
                                            "gpt_FXS_2026-10-22.csv"))
    sky_n = 29
    # 하늘 정지 1.2초 + 섬광(작은 점, 0.2초)
    for k in range(sky_n + 6):
        objs = []
        if sky_n <= k < sky_n + 5 and sh:
            sz = [10, 26, 34, 22, 10][k - sky_n]
            for j, (m, al) in enumerate(((1.0, 0.3), (0.55, 0.65), (0.25, 1.0))):
                L = sh.pick("flash", 3 + j)
                if L:
                    cx, cy = W / 2, H * 0.30
                    objs += FW.to_fills(L, lambda q, m=m: np.stack([cx + q[:, 0] * sz * m * 3, cy + q[:, 1] * sz * m * 3], -1),
                                        tint=(40, 40, 215), gray=False, alpha=al, layer=1)
        frames.append(objs)
        bgs.append((255, 255, 255))
    shake = {}
    for item in S:
        kind, p = item[0], item[1]
        if kind == "black":
            frames.append([])
            bgs.append((12, 12, 12))
            continue
        J, z = fk(p)
        if kind == "fall":
            k = item[2]
            g = (k / 46) ** 1.25
            s = 14 * (2600 / 14) ** g  # 화면 속 크기가 일정 비율로 커져 마지막엔 화면을 가림
            P2 = to_screen(J, 0.0, 0.25, s)
            P2[:, 1] += -H * 0.20 * (1 - g)  # 섬광 자리(위쪽)에서 가운데로
            objs = []
        elif kind == "city":
            k = item[2]
            s = 300
            horizon = H * 0.40
            P2 = to_screen(J, 0.0, 0.95, s)
            P2[:, 1] += H * 0.12
            if 4 <= k < 12:  # 착지 흔들림
                amp = 18 * (1 - (k - 4) / 8)
                P2 += [amp * (1 if k % 2 else -1), amp * 0.6 * (1 if k % 3 else -1)]
            objs = ground_objs(horizon, 1.0, 0.0)
        elif kind in ("walk", "run"):
            s = 300
            horizon = H * 0.40
            P2 = to_screen(J, 0.0, 0.95, s)
            P2[:, 1] += H * 0.12
            objs = ground_objs(horizon, 1.0, item[3] * (0.7 if kind == "walk" else 1.6))
        elif kind == "punch":
            s = 1150
            P2 = to_screen(J, 0.35, 1.25, s)
            objs = []
            if item[2] in (6, 7):  # 임팩트: 바탕 검정, 인물 흰 실루엣
                fig = (255, 255, 255)
                Z = np.full(22, 3 / (THICK * s)) + z * 1e-3
                objs = M.figure(P2, Z, s, fig, fig, 1.0)
                frames.append(objs)
                bgs.append((12, 12, 12))
                continue
        Z = np.full(22, 3 / (THICK * s)) + z * 1e-3  # 굵기 ∝ 화면 속 몸 크기(조립기와 같은 비율), 뒤쪽 팔다리 표시
        objs += M.figure(P2, Z, s, (15, 15, 15), (85, 85, 85), 1.0)
        frames.append(objs)
        bgs.append((255, 255, 255))
    return frames, bgs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--shapes")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    frames, bgs = render_frames(shot_plan(), a.shapes)
    per = 5 * F
    name = os.path.basename(os.path.normpath(a.out))
    files = []
    for p in range(0, len(frames), per):
        fn = os.path.join(a.out, f"{name}_{p // per + 1:02d}.sfa")
        M.write(frames[p:p + per], (255, 255, 255), os.path.splitext(os.path.basename(fn))[0], fn, layer_names=("배경", "이펙트", "인물"),
                frame_bgs=bgs[p:p + per], layers=lambda oid: 0 if oid >= 1000 else 2)
        files.append(os.path.basename(fn))
    info = {"F": F, "전체_프레임": len(frames), "초": round(len(frames) / F, 2), "파일": files, "방식": "키 자세 + 타이밍 직접 설계(정답 예시)"}
    json.dump(info, open(os.path.join(a.out, "조립정보.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(info)


if __name__ == "__main__":
    main()
