#!/usr/bin/env python3
"""Common representation (characters) -> stickman SFA, one SFA frame per video frame.

Uses the app's default stickman (examples/default_stickman.xml: head circle, torso, two-part
arms from the neck, two-part legs). Each character keeps its AO IDs in every frame so the app
pairs them for tweening; point IDs are unique per frame, as in sfa.make_wave. Holds become
repeated frames, so export with tween = playback = clip fps. Video pixels are fitted into the
16:9 canvas (centre, uniform scale); X/Y are percentages of canvas width/height. Line
thickness follows character height (thin by default). Joints still missing after clean-up
reuse the last known offset from their parent joint, or the template pose.

Usage:  .venv\\Scripts\\python -m pipeline.to_sfa data_sakuga\\media\\123.motion.json OUT.sfa [--shot N]
"""
import argparse
import copy
import json
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / 'examples' / 'default_stickman.xml'
CANVAS = (16.0, 9.0)
TEMPLATE_HEIGHT = 57.0       # head top (Y 5) to feet (Y 62) in the template, % of canvas height
# Template AO order -> (start joint, end joint) in the derived 11-point skeleton below.
# Points: 0 head top, 1 neck, 2 hip, 3 r elbow, 4 r wrist, 5 l elbow, 6 l wrist,
#         7 r knee, 8 r ankle, 9 l knee, 10 l ankle   (screen-left limbs = character's right)
AO_POINTS = [(0, 1), (1, 2), (3, 1), (4, 3), (5, 1), (6, 5), (2, 7), (7, 8), (2, 9), (9, 10)]
PARENT = {0: 1, 2: 1, 3: 1, 4: 3, 5: 1, 6: 5, 7: 2, 8: 7, 9: 2, 10: 9}
COCO_FOR = {3: 8, 4: 10, 5: 7, 6: 9, 7: 14, 8: 16, 9: 13, 10: 15}


def _mid(f, a, b):
    if f[a] is None or f[b] is None:
        return f[a] if f[b] is None else f[b]
    return ((f[a][0] + f[b][0]) / 2, (f[a][1] + f[b][1]) / 2)


def skeleton(frame):
    """17 COCO joints [[x,y,c]] -> 11 stickman points (None when unknown)."""
    f = [None if j[0] is None else (j[0], j[1]) for j in frame]
    neck, hip = _mid(f, 5, 6), _mid(f, 11, 12)
    face = [p for p in f[0:5] if p is not None]
    head_top = None
    if neck is not None and face:
        cx, cy = np.mean([p[0] for p in face]), np.mean([p[1] for p in face])
        head_top = (2 * cx - neck[0], 2 * cy - neck[1])       # circle through neck, centred on the face
    pts = [head_top, neck, hip] + [f[COCO_FOR[i]] for i in range(3, 11)]
    return pts


def template_points():
    root = ET.parse(TEMPLATE).getroot()
    aps = [[(float(p.get('X')), float(p.get('Y'))) for p in ao.findall('AP')] for ao in root.find('Frame').findall('AO')]
    pts = [None] * 11
    for (a, b), ao in zip(AO_POINTS, aps):
        pts[a], pts[b] = ao[0], ao[1]
    return pts


def fit(size):
    """Video px -> canvas % mapping (uniform scale, centred)."""
    w, h = size
    s = min(CANVAS[0] / w, CANVAS[1] / h)
    ox, oy = (CANVAS[0] - w * s) / 2, (CANVAS[1] - h * s) / 2
    return lambda p: ((p[0] * s + ox) / CANVAS[0] * 100, (p[1] * s + oy) / CANVAS[1] * 100)


