"""부위 고정 스미어 탐지 v2와 평가기의 코드 검사(합성 조건). 실제 애니 탐지 성공의 근거가 아니다."""
import sys, unittest
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
try:
    import cv2
    import smear_limb_scan as S
    import smear_eval as E
except ImportError:  # pragma: no cover
    cv2 = None


def person(cx=300, cy=200, t=100):
    k = np.zeros((133, 3))
    k[:, 2] = 5.0
    k[5, :2], k[6, :2] = (cx - 30, cy), (cx + 30, cy)
    k[11, :2], k[12, :2] = (cx - 25, cy + t), (cx + 25, cy + t)
    k[7, :2], k[9, :2] = (cx - 60, cy + 40), (cx - 90, cy + 80)
    k[8, :2], k[10, :2] = (cx + 60, cy + 40), (cx + 120, cy + 40)
    k[13, :2], k[15, :2] = (cx - 25, cy + 160), (cx - 25, cy + 220)
    k[14, :2], k[16, :2] = (cx + 25, cy + 160), (cx + 25, cy + 220)
    k[0:5, :2] = (cx, cy - 60)
    return k


@unittest.skipIf(cv2 is None, 'cv2 없음')
class LimbScan(unittest.TestCase):
    def test_comb_beats_plain_hand(self):
        gray = np.full((480, 640), 200, np.uint8)
        comb = np.zeros((480, 640), np.uint8)
        cv2.circle(comb, (420, 240), 22, 1, -1)
        for i in range(12):  # 평행한 가는 가닥 12개
            y = 220 + 4 * i
            cv2.line(comb, (440, y), (500, y - 6), 1, 1)
        plain = np.zeros_like(comb)
        cv2.circle(plain, (420, 240), 22, 1, -1)
        for a in np.linspace(-0.8, 0.8, 5):  # 퍼진 굵은 손가락 5개
            cv2.line(plain, (420, 240), (int(420 + 45 * np.cos(a)), int(240 + 45 * np.sin(a))), 1, 8)
        z = np.zeros_like(comb)
        fc = S.window_features(gray, comb, (440, 240), 70, z, 640 / 1152)
        fp = S.window_features(gray, plain, (440, 240), 70, z, 640 / 1152)
        self.assertGreater(fc['thin_strands'], fp['thin_strands'])
        self.assertGreater(fc['thin_coherence'], 0.8)

    def test_actor_assignment_and_head_zone(self):
        rgb = np.full((480, 640, 3), 128, np.uint8)
        k = person()
        reg = S.person_region((480, 640), k)
        rgb[reg > 0] = (200, 60, 60)
        acts = S.assign_actors(S.color_masks(rgb), [k])
        self.assertEqual(list(acts), ['red'])
        self.assertEqual(S.head_zone((480, 640), k)[140, 300], 1)

    def test_green_block_is_not_blue(self):
        rgb = np.zeros((10, 10, 3), np.uint8)
        rgb[:] = (110, 200, 120)  # 초록 블록
        self.assertEqual(int(S.color_masks(rgb)['blue'].sum()), 0)


class Eval(unittest.TestCase):
    def test_uncertain_is_neither_hit_nor_false(self):
        labels = [dict(frame=1, actor='red', part='arm', x=50, y=50, conf='S', box=[40, 40, 60, 60]),
                  dict(frame=1, actor='blue', part='arm', x=200, y=200, conf='U', box=[190, 190, 210, 210])]
        scan = dict(rows=[dict(source_index=1, candidates=[
            dict(actor='red', box=[45, 45, 70, 70], score=3),
            dict(actor='blue', box=[195, 195, 205, 205], score=2),
            dict(actor='red', box=[300, 300, 320, 320], score=1)])])
        r = E.evaluate(labels, scan, margin=0)
        self.assertEqual((r['detections_hit_positive'], r['detections_on_uncertain'], r['detections_false']), (1, 1, 1))
        self.assertEqual(r['recall_all'], 1.0)
        self.assertEqual(r['average_precision'], 1.0)

    def test_actor_must_match(self):
        l = dict(frame=1, actor='red', x=10, y=10, conf='S', box=[0, 0, 20, 20])
        self.assertFalse(E.hit(l, dict(actor='blue', box=[0, 0, 20, 20]), 0))


if __name__ == '__main__':
    unittest.main()
