"""GPT 확인(ROUND2-FLOWTEST, 11-01, docs/GPT-VERIFY-ROUND2-FLOWTEST-2026-11-01.md) 반례 → 회귀 방지.
학습기 안쪽 함수는 실제 소스에서 AST로 꺼내 돌린다(모델·자료 없이)."""
import ast
import contextlib
import io
import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))

import sfa_compose as C  # noqa: E402
import sfa_render as R  # noqa: E402
import sfa_tokens as K  # noqa: E402

TREE = ast.parse((ROOT / 'tools' / 'seq_train.py').read_text(encoding='utf-8'))
TRAIN = next(n for n in TREE.body if isinstance(n, ast.FunctionDef) and n.name == 'train')


def inner(*names, **env):
    nodes = [n for n in TRAIN.body if isinstance(n, ast.FunctionDef) and n.name in names]
    exec(compile(ast.Module(body=nodes, type_ignores=[]), '<seq_train>', 'exec'), env)
    return env


class GenModelTest(unittest.TestCase):
    def cost(self, samples, cap=2048, est='cap'):
        env = inner('gen_model', 'gen_cost', np=np, rate={'gen_s': {'640': samples}}, final_plan=lambda final: [(640, cap)],
                    a=SimpleNamespace(final_gen_est=est))
        return env['gen_model'](), env['gen_cost'](True)

    def test_observed_length_bound(self):
        """11-05 coord3 회차: 모델이 스스로 끝내면 상한 가정이 20배 넘게 컸다. 실측 길이 95% 분위×1.5와 상한 중 작은 쪽."""
        s = [[100 + 10 * (i % 10), 1 + 0.01 * (100 + 10 * (i % 10))] for i in range(20)]
        s[0] = [400, 5.0]  # 표본 길이 차이(식별 조건) + 긴 꼬리
        _, c_cap = self.cost(s, est='cap')
        _, c_obs = self.cost(s, est='observed')
        lq = float(np.quantile([x[0] for x in s], 0.95)) * 1.5
        m, _ = self.cost(s)
        self.assertAlmostEqual(c_obs, m[0][640] + m[1] * lq, places=6)
        self.assertLess(c_obs, c_cap / 4)
        _, c_small = self.cost(s, cap=200, est='observed')   # 상한이 더 작으면 상한
        self.assertAlmostEqual(c_small, m[0][640] + m[1] * 200, places=6)
        _, c_few = self.cost(s[:10] + [[400, 5.0]], est='observed')   # 표본 16개 미만이면 예전처럼 상한
        _, c_few_cap = self.cost(s[:10] + [[400, 5.0]], est='cap')
        self.assertAlmostEqual(c_few, c_few_cap, places=6)

    def test_linear_samples_extrapolate(self):
        """참값 T = 1 + 0.01L 모의 표본: 수정 전 6.76초(참값 21.48)."""
        _, c = self.cost([[64, 1.64], [128, 2.28]])
        self.assertAlmostEqual(c, 1 + 0.01 * 2048, places=6)
        _, c = self.cost([[40, 1.4], [100, 2.0], [300, 4.0], [900, 10.0]])
        self.assertAlmostEqual(c, 1 + 0.01 * 2048, places=6)

    def test_unidentified_slope_uses_default(self):
        """표본 하나·길이 차이가 작으면 기울기를 정하지 않는다(수정 전: 한 개면 기울기 0, 2.28초)."""
        for s in ([[128, 2.28]], [[100, 2.0], [120, 2.2]], [[8, 0.1], [8, 0.12], [8, 0.11]]):
            m, c = self.cost(s)
            self.assertIsNone(m, s)
            self.assertIsNone(c, s)


