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


if __name__ == '__main__':
    unittest.main()
