#!/usr/bin/env python3
"""손으로 짠 1대1 결투 시연 SFA (학습 모델 아님): 3D 장면을 어안/더치 카메라로 투영해 매 프레임 그린다.

24fps 온 원즈(모든 프레임이 다른 그림). 앱 트위닝을 쓰지 않으므로 (트위닝, 재생) FPS = (24, 24).
구간 1 대치·초고속 접근(어안·더치·360도 회전·스미어·배경 동화), 구간 2 임팩트 프레임·큐브 파쇄·
근접 공방(극단 투시·해칭), 구간 3 도약·유도 광탄 군무·큐브 발판 회피·지그재그 광선·구형 폭발과
3단계 타이밍(1s→2s→3s) 연기.

  python tools/make_duel.py OUT.sfa [--preview OUT.mp4 --size 960x540]
"""
import argparse
import math
import random
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import sfa  # noqa: E402

W, H = 1920.0, 1080.0
FPS = 24
N_FRAMES = 264


def argb(r, g, b, a=255):
    return str((a << 24) | (r << 16) | (g << 8) | b)


# palette
SKY = argb(205, 170, 128)
SKY_HOT = argb(235, 196, 140)
GROUND = argb(92, 62, 44)
GROUND_FAR = argb(130, 92, 64)
GROUND_FILL = argb(168, 126, 92)
INK = argb(18, 14, 16)
WHITE = argb(255, 255, 255)
BLACK = argb(0, 0, 0)
RED = argb(255, 70, 40)
CYAN = argb(60, 215, 255)
SMOKE = argb(240, 236, 228)
YELLOW = argb(255, 238, 150)
CLEAR = '0'


def v3(x, y, z):
    return np.array([x, y, z], float)


def norm(v):
    n = np.linalg.norm(v)
    return v / n if n > 1e-9 else v


def ease(s):
    s = min(max(s, 0.0), 1.0)
    return s * s * (3 - 2 * s)


def ease_in(s):
    s = min(max(s, 0.0), 1.0)
    return s * s


def ease_out(s):
    s = min(max(s, 0.0), 1.0)
    return 1 - (1 - s) ** 2


def lerp(a, b, s):
    return a + (b - a) * s


def ground_y(x, z):
    return 0.0012 * (x * x + z * z)          # shallow crater bowl


# ----------------------------------------------------------------------------- 2D frame builder
class Frame2D:
    """Objects in screen pixels (1920x1080), written as SFA AO/AP/FR."""

    def __init__(self, bg, mode='normal'):
        self.bg, self.mode, self.items, self.layer = bg, mode, [], 'fg'

    def _col(self, c):
        if self.mode == 'impact_dark':
            return WHITE if c != CLEAR else c
        if self.mode == 'impact_light':
            return BLACK if c != CLEAR else c
        return c

    def _visible(self, pts, pad=40):
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        return max(xs) > -pad and min(xs) < W + pad and max(ys) > -pad and min(ys) < H + pad

    def line(self, a, b, color, th=1.0, glow=None):
        if self._visible([a, b]):
            self.items.append((self.layer, '1', [a, b], self._col(color), th, glow, None))

    def curve(self, a, c, b, color, th=1.0, glow=None):
        if self._visible([a, c, b]):
            self.items.append((self.layer, '3', [a, c, b], self._col(color), th, glow, None))

    def circle(self, c, r, color, th=1.0, glow=None, fill=None):
        if r <= 0.5 or not self._visible([(c[0] - r, c[1] - r), (c[0] + r, c[1] + r)]):
            return
        fill = self._col(fill) if fill is not None and self.mode == 'normal' else (
            fill if fill is None else (BLACK if self.mode == 'impact_dark' else WHITE))
        self.items.append((self.layer, '2', [(c[0], c[1] - r), (c[0], c[1] + r)], self._col(color), th,
                           glow if self.mode == 'normal' else None, fill))

    def poly(self, pts, fill, color=CLEAR, th=1.0):
        if len(pts) < 3 or not self._visible(pts):
            return
        if self.mode != 'normal':
            fill = BLACK if self.mode == 'impact_dark' else WHITE
        self.items.append((self.layer, 'poly', pts, self._col(color) if color != CLEAR else CLEAR, th, None, fill))

    def write(self, root, n, ids):
        """ids: IdPlan shared by all frames. Frame n gets ID 500000+n, its points 10000000+n*10000+k
        (the probe convention), and every AO ID keeps one TypeId/point count/connection shape and
        one DrawOrder for the whole file (the importer keys objects by AO ID across frames)."""
        frame = ET.SubElement(root, 'Frame', {'BackgroundColor': self.bg, 'ID': str(500000 + n), 'Position': str(n)})
        for k, name in enumerate(LAYER_NAMES):            # list order = stacking (first = bottom)
            ET.SubElement(frame, 'LayerDef', {'ID': str(k), 'Name': name, 'Visible': 'true', 'Locked': 'false'})
        pid = 10000000 + n * 10000
        fills, used = [], {}

        def ao(oid, kind, color, th, glow):
            gr, gt, gc, ga = glow if glow else (0, 0, WHITE, 0)
            return ET.Element('AO', {
                'ID': str(oid), 'TypeId': kind, 'Color': color, 'LayerId': str(LAYERS.index(layer)), 'DrawOrder': str(oid),
                'ThicknessScale': f'{max(th, 0.06):.3f}', 'ObjectScale': '1.0', 'GlowRadius': str(int(gr)),
                'GlowThickness': str(int(gt)), 'GlowColor': gc, 'GlowAlpha': str(int(ga))})

        def ap(parent, idx, p, flags):
            nonlocal pid
            pid += 1
            return ET.SubElement(parent, 'AP', {'ID': str(pid), 'Flags': str(flags), 'Index': str(idx),
                                                'X': f'{p[0] / W * 100:.2f}', 'Y': f'{p[1] / H * 100:.2f}'})

        objs_out = []
        for layer, kind, pts, color, th, glow, fill in self.items:
            if kind == 'poly':
                pts = clip_poly(pts)
                if len(pts) < 3:
                    continue
                n_ = min(len(pts), 40)
                pts = pts if len(pts) == n_ else [pts[int(k * len(pts) / n_)] for k in range(n_)]
                pool = (layer, 'poly', n_)
            else:
                pool = (layer, kind)
            k = used.get(pool, 0)
            used[pool] = k + 1
            base = ids.slot(pool, k)
            if kind == 'poly':
                objs, aps = [], []
                for e in range(n_):
                    o = ao(base + e, '1', color, th, None)
                    aps.append((ap(o, 0, pts[e], 3), ap(o, 1, pts[(e + 1) % n_], 9)))
                    objs.append(o)
                for e in range(n_):                      # chain: end e <-> start e+1
                    ET.SubElement(aps[e][1], 'AC', {'ConnPtId': aps[(e + 1) % n_][0].get('ID')})
                    ET.SubElement(aps[(e + 1) % n_][0], 'AC', {'ConnPtId': aps[e][1].get('ID')})
                fr = ET.Element('FR', {'Color': fill})
                for o, (a0, a1) in zip(objs, aps):
                    ET.SubElement(fr, 'FS', {'Kind': '0', 'ObjId': o.get('ID'), 'StartPtId': a0.get('ID'),
                                             'EndPtId': a1.get('ID'), 'StartT': '0.0', 'EndT': '1.0'})
                fills.append(fr)
                objs_out += objs
                continue
            o = ao(base, kind, color, th, glow)
            for e, q in enumerate(pts):
                ap(o, e, q, 3 if e == 0 else 9)
            if kind == '2' and fill is not None:
                fr = ET.Element('FR', {'Color': fill})
                ET.SubElement(fr, 'FS', {'Kind': '1', 'ObjId': o.get('ID')})
                fills.append(fr)
            objs_out.append(o)
        for o in sorted(objs_out, key=lambda o: int(o.get('ID'))):
            frame.append(o)
        for fr in fills:
            frame.append(fr)


