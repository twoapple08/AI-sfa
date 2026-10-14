import tempfile
import unittest
from pathlib import Path
from build_priority_probes import build
import sfa


class PriorityProbes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.manifest, cls.roots = build(cls.tmp.name)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_references_and_global_point_identity(self):
        for name, root in self.roots.items():
            self.assertEqual(sfa.validate(root), [], name)
            points = [p.get('ID') for p in root.iter('AP')]
            self.assertEqual(len(points), len(set(points)), name)
            loaded = sfa.read_sfa(Path(self.tmp.name)/(name+'.sfa'))
            self.assertEqual(sfa.validate(loaded), [], name)

    def test_draw_order_never_conflicts_for_same_object(self):
        for name, root in self.roots.items():
            orders = {}
            for obj in root.iter('AO'):
                oid = obj.get('ID'); order = obj.get('DrawOrder')
                self.assertEqual(orders.setdefault(oid, order), order, name)

    def test_glow_variants_isolate_attributes(self):
        frames = self.roots['02_glow'].findall('Frame')
        reference = frames[48].find('AO').attrib
        targets = {0:'GlowAlpha',1:'GlowRadius',3:'GlowRadius',4:'GlowThickness',
                   5:'GlowThickness',6:'GlowAlpha',7:'GlowAlpha',8:'Color',
                   9:'GlowColor',10:'ObjectScale'}
        for section, expected in targets.items():
            obj = frames[section*24].find('AO')
            changed = {k for k,v in obj.attrib.items() if k not in ('ID','DrawOrder') and reference[k]!=v}
            self.assertEqual(changed,{expected},section)
            geometry = lambda o: [(p.get('X'),p.get('Y'),p.get('Index')) for p in o.findall('AP')]
            self.assertEqual(geometry(obj),geometry(frames[48].find('AO')))

    def test_tween_controls_and_expected_duration(self):
        frames = self.roots['03_tween'].findall('Frame')
        a = {o.get('ID') for o in frames[48].findall('AO')}
        b = {o.get('ID') for o in frames[54].findall('AO')}
        self.assertEqual(len(a & b),1)  # only the grey control; main ID replacement
        for phase in range(4):
            self.assertEqual(len(frames[24+phase*6].findall('AO')),2 if phase%2 else 1)
        row = next(x for x in self.manifest['files'] if x['name']=='03_tween.sfa')
        self.assertEqual(row['original_frames'],168)
        self.assertEqual(row['expected_output_frames'],336)
        self.assertEqual(row['expected_seconds'],14)


if __name__ == '__main__':
    unittest.main()
