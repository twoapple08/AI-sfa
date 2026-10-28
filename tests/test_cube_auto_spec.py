import os
import sys
import unittest

import cv2
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
from cube_auto_spec import find  # noqa: E402


class CubeAutoSpecTest(unittest.TestCase):
    def _box(self, gap):
        img = np.zeros((200, 200, 3), np.uint8)
        img[:] = (40, 120, 230)  # 주황 바탕
        top = np.array([[50, 60], [130, 50], [150, 80], [70, 90]])
        front = np.array([[70, 90], [150, 80], [150, 140], [70, 150]])
        cv2.fillPoly(img, [top], (90, 90, 90))
        cv2.fillPoly(img, [front], (210, 210, 210))
        for p in (top, front):
            cv2.polylines(img, [p.reshape(-1, 1, 2)], True, (20, 20, 20), 3)
        if gap:  # 공유 모서리 먹선을 끊는다 → 두 면이 붙어도 색으로 갈라야 함
            cv2.line(img, (100, 86), (115, 84), (210, 210, 210), 4)
        return find(img, (10, 10, 190, 190))[0]

    def test_box(self):
        cubes = self._box(False)
        self.assertEqual(len(cubes), 1)
        self.assertEqual(len(cubes[0]["faces"]), 2)
        self.assertEqual(len(cubes[0]["v"]), 6)

    def test_box_with_gap(self):  # 끊긴 자리에 면이 파고들어 꼭짓점이 늘 수 있다 — 면 둘로 갈리는지만 본다
        cubes = self._box(True)
        self.assertEqual(len(cubes), 1)
        self.assertEqual(len(cubes[0]["faces"]), 2)


if __name__ == "__main__":
    unittest.main()
