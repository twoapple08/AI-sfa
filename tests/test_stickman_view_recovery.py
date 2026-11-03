import json
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from stickman_view_recovery import match_face, recover_key_views, transfer_face_box
from stickman_face_evidence import load_evidence, digest
from stickman_scene import rig_layout_fingerprint


class TestViewRecovery(unittest.TestCase):
    def inputs(self):
        k = np.ones((1, 23, 3))*5
        k[0, :5, :2] = [[300, 200], [290, 180], [310, 180], [270, 200], [330, 200]]
        k[0, [5, 6], :2] = [[250, 300], [350, 300]]
        k[0, [11, 12], :2] = [[270, 450], [330, 450]]
        k[0, [13, 14], :2] = [[240, 550], [360, 550]]
        k[0, [15, 16], :2] = [[230, 650], [370, 650]]
        j = {n: np.array([p], float) for n, p in dict(neck=[300, 300], pelvis=[300, 450],
             head_t=[300, 180], head_b=[300, 300], elb_l=[200, 350], wri_l=[180, 400],
             elb_r=[400, 350], wri_r=[420, 400], kne_l=[240, 550], kne_r=[360, 550],
             ank_l=[230, 650], ank_r=[370, 650]).items()}
        return k, j, np.array([160.]), [(0, 0)], np.full((1, 3), np.nan), np.ones((1, 23)), (0, 1151, 63, 719)

    def test_normal_full_body_and_fast_kick_remain_untouched(self):
        args = self.inputs()
        args[0][0, 15, :2] = [1200, 150]  # 실제로 뻗은 긴 다리를 길이/속도 상한으로 자르지 않는다.
        out, scale, visible, events = recover_key_views(*args)
        for n in args[1]:
            np.testing.assert_array_equal(out[n], args[1][n])
        np.testing.assert_array_equal(scale, args[2])
        self.assertTrue(visible.all())

    def test_independent_large_face_repairs_collapsed_body_without_new_layout(self):
        k, j, scale, spans, faces, support, bounds = self.inputs()
        k[0, [5, 6], 1] = 680
        k[0, [11, 12], 1] = 714
        faces[0] = [320, 360, 480]
        before = rig_layout_fingerprint()
        out, s, visible, events = recover_key_views(k, j, scale, spans, faces, support, bounds)
        np.testing.assert_array_equal((out['head_t']+out['head_b'])/2, [[320, 360]])
        self.assertAlmostEqual(np.linalg.norm(out['head_t']-out['head_b']), 480)
        self.assertGreater(out['pelvis'][0, 1], bounds[3])
        self.assertEqual(np.flatnonzero(visible[0]).tolist(), [0, 1])
        self.assertEqual(events[0]['mode'], 'large_face_cropped_body')
        self.assertEqual(before, rig_layout_fingerprint())

    def test_visible_ankle_survives_censored_parent_in_lower_body_view(self):
        k, j, scale, spans, faces, support, bounds = self.inputs()
        k[0, :13, 1] = 80
        k[0, [13, 14], :2] = [[480, 65], [205, 358]]
        k[0, [15, 16], :2] = [[682, 441], [154, 492]]
        out, s, visible, events = recover_key_views(k, j, scale, spans, faces, support, bounds)
        np.testing.assert_array_equal(out['ank_l'], [[682, 441]])
        self.assertLess(out['kne_l'][0, 1], bounds[2])
        self.assertLess(out['pelvis'][0, 1], bounds[2])
        self.assertLess(out['head_b'][0, 1], bounds[2])
        self.assertEqual(np.flatnonzero(visible[0]).tolist(), [6, 7, 8, 9])
        self.assertEqual(events[0]['mode'], 'upper_body_outside_top')

    def test_unrelated_or_other_colored_face_does_not_validate_body(self):
        k = self.inputs()[0][0]
        own = np.zeros((720, 1152), bool)
        own[150:250, 250:350] = True
        other = np.zeros_like(own)
        self.assertIsNone(match_face([dict(box=[900, 100, 50, 50], score=.9)], k, own, other))
        self.assertIsNotNone(match_face([dict(box=[250, 150, 100, 100], score=.9)], k, own, other))
        self.assertIsNone(match_face([dict(box=[250, 150, 100, 100], score=.9)], k, other, own))
        self.assertIsNone(match_face([dict(box=[250, 150, 100, 100], score=.4)], k, own, other))

    def test_missing_face_alone_never_erases_a_person(self):
        args = self.inputs()
        args[0][0, :5, :2] = [300, 220]
        args[1]['head_t'][0] = [300, 100]
        out, _, visible, events = recover_key_views(*args)
        self.assertTrue(visible.all())
        np.testing.assert_array_equal(out['head_t'], args[1]['head_t'])
        self.assertTrue(any(e['mode'] == 'needs_review' for e in events))

    def test_ankle_on_background_uses_nearby_supported_observation_not_wrong_fallback(self):
        k, j, scale, _, _, support, bounds = self.inputs()
        k[0, :13, 1] = 80
        k[0, [13, 14], :2] = [[480, 65], [205, 358]]
        k[0, [15, 16], :2] = [[682, 441], [300, 492]]
        k = np.repeat(k, 3, axis=0)
        k[1, 16, :2] = [154, 492]  # 모델이 몸 대신 그림자에 찍은 고신뢰 점
        support = np.repeat(support, 3, axis=0)
        support[1, 16] = 0
        j = {n: np.repeat(v, 3, axis=0) for n, v in j.items()}
        j['ank_r'][1] = [154, 492]
        out, _, _, events = recover_key_views(k, j, np.repeat(scale, 3),
            [(0, 0), (1, 1), (2, 2)], np.full((3, 3), np.nan), support, bounds)
        np.testing.assert_array_equal(out['ank_r'][1], [300, 492])
        self.assertTrue(any('ank_r' in e.get('inferred_leg_nodes', []) for e in events))

    def test_short_face_detector_gap_does_not_toggle_back_to_tiny_head(self):
        k, j, scale, _, _, support, bounds = self.inputs()
        k[0, [5, 6], 1] = 680
        k[0, [11, 12], 1] = 714
        k = np.repeat(k, 3, axis=0)
        j = {n: np.repeat(v, 3, axis=0) for n, v in j.items()}
        faces = np.array([[320, 360, 480], [np.nan]*3, [320, 360, 480]])
        out, _, _, events = recover_key_views(k, j, np.repeat(scale, 3),
            [(0, 0), (1, 1), (2, 2)], faces, np.repeat(support, 3, axis=0), bounds)
        np.testing.assert_allclose(np.linalg.norm(out['head_t']-out['head_b'], axis=1), [480]*3)
        self.assertTrue(events[1]['face_box_inferred'])

    def test_face_transfer_needs_consistent_2d_landmark_shape(self):
        old = self.inputs()[0][0]
        new = old.copy()
        new[:5, :2] = old[:5, :2]*1.2+[40, -10]
        face = np.array([300., 200., 120.])
        np.testing.assert_allclose(transfer_face_box(old, new, face), [400, 230, 144])
        new[:5, :2] = old[:5, :2]*.1  # 작은 손에 생긴 가짜 얼굴로 큰 머리를 축소하지 않는다.
        self.assertIsNone(transfer_face_box(old, new, face))

    def test_explicit_lower_body_view_does_not_restore_arms_when_detector_reappears(self):
        k,j,scale,spans,faces,support,bounds=self.inputs()
        k[0,:7,1]=70
        k[0,[5,6],0]=[200,300]
        out,s,visible,events=recover_key_views(k,j,scale,spans,faces,support,bounds,
            forced_lower=np.array([True]))
        self.assertFalse(visible[0,:1].any())
        self.assertFalse(visible[0,2:6].any())
        self.assertTrue(visible[0,6:].all())
        np.testing.assert_array_equal(out['pelvis'],[[300.,450.]])
        self.assertLess(out['neck'][0,1],bounds[2])
        self.assertLess(out['neck'][0,0],out['pelvis'][0,0])  # 보이는 몸통 기울기는 남긴다.
        np.testing.assert_array_equal(s,scale)  # 잘린 길이를 거리/굵기로 오인하지 않는다.
        self.assertEqual(events[0]['mode'],'lower_body_top')

    def test_evidence_rejects_source_mismatch_and_missing_frame(self):
        with tempfile.TemporaryDirectory() as d:
            video, evidence = Path(d)/'video', Path(d)/'faces.json'
            video.write_bytes(b'source')
            data = dict(schema=1, source_sha256=digest(video), size=[1152, 720], frames={'5': []})
            evidence.write_text(json.dumps(data))
            load_evidence(evidence, video, [5], 1152, 720)
            with self.assertRaises(ValueError):
                load_evidence(evidence, video, [5, 6], 1152, 720)
            video.write_bytes(b'other')
            with self.assertRaises(ValueError):
                load_evidence(evidence, video, [5], 1152, 720)


if __name__ == '__main__':
    unittest.main()
