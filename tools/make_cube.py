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
KT = 1.9                                                   # 폭발 후 시간 압축(속도감): 같은 궤적을 1.9배 빠르게
argb, CLEAR = md.argb, md.CLEAR

BG = argb(196, 192, 184)
GRID = argb(176, 172, 164)
INK = argb(40, 38, 36)
TOP, MID, DARK = argb(222, 218, 208), argb(178, 174, 166), argb(70, 67, 63)
SHADOW = argb(160, 156, 148)
SPECK = argb(112, 108, 102)
D_LINE, D_SHADE, D_LITE, D_BASE = argb(126, 120, 110), argb(160, 153, 141), argb(232, 228, 218), argb(212, 206, 194)
D_DEEP = argb(136, 129, 118)
CORE, RAY = (250, 248, 242), (62, 58, 54)
K, Wt = (16, 15, 14), (246, 244, 238)

LAYERS = [('ground', '땅·그림자'), ('dust_b_shade', '뒤 먼지 실루엣'), ('dust_b_lite', '뒤 먼지 밝은 몸통'),
          ('dust_b_base', '뒤 먼지 테두리·그림자 혀'), ('dust_b_tail', '뒤 먼지 줄무늬'), ('cube', '큐브·잔해'),
          ('blast', '폭발'), ('dust_f_shade', '앞 먼지 실루엣'), ('dust_f_lite', '앞 먼지 밝은 몸통'),
          ('dust_f_base', '앞 먼지 테두리·그림자 혀'), ('dust_f_tail', '앞 먼지 줄무늬'), ('debris', '돌 파편'),
          ('fx', '바람·줄무늬'), ('imp_bg', '반전 면(알파)'), ('imp_bgtex', '임팩트 바탕 연필 결'),
          ('imp_fg', '임팩트 흑백 형태'), ('imp_tex', '임팩트 연필 결·잔털'), ('imp_glow', '임팩트 빛(글로우)')]


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
    """진동: 라이즈(8–19) 점점 커짐, 임팩트(20–31) 최대, 폭발 후(32–53) 크게 시작해 감쇠, 착지 여진(44–49)."""
    r = random.Random(t * 31 + 7)
    if 8 <= t < 20:
        a = 2 + 1.3 * (t - 8)
    elif 20 <= t < 32:
        a = 16
    elif 32 <= t < 54:
        a = 30 * (1 - (t - 32) / 22) ** 1.6
    elif 44 <= t < 50:                                     # 큰 파편 첫 착지 여진
        a = 8 * (1 - (t - 44) / 6)
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
        v = r.uniform(.08, .17) * (1 if big else 1.25) * KT
        p = np.array([r.uniform(-.4, .4), r.uniform(-.4, .4), 1.4])
        vel = np.array([v * math.cos(a), v * math.sin(a), r.uniform(.12, .3) * KT])
        size = r.uniform(.28, .6) if big else r.uniform(.09, .18)
        rot, tilt = r.uniform(0, 6), r.uniform(0, 6)
        spin, tspin = r.uniform(.2, .5) * r.choice((-1, 1)) * KT, r.uniform(.15, .4) * KT
        path = []
        for f in range(N):
            vel[2] -= .018 * KT * KT
            p = p + vel
            if p[2] < size / 2:
                p[2] = size / 2
                if abs(vel[2]) > .03 * KT:
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
    x_ = min(max((t - T_BOOM) / 22, 0.0), 1.0)
    g = 1 - (1 - x_) ** 3                                  # 0~4f에 절반 이상 터져 나오고 이후 감속
    R = .4 + 3.9 * g
    zc, flat = .8 - .4 * g, .55 - .2 * g
    wind = ease_in((t - 54) / 40) if t >= 54 else 0.0
    back, front = [], []
    for L in LOBES:
        rr = R * L['rf']
        life = 1.0
        if L['rf'] < .7 and t > 46:                       # 가운데부터 걷힘
            life *= max(0.0, 1 - (t - 46) / (18 * L['die']))
        if t > 70:
            life *= max(0.0, 1 - (t - 70) / (30 * L['die']))
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
    """마스크의 큰 윤곽(SFA px, 시계 방향). 안쪽 구멍은 메운다(앞뒤로 나눠 그려 잔해는 따로 드러남)."""
    cs, _ = cv2.findContours(m.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
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


def cloud_bulges(P, seed, scale, width=1.0, height=(.34, .52)):
    """윤곽을 따라 볼록들을 곡선 4개씩으로 설계(조절점을 이음점에서 반사해 매끄럽게 이음):
    골 A →(뒤로 걸치는 갈고리)→ 어깨 S1 → 꼭대기 → 어깨 S2 → 다음 골 B.
    볼록마다 폭·높이·기울기·어깨 높이·둥근 정도가 다르고, 골은 뾰족하게 남아 앞 덩어리가 뒤 덩어리를 덮는다."""
    r = random.Random(seed)
    seg = np.vstack([P, P[:1]])
    cum = np.concatenate([[0], np.cumsum(np.hypot(*np.diff(seg, axis=0).T))])
    L = cum[-1]
    mean_w = max(40.0, 125 * scale * width)
    n = max(4, int(round(L / mean_w)))
    s0 = cum[int(np.argmin(P[:, 0]))]                      # 시작점: 가장 왼쪽(프레임 사이 안정)
    cuts = sorted(s0 + L * (k + r.uniform(-.3, .3)) / n for k in range(n))
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
        h = w * (r.uniform(*height) if kind < .8 else (r.uniform(.15, .22) if kind < .93 else r.uniform(.55, .75)))
        lean = r.uniform(-.2, .2)
        hook = r.uniform(.0, .07)                           # 골에서 뒤로 걸치는 정도(작게: 고리 생기지 않게)
        Pk = M + nrm * h + tg * w * lean
        S1 = A + nrm * h * r.uniform(.55, .8) + tg * w * (.08 - hook * .6)
        S2 = B + nrm * h * r.uniform(.3, .55) + tg * w * r.uniform(-.04, .06)
        cA = A + nrm * h * r.uniform(.3, .45) - tg * w * hook           # 골에서 바깥으로 곧게 솟음
        c1 = S1 + (S1 - cA) / (np.hypot(*(S1 - cA)) or 1) * w * r.uniform(.12, .2)   # S1에서 매끄럽게
        c2 = Pk + (Pk - c1) / (np.hypot(*(Pk - c1)) or 1) * w * r.uniform(.14, .24)  # 꼭대기에서 매끄럽게
        cB = S2 + (S2 - c2) / (np.hypot(*(S2 - c2)) or 1) * w * r.uniform(.1, .18)   # S2에서 매끄럽게, 골로 들어감
        seq = [A, cA, S1, c1, Pk, c2, S2, cB]
        bul.append(dict(A=A, B=B, P=Pk, S1=S1, S2=S2, c1=c1, c2=c2, n=nrm, h=h, w=w, seq=seq, tg=tg))
    return bul


def _ring(bul):
    ring = []
    for b in bul:
        ring += [tuple(q) for q in b['seq']]
    return ring


def _spike(fr, base, out, tg, w, ln, col, r):
    """가장자리에서 털·불꽃처럼 뻗는 가시: 살짝 휜 뾰족한 곡선 쐐기."""
    a1, a2 = base - tg * w / 2, base + tg * w / 2
    tip = base + out * ln + tg * ln * r.uniform(-.25, .25)
    bend = tg * ln * r.uniform(-.18, .18)
    fr.cpoly([tuple(a1), tuple((a1 + tip) / 2 + bend), tuple(tip), tuple((a2 + tip) / 2 + bend)], col)


def draw_dust(fr, lobes, side, t, center):
    """애니 먼지(Sakugabooru smoke·debris 40편 140장 참고)를 곡선으로 직접 설계.
    - 굵은 검은 외곽선 없음: 바탕보다 조금 어두운 가는 선만(돌덩이처럼 보이지 않게)
    - 밝은 베이지·회색 2톤 + 아주 짙은 점 몇 개
    - 터지는 동안 바깥 가장자리에 털·불꽃 같은 뾰족한 가시(폭발 중심에서 멀어지는 쪽)
    - 그림자 경계는 둥글지 않고 날카롭게 파고드는 가시, 그림자색 작은 타원 구멍"""
    if not lobes:
        return
    scale = float(np.median([l[2] for l in lobes])) / 60
    spike = max(0.0, 1 - (t - T_BOOM) / 26) ** .7          # 폭발 직후일수록 가시가 길다
    body = _body_mask(lobes)
    mw = max(40.0, 125 * scale) / DS
    k = max(2, int(mw * .16))
    lit = cv2.erode(body, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * k + 1, 2 * k + 1)))
    lit = cv2.warpAffine(lit, np.float32([[1, 0, -.1 * mw], [0, 1, -.16 * mw]]), (lit.shape[1], lit.shape[0]))
    lit = cv2.bitwise_and(lit, cv2.erode(body, np.ones((5, 5), np.uint8)))
    base_seed = int(len(lobes)) * 7 + (1 if side == 'f' else 0)
    cen = np.array(center)
    sil = [cloud_bulges(P, base_seed + ci, scale, .62, (.36, .56)) for ci, P in enumerate(_outlines(body))]
    for ci, bul in enumerate(sil):
        fr.layer = f'dust_{side}_shade'
        fr.cpoly(_ring(bul), D_SHADE, D_LINE, .28)         # 곡선이 이어진 커스텀 오브젝트 하나(가는 외곽선)
        if spike > .05:                                    # 털·불꽃 가시: 바깥(폭발 중심 반대)을 향한 볼록에서
            r = random.Random(base_seed + 70 + ci)
            for b in bul:
                d = b['P'] - cen
                if float(np.dot(b['n'], d / (np.hypot(*d) or 1))) < .25:
                    continue
                out = (b['n'] * .5 + d / (np.hypot(*d) or 1) * .5)
                out /= np.hypot(*out) or 1
                for _ in range(r.randint(3, 6)):
                    u = r.uniform(.15, .85)
                    base = _q(b['S1'], b['c1'], b['P'], u * 2) if u < .5 else _q(b['P'], b['c2'], b['S2'], u * 2 - 1)
                    base = base - b['n'] * 3
                    fr.layer = f'dust_{side}_shade'
                    _spike(fr, base, out, b['tg'], b['w'] * r.uniform(.14, .26), b['w'] * r.uniform(.5, 1.4) * spike, D_SHADE, r)
    for ci, P in enumerate(_outlines(lit, 30)):
        seed = base_seed + 100 + ci
        bul = cloud_bulges(P, seed, scale, .55, (.3, .5))
        fr.layer = f'dust_{side}_lite'
        fr.cpoly(_ring(bul), D_BASE)
        r = random.Random(seed + 7)
        fr.layer = f'dust_{side}_base'
        for i, b in enumerate(bul):
            face = float(np.dot(b['n'], L2))
            A, B, nrm, tg = b['A'], b['B'], b['n'], b['tg']
            if face < .25 and r.random() < .85:             # 날카롭게 파고드는 그림자 가시(골에서 몸통 안으로)
                inn = -(nrm + bul[i - 1]['n']) / 2
                inn /= np.hypot(*inn) or 1
                inn = inn * .7 + L2 * -.3 * -1               # 빛 쪽(왼쪽 위)으로 기울어 파고듦
                inn /= np.hypot(*inn) or 1
                _spike(fr, A - nrm * 2, inn, tg, b['w'] * r.uniform(.16, .28), b['w'] * r.uniform(.45, .95), D_SHADE, r)
                if r.random() < .4:                          # 갈래 가시
                    _spike(fr, A - nrm * 2 + tg * b['w'] * .18, inn, tg, b['w'] * .11, b['w'] * r.uniform(.25, .5), D_SHADE, r)
            if face > .45 and r.random() < .5:              # 밝은 면 위 얇은 하이라이트(꼭대기 쪽)
                Pk, S1, S2, c1, c2 = b['P'], b['S1'], b['S2'], b['c1'], b['c2']
                d_ = b['h'] * r.uniform(.12, .2)
                a2, b2 = _q(S1, c1, Pk, .35), _q(Pk, c2, S2, .65)
                ca, cb = _q(S1, c1, Pk, .7), _q(Pk, c2, S2, .3)
                fr.cpoly([tuple(a2), tuple(ca), tuple(Pk), tuple(cb), tuple(b2), tuple(Pk - nrm * d_)], D_LITE)
        for _ in range(r.randint(2, 6)):                    # 그림자색 작은 타원 구멍
            b = r.choice(bul)
            q = b['P'] - b['n'] * b['h'] * r.uniform(1.2, 2.6)
            rr = b['w'] * r.uniform(.04, .09)
            fr.circle(tuple(q), rr, CLEAR, .06, None, fill=D_SHADE if r.random() < .75 else D_DEEP)
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
GRAPHITE = (36, 35, 33)


