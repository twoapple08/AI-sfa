#!/usr/bin/env python3
"""이펙트 생성기 시제품(캐릭터 없음): 종류·시드·길이로 이펙트만 있는 SFA를 만든다(사용자 2026-10-22: 이펙트·연출 먼저, 결과물은 이펙트만).

사용: python tools/fx_gen.py <effects.txt> <palette.txt> <출력.sfa> [--kind impact|explosion|smoke|debris|shockwave|flash]
      [--frames 48] [--seed 1] [--bg 0,0,0] [--stats 수치.json] [--check 확인.jpg]
- 모양: 이펙트 사전(tools/effect_library.py, 나카무라 임팩트 장면에서 딴 포물선 조각 윤곽 — 쐐기·덩어리). 원·직선 대용 없음.
- 그리기: AGENTS.md 원칙 — 같은 형태를 크기·알파·색을 바꿔 여러 겹(바깥 넓고 옅게 → 안쪽 좁고 진하게). 모든 경계는 2차 베지어(TypeId 3) + FR 채우기.
- 움직임 기본값(--stats로 덮어쓴다. 이펙트 분리 결과를 tools/fx_timing.py로 잰 값으로 바꿀 예정):
  파편: 정점 속도 0.014 화면높이/프레임, 속도 반감 3프레임(data/p4/nakamura_debris_rhythm_2026-10-21.json 폭발 파편 중앙값),
  섬광: 임팩트 1~2프레임 — 나카무라 임팩트 장면 플립북(사전 Q, 흑백 실루엣·먹선)을 시드로 골라 한 장씩(없으면 단색).
  그림 유지: 2s 바탕·빠른 순간 1s(docs/P1-STRIKE-TIMING-2026-10-22.md).
  폭발 면적은 빠르게 커져 수명 약 30%에서 정점(가정, 측정 전), 연기는 오르며 넓어지고 천천히 옅어짐(가정).
- impact = 섬광 → 충격파·폭발·파편 → 연기가 이어지는 묶음.
이펙트 사전은 다른 작가 그림 유래라 저장소 밖(Drive). 이 도구와 수치만 저장소에 둔다.
"""
import argparse
import json
import math
import os
import random
import sys
import zipfile

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from effect_clip_sfa import Writer, argb  # noqa: E402

W, H = 960, 540
DEFAULT = {
    "debris_v0": 0.014, "debris_half": 3.0, "debris_gravity": 0.0012, "debris_count": 40,
    "explosion_peak": 0.3, "explosion_size": 0.33, "smoke_rise": 0.004, "smoke_grow": 0.012,
    "shock_speed": 0.045, "flash_frames": 2, "hold": 2,
}


def load_lib(path):
    wedges, blobs = [], []
    lines = open(path, encoding="utf-8").read().splitlines()
    i = 0
    while i < len(lines):
        f = lines[i].split()
        if f and f[0] == "K":
            n = int(f[3])
            cs = [(int(lines[i + k].split()[1]), np.array(lines[i + k].split()[2:], float).reshape(-1, 6)) for k in range(1, n + 1)]
            (wedges if f[1] == "wedge" else blobs).append(cs)
            i += 1 + n
        else:
            i += 1
    return wedges, blobs


def load_scenes(path):
    """임팩트 장면 플립북(Q): [(흰 먹 여부, 폭 w(높이 1 기준), [그룹 윤곽 목록])] 프레임 목록."""
    lines = open(path, encoding="utf-8").read().splitlines()
    scenes, i = [], 0
    while i < len(lines):
        f = lines[i].split()
        if f and f[0] == "Q":
            nf, i = int(f[2]), i + 1
            frames = []
            for _ in range(nf):
                h = lines[i].split()
                i += 1
                groups = []
                for _ in range(int(h[3])):
                    nc = int(lines[i].split()[1])
                    i += 1
                    groups.append([(int(lines[i + k].split()[1]), np.array(lines[i + k].split()[2:], float).reshape(-1, 6))
                                   for k in range(nc)])
                    i += nc
                frames.append((h[1] == "1", float(h[2]), groups))
            scenes.append((f[1], frames))
        else:
            i += 1
    return scenes


def load_pal(path):
    out = []
    for ln in open(path, encoding="utf-8"):
        f = ln.split()
        if f and f[0] == "P":
            out.append((int(f[3]), int(f[2]), int(f[1])))  # BGR
    return out


def nearest(pal, rgb):
    r, g, b = rgb
    if not pal:
        return (b, g, r)
    return min(pal, key=lambda c: (c[2] - r) ** 2 + (c[1] - g) ** 2 + (c[0] - b) ** 2)


