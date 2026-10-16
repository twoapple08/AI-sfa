#!/usr/bin/env python3
"""Pose tracks -> common representation (characters part), with temporal clean-up.

Reads <id>.pose.npz (+ <id>.shots.json, + the clip for the camera) and writes <id>.motion.json:
  {"clip", "fps", "size": [w, h], "characters": [
     {"shot", "track", "start": first video frame, "joints": [[[x, y, conf] x17] per frame],
      "runs": drawing hold runs, "uncertain": frame offsets with implausible bone lengths,
      "offscreen": per-frame bitmask of COCO joints that left the picture (bit j = joint j),
      "camera": per-frame [a, b, tx, c, d, ty] world -> screen (pipeline.camera)}]}
Joints are screen pixels (camera applied); filled joints may lie outside the frame.
Clean-up, in order (no smoothing that would erase smears or impact frames):
  1. tracks that vanish for a few frames, or come back under a new ID where they left, are
     stitched into one person (otherwise the stickman blinks out);
  2. joints below MIN_CONF are missing; joints pinned to the frame border are off-screen
     (the detector clamps them to the edge) and are missing too, flagged in "offscreen";
  3. everything moves to world coordinates (camera zoom/pan removed);
  4. left/right swap when the mirrored pose matches the previous frame much better;
  5. gaps up to MAX_GAP frames are linearly filled (conf 0.01 = interpolated);
  6. frames inside a hold run are snapped to the run's first frame (exact holds);
  7. a joint still missing takes its offset from its parent from frames where both were seen:
     blended between the last frame before and the first after, or copied from the nearest
     one when only one side exists (a close-up's hidden legs come from the wide frames after
     a zoom-out) (conf 0.02 = borrowed);
  8. one adaptive (One-Euro) filter per joint over the drawings, not the frames: detector
     jitter on slow motion is removed, fast strikes and smears pass almost unchanged;
  9. bones longer than BONE_MAX x their median are flagged uncertain, not "fixed".
COCO order: 0 nose, 1-2 eyes, 3-4 ears, 5-6 shoulders, 7-8 elbows, 9-10 wrists, 11-12 hips,
13-14 knees, 15-16 ankles (odd = left, even = right).

Usage (repository root):  .venv\\Scripts\\python -m pipeline.motion data_sakuga
"""
import argparse
import json
import math
from pathlib import Path

import numpy as np

from pipeline import camera
from pipeline.pose import pose_runs

MIN_CONF = 0.3
MAX_GAP = 8
SWAP_GAIN = 0.6      # swap when the mirrored error is below 60% of the direct error
BONE_MAX = 1.6
EDGE_FRAC = 0.01     # joints within 1% of the border (per axis) are clamped, i.e. off-screen
STITCH_GAP = 8       # frames a person may vanish and still be the same person
STITCH_DIST = 0.6    # ... if they reappear within 0.6 box sizes of where they left
MIN_LEN = 8
EURO_MINCUT = 0.05   # One-Euro on joints / torso length, one sample per drawing (tools/motion_bench.py)
EURO_BETA = 2.0
MIRROR = [0, 2, 1, 4, 3, 6, 5, 8, 7, 10, 9, 12, 11, 14, 13, 16, 15]
BONES = [(5, 7), (7, 9), (6, 8), (8, 10), (11, 13), (13, 15), (12, 14), (14, 16), (5, 11), (6, 12)]
# (joint, parent) in fill order; the shoulders lean on each other, the face on the nose.
TREE = [(5, 6), (6, 5), (11, 5), (12, 6), (11, 12), (12, 11), (7, 5), (8, 6), (9, 7), (10, 8),
        (13, 11), (14, 12), (15, 13), (16, 14), (0, 5), (1, 0), (2, 0), (3, 0), (4, 0)]


