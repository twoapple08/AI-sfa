"""레이어 투명도(LayerDef Opacity, 11-02 새 앱 기능)와 C안 최종 시험 봉인."""
import json
import os
import sys
import unittest
import xml.etree.ElementTree as ET

import numpy as np

ROOT = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, os.path.join(ROOT, 'tools'))


class LayerOpacity(unittest.TestCase):
    def frame(self, op):
        fr = ET.Element('Frame', BackgroundColor='-1')
        ld = ET.SubElement(fr, 'LayerDef', ID='0', Visible='true')
        if op is not None:
            ld.set('Opacity', str(op))
        a = ET.SubElement(fr, 'AO', ID='1', TypeId='1', Color='-16777216', LayerId='0', DrawOrder='1', ThicknessScale='10')
        ET.SubElement(a, 'AP', ID='10', X='10', Y='50')
        ET.SubElement(a, 'AP', ID='11', X='90', Y='50')
        return fr

    def test_opacity_blends_layer(self):
        """Opacity 30 = 검은 선이 흰 바탕 위에 30%만(약 179) — 100·없음은 그대로."""
        import sfa_render as R
        sq = ET.Element('Sequence', HeightWidthRatio='.5625', BackgroundColor='-1')
        full = R.render_frame(sq, self.frame(None), 320, 180)
        same = R.render_frame(sq, self.frame(100), 320, 180)
        part = R.render_frame(sq, self.frame(30), 320, 180)
        self.assertTrue(np.array_equal(full, same))
        c = full[90, 160]
        self.assertLess(int(c.max()), 10)
        self.assertTrue(abs(int(part[90, 160].mean()) - 255 * 0.7) < 4)


class FinalTestSealed(unittest.TestCase):
    def test_not_in_training_list(self):
        """C안 최종 시험 파일은 학습 목록(index.csv)에 없다."""
        import vec_data as V
        m = json.load(open(os.path.join(ROOT, 'data', 'final_test_c', 'manifest.json'), encoding='utf-8'))
        names = {os.path.basename(f['file']) for f in m['files']}
        listed = {os.path.basename(p) for p in V.file_list(exclude_holdout=False)}
        self.assertFalse(names & listed)
        self.assertEqual(sum(f['frames'] for f in m['files']), 243)


if __name__ == '__main__':
    unittest.main()