def pencil(fr, p0, p1, w, rgb, alpha, r):
    """4B 연필 획: 한 획을 2~3가닥(살짝 어긋나고 길이·진하기 다름)으로. 끝은 가늘게."""
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    L = math.hypot(dx, dy) or 1
    nx, ny = -dy / L, dx / L
    for j in range(r.choice((2, 2, 3))):
        o = r.uniform(-w * .5, w * .5)
        t0, t1 = r.uniform(0, .08), r.uniform(.75, 1.0)
        a = (p0[0] + dx * t0 + nx * o, p0[1] + dy * t0 + ny * o)
        m = (p0[0] + dx * (t0 + t1) / 2 + nx * o * 1.2 + r.uniform(-1.5, 1.5), p0[1] + dy * (t0 + t1) / 2 + ny * o * 1.2 + r.uniform(-1.5, 1.5))
        b = (p0[0] + dx * t1 + nx * o * .6, p0[1] + dy * t1 + ny * o * .6)
        al = int(alpha * r.uniform(.25, 1.0))           # 낮은 알파 획이 겹치며 흑연처럼 진해짐
        fr.line(a, m, argb(*rgb, al), max(w / 9 * r.uniform(.5, 1.0), .08))
        fr.line(m, b, argb(*rgb, al), max(w / 20 * r.uniform(.5, 1.0), .06))


