"""Seed for app timeline frame-command checks (APP-V3); app results are pending."""
import json
from pathlib import Path
import xml.etree.ElementTree as E
from build_feature_probes import argb
import sfa

ROOT = Path(__file__).resolve().parent
BG0 = argb(255, 24, 24, 24)
BG1 = argb(255, 20, 40, 90)
CYAN = argb(255, 40, 195, 205)
BLUE = argb(255, 50, 125, 240)
ORANGE = argb(255, 250, 150, 30)
WHITE = argb(255, 255, 255, 255)
GROUP_BIT = 0x10


def line(oid, pid, points, color, layer=0, **attrs):
    obj = E.Element('AO', ID=str(oid), TypeId='1', Color=color, LayerId=str(layer),
                    DrawOrder=str(oid), ThicknessScale='1.0', ObjectScale='1.0',
                    GlowRadius='0', GlowThickness='20', GlowColor=WHITE, GlowAlpha='0')
    for key, value in attrs.items():
        obj.set(key, value)
    for i, (x, y) in enumerate(points):
        E.SubElement(obj, 'AP', ID=str(pid + i), Flags='3' if i == 0 else '9',
                     Index=str(i), X=str(x), Y=str(y))
    return obj


def connect(a, b):
    E.SubElement(a, 'AC', ConnPtId=b.get('ID'))
    E.SubElement(b, 'AC', ConnPtId=a.get('ID'))


def group_child(point, parent):
    base = int(point.get('Flags')) & 0x2f
    point.set('Flags', str((int(parent.get('ID')) << 6) | (base & 0x3f) | GROUP_BIT))


def make_frame(index, dx, bg):
    pid = 10000 + index * 1000  # keeps group Flags (pid << 6) below 2**31
    f = E.Element('Frame', BackgroundColor=bg, ID=str(800000 + index), Position=str(index))
    E.SubElement(f, 'LayerDef', ID='0', Name='Layer 1', Visible='true', Locked='false')
    E.SubElement(f, 'LayerDef', ID='1', Name='Layer 2', Visible='true', Locked='false')
    corners = [(12 + dx, 25), (32 + dx, 25), (22 + dx, 60)]
    tri = [line(10 + i, pid + 10 * i, [corners[i], corners[(i + 1) % 3]], '0') for i in range(3)]
    for i in range(3):
        connect(tri[i].findall('AP')[1], tri[(i + 1) % 3].findall('AP')[0])
    # Group: AO20 is the parent line, AO21 a direct child, AO22 a child of AO21's point
    # (a chain that the static reading resolves to AO20's point on copy).
    parent = line(20, pid + 100, [(45 + dx, 25), (45 + dx, 60)], ORANGE)
    child = line(21, pid + 110, [(52 + dx, 25), (52 + dx, 60)], ORANGE)
    grandchild = line(22, pid + 120, [(59 + dx, 25), (59 + dx, 60)], ORANGE, layer=1)
    p0, c0, g0 = parent.find('AP'), child.find('AP'), grandchild.find('AP')
    connect(p0, c0)
    connect(c0, g0)
    group_child(c0, p0)
    group_child(g0, c0)
    circle = E.Element('AO', ID='30', TypeId='2', Color=WHITE, LayerId='1', DrawOrder='30',
                       ThicknessScale='1.5', ObjectScale='1.0', GlowRadius='10',
                       GlowThickness='20', GlowColor=argb(64, 50, 160, 255), GlowAlpha='128')
    E.SubElement(circle, 'AP', ID=str(pid + 300), Flags='3', Index='0', X=str(78 + dx), Y='35')
    E.SubElement(circle, 'AP', ID=str(pid + 301), Flags='9', Index='1', X=str(78 + dx), Y='60')
    f.extend([*tri, parent, child, grandchild, circle])
    region = E.SubElement(f, 'FR', Color=CYAN)
    for obj in tri:
        a, b = obj.findall('AP')
        E.SubElement(region, 'FS', Kind='0', ObjId=obj.get('ID'), StartPtId=a.get('ID'),
                     EndPtId=b.get('ID'), StartT='0.0', EndT='1.0', Contour='0')
    ring = E.SubElement(f, 'FR', Color=BLUE)
    E.SubElement(ring, 'FS', Kind='1', ObjId='30')
    return f


def build(destination):
    dest = Path(destination)
    dest.mkdir(parents=True, exist_ok=True)
    root = E.Element('Sequence', Name='06_frame_commands_seed', HeightWidthRatio='0.5625',
                     RatioX='16', RatioY='9', FrameCount='2', BackgroundColor=BG0)
    root.append(make_frame(0, 0, BG0))
    root.append(make_frame(1, 8, BG1))
    sfa.write_sfa(root, dest / '06_frame_commands_seed.sfa')
    manifest = {
        'status': 'generated; app execution pending',
        'file': '06_frame_commands_seed.sfa',
        'fps': {'tween_fps': 24, 'playback_fps': 24},
        'frames': 2,
        'purpose': 'Timeline copy/paste/insert/delete export checks; see docs/APP-V3-FRAME-COMMANDS-PROTOCOL-2026-10-16.md',
        'checker': 'python tools/check_frame_commands.py BEFORE.sfa AFTER.sfa',
        'seed_note': 'Group flags are generator-encoded; import may repair them. Compare app exports, not this seed.',
    }
    (dest / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=1) + '\n',
                                        encoding='utf-8')
    return manifest, root


if __name__ == '__main__':
    build(ROOT / 'examples/frame_commands_v3')
    print('Built 06_frame_commands_seed.sfa; app execution pending')
