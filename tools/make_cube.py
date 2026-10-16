#!/usr/bin/env python3
"""돌 큐브 폭발 SFA (손으로 짠 연출, 학습 모델 아님). (트위닝, 재생) = (24, 24), 120프레임.

정지 → 떨림·클로즈업 라이즈 → 나카무라식 임팩트 프레임 6장(반전 레이어 알파) → 톱니 폭발(펑)·폭발 후 진동
→ 모서리 깎인 돌 파편(중력·반발·구르기) → 가운데에서 터져 퍼지는 덩어리 먼지 → 바람 → 정리.
스토리보드: 대화에서 확정한 8컷 + 임팩트 6장.

  python tools/make_cube.py OUT.sfa [--preview OUT.mp4 --size 960x540]
"""
import argparse
import math
import random
import sys
from pathlib import Path

import cv2
import numpy as np
from scipy.spatial import ConvexHull

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tools'))
import make_duel as md  # noqa: E402
import make_copy as mc  # noqa: E402

W, H = md.W, md.H
N = 120
argb, CLEAR = md.argb, md.CLEAR

BG = argb(196, 192, 184)
GRID = argb(176, 172, 164)
INK = argb(40, 38, 36)
TOP, MID, DARK = argb(222, 218, 208), argb(178, 174, 166), argb(70, 67, 63)
SHADOW = argb(160, 156, 148)
SPECK = argb(112, 108, 102)
D_LINE, D_SHADE, D_LITE, D_BASE = argb(52, 50, 48), argb(128, 124, 120), argb(226, 223, 216), argb(186, 182, 176)
CORE, RAY = (250, 248, 242), (62, 58, 54)
K, Wt = (16, 15, 14), (246, 244, 238)

LAYERS = [('ground', '땅·그림자'), ('dust_b_shade', '뒤 먼지 실루엣'), ('dust_b_lite', '뒤 먼지 밝은 몸통'),
          ('dust_b_base', '뒤 먼지 테두리·그림자 혀'), ('dust_b_tail', '뒤 먼지 줄무늬'), ('cube', '큐브·잔해'),
          ('blast', '폭발'), ('dust_f_shade', '앞 먼지 실루엣'), ('dust_f_lite', '앞 먼지 밝은 몸통'),
          ('dust_f_base', '앞 먼지 테두리·그림자 혀'), ('dust_f_tail', '앞 먼지 줄무늬'), ('debris', '돌 파편'),
          ('fx', '바람·줄무늬'), ('imp_bg', '반전 면(알파)'), ('imp_fg', '임팩트 선')]


def ease_out(s):
    s = min(max(s, 0.0), 1.0)
    return 1 - (1 - s) ** 2


def ease_in(s):
    s = min(max(s, 0.0), 1.0)
    return s * s


# ----------------------------------------------------------------------------- camera
AZ, EL = math.radians(38), math.radians(34)


class Cam:
    """사선 부감 고정 카메라. zoom은 화면 중심 기준 클로즈업, (sx, sy)는 진동."""

    def __init__(self, zoom=1.0, sx=0.0, sy=0.0):
        self.sc = 168 * zoom
        self.cx, self.cy = W / 2 + sx, H * 0.60 + sy + 40 * (zoom - 1)

    def __call__(self, x, y, z):
        xr = x * math.cos(AZ) - y * math.sin(AZ)
        yr = x * math.sin(AZ) + y * math.cos(AZ)
        d = 1 + 0.035 * yr
        return (self.cx + self.sc * xr / d, self.cy + self.sc * (yr * math.sin(EL) - z * math.cos(EL)) / d)

    def depth(self, x, y):
        return x * math.sin(AZ) + y * math.cos(AZ)


VIEW = np.array([math.sin(AZ), math.cos(AZ), 1.2])
_L = np.array([-math.cos(AZ) * .9, math.sin(AZ) * .9, 1.0])
LIGHT = _L / np.linalg.norm(_L)


def shake_at(t):
    """진동: 라이즈(8–19) 점점 커짐, 임팩트(20–31) 최대, 폭발 후(32–60) 감쇠, 착지 여진(66–71)."""
    r = random.Random(t * 31 + 7)
    if 8 <= t < 20:
        a = 2 + 1.3 * (t - 8)
    elif 20 <= t < 32:
        a = 16
    elif 32 <= t < 62:
        a = 24 * (1 - (t - 32) / 30) ** 1.5
    elif 66 <= t < 72:
        a = 7 * (1 - (t - 66) / 6)
    else:
        return 0.0, 0.0
    s = 1 if t % 2 else -1
    return s * a * r.uniform(.7, 1.0), -s * a * .6 * r.uniform(.5, 1.0)


def cam_at(t):
    sx, sy = shake_at(t)
    if 8 <= t < 32:
        z = 1 + 0.18 * ease_in((t - 8) / 12) if t < 20 else 1.18
        return Cam(z, sx, sy)
    return Cam(1.0, sx, sy)


