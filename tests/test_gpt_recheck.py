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
        self.assertFalse(f(True, 600, 600, False, 854, 854))    # 기본 입력을 854로 시작해도 공식 아님 — 360(640폭) 고정(GPT 확인 11-01)
        self.assertFalse(f(True, 600, 600, False, 640, 854))


def _controller():
    """실제 seq_train.train의 judge_eval과 마지막 저장·판정 순서(AST 그대로)를 모델·채점·저장 대신 가짜로 돌리는 장치
    (GPT 확인 11-01 부록 B를 회귀 시험으로). 모델 학습·생성·torch 파일 저장 검증이 아니다."""
    import ast
    import contextlib
    import copy
    import io
    import time
    from collections import Counter
    from types import SimpleNamespace
    import seq_train as ST
    tree = ast.parse((Path(ST.__file__)).read_text(encoding='utf-8'))
    train = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'train')
    judge = [n for n in train.body if isinstance(n, ast.FunctionDef) and n.name in ('official_gate', 'judge_eval')]
    loop_idx = max(i for i, n in enumerate(train.body) if isinstance(n, ast.While))

    def is_save(n):
        return isinstance(n, ast.Expr) and isinstance(n.value, ast.Call) and isinstance(n.value.func, ast.Name) and n.value.func.id == 'save_ckpt'

    def has_gen(n):
        return any(isinstance(x, ast.Call) and isinstance(x.func, ast.Name) and x.func.id == 'gen_eval' for x in ast.walk(n))
    tail = [n for n in train.body[loop_idx + 1:] if is_save(n) or (isinstance(n, ast.If) and has_gen(n))]
    tail_code = compile(ast.Module(body=tail, type_ignores=[]), '<train-tail>', 'exec')
    judge_code = compile(ast.Module(body=judge, type_ignores=[]), '<judge_eval>', 'exec')

    def run(state, width=640, reduced=False):
        st = copy.deepcopy(state)
        saved, caps = {}, []
        js = SimpleNamespace(stage={1920, 1280, 854}, tok=[[[0] * 25, [0] * 22, [0] * 25, [0] * 22]], ents=[dict(hwr=.5625)],
                             image=lambda i, d, w=None: (w or 640, d))

        def fake_eval(js_, gen, dirs, **kw):
            for d in dirs:
                gen(0, d)
            return {}, {}

        def gen_img(im, hwr, n_ans=None):
            caps.append((im[0], 2048 if n_ans is None else min(2048, 2 * n_ans + 128)))
            return [1, 2], True, 0.01
        env = dict(net=SimpleNamespace(eval=lambda: None, train=lambda: None), time=time, widths=[width], st=st, js=js,
                   cfg=dict(in_w=640), js_reduced=reduced, official_judgment=ST.official_judgment, reasons=Counter(), gen_img=gen_img,
                   J=SimpleNamespace(evaluate=fake_eval, flat=lambda out, pre='judge_': {}, summary_line=lambda *x: ''),
                   memo={2: 12.07, 4: 11.63}, judge_sheet=lambda *x: None, dev='cpu', a=SimpleNamespace(gen_minutes=1), rec={},
                   tm={'gen': 0})
        exec(judge_code, env)
        env['save_ckpt'] = lambda **kw: saved.update(copy.deepcopy(st))
        env['gen_eval'] = lambda final=False: env['judge_eval'](4, final)
        with contextlib.redirect_stdout(io.StringIO()):
            exec(tail_code, env)
        return dict(rec=env['rec'], live=st, saved=saved, caps=caps)
    return run


class OfficialCountTest(unittest.TestCase):
    def test_first_save_resume_extension(self):
        """최초 공식 1 → 저장 → 재개 → 연장 공식 2(수정 전: 저장본 0, 연장 다시 1)."""
        run = _controller()
        first = run(dict(stage=0, done_min=600, train_min=600, plan_min=600))
        self.assertEqual(first['rec']['judge_official_n'], 1)
        self.assertEqual(first['saved'].get('official_n'), 1)
        second = run(dict(first["saved"], done_min=1200, train_min=1200, plan_min=1200))
        self.assertEqual(second['rec']['judge_official_n'], 2)
        self.assertEqual(second['saved'].get('official_n'), 2)

    def test_repeat_and_third_not_official(self):
        """GPT 코드 검토 P-02: 같은 계획 끝 재실행은 재계산(공식 아님), 셋째 기회도 공식 아님(수정 전: 공식 1 → 2 → 3)."""
        run = _controller()
        s = dict(stage=0, done_min=600, train_min=600, plan_min=600)
        r1 = run(s)
        r2 = run(r1['saved'])
        self.assertEqual((r1['rec']['judge_official'], r1['rec']['judge_official_n']), (True, 1))
        self.assertEqual((r2['rec']['judge_official'], r2['rec']['judge_official_blocked']), (False, 'repeat'))
        r3 = run(dict(r2['saved'], train_min=780, plan_min=780))
        self.assertEqual((r3['rec']['judge_official'], r3['rec']['judge_official_n']), (True, 2))
        r4 = run(dict(r3['saved'], train_min=900, plan_min=900))
        self.assertEqual((r4['rec']['judge_official'], r4['rec']['judge_official_blocked']), (False, 'third'))

    def test_high_res_end_counts_once(self):
        """고해상도에서 끝난 회차: 고해상도 판정은 추세, 뒤따르는 360만 공식 — 한 번만 센다. 상한은 추세 178·공식 2048."""
        run = _controller()
        high = run(dict(stage=0, done_min=600, train_min=600, plan_min=600), 1920)
        self.assertFalse(high['rec']['judge_official'])
        self.assertTrue(high['rec']['judge360_official'])
        self.assertEqual((high['live']['official_n'], high['saved']['official_n'], high['rec']['judge360_official_n']), (1, 1, 1))
        self.assertEqual([c for _, c in high['caps']], [178] * 4 + [2048] * 2)
        small = run(dict(stage=0, done_min=600, train_min=600, plan_min=600), 1920, True)
        self.assertFalse(small['rec']['judge_official'] or small['rec']['judge360_official'])
        self.assertNotIn('official_n', small['saved'])


if __name__ == '__main__':
    unittest.main()