def stitch_tracks(data):
    """[(shot, {frame: row})] per person and shot."""
    chains = []
    for shot in np.unique(data['shot']):
        sel = np.flatnonzero(data['shot'] == shot)
        segs = []
        for tr in np.unique(data['track'][sel]):
            if tr < 0:
                continue
            rows = sel[data['track'][sel] == tr]
            segs.append({int(data['frame'][r]): int(r) for r in rows})
        segs.sort(key=min)
        people = []
        for seg in segs:
            s0, best = min(seg), None
            for person in people:
                last = max(person)
                if last < s0 and s0 - last <= STITCH_GAP + 1:
                    b0, b1 = data['box'][person[last]], data['box'][seg[s0]]
                    size = max(b0[2] - b0[0], b0[3] - b0[1], 1.0)
                    d = math.hypot((b1[0] + b1[2] - b0[0] - b0[2]) / 2, (b1[1] + b1[3] - b0[1] - b0[3]) / 2) / size
                    if d <= STITCH_DIST and (best is None or d < best[0]):
                        best = (d, person)
            if best:
                best[1].update(seg)
            else:
                people.append(dict(seg))
        chains += [(int(shot), p) for p in people if len(p) >= MIN_LEN]
    return chains


def chain_arrays(data, rows_by_frame):
    """Frames start..end of one person; frames without a detection are NaN (boxes held)."""
    start, end = min(rows_by_frame), max(rows_by_frame) + 1
    k = np.full((end - start, 17, 3), np.nan)
    k[..., 2] = 0.0
    boxes = np.zeros((end - start, 4))
    last = data['box'][rows_by_frame[start]]
    for t in range(end - start):
        r = rows_by_frame.get(start + t)
        if r is not None:
            k[t] = data['kpts'][r]
            last = data['box'][r]
        boxes[t] = last
    return start, k, boxes


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


def borrow_limbs(k):
    """Fill a missing joint from its parent with the offset seen at the nearest frame (either way)."""
    k = k.copy()
    for j, p in TREE:
        known = ~np.isnan(k[:, j, 0])
        src = np.flatnonzero(known & ~np.isnan(k[:, p, 0]) & (k[:, j, 2] > 0.02))
        if not len(src):
            continue
        rel = k[src, j, :2] - k[src, p, :2]
        for t in np.flatnonzero(~known & ~np.isnan(k[:, p, 0])):
            i = np.searchsorted(src, t)
            if 0 < i < len(src):                       # seen before and after: blend the limb shape
                a = (t - src[i - 1]) / (src[i] - src[i - 1])
                off = (1 - a) * rel[i - 1] + a * rel[i]
            else:                                      # only on one side (close-up then zoom-out)
                off = rel[min(i, len(src) - 1)]
            k[t, j, :2] = k[t, p, :2] + off
            k[t, j, 2] = 0.02
    return k


def one_euro(xs, mincut=None, beta=None, dcut=1.0):
    """Adaptive low-pass along axis 0 (one sample per drawing); NaN restarts the filter."""
    mincut = EURO_MINCUT if mincut is None else mincut
    beta = EURO_BETA if beta is None else beta
    def alpha(cut):
        return 1.0 / (1.0 + 1.0 / (2 * math.pi * cut))
    out = xs.copy()
    dx = np.zeros(xs.shape[1:])
    for i in range(1, len(xs)):
        prev, x = out[i - 1], xs[i]
        ok = ~np.isnan(x) & ~np.isnan(prev)
        d = np.where(ok, x - prev, 0.0)
        dx = np.where(ok, alpha(dcut) * d + (1 - alpha(dcut)) * dx, 0.0)
        a = alpha(mincut + beta * np.abs(dx))
        out[i] = np.where(ok, a * x + (1 - a) * prev, x)
    return out


def smooth(k, runs):
    torso = np.nanmedian(np.linalg.norm(k[:, 5, :2] - k[:, 11, :2], axis=1)) if len(k) else np.nan
    if not np.isfinite(torso) or torso <= 0:
        return k
    starts = np.cumsum([0] + runs[:-1])
    x = k[starts, :, :2] / torso
    keys = (one_euro(x) + one_euro(x[::-1])[::-1]) / 2 * torso     # both directions: no lag
    k = k.copy()
    for s, n, key in zip(starts, runs, keys):
        k[s:s + n, :, :2] = key
    return k


def uncertain_frames(k):
    lengths = np.stack([np.linalg.norm(k[:, a, :2] - k[:, b, :2], axis=1) for a, b in BONES], 1)
    if np.all(np.isnan(lengths)):
        return []
    with np.errstate(invalid='ignore'), np.testing.suppress_warnings() as sup:
        sup.filter(RuntimeWarning)
        med = np.nanmedian(lengths, axis=0)
        bad = np.any(lengths > BONE_MAX * med, axis=1)
    return [int(t) for t in np.flatnonzero(bad)]


