import json
from pathlib import Path
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
import zipfile

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import stickman_clip as sc
from stickman_finalize import finalize
from stickman_quality import audit, digest, read_sfa
from stickman_scene import JOINTS


def clip():
    root = ET.Element('Sequence', HeightWidthRatio='1', FrameCount='5')
    for i in range(5):
        frame = ET.SubElement(root, 'Frame', Position=str(i))
        for slot, color in enumerate(('blue', 'red')):
            pose = {n: np.array([20. + slot * 50, 50.]) for n in JOINTS}
            pose.update(head_t=np.array([20. + slot * 50, 10.]), head_b=np.array([20. + slot * 50, 30.]),
                        neck=np.array([20. + slot * 50, 30.]), pelvis=np.array([20. + slot * 50, 70.]))
            # 실제 빠른 동작도 허용하고 화면 밖 좌표도 유효하다.
            pose['wri_r'] = np.array([200. if i == 2 else 10., 50.])
            frame.extend(ET.fromstring('<Frame>' + sc.person_aos(i, slot, pose, lambda p: p, color) + '</Frame>'))
    return root


def scene():
    return dict(schema=1, rig='stickman-2d-11-v1', start=100, end=104, cuts=[])


class TestQuality(unittest.TestCase):
    def test_fast_motion_and_outside_coordinates_are_review_candidates(self):
        report, _, _ = audit(clip(), scene(), width=100, crop_y=0)
        self.assertEqual(report['errors'], [])
        self.assertEqual(report['unique_points'], 220)
        self.assertEqual(report['review_candidates'][0]['frame'], 102)
        self.assertTrue(report['review_candidates'][0]['review_only'])
        cut_scene = scene()
        cut_scene['cuts'] = [102]
        report, _, _ = audit(clip(), cut_scene, width=100, crop_y=0)
        self.assertNotIn(102, [r['frame'] for r in report['review_candidates']])
        self.assertNotIn(101, [r['frame'] for r in report['review_candidates']])

    def test_cross_actor_connection_and_split_coordinate_are_rejected(self):
        root = clip()
        point = next(p for p in root.iter('AP') if p.find('AC') is not None)
        point.find('AC').set('ConnPtId', str(sc.PT0 + 101))
        report, _, _ = audit(root, scene(), width=100, crop_y=0)
        self.assertTrue(any('인물 밖 연결' in e for e in report['errors']))
        root = clip()
        point = next(p for p in root.iter('AP') if p.find('AC') is not None)
        point.set('X', '999')
        report, _, _ = audit(root, scene(), width=100, crop_y=0)
        self.assertTrue(any('좌표 분리' in e for e in report['errors']))

    def test_white_head_and_confirmed_contact_are_checked(self):
        root = clip()
        root.find('Frame/FR').set('Color', '-65536')
        spec = scene()
        spec['contacts'] = [dict(id='block', start=100, end=100,
                                 members=[['blue', 'wri_l']], target=['red', 'ank_r'])]
        report, _, _ = audit(root, spec, width=100, crop_y=0)
        self.assertTrue(any('흰 머리' in e for e in report['errors']))
        self.assertTrue(any('접촉 잔차' in e for e in report['errors']))

    def test_coincident_legs_are_flagged_without_being_automatically_moved(self):
        root = clip()
        frame = root.find('Frame')
        for oid, ys in ((7, (70, 80)), (8, (80, 90)), (9, (70, 80)), (10, (80, 90))):
            obj = next(a for a in frame.findall('AO') if int(a.get('ID')) == sc.AO0 + oid)
            for point, y in zip(obj.findall('AP'), ys):
                point.set('Y', str(y))
        before = ET.tostring(root)
        report, _, _ = audit(root, scene(), width=100, crop_y=0)
        self.assertTrue(any(r['frame'] == 100 and r['actor'] == 'blue' and r['part'] == 'leg' for r in report['overlap_candidates']))
        self.assertEqual(ET.tostring(root), before)
        self.assertEqual(report['errors'], [])

    def test_finalize_uses_frozen_input_and_does_not_change_rig(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            base, out, config = tmp/'base.sfa', tmp/'out.sfa', tmp/'scene.json'
            with zipfile.ZipFile(base, 'w') as z:
                z.writestr('base.xml', ET.tostring(clip()))
            original = base.read_bytes()
            spec = scene()
            spec['tracks'] = [dict(actor='red', start=102, end=102, feather=1,
                                  keys={'102': {'kne_l': [80, 90], 'ank_l': [90, 120]}})]
            config.write_text(json.dumps(spec))
            report = finalize(base, config, out, 100, 0, expected_sha=digest(base))
            self.assertEqual(report['errors'], [])
            self.assertEqual(base.read_bytes(), original)
            before, after = read_sfa(base).findall('Frame'), read_sfa(out).findall('Frame')
            for i in (0, 1, 3, 4):
                self.assertEqual(ET.tostring(before[i]), ET.tostring(after[i]))
            self.assertNotEqual(ET.tostring(before[2]), ET.tostring(after[2]))
            with self.assertRaisesRegex(ValueError, '해시'):
                finalize(base, config, out, 100, 0, expected_sha='wrong')
            with self.assertRaisesRegex(ValueError, '덮어쓸'):
                finalize(base, config, base, 100, 0)


if __name__ == '__main__':
    unittest.main()
