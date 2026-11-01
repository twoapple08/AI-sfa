"""GPT 독립 코드 검토(11-01, docs/GPT-CODE-REVIEW-2026-11-01.md) 반례 → 회귀 방지."""
import contextlib
import copy
import io
import json
import random
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'tools'), str(ROOT / 'tests')]

import sfa_tokens as K  # noqa: E402


def toy_run(extra, minutes=1.0, patches=()):
    """작은 실제 학습기(GPT 부록 B-2): 한 장짜리 자료, resnet18·폭 32·1층, CPU. 마지막 기록을 돌려준다."""
    import torch
    import seq_train as ST
    sq = ET.Element('Sequence', HeightWidthRatio='.5625', BackgroundColor='-1')
    fr = ET.SubElement(sq, 'Frame', Position='0')
    ET.SubElement(fr, 'LayerDef', ID='0', Visible='true')
    ao = ET.SubElement(fr, 'AO', ID='1', TypeId='1', LayerId='0', Color='-16777216', DrawOrder='0')
    for i, x in enumerate((20, 80)):
        ET.SubElement(ao, 'AP', ID=str(i + 10), X=str(x), Y='50')
    t = K.encode(sq, fr)[0]
    real_net = ST.Net
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp) / 'data'
        d.mkdir()
        out = Path(tmp) / 'out'
        np.savez_compressed(d / 'toy.npz', img=np.full((1, 36, 64, 3), 255, np.uint8), tok=np.array(t, np.int16),
                            fld=np.array(K.fields(t), np.int8), off=np.array([0, len(t)]), pos=np.array([0]),
                            meta=json.dumps(dict(file='toy', W=64, hwr=.5625)))
        cli = ['seq_train', 'train', str(d), str(d), str(out), '--minutes', str(minutes), '--in-w', '64', '--maxlen', '64', '--d', '32',
               '--layers', '1', '--heads', '2', '--backbone', 'resnet18', '--val-n', '1', '--gen-n', '1', '--gen-minutes', '0',
               '--final-reserve-min', '0.05'] + extra

        def small(*a, **kw):
            return real_net(*a, **dict(kw, pretrained=False))
        with contextlib.ExitStack() as es:
            es.enter_context(patch.object(ST, 'Net', small))
            es.enter_context(patch.object(ST.os, 'cpu_count', lambda: 2))
            es.enter_context(patch.object(sys, 'argv', cli))
            es.enter_context(contextlib.redirect_stdout(io.StringIO()))
            for p in patches:
                es.enter_context(p)
            torch.set_num_threads(2)
            ST.main()
        return json.loads((out / 'log.jsonl').read_text().splitlines()[-1])


class JudgeListTest(unittest.TestCase):
    def test_only_fixed_manifest_is_official(self):
        """I-06: 축소·다른 목록의 판정 자료는 공식 자격이 없다(수정 전: 6장·틀린 해시도 공식)."""
        import seq_judge as J
        import seq_train as ST
        m = J.load_manifest()
        meta = dict(manifest_sha=J.manifest_sha(m), entries=[dict(file=e['file'], pos=e['pos'], group=e['group']) for e in m['entries']],
                    dirs=[list(d) for d in J.DIRS], W=640)
        self.assertTrue(ST.judge_list_ok(meta, m))
        for bad in (dict(meta, manifest_sha='wrong-list'), dict(meta, entries=meta['entries'][:6]), dict(meta, W=854),
                    dict(meta, dirs=meta['dirs'][:2]), dict(meta, entries=[dict(e, group=0) for e in meta['entries']])):
            self.assertFalse(ST.judge_list_ok(bad, m))


