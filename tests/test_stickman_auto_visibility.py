"""자동 가시성(원본 인물색 받침) 합성 반례 시험. 실제 장면 품질 확인이 아니다."""
import os, sys, unittest
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))
import stickman_auto_visibility as AV


def pose():
    return {'head_t': np.array([100., 40.]), 'head_b': np.array([100., 100.]), 'neck': np.array([100., 110.]),
            'pelvis': np.array([100., 260.]), 'elb_r': np.array([60., 170.]), 'wri_r': np.array([30., 230.]),
            'elb_l': np.array([140., 170.]), 'wri_l': np.array([170., 230.]), 'kne_r': np.array([80., 330.]),
            'ank_r': np.array([80., 400.]), 'kne_l': np.array([120., 330.]), 'ank_l': np.array([120., 400.])}


class AutoVisibility(unittest.TestCase):
    def run_case(self, paint, **kw):
        rgb = np.full((420, 300, 3), 200, np.uint8)
        paint(rgb)
        return AV.auto_visibility([dict(red=pose())], [5], lambda n: rgb, 0, **kw)

    def test_invented_body_is_hidden_only_where_unsupported(self):
        def arm_only(rgb):  # 원본에는 오른팔만 빨강
            import cv2
            p = pose(); cv2.line(rgb, tuple(map(int, p['neck'])), tuple(map(int, p['elb_r'])), (220, 40, 40), 14)
            cv2.line(rgb, tuple(map(int, p['elb_r'])), tuple(map(int, p['wri_r'])), (220, 40, 40), 14)
        out, log = self.run_case(arm_only)
        self.assertEqual(out[0]['red']['_visible_segments'], [3, 4])

    def test_supported_body_keeps_fast_limbs(self):
        def body_no_arm(rgb):  # 몸통·머리는 받쳐지고 팔만 비어 있음(빠른 팔 스미어 등) → 그대로
            import cv2
            p = pose(); cv2.circle(rgb, (100, 70), 30, (220, 40, 40), -1)
            cv2.line(rgb, (100, 110), (100, 260), (220, 40, 40), 20)
        out, log = self.run_case(body_no_arm)
        self.assertNotIn('_visible_segments', out[0]['red'])
        self.assertEqual(log, [])

    def test_small_or_protected_person_untouched(self):
        out, log = self.run_case(lambda rgb: None, min_torso=500.)
        self.assertEqual(log, [])
        out2, log2 = AV.auto_visibility([dict(red=pose())], [5], lambda n: np.full((420, 300, 3), 200, np.uint8), 0, protected={(5, 'red')})
        self.assertEqual(log2, [])


if __name__ == '__main__':
    unittest.main()
