#!/usr/bin/env python3
"""Pose tracks -> common representation (characters part), with temporal clean-up.

Reads <id>.pose.npz (+ <id>.shots.json) and writes <id>.motion.json:
  {"clip", "fps", "size": [w, h], "characters": [
     {"shot", "track", "start": first video frame, "joints": [[[x, y, conf] x17] per frame],
      "runs": drawing hold runs, "uncertain": frame offsets with implausible bone lengths,
      "offscreen": per-frame bitmask of COCO joints that left the picture (bit j = joint j)}]}
Clean-up, in order (no smoothing: smears and impact frames are intentional deformations):
  1. joints below MIN_CONF are missing; joints pinned to the frame border are off-screen
     (the detector clamps them to the edge) and are missing too, flagged in "offscreen";
  2. left/right swap when the mirrored pose matches the previous frame much better;
  3. gaps up to MAX_GAP frames are linearly filled (conf marked 0.01 = interpolated);
  4. frames inside a hold run are snapped to the run's first frame (exact holds, no jitter);
  5. bones longer than BONE_MAX x their median are flagged uncertain, not "fixed".
COCO order: 0 nose, 1-2 eyes, 3-4 ears, 5-6 shoulders, 7-8 elbows, 9-10 wrists, 11-12 hips,
13-14 knees, 15-16 ankles (odd = left, even = right).

Usage (repository root):  .venv\\Scripts\\python -m pipeline.motion data_sakuga
"""
import argparse
import json
from pathlib import Path

import numpy as np

from pipeline.pose import pose_runs, track_segments

MIN_CONF = 0.3
MAX_GAP = 4
SWAP_GAIN = 0.6      # swap when the mirrored error is below 60% of the direct error
BONE_MAX = 1.6
EDGE_FRAC = 0.01     # joints within 1% of the border are clamped, i.e. off-screen
MIRROR = [0, 2, 1, 4, 3, 6, 5, 8, 7, 10, 9, 12, 11, 14, 13, 16, 15]
BONES = [(5, 7), (7, 9), (6, 8), (8, 10), (11, 13), (13, 15), (12, 14), (14, 16), (5, 11), (6, 12)]


def fix_swaps(k):
    """k (T,17,3) with NaN for missing; mirror frames whose L/R labels flipped."""
    k = k.copy()
    for t in range(1, len(k)):
        prev, cur, mir = k[t - 1, :, :2], k[t, :, :2], k[t, MIRROR, :2]
        both = ~np.isnan(prev[:, 0]) & ~np.isnan(cur[:, 0]) & ~np.isnan(mir[:, 0])
        if both.sum() < 4:
            continue
        direct = np.linalg.norm(cur[both] - prev[both], axis=1).mean()
        mirrored = np.linalg.norm(mir[both] - prev[both], axis=1).mean()
        if mirrored < SWAP_GAIN * direct:
            k[t] = k[t, MIRROR]
    return k


def fill_gaps(k):
    k = k.copy()
    for j in range(k.shape[1]):
        miss = np.isnan(k[:, j, 0])
        t = 0
        while t < len(k):
            if not miss[t]:
                t += 1
                continue
            e = t
            while e < len(k) and miss[e]:
                e += 1
            if 0 < t and e < len(k) and e - t <= MAX_GAP:
                for i in range(t, e):
                    a = (i - t + 1) / (e - t + 1)
                    k[i, j, :2] = (1 - a) * k[t - 1, j, :2] + a * k[e, j, :2]
                    k[i, j, 2] = 0.01
            t = e
    return k


def snap_holds(k, runs):
    k = k.copy()
    t = 0
    for n in runs:
        k[t:t + n] = k[t]
        t += n
    return k


def uncertain_frames(k):
    lengths = np.stack([np.linalg.norm(k[:, a, :2] - k[:, b, :2], axis=1) for a, b in BONES], 1)
    med = np.nanmedian(lengths, axis=0)
    with np.errstate(invalid='ignore'):
        bad = np.any(lengths > BONE_MAX * med, axis=1)
    return [int(t) for t in np.flatnonzero(bad)]


def edge_mask(kpts, size):
    """Joints pinned to the frame border. The detector never reports a joint outside the frame:
    a leg leaving the picture is clamped to the edge with a confident score, so treat it as off-screen."""
    w, h = size
    mx, my = EDGE_FRAC * w, EDGE_FRAC * h
    x, y = kpts[..., 0], kpts[..., 1]
    return (kpts[..., 2] >= MIN_CONF) & ((x <= mx) | (x >= w - 1 - mx) | (y <= my) | (y >= h - 1 - my))


def clean_track(kpts, boxes, size=None):
    k = kpts.astype(np.float64).copy()
    off = edge_mask(k, size) if size else np.zeros(k.shape[:2], bool)
    k[(k[..., 2] < MIN_CONF) | off, :2] = np.nan
    k = fill_gaps(fix_swaps(k))
    k[off, :2] = np.nan                            # never interpolate through the off-screen stretch
    runs = pose_runs(np.nan_to_num(k, nan=0.0), boxes)
    k = snap_holds(k, runs)
    off = snap_holds(off[..., None], runs)[..., 0]
    bits = [int(sum(1 << j for j in np.flatnonzero(f))) for f in off]
    return k, runs, uncertain_frames(k), bits


def clip_motion(npz_path, shots_path):
    data = dict(np.load(npz_path))
    meta = json.loads(Path(shots_path).read_text(encoding='utf-8'))
    size = meta.get('size', [1920, 1080])
    chars = []
    for track, rows in track_segments(data):
        k, runs, unsure, off = clean_track(data['kpts'][rows], data['box'][rows], size)
        joints = [[[None, None, 0.0] if np.isnan(x) else [round(float(x), 1), round(float(y), 1), round(float(c), 2)]
                   for x, y, c in frame] for frame in k]
        chars.append({'shot': int(data['shot'][rows[0]]), 'track': track, 'start': int(data['frame'][rows[0]]),
                      'joints': joints, 'runs': runs, 'uncertain': unsure, 'offscreen': off})
    return {'clip': Path(npz_path).name.split('.')[0], 'fps': meta.get('fps', 24.0),
            'size': size, 'characters': chars}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('data_dir')
    a = ap.parse_args(argv)
    media = Path(a.data_dir, 'media')
    done = tracks = frames = unsure = 0
    for npz in sorted(media.glob('*.pose.npz')):
        out = npz.with_name(npz.name.replace('.pose.npz', '.motion.json'))
        if out.exists():
            continue
        m = clip_motion(npz, npz.with_name(npz.name.replace('.pose.npz', '.shots.json')))
        tmp = out.with_suffix('.tmp')
        tmp.write_text(json.dumps(m, separators=(',', ':')), encoding='utf-8')
        tmp.replace(out)
        done += 1
        tracks += len(m['characters'])
        frames += sum(len(c['joints']) for c in m['characters'])
        unsure += sum(len(c['uncertain']) for c in m['characters'])
    print(f'새로 변환 {done}개: 트랙 {tracks}, 프레임 {frames}, 뼈 길이 의심 프레임 {unsure}')


if __name__ == '__main__':
    main()
