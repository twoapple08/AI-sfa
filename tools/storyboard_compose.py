#!/usr/bin/env python3
"""조립기(4단계): 스토리보드(컷 계획표) → 장면 길이 → 동작 생성(글→동작 모델) → 카메라 → 땅 → 연출 → .sfa(나누기_초마다 여러 파일).

사용: python tools/storyboard_compose.py <스토리보드 json> <출력 폴더> --momask <momask-codes 폴더>
        [--name t2m_…] [--res-name tres_…] [--style "in anime style"] [--seed 1] [--check]
- 길이: docs/STORYBOARD-SCHEMA-2026-10-22.md 순서(장면 초 → AI 추정(_AI_추정초) → 최소초 → 전체_초 비율 맞춤). 프레임 = 초 × F.
- 동작: 장면마다 동작 사건의 en 문장(없으면 장면을 이어 쓰기)을 모델에 넣는다. 길이는 20fps 기준 40–196프레임으로 자르고 F로 다시 뽑는다.
  모델 이름(--name/--res-name)을 바꾸면 학습한 가중치로 뽑는다. --style을 주면 문장 끝에 붙인다(트리거).
- 카메라(규칙): 하늘_올려다봄 · 지면_낮게 · 고정 · 뒤로_이동(속도: 느림/점점 빨라짐/더 빨라짐/유지) · 정지. 인물 엉덩이 기준 상대 위치.
- 땅: 비채색이면 회색 원근 격자선(화면에 땅·깊이를 보이게). 채색은 아직 자료가 없어 같은 격자.
- 연출: 임팩트_색포인트/단색섬광(그 프레임 바탕을 그 색으로, 인물은 반대색 실루엣), 흔들림(카메라), 순간이동(그 장면 동작을 카메라 바로 앞에 둠),
  암전(검정 프레임), 하늘에서 떨어짐(기초 모델이 높이를 못 내 장면 1에 낙하 높이를 더함).
- 아직 안 그리는 것(자료·모델 없음): 균열, 부스러기 파편, 붉은 가시, 임팩트 연필 그림. 출력 목록에 '미구현'으로 적는다.
"""
import argparse
import json
import math
import os
import random
import subprocess
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import motion_to_sfa as M  # noqa: E402

COLORS = {"빨강": (220, 30, 30), "파랑": (40, 80, 230), "노랑": (240, 210, 40), "초록": (40, 180, 70), "흰색": (255, 255, 255), "검정": (12, 12, 12)}


def durations(sb):
    st = sb.get("설정", {})
    F = st.get("F") or 24
    secs = []
    for c in sb["컷"]:
        s = c.get("초") or c.get("_AI_추정초") or 2.0
        if c.get("최소초"):
            s = max(s, c["최소초"])
        secs.append(s)
    total = st.get("전체_초")
    if total:
        fixed = sum(s for s, c in zip(secs, sb["컷"]) if c.get("초"))
        free = [i for i, c in enumerate(sb["컷"]) if not c.get("초")]
        k = max(total - fixed, 0.1) / max(sum(secs[i] for i in free), 1e-6)
        for i in free:
            secs[i] *= k
    if st.get("전체_최소초") and sum(secs) < st["전체_최소초"]:
        k = st["전체_최소초"] / sum(secs)
        secs = [s * (1 if c.get("초") else k) for s, c in zip(secs, sb["컷"])]
    return [max(1, round(s * F)) for s in secs], F