class SkippedUpdateTest(unittest.TestCase):
    def test_nonfinite_grad_is_failure(self):
        """I-01: 기울기가 넘쳐 업데이트가 없으면 성공 걸음·학습 진행이 아니다(수정 전: 성공으로 기록)."""
        import torch
        inf = lambda *a, **k: torch.tensor(float('inf'))  # noqa: E731
        r = toy_run(['--plan-minutes', '0.5', '--max-fail-row', '5'], patches=[patch.object(torch.nn.utils, 'clip_grad_norm_', inf)])
        self.assertEqual(r['step'], 0)
        self.assertEqual(r['train_min'], 0.0)
        self.assertEqual(r['stop'], 'failures')
        self.assertGreater(r['fail_min'], 0.0)

    def test_normal_run_updates(self):
        r = toy_run(['--plan-minutes', '0.05'])
        self.assertGreater(r['step'], 0)
        self.assertEqual(r['stop'], 'plan')


if __name__ == '__main__':
    unittest.main()


class SaveFailureTest(unittest.TestCase):
    def test_final_save_failure_stops_and_fallback(self):
        """I-08: 저장 실패를 성공처럼 넘기지 않는다 — 본 파일 실패면 예비 파일, 마지막 저장이 둘 다 실패하면 멈춘다(수정 전: None 반환·횟수 증가)."""
        import ast
        import time
        import types
        import torch
        tree = ast.parse((ROOT / 'tools' / 'seq_train.py').read_text(encoding='utf-8'))
        tr = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'train')
        node = next(n for n in tr.body if isinstance(n, ast.FunctionDef) and n.name == 'save_ckpt')
        empty = types.SimpleNamespace(state_dict=lambda: {})

        def make(results):
            calls = []

            def save(obj, path, tries=60):
                calls.append(path)
                return results[len(calls) - 1]
            env = dict(time=time, st={'official_n': 1}, done0=0, active_min=lambda: 3., random=random, torch=torch, dev='cpu',
                       VT=types.SimpleNamespace(save=save), net=empty, opt=empty, scaler=empty, cfg={}, ck='ckpt.pt', rate={})
            exec(compile(ast.Module(body=[node], type_ignores=[]), '<save>', 'exec'), env)
            return env, calls
        env, calls = make([False, True])
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertTrue(env['save_ckpt']())
        self.assertEqual(calls, ['ckpt.pt', 'ckpt.pt.fallback'])
        self.assertEqual(env['st']['save_failed'], 1)
        env, _ = make([False, False])
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertFalse(env['save_ckpt']())             # 중간 저장은 실패를 알리고 계속
            self.assertNotIn('save', env['rate'])           # 실패한 저장은 저장 속도에 넣지 않는다
            env2, _ = make([False, False])
            with self.assertRaises(SystemExit):
                env2['save_ckpt'](final=True)


class TrendTest(unittest.TestCase):
    def test_unofficial_not_pass_and_condition_split(self):
        """I-07: 비공식 결과에 '통과'를 쓰지 않고, 조건이 다른 기록끼리 추세를 비교하지 않는다."""
        import seq_trend as T
        r = dict(minutes=1, step=1, judge_N=3, judge_win=3, judge_need=3, judge_passed_all=True, judge_health_passed=True,
                 judge_official=False, judge_reduced=True, judge_w=1920)
        t = T.table([r])
        self.assertNotIn(' 통과 @', t)
        self.assertIn('기준선 초과(추세)', t)
        self.assertIn(' 통과', T.table([dict(r, judge_official=True, judge_reduced=False, judge_w=640)]))
        a = dict(r, judge_win=1, judge_delta_median=0.1)
        b = dict(r, judge_w=640, judge_win=3, judge_delta_median=5.0)
        v = T.verdict([a, b])
        self.assertIn('조건 바뀐 곳', v)
        self.assertIn('2번 미만', v)


