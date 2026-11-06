import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import sfa_event_review as R
import event_context as C

ROOT = Path(__file__).resolve().parents[1]


class SfaEventReviewTests(unittest.TestCase):
    def setUp(self):
        self.event = json.loads((ROOT / 'data/research/anime_smear_event_2026-11-06.json').read_text())
        self.annotations = dict(image_size=[100, 100], source_sha256=self.event['source']['sha256'],
            frames=[dict(source_index=1392, points_px=[[10, 10], [30, 30], [60, 50]]),
                    dict(source_index=1393, points_px=[[10, 10], [20, 20], [35, 30]])])
        self.context = C.create(self.event, 0, [1392, 1393])

    def test_roundtrip_geometry_and_connected_roles(self):
        root, points = R.build(self.annotations, 'observed')
        root = ET.fromstring(ET.tostring(root))
        report = R.inspect(root, self.context)
        self.assertEqual(report['unique_point_ids'], 8)
        self.assertFalse(report['app_editing_verified'])
        for frame, expected in zip(root.findall('Frame'), points):
            aos = frame.findall('AO')
            actual = [aos[0].findall('AP')[0], aos[0].findall('AP')[1], aos[1].findall('AP')[1]]
            self.assertEqual([[float(p.get('X')), float(p.get('Y'))] for p in actual], expected)

    def test_asset_edit_invalidates_old_context_binding(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder)
            records = R.create_review(self.annotations, self.event, output)
            path = output / 'observed.sfa'
            self.assertTrue(R.verify(path, records['observed'])['all_connections_resolve'])
            root, _ = R.build(self.annotations, 'observed')
            root.find('.//AP').set('X', '99')
            with zipfile.ZipFile(path, 'w') as z:
                z.writestr('review.xml', ET.tostring(root))
            with self.assertRaises(ValueError): R.verify(path, records['observed'])

    def test_context_edit_invalidates_binding(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder)
            records = R.create_review(self.annotations, self.event, output)
            manifest = copy.deepcopy(records['observed'])
            manifest['context']['source_indices'].reverse()
            with self.assertRaises(ValueError): R.verify(output / 'observed.sfa', manifest)

    def test_bad_structure_is_rejected(self):
        for mode in ('shared_point', 'missing_object', 'dangling', 'no_joint'):
            root, _ = R.build(self.annotations, 'observed')
            f = root.findall('Frame')
            if mode == 'shared_point': f[1].find('.//AP').set('ID', f[0].find('.//AP').get('ID'))
            elif mode == 'missing_object': f[0].remove(f[0].findall('AO')[1])
            elif mode == 'dangling': f[0].find('.//AC').set('ConnPtId', '99999')
            else: f[0].findall('AO')[1].find('AP').set('Flags', '9')
            with self.subTest(mode=mode), self.assertRaises(ValueError): R.inspect(root, self.context)

    def test_source_or_frame_mismatch_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            bad = copy.deepcopy(self.annotations); bad['source_sha256'] = '0' * 64
            with self.assertRaises(ValueError): R.create_review(bad, self.event, Path(folder))
        root, _ = R.build(self.annotations, 'observed')
        with self.assertRaises(ValueError): R.inspect(root, C.slice_context(self.context, 0, 1))

    def test_tip_extension_preserves_axes_and_joint_roles(self):
        root, _ = R.build(self.annotations, 'observed')
        extended = R.extend_to_tips(root, [[65, 55], [40, 35]], [100, 100])
        report = R.inspect(extended, self.context, R.OBJECT_IDS + ['4560009'])
        self.assertEqual(report['objects_per_frame'], 3)
        self.assertEqual(report['unique_point_ids'], 12)
        for old, new in zip(root.findall('Frame'), extended.findall('Frame')):
            for a, b in zip(old.findall('AO'), new.findall('AO')[:2]):
                self.assertEqual(a.attrib, b.attrib)
                for pa, pb in zip(a.findall('AP'), b.findall('AP')):
                    self.assertEqual(pa.attrib, pb.attrib)
        with self.assertRaises(ValueError): R.extend_to_tips(root, [[65, 55]], [100, 100])

    def test_knee_to_heel_is_one_line_then_turns_to_tip(self):
        root, _ = R.build(self.annotations, 'observed')
        heels, tips = [[62, 52], [37, 32]], [[70, 55], [45, 35]]
        out = R.extend_to_tips(root, tips, [100, 100], heels=heels)
        self.assertEqual(R.inspect(out, self.context, R.OBJECT_IDS + ['4560009'])['objects_per_frame'], 3)
        for i, (before, after) in enumerate(zip(root.findall('Frame'), out.findall('Frame'))):
            old, new = before.findall('AO'), after.findall('AO')
            self.assertEqual(ET.tostring(old[0]), ET.tostring(new[0]))
            self.assertEqual(old[1].find('AP').attrib, new[1].find('AP').attrib)
            p = new[1].findall('AP')[1]; q, t = new[2].findall('AP')
            self.assertEqual([float(p.get(k)) for k in ('X', 'Y')], heels[i])
            self.assertEqual([q.get(k) for k in ('X', 'Y')], [p.get(k) for k in ('X', 'Y')])
            self.assertEqual([float(t.get(k)) for k in ('X', 'Y')], tips[i])


if __name__ == '__main__':
    unittest.main()
