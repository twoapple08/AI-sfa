#!/usr/bin/env python3
"""Sample-derived Stick Fighter SFA tools. Python standard library only."""
import argparse
import copy
import html
import json
import math
import os
from pathlib import Path
import tempfile
import xml.etree.ElementTree as ET
from zipfile import ZipFile, ZIP_DEFLATED, BadZipFile

MAX_XML = 32 * 1024 * 1024


def read_sfa(path):
    with ZipFile(path) as archive:
        entries = [e for e in archive.infolist() if e.filename.lower().endswith('.xml')]
        if len(entries) != 1:
            raise ValueError('SFA must contain exactly one XML entry')
        entry = entries[0]
        if entry.file_size > MAX_XML:
            raise ValueError('XML exceeds 32 MiB limit')
        with archive.open(entry) as stream:
            raw = stream.read(MAX_XML + 1)
    if len(raw) > MAX_XML:
        raise ValueError('XML exceeds 32 MiB limit')
    # Strip NULs for declaration detection in UTF-16/32 as well as UTF-8.
    declarations = raw.replace(b'\x00', b'').upper()
    if b'<!DOCTYPE' in declarations or b'<!ENTITY' in declarations:
        raise ValueError('DTD/entity declarations are not supported')
    root = ET.fromstring(raw)
    if root.tag != 'Sequence':
        raise ValueError('Expected Sequence root')
    return root


def validate(root):
    errors = []
    frames = root.findall('Frame')
    if not frames:
        errors.append('No frames')
    if root.get('FrameCount') != str(len(frames)):
        errors.append('FrameCount does not match frame elements')
    for key in ('RatioX', 'RatioY'):
        try:
            if not math.isfinite(float(root.get(key, 'nan'))) or float(root.get(key)) <= 0:
                raise ValueError()
        except (ValueError, TypeError):
            errors.append(f'Invalid {key}')
    frame_ids = set()
    for index, frame in enumerate(frames):
        prefix = f'Frame {index}: '
        if frame.get('Position') != str(index):
            errors.append(prefix + 'Position must be sequential from zero')
        fid = frame.get('ID')
        if fid is None or fid in frame_ids:
            errors.append(prefix + 'missing/duplicate frame ID')
        frame_ids.add(fid)
        for tag in ('AO', 'AP', 'LayerDef'):
            nodes = list(frame.iter(tag))
            ids = [n.get('ID') for n in nodes]
            if None in ids or len(ids) != len(set(ids)):
                errors.append(prefix + f'missing/duplicate {tag} ID')
        points = {p.get('ID') for p in frame.iter('AP')}
        objects = {a.get('ID') for a in frame.findall('AO')}
        layers = {l.get('ID') for l in frame.findall('LayerDef')}
        for a in frame.findall('AO'):
            if a.get('LayerId') not in layers:
                errors.append(prefix + 'unknown LayerId')
        for p in frame.iter('AP'):
            for axis in ('X', 'Y'):
                try:
                    if not math.isfinite(float(p.get(axis, 'nan'))):
                        raise ValueError()
                except (ValueError, TypeError):
                    errors.append(prefix + f'invalid {axis} coordinate')
        for c in frame.iter('AC'):
            if c.get('ConnPtId') not in points:
                errors.append(prefix + 'dangling ConnPtId')
        for s in frame.iter('FS'):
            if s.get('ObjId') not in objects:
                errors.append(prefix + 'dangling fill ObjId')
            for key in ('StartPtId', 'EndPtId'):
                # Real app exports use -1 for boundary positions and omit
                # endpoints for Kind=1. Preserve these observed representations.
                ref = s.get(key)
                if ref == '-1' or (ref is None and s.get('Kind') == '1'):
                    continue
                if ref not in points:
                    errors.append(prefix + f'dangling fill {key}')
    return errors


def write_sfa(root, path):
    errors = validate(root)
    if errors:
        raise ValueError('; '.join(errors))
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = ET.tostring(root, encoding='utf-8', xml_declaration=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent, suffix='.tmp')
    os.close(fd)
    try:
        with ZipFile(temporary, 'w', ZIP_DEFLATED, compresslevel=9) as archive:
            archive.writestr(path.stem + '.xml', raw)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def summary(root):
    return {
        'sequence': dict(root.attrib),
        'frames': [{
            'id': f.get('ID'), 'position': f.get('Position'),
            'objects': len(f.findall('AO')), 'points': len(list(f.iter('AP'))),
            'layers': [dict(l.attrib) for l in f.findall('LayerDef')],
            'type_ids': sorted({a.get('TypeId', '') for a in f.findall('AO')}),
            'fills': len(list(f.iter('FR'))),
            'tween_links': [dict(e.attrib) for e in f.iter('TweenLink')],
        } for f in root.findall('Frame')],
        'validation_errors': validate(root),
        'timing_note': 'No playback/tween FPS field identified in supplied samples.',
    }


