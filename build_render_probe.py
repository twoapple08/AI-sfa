"""Static render-reference probe (APP-R1); app video pending.

Each segment holds one still image for HOLD frames so codec noise can be averaged.
Coordinates are percent of the 16:9 output (x 0-100 -> width, y 0-100 -> height).
"""
import json
from pathlib import Path
import xml.etree.ElementTree as E
from build_feature_probes import primitive, argb
import copy
from build_priority_probes import polygon, fill
import sfa

ROOT = Path(__file__).resolve().parent
HOLD = 12
DARK = argb(255, 24, 24, 24)
GRAY = argb(255, 128, 128, 128)
WHITE = argb(255, 255, 255, 255)
BLACK = argb(255, 0, 0, 0)
CYAN = argb(255, 40, 200, 255)
ORANGE = argb(255, 255, 150, 40)


def frame(bg):
    f = E.Element('Frame', BackgroundColor=bg)
    E.SubElement(f, 'LayerDef', ID='0', Name='Layer 1', Visible='true', Locked='false')
    return f


def glow(obj, radius, thickness=20, color=CYAN, alpha=255):
    for key, value in (('GlowRadius', radius), ('GlowThickness', thickness),
                       ('GlowColor', color), ('GlowAlpha', alpha)):
        obj.set(key, str(value))
    return obj


def thick(obj, scale):
    obj.set('ThicknessScale', str(scale))
    return obj


def square(first, x, y, size, color):
    edges = polygon(first, [(x, y), (x + size, y), (x + size, y + size), (x, y + size)])
    return [*edges, fill(edges, color)]