class CenteredHugeCircleTest(unittest.TestCase):
    def frame(self, xy, hwr='0.5625'):
        sq = ET.Element('Sequence', HeightWidthRatio=hwr, BackgroundColor='-1')
        fr = ET.SubElement(sq, 'Frame', Position='0')
        ET.SubElement(fr, 'LayerDef', ID='0', Visible='true')
        ao = ET.SubElement(fr, 'AO', ID='1', TypeId='2', LayerId='0', Color='-16777216', ThicknessScale='1', DrawOrder='0')
        for i, (x, y) in enumerate(xy):
            ET.SubElement(ao, 'AP', ID=str(i + 10), X=repr(x), Y=repr(y))
        return sq, fr

    def test_concentric_and_near(self):
        """화면 가운데와 중심이 같거나 가까운 큰 원: 수정 전 정규화·인코딩·렌더 모두 0으로 나누기."""
        saved = dict(R.PARAMS)
        try:
            R.PARAMS.update(pad=0.0, thick_mul=1 / 3)
            for hwr in ('0.5625', '0.75', '1.0'):
                h = float(hwr)
                for xy in ([(50 - 1e9, 50), (50 + 1e9, 50)], [(50, 50 - 1e9 / h), (50, 50 + 1e9 / h)], [(50 - 1e9 + 3, 52), (50 + 1e9 + 3, 52)]):
                    self.assertEqual(K.canon_circle(xy, h), [])               # 화면에서 반지름(1억 % 넘음)만큼 떨어진 원 → 안 보이는 원
                    sq, fr = self.frame(xy, hwr)
                    t, st = K.encode(sq, fr)
                    self.assertEqual(st['drop_far'], 1)
                    img = R.render_frame(sq, fr, 640, int(round(640 * h)))[..., :3]
                    self.assertEqual(int((img < 250).any(-1).sum()), 0)       # 아무것도 안 그림
        finally:
            R.PARAMS.clear()
            R.PARAMS.update(saved)

    def test_tangent_huge_circle_kept(self):
        """화면에 걸치는 큰 원은 그대로 정규화(뺀 것과 구분)."""
        c = K.canon_circle([(18.2, -1.996e9), (18.2, 50.19)], 0.5625)
        self.assertEqual(len(c), 2)


class SmallComposePlanTest(unittest.TestCase):
    def plan(self, total, nfiles=403):
        src = ast.parse((ROOT / 'tools' / 'seq_data.py').read_text(encoding='utf-8'))
        main = next(n for n in src.body if isinstance(n, ast.FunctionDef) and n.name == 'main_compose')
        prefix = []
        for node in main.body:
            if isinstance(node, ast.With):
                break
            prefix.append(node)
        env = dict(a=SimpleNamespace(seed=0, W=640, compose=total, maxlen=2048, video=False, out_dir='unused'),
                   V=SimpleNamespace(file_list=lambda: list(range(nfiles))), ROOT='unused')
        root = SimpleNamespace(findall=lambda tag: [object()])
        with patch.object(C, 'load', return_value=root), contextlib.redirect_stdout(io.StringIO()):
            exec(compile(ast.Module(body=prefix, type_ignores=[]), '<main_compose>', 'exec'), env)
        return sum(j[0] == 'real' for j in env['jobs']), sum(j[0] == 'comp' for j in env['jobs']), env['n_comp']

    def test_small_targets_have_compose_jobs(self):
        """수정 전: --compose 40/30이 실제 403·조합 0."""
        for total in (30, 40):
            real, comp, n_comp = self.plan(total)
            self.assertEqual(real, round(total * 0.3))
            self.assertGreater(comp, 0)
            self.assertGreater(n_comp, 0)

    def test_full_and_sc_unchanged(self):
        """본 자료(4만)·sc(1,200)는 예전처럼 모든 파일에서 실제 장."""
        for total in (40000, 1200):
            real, comp, _ = self.plan(total)
            self.assertEqual(real, 403)
            self.assertGreater(comp, 0)


class FailureClockTest(unittest.TestCase):
    def tick(self, ok):
        env = inner('train_tick', time=SimpleNamespace(time=lambda: 120.), tm_load=[0.], yl=SimpleNamespace(paused=0.),
                    st={'train_min': 0., 'step': 0}, step_s=[0.], tm={'train': 0.})
        env['train_tick'](0., 0., 0., ok=ok)
        return env['st'], env['tm']

    def test_failed_attempt_not_progress(self):
        """실패한 시도는 학습 진행이 아니다(수정 전: 업데이트 0인데 train_min 2.0)."""
        st, tm = self.tick(False)
        self.assertEqual((st['train_min'], st['fail_min'], tm['train']), (0.0, 2.0, 0.0))
        st, tm = self.tick(True)
        self.assertEqual((st['train_min'], tm['train']), (2.0, 120.0))

    def test_plan_not_reduced(self):
        """계획은 첫 회차에 고정 — 줄이는 요청(600 → 480)은 따르지 않고 알린다. 늘리는 요청은 연장."""
        restore = next(n for n in TRAIN.body if isinstance(n, ast.If) and isinstance(n.test, ast.Name) and n.test.id == 'saved')
        nodes = [n for n in restore.body if isinstance(n, ast.If) and 'plan_minutes' in ast.unparse(n.test)]
        for want, keep in ((480., 600.), (780., 780.)):
            env = dict(st={'plan_min': 600., 'train_min': 100.}, a=SimpleNamespace(plan_minutes=want, minutes=180.))
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                exec(compile(ast.Module(body=nodes, type_ignores=[]), '<plan>', 'exec'), env)
            self.assertEqual(env['st']['plan_min'], keep)
            self.assertEqual('축소' in out.getvalue(), want < 600)


if __name__ == '__main__':
    unittest.main()
