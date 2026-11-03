import sys
import unittest
from pathlib import Path
import xml.etree.ElementTree as ET

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from stickman_limb_view import measure_single_shin, partial_pose, associate_two_shins
from stickman_clip import person_aos
from stickman_quality import audit


class TestLimbView(unittest.TestCase):
    def test_blank_frame_is_not_manufactured_into_a_limb(self):
        with self.assertRaises(ValueError):
            measure_single_shin(np.full((240, 320, 3), 255, 'uint8'), 'red', 0, 240)

    def test_white_gap_does_not_drop_the_lower_foot_component(self):
        image = np.full((240, 320, 3), 255, 'uint8')
        cv2.rectangle(image, (130, 0), (150, 100), (0, 0, 180), -1)
        cv2.rectangle(image, (125, 165), (210, 210), (0, 0, 180), -1)
        entry, end, report = measure_single_shin(image, 'red', 0, 240)
        self.assertLess(abs(entry[0]-140), 20)
        self.assertGreater(end[1], 150)  # 위쪽 연결 성분만 남겨 발을 지우지 않는다.
        self.assertTrue(report['interpretation'])

    def test_two_dimensional_branch_assignment_preserves_both_fast_strides(self):
        rows = [dict(entry=[x, 0], end=[x, 200]) for x in (10, 1000, 20, 990, 30, 980)]
        before = [dict(entry=r['entry'][:], end=r['end'][:]) for r in rows]
        self.assertEqual(associate_two_shins(rows), [0, 1, 0, 1, 0, 1])
        self.assertEqual(rows, before)  # 가지 이름만 대응하며 빠른 관측의 위치/길이는 자르지 않는다.

    def example(self):
        pose = partial_pose([140, 0], [90, 180], 80, 8)
        text = ('<Sequence HeightWidthRatio="1" FrameCount="1"><Frame ID="5000" Position="0" BackgroundColor="-1">'
                '<LayerDef ID="0"/>'+person_aos(0, 1, pose, lambda p: p, 'red', visible_segments=[8])+'</Frame></Sequence>')
        scene = dict(schema=1, rig='stickman-2d-11-v1', start=0, end=0, cuts=[], contacts=[],
                     partials=[dict(actor='red', start=0, end=0, visible_segments=[8])])
        return ET.fromstring(text), scene

    def test_partial_keeps_fixed_editable_rig_and_missing_person_is_an_error(self):
        root, scene = self.example()
        report, _, _ = audit(root, scene, width=100, crop_y=0)
        self.assertEqual(report['errors'], [])
        self.assertEqual(len(root.findall('Frame/AO')), 11)
        self.assertEqual(sum(p.get('Flags') == '3' for p in root.iter('AP')), 1)
        self.assertEqual(len(root.findall('Frame/FR')), 0)
        for node in list(root.find('Frame')):
            if node.tag == 'AO':
                root.find('Frame').remove(node)
        report, _, _ = audit(root, scene, width=100, crop_y=0)
        self.assertTrue(any('부분 인물 누락' in error for error in report['errors']))

    def test_visibility_plan_never_suppresses_a_broken_connection(self):
        root, scene = self.example()
        plan = [dict(actor='red', start=0, end=0, visible_segments=[8])]
        scene['partials'] = []
        report, _, _ = audit(root, scene, width=100, crop_y=0, visibility_plan=plan)
        self.assertEqual(report['errors'], [])
        root.find('.//AC').set('ConnPtId', '-1')
        report, _, _ = audit(root, scene, width=100, crop_y=0, visibility_plan=plan)
        self.assertTrue(report['errors'])


if __name__ == '__main__':
    unittest.main()
