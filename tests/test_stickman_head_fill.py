import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
import zipfile

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from stickman_head_fill import convert, repair
from stickman_quality import audit, digest
from test_stickman_quality import clip, scene


def legacy(root):
    for seg in root.iter('FS'):
        seg.attrib.pop('Kind')
        seg.set('StartT', '0')
        seg.set('EndT', '1')
    return root


class TestHeadFill(unittest.TestCase):
    def test_viewer_pixels_do_not_prove_app_fill_metadata_is_valid(self):
        from sfa_render import render_frame
        good = clip()
        bad = legacy(copy.deepcopy(good))
        before = ET.tostring(bad)
        np.testing.assert_array_equal(render_frame(good, good.find('Frame'), 200, 200),
                                      render_frame(bad, bad.find('Frame'), 200, 200))
        report, _, _ = audit(bad, scene(), width=100, crop_y=0)
        self.assertEqual(sum('원 전체 채움 저장 형식' in e for e in report['errors']), 10)
        self.assertEqual(ET.tostring(bad), before)

    def test_repair_changes_only_head_segments_and_is_idempotent(self):
        source = legacy(clip())
        extra = ET.SubElement(source.find('Frame'), 'FR', ID='unrelated', Color='-65536')
        ET.SubElement(extra, 'FS', Kind='0', ObjId='unrelated', StartT='0', EndT='1')
        original = ET.tostring(source)
        fixed, changes = repair(source)
        self.assertEqual(len(changes), 10)
        self.assertEqual(ET.tostring(source), original)
        self.assertEqual([ET.tostring(a) for a in source.iter('AO')], [ET.tostring(a) for a in fixed.iter('AO')])
        self.assertEqual(ET.tostring(extra), ET.tostring(fixed.find("Frame/FR[@ID='unrelated']")))
        restored = copy.deepcopy(fixed)
        for row in changes:
            head_id = row['after']['ObjId']
            seg = restored.findall('Frame')[row['index']].find(f"FR/FS[@ObjId='{head_id}']")
            seg.attrib.clear()
            seg.attrib.update(row['before'])
        self.assertEqual(ET.tostring(restored), original)
        again, rows = repair(fixed)
        self.assertEqual(rows, [])
        self.assertEqual(ET.tostring(again), ET.tostring(fixed))

    def test_missing_or_ambiguous_fill_is_not_invented(self):
        for mutate in ('missing', 'wrong_color', 'extra_segment'):
            source = legacy(clip())
            frame = source.find('Frame')
            fill = frame.find('FR')
            if mutate == 'missing':
                frame.remove(fill)
            elif mutate == 'wrong_color':
                fill.set('Color', '-65536')
            else:
                fill.append(copy.deepcopy(fill.find('FS')))
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                repair(source)
        source = legacy(clip())
        frame = source.find('Frame')
        head_id = frame.find('FR/FS').get('ObjId')
        frame.find(f"AO[@ID='{head_id}']").set('Color', '0')
        frame.remove(frame.find('FR'))
        fixed, changes = repair(source)
        self.assertEqual(len(changes), 9)
        self.assertIsNone(fixed.find('Frame').find(f"FR/FS[@ObjId='{head_id}']"))

    def test_saved_file_preserves_input_and_rejects_wrong_hash(self):
        with tempfile.TemporaryDirectory() as temp:
            base, out, config = (Path(temp)/n for n in ('base.sfa', 'out.sfa', 'scene.json'))
            with zipfile.ZipFile(base, 'w') as archive:
                archive.writestr('base.xml', ET.tostring(legacy(clip())))
            config.write_text(json.dumps(scene()))
            before = base.read_bytes()
            with self.assertRaisesRegex(ValueError, '해시'):
                convert(base, out, config, 100, 0, '0'*64)
            self.assertFalse(out.exists())
            report = convert(base, out, config, 100, 0, digest(base))
            self.assertEqual(report['errors'], [])
            self.assertEqual(len(report['head_fill_changes']), 10)
            self.assertEqual(base.read_bytes(), before)
            with self.assertRaisesRegex(ValueError, '덮어쓸'):
                convert(base, base, config, 100, 0, digest(base))


if __name__ == '__main__':
    unittest.main()