LAYERS = ('ground', 'bg', 'mid', 'fg', 'fx')            # back to front
LAYER_NAMES = ('땅 채우기', '배경 선', '큐브·미사일', '인물', '효과')    # one SFA layer each: within a layer the app does not keep fills behind lines


class IdPlan:
    """Stable AO IDs: pool (layer, kind[, edges]) slot k -> fixed ID block. IDs grow with the layer,
    so DrawOrder = ID keeps background behind figures in every frame."""

    def __init__(self):
        self.need = {}

    def slot(self, pool, k):
        self.need[pool] = max(self.need.get(pool, 0), k + 1)
        return self.base[pool] + k * self.width(pool)

    @staticmethod
    def width(pool):
        return pool[2] if pool[1] == 'poly' else 1

    def plan(self):
        """Assign ID ranges after a dry run counted every pool's size."""
        self.base, nxt = {}, 1000
        for layer in LAYERS:
            for pool in sorted((p for p in self.need if p[0] == layer), key=lambda p: (p[1] != 'poly', str(p))):  # fills first
                self.base[pool] = nxt
                nxt += self.need[pool] * self.width(pool) + 10


def clip_poly(pts, pad=60):
    """Sutherland-Hodgman clip to the canvas (plus a margin): the editor shows off-canvas fills."""
    def clip(poly, inside, cut):
        out = []
        for a, b in zip(poly, poly[1:] + poly[:1]):
            ia, ib = inside(a), inside(b)
            if ia:
                out.append(a)
            if ia != ib:
                out.append(cut(a, b))
        return out
    edges = [(lambda q: q[0] >= -pad, lambda a, b: _ix(a, b, 0, -pad)),
             (lambda q: q[0] <= W + pad, lambda a, b: _ix(a, b, 0, W + pad)),
             (lambda q: q[1] >= -pad, lambda a, b: _ix(a, b, 1, -pad)),
             (lambda q: q[1] <= H + pad, lambda a, b: _ix(a, b, 1, H + pad))]
    poly = list(pts)
    for inside, cut in edges:
        if not poly:
            break
        poly = clip(poly, inside, cut)
    return poly


def _ix(a, b, axis, v):
    t = (v - a[axis]) / ((b[axis] - a[axis]) or 1e-9)
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


# ----------------------------------------------------------------------------- camera
class Cam:
    """Perspective blended with equidistant fisheye, plus Dutch roll and a screen shake."""

    def __init__(self, pos, target, fov=90.0, fish=0.0, roll=0.0, shake=(0.0, 0.0)):
        self.pos = np.asarray(pos, float)
        fwd = norm(np.asarray(target, float) - self.pos)
        up = v3(0, 1, 0) if abs(fwd[1]) < 0.98 else v3(0, 0, 1)
        self.right = norm(np.cross(fwd, up))
        self.up = np.cross(self.right, fwd)
        self.fwd = fwd
        half = math.radians(min(fov, 178) / 2)
        self.fp = (W / 2) / math.tan(min(half, math.radians(80)))
        self.fe = (W / 2) / half
        self.fish = fish
        self.roll = math.radians(roll)
        self.shake = shake

    def cam(self, p):
        d = np.asarray(p, float) - self.pos
        return np.array([d @ self.right, d @ self.up, d @ self.fwd])

    def proj_c(self, c):
        x, y, z = c
        rho = math.hypot(x, y)
        th = math.atan2(rho, z)
        r = (1 - self.fish) * self.fp * math.tan(min(th, 1.45)) + self.fish * self.fe * th
        if rho < 1e-9:
            sx = sy = 0.0
        else:
            sx, sy = r * x / rho, -r * y / rho
        cr, sr = math.cos(self.roll), math.sin(self.roll)
        return (W / 2 + cr * sx - sr * sy + self.shake[0], H / 2 + sr * sx + cr * sy + self.shake[1])

    def proj(self, p):
        c = self.cam(p)
        return None if c[2] < 0.05 else self.proj_c(c)

    def scale(self, p, base=6.0):
        """Line thickness factor from distance (nearer = thicker)."""
        d = np.linalg.norm(np.asarray(p, float) - self.pos)
        return float(np.clip(base / max(d, 0.2), 0.12, 9.0))

    def seg(self, a, b):
        """Clip a 3D segment to the near plane; return projected (pa, ctrl_or_None, pb, mid3d)."""
        ca, cb = self.cam(a), self.cam(b)
        near = 0.08
        if ca[2] < near and cb[2] < near:
            return None
        if ca[2] < near or cb[2] < near:
            t = (near - ca[2]) / (cb[2] - ca[2])
            cm = ca + (cb - ca) * t
            if ca[2] < near:
                ca = cm
            else:
                cb = cm
        pa, pb = self.proj_c(ca), self.proj_c(cb)
        pm = self.proj_c((ca + cb) / 2)
        ctrl = (2 * pm[0] - (pa[0] + pb[0]) / 2, 2 * pm[1] - (pa[1] + pb[1]) / 2)
        dev = math.hypot(pm[0] - (pa[0] + pb[0]) / 2, pm[1] - (pa[1] + pb[1]) / 2)
        return pa, (ctrl if dev > 2.5 else None), pb


def draw_seg(fr, cam, a, b, color, th=1.0, glow=None, base=6.0, jitter=0.0, rng=None):
    s = cam.seg(a, b)
    if s is None:
        return
    pa, ctrl, pb = s
    if jitter and rng is not None:
        pa = (pa[0] + rng.uniform(-jitter, jitter), pa[1] + rng.uniform(-jitter, jitter))
        pb = (pb[0] + rng.uniform(-jitter, jitter), pb[1] + rng.uniform(-jitter, jitter))
    k = cam.scale((np.asarray(a) + np.asarray(b)) / 2, base) * th
    if ctrl is None:
        fr.line(pa, pb, color, k, glow)
    else:
        fr.curve(pa, ctrl, pb, color, k, glow)


# ----------------------------------------------------------------------------- characters
POSE_KEYS = ('lean', 'head', 'ls', 'le', 'rs', 're', 'lh', 'lk', 'rh', 'rk', 'wpn', 'spread')
STAND = dict(lean=5, head=0, ls=15, le=20, rs=25, re=40, lh=8, lk=10, rh=-8, rk=5, wpn=60, spread=0.14)


def pose(**kw):
    p = dict(STAND)
    p.update(kw)
    return p


def mix(p, q, s):
    return {k: lerp(p[k], q[k], s) for k in POSE_KEYS}


def keyed(keys, t):
    """keys: [(frame, pose)] -> eased pose at t."""
    if t <= keys[0][0]:
        return keys[0][1]
    for (f0, p0), (f1, p1) in zip(keys, keys[1:]):
        if t <= f1:
            return mix(p0, p1, ease((t - f0) / max(f1 - f0, 1e-6)))
    return keys[-1][1]


def rot2(v, deg):
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    return (c * v[0] - s * v[1], s * v[0] + c * v[1])