def smudge(fr, c, r0, r1, n, w, rgb, alpha, seed):
    """연필 문지름: 넓고 아주 옅은 획(알파 10~30)을 겹쳐 회색 톤의 번짐을 만듦."""
    r = random.Random(seed)
    for _ in range(n):
        a = r.uniform(0, 2 * math.pi)
        p0 = (c[0] + r0 * r.uniform(.8, 1.2) * math.cos(a), c[1] + r0 * r.uniform(.8, 1.2) * math.sin(a))
        p1 = (c[0] + r1 * r.uniform(.6, 1.1) * math.cos(a + r.uniform(-.05, .05)), c[1] + r1 * r.uniform(.6, 1.1) * math.sin(a + r.uniform(-.05, .05)))
        fr.line(p0, p1, argb(*rgb, int(alpha * r.uniform(.4, 1))), w / 9 * r.uniform(.6, 1.4))


def radial_glow(fr, c, R, steps, rgb, alpha, sx=1.25, sy=.85, jag=0.0, seed=0):
    """반투명 타원을 겹쳐 중심이 가장 밝은 그라데이션(알파가 겹칠수록 진해짐)."""
    r = random.Random(seed)
    for i in range(steps):
        rr = R * (1 - i / steps)
        pts = []
        for j in range(40):
            a = 2 * math.pi * j / 40
            k_ = 1 + (jag * r.uniform(-.5, 1) if j % 2 == 0 else 0)
            pts.append((c[0] + rr * k_ * sx * math.cos(a), c[1] + rr * k_ * sy * math.sin(a)))
        fr.poly(pts, argb(*rgb, alpha))


