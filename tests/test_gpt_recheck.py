"""GPT 재확인(11-01, docs/GPT-RECHECK-COMPOSE-ROUND1-2026-11-01.md) 재현 반례 → 회귀 방지:
정합성 검사가 전역 렌더 설정을 바꿔 1080 학습 영상의 선이 얇아지던 것, 축소 목록·고해상도 판정이 공식으로 표시되던 것."""
import json
import shutil
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))

import seq_check as SC  # noqa: E402
import sfa_compose as C  # noqa: E402
import sfa_render as R  # noqa: E402


def scene():
    seq = ET.Element('Sequence', HeightWidthRatio='0.5625', BackgroundColor='-1')
    fr = ET.SubElement(seq, 'Frame', ID='1', Position='0')
    ET.SubElement(fr, 'LayerDef', ID='0', Visible='true')
    ao = ET.SubElement(fr, 'AO', ID='1', TypeId='1', Color='-16777216', LayerId='0', DrawOrder='0', ThicknessScale=repr(C.snap_th(4)))
    for i, x in enumerate((20, 80)):
        ET.SubElement(ao, 'AP', ID=str(i + 10), X=str(x), Y='50')
    return seq, fr


class RenderStateTest(unittest.TestCase):
    def test_mismatch_restores_render_params(self):
        seq, fr = scene()
        before = dict(R.PARAMS)
        R.PARAMS.update(pad=0.0, thick_mul=1.0)
        try:
            SC.mismatch(seq, fr)
            self.assertEqual(R.PARAMS['thick_mul'], 1.0)   # 수정 전: 640/1920으로 남았다
            self.assertEqual(R.PARAMS['pad'], 0.0)
        finally:
            R.PARAMS.clear()
            R.PARAMS.update(before)

    @unittest.skipUnless(shutil.which('ffmpeg'), 'ffmpeg 필요')
    def test_saved_1080_video_same_with_or_without_check(self):
        """실제 save_frames(1920, 영상) → H.264 저장·복원: 정합성 검사를 켜도 선 굵기가 같아야 한다(수정 전 36 → 12화소)."""
        import seq_data as D
        seq, fr = scene()
        old = D.CHECK_EVERY
        widths = {}
        try:
            with tempfile.TemporaryDirectory() as d:
                for chk in (0, 50):
                    D.CHECK_EVERY = chk
                    name = f's{chk}.npz'
                    D.save_frames(d, name, [(seq, fr)], 0.5625, dict(W=1920, maxlen=2048, video=True), 23, dict(compose='real'))
                    z = np.load(Path(d) / name)
                    pix = D.V.decode_video(z['vid'], 1920, 1080)[0]
                    widths[chk] = int((pix[:, 960].mean(1) < 128).sum())
                    if chk:
                        self.assertEqual(json.loads(str(z['meta']))['items'][0].get('check'), 0)
        finally:
            D.CHECK_EVERY = old
        self.assertEqual(widths[0], widths[50])
        self.assertGreater(widths[0], 20)   # 1920폭 굵기(약 36화소)


class OfficialJudgmentTest(unittest.TestCase):
    def test_table(self):
        import seq_train as ST
        f = ST.official_judgment
        self.assertFalse(f(False, 600, 600, False, 640, 640))   # 중간 판정
        self.assertFalse(f(True, 599, 600, False, 640, 640))    # 계획 끝 전
        self.assertTrue(f(True, 600, 600, False, 640, 640))     # 공식
        self.assertFalse(f(True, 600, 600, True, 640, 640))     # --judge-n 축소 목록(수정 전: 공식)
        self.assertFalse(f(True, 600, 600, False, 1920, 640))   # 고해상도 판정(수정 전: 공식)


if __name__ == '__main__':
    unittest.main()
