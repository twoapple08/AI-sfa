#!/usr/bin/env python3
"""Reference renderer for Stick Fighter SFA frames (work in progress).

Built from static AOT reading plus APP-R1 app-video measurements
(docs/APP-R1-RENDER-REFERENCE-PROTOCOL-2026-10-16.md). It is an approximation
whose error against real app output is measured, not a copy of the app renderer.
Requires numpy.
"""
import argparse
import math
from pathlib import Path

import numpy as np

import sfa

# Calibrated against APP-R1 (1920x1080). Values marked fitted are refined by tools/fit_render.py.
PARAMS = {
    'padding_px_at_1080': 10.52,    # DrawInformation padding P, measured (APP-R1 swatch edges)
    'stroke_px_per_scale': 9.0,     # fitted: core stroke width per ThicknessScale at 1080p
    'glow_w_per_thickness': 0.78,   # fitted: glow band width W (px) per GlowThickness
    'glow_sigma_per_radius': 1.0,   # fitted: sigma (px) per GlowRadius
    'glow_sigma_floor': 0.29,       # sigma = sqrt(R^2 + 0.29^2) (static, DPR 1)
    'offset_x': 0.19,               # measured sub-pixel origin shift (px at 1080p)
    'offset_y': 0.08,
}


def argb(value):
    v = int(value) & 0xFFFFFFFF
    return ((v >> 16) & 255, (v >> 8) & 255, v & 255, (v >> 24) & 255)


def erf(x):
    # Abramowitz-Stegun 7.1.26, |error| < 1.5e-7
    s = np.sign(x)
    a = np.abs(x)
    t = 1.0 / (1.0 + 0.3275911 * a)
    y = 1.0 - (((((1.061405429 * t - 1.453152027) * t) + 1.421413741) * t - 0.284496736) * t
               + 0.254829592) * t * np.exp(-a * a)
    return s * y


def phi(x):
    return 0.5 * (1.0 + erf(x / math.sqrt(2.0)))


class Canvas:
    def __init__(self, width=1920, height=1080, ratio=0.5625, params=None):
        self.w, self.h = width, height
        self.p = dict(PARAMS, **(params or {}))
        # APP-R1 measured a uniform shrink about the centre: usable width = W - 2P and
        # height = width * ratio (horizontal margin P, vertical margin P * ratio). Applying the
        # static DrawInformation formula to an exact 1920x1080 canvas would instead be
        # height-limited (1080 - 2P), which does not match the measured output.
        pad = self.p['padding_px_at_1080'] * width / 1920.0
        uw = max(width - 2 * pad, 1)
        uh = uw * ratio
        if uh > height:
            uh, uw = height, height / ratio
        self.ox, self.oy, self.uw, self.uh = (width - uw) / 2, (height - uh) / 2, uw, uh
        self.px_scale = uh / 1068.0  # stroke/glow constants were fitted at 1080p output
        self.img = np.zeros((height, width, 3))
        ys, xs = np.mgrid[0:height, 0:width]
        self.X, self.Y = xs + 0.5, ys + 0.5

    def to_px(self, x, y):
        return (self.ox + x / 100.0 * self.uw + self.p['offset_x'] * self.px_scale,
                self.oy + y / 100.0 * self.uh + self.p['offset_y'] * self.px_scale)

    def fill_bg(self, color):
        r, g, b, _ = argb(color)
        self.img[:] = (r, g, b)

    def blend(self, cov, color, alpha_scale=1.0, box=None):
        r, g, b, a = argb(color)
        alpha = np.clip(cov, 0, 1) * (a / 255.0) * alpha_scale
        if box is None:
            region = self.img
        else:
            y0, y1, x0, x1 = box
            region = self.img[y0:y1, x0:x1]
        region += (np.array([r, g, b]) - region) * alpha[..., None]

    def box(self, pts, margin):
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        x0 = max(int(min(xs) - margin) - 1, 0)
        x1 = min(int(max(xs) + margin) + 2, self.w)
        y0 = max(int(min(ys) - margin) - 1, 0)
        y1 = min(int(max(ys) + margin) + 2, self.h)
        if x0 >= x1 or y0 >= y1:
            return None
        return y0, y1, x0, x1


def polyline_distance(X, Y, pts):
    d = np.full(X.shape, np.inf)
    for (ax, ay), (bx, by) in zip(pts, pts[1:]):
        vx, vy = bx - ax, by - ay
        ll = vx * vx + vy * vy
        if ll < 1e-12:
            t = np.zeros(X.shape)
        else:
            t = np.clip(((X - ax) * vx + (Y - ay) * vy) / ll, 0, 1)
        d = np.minimum(d, np.hypot(X - ax - t * vx, Y - ay - t * vy))
    if len(pts) == 1:
        d = np.hypot(X - pts[0][0], Y - pts[0][1])
    return d


def quad(p0, p1, p2, t):
    u = 1 - t
    return (u * u * p0[0] + 2 * u * t * p1[0] + t * t * p2[0],
            u * u * p0[1] + 2 * u * t * p1[1] + t * t * p2[1])


