"""Small controlled probes for app execution; generated results are unverified."""
import copy
import json
from pathlib import Path
import xml.etree.ElementTree as E
from zipfile import ZipFile, ZIP_DEFLATED
from build_feature_probes import primitive, argb
import sfa

ROOT = Path(__file__).resolve().parent
BG = argb(255, 24, 24, 24)
WHITE = argb(255, 255, 255, 255)
RED = argb(255, 235, 65, 55)
BLUE = argb(255, 50, 125, 240)
CYAN = argb(255, 40, 195, 205)


def frame(bg=BG):
    f = E.Element('Frame', BackgroundColor=bg)
    E.SubElement(f, 'LayerDef', ID='0', Name='Layer 1', Visible='true', Locked='false')
    return f


def polygon(first, points, color='0'):
    objects = [primitive(first+i, 1, [p, points[(i+1) % len(points)]], color)
               for i, p in enumerate(points)]
    for i, obj in enumerate(objects):
        end = obj.findall('AP')[1]
        start = objects[(i+1) % len(objects)].findall('AP')[0]
        E.SubElement(end, 'AC', ConnPtId=start.get('ID'))
        E.SubElement(start, 'AC', ConnPtId=end.get('ID'))
    return objects


def fill(objects, color, contour=0, reverse=False):
    region = E.Element('FR', Color=color)
    add_contour(region, objects, contour, reverse)
    return region


def add_contour(region, objects, contour, reverse=False):
    for obj in (list(reversed(objects)) if reverse else objects):
        a, b = obj.findall('AP')
        E.SubElement(region, 'FS', Kind='0', ObjId=obj.get('ID'),
                     StartPtId=(b if reverse else a).get('ID'),
                     EndPtId=(a if reverse else b).get('ID'),
                     StartT='1.0' if reverse else '0.0',
                     EndT='0.0' if reverse else '1.0', Contour=str(contour))


def hole_frame(mode):
    f = frame()
    marker = polygon(10, [(23,20),(27,20),(27,80),(23,80)])
    outer = polygon(20, [(10, 20), (40, 20), (40, 80), (10, 80)])
    inner = polygon(30, [(20, 38), (30, 38), (30, 62), (20, 62)])
    region = fill(outer, CYAN)
    if mode:
        add_contour(region, inner, 1, reverse=mode == 2)
    f.extend([*marker, *outer, *inner, fill(marker,RED), region])
    return f


def fill_order(reverse=False):
    f = frame()
    a = polygon(20, [(25, 20), (60, 20), (60, 65), (25, 65)])
    b = polygon(30, [(40, 35), (75, 35), (75, 80), (40, 80)])
    regions = [fill(a, RED), fill(b, BLUE)]
    f.extend([*a, *b, *(reversed(regions) if reverse else regions)])
    return f


def stroke_order(reverse=False, with_fill=False):
    f = frame()
    red = primitive(10, 1, [(30, 25), (70, 75)], RED)
    blue = primitive(20, 1, [(30, 75), (70, 25)], BLUE)
    red.set('ThicknessScale', '6.0'); blue.set('ThicknessScale', '6.0')
    if reverse:
        red.set('DrawOrder', '30')
    f.extend([red, blue])
    if with_fill:
        square = polygon(40, [(38, 30), (62, 30), (62, 70), (38, 70)])
        f.extend([*square, fill(square, CYAN)])
    return f


def glow_frame(radius=12, thickness=20, alpha=255, base_alpha=255,
               color_alpha=255, scale=1, count=1):
    f = frame()
    for i in range(count):
        obj = primitive(10+i, 1, [(35, 50), (65, 50)], argb(base_alpha, 240, 140, 40))
        obj.set('GlowRadius', str(radius)); obj.set('GlowThickness', str(thickness))
        obj.set('GlowAlpha', str(alpha)); obj.set('GlowColor', argb(color_alpha, 50, 160, 255))
        obj.set('ObjectScale', str(scale)); f.append(obj)
    return f


