#!/usr/bin/env python3
"""Stage 2 pre-pass: split clips into shots and measure holds and camera-only motion.

For every downloaded clip (DATA_DIR/media/<id>.mp4) this writes <id>.shots.json with, per shot:
  - frame range and the drawing runs: a "hold" is a frame that repeats the previous frame,
    so run lengths give the timing (on 1s/2s/3s) instead of being treated as errors. This is
    whole-frame timing: a pan or effect on 1s over a character on 2s reads as on 1s. Real
    drawing timing comes from pose tracks later; change_pct keeps the raw per-frame signal;
  - flashes: 1-2 frame impact/flash frames between matching frames (events, not cuts);
  - kind: 'still' (one drawing), 'camera_only' (drawing changes explained by one global
    similarity transform = pan/zoom/shake over a single picture) or 'animated';
  - lineart_like: low saturation on a bright page (genga/key drawings; excluded from colour learning).
Resumable: clips with an existing .shots.json are skipped. Needs numpy + opencv (.venv).

Usage (repository root):  .venv\\Scripts\\python -m pipeline.shots data_sakuga [--max 50]
"""
import argparse
import json
from collections import Counter
from pathlib import Path

import cv2
import numpy as np

WIDTH = 320          # analysis width; timing and global motion survive this downscale
HOLD_PIX = 20        # |gray diff| above which a pixel counts as redrawn (codec noise stays below)
HOLD_FRAC = 0.0003   # a frame repeats the previous drawing if fewer pixels than this fraction changed
CUT_DIFF = 20.0      # a cut is a large pixel change with a colour-histogram change ...
CUT_CORR = 0.6
CUT_CORR_STRONG = 0.3    # ... or a near-total colour change even when mean brightness is similar
CUT_DIFF_MIN = 8.0
MAX_FRAMES = 6000


def read_frames(path, width=WIDTH, max_frames=MAX_FRAMES):
    cap = cv2.VideoCapture(str(path))
    fps = cap.get(cv2.CAP_PROP_FPS) or 24.0
    size = [int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))]
    frames = []
    while len(frames) < max_frames:
        ok, frame = cap.read()
        if not ok:
            break
        h, w = frame.shape[:2]
        frames.append(cv2.resize(frame, (width, max(1, round(h * width / w))), interpolation=cv2.INTER_AREA))
    cap.release()
    return fps, size, frames


def _hist(frame):
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    h = cv2.calcHist([hsv], [0, 1], None, [16, 8], [0, 180, 0, 256])
    return cv2.normalize(h, h)


def frame_diffs(grays):
    """Per frame: (mean |diff|, fraction of redrawn pixels) against the previous frame."""
    out = [(0.0, 0.0)]
    for a, b in zip(grays, grays[1:]):
        d = cv2.absdiff(a, b)
        out.append((float(np.mean(d)), float(np.count_nonzero(d > HOLD_PIX)) / d.size))
    return out


FLASH_MAX = 2        # a segment this short whose neighbours match is a flash/impact frame, not a shot
FLASH_SAME = 0.8


def find_cuts(frames, diffs):
    """Shot start indices and flash events [(start, end)] that were folded into their shot."""
    hists = [_hist(f) for f in frames]
    cuts = [0]
    for i in range(1, len(frames)):
        corr = cv2.compareHist(hists[i - 1], hists[i], cv2.HISTCMP_CORREL)
        mean = diffs[i][0]
        if (mean > CUT_DIFF and corr < CUT_CORR) or (mean > CUT_DIFF_MIN and corr < CUT_CORR_STRONG):
            cuts.append(i)
    kept, flashes, i = [0], [], 1
    while i < len(cuts):
        s = cuts[i]
        e = cuts[i + 1] if i + 1 < len(cuts) else len(frames)
        if e - s <= FLASH_MAX and e < len(frames) and \
                cv2.compareHist(hists[s - 1], hists[e], cv2.HISTCMP_CORREL) > FLASH_SAME:
            flashes.append((s, e))
            i += 2                                  # drop both the cut into and out of the flash
            continue
        kept.append(s)
        i += 1
    return kept, flashes