def skeleton(pelvis, yaw, pitch, P, roll=0.0):
    """Local sagittal FK (x forward, y up, z right) -> world joints."""
    tor = rot2((0.0, 1.0), -P['lean'])                 # lean forward = rotate toward +x
    down = (-tor[0], -tor[1])
    loc = {'pelvis': (0.0, 0.0, 0.0)}
    neck = (tor[0] * 0.55, tor[1] * 0.55)
    loc['neck'] = (neck[0], neck[1], 0.0)
    hd = rot2(tor, -P['head'])
    loc['head'] = (neck[0] + hd[0] * 0.2, neck[1] + hd[1] * 0.2, 0.0)
    sp = P['spread']
    down = (0.0, -1.0)                                 # limb angles are measured from the vertical
    for side, sgn in (('l', -1), ('r', 1)):
        up_ = rot2(down, P[side + 's'])
        el = (neck[0] + up_[0] * 0.3, neck[1] + up_[1] * 0.3)
        fo = rot2(up_, P[side + 'e'])
        ha = (el[0] + fo[0] * 0.28, el[1] + fo[1] * 0.28)
        loc[side + 'elb'] = (el[0], el[1], sgn * sp * 0.8)
        loc[side + 'hand'] = (ha[0], ha[1], sgn * sp * 0.6)
        th_ = rot2(down, P[side + 'h'])
        kn = (th_[0] * 0.45, th_[1] * 0.45)
        sh = rot2(th_, -P[side + 'k'])
        ft = (kn[0] + sh[0] * 0.45, kn[1] + sh[1] * 0.45)
        loc[side + 'knee'] = (kn[0], kn[1], sgn * sp * 0.6)
        loc[side + 'foot'] = (ft[0], ft[1], sgn * sp * 0.7)
        if side == 'r':
            wd = rot2(fo, P['wpn'])
            loc['wdir'] = (wd[0], wd[1], 0.0)
    cy, sy = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
    cp, spch = math.cos(math.radians(pitch)), math.sin(math.radians(pitch))
    cr, sr = math.cos(math.radians(roll)), math.sin(math.radians(roll))
    out = {}
    for k, (x, y, z) in loc.items():
        x, y = cp * x - spch * y, spch * x + cp * y        # pitch (flip) in the sagittal plane
        y, z = cr * y - sr * z, sr * y + cr * z            # roll
        wx, wz = cy * x - sy * z, sy * x + cy * z          # yaw about world up
        v = v3(wx, y, wz)
        out[k] = v if k == 'wdir' else np.asarray(pelvis, float) + v
    return out


class Fighter:
    def __init__(self, name, accent, blade):
        self.name, self.accent, self.blade = name, accent, blade


A = Fighter('A', RED, 1.15)       # sword
B = Fighter('B', CYAN, 1.9)       # glaive


def weapon_pts(J, f):
    h = J['rhand']
    d = norm(J['wdir'])
    if f is A:
        return h - d * 0.18, h + d * f.blade
    return h - d * 0.9, h + d * f.blade


def draw_fighter(fr, cam, J, f, ink=INK, alpha=255, th=1.0, hatch=False, glow=True, rng=None, jitter=0.0):
    col = ink if alpha == 255 else argb(*_rgb(ink), alpha)
    g = (14, 40, f.accent, 200) if glow else None
    segs = [('neck', 'pelvis'), ('neck', 'lelb'), ('lelb', 'lhand'), ('neck', 'relb'), ('relb', 'rhand'),
            ('pelvis', 'lknee'), ('lknee', 'lfoot'), ('pelvis', 'rknee'), ('rknee', 'rfoot')]
    w0, w1 = weapon_pts(J, f)
    wcol = f.accent if alpha == 255 else argb(*_rgb(f.accent), alpha)
    draw_seg(fr, cam, w0, w1, wcol, 0.9 * th, g if alpha == 255 else None, jitter=jitter, rng=rng)
    if f is B:                                            # glaive head: a short angled blade
        d = norm(J['wdir'])
        side = norm(np.cross(d, v3(0, 0, 1))) if abs(d[2]) < 0.9 else v3(1, 0, 0)
        draw_seg(fr, cam, w1, w1 - d * 0.45 + side * 0.18, wcol, 0.9 * th, None)
    for a, b in segs:
        draw_seg(fr, cam, J[a], J[b], col, th, None, jitter=jitter, rng=rng)
    hc = cam.proj(J['head'])
    if hc is not None:
        e = cam.proj(J['head'] + cam.up * 0.13)
        r = math.hypot(e[0] - hc[0], e[1] - hc[1]) if e else 8
        fr.circle(hc, r, col, cam.scale(J['head']) * th, None, fill=None)
    if hatch:                                             # shadow hatching on the lower-right side
        for a, b in (('neck', 'pelvis'), ('pelvis', 'lknee'), ('pelvis', 'rknee'), ('neck', 'relb')):
            pa, pb = cam.proj(J[a]), cam.proj(J[b])
            if pa is None or pb is None:
                continue
            k = cam.scale((J[a] + J[b]) / 2) * th
            dx, dy = pb[0] - pa[0], pb[1] - pa[1]
            n = math.hypot(dx, dy) or 1
            nx, ny = -dy / n, dx / n
            if nx + ny < 0:
                nx, ny = -nx, -ny
            off = 9 * k + 4
            for s in (0.25, 0.45, 0.65, 0.85):
                cx, cy = pa[0] + dx * s + nx * off, pa[1] + dy * s + ny * off
                L = 5 * k + 6
                fr.line((cx - L * 0.7, cy - L * 0.7), (cx + L * 0.7, cy + L * 0.7), col, 0.3 * th)


def _rgb(c):
    v = int(c)
    return (v >> 16) & 255, (v >> 8) & 255, v & 255


# ----------------------------------------------------------------------------- scene pieces
RNG0 = random.Random(7)
CRACKS = [(RNG0.uniform(0, 2 * math.pi), RNG0.uniform(10, 24), RNG0.uniform(32, 60)) for _ in range(10)]
RIM = [(i / 18 * 2 * math.pi, RNG0.uniform(6, 16)) for i in range(18)]
ROCKS = [(RNG0.uniform(-40, 40), RNG0.uniform(-40, 40), RNG0.uniform(0.5, 1.6)) for _ in range(10)]