def stroke_grad(fr, c, rin, rout, n, w, rgb, alpha, seed, outward=True, sy=.85):
    """연필 획 그라데이션: 넓고 옅은 획을 길이 제각각으로 겹쳐 띠 없이 부드럽게.
    outward=True면 중심에서 뻗어(중심이 진함), False면 가장자리에서 안으로(가장자리가 진함)."""
    r = random.Random(seed)
    for _ in range(n):
        a = r.uniform(0, 2 * math.pi)
        far = rin + (rout - rin) * r.random() ** .7
        u = (math.cos(a), math.sin(a) * sy)
        p0 = (c[0] + u[0] * (rin if outward else rout), c[1] + u[1] * (rin if outward else rout))
        p1 = (c[0] + u[0] * far, c[1] + u[1] * far)
        fr.line(p0, p1, argb(*rgb, int(alpha * r.uniform(.5, 1))), w / 9 * r.uniform(.6, 1.5))


def vignette(fr, c, R0, R1, steps, rgb, alpha):
    """반투명 굵은 고리를 겹쳐 가장자리로 갈수록 어두워지는 그라데이션."""
    for i in range(steps):
        rr = R0 + (R1 - R0) * (i + .5) / steps
        width = (R1 - R0) / steps * (steps - i) * 1.6           # 바깥 고리일수록 여러 겹 겹침
        fr.circle(c, rr + width / 2, argb(*rgb, alpha), width / 9, None)


def pencil_rays(fr, c, r0, r1, n, w, rgb, alpha, seed, inward=False, spread=(0, 2 * math.pi), sy=1.0):
    r = random.Random(seed)
    for _ in range(n):
        a = r.uniform(*spread)
        a0, a1 = r0 * r.uniform(.8, 1.3), r1 * r.uniform(.4, 1.1)
        p0 = (c[0] + a0 * math.cos(a), c[1] + a0 * math.sin(a) * sy)
        p1 = (c[0] + a1 * math.cos(a), c[1] + a1 * math.sin(a) * sy)
        if inward:
            p0, p1 = p1, p0
        pencil(fr, p0, p1, w * r.uniform(.4, 1.0), rgb, alpha, r)


