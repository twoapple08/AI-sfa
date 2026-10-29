import os
import sys
import tempfile
import unittest
import zipfile
import xml.etree.ElementTree as ET

import cv2
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))
import video_to_sfa as V  # noqa: E402


class VideoToSfaTest(unittest.TestCase):
    def test_lines_and_mass(self):
        img = np.full((180, 320, 3), 255, np.uint8)
        cv2.line(img, (20, 150), (300, 150), (0, 0, 0), 2)          # 가는 검은 선
        cv2.circle(img, (80, 60), 25, (0, 0, 0), 2)                 # 머리 같은 원
        cv2.rectangle(img, (200, 40), (260, 110), (200, 60, 30), -1)  # 굵은 덩어리(파랑)
        (reg, st), w, _ = V.frame_strokes(img, corner=50, line_tol=1.5, quad_tol=2.0)
        self.assertEqual(len(reg), 1)
        self.assertGreater(reg[0][1][0], 150)  # 덩어리 색 = 파랑(BGR의 B)
        self.assertGreaterEqual(len(st), 2)
        self.assertTrue(all(np.allclose(c, 0) for _, c in st))  # 선은 검정으로 맞춤
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, 't.sfa')
            V.write_sfa(p, [(reg, st)], 320, 180, 1.0)
            z = zipfile.ZipFile(p)
            r = ET.fromstring(z.read(z.namelist()[0]))
            fr = r.find('Frame')
            self.assertEqual(len(fr.findall('FR')), 1)
            self.assertEqual(len(fr.findall('AO')), sum(len(sg) for g, _ in reg for _, sg in g) + sum(len(s) for s, _ in st))


if __name__ == '__main__':
    unittest.main()
