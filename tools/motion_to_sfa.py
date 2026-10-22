#!/usr/bin/env python3
"""3D 관절 움직임(글→동작 모델 출력, SMPL 22관절) → 3D 카메라로 찍어 스틱파이터 뼈대(리그 A 모양) SFA로 쓴다.

사용: python tools/motion_to_sfa.py <장면 계획 json> <출력.sfa> [--check 확인.jpg]
장면 계획 json(지금은 손으로 쓰고, 나중에 스토리보드 → 자동):
  {"fps": [T, F], "src_fps": 20, "hold": 2, "bg": [255,255,255], "fig": [0,0,0],
   "clips": [{"path": "x.npy", "frames": null, "offset": [x, y, z] | null, "drop": 0.0}, ...],
   "camera": [{"t": 0, "eye": [x,y,z], "at": [x,y,z], "fov": 50, "rel": false}, ...]}
- clips: 이어 붙일 동작 조각(np.save한 (프레임, 22, 3) — y 위, 미터). offset이 null이면 앞 조각 끝의 엉덩이 위치(x·z)에 이어 붙인다.
  drop > 0이면 그 조각 앞부분에서 엉덩이를 그만큼(미터) 위에서 내려오게 더한다(하늘에서 떨어지기 — 기초 모델이 높이를 못 냄).
- 시간: 원래 src_fps(MoMask는 20) → 재생 F로 다시 뽑는다. hold = 그림 유지(2면 2프레임마다 새 자세, 애니식).
- camera: 프레임 t(재생 F 기준)마다 눈 위치·보는 점·세로 화각. 사이 프레임은 선형 보간(속도 변화는 키를 촘촘히 두어 표현).
- 그리기: 리그 A와 같은 14점(엉덩이·가슴·목·머리, 팔꿈치·손, 무릎·발목·발끝) 직선(TypeId 1) + 머리 원(TypeId 2, 목 → 정수리 지름).
  카메라에서 먼 쪽 팔다리를 뒤(회색), 가까운 쪽을 앞(검정)에 그린다. 선 굵기는 거리에 반비례(원근). AO ID는 프레임마다 같게(트위닝 대응).
"""
import argparse
import json
import math
import os
import sys
import zipfile

import numpy as np

W, H = 1920, 1080
# SMPL 22: 0 골반 1 왼엉덩이 2 오른엉덩이 3 척추1 4 왼무릎 5 오른무릎 6 척추2 7 왼발목 8 오른발목 9 척추3 10 왼발 11 오른발
#          12 목 13 왼쇄골 14 오른쇄골 15 머리 16 왼어깨 17 오른어깨 18 왼팔꿈치 19 오른팔꿈치 20 왼손목 21 오른손목
LIMBS = {"armL": [16, 18, 20], "armR": [17, 19, 21], "legL": [0, 4, 7, 10], "legR": [0, 5, 8, 11]}


def load_clips(plan):
    out, end = [], None
    for c in plan["clips"]:
        J = np.load(c["path"]).astype(np.float64)
        if c.get("frames"):
            J = J[: c["frames"]]
        if c.get("offset") is not None:
            J = J + np.array(c["offset"]) - [J[0, 0, 0], 0, J[0, 0, 2]]
        elif end is not None:
            J = J + [end[0] - J[0, 0, 0], 0, end[2] - J[0, 0, 2]]
        if c.get("drop"):
            n = len(J)
            k = np.clip(1 - np.arange(n) / max(1, int(n * c.get("drop_part", 0.4))), 0, 1) ** 2   # 앞부분에서 빠르게 내려옴(가속 낙하)
            J[:, :, 1] += (c["drop"] * k)[:, None]
        out.append(J)
        end = J[-1, 0]
    return np.concatenate(out)


