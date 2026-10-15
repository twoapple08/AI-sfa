#!/usr/bin/env python3
"""Compare two app-exported SFA files around one timeline frame command.

The expectations come from static AOT reading (docs/AOT-TIMELINE-FRAME-COMMANDS-
TRACE-2026-10-16.md, docs/AOT-GROUP-REPAIR-TRACE-2026-10-15.md). A pass means the
export-visible state is consistent with that reading; it does not prove the
internal DB/root path. Python standard library only (runs in Termux).
"""
import argparse
import difflib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import sfa  # noqa: E402

AO_ATTRS = ('TypeId', 'Color', 'LayerId', 'ThicknessScale', 'ObjectScale',
            'GlowRadius', 'GlowThickness', 'GlowColor', 'GlowAlpha')
GROUP_BIT = 0x10
BASE_MASK = 0x2f


def num(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return value
    return int(number) if number.is_integer() else round(number, 6)


def parse_frame(frame):
    aos, points = [], {}
    for obj in frame.findall('AO'):
        pts = []
        for p in obj.findall('AP'):
            point = {'id': p.get('ID'), 'ao': obj.get('ID'), 'index': int(p.get('Index', '0')),
                     'x': num(p.get('X')), 'y': num(p.get('Y')),
                     'flags': int(p.get('Flags', '0')),
                     'conns': [c.get('ConnPtId') for c in p.findall('AC')]}
            pts.append(point)
            points[point['id']] = point
        aos.append({'id': obj.get('ID'), 'draw_order': num(obj.get('DrawOrder')),
                    'attrs': tuple(num(obj.get(k)) for k in AO_ATTRS), 'points': pts})
    fills = []
    for region in frame.iter('FR'):
        segs = [{'kind': s.get('Kind', '0'), 'obj': s.get('ObjId'),
                 'start': s.get('StartPtId'), 'end': s.get('EndPtId'),
                 'st': num(s.get('StartT')), 'et': num(s.get('EndT')),
                 'contour': num(s.get('Contour', '0'))} for s in region.findall('FS')]
        fills.append({'color': region.get('Color'), 'segs': segs})
    layers = tuple((l.get('ID'), l.get('Name'), l.get('Visible'), l.get('Locked'))
                   for l in frame.findall('LayerDef'))
    return {'id': frame.get('ID'), 'position': int(frame.get('Position', '-1')),
            'bg': frame.get('BackgroundColor'), 'layers': layers,
            'aos': aos, 'points': points, 'fills': fills}


def load(path):
    root = sfa.read_sfa(path)
    frames = sorted((parse_frame(f) for f in root.findall('Frame')),
                    key=lambda f: f['position'])
    return root, frames


def resolve_group_root(pid, points):
    """Current-representation parent walk (ResolveGroupParentId reading).

    Returns (root_id, status). status: 'none' (no group bit), 'ok', 'unresolved',
    'legacy' (old 16-bit token form; not judged here).
    """
    flags = points[pid]['flags']
    if not flags & GROUP_BIT:
        return None, 'none'
    visited, current = {pid}, str(flags >> 6)
    while True:
        if current not in points or current in visited:
            break
        visited.add(current)
        cflags = points[current]['flags']
        if cflags & GROUP_BIT:
            current = str(cflags >> 6)
            continue
        if current != pid and (cflags & 0x2e) == 2:
            return current, 'ok'
        break
    if (flags >> 6) & 0x3ff == 0 and (flags >> 16) & 0xffff:
        return None, 'legacy'
    return None, 'unresolved'


def signature(frame):
    """ID-free content signature used to align frames between exports."""
    def content(ao):
        pts = tuple(sorted((p['index'], p['x'], p['y'], p['flags'] & BASE_MASK,
                            bool(p['flags'] & GROUP_BIT)) for p in ao['points']))
        return (ao['attrs'], pts)
    order = sorted(frame['aos'], key=lambda a: (a['draw_order'], content(a)))
    ordinal = {a['id']: i for i, a in enumerate(order)}
    pref = {pid: (ordinal[p['ao']], p['index']) for pid, p in frame['points'].items()}
    conns, groups = set(), []
    for pid, p in frame['points'].items():
        for target in p['conns']:
            conns.add((pref[pid], pref.get(target)))
        root, status = resolve_group_root(pid, frame['points'])
        if status != 'none':
            groups.append((pref[pid], pref.get(root), status))
    fills = tuple((f['color'], tuple((s['kind'], ordinal.get(s['obj']),
                  pref.get(s['start'], s['start'] if s['start'] in (None, '-1') else '?'),
                  pref.get(s['end'], s['end'] if s['end'] in (None, '-1') else '?'),
                  s['st'], s['et'], s['contour']) for s in f['segs'])) for f in frame['fills'])
    return (frame['bg'], frame['layers'], tuple(content(a) for a in order),
            tuple(sorted(conns, key=repr)), tuple(sorted(groups, key=repr)), fills)


def is_empty(frame):
    return not frame['aos'] and not frame['fills']


def check(name, ok, detail='', status=None):
    return {'name': name, 'status': status or ('pass' if ok else 'fail'), 'detail': detail}


def same_sequence_copy_checks(src, dst):
    """Expectations for a same-sequence paste whose source AO IDs are unique."""
    out = []
    src_ids = [a['id'] for a in src['aos']]
    dst_ids = [a['id'] for a in dst['aos']]
    unique = len(src_ids) == len(set(src_ids))
    out.append(check('source_ao_ids_unique', unique,
                     'fast unstored path applies only when source AO IDs are unique',
                     None if unique else 'info'))
    out.append(check('ao_ids_kept', sorted(src_ids) == sorted(dst_ids),
                     f'source={len(src_ids)} pasted={len(dst_ids)}'))
    by_id = {a['id']: a for a in dst['aos']}
    attr_bad = [a['id'] for a in src['aos']
                if a['id'] in by_id and (a['attrs'], a['draw_order']) !=
                (by_id[a['id']]['attrs'], by_id[a['id']]['draw_order'])]
    out.append(check('ao_attributes_and_draw_order_kept', not attr_bad,
                     f'mismatch AO IDs={attr_bad[:10]}'))
    shared = set(src['points']) & set(dst['points'])
    out.append(check('point_ids_new', not shared, f'shared AP IDs={len(shared)}'))
    dst_by_key = {(p['ao'], p['index']): pid for pid, p in dst['points'].items()}
    mapping = {pid: dst_by_key.get((p['ao'], p['index'])) for pid, p in src['points'].items()}
    unmapped = [pid for pid, target in mapping.items() if target is None]
    out.append(check('points_mapped_by_ao_and_index',
                     not unmapped and len(src['points']) == len(dst['points']),
                     f'unmapped={len(unmapped)} source={len(src["points"])} pasted={len(dst["points"])}'))
    geo_bad = [pid for pid, target in mapping.items() if target and
               (src['points'][pid]['x'], src['points'][pid]['y']) !=
               (dst['points'][target]['x'], dst['points'][target]['y'])]
    out.append(check('point_coordinates_kept', not geo_bad, f'mismatch={len(geo_bad)}'))
    expected_conns = {(mapping[pid], mapping.get(t)) for pid, p in src['points'].items()
                      for t in p['conns'] if mapping[pid] and mapping.get(t)}
    actual_conns = {(pid, t) for pid, p in dst['points'].items() for t in p['conns']}
    out.append(check('connections_remapped', expected_conns == actual_conns,
                     f'missing={len(expected_conns - actual_conns)} extra={len(actual_conns - expected_conns)}'))
    flag_bad, legacy, unresolved_src = [], 0, 0
    for pid, p in src['points'].items():
        target = mapping[pid]
        if not target:
            continue
        base = p['flags'] & BASE_MASK
        root, status = resolve_group_root(pid, src['points'])
        if status == 'legacy':
            legacy += 1
            continue
        if status == 'unresolved':
            unresolved_src += 1
        expected = base
        if status == 'ok' and mapping.get(root):
            expected = (int(mapping[root]) << 6) | (base & 0x3f) | GROUP_BIT
        if dst['points'][target]['flags'] != expected:
            flag_bad.append((pid, p['flags'], dst['points'][target]['flags'], expected))
    out.append(check('flags_remapped_to_root_parent', not flag_bad,
                     f'mismatch={len(flag_bad)} first={flag_bad[:3]} legacy_not_judged={legacy} '
                     f'source_unresolved_group={unresolved_src}'))
    fill_bad = []
    if len(src['fills']) != len(dst['fills']):
        fill_bad.append(f'region count {len(src["fills"])}->{len(dst["fills"])}')
    for i, (a, b) in enumerate(zip(src['fills'], dst['fills'])):
        if a['color'] != b['color'] or len(a['segs']) != len(b['segs']):
            fill_bad.append(f'region {i} color/segment count')
            continue
        for j, (s, t) in enumerate(zip(a['segs'], b['segs'])):
            if s['kind'] == '1':
                # Ring: same AO/contour; endpoint/T representation is reported only.
                if (t['kind'], t['obj'], t['contour']) != ('1', s['obj'], s['contour']):
                    fill_bad.append(f'region {i} ring seg {j}')
                continue
            want = {k: (s[k] if s[k] in (None, '-1') else (mapping.get(s[k]) or '-1'))
                    for k in ('start', 'end')}
            if (t['kind'], t['obj'], t['start'], t['end'], t['st'], t['et'], t['contour']) != \
               (s['kind'], s['obj'], want['start'], want['end'], s['st'], s['et'], s['contour']):
                fill_bad.append(f'region {i} seg {j}')
    out.append(check('fill_regions_remapped', not fill_bad, '; '.join(fill_bad[:5])))
    rings = [(t['start'], t['end'], t['st'], t['et']) for f in dst['fills']
             for t in f['segs'] if t['kind'] == '1']
    if rings:
        out.append(check('ring_segment_form', True, f'observed (start,end,st,et)={rings[:3]}', 'info'))
    out.append(check('layers_kept', src['layers'] == dst['layers'],
                     f'source={src["layers"]} pasted={dst["layers"]}'))
    out.append(check('background_kept', src['bg'] == dst['bg'],
                     f'source={src["bg"]} pasted={dst["bg"]}'))
    return out


def pick_source(index, frames, sigs, inserted):
    """Prefer an unchanged frame with identical content, then the same AO ID set."""
    ids = sorted(a['id'] for a in frames[index]['aos'])
    candidates = [i for i, f in enumerate(frames) if i != index and i not in inserted and
                  (sigs[i] == sigs[index] or sorted(a['id'] for a in f['aos']) == ids)]
    if not candidates:
        return None, []
    candidates.sort(key=lambda i: (sigs[i] != sigs[index], abs(i - index), i))
    return candidates[0], candidates


def compare(before_path, after_path):
    _, before = load(before_path)
    after_root, after = load(after_path)
    report = {'before': str(before_path), 'after': str(after_path),
              'frames': {'before': len(before), 'after': len(after)}, 'checks': [], 'events': []}
    checks = report['checks']
    checks.append(check('after_validates', not sfa.validate(after_root),
                        '; '.join(sfa.validate(after_root)[:5])))
    checks.append(check('after_positions_contiguous',
                        [f['position'] for f in after] == list(range(len(after)))))
    sig_b = [signature(f) for f in before]
    sig_a = [signature(f) for f in after]
    matcher = difflib.SequenceMatcher(a=sig_b, b=sig_a, autojunk=False)
    inserted, deleted, aligned = [], [], []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == 'equal':
            aligned += list(zip(range(i1, i2), range(j1, j2)))
        else:
            deleted += list(range(i1, i2))
            inserted += list(range(j1, j2))
    renumbered = sum(1 for i, j in aligned if
                     sorted(before[i]['points']) != sorted(after[j]['points']))
    checks.append(check('unchanged_frame_ids_stable_between_exports', renumbered == 0,
                        f'aligned={len(aligned)} renumbered_point_sets={renumbered}', 'info'))
    inserted_set = set(inserted)
    for j in inserted:
        frame = after[j]
        if is_empty(frame):
            neighbours = [after[k] for k in (j - 1, j + 1) if 0 <= k < len(after) and k not in inserted_set]
            same = [n['position'] for n in neighbours if n['layers'] == frame['layers']]
            report['events'].append({'kind': 'empty_frame', 'after_position': j,
                                     'background': frame['bg'], 'layers': frame['layers']})
            checks.append(check(f'empty_frame@{j}_layers_from_neighbour', bool(same) or not neighbours,
                                f'neighbour positions with identical LayerDef={same}'))
            continue
        before_frame_ids = {f['id'] for f in before}
        if frame['id'] in before_frame_ids:
            # Alignment may mark an old copy as inserted when several frames share content;
            # frame IDs persist between exports, so prefer the one content-equal unseen ID.
            unseen = [k for k, f in enumerate(after) if sig_a[k] == sig_a[j]
                      and f['id'] not in before_frame_ids]
            if len(unseen) == 1:
                inserted_set = (inserted_set - {j}) | {unseen[0]}
                j = unseen[0]
        source, candidates = pick_source(j, after, sig_a, inserted_set)
        if source is None:
            report['events'].append({'kind': 'unmatched_new_frame', 'after_position': j})
            checks.append(check(f'new_frame@{j}_source_found', False,
                                'no unchanged frame with the same AO ID set', 'info'))
            continue
        # Content-equal source/copy: decide which one is new by frame IDs, then point IDs.
        new_index, direction = j, 'content_differs'
        src_old, new_old = after[source]['id'] in before_frame_ids, after[j]['id'] in before_frame_ids
        if sig_a[source] == sig_a[j] and src_old != new_old:
            # Frame IDs persist between exports of one project; the new frame's ID is unseen.
            if new_old:
                source, new_index = j, source
            direction = 'by_frame_ids'
        elif sig_a[source] == sig_a[j] and not src_old and not new_old and \
                after[source]['id'].isdigit() and after[j]['id'].isdigit():
            # frame._id is AUTOINCREMENT in the app schema: the newest row has the largest ID.
            if int(after[source]['id']) > int(after[j]['id']):
                source, new_index = j, source
            direction = 'by_highest_frame_id'
        elif sig_a[source] == sig_a[j]:
            known = [set(f['points']) for f in before]
            src_known = set(after[source]['points']) in known
            new_known = set(after[j]['points']) in known
            if new_known and not src_known:
                source, new_index, direction = j, source, 'by_point_ids_swapped'
            elif src_known and not new_known:
                direction = 'by_point_ids'
            else:
                forward = same_sequence_copy_checks(after[source], after[j])
                backward = same_sequence_copy_checks(after[j], after[source])
                if sum(c['status'] == 'fail' for c in backward) < sum(c['status'] == 'fail' for c in forward):
                    source, new_index = j, source
                direction = 'ambiguous_best_of_both'
        report['events'].append({'kind': 'paste_same_sequence', 'after_position': new_index,
                                 'source_after_position': source,
                                 'other_candidates': [c for c in candidates[1:] if c != new_index],
                                 'direction': direction,
                                 'side': 'pasted_after_source' if source < new_index else 'pasted_before_source'})
        for item in same_sequence_copy_checks(after[source], after[new_index]):
            item['name'] = f'paste@{new_index}:{item["name"]}'
            checks.append(item)
    for i in deleted:
        report['events'].append({'kind': 'removed_or_changed_frame', 'before_position': i})
    if len(before) == 1 and deleted and len(after) == 1 and is_empty(after[0]):
        report['events'].append({'kind': 'last_frame_delete_recreated_empty_frame0'})
    if not inserted and not deleted:
        report['events'].append({'kind': 'no_frame_level_change'})
    report['fail_count'] = sum(c['status'] == 'fail' for c in checks)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('before')
    parser.add_argument('after')
    parser.add_argument('--json', help='write full report JSON here')
    args = parser.parse_args(argv)
    report = compare(args.before, args.after)
    if args.json:
        Path(args.json).write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding='utf-8')
    print(f"frames {report['frames']['before']} -> {report['frames']['after']}")
    for event in report['events']:
        print('event', json.dumps(event, ensure_ascii=False))
    for item in report['checks']:
        print(f"[{item['status']}] {item['name']} {item['detail']}".rstrip())
    print(f"fail={report['fail_count']} (pass = export-visible consistency, not internal-path proof)")
    return 1 if report['fail_count'] else 0


if __name__ == '__main__':
    sys.exit(main())
