import os
import sys
import unittest
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))
import sfa_objscore as OS  # noqa: E402


def frame(objs, bg='-1', fills=(), glow=None):
    """objs: (type, [(x,y)...], color, draworder, links[(내 점 번호, 상대 점 ID)]) — 점 ID는 '오브젝트 번호*10+점 번호'."""
    fr = ET.Element('Frame', dict(BackgroundColor=bg))
    ET.SubElement(fr, 'LayerDef', dict(ID='0', Name='L', Visible='true', Locked='false'))
    for k, (t, pts, col, order, links) in enumerate(objs):
        a = ET.SubElement(fr, 'AO', dict(ID=str(1000 + k), TypeId=t, Color=str(col), LayerId='0', DrawOrder=str(order)))
        if glow and k in glow:
            a.attrib.update(GlowRadius='8', GlowThickness='20', GlowAlpha='200', GlowColor='255')
        for j, (x, y) in enumerate(pts):
            p = ET.SubElement(a, 'AP', dict(ID=str(k * 10 + j), X=str(x), Y=str(y)))
            for jj, other in links:
                if jj == j:
                    ET.SubElement(p, 'AC', dict(ConnPtId=str(other)))
    for col, ids in fills:
        r = ET.SubElement(fr, 'FR', dict(Color=str(col)))
        for i in ids:
            ET.SubElement(r, 'FS', dict(Kind='1', ObjId=str(1000 + i)))
    return fr


BLACK, RED = -16777216, -65536