def draw_ground(fr, cam, t, boil=0.0, color=None):
    rng = random.Random(1000 + t)
    gcol = color or GROUND
    if fr.mode == 'normal':                               # ground plane fill up to the rim horizon
        f = cam.fwd.copy()
        f[1] = 0
        az = math.atan2(f[2], f[0]) if np.linalg.norm(f) > 1e-6 else 0.0
        hz = []
        for d in np.linspace(-2.9, 2.9, 29):
            a = az + d
            q = cam.proj(v3(95 * math.cos(a), ground_y(95, 0), 95 * math.sin(a)))
            if q is not None:
                hz.append(q)
        if len(hz) >= 2:
            dx, dy = -math.sin(cam.roll) * 6000, math.cos(cam.roll) * 6000
            ex, ey = hz[-1][0] - hz[0][0], hz[-1][1] - hz[0][1]
            n = math.hypot(ex, ey) or 1.0
            ex, ey = ex / n * 6000, ey / n * 6000
            a0, a1 = (hz[0][0] - ex, hz[0][1] - ey), (hz[-1][0] + ex, hz[-1][1] + ey)
            ground = [a0] + hz + [a1, (a1[0] + dx, a1[1] + dy), (a0[0] + dx, a0[1] + dy)]
            keep = fr.layer
            fr.layer = 'ground'
            fr.poly(ground, GROUND_FILL)
            fr.layer = keep
    for R in (12, 28, 46, 66):
        n = 10
        for i in range(n):
            a0, a1 = 2 * math.pi * i / n, 2 * math.pi * (i + 1) / n
            w0 = 1 + boil * 0.08 * math.sin(3 * a0 + t * 0.7 + R) + boil * rng.uniform(-0.03, 0.03)
            w1 = 1 + boil * 0.08 * math.sin(3 * a1 + t * 0.7 + R) + boil * rng.uniform(-0.03, 0.03)
            p = v3(R * w0 * math.cos(a0), 0, R * w0 * math.sin(a0))
            q = v3(R * w1 * math.cos(a1), 0, R * w1 * math.sin(a1))
            p[1], q[1] = ground_y(p[0], p[2]), ground_y(q[0], q[2])
            draw_seg(fr, cam, p, q, gcol if R < 50 else GROUND_FAR, 0.8, base=10)
    for ang, r0, r1 in CRACKS:
        jitter = boil * rng.uniform(-0.15, 0.15)
        p = v3(r0 * math.cos(ang), 0, r0 * math.sin(ang))
        q = v3(r1 * math.cos(ang + 0.12 + jitter), 0, r1 * math.sin(ang + 0.12 + jitter))
        p[1], q[1] = ground_y(p[0], p[2]), ground_y(q[0], q[2])
        draw_seg(fr, cam, p, q, gcol, 0.6, base=10)
    pts = []
    for ang, hgt in RIM:                                   # jagged crater rim / distant cliffs
        h = hgt * (1 + boil * 0.25 * math.sin(t * 0.9 + ang * 5))
        pts.append(v3(95 * math.cos(ang), ground_y(95, 0) + h, 95 * math.sin(ang)))
    for i in range(len(pts)):
        a, b = pts[i], pts[(i + 1) % len(pts)]
        base_a = v3(a[0], ground_y(95, 0), a[2])
        draw_seg(fr, cam, a, b, GROUND_FAR, 1.2, base=14)
        if i % 3 == 0:
            draw_seg(fr, cam, a, base_a, GROUND_FAR, 0.7, base=14)
    for x, z, s in ROCKS:
        y = ground_y(x, z)
        draw_seg(fr, cam, v3(x - s, y, z), v3(x, y + s, z), gcol, 0.7, base=10)
        draw_seg(fr, cam, v3(x, y + s, z), v3(x + s * 0.8, y, z), gcol, 0.7, base=10)


def speed_lines(fr, rng, n, color, center=None, alpha=150):
    """Screen-space radial speed lines (ink streaks toward the frame edge)."""
    cx, cy = center or (W / 2, H / 2)
    col = argb(*_rgb(color), alpha)
    for _ in range(n):
        a = rng.uniform(0, 2 * math.pi)
        r0 = rng.uniform(0.45, 0.7) * W
        r1 = r0 + rng.uniform(0.2, 0.5) * W
        fr.line((cx + r0 * math.cos(a), cy + r0 * math.sin(a)), (cx + r1 * math.cos(a), cy + r1 * math.sin(a)),
                col, rng.uniform(0.2, 0.7))


# ----------------------------------------------------------------------------- cubes (Yutapon)
class Cube:
    def __init__(self, rng, i):
        ang = rng.uniform(0, 2 * math.pi)
        r = rng.uniform(3.5, 15)
        self.base = v3(r * math.cos(ang), 0, r * math.sin(ang))
        self.base[1] = ground_y(self.base[0], self.base[2])
        self.size = rng.uniform(1.0, 2.6)
        self.height = rng.uniform(3, 13)
        self.delay = rng.uniform(0, 6) + r * 0.25
        self.axis = norm(v3(rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-1, 1)))
        self.spin = rng.uniform(-0.03, 0.03)
        self.tilt = rng.uniform(0.2, 0.7)
        self.i = i

    def center(self, t):
        s = max(t - (69 + self.delay), 0)
        rise = self.height * (1 - math.exp(-s / 7.0))
        bob = 0.25 * math.sin(t * 0.08 + self.i) if s > 0 else 0
        return self.base + v3(0, rise + bob - (self.size * 0.5 if s <= 0 else 0), 0)

    def angle(self, t):
        s = max(t - (69 + self.delay), 0)
        return self.tilt * (1 - math.exp(-s / 9.0)) + self.spin * s

    def verts(self, t):
        c, a, h = self.center(t), self.angle(t), self.size / 2
        k = self.axis
        K = np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]])
        R = np.eye(3) + math.sin(a) * K + (1 - math.cos(a)) * K @ K
        return [c + R @ v3(sx * h, sy * h, sz * h) for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)]

    def top(self, t):
        return self.center(t) + v3(0, self.size / 2, 0)


FACES = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
LIGHT = norm(v3(-0.4, 0.8, -0.45))
CUBES = [Cube(random.Random(50 + i), i) for i in range(12)]


def draw_cube(fr, cube, cam, t, mode='normal'):
    if t < 66:
        return
    V = cube.verts(t)
    c = cube.center(t)
    for f in FACES:
        q = [V[i] for i in f]
        n = norm(np.cross(q[1] - q[0], q[3] - q[0]))
        if n @ (c - (q[0] + q[2]) / 2) > 0:
            n = -n
        if n @ (cam.pos - (q[0] + q[2]) / 2) <= 0:
            continue
        P = [cam.proj(p) for p in q]
        if any(p is None for p in P):
            continue
        lum = 0.35 + 0.65 * max(0.0, float(n @ LIGHT))
        shade = argb(int(70 + 120 * lum), int(52 + 90 * lum), int(40 + 70 * lum))
        fr.poly(P, shade, INK, cam.scale(c) * 0.5)


# ----------------------------------------------------------------------------- missiles (Itano)
class Missile:
    def __init__(self, rng, i, launch, origin):
        self.launch = launch
        d = norm(v3(rng.uniform(-1, 1), rng.uniform(0.2, 1.2), rng.uniform(-1, 1)))
        self.v0 = d * rng.uniform(18, 30)
        self.origin = origin
        self.spiral = rng.uniform(2.5, 5.0)
        self.phase = rng.uniform(0, 2 * math.pi)
        self.freq = rng.uniform(0.35, 0.7)
        self.offset = v3(rng.uniform(-3, 3), rng.uniform(-1, 2.5), rng.uniform(-3, 3))
        self.life = rng.uniform(34, 52)
        self.i = i
        self.path = None

    def simulate(self, target_at):
        pos, vel = self.origin.copy(), self.v0.copy()
        out = {}
        for k in range(int(self.life) + 1):
            t = self.launch + k
            out[t] = pos.copy()
            tgt = target_at(t - 6) + self.offset
            want = norm(tgt - pos) * (26 + k * 0.6)
            vel = vel + (want - vel) * min(0.05 + k * 0.004, 0.35)
            side = norm(np.cross(vel, v3(0, 1, 0)))
            upv = norm(np.cross(side, vel))
            sp = self.spiral * math.exp(-k / 40)
            wob = side * math.cos(self.phase + k * self.freq) + upv * math.sin(self.phase + k * self.freq)
            pos = pos + vel / FPS + wob * sp * self.freq / 6
        self.path = out
        self.end = self.launch + int(self.life)


