import copy
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET
from zipfile import ZipFile
import sfa


class FormatTests(unittest.TestCase):
    def setUp(self):
        self.root = ET.parse(Path(__file__).resolve().parents[1] / 'examples/default_stickman.xml').getroot()

    def test_wave_references_and_correspondence(self):
        wave = sfa.make_wave(self.root, 48)
        self.assertEqual(sfa.validate(wave), [])
        frames = wave.findall('Frame')
        self.assertEqual(len(frames), 48)
        self.assertEqual([a.get('ID') for a in frames[0].findall('AO')],
                         [a.get('ID') for a in frames[-1].findall('AO')])
        ids = [p.get('ID') for p in wave.iter('AP')]
        self.assertEqual(len(ids), len(set(ids)))
        # Shared elbow endpoints must remain coincident, including at peak motion.
        for frame in frames:
            objects = frame.findall('AO')
            self.assertEqual(objects[4][0].get('X'), objects[5][1].get('X'))
            self.assertEqual(objects[4][0].get('Y'), objects[5][1].get('Y'))
        self.assertNotEqual(frames[0].findall('AO')[5][0].get('Y'),
                            frames[15].findall('AO')[5][0].get('Y'))

    def test_roundtrip_preserves_unknown_data(self):
        self.root.set('FutureAttribute', 'keep-me')
        ET.SubElement(self.root, 'FutureNode', {'value': '123'})
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'test.sfa'
            sfa.write_sfa(self.root, path)
            read = sfa.read_sfa(path)
            self.assertEqual(ET.tostring(self.root), ET.tostring(read))

    def test_dangling_connection_rejected(self):
        self.root.find('.//AC').set('ConnPtId', 'missing')
        self.assertTrue(any('ConnPtId' in e for e in sfa.validate(self.root)))

    def test_nonfinite_coordinate_rejected(self):
        self.root.find('.//AP').set('X', 'nan')
        self.assertTrue(any('coordinate' in e for e in sfa.validate(self.root)))

    def test_references_scoped_to_frame(self):
        frame = copy.deepcopy(self.root.find('Frame'))
        frame.set('ID', '999'); frame.set('Position', '1')
        self.root.append(frame); self.root.set('FrameCount', '2')
        self.assertEqual(sfa.validate(self.root), [])

    def test_entity_declaration_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'bad.sfa'
            with ZipFile(path, 'w') as z:
                z.writestr('bad.xml', '<!DOCTYPE Sequence [<!ENTITY x "bad">]><Sequence/>')
            with self.assertRaisesRegex(ValueError, 'DTD'):
                sfa.read_sfa(path)

    def test_preview_and_timing(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'preview.html'
            sfa.preview(self.root, path, 24, 48)
            page = path.read_text()
            self.assertIn('목표 트위닝: 48 FPS', page)
            self.assertNotIn('TweenFPS', ET.tostring(self.root, encoding='unicode'))

    def test_observed_fill_forms_and_tween_links_survive(self):
        frame = self.root.find('Frame')
        fill = ET.SubElement(frame, 'FR', {'Color': '-16777216'})
        ET.SubElement(fill, 'FS', {'Kind': '0', 'ObjId': '1',
                                 'StartPtId': '-1', 'EndPtId': '-1',
                                 'StartT': '0.2', 'EndT': '0.8'})
        ET.SubElement(fill, 'FS', {'Kind': '1', 'ObjId': '1', 'Contour': '1'})
        ET.SubElement(frame, 'TweenLink', {'ID': '2', 'From': '1'})
        self.assertEqual(sfa.validate(self.root), [])
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'complex.sfa'
            sfa.write_sfa(self.root, path)
            self.assertEqual(ET.tostring(self.root), ET.tostring(sfa.read_sfa(path)))
        fill[0].set('StartPtId', 'missing')
        self.assertTrue(any('StartPtId' in e for e in sfa.validate(self.root)))

    def test_unrelated_rig_rejected(self):
        self.root.find('.//AP').set('X', '42')
        with self.assertRaisesRegex(ValueError, 'geometry'):
            sfa.make_wave(self.root)


if __name__ == '__main__':
    unittest.main()
