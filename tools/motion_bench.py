#!/usr/bin/env python3
"""Synthetic ground-truth benchmark for pose clean-up + stickman SFA conversion.

A known world-space motion is filmed by a known camera and turned into detector-like output
(clamping at the frame edge, per-drawing jitter, dropped frames, track ID changes, occlusion).
It then goes through pipeline.motion and pipeline.to_sfa exactly like real clips, and the
stickman points are compared with the truth (head excluded: its size is a stickman rule).

Scenarios: zoom_reveal (close-up -> wide, legs off-screen first), jitter, track_break, occlusion.
Usage:  .venv\\Scripts\\python tools\\motion_bench.py [--old MOTION_PY TO_SFA_PY]
"""
import argparse
import importlib.util
import math
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from pipeline import motion as new_motion, to_sfa as new_to_sfa  # noqa: E402

W, H, T = 1920, 1080, 72
GT_POINTS = (1, 2, 3, 4, 5, 6, 7, 8, 9, 10)            # stickman points compared (not the head top)


def world_pose(t):
    """COCO 17 joints of a fighter in world px (drawn on 2s: call with the drawing time)."""
    hip = np.array([960 + 40 * math.sin(t / 9), 640.0])
    neck = hip + [8 * math.sin(t / 7), -170]
    j = np.zeros((17, 2))
    j[5], j[6] = neck + [-40, 0], neck + [40, 0]
    j[11], j[12] = hip + [-28, 0], hip + [28, 0]
    for sh, el, wr, ph in ((5, 7, 9, 0.0), (6, 8, 10, 1.7)):
        a1, a2 = 1.2 + 0.9 * math.sin(t / 6 + ph), 0.6 + 1.1 * math.sin(t / 4 + ph)
        j[el] = j[sh] + 110 * np.array([math.cos(a1) * (1 if sh == 6 else -1), math.sin(a1)])
        j[wr] = j[el] + 100 * np.array([math.cos(a1 - a2) * (1 if sh == 6 else -1), math.sin(a1 - a2)])
    for hp, kn, an, ph in ((11, 13, 15, 0.0), (12, 14, 16, math.pi)):
        a = math.pi / 2 + 0.35 * math.sin(t / 8 + ph)
        j[kn] = j[hp] + 120 * np.array([math.cos(a), math.sin(a)])
        j[an] = j[kn] + 120 * np.array([math.cos(a - 0.3 * math.sin(t / 8 + ph)), math.sin(a)])
    j[0] = neck + [0, -70]
    j[1], j[2], j[3], j[4] = neck + [-12, -80], neck + [12, -80], neck + [-25, -75], neck + [25, -75]
    return j


def cameras(kind):
    cams = []
    for t in range(T):
        if kind == 'zoom_reveal':
            s = 2.6 if t < 12 else 1.0 if t >= 60 else 2.6 - 1.6 * (t - 12) / 48
            focus = np.array([960.0, 520.0])
            off = np.array([960.0, 540.0]) - s * focus
        elif kind == 'occlusion':
            s, off = 1.0, np.array([-6.0 * t + 200, 0.0])
        else:
            s, off = 1.0, np.zeros(2)
        cams.append(np.array([[s, 0, off[0]], [0, s, off[1]]]))
    return cams