class ScorerOrderTest(unittest.TestCase):
    """I-02·03·09(GPT 부록 A): 순서가 영상을 바꾸는데 만점이던 경우, 조합 묶음 레이어 순서."""

    @classmethod
    def setUpClass(cls):
        import sfa_render as R
        cls.saved = dict(R.PARAMS)
        R.PARAMS.update(pad=0., thick_mul=640 / 1920)

    @classmethod
    def tearDownClass(cls):
        import sfa_render as R
        R.PARAMS.clear()
        R.PARAMS.update(cls.saved)

    def diff(self, p, a):
        import sfa_render as R
        sq = ET.Element('Sequence', HeightWidthRatio='.5625', BackgroundColor='-1')
        x, y = R.render_frame(sq, p, 640, 360), R.render_frame(sq, a, 640, 360)
        return int((np.abs(x.astype(int) - y.astype(int)).max(-1) > 24).sum())

    def test_same_fill_order(self):
        import sfa_objscore as OS
        from test_sfa_objscore import frame, BLACK, RED
        base = [('2', [(20, 50), (50, 50)], BLACK, 0, []), ('2', [(40, 50), (70, 50)], BLACK, 1, [])]
        a = frame(base, fills=[(RED, [0]), (RED, [1])])
        p = frame([(t, xy, c, 1 - o, l) for t, xy, c, o, l in base], fills=[(RED, [0]), (RED, [1])])
        self.assertGreater(self.diff(p, a), 100)
        self.assertFalse(OS.score(p, a)['perfect'])          # 수정 전: perfect=True, order=None

    def test_glow_order(self):
        import sfa_objscore as OS
        from test_sfa_objscore import frame, BLACK, RED
        base = [('1', [(20, 45), (80, 45)], BLACK, 0, []), ('1', [(20, 55), (80, 55)], RED, 1, [])]
        a = frame(base, glow={0, 1})
        for i, o in enumerate(a.findall('AO')):
            o.attrib.update(GlowRadius='30', GlowThickness='200', GlowAlpha='200', GlowColor=str(0xFF0000 if i == 0 else 0x0000FF))
        p = copy.deepcopy(a)
        for o in p.findall('AO'):
            o.set('DrawOrder', str(1 - int(o.get('DrawOrder'))))
        self.assertGreater(self.diff(p, a), 1000)
        self.assertFalse(OS.score(p, a)['perfect'])          # 수정 전: perfect=True, order=None

    def test_same_plain_lines_still_free(self):
        """같은 색 단색 선끼리는 순서를 바꿔도 같은 영상 — 그대로 만점."""
        import sfa_objscore as OS
        from test_sfa_objscore import frame, BLACK
        base = [('1', [(20, 50), (80, 50)], BLACK, 0, []), ('1', [(50, 20), (50, 80)], BLACK, 1, [])]
        a = frame(base)
        p = frame([(t, xy, c, 1 - o, l) for t, xy, c, o, l in base])
        self.assertEqual(self.diff(p, a), 0)
        self.assertTrue(OS.score(p, a)['perfect'])

    def test_unit_keeps_layer_order(self):
        import sfa_compose as C
        src = ET.Element('Frame', ID='1', Position='0', BackgroundColor='-1')
        for lid in ('1', '0'):
            ET.SubElement(src, 'LayerDef', ID=lid, Visible='true')
        for i, (lid, col) in enumerate((('0', -16777216), ('1', -65536))):
            ao = ET.SubElement(src, 'AO', ID=str(i + 1), TypeId='1', LayerId=lid, Color=str(col), DrawOrder=str(i), ThicknessScale=str(C.snap_th(4)))
            for j, x in enumerate((20, 80)):
                ET.SubElement(ao, 'AP', ID=str(10 * i + j), X=str(x), Y='50')
        f = ET.SubElement(src, 'FR', Color='0')
        for i in (1, 2):
            ET.SubElement(f, 'FS', Kind='1', ObjId=str(i))
        u = C.units_of(src, .5625)[0]
        dst = ET.Element('Frame', BackgroundColor='-1')
        layers = []
        C.place(u, dst, .5625, random.Random(0), C.Ids(), layers, keep='exact')
        for i, ld in enumerate(layers):
            dst.insert(i, ld)
        sq = ET.Element('Sequence', HeightWidthRatio='.5625', BackgroundColor='-1')
        self.assertEqual([a.get('Color') for _, a in K.order_objects(sq, src)], [a.get('Color') for _, a in K.order_objects(sq, dst)])
        self.assertEqual(self.diff(dst, src), 0)             # 수정 전: 4,728화소
