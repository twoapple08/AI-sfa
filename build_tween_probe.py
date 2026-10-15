"""Tween reference probe (APP-T1); app video pending.

Each case is two consecutive source frames (A then B). Export at (tween, playback) = (30, 12)
so K = round(2.5) = 3 and t is quantised. Predictions come from sfa_tween (static reading).
"""
import json
from pathlib import Path
import xml.etree.ElementTree as E
from build_feature_probes import primitive, argb
from build_render_probe import frame, glow, thick, identify, DARK, WHITE, ORANGE, CYAN
from build_priority_probes import polygon
import sfa
import sfa_tween

ROOT = Path(__file__).resolve().parent
TWEEN_FPS, PLAYBACK_FPS = 30, 12
RED, BLUE = argb(255, 230, 40, 40), argb(255, 40, 90, 235)


def case_motion():
    a, b = frame(DARK), frame(DARK)
    a.append(primitive(10, 1, [(10, 30), (40, 30)], argb(255, 0, 0, 0)))
    b.append(thick(primitive(10, 1, [(60, 70), (90, 40)], argb(255, 255, 255, 255)), 3.0))
    a[-1].set('Color', argb(255, 10, 200, 20))
    b[-1].set('Color', argb(255, 250, 20, 230))
    return a, b, 'motion', 'Line moves/rotates; colour (10,200,20)->(250,20,230); thickness 1->3.'


def case_glow():
    a, b = frame(DARK), frame(DARK)
    a.append(glow(primitive(10, 1, [(15, 50), (85, 50)], ORANGE), 0, 10, CYAN, 0))
    b.append(glow(primitive(10, 1, [(15, 50), (85, 50)], ORANGE), 24, 60, argb(255, 255, 40, 200), 255))
    return a, b, 'glow', 'GlowRadius 0->24, GlowThickness 10->60, GlowAlpha 0->255, GlowColor cyan->pink.'


def case_hidden_layer():
    a, b = frame(DARK), frame(DARK)
    for f, dx in ((a, 0), (b, 20)):
        E.SubElement(f, 'LayerDef', ID='1', Name='Layer 2', Visible='false', Locked='false')
        f.append(thick(primitive(10, 1, [(10 + dx, 30), (40 + dx, 30)], WHITE), 2.0))
        hidden = thick(primitive(11, 1, [(10 + dx, 70), (40 + dx, 70)], ORANGE, layer=1), 2.0)
        f.append(hidden)
    return a, b, 'hidden_layer', 'Both frames: white line on visible Layer 1, orange line on hidden Layer 2. Prediction: orange drawn in source frames, absent in intermediate frames.'


def case_links():
    a, b = frame(DARK), frame(DARK)
    a.append(thick(primitive(10, 1, [(10, 30), (30, 30)], WHITE), 2.0))
    b.append(thick(primitive(11, 1, [(60, 30), (80, 30)], WHITE), 2.0))
    a.append(thick(primitive(12, 1, [(10, 70), (30, 70)], ORANGE), 2.0))
    b.append(thick(primitive(13, 1, [(60, 70), (80, 70)], ORANGE), 2.0))
    return a, b, 'links', 'Different AO IDs: white pair has TweenLink (B.ID=11 From=10), orange pair has none. Prediction: white slides; orange absent in intermediate frames.'


def tri(first, x, color, refs):
    edges = polygon(first, [(x, 70), (x + 12, 30), (x + 24, 70)], '0')
    region = E.Element('FR', Color=color)
    for e in edges:
        a, b = e.findall('AP')
        E.SubElement(region, 'FS', Kind='0', ObjId=e.get('ID'),
                     StartPtId=a.get('ID') if refs else '-1', EndPtId=b.get('ID') if refs else '-1',
                     StartT='0.0', EndT='1.0', Contour='0')
    for e in edges:
        e.set('Color', WHITE)
    return [*edges, region]


def case_fills():
    a, b = frame(DARK), frame(DARK)
    a.extend(tri(10, 15, RED, refs=False))
    b.extend(tri(10, 15, BLUE, refs=False))
    a.extend(tri(20, 60, RED, refs=True))
    b.extend(tri(20, 60, BLUE, refs=True))
    return a, b, 'fills', 'Left triangle fill FS with -1 point refs, right with point IDs; red->blue. Prediction: left colour interpolates, right stays red until B.'


def case_create_delete():
    a, b = frame(DARK), frame(DARK)
    a.append(thick(primitive(10, 2, [(25, 35), (25, 65)], WHITE), 2.0))
    b.append(thick(primitive(11, 2, [(75, 35), (75, 65)], ORANGE), 2.0))
    return a, b, 'create_delete', 'Circle only in A, another only in B. Prediction: both absent in intermediate frames.'


def case_shapes():
    a, b = frame(DARK), frame(DARK)
    a.append(thick(primitive(10, 3, [(10, 70), (25, 70), (40, 70)], WHITE), 2.0))
    b.append(thick(primitive(10, 3, [(10, 70), (25, 10), (40, 70)], WHITE), 2.0))
    a.append(thick(primitive(11, 2, [(70, 45), (70, 55)], ORANGE), 2.0))
    b.append(thick(primitive(11, 2, [(70, 20), (70, 80)], ORANGE), 2.0))
    return a, b, 'shapes', 'Curve control point rises; circle diameter 10->60 (linear point interpolation).'


CASES = (case_motion, case_glow, case_hidden_layer, case_links, case_fills, case_create_delete, case_shapes)


def build(destination):
    dest = Path(destination)
    dest.mkdir(parents=True, exist_ok=True)
    root = E.Element('Sequence', Name='08_tween_reference', HeightWidthRatio='0.5625',
                     RatioX='16', RatioY='9', FrameCount='0', BackgroundColor=DARK)
    cases, index = [], 0
    for section, make in enumerate(CASES, start=1):
        a, b, key, note = make()
        fa, fb = identify(a, index, section), identify(b, index + 1, section)
        if key == 'links':
            E.SubElement(fb, 'TweenLink', ID=str(section * 1000 + 11), From=str(section * 1000 + 10))
        root.extend([fa, fb])
        cases.append({'case': key, 'source_frames_1based': [index + 1, index + 2], 'note': note})
        index += 2
    root.set('FrameCount', str(index))
    sfa.write_sfa(root, dest / '08_tween_reference.sfa')
    plan = sfa_tween.timeline(index, TWEEN_FPS, PLAYBACK_FPS)
    manifest = {
        'status': 'generated; app video pending',
        'file': '08_tween_reference.sfa',
        'fps': {'tween_fps': TWEEN_FPS, 'playback_fps': PLAYBACK_FPS},
        'source_frames': index,
        'predicted': {'output_fps': plan['output_fps'], 'steps_K': plan['steps'],
                      'output_frames': len(plan['frames']),
                      'output_map_1based': [[j + 1, a + 1, b + 1, round(t, 4)] for j, (a, b, t) in enumerate(plan['frames'])]},
        'cases': cases,
        'prediction_source': 'sfa_tween.py (static AOT reading); not app-verified',
    }
    (dest / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    return manifest, root


if __name__ == '__main__':
    m, _ = build(ROOT / 'examples/tween_v1')
    print(f"Built 08_tween_reference.sfa: {m['source_frames']} source frames -> predicted "
          f"{m['predicted']['output_frames']} output frames at {m['predicted']['output_fps']} fps; app video pending")