def detections(kind, seed=0):
    rng = np.random.default_rng(seed)
    cams = cameras(kind)
    truth, rows = [], {'frame': [], 'shot': [], 'track': [], 'box': [], 'kpts': []}
    noise = {}
    for t in range(T):
        w = world_pose(t // 2 * 2)                           # on 2s
        scr = w @ cams[t][:, :2].T + cams[t][:, 2]
        truth.append(scr)
        if kind == 'track_break' and 30 <= t <= 32:
            continue
        d = t // 2
        if d not in noise:
            noise[d] = rng.normal(0, 0.012 * 540, (17, 2)) if kind == 'jitter' else np.zeros((17, 2))
        k = np.zeros((17, 3))
        k[:, :2] = np.clip(scr + noise[d] * cams[t][0, 0], [0, 0], [W - 1, H - 1])   # detector clamps
        k[:, 2] = 0.9
        if kind == 'occlusion' and 20 <= t < 35:
            k[[8, 10], 2] = 0.05                             # right arm hidden
        vis = k[k[:, 2] > 0.3, :2]
        rows['frame'].append(t)
        rows['shot'].append(0)
        rows['track'].append(2 if kind == 'track_break' and t > 32 else 1)
        rows['box'].append([*vis.min(0), *vis.max(0)])
        rows['kpts'].append(k)
    data = {k: np.array(v) for k, v in rows.items()}
    return data, cams, np.array(truth)


def run_new(data, cams):
    chars = []
    for shot, rows in new_motion.stitch_tracks(data):
        start, k, boxes = new_motion.chain_arrays(data, rows)
        k, runs, unsure, off = new_motion.clean_track(k, boxes, (W, H), cams[start:start + len(k)])
        chars.append({'shot': shot, 'track': 1, 'start': start, 'runs': runs, 'uncertain': unsure, 'offscreen': off,
                      'camera': [list(np.asarray(c).ravel()) for c in cams[start:start + len(k)]],
                      'joints': [[[None, None, 0.0] if np.isnan(x) else [x, y, c] for x, y, c in f] for f in k]})
    return new_to_sfa.build({'clip': 'bench', 'fps': 24, 'size': [W, H], 'characters': chars}, max_chars=1)[0]


def run_old(mod_motion, mod_to_sfa, data):
    chars = []
    for track, rows in mod_motion.track_segments(data):
        rows = rows[np.argsort(data['frame'][rows])]
        out = mod_motion.clean_track(data['kpts'][rows], data['box'][rows], (W, H))
        k, runs, unsure = out[:3]
        c = {'shot': 0, 'track': track, 'start': int(data['frame'][rows[0]]), 'runs': runs, 'uncertain': unsure,
             'joints': [[[None, None, 0.0] if np.isnan(x) else [x, y, q] for x, y, q in f] for f in k]}
        if len(out) > 3:
            c['offscreen'] = out[3]
        chars.append(c)
    return mod_to_sfa.build({'clip': 'bench', 'fps': 24, 'size': [W, H], 'characters': chars}, max_chars=1)[0]


def sfa_points(root):
    """Per SFA frame: 11 stickman points in canvas %, or None when the character is absent."""
    out = []
    for f in root.findall('Frame'):
        aos = [a for a in f.findall('AO') if int(a.get('ID')) <= 10]
        if len(aos) < 10:
            out.append(None)
            continue
        pts = [None] * 11
        for ao, (a, b) in zip(aos, new_to_sfa.AO_POINTS):
            ap = ao.findall('AP')
            pts[a] = (float(ap[0].get('X')), float(ap[0].get('Y')))
            pts[b] = (float(ap[1].get('X')), float(ap[1].get('Y')))
        out.append(pts)
    return out


def truth_points(truth):
    to_pct = new_to_sfa.fit((W, H))
    return [[to_pct(p) for p in new_to_sfa.skeleton([[x, y, 1.0] for x, y in f])] for f in truth]


def metrics(kind, root, truth):
    got, want = sfa_points(root), truth_points(truth)
    pct = np.array([1920 / 100, 1080 / 100])                 # canvas % -> px
    body = [np.ptp(f[:, 1]) for f in truth]
    pick = {'zoom_reveal': (7, 8, 9, 10), 'occlusion': (3, 4)}.get(kind, GT_POINTS)
    frames = range(T)
    if kind == 'zoom_reveal':
        frames = [t for t in range(T) if truth[t][15:17, 1].max() > H]           # feet off-screen
    if kind == 'occlusion':
        frames = range(20, 35)
    errs, missing = [], 0
    offset = T - len(got)
    for t in frames:
        g = got[t - offset] if 0 <= t - offset < len(got) else None
        if g is None:
            missing += 1
            continue
        e = [np.hypot(*((np.array(g[i]) - np.array(want[t][i])) * pct)) for i in pick]
        errs.append(np.mean(e) / body[t] * 100)
    res = {'error_%body': round(float(np.mean(errs)), 2) if errs else None, 'missing_frames': missing}
    if kind == 'jitter':
        series = np.array([[g[i] for i in GT_POINTS] for g in got if g is not None]) * pct
        truth_s = np.array([[want[t][i] for i in GT_POINTS] for t in range(T)]) * pct
        jit = lambda s: float(np.mean(np.abs(np.diff(s[::2], 2, axis=0))))   # per drawing
        res['jitter_ratio'] = round(jit(series) / jit(truth_s), 2)
    return res


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def bench(old=None):
    rows = []
    for kind in ('zoom_reveal', 'jitter', 'track_break', 'occlusion'):
        data, cams, truth = detections(kind)
        row = {'scenario': kind, 'new': metrics(kind, run_new(data, cams), truth)}
        if old:
            row['old'] = metrics(kind, run_old(*old, data), truth)
        rows.append(row)
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--old', nargs=2, metavar=('MOTION_PY', 'TO_SFA_PY'))
    a = ap.parse_args()
    old = None
    if a.old:
        sys.modules['pipeline.motion_old'] = m = load(a.old[0], 'pipeline.motion_old')
        old_sfa = load(a.old[1], 'pipeline.to_sfa_old')
        old_sfa.TEMPLATE = new_to_sfa.TEMPLATE
        old = (m, old_sfa)
    for row in bench(old):
        print(row)


if __name__ == '__main__':
    main()