def resample(J, src, dst, hold):
    n = int(round((len(J) - 1) * dst / src)) + 1
    t = np.arange(n) * src / dst
    i0 = np.floor(t).astype(int).clip(0, len(J) - 1)
    i1 = (i0 + 1).clip(0, len(J) - 1)
    f = (t - i0)[:, None, None]
    R = J[i0] * (1 - f) + J[i1] * f
    if hold > 1:
        R = R[(np.arange(n) // hold) * hold]
    return R


def cam_at(keys, t, root=None):
    """rel: true인 키는 눈·보는 점을 그 키 시각의 엉덩이 위치(x·z) 기준 상대값으로 본다(인물을 따라가는 카메라)."""
    def absk(k):
        if not k.get("rel") or root is None:
            return k
        r = root[min(max(int(k["t"]), 0), len(root) - 1)]
        off = np.array([r[0], 0.0, r[2]])
        return dict(k, eye=(np.array(k["eye"]) + off).tolist(), at=(np.array(k["at"]) + off).tolist())
    keys = [absk(k) for k in keys]
    ks = sorted(keys, key=lambda k: k["t"])
    if t <= ks[0]["t"]:
        k0 = k1 = ks[0]
    elif t >= ks[-1]["t"]:
        k0 = k1 = ks[-1]
    else:
        k1 = next(k for k in ks if k["t"] >= t)
        k0 = ks[ks.index(k1) - 1]
    u = 0 if k1["t"] == k0["t"] else (t - k0["t"]) / (k1["t"] - k0["t"])
    lerp = lambda a, b: np.array(a) * (1 - u) + np.array(b) * u
    return lerp(k0["eye"], k1["eye"]), lerp(k0["at"], k1["at"]), float(lerp([k0.get("fov", 50)], [k1.get("fov", 50)])[0])


def project(P, eye, at, fov):
    """세계 좌표(y 위) → 화면 px, 깊이. 핀홀 카메라."""
    f = at - eye
    f = f / np.linalg.norm(f)
    r = np.cross(f, [0, 1, 0])
    r = r / (np.linalg.norm(r) + 1e-9)
    u = np.cross(r, f)
    d = P - eye
    x, y, z = d @ r, d @ u, d @ f
    s = (H / 2) / math.tan(math.radians(fov) / 2)
    z = np.maximum(z, 0.05)
    return np.stack([W / 2 + s * x / z, H / 2 - s * y / z], -1), z, s


def figure(P2, Z, s, fig, back, thick0):
    """14점 리그 모양 → [(id, type, color, thick, pts, links)]. links: (내 점 번호, 상대 AO id, 상대 점 번호)."""
    p = lambda i: P2[i].tolist()
    chest = ((P2[16] + P2[17]) / 2).tolist()
    nk, hd = p(12), p(15)
    top = [2 * hd[0] - nk[0], 2 * hd[1] - nk[1]]
    zc = float(Z[[0, 12]].mean())
    th = thick0 * 3.0 / max(zc, 0.3)          # 거리 3m에서 thick0
    # 카메라에서 먼 쪽 팔다리 = 뒤
    armL_back = Z[[18, 20]].mean() > Z[[19, 21]].mean()
    legL_back = Z[[4, 7]].mean() > Z[[5, 8]].mean()
    o = []
    o.append((1, 1, fig, th, [p(0), chest], []))
    o.append((2, 1, fig, th, [chest, nk], [(0, 1, 1)]))
    o.append((3, 2, fig, th, [top, nk], [(1, 2, 1)]))
    for side, base in (("L", 10), ("R", 20)):
        a = LIMBS["arm" + side]
        col = back if (armL_back == (side == "L")) else fig
        o.append((base + 1, 1, col, th, [chest, p(a[1])], [(0, 1, 1)]))
        o.append((base + 2, 1, col, th, [p(a[1]), p(a[2])], [(0, base + 1, 1)]))
        l = LIMBS["leg" + side]
        col = back if (legL_back == (side == "L")) else fig
        o.append((base + 3, 1, col, th, [p(0), p(l[1])], [(0, 1, 0)]))
        o.append((base + 4, 1, col, th, [p(l[1]), p(l[2])], [(0, base + 3, 1)]))
        o.append((base + 5, 1, col, th, [p(l[2]), p(l[3])], [(0, base + 4, 1)]))
    # 그리기 순서: 뒤쪽 팔다리 먼저
    o.sort(key=lambda x: 0 if x[2] == back else 1)
    return o


def argb(c, a=1.0):
    v = (int(round(a * 255)) << 24) | (int(c[0]) << 16) | (int(c[1]) << 8) | int(c[2])
    return v - (1 << 32) if v >= 1 << 31 else v


def write(frames, bg, name, path, layer_names=("인물",)):
    lines = [f"<?xml version='1.0' encoding='utf-8'?>",
             f'<Sequence Name="{name}" HeightWidthRatio="0.5625" RatioX="16" RatioY="9" FrameCount="{len(frames)}" BackgroundColor="{argb(bg)}">']
    pid = 1
    for k, objs in enumerate(frames):
        lines.append(f'<Frame BackgroundColor="{argb(bg) & 0xFFFFFFFF}" ID="{k + 1}" Position="{k}">')
        lines += [f'<LayerDef ID="{i}" Name="{n}" Visible="true" Locked="false" />' for i, n in enumerate(layer_names)]
        ids = {}
        for o in objs:
            ids[o[0]] = pid
            pid += len(o[4])
        conn = {}
        for o in objs:
            for mine, oid, op in o[5]:
                if oid in ids:
                    a, b = ids[o[0]] + mine, ids[oid] + op
                    conn.setdefault(a, []).append(b)
                    conn.setdefault(b, []).append(a)
        for order, (oid, typ, col, th, pts, _) in enumerate(objs):
            lines.append(f'<AO ID="{oid}" TypeId="{typ}" Color="{argb(col)}" LayerId="0" DrawOrder="{order + 1}" ThicknessScale="{th:.3f}" '
                         f'ObjectScale="1.0" GlowRadius="0.0" GlowThickness="0.0" GlowColor="4294967295" GlowAlpha="0.0">')
            for i, (x, y) in enumerate(pts):
                q = ids[oid] + i
                c = conn.get(q)
                attr = f'ID="{q}" Flags="{4 if c else 5}" Index="{i}" X="{x / W * 100:.3f}" Y="{y / H * 100:.3f}"'
                if c:
                    lines.append(f"<AP {attr}>" + "".join(f'<AC ConnPtId="{b}" />' for b in c) + "</AP>")
                else:
                    lines.append(f"<AP {attr} />")
            lines.append("</AO>")
        lines.append("</Frame>")
    lines.append("</Sequence>")
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(name + ".xml", "\n".join(lines) + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("plan")
    ap.add_argument("out")
    ap.add_argument("--check")
    a = ap.parse_args()
    plan = json.load(open(a.plan, encoding="utf-8"))
    T, F = plan.get("fps", [24, 24])
    J = resample(load_clips(plan), plan.get("src_fps", 20), F, plan.get("hold", 2))
    fig = plan.get("fig", [0, 0, 0])
    back = plan.get("back", [110, 110, 110])
    frames = []
    for k in range(len(J)):
        eye, at, fov = cam_at(plan["camera"], k, J[:, 0])
        P2, Z, s = project(J[k], eye, at, fov)
        frames.append(figure(P2, Z, s, fig, back, plan.get("thick", 1.0)))
    name = os.path.splitext(os.path.basename(a.out))[0]
    write(frames, plan.get("bg", [255, 255, 255]), name, a.out)
    print("프레임", len(frames), f"({len(frames) / F:.2f}초, T,F={T},{F})", "→", a.out)
    if a.check:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import cv2
        from sfa_render import iter_frames, render_frame
        idx = np.linspace(0, len(frames) - 1, 12).astype(int)
        tiles = []
        for seq, fr in iter_frames(a.out, set(idx.tolist())):
            im = render_frame(seq, fr, 640, 360)[..., ::-1].copy()
            cv2.putText(im, fr.get("Position"), (6, 24), 0, 0.8, (0, 0, 255), 2)
            tiles.append(im)
        cv2.imwrite(a.check, np.vstack([np.hstack(tiles[i:i + 4]) for i in range(0, len(tiles), 4)]))


if __name__ == "__main__":
    main()