def camera_explained(ga, gb):
    """True if gb is ga moved by one non-trivial similarity transform, False if not, None if unknown."""
    orb = cv2.ORB_create(600)
    ka, da = orb.detectAndCompute(ga, None)
    kb, db = orb.detectAndCompute(gb, None)
    if da is None or db is None or len(ka) < 12 or len(kb) < 12:
        return None
    matches = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True).match(da, db)
    if len(matches) < 12:
        return None
    src = np.float32([ka[m.queryIdx].pt for m in matches])
    dst = np.float32([kb[m.trainIdx].pt for m in matches])
    m, _ = cv2.estimateAffinePartial2D(src, dst, method=cv2.RANSAC, ransacReprojThreshold=2.0)
    if m is None:
        return None
    scale = float(np.hypot(m[0, 0], m[1, 0]))
    if abs(m[0, 2]) < 0.5 and abs(m[1, 2]) < 0.5 and abs(scale - 1) < 0.005 and abs(m[1, 0]) < 0.005:
        return None                                     # identity: a small drawing change, not a camera move
    h, w = ga.shape
    warped = cv2.warpAffine(ga, m, (w, h), borderMode=cv2.BORDER_REPLICATE)
    c = 8
    resid = float(np.mean(cv2.absdiff(warped[c:-c, c:-c], gb[c:-c, c:-c])))
    raw = float(np.mean(cv2.absdiff(ga[c:-c, c:-c], gb[c:-c, c:-c])))
    return resid <= max(2.0, 0.3 * raw)


def analyse_shot(frames, grays, diffs, start, end):
    runs, changes = [], []
    for i in range(start, end):
        if i == start or diffs[i][1] >= HOLD_FRAC:
            runs.append(1)
            if i > start:
                changes.append(i)
        else:
            runs[-1] += 1
    explained = [camera_explained(grays[i - 1], grays[i]) for i in changes]
    known = [e for e in explained if e is not None]
    camera_moves = {i for i, e in zip(changes, explained) if e}
    drawing_runs = []                               # timing of drawings: camera-only changes do not start one
    for i in range(start, end):
        if i == start or (diffs[i][1] >= HOLD_FRAC and i not in camera_moves):
            drawing_runs.append(1)
        else:
            drawing_runs[-1] += 1
    camera_ratio = round(sum(known) / len(known), 3) if known else 0.0
    if len(runs) == 1:
        kind = 'still'
    elif len(known) >= max(1, len(changes) // 2) and camera_ratio >= 0.8:
        kind = 'camera_only'
    else:
        kind = 'animated'
    hsv = cv2.cvtColor(np.concatenate(frames[start:end:max(1, (end - start) // 8)]), cv2.COLOR_BGR2HSV)
    sat, val = float(hsv[..., 1].mean()), float(hsv[..., 2].mean())
    hist = Counter(runs)
    return {'start': start, 'end': end, 'frames': end - start, 'drawings': len(runs),
            'hold_mode': hist.most_common(1)[0][0], 'hold_hist': dict(sorted(hist.items())),
            'drawing_hold_mode': Counter(drawing_runs).most_common(1)[0][0],
            'kind': kind, 'camera_ratio': camera_ratio,
            'lineart_like': sat < 25 and val > 170}


def analyse_frames(frames, fps):
    grays = [cv2.cvtColor(f, cv2.COLOR_BGR2GRAY) for f in frames]
    diffs = frame_diffs(grays)
    cuts, flashes = find_cuts(frames, diffs)
    cuts.append(len(frames))
    shots = [analyse_shot(frames, grays, diffs, s, e) for s, e in zip(cuts, cuts[1:]) if e > s]
    for shot in shots:
        shot['flashes'] = [list(f) for f in flashes if shot['start'] <= f[0] < shot['end']]
        # Kept for later stages: big/small alternation (e.g. character on 2s over a pan on 1s)
        # is not separable here; drawing timing is re-measured from pose tracks in stage 2.
        shot['change_pct'] = [round(diffs[i][1] * 100, 2) for i in range(shot['start'], shot['end'])]
    return {'fps': round(fps, 3), 'frames': len(frames), 'shots': shots}


def analyse_clip(path):
    fps, size, frames = read_frames(path)
    if not frames:
        return {'error': 'no frames decoded'}
    result = analyse_frames(frames, fps)
    result['size'] = size
    result['truncated'] = len(frames) >= MAX_FRAMES
    return result


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('data_dir')
    ap.add_argument('--max', type=int, default=0, help='clips to process this run (0 = all)')
    a = ap.parse_args(argv)
    clips = sorted(Path(a.data_dir, 'media').glob('*.mp4'), key=lambda p: int(p.stem) if p.stem.isdigit() else 0)
    done, kinds, holds, flashes = 0, Counter(), Counter(), 0
    for clip in clips:
        out = clip.with_suffix('.shots.json')
        if not out.exists():
            if a.max and done >= a.max:
                continue
            out.write_text(json.dumps(analyse_clip(clip), indent=1), encoding='utf-8')
            done += 1
        for s in json.loads(out.read_text(encoding='utf-8')).get('shots', []):
            kinds[s['kind']] += 1
            flashes += len(s.get('flashes', []))
            if s['kind'] == 'animated':
                holds[s['drawing_hold_mode']] += 1
    print(f'새로 분석 {done}개. 샷 종류: {dict(kinds)}, 플래시 {flashes}개. '
          f'움직이는 샷의 그림 홀드(on Ns): {dict(sorted(holds.items()))}')


if __name__ == '__main__':
    main()
