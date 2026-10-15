#!/usr/bin/env python3
"""Export timeline and frame interpolation following the static AOT reading.

Sources: docs/AOT-GROUP-SHADER-TIMELINE-TRACE-2026-10-15.md (PlaybackEnumeration),
docs/AOT-OBJECT-TWEEN-PAIR-TRACE-2026-10-15.md (object/point pairs, attribute rounding),
docs/AOT-FILL-TWEEN-TRACE-2026-10-15.md (fill pairing, held steps).
Unverified choices are marked ASSUMPTION. Standard library only.
"""
import copy
import math
import xml.etree.ElementTree as E


def dart_round(x):
    """Dart num.round(): half away from zero."""
    return int(math.floor(x + 0.5)) if x >= 0 else -int(math.floor(-x + 0.5))


def timeline(frame_count, tween_fps, playback_fps, tweening_enabled=True):
    """[(front_index, back_index, t)] for every exported frame (0-based)."""
    p = max(playback_fps, 1)
    active = tweening_enabled and tween_fps > p
    q = tween_fps if active else p
    k = max(dart_round(q / p), 1) if active else 1
    n = -(-max(frame_count, 0) * q // p)          # ceil
    out = []
    for j in range(n):
        a = min(j * p // q, frame_count - 1)
        b = min(a + 1, frame_count - 1)
        j0 = -(-a * q // p)
        m = 0 if (not active or a == b or j == j0) else ((j * p) % q) * k // q
        out.append((a, b, (m / k) if (m > 0 and k > 0) else 0.0))
    return {'output_fps': q, 'steps': k, 'frames': out, 'interpolation_active': active}


def interpolate_argb(c0, c1, t):
    t = min(max(t, 0.0), 1.0)
    out = 0
    for shift in (24, 16, 8, 0):
        a, b = (c0 >> shift) & 255, (c1 >> shift) & 255
        out |= min(max(a + dart_round((b - a) * t), 0), 255) << shift
    return out


def u32(value):
    return int(value) & 0xFFFFFFFF


def s32(value):
    value &= 0xFFFFFFFF
    return value - (1 << 32) if value >= 1 << 31 else value


def _points(obj):
    return obj.findall('AP')


def _same_points(a, b):
    pa, pb = _points(a), _points(b)
    return len(pa) == len(pb) and all(x.get('Index') == y.get('Index') for x, y in zip(pa, pb))


def resolve_links(front, back):
    """TweenLink on the back frame: ID = back AO, From = front AO. Returns front ID -> back AO."""
    fmap = {o.get('ID'): o for o in front.findall('AO')}
    bmap = {o.get('ID'): o for o in back.findall('AO')}
    links = {}
    for link in back.iter('TweenLink'):
        links[link.get('ID')] = link.get('From')
    result = {}
    for dest in sorted(links, key=lambda v: int(v) if v.lstrip('-').isdigit() else 0):
        src = links[dest]
        a, b = fmap.get(src), bmap.get(dest)
        if a is None or b is None or src in result or dest in fmap or src in bmap:
            continue
        if a.get('TypeId') != b.get('TypeId') or not _same_points(a, b):
            continue
        result[src] = b
    return result


def _visible_front_objects(front):
    layers = front.findall('LayerDef')
    objs = front.findall('AO')
    if not layers:
        return objs
    ordered = []
    for layer in layers:
        if layer.get('Visible', 'true') == 'true':
            ordered += [o for o in objs if o.get('LayerId') == layer.get('ID')]
    return ordered


def _lerp(a, b, t):
    return a + (b - a) * t


def _interp_object(a, b, t):
    o = E.Element('AO', dict(a.attrib))          # ID, LayerId, TypeId, ObjectScale from front
    num = lambda el, k, d='0': float(el.get(k, d) or d)
    o.set('Color', str(s32(interpolate_argb(u32(a.get('Color', '-16777216')), u32(b.get('Color', '-16777216')), t))))
    o.set('GlowColor', str(s32(interpolate_argb(u32(a.get('GlowColor', '-1')), u32(b.get('GlowColor', '-1')), t))))
    o.set('ThicknessScale', repr(_lerp(num(a, 'ThicknessScale', '1'), num(b, 'ThicknessScale', '1'), t)))
    o.set('GlowRadius', str(dart_round(_lerp(num(a, 'GlowRadius'), num(b, 'GlowRadius'), t))))
    o.set('GlowThickness', str(dart_round(_lerp(num(a, 'GlowThickness'), num(b, 'GlowThickness'), t))))
    ga, gb = int(num(a, 'GlowAlpha')), int(num(b, 'GlowAlpha'))
    o.set('GlowAlpha', str(ga + int((gb - ga) * t)))           # trunc toward zero
    bpts = _points(b)
    for i, p in enumerate(_points(a)):
        q = bpts[i] if i < len(bpts) and bpts[i].get('Index') == p.get('Index') else \
            next((x for x in bpts if x.get('Index') == p.get('Index')), p)
        np_ = E.SubElement(o, 'AP', dict(p.attrib))
        np_.set('X', repr(_lerp(float(p.get('X')), float(q.get('X')), t)))
        np_.set('Y', repr(_lerp(float(p.get('Y')), float(q.get('Y')), t)))
        for c in p.findall('AC'):
            np_.append(copy.deepcopy(c))
    return o


# ---- fills -------------------------------------------------------------------------------

def _outer_only_from(region, ids):
    outer = [s for s in region.findall('FS') if float(s.get('Contour', '0') or 0) == 0]
    return bool(outer) and all(s.get('ObjId') in ids for s in outer)


def _seg_signature(s):
    if s.get('Kind') == '1':
        return ('c', s.get('ObjId'), s.get('Contour', '0'))
    return ('e', s.get('ObjId'), s.get('StartPtId'), s.get('EndPtId'),
            float(s.get('StartT', '0') or 0), float(s.get('EndT', '1') or 1), s.get('Contour', '0'))


def _seg_key(s):
    contour = s.get('Contour', '0')
    if s.get('Kind') == '1':
        return (contour, 'c', s.get('ObjId'))
    ref = lambda v: '*' if v is None or v.startswith('-') else v
    return (contour, 'e', s.get('ObjId'), ref(s.get('StartPtId')), ref(s.get('EndPtId')))


def _region_key(region):
    # ASSUMPTION: canonical rotation/direction normalisation is approximated by sorting.
    return tuple(sorted((_seg_key(s) for s in region.findall('FS')), key=repr))


def _rename(region, ao_map, ap_map):
    r = copy.deepcopy(region)
    for s in r.findall('FS'):
        s.set('ObjId', ao_map.get(s.get('ObjId'), s.get('ObjId')))
        for k in ('StartPtId', 'EndPtId'):
            if s.get(k) in ap_map:
                s.set(k, ap_map[s.get(k)])
    return r


def _interp_region(fa, fb, t):
    color = interpolate_argb(u32(fa.get('Color', '0')), u32(fb.get('Color', '0')), t)
    if color >> 24 == 0:
        return None
    sa, sb = fa.findall('FS'), fb.findall('FS')
    ok = len(sa) == len(sb) and all((x.get('Kind'), x.get('Contour', '0'), x.get('ObjId')) ==
                                     (y.get('Kind'), y.get('Contour', '0'), y.get('ObjId')) for x, y in zip(sa, sb))
    out = E.Element('FR', Color=str(s32(color)))
    if ok:
        for x, y in zip(sa, sb):
            s = E.SubElement(out, 'FS', dict(x.attrib))
            for k in ('StartPtId', 'EndPtId'):
                if x.get(k) is not None and x.get(k).startswith('-') and y.get(k) is not None:
                    s.set(k, y.get(k))
            if x.get('Kind') != '1':
                tc = min(max(t, 0.0), 1.0)
                s.set('StartT', repr(_lerp(float(x.get('StartT', '0') or 0), float(y.get('StartT', '0') or 0), tc)))
                s.set('EndT', repr(_lerp(float(x.get('EndT', '1') or 1), float(y.get('EndT', '1') or 1), tc)))
    else:
        for s in (sa if t < 0.5 else sb):
            out.append(copy.deepcopy(s))
    return out


def _plan_fills(front, back, pairs, links, t):
    ids = {a.get('ID') for a, _ in pairs}
    ao_map = {b.get('ID'): src for src, b in links.items()}
    ap_map = {}
    fmap = {o.get('ID'): o for o in front.findall('AO')}
    for src, b in links.items():
        for pa, pb in zip(_points(fmap[src]), _points(b)):
            ap_map[pb.get('ID')] = pa.get('ID')
    fr = [r for r in front.findall('FR') if _outer_only_from(r, ids)]
    br = [x for x in (_rename(r, ao_map, ap_map) for r in back.findall('FR')) if _outer_only_from(x, ids)]
    pairs_out, used_f, used_b = [], set(), set()
    sig = lambda r: tuple(_seg_signature(s) for s in r.findall('FS'))
    queue = {}
    for j, r in enumerate(br):
        queue.setdefault(sig(r), []).append(j)
    for i, r in enumerate(fr):
        q = queue.get(sig(r))
        if q:
            j = q.pop(0)
            pairs_out.append((i, j))
            used_f.add(i)
            used_b.add(j)
    kf, kb = {}, {}
    for i, r in enumerate(fr):
        if i not in used_f:
            kf.setdefault(_region_key(r), []).append(i)
    for j, r in enumerate(br):
        if j not in used_b:
            kb.setdefault(_region_key(r), []).append(j)
    for key, fi in kf.items():
        if len(fi) == 1 and len(kb.get(key, [])) == 1:
            pairs_out.append((fi[0], kb[key][0]))
            used_f.add(fi[0])
            used_b.add(kb[key][0])
    out = []
    for i, j in pairs_out:
        region = _interp_region(fr[i], br[j], t)
        if region is not None:
            out.append(region)
    if t < 1:
        out += [copy.deepcopy(fr[i]) for i in range(len(fr)) if i not in used_f]
    else:
        out += [copy.deepcopy(br[j]) for j in range(len(br)) if j not in used_b]
    return [r for r in out if u32(r.get('Color', '0')) >> 24]


def interpolate(front, back, t):
    """Interpolated frame element; t == 0 returns the original front frame."""
    if t <= 0:
        return front
    links = resolve_links(front, back)
    bmap = {o.get('ID'): o for o in back.findall('AO')}
    pairs = []
    for a in _visible_front_objects(front):
        b = links.get(a.get('ID')) or bmap.get(a.get('ID'))
        if b is not None:
            pairs.append((a, b))
    # ASSUMPTION: background colour of an intermediate frame is the front frame's.
    f = E.Element('Frame', dict(front.attrib))
    for layer in front.findall('LayerDef'):
        f.append(copy.deepcopy(layer))
    for a, b in pairs:
        f.append(_interp_object(a, b, t))
    for region in _plan_fills(front, back, pairs, links, t):
        f.append(region)
    return f


def export_frames(root, tween_fps, playback_fps, tweening_enabled=True):
    """Yield (output_index, frame_element, (a, b, t))."""
    frames = sorted(root.findall('Frame'), key=lambda f: int(f.get('Position', '0')))
    plan = timeline(len(frames), tween_fps, playback_fps, tweening_enabled)
    for j, (a, b, t) in enumerate(plan['frames']):
        yield j, (frames[a] if (t <= 0 or a == b) else interpolate(frames[a], frames[b], t)), (a, b, t)
