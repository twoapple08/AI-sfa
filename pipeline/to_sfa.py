#!/usr/bin/env python3
"""Common representation (characters) -> stickman SFA, one SFA frame per video frame.

Uses the app's default stickman (examples/default_stickman.xml: head circle, torso, two-part
arms from the neck, two-part legs). Each character keeps its AO IDs in every frame so the app
pairs them for tweening; point IDs are unique per frame, as in sfa.make_wave. Holds become
repeated frames, so export with tween = playback = clip fps. Video pixels are fitted into the
16:9 canvas (centre, uniform scale); X/Y are percentages of canvas width/height. Line
thickness follows character height (thin by default). Joints still missing after clean-up:
a briefly hidden limb keeps its last shape; an off-screen (or long-hidden) one continues its
parent bone straight at its usual length, beyond the canvas edge when it left the picture.
A person whose track broke into pieces keeps one slot (one set of AO IDs): pieces that do not
overlap in time are chained into the slot whose neighbouring piece ends/starts nearest to them.

Usage:  .venv\\Scripts\\python -m pipeline.to_sfa data_sakuga\\media\\123.motion.json OUT.sfa [--shot N | --clip]
        .venv\\Scripts\\python -m pipeline.to_sfa data_sakuga        (every clip -> data_sakuga\\sfa\\<id>.sfa)
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
    face_c = (float(np.mean([p[0] for p in face])), float(np.mean([p[1] for p in face]))) if face else None
    return [face_c, neck, hip] + [f[COCO_FOR[i]] for i in range(3, 11)]   # point 0: face centre for now


def place_heads(seq, torso):
    """Point 0 (face centre) -> head-circle top. The stickman head is a rigid circle: its size is
    fixed per character (template head/torso ratio x the character's median torso), never taken
    from the drawing (hair, big anime heads) or from the face-neck distance (shrinks when the head
    bows). Only its direction follows the face: bowing, looking up and tilting move the circle."""
    ratio, _ = _template_geometry()
    diameter = ratio[0] * torso
    out = []
    for pts in seq:
        pts = list(pts)
        neck, face, hip = pts[1], pts[0], pts[2]
        v = (face[0] - neck[0], face[1] - neck[1]) if face is not None else (neck[0] - hip[0], neck[1] - hip[1])
        n = float(np.hypot(*v)) or 1.0
        pts[0] = (neck[0] + v[0] / n * diameter, neck[1] + v[1] / n * diameter)
        out.append(pts)
    return out


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


ORDER = (2, 0, 3, 5, 7, 9, 4, 6, 8, 10)          # parents before children (neck handled first)
RECENT = 6                                       # frames a briefly hidden limb keeps its last shape


def offscreen_points(bits):
    """COCO off-screen bitmask -> set of stickman point indices."""
    off = {i for i, j in COCO_FOR.items() if bits >> j & 1}
    if bits >> 5 & 1 and bits >> 6 & 1:
        off.add(1)
    if bits >> 11 & 1 and bits >> 12 & 1:
        off.add(2)
    return off


def _template_geometry():
    """Bone length / torso length and unit direction of each bone in the template (canvas units)."""
    phys = [(x * CANVAS[0] / 100, y * CANVAS[1] / 100) for x, y in template_points()]
    torso = float(np.hypot(phys[2][0] - phys[1][0], phys[2][1] - phys[1][1]))
    ratio, direction = {}, {}
    for i, p in PARENT.items():
        v = (phys[i][0] - phys[p][0], phys[i][1] - phys[p][1])
        n = float(np.hypot(*v)) or 1.0
        ratio[i], direction[i] = n / torso, (v[0] / n, v[1] / n)
    return ratio, direction


def fill_missing(seq, offscreen=None, frame_height=1080):
    """Fill unknown points in video pixels (isotropic, so lengths are real).
    A limb hidden for a moment keeps its last shape; a limb that left the picture (or stays
    hidden) continues its parent bone straight at its usual length, past the frame edge if
    needed (the app keeps off-canvas coordinates)."""
    ratio, tdir = _template_geometry()
    lengths = {}
    for i, p in PARENT.items():
        seen = [np.hypot(f[i][0] - f[p][0], f[i][1] - f[p][1]) for f in seq if f[i] is not None and f[p] is not None]
        if seen:
            lengths[i] = float(np.median(seen))
    torso = lengths.get(2, 0.25 * frame_height)
    for i in PARENT:
        lengths.setdefault(i, ratio[i] * torso)
    first_neck = next((f[1] for f in seq if f[1] is not None), (0.0, 0.0))
    last, age, out = {}, {}, []
    for t, pts in enumerate(seq):
        pts = list(pts)
        off = offscreen_points(offscreen[t]) if offscreen else set()
        if pts[1] is None:
            pts[1] = out[-1][1] if out else first_neck
        for i in ORDER:
            p = PARENT[i]
            if pts[i] is not None:
                last[i], age[i] = (pts[i][0] - pts[p][0], pts[i][1] - pts[p][1]), 0
                continue
            age[i] = age.get(i, RECENT) + 1
            if i not in off and i in last and age[i] <= RECENT:
                pts[i] = (pts[p][0] + last[i][0], pts[p][1] + last[i][1])
                continue
            gp = PARENT.get(p)
            v = (pts[p][0] - pts[gp][0], pts[p][1] - pts[gp][1]) if gp is not None else last.get(i, tdir[i])
            n = float(np.hypot(*v)) or 1.0
            pts[i] = (pts[p][0] + v[0] / n * lengths[i], pts[p][1] + v[1] / n * lengths[i])
        out.append(pts)
    return out


def fit_box(points, margin=0.06):
    """World mode: fit the whole composition (every joint of the shot) into the canvas."""
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    w, h = max(xs) - min(xs) or 1.0, max(ys) - min(ys) or 1.0
    s = min(CANVAS[0] * (1 - 2 * margin) / w, CANVAS[1] * (1 - 2 * margin) / h)
    ox = (CANVAS[0] - w * s) / 2 - min(xs) * s
    oy = (CANVAS[1] - h * s) / 2 - min(ys) * s
    return lambda q: ((q[0] * s + ox) / CANVAS[0] * 100, (q[1] * s + oy) / CANVAS[1] * 100)


def _cams(c):
    cams = c.get('camera')
    return [np.asarray(m, float).reshape(2, 3) for m in cams] if cams and len(cams) == len(c['joints']) else None


JOIN_DIST = 1.5          # max neck jump (x the piece's torso) to chain a piece onto an occupied slot


def _anchor(c, last):
    """Screen position of a piece at its first/last frame with a known neck or hip, and its torso."""
    frames = c['joints'][::-1] if last else c['joints']
    for f in frames:
        pts = skeleton(f)
        if pts[1] is not None and pts[2] is not None:
            return pts[1], float(np.hypot(pts[2][0] - pts[1][0], pts[2][1] - pts[1][1]))
        if pts[1] is not None or pts[2] is not None:
            return pts[1] or pts[2], None
    return None, None


def assign_slots(chars, frame_height, max_slots=2):
    """Track pieces of one shot -> at most max_slots people, each a list of pieces that never
    overlap in time. Longest pieces first; a piece joins the free-in-time slot whose neighbouring
    piece (just before or after it) is nearest at the junction, or opens a new slot when every
    such slot is far (another person) and a slot is still free. Pieces that overlap every slot
    are dropped (a third person, or a duplicate detection)."""
    slots = []
    for c in sorted(chars, key=lambda c: -len(c['joints'])):
        a, b = c['start'], c['start'] + len(c['joints'])
        best = None
        for slot in slots:
            if any(a < d['start'] + len(d['joints']) and d['start'] < b for d in slot):
                continue
            before = [d for d in slot if d['start'] + len(d['joints']) <= a]
            after = [d for d in slot if d['start'] >= b]
            dists = []
            if before:
                d = max(before, key=lambda d: d['start'])
                p, _ = _anchor(d, last=True)
                q, torso = _anchor(c, last=False)
                if p is not None and q is not None:
                    dists.append(np.hypot(p[0] - q[0], p[1] - q[1]) / (torso or 0.25 * frame_height))
            if after:
                d = min(after, key=lambda d: d['start'])
                p, _ = _anchor(d, last=False)
                q, torso = _anchor(c, last=True)
                if p is not None and q is not None:
                    dists.append(np.hypot(p[0] - q[0], p[1] - q[1]) / (torso or 0.25 * frame_height))
            dist = min(dists) if dists else float('inf')
            if best is None or dist < best[0]:
                best = (dist, slot)
        if len(slots) < max_slots and (best is None or best[0] > JOIN_DIST):
            slots.append([c])
        elif best is not None:
            best[1].append(c)
    return [sorted(slot, key=lambda c: c['start']) for slot in slots]


def _slot_tracks(motion, slots, world):
    """Slots of one shot -> per slot ({video frame: canvas points}, line thickness)."""
    from pipeline import camera
    raws, torsos = {}, {}
    for k, slot in enumerate(slots):                       # one body size per slot, not per piece
        seen = []
        for c in slot:
            cams = _cams(c)
            raw = [skeleton(f) for f in c['joints']]
            if cams is not None:                           # geometry in world units: lengths and head fixed
                raw = [[None if p is None else tuple(camera.to_world(m, [p])[0]) for p in pts]
                       for pts, m in zip(raw, cams)]
            raws[id(c)] = raw
            seen += [np.hypot(f[2][0] - f[1][0], f[2][1] - f[1][1]) for f in raw if f[1] is not None and f[2] is not None]
        torsos[k] = float(np.median(seen)) if seen else 0.25 * motion['size'][1]
    worlds = []
    for k, slot in enumerate(slots):
        for c in slot:
            cams = _cams(c)
            px = place_heads(fill_missing(raws[id(c)], c.get('offscreen'), motion['size'][1]), torsos[k])
            if cams is not None and not world:
                px = [[tuple(camera.to_screen(m, [p])[0]) for p in pts] for pts, m in zip(px, cams)]
            worlds.append((k, c, px))
    to_pct = fit_box([p for _, _, px in worlds for pts in px for p in pts]) if world else fit(motion['size'])
    tracks = [({}, []) for _ in slots]                     # per slot: video frame -> points, heights
    for k, c, px in worlds:
        for t, pts in enumerate(px):
            seq = [to_pct(p) for p in pts]
            tracks[k][0][c['start'] + t] = seq
            tracks[k][1].append(max(p[1] for p in seq) - min(p[1] for p in seq))
    return [(frames, float(np.clip(0.8 * np.median(h) / TEMPLATE_HEIGHT, 0.25, 1.5))) for frames, h in tracks]


def _write_frames(root, proto, tracks, start, end):
    """One SFA frame per video frame in [start, end); a slot keeps its AO IDs (base 100*k).
    thick: one value per slot, or {video frame: value} when it changes per shot."""
    point_id = 1
    for n, vf in enumerate(range(start, end)):
        frame = ET.SubElement(root, 'Frame', {'BackgroundColor': proto.get('BackgroundColor'),
                                              'ID': str(n + 1), 'Position': str(n)})
        frame.append(copy.deepcopy(proto.find('LayerDef')))
        for k, (frames, thick) in enumerate(tracks):
            pts = frames.get(vf)
            if pts is None:
                continue                                       # character not in this frame
            th = thick[vf] if isinstance(thick, dict) else thick
            body = copy.deepcopy(proto.findall('AO'))
            remap = {}
            for ao in body:
                for ap in ao.findall('AP'):
                    remap[ap.get('ID')] = str(point_id)
                    point_id += 1
            for ao, (a, b) in zip(body, AO_POINTS):
                ao.set('ID', str(int(ao.get('ID')) + 100 * k))
                ao.set('DrawOrder', str(int(ao.get('DrawOrder')) + 100 * k))
                ao.set('ThicknessScale', f'{th:.3f}')
                for ap, idx in zip(ao.findall('AP'), (a, b)):
                    ap.set('ID', remap[ap.get('ID')])
                    ap.set('X', f'{pts[idx][0]:.4f}')
                    ap.set('Y', f'{pts[idx][1]:.4f}')
                    for ac in ap.findall('AC'):
                        ac.set('ConnPtId', remap[ac.get('ConnPtId')])
                frame.append(ao)
    root.set('FrameCount', str(end - start))


def _template_root():
    root = ET.parse(TEMPLATE).getroot()
    proto = root.find('Frame')
    root.remove(proto)
    return root, proto


def build(motion, shot=None, max_chars=2, world=False):
    """One shot (default: the shot with the most tracked frames).
    world=False: as filmed (camera zoom/pan baked into the points, the app has no camera).
    world=True: camera removed, the whole composition fitted once, so a camera move can be
    added by hand in the editor (move/scale everything together)."""
    root, proto = _template_root()
    chars = [c for c in motion['characters'] if shot is None or c['shot'] == shot]
    if shot is None and chars:
        shot = max({c['shot'] for c in chars}, key=lambda s: sum(len(c['joints']) for c in chars if c['shot'] == s))
        chars = [c for c in chars if c['shot'] == shot]
    slots = assign_slots(chars, motion['size'][1], max_chars)
    if not slots:
        raise ValueError('no character track in this shot')
    chars = [c for slot in slots for c in slot]
    start = min(c['start'] for c in chars)
    end = max(c['start'] + len(c['joints']) for c in chars)
    tracks = _slot_tracks(motion, slots, world)
    root.set('Name', f"{motion['clip']}_shot{shot}")
    _write_frames(root, proto, tracks, start, end)
    return root, {'shot': shot, 'frames': end - start, 'characters': len(tracks), 'pieces': len(chars),
                  'fps': motion['fps']}


def build_clip(motion, n_frames=None, max_chars=2, world=False):
    """Whole clip, every shot, frame n = video frame n (so it lines up with the video; frames
    without a tracked person stay empty). n_frames: clip length (shots.json); default: last
    tracked frame. Slots are chosen per shot; world mode fits each shot separately."""
    root, proto = _template_root()
    tracks, pieces = [], 0
    for shot in sorted({c['shot'] for c in motion['characters']}):
        slots = assign_slots([c for c in motion['characters'] if c['shot'] == shot], motion['size'][1], max_chars)
        pieces += sum(len(s) for s in slots)
        for k, (frames, thick) in enumerate(_slot_tracks(motion, slots, world)):
            if k == len(tracks):
                tracks.append(({}, {}))
            tracks[k][0].update(frames)
            tracks[k][1].update(dict.fromkeys(frames, thick))   # line width follows each shot's framing
    if not tracks:
        raise ValueError('no character track in this clip')
    end = max(max(f) + 1 for f, _ in tracks)
    end = max(end, n_frames or 0)
    root.set('Name', f"{motion['clip']}")
    _write_frames(root, proto, tracks, 0, end)
    return root, {'frames': end, 'characters': len(tracks), 'pieces': pieces, 'fps': motion['fps']}


def convert_all(data_dir, max_chars=2, world=False):
    """media/<id>.motion.json -> sfa/<id>.sfa (whole clip), skipping files already made."""
    import sys
    sys.path.insert(0, str(ROOT))
    import sfa
    media, out_dir = Path(data_dir, 'media'), Path(data_dir, 'sfa')
    out_dir.mkdir(exist_ok=True)
    done = empty = 0
    for path in sorted(media.glob('*.motion.json')):
        stem = path.name.replace('.motion.json', '')
        out = out_dir / f'{stem}.sfa'
        if out.exists():
            continue
        shots = media / f'{stem}.shots.json'
        n = json.loads(shots.read_text(encoding='utf-8')).get('frames') if shots.exists() else None
        try:
            root, _ = build_clip(json.loads(path.read_text(encoding='utf-8')), n, max_chars, world)
        except ValueError:                                     # nobody tracked in the whole clip
            empty += 1
            continue
        sfa.write_sfa(root, out)                               # atomic (temp file + replace)
        done += 1
    print(f'새로 변환 {done}개, 인물 없음 {empty}개 → {out_dir}')


def main(argv=None):
    import sys
    sys.path.insert(0, str(ROOT))
    import sfa
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('motion', help='<id>.motion.json, or the data folder (data_sakuga) to convert every clip')
    ap.add_argument('out', nargs='?')
    ap.add_argument('--shot', type=int)
    ap.add_argument('--clip', action='store_true', help='whole clip, every shot, aligned with the video')
    ap.add_argument('--world', action='store_true', help='camera removed: whole composition, fixed framing')
    a = ap.parse_args(argv)
    if Path(a.motion).is_dir():
        convert_all(a.motion, world=a.world)
        return
    if not a.out:
        ap.error('out is required for a single motion file')
    motion = json.loads(Path(a.motion).read_text(encoding='utf-8'))
    if a.clip:
        root, info = build_clip(motion, world=a.world)
        label = '클립 전체'
    else:
        root, info = build(motion, a.shot, world=a.world)
        label = f"샷 {info['shot']}"
    sfa.write_sfa(root, a.out)
    fps = round(info['fps'])
    print(f"{label}: {info['frames']}프레임, 인물 {info['characters']}명(조각 {info['pieces']}) → {a.out} "
          f"(트위닝·재생 FPS = {fps},{fps})")

if __name__ == '__main__':
    main()
