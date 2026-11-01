"""단어장 레이어 투명도(LOPAC)와 파란점 규칙(11-02 사용자)."""
import copy
import os
import random
import sys
import unittest
import xml.etree.ElementTree as ET

import numpy as np

ROOT = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, os.path.join(ROOT, 'tools'))
sys.path.insert(0, os.path.dirname(__file__))


def two_layer(op):
    fr = ET.Element('Frame', BackgroundColor='-1')
    ET.SubElement(fr, 'LayerDef', ID='0', Visible='true')
    l1 = ET.SubElement(fr, 'LayerDef', ID='1', Visible='true')
    if op is not None:
        l1.set('Opacity', str(op))
    for k, (lid, y, col) in enumerate((('0', 40, '-16777216'), ('1', 60, '-65536'))):
        a = ET.SubElement(fr, 'AO', ID=str(k + 1), TypeId='1', Color=col, LayerId=lid, DrawOrder=str(k + 1), ThicknessScale='8')
        ET.SubElement(a, 'AP', ID=str(10 * k + 10), X='10', Y=str(y))
        ET.SubElement(a, 'AP', ID=str(10 * k + 11), X='90', Y=str(y))
    return fr


class Lopac(unittest.TestCase):
    def test_roundtrip(self):
        import sfa_tokens as K
        import sfa_render as R
        sq = ET.Element('Sequence', HeightWidthRatio='.5625', BackgroundColor='-1')
        fr = two_layer(30)
        t, st = K.encode(sq, fr)
        self.assertIn(K.TOK['LOPAC'], t)
        K.fields(t)
        d = K.decode(t)
        self.assertEqual([l.get('Opacity') for l in d.findall('LayerDef')], [None, '30'])
        a, b = R.render_frame(sq, fr, 320, 180), R.render_frame(sq, d, 320, 180)
        self.assertLess(int((np.abs(a.astype(int) - b.astype(int)).max(-1) > 24).sum()), 20)
        # 100(불투명)·없음은 적지 않는다
        self.assertNotIn(K.TOK['LOPAC'], K.encode(sq, two_layer(100))[0])
        self.assertNotIn(K.TOK['LOPAC'], K.encode(sq, two_layer(None))[0])

    def test_grammar_only_after_layer(self):
        import sfa_tokens as K
        sq = ET.Element('Sequence', HeightWidthRatio='.5625', BackgroundColor='-1')
        t = K.encode(sq, two_layer(30))[0]
        i = t.index(K.TOK['LOPAC'])
        self.assertEqual(t[i - 1], K.TOK['LAYER'])
        bad = t[:i + 2] + [K.TOK['LOPAC'], K.OFF + 5] + t[i + 2:]   # 같은 레이어에 두 번
        with self.assertRaises(ValueError):
            K.fields(bad)

    def test_scorer_sees_opacity(self):
        import sfa_objscore as OS
        self.assertTrue(OS.score(two_layer(30), two_layer(30))['perfect'])
        self.assertFalse(OS.score(two_layer(None), two_layer(30))['perfect'])

    def test_compose_adds_some_opacity(self):
        import sfa_compose as C
        sq = ET.Element('Sequence', HeightWidthRatio='.5625', BackgroundColor='-1')
        units = C.units_of(two_layer(None), .5625)
        rng = random.Random(0)
        ops = 0
        for _ in range(200):
            z = []
            fr = ET.Element('Frame')
            C.place(copy.deepcopy(units[0]), fr, .5625, rng, C.Ids() if hasattr(C, 'Ids') else type('I', (), dict(layer=0, ao=0, ap=0))(), z)
            ops += sum(l.get('Opacity') is not None for l in z)
        self.assertTrue(5 < ops < 60)


class BluePoint(unittest.TestCase):
    def test_every_linked_group_has_blue(self):
        """사용자 11-02: 연결된 무리(무리 통째로 하나의 오브젝트)마다 파란점(Flags 3)이 하나는 있어야 앱에서 편집할 수 있다."""
        import sfa_render as R
        import sfa_tokens as K
        import vec_data as V
        files = V.file_list(exclude_holdout=False)[::40]
        groups = 0
        for f in files:
            for i, (s, fr) in enumerate(R.iter_frames(os.path.join(V.ROOT, f))):
                if i % 10:
                    continue
                d = K.decode(K.encode(s, fr)[0])
                aos = d.findall('AO')
                find = K.link_groups(aos, True)
                has = {}
                for a in aos:
                    r = find(a.get('ID'))
                    has[r] = has.get(r, False) or any(int(p.get('Flags') or 0) == 3 for p in a.findall('AP'))
                groups += len(has)
                self.assertTrue(all(has.values()), f'{f} {i}')
        self.assertGreater(groups, 100)


if __name__ == '__main__':
    unittest.main()
