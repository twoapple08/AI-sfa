import os
import sys
import unittest

import cv2
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))
from stickman_image_keys import color_patch, match_patches, segments_from_matches, align_limb_pairs
from stickman_projection import projected_joints
from rtmw_to_stickman_2d import OBS


class TestImageKeys(unittest.TestCase):
    def test_same_drawing_with_camera_translation_and_noisy_pose(self):
        image = np.full((320, 480, 3), 155, np.uint8)
        cv2.rectangle(image, (160, 80), (225, 190), (180, 80, 35), -1)
        cv2.circle(image, (193, 55), 25, (210, 120, 55), -1)
        for a, b in [((160, 100), (115, 155)), ((225, 100), (265, 150)),
                     ((175, 190), (155, 265)), ((215, 190), (240, 260))]:
            cv2.line(image, a, b, (200, 100, 40), 15)
        cv2.line(image, (170, 90), (212, 180), (20, 20, 20), 3)
        k = np.tile([193., 150., 5.], (23, 1))
        k[:4, :2] = [[115, 30], [265, 30], [115, 265], [265, 265]]
        shift = np.array([19., 4.])
        moved = cv2.warpAffine(image, np.float32([[1, 0, shift[0]], [0, 1, shift[1]]]),
                               (480, 320), borderValue=(155, 155, 155))
        noisy = k.copy()
        noisy[:, :2] += shift
        noisy[13:17, :2] += [[30, -40], [-20, 30], [-35, 20], [30, -20]]
        match = match_patches(color_patch(image, k, 'blue'), color_patch(moved, noisy, 'blue'), moved)
        segments, _ = segments_from_matches([10, 11], [(10, 10), (11, 11)], [match])
        self.assertEqual(segments, [(10, 11)])  # 관절이 튀어도 같은 그림을 새 포즈로 가르지 않는다.
        np.testing.assert_array_equal(match['translation'], shift)

    def test_unknown_match_and_explicit_boundary(self):
        same = dict(ncc=.99, mae=.01)
        different = dict(ncc=.2, mae=.2)
        segs, _ = segments_from_matches([10, 11, 12, 13], [(10, 10), (11, 13)],
                                       [None, same, different], key_starts=[12])
        self.assertEqual(segs, [(10, 10), (11, 11), (12, 12), (13, 13)])
        with self.assertRaises(ValueError):
            segments_from_matches([10, 11], [(10, 11)], [])

    def paired_legs(self):
        k = np.zeros((2, 23, 3))
        k[:, :, 2] = 5
        k[0, [11, 13, 15], :2] = [[-4, 0], [-10, 10], [-10, 20]]
        k[0, [12, 14, 16], :2] = [[4, 0], [10, 10], [10, 20]]
        k[1] = k[0]
        k[1, [11, 13, 15]] = k[0, [12, 14, 16]]
        k[1, [12, 14, 16]] = k[0, [11, 13, 15]]
        return k

    def test_side_exchange_does_not_collapse_held_pose_average(self):
        k = self.paired_legs()
        original = k.copy()
        aligned, _, events = align_limb_pairs(k, np.ones((2, 23, 2)), [(0, 1)], np.ones(2) * 20)
        self.assertEqual(float(k[:, 13, 0].mean()), 0.)
        np.testing.assert_allclose(aligned[:, 13, 0], -10)
        np.testing.assert_allclose(aligned[:, 14, 0], 10)
        np.testing.assert_array_equal(k, original)
        self.assertTrue(any(e['within_key'] and e['part'] == 'leg' for e in events))

    def test_partial_observation_does_not_invent_side_assignment(self):
        k = self.paired_legs()
        w = np.ones((2, 23, 2))
        w[1, 13, 1] = 0
        aligned, _, events = align_limb_pairs(k, w, [(0, 1)], np.ones(2) * 20)
        np.testing.assert_array_equal(aligned, k)
        self.assertFalse(any(e['part'] == 'leg' for e in events))

    def test_body_midpoint_does_not_depend_on_side_names(self):
        k = np.zeros((6, 23, 3))
        k[:, :, 2] = 5
        k[:, 11, 0] = [-40, -40, 0, 0, 20, 20]
        k[:, 12, 0] = [40, 40, 40, 40, 100, 100]
        k[:, [11, 12], 1] = 100
        other = k.copy()
        other[2:4, [11, 12]] = k[2:4, [12, 11]]
        fallback = {n: np.zeros((6, 2)) for n in OBS}
        fallback.update(neck=np.zeros((6, 2)), pel=np.tile([0., 100.], (6, 1)))
        w = np.ones((6, 23))
        args = (w, None, list(range(6)), [(0, 1), (2, 3), (4, 5)], fallback, np.ones(6) * 100)
        a, _ = projected_joints(k, *args, direct_keys=True, track_pairs=False)
        b, _ = projected_joints(other, *args, direct_keys=True, track_pairs=False)
        np.testing.assert_allclose(a['pelvis'], b['pelvis'])

    def test_constant_observed_keys_reject_fallback_wobble(self):
        T = 6
        pts = {'sho_l': [-5, 0], 'sho_r': [5, 0], 'hip_l': [-5, 100], 'hip_r': [5, 100],
               'elb_l': [-20, 20], 'wri_l': [-40, 40], 'elb_r': [20, 20], 'wri_r': [40, 40],
               'kne_l': [-20, 150], 'ank_l': [-20, 200], 'kne_r': [20, 150], 'ank_r': [20, 200]}
        k = np.zeros((T, 23, 3))
        k[:, :, 2] = 5
        fallback = {n: np.tile(np.asarray(p, float), (T, 1)) for n, p in pts.items()}
        fallback.update(neck=np.zeros((T, 2)), pel=np.tile([0., 100.], (T, 1)))
        for name, index in OBS.items():
            k[:, index, :2] = pts[name]
        fallback['wri_l'][1, 0] += 80
        weights = np.ones((T, 23))
        wax = np.ones((T, 23, 2))
        half = (wax, np.zeros((T, 23), int), (-1000, 1000, -1000, 1000))
        args = (k, weights, half, list(range(T)), [(0, 1), (2, 3), (4, 5)], fallback, np.ones(T) * 100)
        old, _ = projected_joints(*args)
        new, _ = projected_joints(*args, direct_keys=True)
        self.assertGreater(abs(old['wri_l'][1, 0] + 40), 10.)
        np.testing.assert_allclose(new['wri_l'], np.tile([-40, 40], (T, 1)))
        # 보이지 않는 축은 직접 관측 모드에서도 기존 풀이를 보존한다.
        wax[:, 9, 1] = 0
        weights[:, 9] = 0
        fallback['wri_l'][:, 1] = np.arange(T) + 300
        partial, _ = projected_joints(*args, direct_keys=True)
        np.testing.assert_allclose(partial['wri_l'][:, 1], fallback['wri_l'][:, 1])

        # 양끝에서만 보이는 무릎을 직접 보간하면 틀 밖 중간 구간으로 끌어들이는 반례.
        wax[:, 13, 1] = [1, 0, 0, 0, 0, 1]
        weights[1:5, 13] = 0
        half[1][1:5, 13] = 1
        k[:, 13, 1] = 400
        fallback['kne_l'][:, 1] = [400, 900, 1000, 1000, 900, 400]
        guarded, rep = projected_joints(k, weights, half, list(range(T)), [(i, i) for i in range(T)],
                                       fallback, np.ones(T) * 100, direct_keys=True)
        self.assertGreater(guarded['kne_l'][2, 1], 900)
        self.assertIn({'joint': 'kne_l', 'axis': 1}, rep['protected_edge_axes'])


if __name__ == '__main__':
    unittest.main()
