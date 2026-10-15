"""Checker logic tests against a simulator of the static reading (not app results)."""
import copy
import tempfile
import unittest
from pathlib import Path
import xml.etree.ElementTree as E

from build_frame_command_probe import build
import sfa
from tools import check_frame_commands as cfc


def renumber(root):
    frames = root.findall('Frame')
    for i, f in enumerate(frames):
        f.set('Position', str(i))
    root.set('FrameCount', str(len(frames)))


def paste(root, source_index, after=True, corrupt=None):
    """Same-sequence paste as read statically: AO IDs kept, new point IDs, remaps."""
    frames = root.findall('Frame')
    src = frames[source_index]
    new = copy.deepcopy(src)
    new.set('ID', str(max(int(f.get('ID')) for f in frames) + 1))
    next_pid = max(int(p.get('ID')) for p in root.iter('AP')) + 1
    old_points = {p.get('ID'): p for p in src.iter('AP')}
    mapping = {}
    for p in new.iter('AP'):
        mapping[p.get('ID')] = str(next_pid)
        next_pid += 1
    parsed = cfc.parse_frame(src)
    for p in new.iter('AP'):
        old = p.get('ID')
        root_id, status = cfc.resolve_group_root(old, parsed['points'])
        base = int(old_points[old].get('Flags')) & 0x2f
        flags = (int(mapping[root_id]) << 6) | base | 0x10 if status == 'ok' else base
        p.set('ID', mapping[old])
        p.set('Flags', str(flags))
        for c in p.findall('AC'):
            c.set('ConnPtId', mapping[c.get('ConnPtId')])
    for s in new.iter('FS'):
        for key in ('StartPtId', 'EndPtId'):
            if s.get(key) in mapping:
                s.set(key, mapping[s.get(key)])
    if corrupt == 'keep_point_ids':
        for p in new.iter('AP'):
            inverse = {v: k for k, v in mapping.items()}
            p.set('ID', inverse[p.get('ID')])
            for c in p.findall('AC'):
                c.set('ConnPtId', inverse[c.get('ConnPtId')])
        for s in new.iter('FS'):
            for key in ('StartPtId', 'EndPtId'):
                inverse = {v: k for k, v in mapping.items()}
                if s.get(key) in inverse:
                    s.set(key, inverse[s.get(key)])
    if corrupt == 'raw_flags':
        for p in new.iter('AP'):
            p.set('Flags', old_points[{v: k for k, v in mapping.items()}[p.get('ID')]].get('Flags'))
    if corrupt == 'background':
        new.set('BackgroundColor', '0')
    root.insert(list(root).index(src) + (1 if after else 0), new)
    renumber(root)
    return root


class FrameCommandChecker(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.dir = Path(cls.tmp.name)
        cls.manifest, cls.seed = build(cls.dir)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def write(self, name, root):
        path = self.dir / name
        sfa.write_sfa(root, path)
        return path

    def run_pair(self, after_root):
        before = self.dir / '06_frame_commands_seed.sfa'
        return cfc.compare(before, self.write('after.sfa', after_root))

    def statuses(self, report):
        return {c['name'].split(':')[-1]: c['status'] for c in report['checks']}

    def test_seed_is_valid_and_group_chain_resolves_to_root(self):
        self.assertEqual(sfa.validate(self.seed), [])
        frame = cfc.parse_frame(self.seed.findall('Frame')[0])
        grandchild = next(pid for pid, p in frame['points'].items() if p['ao'] == '22' and p['index'] == 0)
        parent = next(pid for pid, p in frame['points'].items() if p['ao'] == '20' and p['index'] == 0)
        self.assertEqual(cfc.resolve_group_root(grandchild, frame['points']), (parent, 'ok'))
        self.assertLess(max(int(p.get('Flags')) for p in self.seed.iter('AP')), 2 ** 31)

    def test_paste_after_and_before_pass(self):
        for after in (True, False):
            report = self.run_pair(paste(copy.deepcopy(self.seed), 0, after))
            self.assertEqual(report['fail_count'], 0, report['checks'])
            event = next(e for e in report['events'] if e['kind'] == 'paste_same_sequence')
            self.assertEqual(event['side'], 'pasted_after_source' if after else 'pasted_before_source')
            self.assertTrue(event['direction'].startswith('by_point_ids'), event)

    def test_direction_ambiguous_when_export_renumbers_points(self):
        root = paste(copy.deepcopy(self.seed), 0, False)
        offset = {p.get('ID'): str(int(p.get('ID')) + 500000) for p in root.iter('AP')}
        for p in root.iter('AP'):
            p.set('ID', offset[p.get('ID')])
            f = int(p.get('Flags'))
            if f & 0x10:
                p.set('Flags', str((int(offset[str(f >> 6)]) << 6) | (f & 0x3f)))
            for c in p.findall('AC'):
                c.set('ConnPtId', offset[c.get('ConnPtId')])
        for seg in root.iter('FS'):
            for key in ('StartPtId', 'EndPtId'):
                if seg.get(key) in offset:
                    seg.set(key, offset[seg.get(key)])
        report = self.run_pair(root)
        self.assertEqual(report['fail_count'], 0, report['checks'])
        event = next(e for e in report['events'] if e['kind'] == 'paste_same_sequence')
        self.assertEqual(event['direction'], 'ambiguous_best_of_both')

    def test_paste_detects_deviations(self):
        expected = {'keep_point_ids': 'point_ids_new', 'raw_flags': 'flags_remapped_to_root_parent',
                    'background': 'background_kept'}
        for corrupt, name in expected.items():
            report = self.run_pair(paste(copy.deepcopy(self.seed), 1, True, corrupt))
            self.assertEqual(self.statuses(report)[name], 'fail', corrupt)

    def test_empty_insert_and_last_frame_delete(self):
        root = copy.deepcopy(self.seed)
        empty = E.Element('Frame', BackgroundColor=root.get('BackgroundColor'), ID='999')
        for layer in root.find('Frame').findall('LayerDef'):
            empty.append(copy.deepcopy(layer))
        root.insert(list(root).index(root.find('Frame')), empty)
        renumber(root)
        report = self.run_pair(root)
        self.assertEqual(report['fail_count'], 0, report['checks'])
        self.assertEqual(report['events'][0]['kind'], 'empty_frame')

        single = copy.deepcopy(self.seed)
        single.remove(single.findall('Frame')[1])
        renumber(single)
        before = self.write('single.sfa', single)
        recreated = copy.deepcopy(single)
        recreated.remove(recreated.find('Frame'))
        recreated.append(copy.deepcopy(empty))
        renumber(recreated)
        report = cfc.compare(before, self.write('recreated.sfa', recreated))
        self.assertIn('last_frame_delete_recreated_empty_frame0', [e['kind'] for e in report['events']])

    def test_unchanged_pair_reports_no_change(self):
        report = self.run_pair(copy.deepcopy(self.seed))
        self.assertEqual(report['events'], [{'kind': 'no_frame_level_change'}])
        self.assertEqual(report['fail_count'], 0)


if __name__ == '__main__':
    unittest.main()