def make_wave(template, count=48):
    """Animate the supplied default stickman; do not assume arbitrary custom rigs."""
    if not 5 <= count <= 1000:
        raise ValueError('frames must be between 5 and 1000')
    errors = validate(template)
    if errors:
        raise ValueError('; '.join(errors))
    source = template.find('Frame')
    objects = source.findall('AO')
    points = [p for a in objects for p in a.findall('AP')]
    if len(objects) != 10 or len(points) != 20 or [a.get('TypeId') for a in objects] != ['2'] + ['1'] * 9:
        raise ValueError('Wave demo requires the supplied default stickman topology')
    # Geometry check ensures an unrelated ten-object custom rig is not animated.
    expected = [(50,5),(50,20),(50,20),(50,40),(45.78125,30),(50,20),
                (41.5625,40),(45.78125,30),(54.21875,30),(50,20),
                (58.4375,40),(54.21875,30),(50,40),(45.78125,52),
                (45.78125,52),(45.78125,62),(50,40),(54.21875,52),
                (54.21875,52),(54.21875,62)]
    if any(abs(float(p.get('X'))-x)>1e-6 or abs(float(p.get('Y'))-y)>1e-6
           for p,(x,y) in zip(points, expected)):
        raise ValueError('Wave demo requires unchanged 01_base geometry')
    root = copy.deepcopy(template)
    for child in list(root):
        if child.tag == 'Frame':
            root.remove(child)
    root.set('Name', 'AI_sfa_wave_test')
    root.set('FrameCount', str(count))
    for i in range(count):
        frame = copy.deepcopy(source)
        frame.set('ID', str(100000 + i))
        frame.set('Position', str(i))
        remap = {}
        for j, p in enumerate(frame.iter('AP')):
            remap[p.get('ID')] = str(1000000 + i * 20 + j)
        for p in frame.iter('AP'):
            p.set('ID', remap[p.get('ID')])
        for c in frame.iter('AC'):
            c.set('ConnPtId', remap[c.get('ConnPtId')])
        for s in frame.iter('FS'):
            for key in ('StartPtId', 'EndPtId'):
                s.set(key, remap[s.get(key)])
        # Angles in physical canvas space; stored X/Y use separate percentages.
        t = i / (count - 1)
        ramp = min(1.0, t / 0.22, (1-t) / 0.22)
        ramp = ramp * ramp * (3 - 2 * ramp)
        shoulder = (50.0, 20.0)
        ratio = float(root.get('RatioY')) / float(root.get('RatioX'))
        rest_angle = math.degrees(math.atan2(10, 7.5))
        upper_angle = math.radians(rest_angle - (rest_angle + 25) * ramp)
        lower_angle = math.radians(rest_angle - (rest_angle + 80) * ramp + 22 * math.sin(t * math.tau * 3) * ramp)
        length = math.hypot(4.21875 / ratio, 10)
        elbow = (shoulder[0] + length * math.cos(upper_angle) * ratio,
                 shoulder[1] + length * math.sin(upper_angle))
        wrist = (elbow[0] + length * math.cos(lower_angle) * ratio,
                 elbow[1] + length * math.sin(lower_angle))
        arm = frame.findall('AO')
        for p, xy in ((arm[4][0], elbow), (arm[5][1], elbow), (arm[5][0], wrist)):
            p.set('X', str(xy[0])); p.set('Y', str(xy[1]))
        root.append(frame)
    return root


def color(value):
    number = int(value) & 0xffffffff
    return f'#{number & 0xffffff:06x}', ((number >> 24) & 255) / 255


def frame_svg(root, frame):
    """Schematic preview, not an exact reproduction of the Android renderer."""
    width, height = 960.0, 960.0 * float(root.get('RatioY')) / float(root.get('RatioX'))
    def xy(p):
        return float(p.get('X')) * width / 100, float(p.get('Y')) * height / 100
    bg, alpha = color(frame.get('BackgroundColor', root.get('BackgroundColor', '-1')))
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}">',
             f'<rect width="100%" height="100%" fill="{bg}" fill-opacity="{alpha}"/>']
    # Observed layer order is used as an approximation until app validation.
    layers = frame.findall('LayerDef')
    objects = frame.findall('AO')
    for layer in layers:
        if layer.get('Visible') == 'false':
            continue
        for a in sorted((o for o in objects if o.get('LayerId') == layer.get('ID')),
                        key=lambda o: int(o.get('DrawOrder', '0'))):
            pts = [xy(p) for p in a.findall('AP')]
            rgb, opacity = color(a.get('Color', '-16777216'))
            stroke = height * 0.003 * float(a.get('ThicknessScale', '1'))
            style = f'fill="none" stroke="{rgb}" stroke-opacity="{opacity}" stroke-width="{stroke}" stroke-linecap="round"'
            kind = a.get('TypeId')
            if kind == '1' and len(pts) == 2:
                (x1,y1),(x2,y2) = pts
                parts.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" {style}/>')
            elif kind == '2' and len(pts) == 2:
                (x1,y1),(x2,y2) = pts
                radius = math.hypot(x2-x1,y2-y1)/2
                parts.append(f'<circle cx="{(x1+x2)/2}" cy="{(y1+y2)/2}" r="{radius}" {style}/>')
            elif kind == '3' and len(pts) == 3:
                (x1,y1),(cx,cy),(x2,y2) = pts
                parts.append(f'<path d="M {x1} {y1} Q {cx} {cy} {x2} {y2}" {style}/>')
    parts.append('</svg>')
    return ''.join(parts)