def object_path(obj, cv, t0=0.0, t1=1.0, samples=96):
    """Pixel polyline of an AO between parameters t0..t1; None for circles."""
    pts = sorted(obj.findall('AP'), key=lambda p: int(p.get('Index', '0')))
    xy = [cv.to_px(float(p.get('X')), float(p.get('Y'))) for p in pts]
    kind = obj.get('TypeId')
    if kind == '3' and len(xy) >= 3:
        n = max(2, int(samples * abs(t1 - t0)) + 1)
        return [quad(xy[0], xy[1], xy[2], t0 + (t1 - t0) * i / (n - 1)) for i in range(n)]
    if kind == '2':
        return None
    if len(xy) >= 2:
        a, b = xy[0], xy[1]
        return [(a[0] + (b[0] - a[0]) * t0, a[1] + (b[1] - a[1]) * t0),
                (a[0] + (b[0] - a[0]) * t1, a[1] + (b[1] - a[1]) * t1)]
    return xy


def circle_geom(obj, cv):
    pts = sorted(obj.findall('AP'), key=lambda p: int(p.get('Index', '0')))
    (ax, ay), (bx, by) = [cv.to_px(float(p.get('X')), float(p.get('Y'))) for p in pts[:2]]
    return ((ax + bx) / 2, (ay + by) / 2), math.hypot(bx - ax, by - ay) / 2


def object_distance(obj, cv, box):
    y0, y1, x0, x1 = box
    X, Y = cv.X[y0:y1, x0:x1], cv.Y[y0:y1, x0:x1]
    if obj.get('TypeId') == '2':
        (cx, cy), r = circle_geom(obj, cv)
        return np.abs(np.hypot(X - cx, Y - cy) - r)
    return polyline_distance(X, Y, object_path(obj, cv))


def object_extent(obj, cv):
    if obj.get('TypeId') == '2':
        (cx, cy), r = circle_geom(obj, cv)
        return [(cx - r, cy - r), (cx + r, cy + r)]
    return object_path(obj, cv)


def stroke_width(obj, cv, seq_thickness):
    scale = float(obj.get('ThicknessScale', '1') or 1)
    if not math.isfinite(scale) or scale <= 0:
        scale = 1.0
    return cv.p['stroke_px_per_scale'] * scale * seq_thickness / 100.0 * cv.px_scale


def draw_core(obj, cv, seq_thickness):
    w = stroke_width(obj, cv, seq_thickness)
    box = cv.box(object_extent(obj, cv), w / 2 + 2)
    if box is None:
        return
    d = object_distance(obj, cv, box)
    cv.blend(w / 2 - d + 0.5, obj.get('Color', '-16777216'), box=box)


def draw_glow(obj, cv):
    radius = float(obj.get('GlowRadius', '0') or 0)
    alpha = float(obj.get('GlowAlpha', '0') or 0) / 255.0
    thickness = float(obj.get('GlowThickness', '0') or 0)
    if radius <= 0 or alpha <= 0 or thickness <= 0:
        return
    sigma = math.hypot(radius * cv.p['glow_sigma_per_radius'], cv.p['glow_sigma_floor']) * cv.px_scale
    half = thickness * cv.p['glow_w_per_thickness'] * cv.px_scale / 2
    box = cv.box(object_extent(obj, cv), half + 4 * sigma + 1)
    if box is None:
        return
    path = object_path(obj, cv) if obj.get('TypeId') == '1' else None
    if path and len(path) == 2 and math.dist(*path) >= 1e-5 and cv.p.get('glow_line_separable', True):
        # Straight line: shader body coverage = along-axis erf window x cross-axis band
        # (Cbody = B(-u, L-u) * A in the static reading).
        (ax, ay), (bx, by) = path
        length = math.dist(path[0], path[1])
        ex, ey = (bx - ax) / length, (by - ay) / length
        y0, y1, x0, x1 = box
        dx, dy = cv.X[y0:y1, x0:x1] - ax, cv.Y[y0:y1, x0:x1] - ay
        u, v = dx * ex + dy * ey, ex * dy - ey * dx
        band = lambda hh: phi((hh - v) / sigma) - phi((-hh - v) / sigma)
        cov = band(half) * (phi(u / sigma) - phi((u - length) / sigma))
        # Semicircular caps of radius `half` beyond each end, Gauss-Legendre over the axis.
        nodes, weights = np.polynomial.legendre.leggauss(16)
        a_k, w_k = (nodes + 1) * half / 2, weights * half / 2
        g = lambda x: np.exp(-x * x / (2 * sigma * sigma)) / (math.sqrt(2 * math.pi) * sigma)
        for a, w in zip(a_k, w_k):
            hh = math.sqrt(max(half * half - a * a, 0.0))
            b = band(hh)
            cov = cov + w * (g(u - length - a) + g(-u - a)) * b
    else:
        d = object_distance(obj, cv, box)
        cov = phi((half - d) / sigma) - phi((-half - d) / sigma)
    cv.blend(cov, obj.get('GlowColor', '-1'), alpha, box=box)


