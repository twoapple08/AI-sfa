"""먼 곡선 자르기(11-01): 조절점이 수백만 %인 2차 베지어를 렌더러(skia)가 좌표가 조금만 달라도 '안 보임'↔'화면 전체 회색'으로
다르게 그려, 판 5 Kaggle 자료의 정합성 표본에서 그림·정답이 180,375화소 어긋났다(H_SPECTRUM 58장). 정답 문장과 렌더러가
같은 정확한 자르기(sfa_tokens.clip_quad)를 쓰는지 확인한다."""
import math
import random
import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))

import seq_check as SC  # noqa: E402
import sfa_compose as C  # noqa: E402
import sfa_render as R  # noqa: E402
import sfa_tokens as K  # noqa: E402

# H_SPECTRUM 58장 변환 뒤 곡선(원래 좌표)과, 정답 토큰을 거쳐 조금 달라진 좌표
FAR = [(104.5, 115.35), (2350001.475, -2627269.275), (-789672.075, 324089.6)]
FAR2 = [(104.5, 115.35), (2350056.575, -2627330.875), (-789690.6, 324097.2)]


def qb(p, t):
    u = 1 - t
    return np.array([u * u * p[0][i] + 2 * u * t * p[1][i] + t * t * p[2][i] for i in (0, 1)])


def scene(pts, extra_line=True):
    seq = ET.Element('Sequence', HeightWidthRatio='0.5625', BackgroundColor='-1')
    fr = ET.SubElement(seq, 'Frame', ID='1', Position='0')
    ET.SubElement(fr, 'LayerDef', ID='0', Visible='true')
    oid = 1
    if extra_line:
        ao = ET.SubElement(fr, 'AO', ID='1', TypeId='1', Color='-16777216', LayerId='0', DrawOrder='0', ThicknessScale='1.0')
        for i, (x, y) in enumerate(((20, 40), (80, 60))):
            ET.SubElement(ao, 'AP', ID=str(10 + i), X=str(x), Y=str(y))
        oid = 2
    ao = ET.SubElement(fr, 'AO', ID=str(oid), TypeId='3', Color='-2122416514', LayerId='0', DrawOrder='1', ThicknessScale='0.758825')
    for i, (x, y) in enumerate(pts):
        ET.SubElement(ao, 'AP', ID=str(20 + i), X=repr(x), Y=repr(y))
    return seq, fr


class ClipQuadTest(unittest.TestCase):
    def test_sub_curve_is_exact(self):
        p = [(10.0, 20.0), (300.0, -50.0), (-40.0, 90.0)]
        a, b = 0.2, 0.7
        q = K.quad_sub(p, a, b)
        for s in np.linspace(0, 1, 11):
            np.testing.assert_allclose(qb(q, s), qb(p, a + (b - a) * s), atol=1e-9)

    def test_inside_untouched_far_cut(self):
        self.assertIsNone(K.clip_quad([(0, 0), (50, 120), (100, 0)]))
        self.assertEqual(K.clip_quad([(5000, 5000), (6000, 7000), (8000, 5000)]), [])   # 상자 밖 → 안 보임
        q = K.clip_quad(FAR)
        lo, hi = K.CLIP
        self.assertEqual(q[0], FAR[0])                      # 화면 쪽 끝은 그대로
        self.assertTrue(all(lo - 1e-6 <= v <= hi + 1e-6 for v in q[2]))   # 다른 끝은 상자 경계
        for s in np.linspace(0, 1, 7):                      # 원래 곡선 위의 점
            pt = qb(q, s)
            self.assertTrue(lo - 1e-6 <= pt[0] <= hi + 1e-6 and lo - 1e-6 <= pt[1] <= hi + 1e-6)

    def test_render_same_for_nearby_far_coords(self):
        """수정 전: FAR2(정답 토큰 복원 좌표)는 화면 전체가 회색(평균 밝기 187), FAR는 흰 바탕(249)."""
        saved = dict(R.PARAMS)
        try:
            R.PARAMS.update(pad=0.0, thick_mul=640 / 1920)
            a = R.render_frame(*scene(FAR), 640, 360)[..., :3].astype(float)
            b = R.render_frame(*scene(FAR2), 640, 360)[..., :3].astype(float)
        finally:
            R.PARAMS.clear()
            R.PARAMS.update(saved)
        self.assertGreater(a.mean(), 245)
        self.assertGreater(b.mean(), 245)
        self.assertLess(SC.tolerant_diff(a, b), 30)

    def test_answer_matches_image_under_transforms(self):
        """실제 장 변환(반전·확대·이동·굵기) 여러 개에서 그림과 정답 복원 그림이 맞는다(수정 전: 변환에 따라 19만 화소)."""
        seq0, fr0 = scene(FAR)
        root = ET.Element('Sequence', HeightWidthRatio='0.5625', BackgroundColor='-1')
        root.append(fr0)
        for sd in range(8):
            seq, fr = C.real_frame(root, fr0, random.Random(sd), 0.5625)
            self.assertLess(SC.mismatch(seq, fr)[0], 100, sd)

    def test_fill_curve_not_clipped(self):
        """면이 쓰는 곡선은 자르지 않는다(면 T가 원래 곡선 기준). 정답에 원래 큰 좌표가 남는다."""
        seq, fr = scene(FAR, extra_line=False)
        r = ET.SubElement(fr, 'FR', ID='1', Color='-65536')
        ET.SubElement(r, 'FS', ObjId='1', StartT='0', EndT='1', Contour='0')
        self.assertGreater(self.max_coord(seq, fr), 1e6)
        seq, fr = scene(FAR, extra_line=False)
        self.assertLess(self.max_coord(seq, fr), 1e4)   # 자른 곡선: 상자 근처 좌표만(BIG 수는 상자 범위에서도 쓰일 수 있다)

    @staticmethod
    def max_coord(seq, fr):
        d = K.decode(K.encode(seq, fr)[0])
        return max(abs(float(p.get(k))) for p in d.iter('AP') for k in ('X', 'Y'))