def draw_missile(fr, m, cam, t):
    if t < m.launch:
        return
    if t <= m.end:
        head = m.path[t]
        hist = [m.path[k] for k in range(max(m.launch, t - 12), t + 1)]
    else:
        head = None
        hist = [m.path[k] for k in range(max(m.launch, m.end - 12 + (t - m.end) * 2), m.end + 1)]
    if len(hist) >= 3:                                     # smoke trail: thin at the head, wide behind
        n = len(hist) - 1
        for k in range(0, n - 1, 2):
            a, c, b = hist[k], hist[k + 1], hist[k + 2]
            pa, pc, pb = cam.proj(a), cam.proj(c), cam.proj(b)
            if pa is None or pc is None or pb is None:
                continue
            age = (n - k) / max(n, 1)
            alpha = int(200 * (1 - age) + 40)
            ctrl = (2 * pc[0] - (pa[0] + pb[0]) / 2, 2 * pc[1] - (pa[1] + pb[1]) / 2)
            fr.curve(pa, ctrl, pb, argb(240, 236, 228, alpha), cam.scale(c, 5) * (0.6 + 1.6 * age))
    if head is not None:
        p = cam.proj(head)
        if p is not None:
            fr.circle(p, max(2.0, 9 * cam.scale(head, 3)), YELLOW, 0.5, (10, 30, argb(255, 160, 60), 230),
                      fill=WHITE)
    elif t - m.end < 5:                                    # burst where it missed
        p = cam.proj(m.path[m.end])
        if p is not None:
            s = (t - m.end + 1) / 5
            fr.circle(p, 40 * s * cam.scale(m.path[m.end], 6), argb(255, 220, 140, int(255 * (1 - s))), 0.6,
                      (16, 40, argb(255, 140, 40), int(200 * (1 - s))), fill=argb(255, 245, 210, int(220 * (1 - s))))


# ----------------------------------------------------------------------------- choreography
def standoff_pose(f):
    if f is A:
        return pose(lean=12, ls=-20, le=30, rs=-35, re=20, wpn=-150, lh=25, lk=30, rh=-25, rk=15)
    return pose(lean=8, ls=40, le=60, rs=20, re=70, wpn=100, lh=20, lk=25, rh=-20, rk=10)


CROUCH = {A: pose(lean=40, ls=-40, le=40, rs=-60, re=30, wpn=-150, lh=70, lk=110, rh=-10, rk=80),
          B: pose(lean=35, ls=50, le=80, rs=-40, re=60, wpn=150, lh=70, lk=110, rh=-10, rk=80)}


def dash_pose(f, t):
    ph = t * 1.4
    s = math.sin(ph)
    base = pose(lean=55, ls=-70, le=30, rs=-80, re=10, wpn=-160 if f is A else 170,
                lh=35 * s + 25, lk=60 + 40 * max(s, 0), rh=-35 * s + 25, rk=60 + 40 * max(-s, 0))
    return base


def fighter_state(f, t):
    """-> pelvis, yaw, pitch, pose, smear(bool)."""
    side = -1 if f is A else 1
    yaw = 0 if f is A else 180
    x0 = 20 * side
    if t < 24:                                              # standoff + anticipation crouch
        P = mix(standoff_pose(f), CROUCH[f], ease((t - 10) / 13))
        x = x0
        drop = 0.35 * ease((t - 10) / 13)
        return v3(x, ground_y(x, 0) + 0.98 - drop, 0), yaw, 0, P, False
    if t < 50:                                              # subsonic dash
        s = (t - 24) / 26
        x = x0 + (-side) * 17.0 * (0.15 * s + 0.85 * ease_in(s) ** 0.8)
        hop = 0.25 * abs(math.sin(t * 0.9))
        return v3(x, ground_y(x, 0) + 0.8 + hop, 0), yaw, 0, dash_pose(f, t), True
    if t < 66:                                              # last metres: wind-up and swing
        s = (t - 50) / 16
        x = lerp(x0 + (-side) * 17.0, side * 0.95, ease_out(s))
        if f is A:
            wind = pose(lean=30, ls=-30, le=20, rs=160, re=20, wpn=10, lh=60, lk=60, rh=-30, rk=40)
            hit = pose(lean=35, ls=-50, le=30, rs=70, re=5, wpn=5, lh=60, lk=70, rh=-35, rk=30)
        else:
            wind = pose(lean=25, ls=60, le=40, rs=-120, re=30, wpn=40, lh=60, lk=60, rh=-30, rk=40)
            hit = pose(lean=35, ls=50, le=40, rs=75, re=10, wpn=-5, lh=60, lk=70, rh=-35, rk=30)
        P = mix(dash_pose(f, t), wind, ease(s * 2)) if s < 0.5 else mix(wind, hit, ease_in((s - 0.5) * 2))
        return v3(x, ground_y(x, 0) + 0.85, 0), yaw, 0, P, s < 0.5
    if t < 96:                                              # blades locked, sliding back from the blast
        s = (t - 66) / 30
        x = side * (0.95 + 0.7 * ease_out(s))
        bind = pose(lean=35, ls=-50, le=30, rs=72, re=8, wpn=3, lh=60, lk=70, rh=-35, rk=30)
        if f is B:
            bind = pose(lean=35, ls=50, le=40, rs=72, re=8, wpn=-3, lh=60, lk=70, rh=-35, rk=30)
        tremble = 2.0 * math.sin(t * 2.3)
        bind['rs'] += tremble
        return v3(x, ground_y(x, 0) + 0.85, 0), yaw, 0, bind, False
    if t < 144:                                             # close exchanges
        return melee_state(f, t)
    return air_state(f, t)


def melee_state(f, t):
    side = -1 if f is A else 1
    yaw = 0 if f is A else 180
    guard = pose(lean=25, ls=-40, le=40, rs=40, re=60, wpn=60, lh=45, lk=50, rh=-30, rk=30)
    if f is A:
        keys = [(96, guard),
                (100, pose(lean=10, ls=-60, le=20, rs=-30, re=80, wpn=80, lh=40, lk=50, rh=-40, rk=30)),
                (104, pose(lean=55, ls=-80, le=10, rs=90, re=0, wpn=0, lh=75, lk=60, rh=-45, rk=20)),   # thrust
                (110, guard),
                (115, pose(lean=10, ls=-20, le=90, rs=150, re=40, wpn=90, lh=40, lk=60, rh=-30, rk=40)),  # high block
                (120, guard),
                (126, pose(lean=30, ls=-90, le=10, rs=-60, re=10, wpn=10, lh=50, lk=60, rh=-20, rk=40)),
                (131, pose(lean=40, ls=60, le=10, rs=100, re=0, wpn=0, lh=70, lk=60, rh=-40, rk=30)),     # spin slash
                (136, pose(lean=-10, ls=-40, le=30, rs=30, re=60, wpn=60, lh=-30, lk=80, rh=40, rk=90)),
                (143, guard)]
        dx = [(96, 0.95), (104, 0.45), (110, 1.0), (120, 1.0), (131, 0.7), (143, 6.0)]
    else:
        keys = [(96, guard),
                (104, pose(lean=10, ls=60, le=60, rs=110, re=20, wpn=-20, lh=40, lk=60, rh=-30, rk=40)),  # parry
                (108, pose(lean=0, ls=40, le=30, rs=170, re=20, wpn=0, lh=30, lk=40, rh=-20, rk=30)),     # overhead
                (115, pose(lean=50, ls=60, le=40, rs=60, re=0, wpn=10, lh=70, lk=60, rh=-40, rk=30)),     # chop
                (120, guard),
                (128, pose(lean=-20, ls=60, le=30, rs=30, re=40, wpn=60, lh=-40, lk=100, rh=50, rk=110)),  # dodge back
                (131, guard),
                (136, pose(lean=-10, ls=40, le=30, rs=30, re=60, wpn=60, lh=-30, lk=80, rh=40, rk=90)),
                (143, guard)]
        dx = [(96, 0.95), (104, 1.05), (115, 0.6), (120, 1.0), (128, 1.8), (143, 6.0)]
    P = keyed(keys, t)
    d = _keyed_scalar(dx, t)
    x = side * d
    lift = 0.6 * math.sin(math.pi * min(max((t - 132) / 11, 0), 1))      # hop back apart
    pitch = 0
    if f is A and 121 <= t <= 131:
        yaw = (t - 121) / 10 * 360                                         # spin slash
    return v3(x, ground_y(x, 0) + 0.88 + lift, 0), yaw, pitch, P, False