def hatch_poly(fr, poly, ang, gap, w, rgb, alpha, seed):
    """다각형 안을 연필 사선으로 채움(경계를 넘는 획 끝도 조금 남겨 거칠게)."""
    r = random.Random(seed)
    ca, sa = math.cos(ang), math.sin(ang)
    rot = [(x * ca + y * sa, -x * sa + y * ca) for x, y in poly]
    vmin, vmax = min(q[1] for q in rot), max(q[1] for q in rot)
    v = vmin + gap * r.uniform(.2, 1)
    while v < vmax:
        xs = []
        for (ux, uy), (wx, wy) in zip(rot, rot[1:] + rot[:1]):
            if (uy > v) != (wy > v):
                xs.append(ux + (v - uy) * (wx - ux) / (wy - uy))
        xs.sort()
        for i in range(0, len(xs) - 1, 2):
            u0, u1 = xs[i] - r.uniform(-4, 10), xs[i + 1] + r.uniform(-4, 10)
            p0 = (u0 * ca - v * sa, u0 * sa + v * ca)
            p1 = (u1 * ca - v * sa, u1 * sa + v * ca)
            pencil(fr, p0, p1, w, rgb, alpha, r)
        v += gap * r.uniform(.6, 1.4)


def fringe(fr, pts, c, n, L, w, rgb, alpha, seed, inward=False):
    """경계에서 털처럼 뻗는 연필 잔털(중심에서 멀어지는 방향, inward면 안쪽)."""
    r = random.Random(seed)
    for _ in range(n):
        i = r.randrange(len(pts))
        a, b = pts[i], pts[(i + 1) % len(pts)]
        t = r.random()
        p = (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
        d = (p[0] - c[0], p[1] - c[1])
        dl = math.hypot(*d) or 1
        u = (d[0] / dl, d[1] / dl)
        if inward:
            u = (-u[0], -u[1])
        ln = L * r.uniform(.3, 1.0)
        q = (p[0] + u[0] * ln + r.uniform(-.15, .15) * ln, p[1] + u[1] * ln + r.uniform(-.15, .15) * ln)
        pencil(fr, p, q, w * r.uniform(.4, 1), rgb, alpha, r)


def glow_line(fr, a, b, th, gr, gt, rgb=(255, 255, 255), ga=255):
    col = argb(*rgb)
    fr.line(a, b, col, th, (gr, gt, argb(*rgb), ga))


def flare(fr, c, L, z, seed):
    """빛나는 십자 플레어: 긴 가로·세로 + 짧은 사선, 모두 글로우. 아래에 반투명 블룸 그라데이션."""
    r = random.Random(seed)
    stroke_grad(fr, c, 0, L * .55, 70, 60, (255, 252, 240), 22, seed + 3, sy=1.0)
    for ang, ln, th in ((0, L, .5), (math.pi / 2, L * .7, .45), (math.pi / 4, L * .3, .3), (-math.pi / 4, L * .3, .3)):
        u = (math.cos(ang), math.sin(ang))
        for sg in (-1, 1):
            glow_line(fr, c, (c[0] + sg * u[0] * ln * r.uniform(.8, 1.1), c[1] + sg * u[1] * ln * r.uniform(.8, 1.1)), th, 18 * z, 24, (255, 252, 240), 230)
    fr.circle(c, 26 * z, argb(255, 255, 255), .3, (40 * z, 70, argb(255, 250, 235), 255), fill=argb(255, 255, 255))


def jag_pts(c, R, seed, sx=1.25, sy=.85, n=40):
    r = random.Random(seed)
    pts = []
    for i in range(n):
        a = 2 * math.pi * i / n
        k_ = 1 + (r.uniform(.12, .32) * (2.4 if r.random() < .12 else 1) if i % 2 == 0 else -r.uniform(0, .08))
        pts.append((c[0] + R * k_ * sx * math.cos(a), c[1] + R * k_ * sy * math.sin(a)))
    return pts


def grain_over(fr, poly, rgb, alpha, seed, ang=.9, gap=9):
    """면 위 반투명 연필 결(흰 면엔 회색, 검은 면엔 흑연 광택)."""
    hatch_poly(fr, poly, ang, gap, 5, rgb, alpha, seed)


def impact(fr, cam, k, sub):
    """나카무라식 임팩트(87편·후보 611장 참고): 흑백 2톤이지만 검정은 4B 연필 획이 겹친 결(회색 결이 비침),
    경계는 털처럼 갈라지는 잔털, 흰 쪽은 글로우로 빛이 번짐(블룸)·십자 플레어·빛나는 가는 광선.
    k: 0..5 = IF1..IF6, sub: 같은 그림의 2번째 프레임(획이 다시 그려져 끓음)."""
    c = cam(0, 0, 1.2)
    z = cam.sc / 168
    sd = 40 + k * 10 + sub * 997
    full = [(-80, -80), (W + 80, -80), (W + 80, H + 80), (-80, H + 80)]
    dark_bg = k in (0, 2, 3)
    fr.layer = 'imp_bg'
    fr.poly(full, argb(*(GRAPHITE if dark_bg else Wt), {0: 238, 1: 255, 2: 250, 3: 245, 4: 255, 5: 252}[k]))
    WH, BK = argb(*Wt), argb(*K)
    top = [cam(-1, -1, 2), cam(1, -1, 2), cam(1, 1, 2), cam(-1, 1, 2)]
    right = [cam(1, -1, 2), cam(1, 1, 2), cam(1, 1, 0), cam(1, -1, 0)]
    front = [cam(-1, 1, 2), cam(1, 1, 2), cam(1, 1, 0), cam(-1, 1, 0)]
    if dark_bg:                                            # 어두운 화면 자체가 연필로 칠한 결 + 종이 결처럼 비치는 밝은 긁힘
        fr.layer = 'imp_bgtex'
        stroke_grad(fr, c, 0, 1100 * z, 160, 110, (255, 250, 238), 16, sd + 21)     # 중심이 밝은 빛 그라데이션(연필 획)
        smudge(fr, c, 200 * z, 1600, 70, 90, (12, 12, 12), 26, sd + 2)            # 흑연 문지름
        pencil_rays(fr, c, 120 * z, 1500, 520, 9, K, 235, sd + 1)
        pencil_rays(fr, c, 160 * z, 1500, 140, 4, (120, 117, 110), 110, sd + 11)
    else:
        fr.layer = 'imp_bgtex'
        stroke_grad(fr, c, 300 * z, 1700, 200, 120, K, 16, sd + 21, outward=False)  # 가장자리가 어두운 그라데이션(연필 획)
        smudge(fr, c, 300 * z, 1600, 60, 80, (40, 40, 40), 22, sd + 2)
    if k == 0:                                             # IF1 흑·집중선 + 빛나는 윗면
        fr.layer = 'imp_fg'
        fr.poly(top, WH)
        fr.poly(right, BK)
        fr.poly(front, BK)
        fr.layer = 'imp_tex'
        grain_over(fr, top, (120, 116, 108), 40, sd + 31, .4, 11)
        for f, ang in ((right, 1.2), (front, 2.0)):
            hatch_poly(fr, f, ang, 7 * z, 6, (70, 68, 64), 150, sd + 3)
        fringe(fr, right + front, c, 90, 70 * z, 7, K, 230, sd + 4)
        fr.layer = 'imp_glow'
        for a_, b_ in zip(top, top[1:] + top[:1]):
            glow_line(fr, a_, b_, .5, 22 * z, 40)
        r = random.Random(sd)
        for _ in range(70):                                 # 빛나는 가는 광선
            a = r.uniform(0, 2 * math.pi)
            p0 = (c[0] + 180 * z * math.cos(a), c[1] + 150 * z * math.sin(a))
            p1 = (c[0] + r.uniform(500, 1500) * math.cos(a), c[1] + r.uniform(500, 1500) * math.sin(a))
            glow_line(fr, p0, p1, r.uniform(.12, .4), r.uniform(4, 10), 10, (255, 253, 245), r.randint(150, 230))
        flare(fr, tuple(np.mean(top, 0)), 520 * z, z, sd + 5)
    elif k == 1:                                           # IF2 반전: 흰 화면 + 검은 큐브, 큐브에서 연필 털 폭발
        fr.layer = 'imp_fg'
        for f in (right, front, top):
            fr.poly(f, BK)
        fr.layer = 'imp_tex'
        pencil_rays(fr, c, 300 * z, 1600, 360, 14, K, 245, sd + 1)
        fringe(fr, right + front + top, c, 260, 160 * z, 9, K, 240, sd + 2)
        hatch_poly(fr, top, .3, 9 * z, 5, (90, 88, 84), 120, sd + 3)
        for f in (right, front):
            grain_over(fr, f, (150, 146, 138), 34, sd + 32, 1.3, 12)
        fr.layer = 'imp_glow'
        tc = tuple(np.mean(top, 0))
        r = random.Random(sd)
        for _ in range(26):
            a = r.uniform(0, 2 * math.pi)
            u = (math.cos(a), math.sin(a))
            dmax = _ray_to_poly(tc, u, top)
            if dmax:
                glow_line(fr, tc, (tc[0] + u[0] * dmax * r.uniform(.6, .95), tc[1] + u[1] * dmax * r.uniform(.6, .95)), r.uniform(.2, .5), 8 * z, 16)
        flare(fr, tc, 260 * z, z, sd + 4)
    elif k == 2:                                           # IF3 십자 분할: 빛줄기(글로우) + 연필로 칠한 검은 4덩어리
        r = random.Random(sd)
        fr.layer = 'imp_fg'
        arms = []
        for ax in ((1, 0), (0, 1)):
            for sg in (-1, 1):
                q = cam(sg * 9 * ax[0], sg * 9 * ax[1], 1.2)
                dx, dy = q[0] - c[0], q[1] - c[1]
                L = math.hypot(dx, dy)
                ux, uy = dx / L, dy / L
                nx, ny = -uy, ux
                g0, g1 = 90 * z, 30 * z
                far = (c[0] + ux * 2600, c[1] + uy * 2600)
                arm = [(c[0] + nx * g0, c[1] + ny * g0), (far[0] + nx * g1, far[1] + ny * g1),
                       (far[0] - nx * g1, far[1] - ny * g1), (c[0] - nx * g0, c[1] - ny * g0)]
                fr.poly(arm, WH)
                arms.append((arm, ux, uy, nx, ny))
        fr.layer = 'imp_tex'
        for arm, ux, uy, nx, ny in arms:                   # 빛에 먹힌 가장자리 = 안쪽으로 파고드는 검은 연필 털
            for side in (0, 3):
                a_, b_ = arm[side], arm[side + 1] if side == 0 else arm[2]
                fringe(fr, [a_, b_], c, 70, 60 * z, 8, K, 235, sd + side + int(ux * 10), inward=False)
        fr.layer = 'imp_glow'
        for arm, ux, uy, nx, ny in arms:
            glow_line(fr, c, (c[0] + ux * 1800, c[1] + uy * 1800), .9, 40 * z, 90, (255, 252, 240), 200)
        flare(fr, c, 700 * z, z, sd + 6)
    elif k == 3:                                           # IF4 톱니 폭발: 블룸 + 연필 결
        rim = jag_pts(c, 380 * z, sd)
        fr.layer = 'imp_fg'
        fr.poly(rim, WH)
        fr.layer = 'imp_tex'
        pencil_rays(fr, c, 110 * z, 420 * z, 160, 8, K, 210, sd + 2, inward=True)
        fringe(fr, rim, c, 220, 140 * z, 9, K, 235, sd + 3)
        grain_over(fr, rim, (110, 106, 100), 32, sd + 33, .7, 14)
        r = random.Random(sd + 3)
        for _ in range(10):
            a, rr, s_ = r.uniform(0, 6.3), r.uniform(120, 380) * z, r.uniform(22, 54) * z
            ch = chunk((c[0] + rr * math.cos(a) * 1.2, c[1] + rr * math.sin(a) * .8), s_, a)
            fr.poly(ch, BK)
            fringe(fr, ch, (c[0], c[1]), 8, s_ * 1.6, 6, K, 220, sd + int(rr), inward=True)
        fr.layer = 'imp_glow'
        for a_, b_ in zip(rim, rim[1:] + rim[:1]):          # 테두리 블룸
            glow_line(fr, a_, b_, .4, 34 * z, 60, (255, 250, 236), 220)
        r = random.Random(sd + 9)
        for _ in range(80):
            a = r.uniform(0, 2 * math.pi)
            p0 = (c[0] + 400 * z * 1.25 * math.cos(a), c[1] + 400 * z * .85 * math.sin(a))
            p1 = (c[0] + r.uniform(700, 1600) * math.cos(a), c[1] + r.uniform(700, 1600) * math.sin(a))
            glow_line(fr, p0, p1, r.uniform(.12, .45), r.uniform(5, 12), 12, (255, 252, 240), r.randint(150, 230))
        flare(fr, c, 600 * z, z, sd + 7)
    elif k == 4:                                           # IF5 쐐기 가시: 연필로 칠한 검은 쐐기 + 빛나는 중심
        r = random.Random(sd)
        wedges = []
        fr.layer = 'imp_fg'
        for i in range(16):
            a = 2 * math.pi * i / 16 + r.uniform(-.12, .12)
            wd, r0 = r.uniform(.06, .16), r.uniform(180, 320) * z
            wg = [(c[0] + r0 * math.cos(a), c[1] + r0 * .8 * math.sin(a)),
                  (c[0] + 2400 * math.cos(a - wd), c[1] + 2400 * math.sin(a - wd)),
                  (c[0] + 2400 * math.cos(a + wd), c[1] + 2400 * math.sin(a + wd))]
            fr.poly(wg, BK)
            wedges.append((wg, a))
        fr.layer = 'imp_tex'
        for wg, a in wedges:
            hatch_poly(fr, wg, a, 10, 7, (84, 82, 78), 140, sd + int(a * 100))
            fringe(fr, wg[1:] + wg[:1], c, 40, 50 * z, 8, K, 230, sd + int(a * 50))
        pencil_rays(fr, c, 80 * z, 320 * z, 90, 7, K, 200, sd + 1, inward=True)
        for _ in range(12):
            a, rr, s_ = r.uniform(0, 6.3), r.uniform(150, 520) * z, r.uniform(24, 64) * z
            p = (c[0] + rr * math.cos(a), c[1] + rr * .8 * math.sin(a))
            fr.poly(chunk(p, s_, a), BK)
            pencil_rays(fr, p, s_ * .3, s_ * 2.2, 10, 10, K, 220, sd + int(rr), spread=(a + math.pi - .35, a + math.pi + .35))
        fr.layer = 'imp_glow'
        flare(fr, c, 760 * z, z, sd + 8)
    else:                                                  # IF6 먹 얼룩 먼지: 곡선 덩어리 + 연필 털 + 빛나는 흰 중심
        r = random.Random(sd)
        fr.layer = 'imp_fg'
        blobs = []
        for i in range(14):
            a = 2 * math.pi * i / 14 + r.uniform(-.1, .1)
            rr, s_ = r.uniform(330, 520) * z, r.uniform(120, 200) * z
            p = (c[0] + rr * math.cos(a) * 1.25, c[1] + rr * .7 * math.sin(a))
            P = np.array([(p[0] + s_ * math.cos(t), p[1] + s_ * .8 * math.sin(t)) for t in np.linspace(0, 2 * math.pi, 24, endpoint=False)])
            bul = cloud_bulges(P, sd + i, s_ / 160)
            ring = _ring(bul)
            fr.cpoly(ring, BK)
            blobs.append((p, [tuple(b['P']) for b in bul]))
        rim = jag_pts(c, 240 * z, sd + 2, 1.3, .8)
        fr.poly(rim, WH)
        fr.layer = 'imp_tex'
        for p, peaks in blobs:
            fringe(fr, peaks, c, 26, 120 * z, 10, K, 235, sd + int(p[0]))
            pencil_rays(fr, p, 10, 140 * z, 12, 6, (96, 94, 90), 150, sd + int(p[1]))
        fr.layer = 'imp_glow'
        for a_, b_ in zip(rim, rim[1:] + rim[:1]):
            glow_line(fr, a_, b_, .4, 30 * z, 55, (255, 250, 236), 220)
        for _ in range(8):
            a, rr, s_ = r.uniform(0, 6.3), r.uniform(340, 600) * z, r.uniform(28, 60) * z
            ch = chunk((c[0] + rr * math.cos(a) * 1.25, c[1] + rr * .7 * math.sin(a)), s_, a)
            for a_, b_ in zip(ch, ch[1:] + ch[:1]):
                glow_line(fr, a_, b_, .45, 10 * z, 18)
        flare(fr, c, 480 * z, z, sd + 9)


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
    s = (t - T_BOOM) / 7
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
    if not 54 <= t < 86:
        return
    fr.layer = 'fx'
    s = (t - 54) / 32
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
    if t < 36:
        return
    fr.layer = 'ground'
    r = random.Random(6)
    n = min(70, int((t - 36) * 5))
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
    draw_dust(fr, back, 'b', t, cam(0, 0, 1))
    draw_dust(fr, front, 'f', t, cam(0, 0, 1))
    fr.layer = 'debris'
    for rock, size, path in DEBRIS:
        p, rot, tilt = path[t - T_BOOM]
        rock.draw(fr, cam, p, rot, tilt, .4 if size > .25 else .25)
    wind(fr, cam, t)
    return fr


def fast_fill_coverage(contours, cv, ss=3):
    """미리보기 전용: sfa_render.fill_polygon_coverage와 같은 even-odd·3x3 표본을 OpenCV로 계산.
    기준 렌더러(sfa_render.py)는 바꾸지 않고 미리보기 때만 바꿔 끼운다."""
    pts = [p for c in contours for p in c]
    box = cv.box(pts, 1)
    if box is None:
        return None, None
    y0, y1, x0, x1 = box
    ox, oy = float(cv.X[y0, x0]), float(cv.Y[y0, x0])
    h, w = y1 - y0, x1 - x0
    acc = np.zeros((h * ss, w * ss), np.uint8)
    for c in contours:
        if len(c) < 3:
            continue
        q = np.array([((x - ox + .5) * ss - .5, (y - oy + .5) * ss - .5) for x, y in c]) * 16
        tmp = np.zeros_like(acc)
        cv2.fillPoly(tmp, [np.round(q).astype(np.int32)], 1, lineType=cv2.LINE_8, shift=4)
        acc ^= tmp
    return acc.reshape(h, ss, w, ss).mean((1, 3)), box


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
        import sfa_render
        sfa_render.fill_polygon_coverage = fast_fill_coverage
        md.preview(root, a.preview, tuple(int(v) for v in a.size.split('x')))
        print('미리보기 →', a.preview)


def write(frames, path):
    return mc.write(frames, LAYERS, 'stone_cube_burst', path)


if __name__ == '__main__':
    main()
