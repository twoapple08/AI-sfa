from pathlib import Path
import sys
import unittest
import xml.etree.ElementTree as ET

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from stickman_clip import person_aos
from stickman_scene import JOINTS
from stickman_limb_surface import contour, apply_surface, audit_surface


def fixture():
    root = ET.Element('Sequence', HeightWidthRatio='1', FrameCount='2')
    for i in range(2):
        frame = ET.SubElement(root, 'Frame', Position=str(i))
        for slot, color in enumerate(('blue', 'red')):
            x = slot*100
            pose = {n: np.array([x+20., 25.]) for n in JOINTS}
            pose.update(head_t=np.array([x+20., 5.]), pelvis=np.array([x+20., 50.]),
                        kne_r=np.array([x+50., 50.]), ank_r=np.array([x+80., 50.]))
            frame.extend(ET.fromstring('<Frame>'+person_aos(i, slot, pose, lambda p: p, color)+'</Frame>'))
    scene = dict(rig='stickman-2d-11-v1', start=0, end=1, cuts=[])
    style = dict(schema=1, representation='filled-limb-v1', rig=scene['rig'], start=0, end=1,
                 tracks=[dict(actor='red', start=0, end=1, segments=[7, 8], keys={'0': [4, 6, 8], '1': [8, 6, 4]})])
    return root, scene, style


class TestLimbSurface(unittest.TestCase):
    def test_contour_is_closed_and_width_continuous_through_knee(self):
        curves = contour([[0, 0], [50, 0], [100, 0]], [4, 6, 8])
        self.assertEqual(curves.shape, (10, 3, 2))
        for i in range(10):
            np.testing.assert_array_equal(curves[i, 2], curves[(i+1)%10, 0])
        # 하나의 옆면 곡선이므로 무릎에서 선 굵기가 끊기지 않는다.
        midpoint = .25*curves[0, 0]+.5*curves[0, 1]+.25*curves[0, 2]
        np.testing.assert_allclose(midpoint, [50, 6])

    def test_base_is_preserved_and_full_surface_graph_has_unique_frame_points(self):
        root, scene, style = fixture()
        original = ET.tostring(root)
        result, records = apply_surface(root, scene, style, 100, 0)
        self.assertEqual(ET.tostring(root), original)
        report, base = audit_surface(result, scene, style, 100, 0)
        self.assertEqual(report['errors'], [])
        self.assertEqual(ET.tostring(base), original)
        self.assertEqual(len(records), 2)
        frames = result.findall('Frame')
        self.assertFalse({p.get('ID') for p in frames[0].iter('AP')} & {p.get('ID') for p in frames[1].iter('AP')})
        self.assertEqual([a.get('ID') for a in frames[0].findall('AO')], [a.get('ID') for a in frames[1].findall('AO')])

    def test_disconnected_surface_is_rejected(self):
        root, scene, style = fixture()
        result, _ = apply_surface(root, scene, style, 100, 0)
        point = next(p for p in result.iter('AP') if int(p.get('ID')) >= 20_000_000 and p.find('AC') is not None)
        point.set('Y', '999')
        report, _ = audit_surface(result, scene, style, 100, 0)
        self.assertTrue(report['errors'])

    def test_bent_chain_or_invalid_radii_do_not_silently_change_pose(self):
        with self.assertRaisesRegex(ValueError, '직선'):
            contour([[0, 0], [50, 20], [100, 0]], [4, 6, 8])
        for radii in ([0, 1, 2], [1, float('nan'), 2], [10, .01, 10]):
            with self.subTest(radii=radii), self.assertRaises(ValueError):
                contour([[0, 0], [50, 0], [100, 0]], radii)


if __name__ == '__main__':
    unittest.main()
