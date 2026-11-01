"""GPT 재확인(docs/GPT-RECHECK-CODE-REVIEW-2026-11-01.md, 2e255ee) 새 반례 R-01–R-06 회귀."""
import copy
import os
import sys
import tempfile
import time
import types
import unittest
import xml.etree.ElementTree as ET

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))
sys.path.insert(0, os.path.dirname(__file__))


class FiniteNormOverflow(unittest.TestCase):
    def test_failure_keeps_optimizer_untouched(self):
        """R-01: 기울기 값은 유한한데 노름만 넘치면 실패로 세고 옵티마이저를 돌리지 않는다(옛: 실패 3·옵티마이저 step 3)."""
        import torch
        from unittest.mock import patch
        from test_gpt_code_review import toy_run
        real_scaler, real_clip, real_opt, opts = torch.amp.GradScaler, torch.nn.utils.clip_grad_norm_, torch.optim.AdamW, []

        def cpu_scaler(*a, **kw):
            return real_scaler('cpu', enabled=True)

        def clip(params, *a, **kw):
            ps = list(params)
            for p in ps:
                if p.grad is not None:
                    p.grad.fill_(1e20)
            return real_clip(ps, *a, **kw)

        def optimizer(*a, **kw):
            o = real_opt(*a, **kw)
            opts.append(o)
            return o
        r = toy_run(['--plan-minutes', '.5', '--max-fail-row', '3', '--lr', '1'],
                    patches=[patch.object(torch.amp, 'GradScaler', cpu_scaler), patch.object(torch.nn.utils, 'clip_grad_norm_', clip),
                             patch.object(torch.optim, 'AdamW', optimizer)])
        self.assertEqual(r['step'], 0)
        self.assertEqual(r['stop'], 'failures')
        self.assertEqual(sum(float(s.get('step', 0)) for s in opts[0].state.values()), 0.0)


class ScorerRecheck(unittest.TestCase):
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

    def test_extrapolated_fill(self):
        """R-02: 직선 조각 T=3인 면은 선 끝을 넘는다 — 그 범위의 앞뒤가 바뀌면 만점 아님(옛: 만점, 588화소)."""
        import sfa_objscore as OS
        from test_sfa_objscore import frame, RED
        a = frame([('1', [(10, 20), (20, 20)], 0, 0, []), ('1', [(10, 80), (20, 80)], 0, 1, []), ('1', [(30, 30), (30, 70)], -16776961, 2, [])])
        r = ET.SubElement(a, 'FR', Color=str(RED))
        for k, t0, t1 in ((0, 0, 3), (1, 3, 0)):
            ET.SubElement(r, 'FS', Kind='0', ObjId=str(1000 + k), StartPtId=str(k * 10), EndPtId=str(k * 10 + 1), StartT=str(t0), EndT=str(t1))
        p = copy.deepcopy(a)
        for k, o in enumerate(p.findall('AO')):
            o.set('DrawOrder', str((1, 2, 0)[k]))
        self.assertGreater(self.diff(p, a), 100)
        self.assertFalse(OS.score(p, a)['perfect'])

    def _unlink(self, a):
        p = copy.deepcopy(a)
        for ap in p.iter('AP'):
            for ac in list(ap):
                ap.remove(ac)
        return p

    def test_cross_layer_link_is_free(self):
        """R-03: 다른 레이어끼리 이음은 렌더러가 레이어마다 따로 그려 영상이 같다 — 만점(옛: glow_group 0)."""
        import sfa_objscore as OS
        from test_sfa_objscore import frame, BLACK, RED
        a = frame([('1', [(20, 50), (80, 50)], BLACK, 0, [(0, 10)]), ('1', [(50, 20), (50, 80)], RED, 1, [(0, 0)])], glow={1})
        ET.SubElement(a, 'LayerDef', ID='1', Visible='true')
        a.findall('AO')[1].set('LayerId', '1')
        p = self._unlink(a)
        self.assertEqual(self.diff(p, a), 0)
        self.assertTrue(OS.score(p, a)['perfect'])

    def test_glow_only_link_is_free(self):
        """R-03: 선이 안 보이는 글로우끼리 이음은 글로우 → 글로우 순서가 같아 영상이 같다 — 만점."""
        import sfa_objscore as OS
        from test_sfa_objscore import frame
        a = frame([('1', [(20, 50), (80, 50)], 0, 0, [(0, 10)]), ('1', [(50, 20), (50, 80)], 0, 1, [(0, 0)])], glow={0, 1})
        a.findall('AO')[1].set('GlowColor', str(0xFF0000))
        p = self._unlink(a)
        self.assertEqual(self.diff(p, a), 0)
        self.assertTrue(OS.score(p, a)['perfect'])


