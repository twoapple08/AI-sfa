#!/usr/bin/env python3
"""Stage 2 layer 1: per-shot person tracks with 17 COCO joints, and drawing timing from them.

Reads DATA_DIR/media/<id>.mp4 and its <id>.shots.json (run pipeline.shots first). For every
'animated' shot (and the first frame of 'still' shots) it runs a YOLO pose model with ByteTrack,
resetting the tracker at each cut, and writes <id>.pose.npz:
  frame, shot, track (int), box (N,4 xyxy px), kpts (N,17,3 x,y,conf)
Model size, image size and fp16 follow pipeline.hwprofile; on GPU out-of-memory the image size
is lowered and the clip retried. Resumable: clips with a .pose.npz are skipped.

Drawing timing: a joint set that does not move between frames is a held drawing, so
pose_runs() gives on-1s/2s/3s per track without the camera/effect noise of pixel differences.

Usage (repository root):  .venv\\Scripts\\python -m pipeline.pose data_sakuga [--max 20]
"""
import argparse
import json
from collections import Counter
from pathlib import Path

import numpy as np

from pipeline import hwprofile

MODEL_BY_SIZE = {'small': 'yolo11s-pose.pt', 'medium': 'yolo11m-pose.pt', 'large': 'yolo11l-pose.pt'}
IMGSZ_STEPS = [640, 480, 320]
MOVE_FRAC = 0.01     # mean joint shift above 1% of the person's box size = a new drawing
MIN_CONF = 0.5


def pose_runs(kpts, boxes):
    """Run lengths of identical poses for one track. kpts (T,17,3), boxes (T,4)."""
    runs = [1]
    for t in range(1, len(kpts)):
        ok = (kpts[t, :, 2] > MIN_CONF) & (kpts[t - 1, :, 2] > MIN_CONF)
        if not ok.any():
            runs.append(1)
            continue
        size = max(boxes[t, 2] - boxes[t, 0], boxes[t, 3] - boxes[t, 1], 1.0)
        shift = np.linalg.norm(kpts[t, ok, :2] - kpts[t - 1, ok, :2], axis=1).mean() / size
        if shift > MOVE_FRAC:
            runs.append(1)
        else:
            runs[-1] += 1
    return runs


def track_segments(data, min_len=8):
    """Yield (track, rows) for consecutive frames of the same track inside one shot."""
    for shot in np.unique(data['shot']):
        sel = data['shot'] == shot
        for track in np.unique(data['track'][sel]):
            rows = np.flatnonzero(sel & (data['track'] == track))
            rows = rows[np.argsort(data['frame'][rows])]
            if track >= 0 and len(rows) >= min_len and np.all(np.diff(data['frame'][rows]) == 1):
                yield int(track), rows


def _reset(model):
    for tracker in getattr(getattr(model, 'predictor', None), 'trackers', None) or []:
        tracker.reset()


def extract_clip(model, clip, shot_list, imgsz, half):
    import cv2
    wanted = {}
    for i, s in enumerate(shot_list):
        if s['kind'] == 'animated':
            wanted.update({f: i for f in range(s['start'], s['end'])})
        elif s['kind'] == 'still':
            wanted[s['start']] = i
    rows = {'frame': [], 'shot': [], 'track': [], 'box': [], 'kpts': []}
    cap = cv2.VideoCapture(str(clip))
    f, last_shot = 0, None
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        shot = wanted.get(f)
        if shot is not None:
            if shot != last_shot:
                _reset(model)
                last_shot = shot
            r = model.track(frame, persist=True, imgsz=imgsz, quantize=16 if half else None, verbose=False,
                            tracker='bytetrack.yaml')[0]
            if r.keypoints is not None and len(r.boxes):
                ids = r.boxes.id.int().cpu().numpy() if r.boxes.id is not None else -np.ones(len(r.boxes), int)
                kp = r.keypoints.data.cpu().numpy()
                for j in range(len(r.boxes)):
                    rows['frame'].append(f)
                    rows['shot'].append(shot)
                    rows['track'].append(ids[j])
                    rows['box'].append(r.boxes.xyxy[j].cpu().numpy())
                    rows['kpts'].append(kp[j])
        f += 1
    cap.release()
    return {'frame': np.array(rows['frame'], np.int32), 'shot': np.array(rows['shot'], np.int16),
            'track': np.array(rows['track'], np.int32),
            'box': np.array(rows['box'], np.float32).reshape(-1, 4),
            'kpts': np.array(rows['kpts'], np.float32).reshape(-1, 17, 3)}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('data_dir')
    ap.add_argument('--max', type=int, default=0, help='clips to process this run (0 = all)')
    a = ap.parse_args(argv)
    import torch
    from ultralytics import YOLO
    profile = hwprofile.detect(a.data_dir)
    settings = profile['settings']
    gpu = torch.cuda.is_available()
    half = bool(settings['fp16'] and gpu)
    models_dir = Path('models')
    models_dir.mkdir(exist_ok=True)
    name = MODEL_BY_SIZE[settings['pose_model']]
    model = YOLO(str(models_dir / name) if (models_dir / name).exists() else name)
    if not (models_dir / name).exists() and Path(name).exists():
        Path(name).replace(models_dir / name)          # keep downloaded weights out of the repo root
    print(f"등급 {profile['tier']}: {name}, fp16={half}, GPU={gpu}")
    media = Path(a.data_dir, 'media')
    done, timing = 0, Counter()
    imgsz_i = 0
    for meta in sorted(media.glob('*.shots.json')):
        clip = media / (meta.name.split('.')[0] + '.mp4')
        out = clip.with_suffix('.pose.npz')
        if out.exists() or not clip.exists():
            continue
        if a.max and done >= a.max:
            break
        shot_list = json.loads(meta.read_text(encoding='utf-8')).get('shots', [])
        while True:
            try:
                data = extract_clip(model, clip, shot_list, IMGSZ_STEPS[imgsz_i], half)
                break
            except torch.cuda.OutOfMemoryError:
                torch.cuda.empty_cache()
                if imgsz_i + 1 >= len(IMGSZ_STEPS):
                    raise
                imgsz_i += 1
                print(f'  메모리 부족: imgsz {IMGSZ_STEPS[imgsz_i]}로 낮춰 재시도')
        tmp = out.with_name(out.name.replace('.pose.npz', '.pose_tmp.npz'))
        np.savez_compressed(tmp, imgsz=IMGSZ_STEPS[imgsz_i], model=name, **data)
        tmp.replace(out)                                # whole file or nothing if the PC is turned off
        for _, rows in track_segments(data):
            runs = pose_runs(data['kpts'][rows], data['box'][rows])
            timing[Counter(runs).most_common(1)[0][0]] += 1
        done += 1
        print(f"  {clip.name}: 사람 검출 {len(data['frame'])}건")
    print(f'새로 추출 {done}개. 트랙별 그림 홀드(on Ns): {dict(sorted(timing.items()))}')


if __name__ == '__main__':
    main()
