import json
from pathlib import Path
import tempfile
import unittest
from build_feature_probes import build_suite
import sfa


class ProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.tmp.name)
        cls.manifest = build_suite(cls.out)
        cls.combined = sfa.read_sfa(cls.out/'feature_probes_v1.sfa')

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_every_probe_has_valid_graph(self):
        for p in self.out.glob('*.sfa'):
            self.assertEqual(sfa.validate(sfa.read_sfa(p)),[],p.name)
        self.assertEqual(len(self.combined.findall('Frame')),768)
        ids=[p.get('ID') for p in self.combined.iter('AP')]
        self.assertEqual(len(ids),len(set(ids)))

    def test_object_budget_and_pending_review(self):
        self.assertLessEqual(self.manifest['max_objects_per_frame'],20)
        self.assertTrue(all(not c['app_verified'] for c in self.manifest['cases']))
        self.assertTrue(self.manifest['not_covered'])

    def test_connected_arm_endpoints_remain_coincident(self):
        root=sfa.read_sfa(self.out/'03_stretch.sfa')
        for frame in root.findall('Frame'):
            upper,lower=frame.findall('AO')[4:6]
            a,b=upper.findall('AP')[0],lower.findall('AP')[1]
            self.assertEqual((a.get('X'),a.get('Y')),(b.get('X'),b.get('Y')))

    def test_probes_actually_change_target_attribute(self):
        color=sfa.read_sfa(self.out/'06_color.sfa').findall('Frame')
        self.assertNotEqual(color[0].find('AO').get('Color'),color[-1].find('AO').get('Color'))
        thickness=sfa.read_sfa(self.out/'08_thickness.sfa').findall('Frame')
        self.assertNotEqual(thickness[0].findall('AO')[4].get('ThicknessScale'),
                            thickness[24].findall('AO')[4].get('ThicknessScale'))
        order=sfa.read_sfa(self.out/'14_draw_order.sfa').findall('Frame')
        self.assertNotEqual(order[0].find('AO').get('DrawOrder'),order[-1].find('AO').get('DrawOrder'))
        visible=sfa.read_sfa(self.out/'13_layers.sfa').findall('Frame')
        self.assertNotEqual(visible[0].findall('LayerDef')[1].get('Visible'),
                            visible[-1].findall('LayerDef')[1].get('Visible'))
        appearance=sfa.read_sfa(self.out/'16_appear_delete.sfa').findall('Frame')
        self.assertEqual([len(appearance[i].findall('AO')) for i in [0,24,47]],[10,11,10])


if __name__=='__main__':unittest.main()