# ----------------------------------------------------------------------------- stone
def face_polys(V, hull_eq_simp, cam, view=VIEW):
    """볼록 다면체의 보이는 면: [(normal, [2D 점…])]."""
    groups = {}
    for simp, eq in hull_eq_simp:
        groups.setdefault(tuple(np.round(eq[:3], 3)), set()).update(simp.tolist())
    out = []
    for n, idx in groups.items():
        n = np.array(n)
        yield_n = n
        if np.dot(yield_n, view) <= 0:
            continue
        pts = [cam(*V[i]) for i in idx]
        if len(pts) >= 3:
            try:
                hv = ConvexHull(np.array(pts)).vertices
                pts = [pts[i] for i in hv]
            except Exception:
                continue
        out.append((yield_n, pts))
    return out


def tone(n):
    lit = float(np.dot(n, LIGHT))
    return TOP if lit > .6 else (MID if lit > -.15 else DARK)


class Rock:
    def __init__(self, seed, size):
        r = random.Random(seed)
        d = np.array([1, r.uniform(.55, 1), r.uniform(.35, .8)]) * size / 2
        chip = set(r.sample(range(8), r.randint(1, 3)))
        pts, ci = [], -1
        for sx in (-1, 1):
            for sy in (-1, 1):
                for sz in (-1, 1):
                    c = np.array([sx, sy, sz]) * d
                    ci += 1
                    if ci in chip:
                        for ax in range(3):
                            q = c.copy()
                            q[ax] -= np.sign(c[ax]) * 2 * d[ax] * r.uniform(.12, .35)
                            pts.append(q)
                    else:
                        pts.append(c)
        self.v = np.array(pts)
        self.hull = ConvexHull(self.v)
        # 패인 홈: 가장 넓은 면 가장자리에 고정(로컬 좌표)
        top = max(range(len(self.hull.equations)), key=lambda i: self.hull.equations[i][2])
        n = self.hull.equations[top][:3]
        on = [i for i in range(len(self.v)) if abs(np.dot(self.v[i], n) + self.hull.equations[top][3]) < 1e-6]
        cen = self.v[on].mean(0)
        a, b = self.v[on[0]], self.v[on[1 % len(on)]]
        m = a + (b - a) * r.uniform(.35, .65)
        u = (b - a) / (np.linalg.norm(b - a) + 1e-9)
        inn = cen - m
        inn /= np.linalg.norm(inn) + 1e-9
        w_ = size * r.uniform(.08, .14)
        self.notch_n = n
        self.notch = [m - u * w_, m + inn * size * r.uniform(.12, .22), m + u * w_]
        self.crack = [self.notch[1], self.notch[1] + inn * size * .25 + u * size * r.uniform(-.15, .15)]

    @staticmethod
    def _rot(v, rot, tilt):
        v = np.atleast_2d(v)
        x, y, z = v[:, 0], v[:, 1], v[:, 2]
        x, y = x * math.cos(rot) - y * math.sin(rot), x * math.sin(rot) + y * math.cos(rot)
        y, z = y * math.cos(tilt) - z * math.sin(tilt), y * math.sin(tilt) + z * math.cos(tilt)
        return np.stack([x, y, z], 1)

    def draw(self, fr, cam, c, rot, tilt, th=.4):
        V = self._rot(self.v, rot, tilt)
        lift = max(0.0, -(V[:, 2].min() + c[2]))
        V = V + np.array(c) + np.array([0, 0, lift])
        eqs = [(s, np.concatenate([self._rot(e[:3], rot, tilt)[0], [0]])) for s, e in zip(self.hull.simplices, self.hull.equations)]
        for n, pts in face_polys(V, eqs, cam):
            fr.poly(pts, tone(n), INK, th)
        nn = self._rot(self.notch_n, rot, tilt)[0]
        if np.dot(nn, VIEW) > 0.15:
            off = np.array(c) + np.array([0, 0, lift])
            q = [cam(*p) for p in self._rot(np.array(self.notch), rot, tilt) + off]
            fr.poly(q, DARK, INK, th * .6)
            k = [cam(*p) for p in self._rot(np.array(self.crack), rot, tilt) + off]
            fr.line(k[0], k[1], INK, .18)


# ----------------------------------------------------------------------------- debris physics
def debris_paths():
    r = random.Random(11)
    out = []
    for i in range(34):
        big = i < 12
        a = 2 * math.pi * i / (12 if big else 22) + r.uniform(-.25, .25)
        v = r.uniform(.08, .17) * (1 if big else 1.25)
        p = np.array([r.uniform(-.4, .4), r.uniform(-.4, .4), 1.4])
        vel = np.array([v * math.cos(a), v * math.sin(a), r.uniform(.12, .3)])
        size = r.uniform(.28, .6) if big else r.uniform(.09, .18)
        rot, tilt = r.uniform(0, 6), r.uniform(0, 6)
        spin, tspin = r.uniform(.2, .5) * r.choice((-1, 1)), r.uniform(.15, .4)
        path = []
        for f in range(N):
            vel[2] -= .018
            p = p + vel
            if p[2] < size / 2:
                p[2] = size / 2
                if abs(vel[2]) > .03:
                    vel[2] = -vel[2] * .45
                    vel[:2] *= .7
                    spin *= -.6
                    tspin *= .5
                else:
                    vel[2] = 0
                    vel[:2] *= .85
                    spin *= .85
                    tspin *= .7
            rot += spin
            tilt += tspin
            path.append((p.copy(), rot, tilt))
        out.append((Rock(100 + i, size), size, path))
    return out