def place(shape, cx, cy, s, ang):
    """형태(중심 원점, 면적 제곱근 1)를 화면 px로: 크기 s(화면 높이 비율), 회전 ang. → effect_clip_sfa.Writer.fill용 윤곽 목록."""
    c, n = math.cos(ang), math.sin(ang)
    out = []
    for cid, (hole, segs) in enumerate(shape):
        P = segs.reshape(-1, 2) * s * H
        R = np.stack([P[:, 0] * c - P[:, 1] * n + cx * H, P[:, 0] * n + P[:, 1] * c + cy * H], 1).reshape(-1, 6)
        out.append({"hole": bool(hole), "segs": R.tolist(), "cid": cid, "parent": 0 if hole else -1})
    return out


def axis(shape):
    P = shape[0][1].reshape(-1, 2)
    P = P - P.mean(0)
    xx, yy, xy = (P[:, 0] ** 2).sum(), (P[:, 1] ** 2).sum(), (P[:, 0] * P[:, 1]).sum()
    return 0.5 * math.atan2(2 * xy, xx - yy)


class Gen:
    def __init__(self, wedges, blobs, pal, seed, frames, st, cx=None, cy=0.5, scenes=()):
        self.wedges, self.blobs, self.pal = wedges, blobs, pal
        self.scenes = list(scenes)
        self.rng = random.Random(seed)
        self.seed = seed
        self.N = frames
        self.st = st
        self.cx = W / H / 2 if cx is None else cx
        self.cy = cy
        self.col = {k: nearest(pal, v) for k, v in {"red": (194, 49, 46), "orange": (234, 131, 26), "yellow": (246, 222, 37),
                                                     "cream": (246, 234, 123), "smoke": (90, 84, 80), "dust": (196, 131, 92)}.items()}
        self.col["white"] = (255, 255, 255)
        self.col["smoke"] = (78, 82, 86)  # 학습 팔레트에 무채색이 없어 가장 가까운 색이 파랑이 됐다 → 연기는 회색 고정(측정 전)

    def held(self, t, fast=False):
        """그림 유지: 빠른 순간은 1s, 나머지는 hold(기본 2s) — 같은 그림을 그 프레임 수만큼 보여 준다."""
        h = 1 if fast else int(self.st["hold"])
        return (t // h) * h

    # 각 함수는 프레임 t에서 [(윤곽 목록, BGR, 알파)] 를 아래 → 위 순서로 돌려준다
    def explosion(self, t, t0=0, life=None):
        life = life or int(self.N * 0.75)
        u = (self.held(t - t0) if t >= t0 else -1) / life
        if u < 0 or u > 1:
            return []
        pk = self.st["explosion_peak"]
        grow = 1 - (1 - min(u / pk, 1)) ** 3  # 빠르게 커짐(ease-out)
        fade = 1.0 if u < pk else max(0.0, 1 - (u - pk) / (1 - pk))
        rng = random.Random(self.seed * 1000 + 7)  # 시드마다 다른 모양(같은 시드면 같은 결과)
        lumps = [(rng.uniform(-0.6, 0.6), rng.uniform(-0.5, 0.4), rng.uniform(0.5, 1.0), rng.uniform(0, 6.28), rng.randrange(len(self.blobs)))
                 for _ in range(7)]
        out = []
        size = self.st["explosion_size"] * grow
        for sc, ck, a in ((1.35, "red", 0.35), (1.0, "orange", 0.6), (0.62, "yellow", 0.85), (0.32, "white", 0.95)):
            inner = sc < 0.7
            k = (1 - 0.6 * (u - pk) / (1 - pk)) if (inner and u > pk) else 1.0  # 안쪽 밝은 겹은 정점 뒤 먼저 줄어든다
            for dx, dy, r, ang, bi in lumps:
                sh = place(self.blobs[bi], self.cx + dx * size, self.cy + dy * size, size * r * sc * k * 0.55, ang + u)
                out.append((sh, self.col[ck], a * fade))
        return out

    def smoke(self, t, t0=0):
        if t < t0:
            return []
        u = self.held(t - t0, False) / max(1, self.N - t0)
        rng = random.Random(self.seed * 1000 + 11)  # 시드마다 다른 모양(같은 시드면 같은 결과)
        out = []
        for i in range(9):
            dx, ph, bi = rng.uniform(-0.5, 0.5), rng.uniform(0, 6.28), rng.randrange(len(self.blobs))
            age = u * self.N
            s = 0.06 + self.st["smoke_grow"] * age * rng.uniform(0.7, 1.3)
            x = self.cx + dx * (0.25 + 0.4 * u)
            y = self.cy - self.st["smoke_rise"] * age * rng.uniform(0.6, 1.4) - 0.05
            fade = max(0.0, 1 - u) ** 1.5
            for sc, a, dark in ((1.3, 0.25, 1.0), (0.85, 0.45, 0.7)):
                c = tuple(int(v * dark) for v in self.col["smoke"])
                out.append((place(self.blobs[bi], x, y, s * sc, ph + 0.3 * u), c, a * fade))
        return out

    def debris(self, t, t0=0):
        if t < t0:
            return []
        tt = self.held(t - t0, fast=(t - t0) < 4)  # 처음 몇 장은 매 프레임(빠른 순간)
        rng = random.Random(self.seed * 1000 + 13)  # 시드마다 다른 모양(같은 시드면 같은 결과)
        out = []
        v0, half, g = self.st["debris_v0"], self.st["debris_half"], self.st["debris_gravity"]
        k = math.log(2) / half
        for i in range(int(self.st["debris_count"])):
            ang = rng.uniform(-math.pi, 0.15) if rng.random() < 0.8 else rng.uniform(0, math.pi)
            sp = v0 * rng.uniform(0.5, 1.6) * 6
            dist = sp * (1 - math.exp(-k * tt)) / k  # 속도가 반감기 half로 줄어든다
            x = self.cx + math.cos(ang) * dist * W / H * 0.5
            y = self.cy + math.sin(ang) * dist + 0.5 * g * tt * tt
            if y > 1.1:
                continue
            s = rng.uniform(0.008, 0.03)
            bi = rng.randrange(len(self.blobs))
            spin = rng.uniform(-0.4, 0.4) * tt
            out.append((place(self.blobs[bi], x, y, s, spin), (60, 64, 70), 1.0))
            out.append((place(self.blobs[bi], x - s * 0.15, y - s * 0.15, s * 0.6, spin), self.col["dust"], 0.8))
        return out

    def shockwave(self, t, t0=0, life=10):
        u = (t - t0) / life
        if u < 0 or u > 1:
            return []
        r = 0.05 + self.st["shock_speed"] * (t - t0) * (1.6 - 0.6 * u)
        fade = 1 - u
        out = []
        segs = 18
        for m in range(segs):
            ang = m / segs * 2 * math.pi
            wi = (m * 5) % len(self.wedges)
            for sc, ck, a in ((0.09, "orange", 0.5), (0.05, "cream", 0.85)):
                sh = place(self.wedges[wi], self.cx + math.cos(ang) * r, self.cy + math.sin(ang) * r * 0.55, sc * (1 - 0.4 * u),
                           ang + math.pi / 2 - axis(self.wedges[wi]))
                out.append((sh, self.col[ck], a * fade))
        return out

    def flash(self, t, t0=0):
        n = int(self.st["flash_frames"])
        if not (t0 <= t < t0 + n + 3):
            return []
        if t < t0 + n:
            x1, y1 = W, H
            box = [{"hole": False, "segs": [[0, 0, x1 / 2, 0, x1, 0], [x1, 0, x1, y1 / 2, x1, y1], [x1, y1, x1 / 2, y1, 0, y1],
                                             [0, y1, 0, y1 / 2, 0, 0]], "cid": 0, "parent": -1}]
            if not self.scenes:  # 단색 섬광: 화면 전체(사각 윤곽을 곡선 4개로)
                return [(box, self.col["white"], 1.0)]
            # 나카무라 임팩트 프레임(흑백 실루엣·먹선 장면)을 한 장씩: 바탕 = 먹의 반대색, 장면이 화면을 덮도록 키운다
            name, frs = self.scenes[self.rng_scene]
            white_ink, w, groups = frs[min(t - t0, len(frs) - 1)]
            ink, paper = ((255, 255, 255), (0, 0, 0)) if white_ink else ((0, 0, 0), (255, 255, 255))
            sc = max(H, W / w)
            ox, oy = W / 2 - w * sc / 2, H / 2 - sc / 2
            out = [(box, paper, 1.0)]
            for gi, g in enumerate(groups):
                shapes = [{"hole": bool(h), "segs": (np.array(sg).reshape(-1, 2) * sc + [ox, oy]).reshape(-1, 6).tolist(),
                           "cid": ci, "parent": 0 if h else -1} for ci, (h, sg) in enumerate(g)]
                out.append((shapes, ink, 1.0))
            return out
        u = (t - t0 - n) / 3
        out = []
        rng = random.Random(self.seed * 1000 + 17)  # 시드마다 다른 모양(같은 시드면 같은 결과)
        for m in range(12):  # 섬광 뒤 방사형 가시(쐐기), 빠르게 옅어짐
            ang = (m + rng.random() * 0.6) / 12 * 2 * math.pi
            wi = (m * 7) % len(self.wedges)
            ln = rng.uniform(0.05, 0.1) * (1 + 0.5 * u)
            d = 0.06 + ln * 1.1
            for sc, ck, a in ((1.3, "red", 0.35), (1.0, "orange", 0.6), (0.6, "cream", 0.9)):
                out.append((place(self.wedges[wi], self.cx + math.cos(ang) * d, self.cy + math.sin(ang) * d, ln * sc,
                                  ang - axis(self.wedges[wi])), self.col[ck], a * (1 - u)))
        return out

    def frame(self, kind, t):
        if kind == "impact":
            n = int(self.st["flash_frames"])
            return (self.smoke(t, n + 6) + self.explosion(t, n, int(self.N * 0.6)) + self.debris(t, n) +
                    self.shockwave(t, n) + self.flash(t, 0))
        return getattr(self, kind)(t)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("fx")
    ap.add_argument("pal")
    ap.add_argument("out")
    ap.add_argument("--kind", default="impact")
    ap.add_argument("--frames", type=int, default=48)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--bg", default="0,0,0")
    ap.add_argument("--stats")
    ap.add_argument("--check")
    ap.add_argument("--scenes", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "p3",
                                                       "impact_scenes_fxonly_2026-10-22.txt"),
                    help="쓸 임팩트 장면 이름 목록(이펙트만 — 인물 실루엣 장면 제외). 빈 문자열이면 전부")
    a = ap.parse_args()
    st = dict(DEFAULT)
    if a.stats:
        st.update(json.load(open(a.stats)))
    wedges, blobs = load_lib(a.fx)
    scenes = load_scenes(a.fx)
    if a.scenes and os.path.exists(a.scenes):
        ok = {l.strip() for l in open(a.scenes, encoding="utf-8") if l.strip() and not l.startswith("#")}
        scenes = [sc for sc in scenes if sc[0] in ok]
    g = Gen(wedges, blobs, load_pal(a.pal), a.seed, a.frames, st, scenes=scenes)
    if g.scenes:
        g.rng_scene = random.Random(a.seed * 977).randrange(len(g.scenes))
        print("임팩트 장면", g.scenes[g.rng_scene][0])
    bg = [int(v) for v in a.bg.split(",")]
    wr = Writer()
    body = []
    for t in range(a.frames):
        out = [f'<Frame BackgroundColor="{argb(bg) & 0xFFFFFFFF}" ID="{t + 1}" Position="{t}">',
               '<LayerDef ID="0" Name="Layer 1" Visible="true" Locked="false" />']
        for shapes, bgr, alpha in g.frame(a.kind, t):
            if alpha > 0.01:
                wr.fill(out, shapes, W, argb(bgr, min(1.0, alpha)), 0, 0.02)
        out.append("</Frame>")
        body.append("\n".join(out))
    name = os.path.splitext(os.path.basename(a.out))[0]
    xml = (f"<?xml version='1.0' encoding='utf-8'?>\n<Sequence Name=\"{name}\" HeightWidthRatio=\"0.5625\" RatioX=\"16\" RatioY=\"9\" "
           f"FrameCount=\"{a.frames}\" BackgroundColor=\"{argb(bg)}\">\n" + "\n".join(body) + "\n</Sequence>\n")
    with zipfile.ZipFile(a.out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(name + ".xml", xml)
    print(a.kind, "프레임", a.frames, "AO", wr.oid - 1, "크기MB", round(os.path.getsize(a.out) / 1e6, 2))
    if a.check:
        import subprocess
        import cv2
        tmp = a.check + "_r"
        idx = [0, 2, 4, 7, 11, 16, 23, 31, 40]
        idx = [i for i in idx if i < a.frames]
        subprocess.run([sys.executable, os.path.join(os.path.dirname(__file__), "sfa_render.py"), a.out, tmp,
                        "--frames", ",".join(map(str, idx)), "--size", "480x270"], check=True, capture_output=True)
        ims = [cv2.imread(os.path.join(tmp, f"f{i:04d}.png")) for i in idx]
        for i, im in zip(idx, ims):
            cv2.putText(im, str(i), (5, 18), 0, 0.6, (0, 0, 255), 2)
        while len(ims) % 3:
            ims.append(np.zeros_like(ims[0]))
        cv2.imwrite(a.check, np.vstack([np.hstack(ims[i:i + 3]) for i in range(0, len(ims), 3)]), [cv2.IMWRITE_JPEG_QUALITY, 80])


if __name__ == "__main__":
    main()