def fill_polygon_coverage(contours, cv, ss=3):
    """Even-odd coverage with ss x ss supersampling inside the bbox."""
    pts = [p for c in contours for p in c]
    box = cv.box(pts, 1)
    if box is None:
        return None, None
    y0, y1, x0, x1 = box
    acc = np.zeros((y1 - y0, x1 - x0))
    offs = [(i + 0.5) / ss - 0.5 for i in range(ss)]
    for oy in offs:
        for ox in offs:
            X = cv.X[y0:y1, x0:x1] + ox
            Y = cv.Y[y0:y1, x0:x1] + oy
            inside = np.zeros(X.shape, dtype=bool)
            for c in contours:
                for (ax, ay), (bx, by) in zip(c, c[1:] + c[:1]):
                    if ay == by:
                        continue
                    cond = (ay > Y) != (by > Y)
                    xint = ax + (Y - ay) * (bx - ax) / (by - ay)
                    inside ^= cond & (X < xint)
            acc += inside
    return acc / (ss * ss), box


def fill_contours(region, objects, cv):
    contours = {}
    for seg in region.findall('FS'):
        obj = objects.get(seg.get('ObjId'))
        if obj is None:
            continue
        key = int(float(seg.get('Contour', '0') or 0))
        if seg.get('Kind') == '1' or obj.get('TypeId') == '2':
            (cx, cy), r = circle_geom(obj, cv)
            ring = [(cx + r * math.cos(2 * math.pi * i / 128), cy + r * math.sin(2 * math.pi * i / 128))
                    for i in range(128)]
            contours.setdefault(('ring', key, seg.get('ObjId')), []).extend(ring)
            continue
        t0 = float(seg.get('StartT', '0') or 0)
        t1 = float(seg.get('EndT', '1') or 1)
        path = object_path(obj, cv, t0, t1)
        if path:
            contours.setdefault(key, []).extend(path)
    return [c for c in contours.values() if len(c) >= 3]


def group_units(frame):
    """Union AOs connected by group-child flags (resolved to the root parent)."""
    owner, flags = {}, {}
    for obj in frame.findall('AO'):
        for p in obj.findall('AP'):
            owner[p.get('ID')] = obj.get('ID')
            flags[p.get('ID')] = int(p.get('Flags', '0'))
    parent = {o.get('ID'): o.get('ID') for o in frame.findall('AO')}

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a
    for pid, f in flags.items():
        seen, cur = {pid}, pid
        while flags.get(cur, 0) & 0x10:
            nxt = str(flags[cur] >> 6)
            if nxt not in flags or nxt in seen:
                cur = None
                break
            seen.add(nxt)
            cur = nxt
        if cur and cur != pid and not flags[cur] & 0x10 and (flags[cur] & 0x2e) == 2:
            parent[find(owner[pid])] = find(owner[cur])
    return find


def render_frame(frame, width=1920, height=1080, params=None, seq_thickness=100.0):
    cv = Canvas(width, height, params=params)
    cv.fill_bg(frame.get('BackgroundColor', '-1'))
    hidden = {l.get('ID') for l in frame.findall('LayerDef') if l.get('Visible', 'true') == 'false'}
    # APP-T1: objects on a hidden layer are not drawn in exported frames.
    objects = {o.get('ID'): o for o in frame.findall('AO') if o.get('LayerId') not in hidden}
    order = lambda o: (float(o.get('DrawOrder', '0') or 0), int(o.get('ID')) if o.get('ID', '').lstrip('-').isdigit() else 0)
    find = group_units(frame)
    units = {}
    for obj in objects.values():
        units.setdefault(find(obj.get('ID')), []).append(obj)
    fills_before = {}
    for region in frame.iter('FR'):
        refs = [objects[s.get('ObjId')] for s in region.findall('FS') if s.get('ObjId') in objects]
        if refs:
            # APP-T1: a fill is drawn below all of its boundary objects (anchor = lowest DrawOrder).
            fills_before.setdefault(find(min(refs, key=order).get('ID')), []).append(region)
    for key in sorted(units, key=lambda k: min(order(o) for o in units[k])):
        members = sorted(units[key], key=order)
        for region in fills_before.get(key, []):
            cov, box = fill_polygon_coverage(fill_contours(region, objects, cv), cv)
            if cov is not None:
                cv.blend(cov, region.get('Color', '0'), box=box)
        for obj in members:
            draw_glow(obj, cv)
            if len(members) == 1:
                draw_core(obj, cv, seq_thickness)
        if len(members) > 1:
            for obj in members:
                draw_core(obj, cv, seq_thickness)
    return np.clip(np.rint(cv.img), 0, 255).astype(np.uint8)


def main():
    ap = argparse.ArgumentParser(description='Render one SFA frame to PNG (reference approximation).')
    ap.add_argument('sfa_path')
    ap.add_argument('frame', type=int, help='1-based frame number')
    ap.add_argument('out_png')
    ap.add_argument('--size', default='1920x1080')
    a = ap.parse_args()
    from PIL import Image
    w, h = (int(v) for v in a.size.split('x'))
    root = sfa.read_sfa(a.sfa_path)
    Image.fromarray(render_frame(root.findall('Frame')[a.frame - 1], w, h)).save(a.out_png)


if __name__ == '__main__':
    main()