class JudgeContent(unittest.TestCase):
    def test_duplicated_payload_rejected(self):
        """R-04: 목록은 전체인데 내용이 한 장 반복이면 내용 검사에서 떨어진다."""
        import hashlib
        import seq_judge as J
        nd = 4
        tok0 = [np.arange(5 + i) for i in range(3)]
        ents = [dict(frame_hash=hashlib.sha1(np.asarray(t, np.int32).tobytes()).hexdigest()[:16]) for t in tok0]
        good = types.SimpleNamespace(meta=dict(dirs=[[0, 0]] * nd), tok0=tok0, tok=[[t + d for d in range(nd)] for t in tok0],
                                     img=np.stack([np.full((2, 2, 3), k, np.uint8) for k in range(3 * nd)]))
        self.assertEqual(J.content_ok(good, dict(entries=ents)), (True, ''))
        bad = copy.copy(good)
        bad.tok0 = [tok0[0]] * 3
        self.assertFalse(J.content_ok(bad, dict(entries=ents))[0])
        bad = copy.copy(good)
        bad.tok = [good.tok[0]] * 3
        self.assertFalse(J.content_ok(bad, dict(entries=ents))[0])


class FallbackExport(unittest.TestCase):
    def test_promote(self):
        """R-05: 예비 저장본이 최신이면 전송 전에 본 파일로, 낡은 예비 파일은 지운다."""
        import ckpt_files
        with tempfile.TemporaryDirectory() as d:
            m, f = os.path.join(d, 'ckpt.pt'), os.path.join(d, 'ckpt.pt.fallback')
            open(m, 'w').write('old')
            time.sleep(0.02)
            open(f, 'w').write('new')
            os.utime(f, (time.time() + 5, time.time() + 5))
            self.assertEqual(ckpt_files.promote(d), 'promoted')
            self.assertEqual(open(m).read(), 'new')
            self.assertFalse(os.path.exists(f))
            open(f, 'w').write('stale')
            os.utime(f, (time.time() - 100, time.time() - 100))
            self.assertEqual(ckpt_files.promote(d), 'stale-removed')
            self.assertEqual(open(m).read(), 'new')
            self.assertEqual(ckpt_files.promote(d), 'none')


class TrendCap(unittest.TestCase):
    def test_trend_and_official_cap_not_compared(self):
        """R-06: 추세(정답 길이 상한)와 공식(최대 길이) 기록은 다른 조건 — 바로 비교해 '위치를 더 읽음'이라 하지 않는다."""
        import seq_trend as T
        a = dict(judge_N=45, judge_win=0, judge_need=30, judge_delta_median=0, judge_w=640, judge_n_entries=46, judge_reduced=False,
                 val_list={'hash': 'v'}, judge_official=False)
        b = dict(a, judge_win=45, judge_delta_median=95, judge_official=True)
        self.assertNotEqual(T.cond(a), T.cond(b))
        self.assertNotIn('위치를 더 읽음', T.verdict([a, b]))
        c = dict(a, judge_cap='ans4x2+128')
        self.assertEqual(T.cond(c), T.cond(dict(c, judge_win=9)))


if __name__ == '__main__':
    unittest.main()
