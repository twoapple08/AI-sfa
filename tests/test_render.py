"""Reference renderer behaviour (synthetic checks; app agreement is in the APP-R1 report)."""
import unittest
import xml.etree.ElementTree as E

try:
    import numpy as np
    import sfa_render
except ImportError:  # numpy is optional for the rest of the repository
    sfa_render = None


def frame(bg='-1'):
    f = E.Element('Frame', BackgroundColor=bg, ID='1', Position='0')
    E.SubElement(f, 'LayerDef', ID='0', Name='Layer 1', Visible='true', Locked='false')
    return f


def ao(f, oid, kind, pts, color='-16777216', order=None, **attrs):
    o = E.SubElement(f, 'AO', ID=str(oid), TypeId=str(kind), Color=str(color), LayerId='0',
                     DrawOrder=str(order or oid), ThicknessScale='1.0', ObjectScale='1.0',
                     GlowRadius='0', GlowThickness='20', GlowColor='-1', GlowAlpha='0')
    for k, v in attrs.items():
        o.set(k, str(v))
    for i, (x, y) in enumerate(pts):
        E.SubElement(o, 'AP', ID=str(oid * 10 + i), Flags='3' if i == 0 else '9', Index=str(i), X=str(x), Y=str(y))
    return o


@unittest.skipIf(sfa_render is None, 'numpy not installed')
class Renderer(unittest.TestCase):
    def test_mapping_matches_measured_app_output(self):
        cv = sfa_render.Canvas(1920, 1080)
        x0, y0 = cv.to_px(0, 0)
        x1, y1 = cv.to_px(100, 100)
        self.assertAlmostEqual(x0, 10.708, delta=0.1)
        self.assertAlmostEqual(x1 - x0, 1898.96, delta=0.5)
        self.assertAlmostEqual((y1 - y0) / (x1 - x0), 0.5625, places=4)

    def test_background_and_src_over_fill(self):
        f = frame('-1')
        edges = [ao(f, 10 + i, 1, [p, q], color='0') for i, (p, q) in enumerate(
            [((20, 20), (80, 20)), ((80, 20), (80, 80)), ((80, 80), (20, 80)), ((20, 80), (20, 20))])]
        region = E.SubElement(f, 'FR', Color=str((128 << 24) | (255 << 16)))
        for e in edges:
            a, b = e.findall('AP')
            E.SubElement(region, 'FS', Kind='0', ObjId=e.get('ID'), StartPtId=a.get('ID'),
                         EndPtId=b.get('ID'), StartT='0.0', EndT='1.0', Contour='0')
        img = sfa_render.render_frame(f, 320, 180).astype(int)
        self.assertEqual(tuple(img[5, 5]), (255, 255, 255))
        self.assertTrue(np.all(np.abs(img[90, 160] - (255, 127, 127)) <= 1))

    def test_group_draws_cores_above_glows(self):
        def scene(grouped):
            f = frame('-16777216')
            glow = dict(GlowRadius=6, GlowThickness=30, GlowColor=-16711681, GlowAlpha=255)
            a = ao(f, 10, 1, [(30, 30), (70, 70)], color=-23296, **glow)
            b = ao(f, 11, 1, [(30, 70), (70, 30)], color=-23296, **glow)
            if grouped:
                child, parent = b.find('AP'), a.find('AP')
                child.set('Flags', str((int(parent.get('ID')) << 6) | 0x13))
            return sfa_render.render_frame(f, 640, 360).astype(int)
        cv = sfa_render.Canvas(640, 360)
        x, y = (round(v) for v in cv.to_px(51, 51))       # on line A, inside B's glow only
        free, grouped = scene(False)[y, x], scene(True)[y, x]
        self.assertEqual(tuple(grouped), (255, 165, 0))   # cores drawn after all group glows
        self.assertLess(free[0], 250)                     # later glow tints the earlier core


if __name__ == '__main__':
    unittest.main()
