import copy
from pathlib import Path
import sys
import unittest
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from stickman_clip import AO0
from stickman_part_thickness import apply_thickness


def fixture():
    root = ET.Element('Sequence', FrameCount='5')
    for i in range(5):
        frame = ET.SubElement(root, 'Frame', Position=str(i))
        for slot in (0, 1):
            for oid in range(1, 12):
                obj = ET.SubElement(frame, 'AO', ID=str(AO0+slot*100+oid), ThicknessScale='2.000', Color='0' if oid == 11 else '-65536')
                ET.SubElement(obj, 'AP', ID=str(i*1000+slot*100+oid), X='10', Y='20', Flags='4')
    scene = dict(rig='stickman-2d-11-v1', start=0, end=4, cuts=[3])
    style = dict(schema=1, rig=scene['rig'], start=0, end=4,
                 tracks=[dict(actor='red', start=1, end=2, feather=2,
                              keys={'1': {'7': 2., '8': 1.5}, '2': {'7': 3., '8': 2.}})])
    return root, scene, style


class TestPartThickness(unittest.TestCase):
    def test_only_selected_object_thickness_changes_and_input_is_immutable(self):
        root, scene, style = fixture()
        before = ET.tostring(root)
        result, changes = apply_thickness(root, scene, style)
        self.assertEqual(ET.tostring(root), before)
        self.assertEqual({c['frame'] for c in changes}, {0, 1, 2})
        for old, new in zip(root.iter(), result.iter()):
            old_at, new_at = dict(old.attrib), dict(new.attrib)
            if old.tag == 'AO':
                old_at.pop('ThicknessScale')
                new_at.pop('ThicknessScale')
            self.assertEqual(old_at, new_at)
        for f in (3, 4):
            self.assertEqual(ET.tostring(root.findall('Frame')[f]), ET.tostring(result.findall('Frame')[f]))

    def test_feather_does_not_cross_cut(self):
        root, scene, style = fixture()
        _, changes = apply_thickness(root, scene, style)
        thigh = {c['frame']: c['after'] for c in changes if c['segment'] == 7}
        self.assertEqual(thigh, {0: 3., 1: 4., 2: 6.})

    def test_keys_interpolate_and_no_style_preserves_full_xml(self):
        root, scene, style = fixture()
        style['tracks'][0].update(start=0, end=2, feather=1,
                                  keys={'0': {'7': 1.}, '2': {'7': 3.}})
        _, changes = apply_thickness(root, scene, style)
        self.assertEqual([c['after'] for c in changes], [4., 6.])
        style['tracks'] = []
        result, changes = apply_thickness(root, scene, style)
        self.assertEqual(ET.tostring(root), ET.tostring(result))
        self.assertEqual(changes, [])

    def test_invalid_hidden_segment_values_and_overlapping_tracks_are_rejected(self):
        root, scene, style = fixture()
        for value in (0., -1., float('nan'), float('inf'), 1e-10):
            with self.subTest(value=value):
                bad = copy.deepcopy(style)
                bad['tracks'][0]['keys']['1']['7'] = value
                with self.assertRaises(ValueError):
                    apply_thickness(root, scene, bad)
        bad = copy.deepcopy(style)
        bad['tracks'][0]['keys'] = {'1': {'11': 2.}, '2': {'11': 2.}}
        with self.assertRaises(ValueError):
            apply_thickness(root, scene, bad)
        style['tracks'].append(copy.deepcopy(style['tracks'][0]))
        with self.assertRaisesRegex(ValueError, '겹친다'):
            apply_thickness(root, scene, style)


if __name__ == '__main__':
    unittest.main()
