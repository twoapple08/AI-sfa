import os
import sys
import unittest

import cv2
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
from cube_hand_sfa import convex_fix  # noqa: E402


class ConvexFixTest(unittest.TestCase):
    # 앞면 왼쪽 위 꼭짓점(1)이 안으로 들어가 윤곽이 꺾인 상자: 0-1-2-3 앞면, 0-1-4-5 윗면
    V = np.array([[50, 150], [60, 80], [150, 80], [150, 150], [140, 50], [40, 50]], float)
    F = [[0, 1, 2, 3], [5, 4, 2, 1]]

    def _img(self, gap_color):
        img = np.full((200, 200, 3), (40, 120, 230), np.uint8)
        cv2.fillPoly(img, [np.array([[40, 50], [140, 50], [150, 80], [150, 150], [50, 150]])], gap_color)
        cv2.fillPoly(img, [self.V[self.F[0]].astype(np.int32)], (210, 210, 210))
        cv2.fillPoly(img, [self.V[self.F[1]].astype(np.int32)], (90, 90, 90))
        ink = (cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) < 70).astype(np.uint8)
        return img, ink

    def test_fill_when_gap_is_face_colored(self):
        img, ink = self._img((90, 90, 90))  # 틈이 윗면과 같은 어두운 회색 → 빠진 면
        V, F, cols, log = convex_fix(img, ink, self.V, self.F)
        self.assertEqual(len(F), 3)
        self.assertEqual(sorted(F[2]), [0, 1, 5])
        self.assertTrue(np.allclose(V, self.V))

    def test_straighten_when_gap_is_background(self):
        img, ink = self._img((40, 120, 230))  # 틈이 바탕 → 꼭짓점을 편다
        V, F, cols, log = convex_fix(img, ink, self.V, self.F)
        self.assertEqual(len(F), 2)
        h1, h2, r = V[5], V[0], V[1]
        u = (h2 - h1) / np.linalg.norm(h2 - h1)
        self.assertLess(abs((r - h1)[0] * u[1] - (r - h1)[1] * u[0]), 1e-6)


if __name__ == "__main__":
    unittest.main()