def tween_frame(case, phase):
    f = frame()
    f.append(primitive(1, 1, [(8, 35), (8, 65)], argb(255, 100, 100, 100)))
    odd = phase % 2
    if case == 'same_id_move':
        x = 35 if not odd else 65
        f.append(primitive(10, 2, [(x, 40), (x, 60)], WHITE))
    elif case == 'presence':
        if odd:
            f.append(primitive(10, 2, [(50, 40), (50, 60)], WHITE))
    elif case == 'new_id_same_pose':
        f.append(primitive(10 if not odd else 20, 2, [(50, 40), (50, 60)], WHITE))
    elif case in ('fill_presence', 'missing_boundary', 'fill_color'):
        objects = polygon(20, [(35, 30), (65, 30), (50, 75)],
                          WHITE if case == 'fill_presence' else '0')
        region = fill(objects, BLUE if case == 'fill_color' and odd else RED)
        if case == 'missing_boundary' and odd:
            # A fill cannot contain a dangling reference. Remove FR with its boundary.
            kept_points = {p.get('ID') for obj in objects[:2] for p in obj.findall('AP')}
            for obj in objects[:2]:
                for p in obj.findall('AP'):
                    for connection in list(p.findall('AC')):
                        if connection.get('ConnPtId') not in kept_points:
                            p.remove(connection)
            f.extend(objects[:2])
        else:
            f.extend(objects)
            if case != 'fill_presence' or odd:
                f.append(region)
    elif case == 'base_alpha':
        f.append(primitive(10, 2, [(50, 40), (50, 60)],
                           argb(0 if odd else 255, 255, 255, 255)))
    return f


def identify(source, index, section):
    f = copy.deepcopy(source)
    f.set('ID', str(900000+index)); f.set('Position', str(index))
    objects = {o.get('ID'): str(section*1000+int(o.get('ID'))) for o in f.findall('AO')}
    points = {p.get('ID'): str(90000000+index*1000+j) for j, p in enumerate(f.iter('AP'))}
    for obj in f.findall('AO'):
        obj.set('ID', objects[obj.get('ID')])
        obj.set('DrawOrder', str(section*1000+int(obj.get('DrawOrder'))))
    for p in f.iter('AP'): p.set('ID', points[p.get('ID')])
    for ac in f.iter('AC'): ac.set('ConnPtId', points[ac.get('ConnPtId')])
    for seg in f.iter('FS'):
        seg.set('ObjId', objects[seg.get('ObjId')])
        for key in ('StartPtId', 'EndPtId'):
            if seg.get(key) in points: seg.set(key, points[seg.get(key)])
    return f


def sequence(name, entries):
    root = E.Element('Sequence', Name=name, HeightWidthRatio='0.5625', RatioX='16',
                     RatioY='9', FrameCount=str(len(entries)), BackgroundColor=BG)
    for i, (source, section) in enumerate(entries):
        root.append(identify(source, i, section))
    return root