def gen_motions(momask, caps, name, res, seed, tag):
    """caps: [(문장, 20fps 프레임)] → [(T,22,3)] — gen_t2m.py를 그대로 쓴다."""
    txt = os.path.join(momask, f"compose_{tag}.txt")
    with open(txt, "w") as fh:
        fh.write("\n".join(f"{c}#{n}" for c, n in caps) + "\n")
    ext = f"compose_{tag}"
    subprocess.run([sys.executable, "gen_t2m.py", "--gpu_id", "-1", "--ext", ext, "--text_path", os.path.basename(txt),
                    "--name", name, "--res_name", res, "--vq_name", "rvq_nq6_dc512_nc512_noshare_qdp0.2", "--repeat_times", "1",
                    "--seed", str(seed)], cwd=momask, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    out = []
    for k, (_, n) in enumerate(caps):
        p = os.path.join(momask, "generation", ext, "joints", str(k), f"sample{k}_repeat0_len{n}_ik.npy")
        out.append(np.load(p).astype(np.float64))
    return out


def ground_lines(eye, at, fov, z0, z1, x0=-12, x1=12, step=2.0):
    """땅(y=0) 격자선 → 화면 선분들. 카메라 뒤로 넘어가는 점은 자른다."""
    segs = []
    for x in np.arange(x0, x1 + 1e-6, step):
        segs.append((np.array([x, 0, z0]), np.array([x, 0, z1])))
    for z in np.arange(math.floor(z0 / step) * step, z1 + 1e-6, step):
        segs.append((np.array([x0, 0, z]), np.array([x1, 0, z])))
    out = []
    f = at - eye
    f = f / np.linalg.norm(f)
    for a, b in segs:
        da, db = (a - eye) @ f, (b - eye) @ f
        if da < 0.3 and db < 0.3:
            continue
        if da < 0.3:  # 카메라 앞쪽까지만
            a = a + (b - a) * (0.3 - da) / (db - da)
        if db < 0.3:
            b = b + (a - b) * (0.3 - db) / (da - db)
        P2, Z, _ = M.project(np.stack([a, b]), eye, at, fov)
        if np.all(np.abs(P2) < 1e5):
            out.append(P2.tolist())
    return out


def camera_frames(cut, n, root, prev):
    """장면 하나의 프레임별 (eye, at, fov). root: 이 장면 엉덩이 위치 [n,3]. prev: 직전 장면 끝 상태(dist, h)."""
    cam = cut.get("카메라", {})
    act, dirn, spd = cam.get("동작", "고정"), cam.get("방향", ""), cam.get("속도", "")
    dist0, h0 = prev
    out = []
    for t in range(n):
        u = t / max(1, n - 1)
        r = root[t] * [1, 0, 1]
        if dirn == "하늘_올려다봄":
            # 착지 지점 앞 땅 가까이에서 떨어지는 인물을 따라 고개를 내리고, 카메라도 같이 내려와 다음 장면(지면_낮게)으로
            # 끊김 없이 이어진다(2026-10-23 사용자 구도: 하늘 올려다봄 → 붉은 섬광 → 카메라 쪽으로 낙하 → 착지까지 따라감)
            land = root[-1] * [1, 0, 1]
            eye, at, fov = land + [0, 1.4 - 0.9 * u ** 2, 3.5], root[t] + [0, 0.9, 0], 60
            dist = 3.5
        elif dirn == "지면_낮게":
            # 공중에서 이어 떨어지는 동안은 인물 높이를 따라 본다(r은 높이 0으로 눌러 둔 값)
            eye, at, fov = r + [0, 0.5, 3.5], r + [0, max(0.8, float(root[t][1]) - 0.1), 0], 55
            dist = 3.5
        elif act == "뒤로_이동":
            if "더 빨라짐" in spd:
                d = dist0 + 6 * u ** 1.6
            elif "점점 빨라짐" in spd:
                d = dist0 + 4 * u ** 2
            elif "유지" in spd:
                d = dist0 + 5 * u
            else:  # 느림 → 조금씩
                d = dist0 + 2 * u ** 1.5
            eye, at, fov, dist = r + [0, 1.0, d], r + [0, 0.9, 0], 50, d
        else:  # 고정·정지: 직전 거리 유지
            eye, at, fov, dist = r + [0, h0, dist0], r + [0, 0.9, 0], 50, dist0
        out.append((np.array(eye, float), np.array(at, float), fov))
    return out, (dist, 1.0)


def burst(dt, tau=1.4):
    return 1 - math.exp(-max(dt, 0) / tau)


def effects_plan(sb, lens, J, cams, a, notes):
    """균열·부유 파편·붉은 가시 → {프레임: [채우기…]} (형태 사전 + GPT 판정, 3D 배치)."""
    import fx_world as FW
    sh = FW.Shapes(a.shapes, a.approved)
    gray = not sb.get("설정", {}).get("배경_채색")
    rng = random.Random(a.seed * 101)
    out = {}
    add = lambda k, L: out.setdefault(k, []).extend(L)
    starts = np.cumsum([0] + lens)
    N = len(J)
    land = None
    for i, c in enumerate(sb["컷"]):
        tags = [e.get("태그") for e in c["사건"]]
        s0, n = int(starts[i]), lens[i]
        if "균열" in tags and land is None:
            land = J[s0, 0] * [1, 0, 1]
            cracks = [(sh.pick("streak", rng.randrange(999)), rng.uniform(0, 2 * math.pi), rng.uniform(0.7, 1.6)) for _ in range(7)]
            for k in range(s0, N):
                g = burst(k - s0, 1.2)
                for L, rot, sz in cracks:
                    if L:
                        cen = land + [math.cos(rot) * sz * 0.5 * g, 0, math.sin(rot) * sz * 0.5 * g]
                        add(k, FW.ground(L, cen, sz * g, rot, cams[k], gray=gray, tint=(40, 40, 40)))
            notes.append(f"장면 {c['장면']}: 균열 = 줄기 형태 7개를 땅에 눕혀 방사형(형태 사전)")
        if "파편" in tags and land is not None and any("부유" in (e.get("움직임") or "") and "떨어" not in (e.get("움직임") or "") for e in c["사건"]):
            # "부유하던 부스러기가 떨어짐"(다음 장면)은 새 부유가 아니라 앞 장면 돌의 낙하 시각이다(2026-10-23 중복 생성 버그)
            # 착지와 함께 튀어 올라 공중에 멈춤 → 다음 장면의 '떨어짐' 시각에 떨어진다
            fall_at = None
            for j in range(i + 1, len(sb["컷"])):
                for e in sb["컷"][j]["사건"]:
                    if e.get("태그") == "파편" and "떨어" in (e.get("움직임") or ""):
                        fall_at = int(starts[j] + round(e.get("시각_비율", 0) * lens[j]))
                        break
                if fall_at:
                    break
            rocks = []
            for r in range(36):
                ang = rng.uniform(0, 2 * math.pi)
                rocks.append((sh.pick("rock", rng.randrange(999)), ang, rng.uniform(0.3, 2.2), rng.uniform(0.3, 1.8),
                              rng.uniform(0.06, 0.22), rng.uniform(0, 6.3), rng.uniform(-0.04, 0.04)))
            for k in range(s0, N):
                for L, ang, dist, h, sz, rot0, spin in rocks:
                    if not L:
                        continue
                    g = burst(k - s0, 1.4)
                    y = h * g
                    if fall_at is not None and k >= fall_at:
                        u = (k - fall_at) / 8
                        y = max(sz * 0.4, h * (1 - u * u))
                    cen = land + [math.cos(ang) * dist * g, y, math.sin(ang) * dist * g * 0.6]
                    add(k, FW.billboard(L, cen, sz, rot0 + spin * (k - s0), cams[k], gray=gray, alpha=1.0))
            notes.append(f"장면 {c['장면']}: 부유 파편 = 돌 형태 36개, '빡' 튀고 멈춤" + (f" → {fall_at}프레임부터 떨어짐" if fall_at else ""))
    # 붉은 가시: 장면마다 간격(느림 → 점점 짧아짐 → 유지)
    spikes, t_next = [], None
    for i, c in enumerate(sb["컷"]):
        ev = [e for e in c["사건"] if e.get("태그") == "붉은_가시"]
        if not ev:
            continue
        s0, n = int(starts[i]), lens[i]
        e = ev[0]
        gap = e.get("간격", "")
        k = s0 + int(round(e.get("시각_비율", 0) * n))
        if t_next is not None:
            k = max(k, t_next)
        while k < s0 + n:
            u = (k - s0) / max(1, n)
            step = 10 if "느림" in gap or "하나둘" in gap else (int(round(10 - 7 * u)) if "짧아" in gap else 3)
            r = J[k, 0]
            base = np.array([r[0] + rng.uniform(-7, 7), 0.0, r[2] - rng.uniform(4, 14)])  # 카메라·인물에서 먼 쪽(인물 뒤)
            spikes.append((k, sh.pick("streak", rng.randrange(999)), base, rng.uniform(1.5, 3.8)))
            k += max(2, step)
        t_next = k
    for k0, L, base, hgt in spikes:
        if not L:
            continue
        for k in range(k0, N):
            add(k, FW.upright(L, base, hgt * burst(k - k0, 1.2), cams[k], tint=(40, 40, 215), gray=False))
    if spikes:
        notes.append(f"붉은 가시 {len(spikes)}개 = 줄기 형태를 세워 빨갛게(형태 사전), 간격 느림→짧아짐→유지")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("storyboard")
    ap.add_argument("out")
    ap.add_argument("--momask", required=True)
    ap.add_argument("--name", default="t2m_nlayer8_nhead6_ld384_ff1024_cdp0.1_rvq6ns")
    ap.add_argument("--res-name", default="tres_nlayer8_ld384_ff1024_rvq6ns_cdp0.2_sw")
    ap.add_argument("--style", default="")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--hold", type=int, default=2)
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--scene-model", action="append", help="장면별 모델 '장면번호=마스크이름,잔차이름'(여러 번). 예: 3=t2m_…_rvq6ns,tres_…_sw")
    ap.add_argument("--shapes", help="이펙트 형태 사전(tools/fx_shapes.py 출력, Drive). 있으면 균열·부유 파편·붉은 가시를 그린다")
    ap.add_argument("--approved", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "style_kb", "ai_results",
                                                      "gpt_FXS_2026-10-22.csv"))
    a = ap.parse_args()
    sb = json.load(open(a.storyboard, encoding="utf-8"))
    os.makedirs(a.out, exist_ok=True)
    lens, F = durations(sb)
    st = sb.get("설정", {})
    # 1) 동작 문장: 장면마다 동작 사건의 en(없으면 앞 장면 동작을 이어 씀)
    caps, last = [], "a person stands still"
    for c, n in zip(sb["컷"], lens):
        en = next((e.get("en") for e in c["사건"] if e["종류"] == "동작" and e.get("en")), None) or last
        last = en
        n20 = int(min(196, max(40, round(n * 20 / F))) // 4 * 4)
        caps.append((en + (f", {a.style}" if a.style else ""), n20))
    clips = gen_motions(a.momask, caps, a.name, a.res_name, a.seed, os.path.basename(os.path.normpath(a.out)))
    # 장면별 모델: "3=마스크이름,잔차이름" — 그 장면만 다른 모델로 다시 뽑는다(2026-10-23: 일어서기는 기본 모델이 최선)
    per = {}
    for spec in a.scene_model or []:
        k, nm = spec.split("=", 1)
        per.setdefault(nm, []).append(int(k) - 1)
    for nm, idx in per.items():
        mn, rn = nm.split(",", 1)
        sub = gen_motions(a.momask, [caps[i] for i in idx], mn, rn, a.seed,
                          os.path.basename(os.path.normpath(a.out)) + "_" + mn[-12:].strip("_"))
        for i, C in zip(idx, sub):
            clips[i] = C
    # 2) 장면 길이에 맞추기(20fps → F, 장면 프레임 수로 늘이거나 줄임) + 이어 붙이기 + 연출 위치
    J, cut_of, end = [], [], None
    notes = []
    fall_carry = None
    for i, (c, n, C) in enumerate(zip(sb["컷"], lens, clips)):
        t = np.linspace(0, len(C) - 1, n)
        i0 = np.floor(t).astype(int)
        i1 = np.minimum(i0 + 1, len(C) - 1)
        R = C[i0] * (1 - (t - i0))[:, None, None] + C[i1] * (t - i0)[:, None, None]
        tele = any(e.get("태그") == "순간이동" for e in c["사건"])
        if end is not None and not tele:
            R = R + [end[0] - R[0, 0, 0], 0, end[2] - R[0, 0, 2]]
        nxt = sb["컷"][i + 1] if i + 1 < len(sb["컷"]) else None
        lands_next = nxt is not None and any(e.get("태그") == "착지" for e in nxt["사건"])
        if any("떨어" in (e.get("설명") or "") for e in c["사건"] if e["종류"] == "동작"):
            # 하늘에서 떨어짐: 기초 모델이 높이를 못 내 높이를 더한다. 다음 장면이 착지면 공중(carry m)에서 끝내고
            # 착지 장면이 나머지를 떨어진다(장면 1 끝에서 한 번, 장면 2에서 또 한 번 착지하던 문제, 2026-10-23)
            k = np.clip(1 - np.arange(n) / max(1, n - 1), 0, 1) ** 2
            carry = 3.0 if lands_next else 0.0
            R[:, :, 1] += (carry + (12.0 - carry) * k)[:, None]
            R[:, :, 2] -= (6.0 * k)[:, None]  # 카메라(+z 쪽) 반대편 먼 하늘에서 카메라 쪽으로 다가오며 떨어짐
            if lands_next:
                fall_carry = (carry, R[-1, 0, 1])
            notes.append(f"장면 {c['장면']}: 낙하 높이 12m·앞으로 6m를 조립기가 더함(모델 한계)" + (f", 공중 {carry:.0f}m에서 다음 장면으로" if lands_next else ""))
        elif any(e.get("태그") == "착지" for e in c["사건"]) and fall_carry is not None:
            # 앞 장면에서 이어지는 낙하: 착지 순간(엉덩이가 가장 낮은 프레임)까지 남은 높이를 빠르게 줄인다
            q = max(1, n // 6)
            li = int(q + np.argmin(R[q:, 0, 1])) if n > q else n - 1
            off = np.zeros(n)
            off0 = max(0.0, fall_carry[1] - R[0, 0, 1])
            tt = np.arange(li + 1) / max(1, li)
            off[: li + 1] = off0 * (1 - tt ** 2)
            R[:, :, 1] += off[:, None]
            notes.append(f"장면 {c['장면']}: 앞 장면 낙하를 이어 {li}프레임에 착지")
            fall_carry = None
        if tele:
            notes.append(f"장면 {c['장면']}: 순간이동 — 카메라 바로 앞(1.8m)에 둠")
        J.append(R)
        cut_of += [i] * n
        end = R[-1, 0]
    J = np.concatenate(J)
    if a.hold > 1:
        J = J[(np.arange(len(J)) // a.hold) * a.hold]
    # 3) 카메라
    cams, prev, start = [], (9.0, 0.8), 0
    for i, (c, n) in enumerate(zip(sb["컷"], lens)):
        fr, prev = camera_frames(c, n, J[start:start + n, 0], prev)
        if any(e.get("태그") == "순간이동" for e in c["사건"]) and cams:  # 카메라는 멈추고 인물을 카메라 앞에
            eye, at, fov = cams[-1]
            fwd = (at - eye) * [1, 0, 1]
            fwd /= np.linalg.norm(fwd) + 1e-9
            tgt = eye + fwd * 1.8
            J[start:start + n] += (tgt - J[start, 0]) * [1, 0, 1]
            fr = [(eye, at, fov)] * n
        cams += fr
        start += n
    # 흔들림
    for i, (c, n) in enumerate(zip(sb["컷"], lens)):
        if "흔들림" in c.get("카메라", {}):
            s0 = sum(lens[:i])
            for t in range(min(n, 8)):
                r = random.Random(a.seed * 31 + (s0 + t) // 2)
                amp = 0.08 * (1 - t / 8)
                eye, at, fov = cams[s0 + t]
                d = np.array([r.uniform(-1, 1), r.uniform(-1, 1), 0]) * amp
                cams[s0 + t] = (eye + d, at + d, fov)
    # 4) 연출: 임팩트(바탕색·실루엣), 암전
    color_bg = bool(st.get("배경_채색"))
    bgs, fig_cols, black = [], [], set()
    base_bg, base_fig = (255, 255, 255), (0, 0, 0)
    flash = {}
    for i, (c, n) in enumerate(zip(sb["컷"], lens)):
        s0 = sum(lens[:i])
        for e in c["사건"]:
            t0 = s0 + int(round(e.get("시각_비율", 0) * n))
            if e["종류"] == "임팩트":
                col = COLORS.get(e.get("색", ""), (255, 255, 255) if "단색" in e.get("태그", "") else (12, 12, 12))
                for t in range(t0, min(s0 + n, t0 + int(e.get("프레임", 2)))):
                    flash[t] = col
            if e.get("태그") == "암전":
                for t in range(t0, s0 + n):
                    black.add(t)
        if not a.shapes:
            for e in c["사건"]:
                if e["종류"] == "이펙트" or e.get("태그") in ("붉은_가시",):
                    notes.append(f"장면 {c['장면']}: {e.get('태그')} 미구현(형태 사전 없음 — --shapes)")
    fx = effects_plan(sb, lens, J, cams, a, notes) if a.shapes else {}
    frames = []
    for k in range(len(J)):
        eye, at, fov = cams[k]
        if k in black:
            frames.append([])
            bgs.append((12, 12, 12))
            continue
        bgc = flash.get(k, base_bg)
        fig = (12, 12, 12) if sum(bgc) > 380 else (255, 255, 255)
        P2, Z, s = M.project(J[k], eye, at, fov)
        objs = M.figure(P2, Z, s, fig, (120, 120, 120) if k not in flash else fig, 1.0)
        if k not in flash:  # 땅 격자(배경 레이어)
            r = J[k, 0]
            for j, seg in enumerate(ground_lines(eye, at, fov, r[2] - 18, r[2] + 18)):
                objs.insert(0, (1000 + j, 1, (200, 200, 200), 0.35, seg, []))
        objs += fx.get(k, [])
        frames.append(objs)
        bgs.append(bgc)
    # 5) 나누기_초마다 파일로
    per = int((st.get("나누기_초") or 5) * F)
    name = os.path.basename(os.path.normpath(a.out))
    files = []
    for p in range(0, len(frames), per):
        fn = os.path.join(a.out, f"{name}_{p // per + 1:02d}.sfa")
        M.write(frames[p:p + per], base_bg, os.path.splitext(os.path.basename(fn))[0], fn, layer_names=("배경", "이펙트", "인물"),
                frame_bgs=bgs[p:p + per], layers=lambda oid: 0 if oid >= 1000 else 2)  # 레이어 0(배경) → 1(이펙트, 채우기) → 2(인물)
        files.append(fn)
    info = {"장면_프레임": lens, "F": F, "전체_프레임": len(frames), "초": round(len(frames) / F, 2), "파일": [os.path.basename(f) for f in files],
            "동작_문장": [c for c, _ in caps], "모델": [a.name, a.res_name], "장면별_모델": a.scene_model or [], "메모": notes, "배경_채색": color_bg}
    json.dump(info, open(os.path.join(a.out, "조립정보.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps({k: info[k] for k in ("장면_프레임", "전체_프레임", "초", "파일")}, ensure_ascii=False))
    for m in notes:
        print(" -", m)
    if a.check:
        import cv2
        from sfa_render import iter_frames, render_frame
        tiles = []
        for fn in files:
            for seq, fr in iter_frames(fn):
                pos = int(fr.get("Position"))
                if pos % max(1, per // 4) == 0 or pos == 0:
                    im = render_frame(seq, fr, 480, 270)[..., ::-1].copy()
                    cv2.putText(im, f"{os.path.basename(fn)[-6:-4]}:{pos}", (5, 20), 0, 0.6, (0, 0, 255), 2)
                    tiles.append(im)
        while len(tiles) % 4:
            tiles.append(np.full_like(tiles[0], 255))
        cv2.imwrite(os.path.join(a.out, "확인.jpg"), np.vstack([np.hstack(tiles[i:i + 4]) for i in range(0, len(tiles), 4)]))


if __name__ == "__main__":
    main()
