#!/usr/bin/env python3
"""영상 클립 → SFA 두 방식: 모작(mosaku)과 로토스코핑(roto). (트위닝, 재생) FPS = (24, 24).

모작: 인물만 앱 기본 스틱맨(pipeline.to_sfa의 관절·머리 처리)으로, 선 색 = 그 인물의 머리카락 색.
      배경·이펙트는 인물을 지운(inpaint) 화면을 샷별 팔레트로 색 면 분해해 곡선 다각형으로 따라 그림.
로토: 인물까지 화면 전체를 색 면으로 따라 그림(배경 층 위에 인물 층).

가벼운 파일: 색 면은 2차 곡선 고리(TypeId 3, 직선 다각형의 절반 객체), 프레임당 객체 예산, 가장 넓은
색은 프레임 배경색(객체 0개). 앞뒤 순서는 색 면 순위마다 레이어 하나(같은 층 안의 채우기 순서는 앱이
보장하지 않음). AO ID는 make_duel의 고정 풀(형태·레이어 고정).

  python tools/make_copy.py DATA_DIR CLIP_ID OUT_DIR [--mode both|mosaku|roto] [--preview]
  DATA_DIR/media/<id>.mp4 (24fps), <id>.shots.json, <id>.motion.json 은 pipeline.shots/pose/motion 결과.
"""
import argparse
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tools'))
import sfa  # noqa: E402
import make_duel as md  # noqa: E402
from pipeline import to_sfa  # noqa: E402

AW, AH = 480, 270                 # analysis size
SX = md.W / AW                    # analysis px -> SFA px (1920x1080)
K_BG, K_ROTO = 7, 8               # palette sizes (brightness levels) per shot
BUDGET = {'mosaku': 80, 'roto': 160}      # curve objects per frame for colour regions
MIN_AREA = 40                     # analysis px^2


def argb_of(rgb):
    return md.argb(int(rgb[0]), int(rgb[1]), int(rgb[2]))


# ----------------------------------------------------------------------------- inputs
def read_frames(path):
    cap = cv2.VideoCapture(str(path))
    out = []
    while True:
        ok, f = cap.read()
        if not ok:
            break
        out.append(cv2.resize(f, (AW, AH), interpolation=cv2.INTER_AREA))
    return np.stack(out)


def person_masks(path, frames, cache):
    if Path(cache).exists():
        return np.load(cache)['m']
    from ultralytics import YOLO
    name = ROOT / 'models' / 'yolo11s-seg.pt'
    model = YOLO(str(name) if name.exists() else 'yolo11s-seg.pt')
    if not name.exists() and Path('yolo11s-seg.pt').exists():
        Path('yolo11s-seg.pt').replace(name)
    cap = cv2.VideoCapture(str(path))
    masks = np.zeros((len(frames), AH, AW), np.uint8)
    for t in range(len(frames)):
        ok, f = cap.read()
        if not ok:
            break
        r = model.predict(f, imgsz=640, classes=[0], conf=0.25, verbose=False, retina_masks=False)[0]
        if r.masks is not None:
            m = r.masks.data.cpu().numpy().max(axis=0)
            masks[t] = cv2.resize((m > 0.5).astype(np.uint8), (AW, AH), interpolation=cv2.INTER_NEAREST)
    np.savez_compressed(cache, m=masks)
    return masks


SKEL = [(5, 7), (7, 9), (6, 8), (8, 10), (5, 6), (5, 11), (6, 12), (11, 12), (11, 13), (13, 15), (12, 14), (14, 16)]


def pose_masks(motion, n):
    """Body area from the cleaned joints (thick limbs + head disc): segmentation misses some anime
    characters entirely, so the person region is seg OR pose."""
    out = np.zeros((n, AH, AW), np.uint8)
    for c in motion['characters']:
        for t, j in enumerate(c['joints']):
            vf = c['start'] + t
            if vf >= n:
                continue
            P = {k: (j[k][0] / SX, j[k][1] / SX) for k in range(17) if j[k][0] is not None}
            if 5 in P and 11 in P:
                torso = np.hypot(P[5][0] - P[11][0], P[5][1] - P[11][1])
            elif 5 in P and 6 in P:
                torso = 2 * np.hypot(P[5][0] - P[6][0], P[5][1] - P[6][1])
            else:
                torso = 20.0
            w = max(3, int(0.35 * torso))
            for a, b in SKEL:
                if a in P and b in P:
                    cv2.line(out[vf], tuple(map(int, P[a])), tuple(map(int, P[b])), 1, w)
            face = [P[k] for k in range(5) if k in P]
            if face and 5 in P and 6 in P:
                fc = np.mean(face, 0)
                nk = ((P[5][0] + P[6][0]) / 2, (P[5][1] + P[6][1]) / 2)
                d = fc - np.array(nk)
                r = max(4, int(1.0 * np.hypot(*d)))
                cv2.circle(out[vf], tuple(map(int, fc + 0.35 * d)), r, 1, -1)
                cv2.line(out[vf], tuple(map(int, nk)), tuple(map(int, fc)), 1, w)
    return out