def build(destination):
    dest = Path(destination); dest.mkdir(parents=True, exist_ok=True)
    manifest = {'status': 'generated; app execution pending', 'files': []}
    outputs = {}
    def put(name, entries, fps, cases):
        root = sequence(name, entries); outputs[name] = root
        sfa.write_sfa(root, dest/(name+'.sfa'))
        manifest['files'].append({'name': name+'.sfa', 'original_frames': len(entries),
                                 'fps': {'tween_fps': fps[0], 'playback_fps': fps[1]},
                                 'expected_output_frames': len(entries)*max(1, fps[0]/fps[1]),
                                 'expected_seconds': len(entries)/fps[1], 'cases': cases})

    baseline = hole_frame(1)
    circle = primitive(50, 2, [(65, 35), (65, 65)], WHITE)
    baseline.append(circle)
    region = E.SubElement(baseline, 'FR', Color=BLUE)
    E.SubElement(region, 'FS', Kind='1', ObjId='50')
    glow = primitive(60, 1, [(78, 30), (78, 70)], '0')
    for key, value in {'GlowRadius':'12','GlowThickness':'20','GlowAlpha':'128',
                       'GlowColor':argb(64,50,160,255)}.items(): glow.set(key,value)
    baseline.append(glow)
    put('00_roundtrip', [(baseline, 1)]*24, (24,24), ['Static import/roundtrip sentinel; no user edits'])

    fill_cases = [('outer_only',hole_frame(0)), ('inner_contour',hole_frame(1)),
                  ('inner_reversed',hole_frame(2)), ('red_then_blue_FR',fill_order()),
                  ('blue_then_red_FR',fill_order(True)), ('red_then_blue_AO',stroke_order()),
                  ('blue_then_red_AO',stroke_order(True)), ('fill_and_strokes',stroke_order(with_fill=True))]
    put('01_fill_order', [(f,i+1) for i,(_,f) in enumerate(fill_cases) for _ in range(24)],
        (24,24), [{'seconds':[i,i+1], 'case':name} for i,(name,_) in enumerate(fill_cases)])

    glow_cases = [('no_glow', {'alpha':0}), ('radius_4',{'radius':4}), ('reference_radius_12',{}),
                  ('radius_28',{'radius':28}), ('thickness_10',{'thickness':10}),
                  ('thickness_40',{'thickness':40}), ('alpha_64',{'alpha':64}),
                  ('alpha_128',{'alpha':128}), ('base_alpha_0',{'base_alpha':0}),
                  ('glow_color_alpha_64',{'color_alpha':64}), ('object_scale_2',{'scale':2}),
                  ('two_coincident_objects',{'count':2})]
    put('02_glow', [(glow_frame(**kwargs),i+1) for i,(_,kwargs) in enumerate(glow_cases) for _ in range(24)],
        (24,24), [{'seconds':[i,i+1], 'case':name, 'change':kwargs} for i,(name,kwargs) in enumerate(glow_cases)])

    tween_cases = ['same_id_move','presence','new_id_same_pose','fill_presence',
                   'missing_boundary','base_alpha','fill_color']
    put('03_tween', [(tween_frame(name,phase),i+1) for i,name in enumerate(tween_cases)
                    for phase in range(4) for _ in range(6)], (24,12),
        [{'seconds':[i*2,(i+1)*2], 'case':name, 'phase_frames':6} for i,name in enumerate(tween_cases)])

    ui = E.parse(ROOT/'examples/default_stickman.xml').getroot().find('Frame')
    ui = copy.deepcopy(ui)
    for obj in ui.findall('AO'):
        obj.set('Color', RED if obj.get('ID') in ('5','6') else BLUE if obj.get('ID') in ('3','4') else argb(255,70,70,70))
        for p in obj.findall('AP'): p.set('X',str(float(p.get('X'))-15))
    orange = argb(255,240,140,40)
    ui.extend([primitive(50,1,[(70,30),(85,30)],orange),
               primitive(60,1,[(70,55),(85,55)],orange)])
    put('04_ui_seed', [(ui,1)], (24,24), ['One frame: red viewer-right arm, blue viewer-left arm; two disconnected orange lines'])

    link_a = frame(); link_b = frame()
    link_a.append(primitive(10,2,[(35,40),(35,60)],WHITE))
    link_b.append(primitive(20,2,[(65,40),(65,60)],WHITE))
    put('05_link_seed', [(link_a,1)]*12+[(link_b,1)]*12, (24,12),
        ['24 originals: frames1-12 left,13-24 right; different AO IDs; no TweenLink stored'])
    (dest/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    return manifest, outputs


def package(destination):
    dest = Path(destination)
    path = dest/'AI-sfa-priority-tests-v2.zip'
    guides = {'PRIORITY-PROBE-USER-GUIDE.md':'START-HERE-KO.md',
              'DEVELOPER-REQUEST-KO.txt':'DEVELOPER-REQUEST-KO.txt',
              'PRIORITY-PROBE-RETURN-TEMPLATE.txt':'RETURN-CHECKLIST-KO.txt'}
    with ZipFile(path, 'w', ZIP_DEFLATED) as archive:
        for source in sorted(dest.glob('*.sfa')):
            archive.write(source, source.name)
        archive.write(dest/'manifest.json', 'manifest.json')
        for source, name in guides.items():
            archive.write(ROOT/'docs'/source, name)
    return path


if __name__ == '__main__':
    manifest, _ = build(ROOT/'examples/priority_probes_v2')
    package(ROOT/'examples/priority_probes_v2')
    print(f"Built {len(manifest['files'])} files; app execution pending")