def _keyed_scalar(keys, t):
    if t <= keys[0][0]:
        return keys[0][1]
    for (f0, a), (f1, b) in zip(keys, keys[1:]):
        if t <= f1:
            return lerp(a, b, ease((t - f0) / max(f1 - f0, 1e-6)))
    return keys[-1][1]


# B hops across cube tops during the missile chase
HOPS = [(168, None), (176, 3), (184, 7), (192, 1), (200, 9), (208, 5), (216, 10)]


def b_air(t):
    pts = []
    for fr_, ci in HOPS:
        p = v3(6.0, ground_y(6, 0) + 0.9, 0) if ci is None else CUBES[ci].top(fr_) + v3(0, 0.9, 0)
        pts.append((fr_, p))
    for (f0, p0), (f1, p1) in zip(pts, pts[1:]):
        if t <= f1:
            s = (t - f0) / (f1 - f0)
            p = p0 + (p1 - p0) * s + v3(0, 3.5 * math.sin(math.pi * s), 0)
            flip = -360 * ease(s) if (f0 // 8) % 2 == 0 else 0
            return p, flip, s
    return pts[-1][1], 0, 1.0


def air_state(f, t):
    if f is A:
        if t < 160:                                         # leap
            s = (t - 144) / 16
            p = v3(lerp(-6, -4, s), lerp(ground_y(6, 0) + 0.9, 17, ease_out(s)), 0)
            P = mix(pose(lean=30, lh=80, lk=120, rh=60, rk=120, ls=-60, rs=-70, re=20, wpn=-150),
                    pose(lean=-5, ls=-150, le=10, rs=-150, re=10, wpn=-160, lh=10, lk=40, rh=-10, rk=30), ease(s))
            return p, 0, 0, P, s < 0.6
        if t < 214:                                         # hover, arms spread, guiding the swarm
            p = v3(-4, 17 + 0.4 * math.sin(t * 0.15), 0)
            P = pose(lean=-5, ls=-110, le=10, rs=-110, re=10, wpn=-170, lh=15, lk=30, rh=-15, rk=40, spread=0.4)
            return p, 15 * math.sin(t * 0.05), 0, P, False
        if t < 222:                                         # dive at B, final slash
            s = (t - 214) / 8
            bt = b_air(216)[0]
            p = v3(-4, 17, 0) + (bt + v3(-1.6, 1.2, 0) - v3(-4, 17, 0)) * ease_in(s)
            P = mix(pose(lean=60, ls=-60, le=10, rs=170, re=10, wpn=0, lh=40, lk=90, rh=-10, rk=60),
                    pose(lean=70, ls=-60, le=20, rs=60, re=0, wpn=0, lh=60, lk=70, rh=-40, rk=30), ease(s))
            return p, 0, 30, P, True
        s = min((t - 222) / 30, 1)                          # falls back to the crater floor
        bt = b_air(216)[0]
        start = bt + v3(-1.6, 1.2, 0)
        land = v3(-8, ground_y(8, 0) + 0.9, 0)
        p = start + (land - start) * ease(s) + v3(0, 4 * math.sin(math.pi * s), 0)
        P = pose(lean=20, ls=-40, le=20, rs=-30, re=20, wpn=-150, lh=30, lk=40, rh=-20, rk=20)
        return p, 0, 0, P, False
    if t < 168:                                             # B on the ground, looking up
        x = 6.0
        P = pose(lean=-15, head=-30, ls=40, le=60, rs=30, re=70, wpn=100, lh=30, lk=40, rh=-20, rk=20)
        return v3(x, ground_y(x, 0) + 0.9, 0), 180, 0, P, False
    p, flip, s = b_air(min(t, 216))
    tuck = pose(lean=40, ls=30, le=100, rs=20, re=110, wpn=130, lh=110, lk=140, rh=100, rk=140)
    land = pose(lean=25, ls=40, le=50, rs=-30, re=60, wpn=120, lh=60, lk=80, rh=-20, rk=60)
    P = mix(land, tuck, math.sin(math.pi * s))
    return p, 180, flip, P, s < 0.8


def b_target(t):
    return fighter_state(B, max(min(t, 216), 168))[0] if t >= 168 else v3(6, ground_y(6, 0) + 0.9, 0)


MISSILES = []
_rngm = random.Random(99)
for _i in range(36):
    m = Missile(_rngm, _i, 160 + _i % 6, v3(-4, 17, 0) + v3(_rngm.uniform(-0.5, 0.5), _rngm.uniform(-0.3, 0.6), 0))
    m.simulate(b_target)
    MISSILES.append(m)


# ----------------------------------------------------------------------------- cameras per shot
def camera_at(t):
    rng = random.Random(500 + t)
    shake = (0.0, 0.0)
    if t < 24:
        drift = t * 0.03
        return Cam(v3(-23.2 + drift, 1.1, -1.6), v3(20, 2.6, 0), fov=165, fish=1.0, roll=18)
    if t < 50:                                              # 360 orbit around the closing fighters
        s = (t - 24) / 26
        ang = -math.pi / 2 + 2 * math.pi * ease(s)
        R = lerp(5.5, 3.4, s)
        c = fighter_state(A, t)[0] + v3(0, 0.4, 0)           # orbit hugs A; B rushes in
        pos = c + v3(R * math.cos(ang), 1.2 + 2.0 * math.sin(math.pi * s), R * math.sin(ang))
        return Cam(pos, c, fov=118, fish=0.75, roll=25 * math.sin(ang * 1.5),
                   shake=(rng.uniform(-6, 6), rng.uniform(-6, 6)))
    if t < 66:                                              # low close angle on the swing
        s = (t - 50) / 16
        return Cam(v3(lerp(-2.5, -1.0, s), 0.6, -3.6), v3(0, 1.6, 0), fov=lerp(120, 135, s), fish=0.6,
                   roll=-15 - 10 * s)
    if t < 69:                                              # impact frames: same framing, hard shake
        return Cam(v3(-1.0, 0.6, -3.6), v3(0, 1.6, 0), fov=135, fish=0.6, roll=-25 + 10 * (t - 66),
                   shake=(rng.uniform(-30, 30), rng.uniform(-30, 30)))
    if t < 96:                                              # pull back: shockwave and rising cubes
        s = (t - 69) / 27
        k = math.exp(-(t - 69) / 6)
        return Cam(v3(lerp(-6, -3, s), lerp(4, 6, s), lerp(-14, -24, ease_out(s))), v3(0, lerp(1.5, 5, s), 0),
                   fov=120, fish=0.7, roll=12, shake=(rng.uniform(-25, 25) * k, rng.uniform(-25, 25) * k))
    if t < 108:                                             # Obari: A's sword tip thrust at the lens
        JA = skeleton(*fighter_state(A, t)[:3], fighter_state(A, t)[3])
        tip = weapon_pts(JA, A)[1]
        pos = v3(1.25, 1.45, -1.1)
        return Cam(pos, (tip + JA['neck']) / 2, fov=125, fish=0.5, roll=-20)
    if t < 120:                                             # worm's-eye under the glaive chop
        return Cam(v3(-0.4, 0.25, -1.4), v3(0.4, 2.4, 0.3), fov=140, fish=0.7, roll=22)
    if t < 132:                                             # spin slash, wide and tilted
        s = (t - 120) / 12
        return Cam(v3(lerp(-1, 1, s), 1.0, -4.0), v3(0, 1.3, 0), fov=150, fish=0.9, roll=30 - 20 * s)
    if t < 144:                                             # disengage, tracking out
        s = (t - 132) / 12
        return Cam(v3(0, 1.5 + s, lerp(-5, -11, ease_out(s))), v3(0, 1.4, 0), fov=120, fish=0.7, roll=-12)
    if t < 160:                                             # worm's-eye on the leap
        pa = fighter_state(A, t)[0]
        return Cam(pa + v3(1.5, -3.5, -3.5), pa + v3(0, 0.5, 0), fov=150, fish=0.9, roll=-18)
    if t < 168:                                             # over A's shoulder: the swarm erupts
        s = (t - 160) / 8
        return Cam(v3(-7.5, 20, -6), v3(4, 2, 0), fov=lerp(110, 140, s), fish=0.7, roll=14)
    if t < 214:                                             # cross-cut missile POV / wide on B
        k = (t - 168) // 6
        s = ((t - 168) % 6) / 5
        pb = fighter_state(B, t)[0]
        if k % 2 == 0:                                      # warhead POV, crash zoom in
            m = MISSILES[(k * 7) % len(MISSILES)]
            head = m.path[min(t, m.end)]
            back = norm(head - pb)
            return Cam(head + back * 1.5, pb, fov=lerp(110, 35, ease_in(s)), fish=0.3, roll=lerp(-20, 20, s))
        return Cam(pb + v3(-10, 3, -12) * lerp(0.35, 0.9, ease_out(s)), pb + v3(0, 1, 0),
                   fov=lerp(60, 130, ease_out(s)), fish=0.8, roll=-16, shake=(rng.uniform(-8, 8), rng.uniform(-8, 8)))
    if t < 222:                                             # final strike
        pb = b_air(216)[0]
        return Cam(pb + v3(-3, -1.5, -6.5), pb + v3(-1, 1.5, 0), fov=135, fish=0.8, roll=-28,
                   shake=(rng.uniform(-14, 14), rng.uniform(-14, 14)))
    pb = b_air(216)[0]                                      # explosion: wide, settling
    k = math.exp(-(t - 222) / 8)
    return Cam(v3(-14, 4.5, -30), pb * 0.6 + v3(0, 2, 0), fov=115, fish=0.6, roll=10,
               shake=(rng.uniform(-30, 30) * k, rng.uniform(-30, 30) * k))


# ----------------------------------------------------------------------------- effects
def impact_frame(t, cam):
    """66-68: colour removed, black/white, rough inverted line art with radial cracks."""
    mode = 'impact_dark' if t != 67 else 'impact_light'
    fr = Frame2D(BLACK if mode == 'impact_dark' else WHITE, mode)
    rng = random.Random(t * 13)
    fr.layer = 'bg'
    draw_ground(fr, cam, t, boil=1.0)
    fr.layer = 'fg'
    for f in (A, B):
        pel, yaw, pitch, P, _ = fighter_state(f, 66)
        draw_fighter(fr, cam, skeleton(pel, yaw, pitch, P), f, th=2.2, glow=False, rng=rng, jitter=10)
    c = cam.proj(v3(0, 2.0, 0)) or (W / 2, H / 2)
    fr.layer = 'fx'
    for i in range(22):                                    # jagged flash rays from the clash point
        a = 2 * math.pi * i / 22 + rng.uniform(-0.1, 0.1) + t
        r = rng.uniform(0.15, 0.3) * W
        pts = [c]
        for _ in range(4):
            r += rng.uniform(0.12, 0.3) * W
            a += rng.uniform(-0.12, 0.12)
            pts.append((c[0] + r * math.cos(a), c[1] + r * math.sin(a)))
        for p, q in zip(pts, pts[1:]):
            fr.line(p, q, INK, rng.uniform(0.6, 3.5))
    fr.circle(c, 70 + 40 * (t - 66), INK, 3.0)
    return fr


def shockwave(fr, cam, t):
    s = t - 66
    if s < 0 or s > 26:
        return
    R = 34 * (1 - math.exp(-s / 6))
    a = int(255 * (1 - s / 26))
    n = 14
    for i in range(n):
        a0, a1 = 2 * math.pi * i / n, 2 * math.pi * (i + 1) / n
        p = v3(R * math.cos(a0), 0, R * math.sin(a0))
        q = v3(R * math.cos(a1), 0, R * math.sin(a1))
        p[1], q[1] = ground_y(p[0], p[2]) + 0.2, ground_y(q[0], q[2]) + 0.2
        draw_seg(fr, cam, p, q, argb(255, 250, 235, a), 1.6, (18, 40, argb(255, 200, 120), a), base=10)


def sparks(fr, cam, at, t, t0, n=10, color=YELLOW):
    s = t - t0
    if s < 0 or s > 4:
        return
    rng = random.Random(t0 * 31)
    c = cam.proj(at)
    if c is None:
        return
    k = cam.scale(at)
    for _ in range(n):
        a = rng.uniform(0, 2 * math.pi)
        r0 = (20 + 60 * s) * k
        r1 = r0 + rng.uniform(30, 90) * k
        fr.line((c[0] + r0 * math.cos(a), c[1] + r0 * math.sin(a)), (c[0] + r1 * math.cos(a), c[1] + r1 * math.sin(a)),
                color, 0.8 * k, (10, 30, argb(255, 170, 60), 220))
    if s < 2:
        fr.circle(c, 30 * k * (s + 1), WHITE, 0.5 * k, (20, 40, argb(255, 200, 90), 255), fill=WHITE)


def kanada_beam(fr, t, rng):
    """216-221: zigzag light splitting the frame diagonally, with angular Kanada flare shapes."""
    s = (t - 216) / 5
    p0, p1 = (-80, -60), (W + 80, H + 60)
    n = 11
    us = sorted([0.0, 1.0] + [rng.uniform(0.03, 0.97) for _ in range(n - 1)])
    pts = []
    sign = 1
    for i, u in enumerate(us):
        x, y = lerp(p0[0], p1[0], u), lerp(p0[1], p1[1], u)
        sign = -sign if rng.random() < 0.8 else sign
        off = sign * rng.uniform(40, 190) * (1 - 0.4 * s)
        pts.append((x + off * 0.55, y - off))
    for a, b in zip(pts, pts[1:]):
        fr.line(a, b, argb(255, 120, 40), 6 * (1 - 0.4 * s), (16, 30, argb(255, 90, 30), 200))
        fr.line(a, b, WHITE, 2.5 * (1 - 0.4 * s), None)
    for i in range(1, n, 2):                                # angular flare wedges along the bolt
        c = pts[i]
        L = rng.uniform(120, 260)
        a = rng.uniform(0, 2 * math.pi)
        tri = [c, (c[0] + L * math.cos(a), c[1] + L * math.sin(a)),
               (c[0] + L * 0.5 * math.cos(a + 0.45), c[1] + L * 0.5 * math.sin(a + 0.45))]
        fr.poly(tri, BLACK if i % 4 == 1 else argb(255, 230, 120), INK, 0.6)


def explosion(fr, cam, t, rng):
    """222+: sphere then smoke in three timings: on 1s (222-229), on 2s (230-245), on 3s (246-)."""
    if t < 230:
        te = t
    elif t < 246:
        te = 230 + (t - 230) // 2 * 2
    else:
        te = 246 + (t - 246) // 3 * 3
    s = te - 222
    c3 = b_air(216)[0] + v3(0, 0.5, 0)
    c = cam.proj(c3)
    if c is None:
        return
    k = cam.scale(c3, 30)
    R = (14 * (1 - math.exp(-s / 3.0))) * k * 28
    core_a = max(0, int(255 * (1 - s / 14)))
    if core_a:
        fr.circle(c, R, argb(255, 250, 220, core_a), 1.0, (60, 120, argb(255, 150, 40), core_a),
                  fill=argb(255, 252, 235, core_a))
    rr = random.Random(77)
    for i in range(16):                                   # smoke puffs: outline + fill, drift outward
        a = rr.uniform(0, 2 * math.pi)
        d = rr.uniform(0.5, 1.0)
        grow = 1 - math.exp(-s / (5 + 5 * d))
        dist = R * (0.55 + 0.6 * d) * (0.6 + 0.6 * grow)
        rise = -s * 3.0 * k
        pc = (c[0] + dist * math.cos(a), c[1] + dist * 0.75 * math.sin(a) + rise)
        pr = R * (0.28 + 0.25 * rr.random()) * (0.5 + grow)
        shade = int(lerp(120, 70, d))
        fr.circle(pc, pr, argb(40, 32, 30), 0.9, None, fill=argb(shade + 40, shade + 30, shade + 20))
        fr.circle((pc[0] - pr * 0.25, pc[1] - pr * 0.25), pr * 0.45, CLEAR, 0.1, None,
                  fill=argb(shade + 90, shade + 80, shade + 60))


# ----------------------------------------------------------------------------- frame assembly
def ghost_states(f, t):
    return [fighter_state(f, t - d) for d in (0.35, 0.7, 1.05)]


def build_frame(t):
    if 66 <= t <= 68:
        return impact_frame(t, camera_at(t))
    cam = camera_at(t)
    rng = random.Random(t * 7 + 3)
    bg = SKY
    if 216 <= t <= 221:
        bg = [WHITE, BLACK, SKY_HOT, BLACK, WHITE, SKY_HOT][t - 216]
    elif 222 <= t < 226:
        bg = SKY_HOT
    fr = Frame2D(bg)
    boil = 1.0 if 24 <= t < 50 else (0.6 if 69 <= t < 96 or 168 <= t < 214 else 0.15)
    fr.layer = 'bg'
    draw_ground(fr, cam, t, boil=boil)
    fr.layer = 'mid'
    for cube in CUBES:
        draw_cube(fr, cube, cam, t)
    shockwave(fr, cam, t)
    for m in MISSILES:
        if t >= 160:
            draw_missile(fr, m, cam, t)
    fr.layer = 'fg'
    for f in (A, B):
        if f is B and t >= 222:
            continue                                       # B vanishes into the blast
        pel, yaw, pitch, P, smear = fighter_state(f, t)
        J = skeleton(pel, yaw, pitch, P)
        hatch = 96 <= t < 144
        if smear:                                         # multiple smear copies + joint streaks
            for k, st in enumerate(ghost_states(f, t)):
                Jg = skeleton(st[0], st[1], st[2], st[3])
                draw_fighter(fr, cam, Jg, f, alpha=150 - 45 * k, th=0.7, glow=False)
            Jp = skeleton(*fighter_state(f, t - 1.5)[:3], fighter_state(f, t - 1.5)[3])
            for name in ('head', 'rhand', 'lhand', 'lfoot', 'rfoot', 'pelvis'):
                draw_seg(fr, cam, Jp[name], J[name], argb(30, 24, 26, 110), 2.2)
        draw_fighter(fr, cam, J, f, th=1.1, hatch=hatch, rng=rng, jitter=1.5)
    fr.layer = 'fx'
    if 24 <= t < 50 or 168 <= t < 222:
        speed_lines(fr, rng, 26, INK, alpha=120)
    for at, t0 in ((v3(0.2, 1.7, 0), 104), (v3(0.2, 2.2, 0), 115), (v3(0.0, 1.5, 0), 131)):
        sparks(fr, cam, at, t, t0)
    if 216 <= t <= 221:
        kanada_beam(fr, t, rng)
    if t >= 222:
        explosion(fr, cam, t, rng)
    return fr


def build(n=N_FRAMES):
    root = ET.Element('Sequence', {'Name': 'duel_demo', 'HeightWidthRatio': '0.5625', 'RatioX': '16',
                                   'RatioY': '9', 'FrameCount': str(n), 'BackgroundColor': SKY})
    frames = [build_frame(t) for t in range(n)]
    ids = IdPlan()
    for fr in frames:                                      # dry run: pool sizes
        used = {}
        for layer, kind, pts, *_ in fr.items:
            pool = (layer, 'poly', min(len(clip_poly(pts)), 40)) if kind == 'poly' else (layer, kind)
            if pool[1] == 'poly' and pool[2] < 3:
                continue
            used[pool] = used.get(pool, 0) + 1
            ids.need[pool] = max(ids.need.get(pool, 0), used[pool])
    ids.plan()
    for t, fr in enumerate(frames):
        fr.write(root, t, ids)
    return root


def _render(args):
    import sfa_render
    xml_frame, size = args
    w, h = size
    return sfa_render.render_frame(ET.fromstring(xml_frame), w, h).tobytes()


def preview(root, out, size=(960, 540)):
    import subprocess
    from multiprocessing import Pool
    frames = [ET.tostring(f, encoding='unicode') for f in root.findall('Frame')]
    proc = subprocess.Popen(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24',
                             '-s', f'{size[0]}x{size[1]}', '-r', str(FPS), '-i', '-', '-pix_fmt', 'yuv420p',
                             '-c:v', 'libx264', '-crf', '20', str(out)], stdin=subprocess.PIPE)
    with Pool() as pool:
        for img in pool.imap(_render, [(f, size) for f in frames], chunksize=2):
            proc.stdin.write(img)
    proc.stdin.close()
    proc.wait()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('out')
    ap.add_argument('--preview')
    ap.add_argument('--size', default='960x540')
    ap.add_argument('--frames', type=int, default=N_FRAMES)
    a = ap.parse_args(argv)
    root = build(a.frames)
    sfa.write_sfa(root, a.out)
    xml_bytes = len(ET.tostring(root))
    print(f'{a.frames}프레임, XML {xml_bytes / 2**20:.1f} MB, '
          f'AO 최대 {max(len(f.findall("AO")) for f in root.findall("Frame"))}개/프레임 → {a.out} (트위닝·재생 FPS = 24,24)')
    if a.preview:
        preview(root, a.preview, tuple(int(v) for v in a.size.split('x')))
        print('미리보기 →', a.preview)


if __name__ == '__main__':
    main()