def fill_missing(seq, rest):
    """Fill None points from the parent using the last known offset (or the template pose)."""
    last = {i: (rest[i][0] - rest[PARENT[i]][0], rest[i][1] - rest[PARENT[i]][1]) for i in PARENT}
    out = []
    for pts in seq:
        pts = list(pts)
        if pts[1] is None:
            pts[1] = out[-1][1] if out else rest[1]
        for i in (2, 0, 3, 5, 7, 9, 4, 6, 8, 10):              # parents before children
            p = PARENT[i]
            if pts[i] is None:
                pts[i] = (pts[p][0] + last[i][0], pts[p][1] + last[i][1])
            else:
                last[i] = (pts[i][0] - pts[p][0], pts[i][1] - pts[p][1])
        out.append(pts)
    return out


def build(motion, shot=None, max_chars=2):
    tree = ET.parse(TEMPLATE)
    root = tree.getroot()
    proto = root.find('Frame')
    root.remove(proto)
    chars = [c for c in motion['characters'] if shot is None or c['shot'] == shot]
    if shot is None and chars:
        shot = max({c['shot'] for c in chars}, key=lambda s: sum(len(c['joints']) for c in chars if c['shot'] == s))
        chars = [c for c in chars if c['shot'] == shot]
    chars = sorted(chars, key=lambda c: -len(c['joints']))[:max_chars]
    if not chars:
        raise ValueError('no character track in this shot')
    to_pct = fit(motion['size'])
    rest = template_points()
    start = min(c['start'] for c in chars)
    end = max(c['start'] + len(c['joints']) for c in chars)
    tracks = []
    for c in chars:
        seq = [[None if p is None else to_pct(p) for p in skeleton(f)] for f in c['joints']]
        seq = fill_missing(seq, rest)
        height = np.median([max(p[1] for p in pts) - min(p[1] for p in pts) for pts in seq])
        tracks.append((c, seq, float(np.clip(0.8 * height / TEMPLATE_HEIGHT, 0.25, 1.5))))
    root.set('Name', f"{motion['clip']}_shot{shot}")
    point_id = 1
    for n, vf in enumerate(range(start, end)):
        frame = ET.SubElement(root, 'Frame', {'BackgroundColor': proto.get('BackgroundColor'),
                                              'ID': str(n + 1), 'Position': str(n)})
        frame.append(copy.deepcopy(proto.find('LayerDef')))
        for k, (c, seq, thick) in enumerate(tracks):
            t = vf - c['start']
            if not 0 <= t < len(seq):
                continue                                       # character not in this frame
            pts = seq[t]
            body = copy.deepcopy(proto.findall('AO'))
            remap = {}
            for ao in body:
                for ap in ao.findall('AP'):
                    remap[ap.get('ID')] = str(point_id)
                    point_id += 1
            for ao, (a, b) in zip(body, AO_POINTS):
                ao.set('ID', str(int(ao.get('ID')) + 100 * k))
                ao.set('DrawOrder', str(int(ao.get('DrawOrder')) + 100 * k))
                ao.set('ThicknessScale', f'{thick:.3f}')
                for ap, idx in zip(ao.findall('AP'), (a, b)):
                    ap.set('ID', remap[ap.get('ID')])
                    ap.set('X', f'{pts[idx][0]:.4f}')
                    ap.set('Y', f'{pts[idx][1]:.4f}')
                    for ac in ap.findall('AC'):
                        ac.set('ConnPtId', remap[ac.get('ConnPtId')])
                frame.append(ao)
    root.set('FrameCount', str(end - start))
    return root, {'shot': shot, 'frames': end - start, 'characters': len(tracks), 'fps': motion['fps']}


def main(argv=None):
    import sys
    sys.path.insert(0, str(ROOT))
    import sfa
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('motion')
    ap.add_argument('out')
    ap.add_argument('--shot', type=int)
    a = ap.parse_args(argv)
    root, info = build(json.loads(Path(a.motion).read_text(encoding='utf-8')), a.shot)
    sfa.write_sfa(root, a.out)
    fps = round(info['fps'])
    print(f"샷 {info['shot']}: {info['frames']}프레임, 인물 {info['characters']}명 → {a.out} "
          f"(트위닝·재생 FPS = {fps},{fps})")


if __name__ == '__main__':
    main()