DEBRIS = debris_paths()
T_BOOM = 32


# ----------------------------------------------------------------------------- dust (덩어리 실루엣)
def _dust_lobes():
    r = random.Random(5)
    L = []
    for i in range(78):
        a = r.uniform(0, 2 * math.pi)
        el = min(abs(r.gauss(0, .55)), 1.3)
        L.append(dict(a=a, el=el, rf=r.uniform(.3, 1.08), sz=r.uniform(.6, 1.2), k=r.uniform(.6, 1.4),
                      die=r.uniform(.75, 1.0), sh=r.random() < .35))
    return L


LOBES = _dust_lobes()


def dust_lobes_at(t, cam):
    """중심에서 터져 공처럼 부풀고(33–60), 낮게 퍼지며 가운데가 걷히고(60–80), 바람에 끌려 흩어짐(80–118).
    덩어리: (x, y, 반지름, 바람 끌림, 몸통 그림자 여부)."""
    if t < T_BOOM + 1:
        return [], []
    g = ease_out((t - T_BOOM - 1) / 40)
    R = .4 + 3.9 * g
    zc, flat = .8 - .4 * g, .55 - .2 * g
    wind = ease_in((t - 66) / 50) if t >= 66 else 0.0
    back, front = [], []
    for L in LOBES:
        rr = R * L['rf']
        life = 1.0
        if L['rf'] < .7 and t > 55:                       # 가운데부터 걷힘
            life *= max(0.0, 1 - (t - 55) / (22 * L['die']))
        if t > 82:
            life *= max(0.0, 1 - (t - 82) / (34 * L['die']))
        if life < .06:
            continue
        x = rr * math.cos(L['el']) * math.cos(L['a'])
        y = rr * math.cos(L['el']) * math.sin(L['a'])
        z = zc + rr * math.sin(L['el']) * flat * (1 - .6 * wind)      # 흩어질수록 낮게 깔림
        sx, sy = cam(x, y, z)
        sx += wind * 260 * L['k']
        sy -= wind * 30 * L['k']
        s = 105 * L['sz'] * (1.15 - .5 * L['el']) * (.45 + .75 * g) * (.2 + .8 * life)
        if s < 10:
            continue
        (front if cam.depth(x, y) > 0 else back).append((sx, sy, s, wind * L['k'], L['sh']))
    return back, front


DS = 2.0                                                   # 덩어리 윤곽 마스크: SFA px / 마스크 px (960x540)
L2 = np.array([-.6, -.8])                                  # 화면에서 빛이 오는 쪽(왼쪽 위)


def _body_mask(lobes):
    hh, ww = int(H / DS), int(W / DS)
    m = np.zeros((hh, ww), np.uint8)
    for x, y, s, w, _ in lobes:
        ax, ay = s * (1 + 1.4 * w), s * .86 * (1 - .3 * min(w, 1))
        cv2.ellipse(m, (int(x / DS), int(y / DS)), (max(1, int(ax / DS)), max(1, int(ay / DS))), 0, 0, 360, 255, -1)
    return (cv2.GaussianBlur(m, (0, 0), 3.0) > 110).astype(np.uint8) * 255      # 큰 형태만 남김


