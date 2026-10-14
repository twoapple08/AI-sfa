"""Read-only boundary statistics; does not render or infer app interpolation."""
import argparse
from collections import Counter
import hashlib
import json
import xml.etree.ElementTree as ET
import zipfile


def audit(path, pairs):
    wanted = {n for pair in pairs for n in pair}
    frames = {}
    with zipfile.ZipFile(path) as archive:
        xml = [n for n in archive.namelist() if n.lower().endswith('.xml')]
        if len(xml) != 1:
            raise ValueError('Expected exactly one XML member')
        with archive.open(xml[0]) as source:
            parser = ET.iterparse(source, events=('start', 'end'))
            _, root = next(parser)
            for event, frame in parser:
                if event != 'end' or frame.tag != 'Frame':
                    continue
                number = int(frame.get('Position')) + 1
                if number in wanted:
                    frames[number] = ET.fromstring(ET.tostring(frame))
                frame.clear()
                root.clear()
    rows = []
    for left, right in pairs:
        ends = [frames[left], frames[right]]
        objects = [{ao.get('ID'): ao for ao in f.findall('AO')} for f in ends]
        common = objects[0].keys() & objects[1].keys()
        row = {'boundary': [left, right], 'ao_count': [len(o) for o in objects],
               'common_ao_count': len(common), 'ends': []}
        for frame, ao in zip(ends, objects):
            fills = frame.findall('FR')
            eligible = [fr for fr in fills if list(fr.iter('FS')) and
                        all(s.get('ObjId') in common for s in fr.iter('FS'))]
            glow = [i for i in common if float(ao[i].get('GlowAlpha', '0')) > 0
                    and float(ao[i].get('GlowRadius', '0')) > 0]
            below = [i for i in glow if ao[i].get('TypeId') == '3' and
                     ao[i].findall('AP') and
                     all(float(p.get('Y')) > 100 for p in ao[i].findall('AP'))]
            row['ends'].append({
                'background_argb': frame.get('BackgroundColor'),
                'common_base_alpha_positive': sum(
                    int(ao[i].get('Color', '0')) >> 24 > 0 for i in common),
                'common_glow_radius_alpha_positive': len(glow),
                'common_glow_curves_control_hull_below_output': len(below),
                'fill_count': len(fills),
                'fills_referencing_only_common_objects': len(eligible),
                'eligible_fill_colors': dict(Counter(fr.get('Color') for fr in eligible)),
            })
        row['changed_common_ao_attributes'] = dict(Counter(
            key for i in common for key in objects[0][i].attrib.keys() | objects[1][i].attrib.keys()
            if objects[0][i].get(key) != objects[1][i].get(key)))
        rows.append(row)
    digest = hashlib.sha256()
    with open(path, 'rb') as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(chunk)
    return {'source_sha256': digest.hexdigest(),
            'scope': 'XML statistics only; no renderer/interpolation verification; no coordinates exported',
            'boundaries': rows}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('sfa')
    parser.add_argument('--pairs', nargs='+', required=True, help='1-based pairs, e.g. 38:39')
    args = parser.parse_args()
    pairs = [tuple(map(int, pair.split(':'))) for pair in args.pairs]
    if any(len(pair) != 2 or min(pair) < 1 for pair in pairs):
        parser.error('Pairs must contain two positive frame numbers')
    print(json.dumps(audit(args.sfa, pairs), ensure_ascii=False, indent=2))