# ----------------------------------------------------------------------------- colour regions
def palette(pixels_bgr, k):
    """k colours spread over the brightness range: pixels are sampled evenly per lightness band so a
    mostly dark frame still gets separate levels for its bright parts (characters, light, props)."""
    lab = cv2.cvtColor(pixels_bgr.reshape(-1, 1, 3), cv2.COLOR_BGR2LAB).reshape(-1, 3).astype(np.float32)
    rng = np.random.default_rng(0)
    bands = np.minimum((lab[:, 0] / 256 * 8).astype(int), 7)
    pick_ = []
    for b in range(8):
        idx = np.flatnonzero(bands == b)
        if len(idx):
            pick_.append(rng.choice(idx, min(len(idx), 6000), replace=False))
    lab = lab[np.concatenate(pick_)]
    k = max(1, min(k, len(np.unique(lab, axis=0))))
    w = np.array([1.6, 1.0, 1.0], np.float32)              # separate brightness levels first
    _, _, centers = cv2.kmeans(lab * w, k, None, (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.5),
                               3, cv2.KMEANS_PP_CENTERS)
    return centers / w


def label(img_bgr, centers):
    lab = cv2.cvtColor(cv2.GaussianBlur(img_bgr, (5, 5), 0), cv2.COLOR_BGR2LAB).astype(np.float32)
    d = ((lab[:, :, None, :] - centers[None, None]) ** 2).sum(-1)
    lab_idx = d.argmin(-1).astype(np.uint8)
    return cv2.medianBlur(lab_idx, 5)


def rgb_of(centers):
    lab = centers.reshape(-1, 1, 3).clip(0, 255).astype(np.uint8)
    return cv2.cvtColor(lab, cv2.COLOR_LAB2RGB).reshape(-1, 3)


def curve_loop(contour):
    """Contour -> [on0, ctrl0, on1, ctrl1, ...] in SFA px; the curve passes through every vertex."""
    peri = cv2.arcLength(contour, True)
    approx = cv2.approxPolyDP(contour, max(1.6, 0.006 * peri), True).reshape(-1, 2).astype(float)
    v = len(approx)
    if v < 3:
        return None
    target = min(max(v + (v % 2), 4), 24)
    if target != v:                                   # resample along the polygon to an even count
        seg = np.vstack([approx, approx[:1]])
        lens = np.hypot(*np.diff(seg, axis=0).T)
        cum = np.concatenate([[0], np.cumsum(lens)])
        s = np.linspace(0, cum[-1], target, endpoint=False)
        approx = np.stack([np.interp(s, cum, seg[:, 0]), np.interp(s, cum, seg[:, 1])], 1)
    pts = approx * SX
    out = []
    for j in range(0, len(pts), 2):
        on, mid, nxt = pts[j], pts[j + 1], pts[(j + 2) % len(pts)]
        ctrl = 2 * mid - (on + nxt) / 2                # quadratic through `mid` at t = 0.5
        out += [tuple(on), tuple(ctrl)]
    return out


def level_regions(labels, order):
    """Stacked level sets: level r = every pixel whose colour is at rank >= r (ranks dark -> light).
    Each level is drawn over the one below, so bright structures stay whole shapes."""
    rank = np.zeros(256, np.uint8)
    for r, li in enumerate(order):
        rank[li] = r
    rk = rank[labels]
    out = {}
    kernel = np.ones((3, 3), np.uint8)
    for r in range(1, len(order)):
        m = cv2.morphologyEx((rk >= r).astype(np.uint8), cv2.MORPH_OPEN, kernel)
        cs, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for c in cs:
            a = cv2.contourArea(c)
            if a >= MIN_AREA:
                loop = curve_loop(c)
                if loop:
                    out.setdefault(r - 1, []).append((a, loop))
    return out