def preview(root, path, playback_fps=24, tween_fps=24):
    if not (1 <= playback_fps <= 240 and 1 <= tween_fps <= 240):
        raise ValueError('FPS must be between 1 and 240')
    errors = validate(root)
    if errors:
        raise ValueError('; '.join(errors))
    frames = [frame_svg(root, f) for f in root.findall('Frame')]
    # SVGs contain only numeric values and generated color strings, no imported markup.
    payload = json.dumps(frames).replace('<', '\\u003c')
    title = html.escape(root.get('Name', 'SFA'))
    page = f'''<!doctype html><html lang="ko"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{title}</title>
<style>body{{font-family:system-ui;background:#17191f;color:#eee;margin:24px}}main{{max-width:1000px;margin:auto}}svg{{width:100%;background:white}}button,input{{margin:8px}}p{{line-height:1.6}}input[type=range]{{width:60%}}</style>
<main><h1>{title}</h1><p>구조 확인용 미리보기 · 채우기/글로우/정확한 선 굵기 및 앱 트위닝은 미지원</p>
<div id="canvas"></div><button id="play">재생/정지</button><input id="seek" aria-label="프레임" type="range" min="0" max="{len(frames)-1}" value="0"><output id="status"></output>
<p>원본 재생속도: {playback_fps} FPS · 목표 트위닝: {tween_fps} FPS.<br>
이 미리보기는 원본 프레임만 재생합니다. FPS 설정은 SFA에 기록하지 않습니다.</p></main>
<script>const frames={payload};const canvas=document.getElementById('canvas'),seek=document.getElementById('seek'),status=document.getElementById('status');let current=0,running=false,start=0;
function draw(){{canvas.innerHTML=frames[current];seek.value=current;status.textContent=(current+1)+' / '+frames.length;}}draw();
seek.oninput=()=>{{current=Number(seek.value);running=false;draw();}};
document.getElementById('play').onclick=()=>{{running=!running;start=performance.now()-current*1000/{playback_fps};}};
function tick(now){{if(running){{current=Math.floor((now-start)*{playback_fps}/1000)%frames.length;draw();}}requestAnimationFrame(tick);}}requestAnimationFrame(tick);
</script></html>'''
    Path(path).write_text(page, encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    for name in ('inspect', 'validate'):
        p = sub.add_parser(name); p.add_argument('input')
    p = sub.add_parser('roundtrip', help='Preserve XML data and repackage as SFA')
    p.add_argument('input'); p.add_argument('output')
    p = sub.add_parser('wave', help='Create a default-stickman wave compatibility test')
    p.add_argument('input'); p.add_argument('output'); p.add_argument('--frames', type=int, default=48)
    p = sub.add_parser('preview', help='Create a standalone schematic HTML preview')
    p.add_argument('input'); p.add_argument('output')
    p.add_argument('--playback-fps', type=float, default=24)
    p.add_argument('--tween-fps', type=float, default=24)
    args = parser.parse_args()
    try:
        if hasattr(args, 'output'):
            if Path(args.input).resolve() == Path(args.output).resolve():
                raise ValueError('Input and output must be different files')
            if Path(args.output).exists():
                raise ValueError('Output already exists; choose a new filename')
        root = read_sfa(args.input)
        if args.command == 'inspect':
            print(json.dumps(summary(root), ensure_ascii=False, indent=2))
        elif args.command == 'validate':
            errors = validate(root)
            if errors:
                raise ValueError('; '.join(errors))
            print('OK: structural checks passed (app compatibility not yet verified)')
        elif args.command == 'roundtrip':
            write_sfa(root, args.output)
        elif args.command == 'wave':
            write_sfa(make_wave(root, args.frames), args.output)
        else:
            preview(root, args.output, args.playback_fps, args.tween_fps)
    except (ValueError, OSError, ET.ParseError, KeyError, BadZipFile) as exc:
        parser.exit(1, f'Error: {exc}\n')


if __name__ == '__main__':
    main()