def _outlines(m, min_area=60):
    """마스크의 큰 윤곽(SFA px, 시계 방향). 구멍은 아래로 1px 틈을 내어 바깥 고리에 합친다."""
    m = m.copy()
    cs, hier = cv2.findContours(m, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
    if hier is not None and (hier[0][:, 3] >= 0).any():
        for c, h in zip(cs, hier[0]):
            if h[3] >= 0:
                x, y = c[c[:, 0, 1].argmax(), 0]
                m[y:, x:x + 1] = 0
        cs, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    out = []
    for c in cs:
        if cv2.contourArea(c) < min_area:
            continue
        P = cv2.approxPolyDP(c, 1.0, True).reshape(-1, 2).astype(float) * DS
        area = .5 * np.sum(P[:, 0] * np.roll(P[:, 1], -1) - np.roll(P[:, 0], -1) * P[:, 1])
        if area < 0:
            P = P[::-1]
        out.append(P)
    return out


def _at(P, cum, s):
    s %= cum[-1]
    i = int(np.searchsorted(cum, s, 'right') - 1)
    i = min(i, len(P) - 1)
    t = (s - cum[i]) / max(cum[i + 1] - cum[i], 1e-9)
    return P[i] + (P[(i + 1) % len(P)] - P[i]) * t


def _q(a, c, b, t):
    return (1 - t) ** 2 * a + 2 * t * (1 - t) * c + t * t * b


def cloud_bulges(P, seed, scale, width=1.0, height=(.26, .42)):
    """윤곽을 따라 비대칭 볼록들을 곡선으로 설계: 골(뾰족) → 어깨 → 꼭대기 → 어깨 → 다음 골.
    볼록마다 폭·높이·기울기가 다르고, 가끔 납작한 볼록과 길게 뻗은 가시 볼록이 섞인다."""
    r = random.Random(seed)
    seg = np.vstack([P, P[:1]])
    cum = np.concatenate([[0], np.cumsum(np.hypot(*np.diff(seg, axis=0).T))])
    L = cum[-1]
    mean_w = max(40.0, 125 * scale * width)
    n = max(4, int(round(L / mean_w)))
    x0 = int(np.argmin(P[:, 0]))                           # 시작점: 가장 왼쪽(프레임 사이 안정)
    s0 = cum[x0]
    cuts = sorted(s0 + L * (k + r.uniform(-.28, .28)) / n for k in range(n))
    bul = []
    for k in range(n):
        sa, sb = cuts[k], cuts[(k + 1) % n] + (L if k == n - 1 else 0)
        A, B = _at(P, cum, sa), _at(P, cum, sb)
        M = _at(P, cum, (sa + sb) / 2)
        tg = B - A
        w = np.hypot(*tg) or 1.0
        tg = tg / w
        nrm = np.array([tg[1], -tg[0]])                    # 시계 방향 윤곽의 바깥쪽
        kind = r.random()
        h = w * (r.uniform(*height) if kind < .82 else (r.uniform(.14, .22) if kind < .95 else r.uniform(.65, .85)))
        lean = r.uniform(-.22, .22)
        Pk = M + nrm * h + tg * w * lean                   # 꼭대기(비대칭)
        # 꼭대기에서 두 곡선의 접선이 이어지게(둥근 꼭대기), 골은 뾰족하게 남김
        c1 = Pk - tg * w * r.uniform(.36, .46) + nrm * h * .05
        c2 = Pk + tg * w * r.uniform(.36, .46) + nrm * h * .05
        bul.append(dict(A=A, B=B, P=Pk, c1=c1, c2=c2, n=nrm, h=h, w=w))
    return bul


def _ring(bul):
    ring = []
    for b in bul:
        ring += [tuple(b['A']), tuple(b['c1']), tuple(b['P']), tuple(b['c2'])]
    return ring


def draw_dust(fr, lobes, side):
    """애니 먼지(Sakugabooru smoke·debris 참고)를 곡선으로 직접 설계.
    ① 실루엣: 큰 비대칭 볼록 곡선 고리, 그림자색 + 곡선 자체가 짙은 외곽선
    ② 밝은 몸통: 실루엣을 깎고 왼쪽 위로 민 형태에 다시 볼록 곡선 → 오른쪽 아래에 볼록한 경계의 그림자 덩어리가 남음
    ③ 밝은 테두리: 왼쪽 위를 향한 몸통 볼록의 얇은 초승달
    ④ 그림자 혀: 몸통 골에서 안쪽으로 짧게 휘어 들어가는 뾰족한 그림자
    ⑤ 흩어질 때 줄무늬 꼬리"""
    if not lobes:
        return
    scale = float(np.median([l[2] for l in lobes])) / 60
    body = _body_mask(lobes)
    mw = max(40.0, 125 * scale) / DS
    k = max(2, int(mw * .2))
    lit = cv2.erode(body, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * k + 1, 2 * k + 1)))
    lit = cv2.warpAffine(lit, np.float32([[1, 0, -.12 * mw], [0, 1, -.18 * mw]]), (lit.shape[1], lit.shape[0]))
    lit = cv2.bitwise_and(lit, cv2.erode(body, np.ones((5, 5), np.uint8)))
    base_seed = int(len(lobes)) * 7 + (1 if side == 'f' else 0)
    fr.layer = f'dust_{side}_shade'
    for ci, P in enumerate(_outlines(body)):
        fr.cpoly(_ring(cloud_bulges(P, base_seed + ci, scale)), D_SHADE, D_LINE, .7)
    for ci, P in enumerate(_outlines(lit, 30)):
        seed = base_seed + 100 + ci
        bul = cloud_bulges(P, seed, scale, .8, (.28, .42))
        fr.layer = f'dust_{side}_lite'
        fr.cpoly(_ring(bul), D_BASE)
        r = random.Random(seed + 7)
        for i, b in enumerate(bul):
            face = float(np.dot(b['n'], L2))
            A, B, Pk, c1, c2, nrm = b['A'], b['B'], b['P'], b['c1'], b['c2'], b['n']
            if face > .4:                                   # 밝은 테두리(꼭대기 쪽 얇은 초승달)
                d = b['h'] * r.uniform(.18, .28)
                a2, b2 = _q(A, c1, Pk, .3), _q(Pk, c2, B, .7)
                ca, cb = _q(A, c1, Pk, .68), _q(Pk, c2, B, .32)
                fr.layer = f'dust_{side}_base'
                fr.cpoly([tuple(a2), tuple(ca), tuple(Pk), tuple(cb), tuple(b2), tuple(Pk - nrm * d)], D_LITE)
            elif face < -.1 and r.random() < .55:            # 그림자 혀: 골에서 짧게 휘어 들어감
                ln = b['w'] * r.uniform(.25, .45)
                tg = (B - A) / (b['w'] or 1)
                inn = -(nrm + bul[i - 1]['n']) / 2
                inn /= np.hypot(*inn) or 1
                tip = A + inn * ln + tg * ln * r.uniform(-.3, .3)
                wd = b['w'] * r.uniform(.06, .1)
                a1, a2_ = A - tg * wd, A + tg * wd
                bend = r.uniform(-.2, .2) * ln
                fr.layer = f'dust_{side}_base'
                fr.cpoly([tuple(a1), tuple((a1 + tip) / 2 + tg * bend), tuple(tip), tuple((a2_ + tip) / 2 + tg * bend)], D_SHADE)
    fr.layer = f'dust_{side}_tail'
    r = random.Random(int(sum(l[0] for l in lobes)))
    for x, y, s, w, _ in lobes:                             # 흩어지는 줄무늬 꼬리: 휘며 가늘어지는 곡선
        if w > .25:
            for j in range(2):
                x0, y0 = x + s * (.2 + .5 * j) * (1 + w), y + s * r.uniform(-.35, .35)
                L = (50 + 170 * w) * r.uniform(.7, 1.2)
                a, m_, b = (x0, y0), (x0 + L * .5, y0 - 14 + 10 * j), (x0 + L, y0 - 4)
                fr.curve(a, m_, b, D_SHADE, .8 - .3 * j)