if __name__ == '__main__':
    unittest.main()


class HugeCircleTest(unittest.TestCase):
    """아주 큰 원(11-01): 렌더러 원 근사가 무너져 대각선 쐐기로 그려지고(판 6 1080 표본 6,410화소), 반지름 1경 %는 BIG 수 범위를 넘어
    정답 좌표가 잘렸다. 렌더러는 상자 안 호를 정확히 그리고, 정답·렌더러 모두 반지름 상한 원(canon_circle)으로 바꾼다."""
    # 나진짜너무슬프고속상하고 11장과 같은 꼴: 지름 한 끝이 화면 안(50.19), 다른 끝이 2천만 % 위
    HUGE = [(18.2, -1.996e7), (18.2, 50.19)]

    def test_canon_keeps_near_point_and_tangent(self):
        self.assertIsNone(K.canon_circle(self.HUGE, 0.5625))   # 반지름 1천만 %는 상한(1억 %) 안 — 그대로, 렌더러가 호만 정확히 그린다
        orig = [(18.2, -1.996e9), (18.2, 50.19)]
        c = K.canon_circle(orig, 0.5625)
        self.assertAlmostEqual(c[1][1], 50.19, places=4)      # 화면 쪽 점 Q: 같은 접선(y ≈ 50.19) 위, 화면 가운데에 가장 가까운 원 위 점
        self.assertLess(abs(c[0][0] - c[1][0]) / abs((c[0][1] - c[1][1]) * 0.5625), 1e-6)   # 지름 방향(거의 세로) 유지 = 같은 접선 방향
        h = 0.5625                                            # 원래 화면 쪽 끝점이 새 원 위에 있다(등방 좌표, 처짐 차이 이내)
        cx, cy = (c[0][0] + c[1][0]) / 2, (c[0][1] + c[1][1]) * h / 2
        r = math.hypot(c[1][0] - c[0][0], (c[1][1] - c[0][1]) * h) / 2
        self.assertLess(abs(math.hypot(18.2 - cx, 50.19 * h - cy) - r), 1e-3)
        self.assertIsNone(K.canon_circle([(10, 10), (60, 40)], 0.5625))   # 작은 원은 그대로
        far = [(5e15, -3e15), (50.0, 30.0)]                   # 1경 %급, 비스듬
        c = K.canon_circle(far, 0.5625)
        self.assertLess(max(abs(v) for q in c for v in q), 7e9)   # BIG 수 범위 안

    def test_render_band_not_wedge(self):
        """큰 원의 화면 부분은 수평 띠(접선). 예전 렌더러는 대각선 쐐기."""
        saved = dict(R.PARAMS)
        try:
            R.PARAMS.update(pad=0.0, thick_mul=640 / 1920)
            seq = ET.Element('Sequence', HeightWidthRatio='0.5625', BackgroundColor='-1')
            fr = ET.SubElement(seq, 'Frame', ID='1', Position='0')
            ET.SubElement(fr, 'LayerDef', ID='0', Visible='true')
            ao = ET.SubElement(fr, 'AO', ID='1', TypeId='2', Color='-16777216', LayerId='0', DrawOrder='0', ThicknessScale='2.0')
            for i, (x, y) in enumerate(self.HUGE):
                ET.SubElement(ao, 'AP', ID=str(10 + i), X=repr(x), Y=repr(y))
            img = R.render_frame(seq, fr, 640, 360)[..., :3]
        finally:
            R.PARAMS.clear()
            R.PARAMS.update(saved)
        dark = img.mean(-1) < 128
        rows = np.where(dark.any(1))[0]
        self.assertTrue(len(rows) and rows.max() - rows.min() < 12)          # 한 줄 띠(두께만큼)
        self.assertGreater(dark.any(0).sum(), 600)                           # 화면 가로 전체

    def test_huge_circle_answer_matches_image(self):
        for far in ([(18.2, -1.996e7), (18.2, 50.19)], [(5e15, -3e15), (50.0, 30.0)], [(-2e9, 40.0), (77.0, 40.0)]):
            seq = ET.Element('Sequence', HeightWidthRatio='0.5625', BackgroundColor='-1')
            fr = ET.SubElement(seq, 'Frame', ID='1', Position='0')
            ET.SubElement(fr, 'LayerDef', ID='0', Visible='true')
            ao = ET.SubElement(fr, 'AO', ID='1', TypeId='2', Color='-16777216', LayerId='0', DrawOrder='0', ThicknessScale='2.0')
            for i, (x, y) in enumerate(far):
                ET.SubElement(ao, 'AP', ID=str(10 + i), X=repr(x), Y=repr(y))
            root = ET.Element('Sequence', HeightWidthRatio='0.5625', BackgroundColor='-1')
            root.append(fr)
            for sd in range(6):
                s_, f_ = C.real_frame(root, fr, random.Random(sd), 0.5625)
                self.assertLess(SC.mismatch(s_, f_)[0], 100, (far, sd))
