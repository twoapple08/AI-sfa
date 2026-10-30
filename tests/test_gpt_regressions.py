"""GPT 추가 검사(10-30, 1·2·3차 42개) 중 우리 시험에 없던 것을 지금 코드의 올바른 기대값으로 옮긴 회귀 시험.
원본 검사는 결함을 재현하면 통과하도록 짜였다(README). 여기서는 고친 동작을 확인한다.
seq_train의 안쪽 함수(val_batch·gen_one 등)는 GPT 검사처럼 ast로 뽑아 가짜 모델로 실행한다(GPU·자료 없이)."""
import ast
import json
import math
import os
import random
import sys
import tempfile
import time
import unittest
import weakref
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

TOOLS = Path(__file__).resolve().parent.parent / 'tools'
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import sfa_objscore as S  # noqa: E402
import sfa_tokens as K  # noqa: E402
from test_sfa_objscore import BLACK, RED, frame  # noqa: E402


def extract(name, scope, file='seq_train.py'):
    tree = ast.parse((TOOLS / file).read_text(encoding='utf-8'))
    node = next(n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.name == name)
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(TOOLS / file), 'exec'), scope)
    return scope[name]


class GptRegressions(unittest.TestCase):
    def test_amp_three_failure_stages(self):
        # 2차: 무조건 scaler.update()는 scale 전·unscale 전에 AssertionError → unscale 뒤에만 update
        for stage in ('before_scale', 'after_backward', 'after_unscale'):
            p = nn.Parameter(torch.tensor(1.0))
            opt = torch.optim.SGD([p], lr=.1)
            sc = torch.amp.GradScaler('cpu')
            unscaled = False
            if stage != 'before_scale':
                sc.scale(p * p).backward()
            if stage == 'after_unscale':
                sc.unscale_(opt)
                unscaled = True
            opt.zero_grad(set_to_none=True)
            if sc.is_enabled() and unscaled:
                sc.update()
            sc.scale(p * p).backward()
            sc.unscale_(opt)
            sc.step(opt)
            sc.update()
            self.assertAlmostEqual(p.item(), .8, places=6)

    def test_val_batch_releases_failed_tensor_and_counts(self):
        # 2차: except 안 재귀가 실패 텐서를 붙들었다 / 단일 장 실패가 조용히 빠졌다
        refs, seen = [], []

        class VA:
            def batch(self, b):
                return torch.zeros(len(b), 2), torch.zeros(len(b), 3), torch.zeros(len(b), 3), torch.ones(len(b))

        def net(im, *a):
            if len(im) > 1:
                held = torch.ones(100)
                refs.append(weakref.ref(held))
                raise torch.OutOfMemoryError('controlled')
            seen.append(refs[0]() is not None)
            return torch.ones(1)
        scope = {'torch': torch, 'va': VA(), 'net': net, 'dev': 'cpu', 'amp': False, 'dt': torch.float16,
                 'loss_fn': lambda *x: (torch.tensor(1.), torch.tensor(.5), torch.tensor(2.))}
        fn = extract('val_batch', scope)
        self.assertEqual(fn([0, 1]), (4., 2., 4., 0))
        self.assertEqual(seen, [False, False])

        class VA2:
            def batch(self, b):
                raise torch.OutOfMemoryError('controlled')
        fn = extract('val_batch', {'torch': torch, 'va': VA2(), 'dev': 'cpu'})
        self.assertEqual(fn([0]), (0., 0., 0., 1))

    def test_generation_oom_contained(self):
        # 2·3차: 생성 채점 중 메모리 부족이 학습을 멈추지 않고, 센 뒤 train 모드로 돌아온다(3차 이후 gen_set/gen_one 구조)
        class Net:
            training = True

            def train(self):
                self.training = True

            def eval(self):
                self.training = False

        class DS:
            hwr = [.5625]
            tok = [np.array([K.TOK['BOS'], K.TOK['EOS']])]
            fld = [np.array([0, 0])]

            def image(self, i):
                return np.zeros((2, 2, 3), np.uint8)

        def gen(*a):
            raise torch.OutOfMemoryError('controlled')
        net = Net()
        scope = {'torch': torch, 'np': np, 'time': time, 'net': net, 'dev': 'cpu', 'amp': False, 'dt': torch.float16,
                 'cfg': {'maxlen': 2048}, 'generate': gen, 'OS': S, 'K': K}
        extract('gen_one', scope)
        fn = extract('gen_set', scope)
        r = fn(DS(), [0], 'gen')
        self.assertEqual((r['gen_oom'], r['gen_frames']), (1, 0))
        self.assertTrue(net.training)

    def test_color_soft_target_stays_in_range(self):
        # 1차: 색 255의 이웃 256·257에 정답 확률이 샜다
        import seq_train as Q
        tgt = torch.tensor([[K.OFF + 255]])
        fld = torch.tensor([[K.FID['color']]])
        logits = torch.zeros(1, 1, K.VOCAB, requires_grad=True)
        loss, _, _ = Q.loss_fn(logits, tgt, fld)
        loss.backward()
        g = -logits.grad[0, 0]   # 정답 분포 쪽으로 미는 크기
        self.assertGreater(g[K.OFF + 255].item(), 0)
        self.assertLessEqual(g[K.OFF + 256].item(), 1e-6)
        self.assertLessEqual(g[K.OFF + 257].item(), 1e-6)

    def test_batches_respect_budget_and_skip_long(self):
        import seq_train as Q

        class DS:
            tok = [np.zeros(n) for n in (10, 20, 30, 300, 40)]

            def __len__(self):
                return len(self.tok)
        random.seed(0)
        out = Q.make_batches(DS(), 4, 100)
        flat = [k for b in out for k in b]
        self.assertNotIn(3, flat)   # 한도보다 긴 장은 뺀다
        for b in out:
            self.assertLessEqual(max(len(DS.tok[k]) for k in b) * len(b), 100)

    def test_done_marker(self):
        # 1·2차: 0장이어도·실패가 있어도 '다 만듦'이던 것
        import seq_data as D
        want = {'version': D.SEQ_DATA_VERSION, 'files': 2}
        with tempfile.TemporaryDirectory() as td:
            Path(td, 'done.json').write_text(json.dumps(dict(want, frames=0, npz=0, fails=[])))
            self.assertFalse(D.done_ok(td, want))
            Path(td, 'one.npz').touch()
            Path(td, 'done.json').write_text(json.dumps(dict(want, frames=1, npz=1, fails=['bad'])))
            self.assertFalse(D.done_ok(td, want))
            Path(td, 'done.json').write_text(json.dumps(dict(want, frames=1, npz=1, fails=[])))
            self.assertTrue(D.done_ok(td, want))

    def test_far_check_counts_stroke_width(self):
        # 1차: 화면 밖 판정이 굵기를 무시했다 — 화면 바로 밖의 아주 굵은 선은 화면에 닿으니 남아야 한다
        seq = ET.fromstring('<Sequence HeightWidthRatio="0.5625"/>')
        a = ET.fromstring('<AO ID="1" TypeId="1" Color="-16777216" ThicknessScale="60"/>')
        self.assertFalse(K.far_away(a, [(-8, 10), (-8, 90)], 0.5625))
        a.set('ThicknessScale', '1')
        self.assertTrue(K.far_away(a, [(-8, 10), (-8, 90)], 0.5625))
        del seq

    def test_reversed_curve_segment_fill(self):
        # 3차: 점 순서가 뒤집힌 곡선의 면 조각은 점·T를 함께 바꿔 대응
        a = frame([('3', [(10, 50), (50, 10), (90, 50)], BLACK, 0, [])])
        p = frame([('3', [(90, 50), (50, 10), (10, 50)], BLACK, 0, [])])
        for f, sp, ep, t0, t1 in ((a, '0', '2', '.2', '.8'), (p, '2', '0', '.8', '.2')):
            ET.SubElement(ET.SubElement(f, 'FR', Color=str(RED)), 'FS', Kind='0', ObjId='1000', StartPtId=sp, EndPtId=ep, StartT=t0, EndT=t1)
        r = S.score(p, a, hwr=1)
        self.assertEqual(r['fill_f1'], 1)
        self.assertTrue(r['perfect'])

    def test_cache_equals_full_with_and_without_sine(self):
        # 3차: KV 캐시 = 전체 계산(sin 끔·켬)
        import seq_train as Q
        torch.manual_seed(0)
        for sine in (False, True):
            net = Q.Net(32, 2, 4, 64, 'resnet18', pretrained=False, stride=16, sine=sine).eval()
            mem = torch.randn(1, 10, 32)
            tok = torch.tensor([[K.TOK['BOS'], K.n(2000), K.n(4000), K.TOK['PT']]])
            fld = torch.zeros_like(tok)
            with torch.no_grad():
                full = net.step(mem, tok, fld)
                c = Q.Cache(net, mem)
                inc = torch.stack([c.step(int(t), 0) for t in tok[0]])[None]
            self.assertLess((full - inc).abs().max().item(), 2e-6)


if __name__ == '__main__':
    unittest.main()