def seg_colors():
    f = frame(GRAY)
    swatches = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0), (0, 255, 255),
                (255, 0, 255), (255, 255, 255), (0, 0, 0), (64, 64, 64), (192, 192, 192),
                (255, 150, 40), (40, 120, 230)]
    for i, rgb in enumerate(swatches):
        f.extend(square(10 + 10 * i, 6 + (i % 6) * 15, 15 + (i // 6) * 40, 12, argb(255, *rgb)))
    return f, 'colors', '12 opaque fill swatches (rows of 6) on gray 128; edge lines alpha 0. Color pipeline calibration.'


def seg_lines():
    f = frame(DARK)
    for i, scale in enumerate((0.5, 1.0, 2.0, 4.0)):
        f.append(thick(primitive(10 + i, 1, [(10, 15 + 12 * i), (60, 15 + 12 * i)], WHITE), scale))
    f.append(primitive(20, 1, [(75, 10), (75, 60)], WHITE))
    f.append(primitive(21, 1, [(10, 70), (60, 95)], WHITE))
    f.append(thick(primitive(22, 1, [(80, 80), (80.2, 80)], WHITE), 4.0))
    return f, 'lines', 'White lines on dark: ThicknessScale 0.5/1/2/4 horizontal, vertical, diagonal, near-point stroke.'


def seg_circles():
    f = frame(DARK)
    for i, (d, scale) in enumerate(((8, 1.0), (20, 1.0), (40, 1.0), (20, 3.0))):
        x = 12 + 24 * i
        f.append(thick(primitive(10 + i, 2, [(x, 50 - d / 2), (x, 50 + d / 2)], WHITE), scale))
    return f, 'circles', 'TypeId2 circles: diameter endpoints vertical, diameters 8/20/40 (scale1) and 20 (scale3).'


def seg_curves():
    f = frame(DARK)
    f.append(primitive(10, 3, [(5, 70), (20, 20), (35, 70)], WHITE))
    f.append(primitive(11, 3, [(40, 50), (50, 49), (60, 50)], WHITE))
    f.append(primitive(12, 3, [(70, 70), (95, 30), (70, 70)], WHITE))
    return f, 'curves', 'TypeId3: symmetric arc, near-straight, returning cusp (start==end).'


def seg_glow_lines():
    f = frame(DARK)
    for i, (radius, gthick) in enumerate(((4, 20), (12, 20), (24, 20), (12, 5), (12, 60))):
        f.append(glow(primitive(10 + i, 1, [(15, 12 + 18 * i), (85, 12 + 18 * i)], ORANGE), radius, gthick))
    return f, 'glow_lines', 'Orange lines, cyan glow alpha255: (GlowRadius,GlowThickness)=(4,20),(12,20),(24,20),(12,5),(12,60).'


def seg_glow_shapes():
    f = frame(DARK)
    f.append(glow(primitive(10, 2, [(20, 30), (20, 70)], ORANGE), 12))
    f.append(glow(primitive(11, 3, [(40, 70), (55, 20), (70, 70)], ORANGE), 12))
    f.append(glow(primitive(12, 1, [(85, 50), (85.2, 50)], ORANGE), 12))
    return f, 'glow_shapes', 'Glow 12/20 on circle, curve and near-point stroke.'


def seg_group_glow():
    f = frame(DARK)
    # Left pair: independent crossing lines. Right pair: same geometry, grouped (flags set later).
    f.append(glow(primitive(10, 1, [(10, 30), (40, 70)], ORANGE), 12))
    f.append(glow(primitive(11, 1, [(10, 70), (40, 30)], ORANGE), 12))
    a = glow(primitive(12, 1, [(60, 30), (90, 70)], ORANGE), 12)
    b = glow(primitive(13, 1, [(60, 70), (90, 30)], ORANGE), 12)
    f.extend([a, b])
    return f, 'group_glow', 'Crossing glowing lines: left independent, right grouped (AO13 Index0 child of AO12 Index0).'


def seg_fill_overlap():
    f = frame(WHITE)
    f.extend(square(10, 15, 20, 30, argb(128, 255, 0, 0)))
    f.extend(square(20, 30, 40, 30, argb(128, 0, 0, 255)))
    f.extend(square(30, 60, 20, 30, argb(255, 0, 160, 0)))
    f.extend(square(40, 75, 40, 15, argb(128, 255, 0, 0)))
    return f, 'fill_overlap', 'Fill alpha 128 red over/under alpha 128 blue on white; opaque green with half-alpha red overlap.'


def seg_boundary():
    f = frame(DARK)
    f.append(glow(primitive(10, 1, [(80, 50), (115, 50)], ORANGE), 12))
    f.append(thick(primitive(11, 2, [(20, -10), (20, 20)], WHITE), 2.0))
    f.extend(square(20, -5, 70, 15, argb(255, 40, 120, 230)))
    return f, 'boundary', 'Shapes crossing right/top/left output edges (negative/over-100 coordinates kept).'


SEGMENTS = (seg_colors, seg_lines, seg_circles, seg_curves, seg_glow_lines,
            seg_glow_shapes, seg_group_glow, seg_fill_overlap, seg_boundary)


def identify(source, index, section):
    """Unique IDs per frame; point IDs stay small so group Flags (id << 6) fit in 31 bits."""
    f = copy.deepcopy(source)
    f.set('ID', str(700000 + index))
    f.set('Position', str(index))
    objects = {o.get('ID'): str(section * 1000 + int(o.get('ID'))) for o in f.findall('AO')}
    points = {p.get('ID'): str(1000000 + index * 1000 + j) for j, p in enumerate(f.iter('AP'))}
    for obj in f.findall('AO'):
        obj.set('ID', objects[obj.get('ID')])
        obj.set('DrawOrder', str(section * 1000 + int(obj.get('DrawOrder'))))
    for p in f.iter('AP'):
        p.set('ID', points[p.get('ID')])
    for ac in f.iter('AC'):
        ac.set('ConnPtId', points[ac.get('ConnPtId')])
    for seg in f.iter('FS'):
        seg.set('ObjId', objects[seg.get('ObjId')])
        for key in ('StartPtId', 'EndPtId'):
            if seg.get(key) in points:
                seg.set(key, points[seg.get(key)])
    return f


def group_child_by_index(frame_el, child_ao, parent_ao):
    objs = {o.get('ID'): o for o in frame_el.findall('AO')}
    child = objs[child_ao].find('AP')
    parent = objs[parent_ao].find('AP')
    base = int(child.get('Flags')) & 0x2f
    child.set('Flags', str((int(parent.get('ID')) << 6) | base | 0x10))
    E.SubElement(child, 'AC', ConnPtId=parent.get('ID'))
    E.SubElement(parent, 'AC', ConnPtId=child.get('ID'))


def build(destination):
    dest = Path(destination)
    dest.mkdir(parents=True, exist_ok=True)
    root = E.Element('Sequence', Name='07_render_reference', HeightWidthRatio='0.5625',
                     RatioX='16', RatioY='9', FrameCount='0', BackgroundColor=DARK)
    segments, index = [], 0
    for section, make in enumerate(SEGMENTS, start=1):
        source, key, note = make()
        start = index
        for _ in range(HOLD):
            f = identify(source, index, section)
            if key == 'group_glow':
                group_child_by_index(f, str(section * 1000 + 13), str(section * 1000 + 12))
            root.append(f)
            index += 1
        segments.append({'segment': key, 'frames_1based': [start + 1, index], 'note': note})
    root.set('FrameCount', str(index))
    sfa.write_sfa(root, dest / '07_render_reference.sfa')
    manifest = {
        'status': 'generated; app video pending',
        'file': '07_render_reference.sfa',
        'fps': {'tween_fps': 24, 'playback_fps': 24},
        'frames': index, 'expected_seconds': index / 24,
        'coordinates': 'percent of 16:9 output; 1 unit = width/100 horizontally, height/100 vertically',
        'segments': segments,
        'measure': 'Use the middle frames of each held segment; compare against a future reference renderer.',
    }
    (dest / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=1) + '\n',
                                        encoding='utf-8')
    return manifest, root


if __name__ == '__main__':
    m, _ = build(ROOT / 'examples/render_v1')
    print(f"Built 07_render_reference.sfa: {m['frames']} frames, {len(m['segments'])} segments; app video pending")
