"""새 작품 시험(sv)에서 학습 파일과 겹치는 시험 파일 빼기(11-01, 사용자 승인). 학습 자료는 그대로, 시험 자료를 읽을 때만 뺀다."""
import json
import os
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))

import seq_data as D  # noqa: E402
import seq_train as ST  # noqa: E402


def scene():
    seq = ET.Element('Sequence', HeightWidthRatio='0.5625', BackgroundColor='-1')
    fr = ET.SubElement(seq, 'Frame', ID='1', Position='0')
    ET.SubElement(fr, 'LayerDef', ID='0', Visible='true')
    ao = ET.SubElement(fr, 'AO', ID='1', TypeId='1', Color='-16777216', LayerId='0', DrawOrder='0', ThicknessScale='1.0')
    for i, x in enumerate((20, 80)):
        ET.SubElement(ao, 'AP', ID=str(i + 10), X=str(x), Y='50')
    return seq, fr


class HoldoutExcludeTest(unittest.TestCase):
    def test_list_has_overlap_file(self):
        files = ST.holdout_exclude()
        self.assertEqual(files.get('묶음2_Drive/47112(2_2)-1.sfa'), {7, 8})   # 파일 전체가 아니라 같은 그림인 두 장만
        with open(ST.HOLDOUT_EXCLUDE, encoding='utf-8') as fh:
            e = json.load(fh)['exclude'][0]
        self.assertEqual(e['train_match'], '묶음2_Drive/바람1-1.sfa')

    def test_loader_drops_only_that_file(self):
        rels = ['묶음2_Drive/47112(2_2)-1.sfa', '묶음2_Drive/47112(2_2)-10.sfa', '묶음2_Drive/4.7.1.1_2_14.sfa']
        with tempfile.TemporaryDirectory() as d:
            for r in rels:   # seq_data의 파일 단위 이름 규칙
                D.save_frames(d, ST.npz_prefix(r) + 'c23.npz', [scene()], 0.5625, dict(W=640, maxlen=2048), 23, {})
            full = ST.Data(d, 2048, 640)
            part = ST.Data(d, 2048, 640, exclude=['묶음2_Drive/47112(2_2)-1.sfa'])
        self.assertEqual(len(full), 3)
        self.assertEqual(len(part), 2)   # 이름이 비슷한 47112(2_2)-10은 남는다
        self.assertEqual([Path(p).name for p in part.excluded], [ST.npz_prefix(rels[0]) + 'c23.npz'])

    def test_loader_drops_only_listed_frames(self):
        def scene_at(pos):
            seq, fr = scene()
            fr.set('Position', str(pos))
            return seq, fr
        r = '묶음2_Drive/47112(2_2)-1.sfa'
        with tempfile.TemporaryDirectory() as d:
            name = ST.npz_prefix(r) + 'c23.npz'
            D.save_frames(d, name, [scene_at(p) for p in (6, 7, 8, 9)], 0.5625, dict(W=640, maxlen=2048), 23, {})
            z = dict(np.load(os.path.join(d, name)))   # 시험 자료(sv)는 파일 단위 저장이라 pos = 장의 Position(seq_data 파일 경로)
            z['pos'] = np.array([6, 7, 8, 9])
            np.savez_compressed(os.path.join(d, name), **z)
            got = ST.Data(d, 2048, 640, exclude={r: {7, 8}})
        self.assertEqual(sorted(m['pos'] for m in got.meta), [6, 9])
        self.assertEqual((got.excluded, got.excluded_frames), ([], 2))

    def test_prefix_matches_seq_data_names(self):
        r = '묶음2_Drive/47112(2_2)-1.sfa'
        self.assertTrue((r.replace('/', '__').replace(' ', '_')[:-4] + '__c23.npz').startswith(ST.npz_prefix(r)))
        self.assertTrue((r.replace('/', '__').replace(' ', '_')[:-4] + '__real00012__c23.npz').startswith(ST.npz_prefix(r)))


if __name__ == '__main__':
    unittest.main()