def pick(regs, budget, weight=None):
    """Most visible shapes first (area x brightness step to the level below) until the curve budget
    is spent; a shape too costly for what is left is skipped, smaller ones may still fit."""
    weight = weight or {}
    flat = sorted(((a * weight.get(r, 1.0), r, loop) for r, lst in regs.items() for a, loop in lst),
                  key=lambda x: -x[0])
    keep, used = [], 0
    for _, r, loop in flat:
        cost = len(loop) // 2
        if used + cost > budget:
            continue
        keep.append((r, loop))
        used += cost
    return keep


# ----------------------------------------------------------------------------- greedy (error-driven) shapes
EW, EH = 192, 108                 # error-evaluation grid
MAX_DEPTH = 10                    # stacking layers for greedy shapes


def loop_polygon(loop, scale):
    """Curve loop (SFA px) -> dense polygon at `scale` (px per SFA px) for rasterising."""
    pts = []
    n = len(loop)
    for j in range(0, n, 2):
        a, c, b = np.array(loop[j]), np.array(loop[j + 1]), np.array(loop[(j + 2) % n])
        for u in np.linspace(0, 1, 8, endpoint=False):
            pts.append((1 - u) ** 2 * a + 2 * u * (1 - u) * c + u * u * b)
    return (np.array(pts) * scale).round().astype(np.int32)


def candidates(img_bgr, cb, valid=None):
    """Shapes worth trying: connected pieces of every palette colour and of every brightness level
    set (both directions), each as a curve loop."""
    labels = label(img_bgr, cb)
    order = list(np.argsort(cb[:, 0]))
    rank = np.zeros(256, np.uint8)
    for r, li in enumerate(order):
        rank[li] = r
    rk = rank[labels]
    masks = [(labels == li) for li in range(len(cb))]
    masks += [(rk >= r) for r in range(1, len(order))] + [(rk <= r) for r in range(len(order) - 1)]
    kernel = np.ones((3, 3), np.uint8)
    out = []
    for m in masks:
        m = cv2.morphologyEx(m.astype(np.uint8), cv2.MORPH_OPEN, kernel)
        if valid is not None:
            m &= valid
        cs, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for c in cs:
            if cv2.contourArea(c) >= MIN_AREA:
                loop = curve_loop(c)
                if loop:
                    out.append(loop)
    return out