# ----------------------------------------------------------------------------- scene parts
def ground(fr, cam):
    fr.layer = 'ground'
    for i in range(-8, 9, 2):
        fr.line(cam(i, -9, 0), cam(i, 9, 0), GRID, .12)
        fr.line(cam(-9, i, 0), cam(9, i, 0), GRID, .12)


def cube(fr, cam, t):
    fr.layer = 'ground'
    fr.poly([cam(-.7, -.7, 0), cam(1.5, -.7, 0), cam(1.5, 1.5, 0), cam(-.7, 1.5, 0)], SHADOW)
    fr.layer = 'cube'
    top = [cam(-1, -1, 2), cam(1, -1, 2), cam(1, 1, 2), cam(-1, 1, 2)]
    right = [cam(1, -1, 2), cam(1, 1, 2), cam(1, 1, 0), cam(1, -1, 0)]
    front = [cam(-1, 1, 2), cam(1, 1, 2), cam(1, 1, 0), cam(-1, 1, 0)]
    fr.poly(top, TOP, INK, .55)
    fr.poly(front, MID, INK, .55)
    fr.poly(right, DARK, INK, .55)
    r = random.Random(1)                                   # 돌 질감: 점·패인 자국(금 없음)
    for _ in range(46):
        u, v = r.uniform(-.92, .92), r.uniform(-.92, .92)
        face = r.choice('trf')
        p = {'t': (u, v, 2.0), 'r': (1.0, u, 1 + v), 'f': (u, 1.0, 1 + v)}[face]
        c = cam(*p)
        fr.circle(c, r.uniform(1.6, 4.2) * cam.sc / 168, CLEAR, .06, None, fill=SPECK)


def _jag(x, y):
    return .9 + .35 * math.sin(3.1 * x + 1.7 * y) + .25 * math.cos(5 * y - x)


def remnant(fr, cam):
    fr.layer = 'ground'
    fr.poly([cam(-.7, -.7, 0), cam(1.5, -.7, 0), cam(1.5, 1.5, 0), cam(-.7, 1.5, 0)], SHADOW)
    fr.layer = 'cube'
    for (a, b), col in ((((1, -1), (1, 1)), DARK), (((-1, 1), (1, 1)), MID)):
        edge = [(a[0] + (b[0] - a[0]) * s, a[1] + (b[1] - a[1]) * s) for s in np.linspace(0, 1, 9)]
        pts = [cam(x, y, 0) for x, y in edge] + [cam(x, y, _jag(x, y)) for x, y in edge[::-1]]
        fr.poly(pts, col, INK, .55)
    rim = ([(-1, 1), (1, 1), (1, -1)] + [(-1 + 2 * s, -1) for s in np.linspace(1, 0, 6)][1:]
           + [(-1, -1 + 2 * s) for s in np.linspace(0, 1, 6)][1:])
    fr.poly([cam(x, y, _jag(x, y)) for x, y in rim], argb(214, 210, 200), INK, .45)
    for x, y in ((-.4, .2), (.3, -.3), (.5, .5)):
        fr.line(cam(x, y, _jag(x, y)), cam(x + .3, y - .2, _jag(x + .3, y - .2)), INK, .15)