class ObjScoreTest(unittest.TestCase):
    def test_same_is_perfect(self):
        f = frame([('1', [(10, 10), (20, 10)], BLACK, 0, [(1, 10)]), ('1', [(20, 10), (20, 30)], RED, 1, [(0, 1)])],
                  fills=[(RED, [0, 1])])
        r = OS.score(f, f)
        self.assertTrue(r['perfect'])

    def test_max_matches_first(self):
        # GPT 반례: 비용 [[1, √2], [0, 1]], 허용 1 → 최소 거리합(0+√2… 대신 1+1)으로 2개를 맞혀야 한다
        A = frame([('1', [(0, 0), (0, 10)], BLACK, 0, []), ('1', [(1, 0), (1, 10)], BLACK, 1, [])])
        P = frame([('1', [(1, 0), (1, 10)], BLACK, 0, []), ('1', [(2, 0), (2, 10)], BLACK, 1, [])])
        r = OS.score(P, A, hwr=1.0)
        self.assertEqual(r['match'], 2)

    def test_draw_order_reversed(self):
        # 겹치는 빨강·검정 선의 실제 그리는 순서(DrawOrder)를 뒤집으면 순서 점수 0(XML 순서가 같아도)
        A = frame([('1', [(0, 0), (10, 10)], BLACK, 0, []), ('1', [(0, 10), (10, 0)], RED, 1, [])])
        P = frame([('1', [(0, 0), (10, 10)], BLACK, 1, []), ('1', [(0, 10), (10, 0)], RED, 0, [])])
        r = OS.score(P, A)
        self.assertEqual(r['order'], 0.0)
        self.assertFalse(r['perfect'])

    def test_circle_flip_links(self):
        # 원의 점 방향과 연결을 함께 뒤집어도 같은 그림 → 연결 F1 1
        A = frame([('2', [(10, 10), (20, 10)], BLACK, 0, [(1, 10)]), ('1', [(20, 10), (30, 10)], BLACK, 1, [(0, 1)])])
        P = frame([('2', [(20, 10), (10, 10)], BLACK, 0, [(0, 10)]), ('1', [(20, 10), (30, 10)], BLACK, 1, [(0, 0)])])
        r = OS.score(P, A)
        self.assertEqual(r['match'], 2)
        self.assertEqual(r['link_f1'], 1.0)

    def test_partial_score(self):
        # 사용자 10-31: 엄격 채점(1% 안만 맞음)에 더해 가까울수록 부분 점수 — 0% 1점, 1% 0.8점, 5% 이상 0점, 빠뜨림·더 그림은 감점
        A = frame([('1', [(10, 10), (20, 10)], BLACK, 0, []), ('1', [(10, 30), (20, 30)], BLACK, 1, [])])
        self.assertAlmostEqual(OS.score(A, A)['partial'], 1.0)
        near = frame([('1', [(12, 10), (22, 10)], BLACK, 0, []), ('1', [(10, 30), (20, 30)], BLACK, 1, [])])   # 하나가 2% 어긋남
        r = OS.score(near, A)
        self.assertEqual(r['match'], 1)                    # 엄격 채점에선 하나만 맞음
        self.assertAlmostEqual(r['partial'], (0.6 + 1.0) / 2)
        far = frame([('1', [(60, 60), (70, 60)], BLACK, 0, [])])
        self.assertAlmostEqual(OS.score(far, A)['partial'], 0.0)
        one = frame([('1', [(10, 10), (20, 10)], BLACK, 0, [])])   # 하나 빠뜨림
        self.assertAlmostEqual(OS.score(one, A)['partial'], 0.5)
        extra = frame([('1', [(10, 10), (20, 10)], BLACK, 0, []), ('1', [(10, 30), (20, 30)], BLACK, 1, []), ('1', [(50, 50), (60, 50)], BLACK, 2, [])])
        self.assertAlmostEqual(OS.score(extra, A)['partial'], 2 / 3)   # 엉뚱하게 더 그림
        circ = frame([('2', [(10, 10), (20, 10)], BLACK, 0, []), ('1', [(10, 30), (20, 30)], BLACK, 1, [])])
        self.assertAlmostEqual(OS.score(circ, A)['partial'], 0.5)      # 종류가 다르면 0점

    def test_links_not_in_perfect(self):
        # 사용자 10-31: 관절 연결은 만점에서 뺀다(24,24 — 한 장 그림에 영향 없음). 연결 F1은 따로 기록
        A = frame([('1', [(0, 0), (10, 0)], BLACK, 0, [(1, 10)]), ('1', [(10, 0), (10, 10)], BLACK, 1, [(0, 1)])])
        P = frame([('1', [(0, 0), (10, 0)], BLACK, 0, []), ('1', [(10, 0), (10, 10)], BLACK, 1, [])])
        r = OS.score(P, A)
        self.assertEqual(r['link_f1'], 0.0)
        self.assertTrue(r['perfect'])

    def test_one_point_circle_no_crash(self):
        A = frame([('2', [(10, 10)], BLACK, 0, [])])
        r = OS.score(A, A)
        self.assertEqual(r['match'], 0)

    def test_no_match_still_counts_links(self):
        A = frame([('1', [(0, 0), (10, 0)], BLACK, 0, [(1, 10)]), ('1', [(10, 0), (10, 10)], BLACK, 1, [(0, 1)])])
        P = frame([('1', [(50, 50), (60, 50)], BLACK, 0, [])])
        r = OS.score(P, A)
        self.assertEqual(r['match'], 0)
        self.assertEqual((r['link_tp'], r['link_ans']), (0, 1))
        self.assertEqual(r['link_f1'], 0.0)

    def test_bg_fill_glow_differences(self):
        base = [('1', [(10, 10), (20, 10)], BLACK, 0, [])]
        A = frame(base, fills=[(RED, [0])])
        self.assertFalse(OS.score(frame(base, bg=str(BLACK), fills=[(RED, [0])]), A)['perfect'])
        self.assertFalse(OS.score(frame(base, fills=[(BLACK, [0])]), A)['perfect'])
        self.assertFalse(OS.score(frame(base, fills=[(RED, [0])], glow={0}), A)['perfect'])

    def test_aspect_circle(self):
        # 비율 0.45: 가로 지름 20인 원과 세로 지름 20인 원은 화면에서 다르다(세로 20% = 가로 9%) → 안 맞음
        A = frame([('2', [(40, 50), (60, 50)], BLACK, 0, [])])
        P = frame([('2', [(50, 40), (50, 60)], BLACK, 0, [])])
        self.assertEqual(OS.score(P, A, hwr=0.45)['match'], 0)

    def test_gpt2_counterexamples(self):
        """GPT 2차(10-30): 큰 좌표 짝짓기 / 면 조각 / 0.5% 이동·굵기 4%는 만점 아님."""
        R = 2000000
        P = frame([('2', [(-R, 0), (R, 0)], BLACK, 0, []), ('1', [(0, -R), (0, R)], BLACK, 1, [])])
        A = frame([('2', [(0, -R), (0, R)], BLACK, 0, []), ('1', [(-R, 0), (R, 0)], BLACK, 1, [])])
        # GPT 반례: 가로 지름 원과 세로 지름 원은 같은 원(중심·반지름 같음) → 맞는 짝 1개(옛 코드는 0개)
        self.assertEqual(OS.score(P, A, hwr=1.0)['match'], 1)
        # 면: 원 전체 채우기 ↔ 같은 원의 일부(T 0..0.25) 채우기는 다르다
        circ = [('2', [(10, 10), (20, 10)], BLACK, 0, [])]
        Aw = frame(circ, fills=[(RED, [0])])
        Ps = frame(circ)
        r_ = ET.SubElement(Ps, 'FR', dict(Color=str(RED)))
        ET.SubElement(r_, 'FS', dict(Kind='0', ObjId='1000', StartPtId='0', EndPtId='1', StartT='0', EndT='0.25'))
        r = OS.score(Ps, Aw)
        self.assertEqual(r['fill_f1'], 0.0)
        self.assertFalse(r['perfect'])
        # 0.5% 이동: 허용 오차 안이라 '맞음'이지만 만점은 아니다
        base = [('1', [(10, 10), (20, 10)], BLACK, 0, [])]
        moved = [('1', [(10.5, 10), (20.5, 10)], BLACK, 0, [])]
        r = OS.score(frame(moved), frame(base))
        self.assertEqual(r['match'], 1)
        self.assertFalse(r['perfect'])
        # 굵기 10 → 10.4: 만점 아님
        f1, f2 = frame(base), frame(base)
        f1.find('AO').set('ThicknessScale', '10')
        f2.find('AO').set('ThicknessScale', '10.4')
        self.assertFalse(OS.score(f2, f1)['perfect'])
        f2.find('AO').set('ThicknessScale', '10')
        self.assertTrue(OS.score(f2, f1)['perfect'])

    def test_gpt3_counterexamples(self):
        """GPT 3차(10-30): 뒤집힌 원의 WHOLE / 면 색이 다른 겹친 원의 순서 / 한 점 한 칸 차이는 perfect 아님."""
        A = frame([('2', [(10, 10), (20, 10)], BLACK, 0, [])], fills=[(RED, [0])])
        P = frame([('2', [(20, 10), (10, 10)], BLACK, 0, [])], fills=[(RED, [0])])
        r = OS.score(P, A)
        self.assertEqual(r['fill_f1'], 1.0)
        self.assertTrue(r['perfect'])
        BLUE = -16776961
        circ = [('2', [(10, 10), (30, 10)], BLACK, 0, []), ('2', [(20, 10), (40, 10)], BLACK, 1, [])]
        A = frame(circ, fills=[(RED, [0]), (BLUE, [1])])
        P = frame([(t, xy, c, 1 - o, l) for t, xy, c, o, l in circ], fills=[(RED, [0]), (BLUE, [1])])
        r = OS.score(P, A)
        self.assertEqual(r['order'], 0.0)
        self.assertFalse(r['perfect'])
        base = [('1', [(10, 10), (20, 10)], BLACK, 0, [])]
        one = [('1', [(10.025, 10), (20, 10)], BLACK, 0, [])]
        r = OS.score(frame(one), frame(base))
        self.assertFalse(r['perfect'])
        self.assertTrue(r['near_perfect'])