def edge_mask(kpts, size):
    """Joints pinned to the frame border. The detector never reports a joint outside the frame:
    a leg leaving the picture is clamped to the edge with a confident score, so treat it as off-screen."""
    w, h = size
    mx, my = EDGE_FRAC * w, EDGE_FRAC * h
    x, y = kpts[..., 0], kpts[..., 1]
    return (kpts[..., 2] >= MIN_CONF) & ((x <= mx) | (x >= w - 1 - mx) | (y <= my) | (y >= h - 1 - my))


def _apply(cams, k, fn):
    out = k.copy()
    for t, c in enumerate(cams):
        ok = ~np.isnan(k[t, :, 0])
        if ok.any():
            out[t, ok, :2] = fn(c, k[t, ok, :2])
    return out


def clean_track(kpts, boxes, size=None, cams=None):
    """Returns screen joints (T,17,3), hold runs, uncertain frames, off-screen bitmasks."""
    k = np.asarray(kpts, np.float64).copy()
    off = edge_mask(np.nan_to_num(k), size) if size else np.zeros(k.shape[:2], bool)
    k[(np.nan_to_num(k[..., 2]) < MIN_CONF) | off, :2] = np.nan
    boxes = np.asarray(boxes, np.float64)
    if cams is not None:
        k = _apply(cams, k, camera.to_world)
        boxes = boxes / np.array([camera.scale_of(c) for c in cams])[:, None]
    k = fill_gaps(fix_swaps(k))
    k[off, :2] = np.nan                            # never interpolate through the off-screen stretch
    probe = k.copy()
    probe[np.isnan(probe[..., 0]), 2] = 0.0        # missing joints must not count as motion
    runs = pose_runs(np.nan_to_num(probe, nan=0.0), boxes)
    k = snap_holds(k, runs)
    off = snap_holds(off[..., None], runs)[..., 0]
    k = smooth(borrow_limbs(k), runs)
    unsure = uncertain_frames(k)
    if cams is not None:
        k = _apply(cams, k, camera.to_screen)
    bits = [int(sum(1 << j for j in np.flatnonzero(f))) for f in off]
    return k, runs, unsure, bits


def shot_cameras(clip, shot_list, data, size):
    """Camera per frame for every shot that has people, from the clip itself."""
    from pipeline import shots as shots_mod
    _, _, frames = shots_mod.read_frames(clip, width=camera.WIDTH)
    boxes = {}
    for f, b in zip(data['frame'], data['box']):
        boxes.setdefault(int(f), []).append(b)
    cams = {}
    for i in np.unique(data['shot']):
        s = shot_list[int(i)]
        span = range(s['start'], min(s['end'], len(frames)))
        if len(span):
            cams[int(i)] = camera.estimate([frames[t] for t in span], [boxes.get(t, []) for t in span], size[0])
    return cams


def clip_motion(npz_path, shots_path, clip_path=None):
    data = dict(np.load(npz_path))
    meta = json.loads(Path(shots_path).read_text(encoding='utf-8'))
    size = meta.get('size', [1920, 1080])
    cams = shot_cameras(clip_path, meta['shots'], data, size) if clip_path and Path(clip_path).exists() else {}
    chars = []
    for shot, rows in stitch_tracks(data):
        start, k, boxes = chain_arrays(data, rows)
        c = None
        if shot in cams:
            s0 = meta['shots'][shot]['start']
            c = cams[shot][start - s0:start - s0 + len(k)]
            c = c if len(c) == len(k) else None
        k, runs, unsure, off = clean_track(k, boxes, size, c)
        joints = [[[None, None, 0.0] if np.isnan(x) else [round(float(x), 1), round(float(y), 1), round(float(q), 2)]
                   for x, y, q in frame] for frame in k]
        track = int(data['track'][rows[start]])
        entry = {'shot': shot, 'track': track, 'start': start, 'joints': joints, 'runs': runs,
                 'uncertain': unsure, 'offscreen': off}
        if c is not None:
            entry['camera'] = [[round(float(v), 4) for v in np.asarray(m).ravel()] for m in c]
        chars.append(entry)
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
        stem = npz.name.replace('.pose.npz', '')
        m = clip_motion(npz, media / f'{stem}.shots.json', media / f'{stem}.mp4')
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