def greedy_shapes(img_bgr, cb, budget, valid=None):
    """Pick shapes that cut the colour error (Lab, on a coarse grid) most per curve spent. Each shape
    is painted with the mean colour under it; later shapes go on higher layers where they overlap."""
    small = cv2.resize(img_bgr, (EW, EH), interpolation=cv2.INTER_AREA)
    target = cv2.cvtColor(small, cv2.COLOR_BGR2LAB).astype(np.float32)
    flat = target.reshape(-1, 3)
    bg = np.median(flat, 0)
    cur = np.broadcast_to(bg, target.shape).copy()
    scale = EW / md.W
    cands = []
    for loop in candidates(img_bgr, cb, valid):
        m = np.zeros((EH, EW), np.uint8)
        cv2.fillPoly(m, [loop_polygon(loop, scale)], 1)
        idx = np.flatnonzero(m)
        if len(idx) >= 3:
            cands.append((loop, idx, len(loop) // 2))
    depth = np.zeros(EH * EW, np.int16)
    err = np.linalg.norm(cur.reshape(-1, 3) - flat, axis=1)
    curf = cur.reshape(-1, 3)
    picked, used = [], 0
    while cands and used < budget:
        best, best_s = None, 0.0
        for n, (loop, idx, cost) in enumerate(cands):
            if used + cost > budget:
                continue
            col = flat[idx].mean(0)
            gain = err[idx].sum() - np.linalg.norm(flat[idx] - col, axis=1).sum()
            s = gain / cost
            if s > best_s:
                best, best_s = n, s
        if best is None:
            break
        loop, idx, cost = cands.pop(best)
        lay = int(depth[idx].max())
        if lay >= MAX_DEPTH:
            continue
        col = flat[idx].mean(0)
        curf[idx] = col
        err[idx] = np.linalg.norm(flat[idx] - col, axis=1)
        depth[idx] = lay + 1
        rgb = cv2.cvtColor(col.reshape(1, 1, 3).clip(0, 255).astype(np.uint8), cv2.COLOR_LAB2RGB).reshape(3)
        picked.append((lay, loop, tuple(int(v) for v in rgb)))
        used += cost
    bg_rgb = cv2.cvtColor(bg.reshape(1, 1, 3).clip(0, 255).astype(np.uint8), cv2.COLOR_LAB2RGB).reshape(3)
    return tuple(int(v) for v in bg_rgb), picked


# ----------------------------------------------------------------------------- stickmen (모작)
PINK_MIN = 0.06                   # share of pink-hair pixels around the head that marks pink hair


def hair_pixels(c, frames, masks):
    """Pixels around the head top of one track piece, split into pink hair (R high, blue above green:
    clothes have B~G, skin B<G under this grading) and dark hair (not the black backdrop)."""
    pink, dark = [], []
    yy, xx = np.ogrid[:AH, :AW]
    for t, joints in enumerate(c['joints'][::2]):
        vf = c['start'] + 2 * t
        face = [j for j in joints[0:5] if j[0] is not None]
        if not face or joints[5][0] is None or joints[6][0] is None:
            continue
        fc = np.mean([[j[0], j[1]] for j in face], 0) / SX
        nk = np.array([(joints[5][0] + joints[6][0]) / 2, (joints[5][1] + joints[6][1]) / 2]) / SX
        d = fc - nk
        n = np.hypot(*d)
        if n < 3:
            continue
        hc = fc + d * 0.8
        rad = max(3, int(0.7 * n))
        sel = ((xx - hc[0]) ** 2 + (yy - hc[1]) ** 2 <= rad * rad) & (masks[vf] > 0)
        px = frames[vf][sel].astype(int)                      # BGR
        b, g, r = px[:, 0], px[:, 1], px[:, 2]
        pink.append(px[(r > 170) & (b > g + 8) & (b > 45)])
        dark.append(px[((r + g + b) < 120) & ((r + g + b) > 20)])
    cat = lambda L: np.concatenate(L) if L else np.zeros((0, 3), int)
    return cat(pink), cat(dark)


def stick_tracks(motion, frames, masks):
    """[(slot frames {vf: 11 canvas-% points}, thickness, {vf: hair rgb})] over every shot.
    Two characters: pink hair (Yuji) and dark hair (Higuruma). Each track piece is classified by its
    pink-hair share; when two pieces share frames only the pinker one may be pink."""
    shots = sorted({c['shot'] for c in motion['characters']})
    per_shot, info = [], {}
    for shot in shots:
        chars = [c for c in motion['characters'] if c['shot'] == shot and len(c['joints']) >= 3]
        slots = to_sfa.assign_slots(chars, motion['size'][1], 2)
        if not slots:
            continue
        per_shot.append((slots, to_sfa._slot_tracks(motion, slots, False)))
        for slot in slots:
            for c in slot:
                pk, dk = hair_pixels(c, frames, masks)
                info[id(c)] = {'c': c, 'share': len(pk) / max(len(pk) + len(dk), 1), 'n': len(pk),
                               'pk': pk, 'dk': dk}
    for d in info.values():
        d['pink'] = d['n'] > 30 and d['share'] > PINK_MIN
    for a in info.values():                                  # simultaneous pieces: one pink at most
        for b in info.values():
            if a is b or not (a['pink'] and b['pink']):
                continue
            ca, cb = a['c'], b['c']
            if ca['start'] < cb['start'] + len(cb['joints']) and cb['start'] < ca['start'] + len(ca['joints']):
                (a if a['share'] < b['share'] else b)['pink'] = False
    pk_all = [d['pk'] for d in info.values() if d['pink'] and len(d['pk'])]
    dk_all = [d['dk'] for d in info.values() if not d['pink'] and len(d['dk'])]
    med = lambda L, dflt: tuple(int(v) for v in np.median(np.concatenate(L), 0)[::-1]) if L else dflt
    pink_rgb, dark_rgb = med(pk_all, (232, 60, 85)), med(dk_all, (45, 10, 10))
    out = []
    for slots, tracks in per_shot:
        for slot, (fr, thick) in zip(slots, tracks):
            cols, raw = {}, {}
            for c in slot:
                col = pink_rgb if info[id(c)]['pink'] else dark_rgb
                for t in range(c['start'], c['start'] + len(c['joints'])):
                    cols[t] = col
                    raw[t] = c['joints'][t - c['start']]
            torsos = [np.hypot(p[2][0] - p[1][0], p[2][1] - p[1][1]) * md.W / 100 for p in fr.values()]
            out.append({'fr': fr, 'thick': thick, 'hair': cols, 'raw': raw,
                        'torso': float(np.median(torsos)) if torsos else 200.0})
    return out


HEAD_FILL = md.argb(246, 240, 234)


RATIO, _ = to_sfa._template_geometry()          # bone length / torso length of the app stickman


def lum(rgb):
    return 0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2]


def draw_stick(f2d, st, t, frame_bgr):
    """App stickman with depth cues: a translucent torso plane through both shoulders and hips, limbs
    thicker the more they are foreshortened (pointing at the camera), a white-ish head fill, and a
    contrasting outline underneath when the hair colour would vanish into the background."""
    pts, thick, rgb = st['fr'][t], st['thick'], st['hair'].get(t, (45, 10, 10))
    color = argb_of(rgb)
    px = [(x / 100 * md.W, y / 100 * md.H) for x, y in pts]
    head_top, neck = px[0], px[1]
    c = ((head_top[0] + neck[0]) / 2, (head_top[1] + neck[1]) / 2)
    r = np.hypot(head_top[0] - neck[0], head_top[1] - neck[1]) / 2
    segs = []
    for a, b in to_sfa.AO_POINTS[1:]:
        child = a if to_sfa.PARENT.get(a) == b else b
        want = RATIO[child] * st['torso']
        have = np.hypot(px[a][0] - px[b][0], px[a][1] - px[b][1])
        k = float(np.clip(want / max(have, 1.0), 1.0, 2.5)) ** 0.8 if child != 2 else 1.0
        segs.append((px[a], px[b], thick * k))
    xs = [q[0] for q in px]
    ys = [q[1] for q in px]
    x0, x1 = int(max(min(xs) / SX, 0)), int(min(max(xs) / SX + 1, AW))
    y0, y1 = int(max(min(ys) / SX, 0)), int(min(max(ys) / SX + 1, AH))
    if x1 > x0 and y1 > y0:
        bg = np.median(frame_bgr[y0:y1, x0:x1].reshape(-1, 3), 0)[::-1]
        if abs(lum(bg) - lum(rgb)) < 70:                 # would vanish: outline in the opposite tone
            oc = md.argb(235, 215, 205) if lum(rgb) < 128 else md.argb(20, 8, 8)
            f2d.layer = 'outline'
            f2d.circle(c, r, oc, thick * 2.2)
            for p0, p1, th in segs:
                f2d.line(p0, p1, oc, th * 2.2)
    j = st['raw'].get(t)
    if j is not None:                                    # torso plane: shoulders and hips as drawn
        quad = [j[k] for k in (5, 6, 12, 11)]
        if all(q[0] is not None for q in quad):
            f2d.layer = 'body'
            f2d.poly([(q[0], q[1]) for q in quad], md.argb(*rgb, 150))
    f2d.layer = 'head'                                     # white-ish head fill under the outline (user request)
    f2d.circle(c, r, md.CLEAR, 0.1, fill=HEAD_FILL)
    f2d.layer = 'fig'
    f2d.circle(c, r, color, thick)
    for p0, p1, th in segs:
        f2d.line(p0, p1, color, th)


# ----------------------------------------------------------------------------- build
def _greedy_job(args):
    img, cb, budget = args
    return greedy_shapes(img, cb, budget)


def build(mode, frames, masks, shots, sticks):
    """Per shot: palette for the candidate shapes, then error-driven shapes per frame (a held drawing,
    i.e. a frame equal to the previous one, reuses its shapes). 모작 works on the frame with the
    people painted out; 로토 on the whole frame."""
    from multiprocessing import Pool
    layers = [(f'g{r}', f'면 {r + 1}') for r in range(MAX_DEPTH)]
    if mode == 'mosaku':
        layers += [('outline', '테두리'), ('body', '몸통 면'), ('head', '머리 채우기'), ('fig', '스틱맨')]
    jobs, src_all = [], []
    for s in shots:
        span = range(s['start'], min(s['end'], len(frames)))
        if not len(span):
            continue
        src = []
        for t in span:
            img = frames[t]
            if mode == 'mosaku' and masks[t].any():          # remove the people, keep background + effects
                img = cv2.inpaint(img, cv2.dilate(masks[t], np.ones((11, 11), np.uint8)) * 255, 9, cv2.INPAINT_TELEA)
            src.append(img)
        sample = np.concatenate([b[::3, ::3].reshape(-1, 3) for b in src[::max(1, len(src) // 8)]])
        cb = palette(sample, 8)
        for t, img in zip(span, src):
            jobs.append((img, cb, BUDGET[mode]))
            src_all.append(t)
    results, prev = [None] * len(jobs), None
    todo = []
    for n, (img, cb, b) in enumerate(jobs):
        if prev is not None and np.abs(img.astype(np.int16) - jobs[prev][0]).mean() < 0.8:
            results[n] = prev                               # held drawing: reuse
        else:
            todo.append(n)
            prev = n
    with Pool() as pool:
        for n, res in zip(todo, pool.imap(_greedy_job, [jobs[n] for n in todo], chunksize=4)):
            results[n] = res
    out = []
    for n, t in enumerate(src_all):
        res = results[n]
        bg, picked = results[res] if isinstance(res, int) else res
        f2d = md.Frame2D(argb_of(bg))
        for lay, loop, rgb in picked:
            f2d.layer = f'g{lay}'
            f2d.cpoly(loop, argb_of(rgb))
        if mode == 'mosaku':
            for st in sticks:
                if t in st['fr']:
                    draw_stick(f2d, st, t, frames[t])
        out.append(f2d)
    return out, layers


def write(frames2d, layers, name, path):
    root = ET.Element('Sequence', {'Name': name, 'HeightWidthRatio': '0.5625', 'RatioX': '16', 'RatioY': '9',
                                   'FrameCount': str(len(frames2d)), 'BackgroundColor': '-1'})
    ids = md.IdPlan()
    for fr in frames2d:                                     # dry run: pool sizes
        used = {}
        for layer, kind, pts, *_ in fr.items:
            if kind == 'cpoly':
                pool = (layer, 'cpoly', len(pts) // 2)
            elif kind == 'poly':
                n_ = min(len(md.clip_poly(pts)), 40)
                if n_ < 3:
                    continue
                pool = (layer, 'poly', n_)
            else:
                pool = (layer, kind)
            used[pool] = used.get(pool, 0) + 1
            ids.need[pool] = max(ids.need.get(pool, 0), used[pool])
    ids.plan([k for k, _ in layers])
    for n, fr in enumerate(frames2d):
        fr.write(root, n, ids, layers, prec=1)
    errs = sfa.validate(root)
    assert not errs, errs[:3]
    sfa.write_sfa(root, path)
    return root


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('data_dir')
    ap.add_argument('clip')
    ap.add_argument('out_dir')
    ap.add_argument('--mode', default='both', choices=['both', 'mosaku', 'roto'])
    ap.add_argument('--preview', action='store_true')
    a = ap.parse_args(argv)
    media = Path(a.data_dir, 'media')
    clip = media / f'{a.clip}.mp4'
    frames = read_frames(clip)
    motion = json.loads((media / f'{a.clip}.motion.json').read_text(encoding='utf-8'))
    masks = person_masks(clip, frames, media / f'{a.clip}.masks.npz') | pose_masks(motion, len(frames))
    shots = json.loads((media / f'{a.clip}.shots.json').read_text(encoding='utf-8'))['shots']
    if shots and shots[-1]['end'] < len(frames):
        shots[-1]['end'] = len(frames)
    Path(a.out_dir).mkdir(parents=True, exist_ok=True)
    for mode in (['mosaku', 'roto'] if a.mode == 'both' else [a.mode]):
        sticks = stick_tracks(motion, frames, masks) if mode == 'mosaku' else []
        f2ds, layers = build(mode, frames, masks, shots, sticks)
        out = Path(a.out_dir, f'{a.clip}_{mode}.sfa')
        root = write(f2ds, layers, f'{a.clip}_{mode}', out)
        xml_mb = len(ET.tostring(root)) / 2 ** 20
        print(f'{mode}: {len(f2ds)}프레임, XML {xml_mb:.1f} MB, SFA {out.stat().st_size / 2**20:.1f} MB, '
              f'AO 최대 {max(len(f.findall("AO")) for f in root.findall("Frame"))}개/프레임, 레이어 {len(layers)} → {out}')
        if a.preview:
            md.preview(root, out.with_suffix('.mp4'))


if __name__ == '__main__':
    main()