def tri(fr, p0, p1, w, color):
    """끝이 뾰족한 붓 획 = 삼각형 채우기."""
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    L = math.hypot(dx, dy) or 1
    nx, ny = -dy / L * w / 2, dx / L * w / 2
    fr.poly([(p0[0] + nx, p0[1] + ny), p1, (p0[0] - nx, p0[1] - ny)], color)


def rays(fr, c, r0, r1, n, color, wmax, seed, inward=False, spread=(0, 2 * math.pi), sy=1.0):
    r = random.Random(seed)
    for _ in range(n):
        a = r.uniform(*spread)
        a0, a1 = r0 * r.uniform(.85, 1.25), r1 * r.uniform(.45, 1.1)
        p0 = (c[0] + a0 * math.cos(a), c[1] + a0 * math.sin(a) * sy)
        p1 = (c[0] + a1 * math.cos(a), c[1] + a1 * math.sin(a) * sy)
        if inward:
            p0, p1 = p1, p0
        w = r.uniform(2, wmax)
        if w > 7 and r.random() < .6:                      # 붓털 갈래: 두 가닥, 길이 다름
            dx, dy = p1[0] - p0[0], p1[1] - p0[1]
            L = math.hypot(dx, dy) or 1
            nx, ny = -dy / L, dx / L
            for o, k in ((-w * .25, r.uniform(.7, 1.0)), (w * .25, r.uniform(.5, .9))):
                tri(fr, (p0[0] + nx * o, p0[1] + ny * o), (p0[0] + dx * k, p0[1] + dy * k), w * .55, color)
        else:
            tri(fr, p0, p1, w, color)


def jag_core(fr, c, R, color, seed, sx=1.25, sy=.85, spikes=70):
    r = random.Random(seed)
    fr.poly([(c[0] + R * sx * math.cos(a), c[1] + R * sy * math.sin(a)) for a in np.linspace(0, 2 * math.pi, 40, endpoint=False)], color)
    for i in range(spikes):
        a = 2 * math.pi * i / spikes + r.uniform(-.03, .03)
        L = R * r.uniform(.12, .32) * (3 if r.random() < .07 else 1)
        b = (c[0] + R * .97 * sx * math.cos(a), c[1] + R * .97 * sy * math.sin(a))
        tip = (c[0] + (R + L) * sx * math.cos(a), c[1] + (R + L) * sy * math.sin(a))
        tri(fr, b, tip, R * r.uniform(.07, .14), color)


def chunk(c, s, rot):
    return [(c[0] + s * math.cos(rot + a) * k, c[1] + s * math.sin(rot + a) * k)
            for a, k in ((0, 1), (1.3, .8), (2.4, 1.05), (3.6, .85), (4.9, .95))]


