"""sfa_tween follows the static reading (not app verification)."""
import unittest
import xml.etree.ElementTree as E

import sfa_tween as tw


def frame(fid, objs, layers=(('0', 'true'),), links=(), fills=()):
    f = E.Element('Frame', ID=str(fid), Position=str(fid), BackgroundColor='-1')
    for lid, vis in layers:
        E.SubElement(f, 'LayerDef', ID=lid, Name='L' + lid, Visible=vis, Locked='false')
    for oid, pts, attrs in objs:
        o = E.SubElement(f, 'AO', dict({'ID': str(oid), 'TypeId': '1', 'Color': '-16777216', 'LayerId': '0',
                                        'DrawOrder': str(oid), 'ThicknessScale': '1.0', 'ObjectScale': '1.0',
                                        'GlowRadius': '0', 'GlowThickness': '20', 'GlowColor': '-1',
                                        'GlowAlpha': '0'}, **{k: str(v) for k, v in attrs.items()}))
        for i, (x, y) in enumerate(pts):
            E.SubElement(o, 'AP', ID=str(fid * 1000 + oid * 10 + i), Flags='3', Index=str(i), X=str(x), Y=str(y))
    for dest, src in links:
        E.SubElement(f, 'TweenLink', ID=str(dest), From=str(src))
    for color, segs in fills:
        r = E.SubElement(f, 'FR', Color=str(color))
        for s in segs:
            E.SubElement(r, 'FS', s)
    return f


class Timeline(unittest.TestCase):
    def test_static_examples(self):
        got = [(a, round(t, 3)) for a, _, t in tw.timeline(3, 24, 12)['frames']]
        self.assertEqual(got, [(0, 0), (0, .5), (1, 0), (1, .5), (2, 0), (2, 0)])
        got = [(a, round(t, 3)) for a, _, t in tw.timeline(3, 25, 12)['frames']]
        self.assertEqual(got, [(0, 0), (0, 0), (0, .5), (1, 0), (1, .5), (2, 0), (2, 0)])
        plan = tw.timeline(2, 60, 12)
        self.assertEqual((plan['output_fps'], plan['steps'], len(plan['frames'])), (60, 5, 10))
        self.assertEqual(len(tw.timeline(4, 30, 12)['frames']), 10)
        self.assertFalse(tw.timeline(3, 12, 24)['interpolation_active'])
        self.assertEqual(tw.timeline(0, 60, 12)['frames'], [])

    def test_k_uses_half_away_rounding(self):
        self.assertEqual(tw.timeline(2, 30, 12)['steps'], 3)   # 2.5 -> 3


class Interpolation(unittest.TestCase):
    def test_attributes_and_points(self):
        a = frame(1, [(1, [(0, 0), (10, 10)], {'Color': -16777216, 'GlowAlpha': 0, 'GlowRadius': 0})])
        b = frame(2, [(1, [(10, 0), (20, 30)], {'Color': -1, 'GlowAlpha': 255, 'GlowRadius': 5})])
        o = tw.interpolate(a, b, 0.3).find('AO')
        p = o.findall('AP')
        self.assertAlmostEqual(float(p[1].get('Y')), 16.0)
        self.assertEqual(o.get('GlowAlpha'), str(int(255 * 0.3)))         # 76, trunc
        self.assertEqual(o.get('GlowRadius'), '2')                         # round(1.5) = 2
        self.assertEqual(tw.u32(int(o.get('Color'))), 0xFF4D4D4D)         # 0 + round(76.5) = 77

    def test_unpaired_and_invisible_layer_objects_drop(self):
        a = frame(1, [(1, [(0, 0), (1, 1)], {}), (2, [(0, 0), (1, 1)], {'LayerId': '1'}), (3, [(0, 0), (1, 1)], {})],
                  layers=(('0', 'true'), ('1', 'false')))
        b = frame(2, [(1, [(0, 0), (1, 1)], {}), (2, [(0, 0), (1, 1)], {'LayerId': '1'}), (4, [(0, 0), (1, 1)], {})],
                  layers=(('0', 'true'), ('1', 'false')))
        ids = [o.get('ID') for o in tw.interpolate(a, b, 0.5).findall('AO')]
        self.assertEqual(ids, ['1'])

    def test_manual_link_and_conflicts(self):
        a = frame(1, [(1, [(0, 0), (1, 1)], {}), (5, [(0, 0), (1, 1)], {})])
        b = frame(2, [(2, [(4, 4), (5, 5)], {}), (5, [(0, 0), (1, 1)], {})], links=[(2, 1), (5, 1)])
        links = tw.resolve_links(a, b)
        self.assertEqual({k: v.get('ID') for k, v in links.items()}, {'1': '2'})  # 5 exists in front

    def test_fill_held_and_paired(self):
        seg = lambda oid, c='0': {'Kind': '0', 'ObjId': str(oid), 'StartPtId': '-1', 'EndPtId': '-1',
                                  'StartT': '0.0', 'EndT': '1.0', 'Contour': c}
        objs = [(1, [(0, 0), (10, 0)], {}), (2, [(10, 0), (10, 10)], {}), (3, [(10, 10), (0, 0)], {})]
        red, blue = -65536, -16776961
        a = frame(1, objs, fills=[(red, [seg(1), seg(2), seg(3)])])
        b = frame(2, objs, fills=[(blue, [seg(1), seg(2), seg(3)])])
        mid = tw.interpolate(a, b, 0.5).findall('FR')
        self.assertEqual(len(mid), 1)
        self.assertEqual(tw.u32(int(mid[0].get('Color'))), 0xFF7F0080)    # paired: colour interpolates (R 255+round(-127.5)=127)
        only_front = frame(1, objs, fills=[(red, [seg(1), seg(2), seg(3)])])
        none_back = frame(2, objs)
        self.assertEqual(len(tw.interpolate(only_front, none_back, 0.9).findall('FR')), 1)
        self.assertEqual(len(tw.interpolate(none_back, only_front, 0.9).findall('FR')), 0)


if __name__ == '__main__':
    unittest.main()


class TweenProbe(unittest.TestCase):
    def test_probe_manifest_matches_timeline(self):
        import tempfile
        from build_tween_probe import build
        import sfa
        with tempfile.TemporaryDirectory() as tmp:
            manifest, root = build(tmp)
        self.assertEqual(sfa.validate(root), [])
        self.assertEqual(manifest['predicted']['output_frames'], 35)
        self.assertEqual(manifest['predicted']['steps_K'], 3)
        links = list(root.iter('TweenLink'))
        self.assertEqual(len(links), 1)