def add_fill(fr, col, segs):
    """segs: (오브젝트 번호, T0, T1, 윤곽) — T0가 None이면 WHOLE(Kind 1)."""
    r = ET.SubElement(fr, 'FR', dict(Color=str(col)))
    for k, t0, t1, c in segs:
        if t0 is None:
            ET.SubElement(r, 'FS', dict(Kind='1', ObjId=str(1000 + k), Contour=str(c)))
        else:
            ET.SubElement(r, 'FS', dict(Kind='0', ObjId=str(1000 + k), StartPtId=str(k * 10), EndPtId=str(k * 10 + 1),
                                        StartT=repr(t0), EndT=repr(t1), Contour=str(c)))
    return fr


def circ_at(cx, cy, r, deg, hwr):
    """화면 화소 비율 기준 각도 deg의 지름 두 점(% 좌표)."""
    import math
    dx, dy = r * math.cos(math.radians(deg)), r * math.sin(math.radians(deg))
    return [(cx + dx, (cy + dy) / hwr), (cx - dx, (cy - dy) / hwr)]


class CircleFillTest(unittest.TestCase):
    """판정 기준 §4 채점기 원 수정 — GPT 3차 §2 반례 시험 10개."""
    H = [(10, 10), (20, 10)]    # 가로 지름: 첫 점 각도 π
    V = [(15, 5), (15, 15)]     # 세로 지름: 첫 점 각도 −π/2 → δ = −0.75

    def fill_f1(self, p_pts, p_fill, a_pts, a_fill, hwr=1.0, extra=()):
        P = add_fill(frame([('2', p_pts, BLACK, 0, [])] + list(extra)), RED, p_fill)
        A = add_fill(frame([('2', a_pts, BLACK, 0, [])] + list(extra)), RED, a_fill)
        return OS.score(P, A, hwr=hwr)

    def test_01_no_fill_rotated_diameter_equal(self):
        r = OS.score(frame([('2', self.V, BLACK, 0, [])]), frame([('2', self.H, BLACK, 0, [])]), hwr=1.0)
        self.assertEqual(r['match'], 1)
        self.assertTrue(r['perfect'])

    def test_02_same_t_after_rotation_not_equal(self):
        r = self.fill_f1(self.V, [(0, 0.0, 0.25, 0)], self.H, [(0, 0.0, 0.25, 0)])
        self.assertEqual(r['fill_f1'], 0.0)
        self.assertFalse(r['perfect'])

    def test_03_t_moved_by_delta_equal(self):
        r = self.fill_f1(self.V, [(0, 0.75, 1.0, 0)], self.H, [(0, 0.0, 0.25, 0)])
        self.assertEqual(r['fill_f1'], 1.0)
        self.assertTrue(r['perfect'])

    def test_04_diameter_swap_is_half_turn_not_reversal(self):
        swap = self.H[::-1]
        self.assertEqual(self.fill_f1(swap, [(0, 0.5, 0.75, 0)], self.H, [(0, 0.0, 0.25, 0)])['fill_f1'], 1.0)
        self.assertEqual(self.fill_f1(swap, [(0, 0.0, 0.25, 0)], self.H, [(0, 0.0, 0.25, 0)])['fill_f1'], 0.0)
        self.assertEqual(self.fill_f1(swap, [(0, 1.0, 0.75, 0)], self.H, [(0, 0.0, 0.25, 0)])['fill_f1'], 0.0)   # 직선용 1−T 변환은 틀림

    def test_05_aspect_slanted_diameter(self):
        for hwr in (0.45, 0.5625):
            A = circ_at(50, 30, 10, 30, hwr)
            P = circ_at(50, 30, 10, 100, hwr)
            d = (100 - 30) / 360   # 화면 화소 각도 차
            self.assertEqual(self.fill_f1(P, [(0, 0.1 - d, 0.35 - d, 0)], A, [(0, 0.1, 0.35, 0)], hwr=hwr)['fill_f1'], 1.0)
            import math
            raw = lambda xy: math.atan2(xy[0][1] - (xy[0][1] + xy[1][1]) / 2, xy[0][0] - (xy[0][0] + xy[1][0]) / 2)  # noqa: E731
            d_raw = (raw(P) - raw(A)) / (2 * math.pi)   # 비율을 무시한 각도 차로 옮기면 다른 구간
            self.assertEqual(self.fill_f1(P, [(0, 0.1 - d_raw, 0.35 - d_raw, 0)], A, [(0, 0.1, 0.35, 0)], hwr=hwr)['fill_f1'], 0.0)

    def test_06_interval_direction_and_turns(self):
        f = lambda p, a: self.fill_f1(self.H, [(0, *p, 0)], self.H, [(0, *a, 0)])['fill_f1']  # noqa: E731
        self.assertEqual(f((0.9, 1.1), (0.9, 0.1)), 0.0)    # +0.2바퀴 ≠ −0.8바퀴
        self.assertEqual(f((0.0, 1.0), (0.0, 2.0)), 0.0)    # 한 바퀴 ≠ 두 바퀴
        self.assertEqual(f((0.0, 0.0), (0.0, 1.0)), 0.0)    # 길이 0 ≠ 한 바퀴
        self.assertEqual(f((-0.1, 0.1), (0.9, 1.1)), 1.0)   # 두 끝점에 같은 정수를 빼면 같은 경로
        self.assertEqual(f((0.9, 1.1), (0.9, 1.1)), 1.0)

    def test_07_shared_circle_many_fills_with_hole(self):
        line = ('1', [(5, 30), (25, 30)], BLACK, 1, [])
        big = [(0, 0), (40, 0)]   # 원 0(큰 원), 직선 1, 작은 원 2(구멍)
        small_a, small_p = [(15, 0), (25, 0)], [(20, -5), (20, 5)]

        def mk(c0, c2, t_outer, t_other, t_hole):
            fr = frame([('2', c0, BLACK, 0, []), line, ('2', c2, BLACK, 2, [])])
            add_fill(fr, RED, [(0, *t_outer, 0), (1, 0.0, 1.0, 0), (2, *t_hole, 1)])
            add_fill(fr, BLACK, [(0, *t_other, 0)])
            return fr
        A = mk(big, small_a, (0.0, 0.5), (0.5, 1.0), (0.0, 1.0))
        rot = big[::-1]   # 큰 원 지름 교환(+0.5바퀴), 작은 원 90° 회전(δ = −0.75)
        P = mk(rot, small_p, (0.5, 1.0), (1.0, 1.5), (0.75, 1.75))
        self.assertEqual(OS.score(P, A, hwr=1.0)['fill_f1'], 1.0)
        P = mk(rot, small_p, (0.5, 1.0), (0.5, 1.0), (0.75, 1.75))   # 둘째 면만 옛 T 그대로
        self.assertEqual(OS.score(P, A, hwr=1.0)['fill_f1'], 0.5)

    def test_08_piece_order_matters(self):
        line = ('1', [(30, 10), (40, 10)], BLACK, 1, [])
        A = add_fill(frame([('2', self.H, BLACK, 0, []), line]), RED, [(0, 0.0, 0.5, 0), (1, 0.0, 1.0, 0)])
        P = add_fill(frame([('2', self.H, BLACK, 0, []), line]), RED, [(1, 0.0, 1.0, 0), (0, 0.0, 0.5, 0)])
        self.assertEqual(OS.score(P, A, hwr=1.0)['fill_f1'], 0.0)

    def test_09_lone_whole_vs_compound_whole(self):
        self.assertEqual(self.fill_f1(self.V, [(0, None, None, 0)], self.H, [(0, None, None, 0)])['fill_f1'], 1.0)
        self.assertEqual(self.fill_f1(self.H[::-1], [(0, None, None, 0)], self.H, [(0, None, None, 0)])['fill_f1'], 1.0)
        # GPT 3차 반례: 같은 윤곽에 WHOLE 원 + 직선 둘 → 원 지름 방향만 바꾸면 자동 연결선이 바뀐다
        lines = [('1', [(30, 10), (40, 20)], BLACK, 1, []), ('1', [(40, 20), (30, 30)], BLACK, 2, [])]
        segs = [(0, None, None, 0), (1, 0.0, 1.0, 0), (2, 0.0, 1.0, 0)]
        r = self.fill_f1(self.H[::-1], segs, self.H, segs, extra=lines)
        self.assertEqual(r['fill_f1'], 0.0)
        self.assertFalse(r['perfect'])
        self.assertEqual(self.fill_f1(self.H, segs, self.H, segs, extra=lines)['fill_f1'], 1.0)
        # 복합 윤곽 안 직선 전체(WHOLE)를 뒤집으면 보수적으로 틀림
        lw = [(0, 0.0, 0.5, 0), (1, None, None, 0)]
        P = add_fill(frame([('2', self.H, BLACK, 0, []), ('1', [(40, 20), (30, 10)], BLACK, 1, [])]), RED, lw)
        A = add_fill(frame([('2', self.H, BLACK, 0, []), ('1', [(30, 10), (40, 20)], BLACK, 1, [])]), RED, lw)
        self.assertEqual(OS.score(P, A, hwr=1.0)['fill_f1'], 0.0)

    def test_10_unstable_angle_is_conservative(self):
        z = [(15, 10), (15, 10)]   # 반지름 0
        r = self.fill_f1(z, [(0, 0.0, 0.5, 0)], z, [(0, 0.0, 0.5, 0)])
        self.assertEqual(r['fill_f1'], 0.0)
        self.assertFalse(r['perfect'])
        one = [(15, 10)]           # 점 하나: 짝이 없어 면도 못 옮김(오류 없이)
        r = self.fill_f1(one, [(0, 0.0, 0.5, 0)], self.H, [(0, 0.0, 0.5, 0)])
        self.assertEqual(r['fill_f1'], 0.0)


if __name__ == '__main__':
    unittest.main()