# ----------------------------------------------------------------------------- impact frames (21–32f)
def impact(fr, cam, k, sub):
    """k: 0..5 = IF1..IF6, sub: 같은 그림의 2번째 프레임(획이 살짝 달라짐)."""
    c = cam(0, 0, 1.2)
    z = cam.sc / 168
    sd = 40 + k * 10 + sub
    fr.layer = 'imp_bg'
    full = [(-80, -80), (W + 80, -80), (W + 80, H + 80), (-80, H + 80)]
    dark_bg = k in (0, 2, 3)
    alpha = {0: 235, 1: 255, 2: 255, 3: 245, 4: 255, 5: 250}[k]
    fr.poly(full, argb(*(K if dark_bg else Wt), alpha))   # 반전 면: 이 프레임에서만 알파를 켬
    fr.layer = 'imp_fg'
    WH, BK = argb(*Wt), argb(*K)
    top = [cam(-1, -1, 2), cam(1, -1, 2), cam(1, 1, 2), cam(-1, 1, 2)]
    right = [cam(1, -1, 2), cam(1, 1, 2), cam(1, 1, 0), cam(1, -1, 0)]
    front = [cam(-1, 1, 2), cam(1, 1, 2), cam(1, 1, 0), cam(-1, 1, 0)]
    if k == 0:                                             # IF1 흑·집중선
        rays(fr, c, 300 * z, 1500, 300, WH, 16, sd)
        fr.poly(top, WH, WH, .5)
        fr.poly(right, BK, WH, .6)
        fr.poly(front, BK, WH, .6)
    elif k == 1:                                           # IF2 반전·윗면 방사
        rays(fr, c, 470 * z, 1500, 170, BK, 26, sd)
        for f in (right, front, top):
            fr.poly(f, BK)
        fr.line(right[0], right[1], WH, .3)
        tc = tuple(np.mean(top, 0))
        r = random.Random(sd)
        for _ in range(60):                                # 윗면 안에만: 면 경계까지의 거리로 길이 제한
            a = r.uniform(0, 2 * math.pi)
            u = (math.cos(a), math.sin(a))
            dmax = _ray_to_poly(tc, u, top)
            if dmax:
                tri(fr, (tc[0] + u[0] * 8, tc[1] + u[1] * 8), (tc[0] + u[0] * dmax * r.uniform(.6, .95), tc[1] + u[1] * dmax * r.uniform(.6, .95)), r.uniform(3, 9), WH)
    elif k == 2:                                           # IF3 십자 분할(원근 방향)
        r = random.Random(sd)
        for ax in ((1, 0), (0, 1)):
            for sg in (-1, 1):
                q = cam(sg * 9 * ax[0], sg * 9 * ax[1], 1.2)
                dx, dy = q[0] - c[0], q[1] - c[1]
                L = math.hypot(dx, dy)
                ux, uy = dx / L, dy / L
                nx, ny = -uy, ux
                g0, g1 = 90 * z, 34 * z
                far = (c[0] + ux * 2600, c[1] + uy * 2600)
                fr.poly([(c[0] + nx * g0, c[1] + ny * g0), (far[0] + nx * g1, far[1] + ny * g1),
                         (far[0] - nx * g1, far[1] - ny * g1), (c[0] - nx * g0, c[1] - ny * g0)], WH)
                for s in np.linspace(.04, 1, 36):
                    g = g0 + (g1 - g0) * s
                    for sdn in (-1, 1):
                        b = (c[0] + ux * 1800 * s + nx * sdn * g * .8, c[1] + uy * 1800 * s + ny * sdn * g * .8)
                        ln = r.uniform(16, 80) * (1.2 - s)
                        tri(fr, b, (b[0] + nx * sdn * ln + ux * ln * .6, b[1] + ny * sdn * ln + uy * ln * .6), r.uniform(6, 16), WH)
        rays(fr, c, 100 * z, 700, 90, WH, 10, sd + 1)
        jag_core(fr, c, 110 * z, WH, sd, 1.2, .9, 40)
    elif k == 3:                                           # IF4 톱니 폭발
        jag_core(fr, c, 380 * z, WH, sd, 1.25, .85, 90)
        rays(fr, c, 420 * z, 1300, 260, WH, 14, sd + 1)
        rays(fr, c, 110 * z, 420 * z, 150, BK, 10, sd + 2, inward=True)
        r = random.Random(sd + 3)
        for _ in range(10):
            a, rr, s = r.uniform(0, 6.3), r.uniform(120, 380) * z, r.uniform(22, 54) * z
            fr.poly(chunk((c[0] + rr * math.cos(a) * 1.2, c[1] + rr * math.sin(a) * .8), s, a), BK)
    elif k == 4:                                           # IF5 쐐기 가시
        r = random.Random(sd)
        for i in range(16):
            a = 2 * math.pi * i / 16 + r.uniform(-.12, .12)
            wd, r0 = r.uniform(.06, .16), r.uniform(180, 320) * z
            fr.poly([(c[0] + r0 * math.cos(a), c[1] + r0 * .8 * math.sin(a)),
                     (c[0] + 2400 * math.cos(a - wd), c[1] + 2400 * math.sin(a - wd)),
                     (c[0] + 2400 * math.cos(a + wd), c[1] + 2400 * math.sin(a + wd))], BK)
        rays(fr, c, 80 * z, 320 * z, 70, BK, 8, sd + 1, inward=True)
        for _ in range(12):
            a, rr, s = r.uniform(0, 6.3), r.uniform(150, 520) * z, r.uniform(24, 64) * z
            p = (c[0] + rr * math.cos(a), c[1] + rr * .8 * math.sin(a))
            fr.poly(chunk(p, s, a), BK, WH, .25)
            tri(fr, p, (p[0] - (p[0] - c[0]) * .5, p[1] - (p[1] - c[1]) * .5), s * 1.4, BK)
    else:                                                  # IF6 먹 얼룩 먼지
        r = random.Random(sd)
        for i in range(22):
            a = 2 * math.pi * i / 22 + r.uniform(-.1, .1)
            rr, s = r.uniform(300, 520) * z, r.uniform(100, 190) * z
            p = (c[0] + rr * math.cos(a) * 1.25, c[1] + rr * .7 * math.sin(a))
            fr.circle(p, s, CLEAR, .06, None, fill=BK)
            rays(fr, p, s * .7, s * 1.9, 12, BK, 12, sd + 10 + i, spread=(a - 1.0, a + 1.0))
        jag_core(fr, c, 240 * z, WH, sd + 2, 1.3, .8, 60)
        for _ in range(8):
            a, rr, s = r.uniform(0, 6.3), r.uniform(340, 600) * z, r.uniform(28, 60) * z
            fr.poly(chunk((c[0] + rr * math.cos(a) * 1.25, c[1] + rr * .7 * math.sin(a)), s, a), CLEAR, WH, .45)


def _ray_to_poly(o, u, poly):
    best = None
    for a, b in zip(poly, poly[1:] + poly[:1]):
        ex, ey = b[0] - a[0], b[1] - a[1]
        den = u[0] * ey - u[1] * ex
        if abs(den) < 1e-9:
            continue
        s = ((a[0] - o[0]) * ey - (a[1] - o[1]) * ex) / den
        v = ((a[0] - o[0]) * u[1] - (a[1] - o[1]) * u[0]) / den
        if s > 0 and 0 <= v <= 1:
            best = s if best is None else min(best, s)
    return best


# ----------------------------------------------------------------------------- explosion (33–44f)
def blast(fr, cam, t):
    s = (t - T_BOOM) / 11
    if not 0 <= s <= 1:
        return
    c = cam(0, 0, 1.4)
    fade = 1 - ease_in(max(0, (s - .55) / .45))
    a = int(255 * fade)
    if a <= 0:
        return
    fr.layer = 'blast'
    R = 300 * (.75 + .6 * ease_out(s))
    rays(fr, c, R * 1.05, R * 2.6, 150, argb(*RAY, a), 15, 70 + t)
    jag_core(fr, c, R, argb(*CORE, a), 80 + t, 1.25, .85, 80)
    if s < .5:
        rays(fr, c, 80, R * 1.05, 110, argb(*RAY, a), 9, 90 + t, inward=True)
    r = random.Random(t)                                   # 중심에서 뻗는 먼지 분사 줄기
    for i in range(14):
        ang = 2 * math.pi * i / 14 + r.uniform(-.15, .15)
        p0 = cam(.6 * math.cos(ang), .6 * math.sin(ang), .7)
        p1 = cam(3.2 * ease_out(s) * math.cos(ang), 3.2 * ease_out(s) * math.sin(ang), .5)
        tri(fr, p0, p1, r.uniform(14, 28), argb(128, 124, 120, a))


# ----------------------------------------------------------------------------- wind (67–104f)
def wind(fr, cam, t):
    if not 66 <= t < 106:
        return
    fr.layer = 'fx'
    s = (t - 66) / 40
    for band, (y0, amp, w) in enumerate(((H * .80, 14, .9), (H * .30, 20, .6), (H * .55, 10, .45))):
        head = -300 + (W + 700) * ease_out(s + band * .08)
        tail = head - 900
        pts = [(x, y0 + amp * math.sin(x / 90 + band * 2 + t * .15)) for x in np.linspace(tail, head, 13)]
        for i in range(0, 12, 2):
            th = w * math.sin(math.pi * (i + 1) / 12)
            fr.curve(pts[i], pts[i + 1], pts[i + 2], argb(70, 66, 62, 220), max(th, .1))
        e = pts[-1]                                         # 끝 말림
        cr = 26
        fr.curve(e, (e[0] + cr, e[1] - cr * .2), (e[0] + cr * .6, e[1] - cr * 1.2), argb(70, 66, 62, 220), w * .5)
        fr.curve((e[0] + cr * .6, e[1] - cr * 1.2), (e[0] - cr * .2, e[1] - cr * 1.5), (e[0] - cr * .1, e[1] - cr * .7), argb(70, 66, 62, 220), w * .35)


def pebbles(fr, cam, t):
    if t < 40:
        return
    fr.layer = 'ground'
    r = random.Random(6)
    n = min(70, int((t - 40) * 2.5))
    for i in range(n):
        a, rr = r.uniform(0, 2 * math.pi), r.uniform(1.6, 6.5)
        p = cam(rr * math.cos(a), rr * math.sin(a), 0)
        s = r.uniform(2.5, 6)
        fr.poly([(p[0] - s, p[1]), (p[0], p[1] - s * .7), (p[0] + s, p[1] - s * .2), (p[0] + s * .3, p[1] + s * .6)], DARK)


# ----------------------------------------------------------------------------- frame
def build_frame(t):
    cam = cam_at(t)
    fr = md.Frame2D(BG)
    ground(fr, cam)
    if t < T_BOOM:
        cube(fr, cam, t)
        if t >= 20:
            impact(fr, cam, (t - 20) // 2, (t - 20) % 2)
        return fr
    remnant(fr, cam)
    pebbles(fr, cam, t)
    blast(fr, cam, t)
    back, front = dust_lobes_at(t, cam)
    draw_dust(fr, back, 'b')
    draw_dust(fr, front, 'f')
    fr.layer = 'debris'
    for rock, size, path in DEBRIS:
        p, rot, tilt = path[t - T_BOOM]
        rock.draw(fr, cam, p, rot, tilt, .4 if size > .25 else .25)
    wind(fr, cam, t)
    return fr


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('out')
    ap.add_argument('--preview')
    ap.add_argument('--size', default='960x540')
    a = ap.parse_args(argv)
    import xml.etree.ElementTree as ET
    import sfa
    frames = [build_frame(t) for t in range(N)]
    root = write(frames, a.out)
    xml_bytes = len(ET.tostring(root))
    print(f'{N}프레임, XML {xml_bytes / 2**20:.1f} MB, AO 최대 {max(len(f.findall("AO")) for f in root.findall("Frame"))}개/프레임 → {a.out} (24,24)')
    if a.preview:
        md.preview(root, a.preview, tuple(int(v) for v in a.size.split('x')))
        print('미리보기 →', a.preview)


def write(frames, path):
    return mc.write(frames, LAYERS, 'stone_cube_burst', path)


if __name__ == '__main__':
    main()
