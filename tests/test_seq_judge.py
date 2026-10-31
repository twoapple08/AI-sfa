"""판정 장치(11-01, docs/JUDGE-CRITERIA-FINAL-2026-10-31.md §2): 부호 검정·건전성·잘림·입력 교환 대조·평가 목록 고정."""
import json
import os
import sys
import unittest
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1] / 'tools'
sys.path.insert(0, str(TOOLS))

import seq_judge as J  # noqa: E402
import sfa_tokens as K  # noqa: E402
import vec_data as V  # noqa: E402


class FakeJS:
    """그림 없이 정답 토큰만 있는 판정 자료(생성은 가짜 함수로)."""

    def __init__(self, ents, tok, tok0):
        self.meta = dict(dirs=J.DIRS)
        self.ents, self.tok, self.tok0 = ents, tok, tok0

    def __len__(self):
        return len(self.ents)


def real_entries(n=3, groups=None):
    """저장소 평가 목록 앞 n장의 방향별 정답 토큰(렌더 없이)."""
    m = J.load_manifest()
    ents, tok, tok0 = [], [], []
    for k, e in enumerate(m['entries'][:n]):
        z = zipfile.ZipFile(os.path.join(V.ROOT, e['file']))
        xml = z.read(z.namelist()[0])
        base = ET.fromstring(xml)
        tok0.append(K.encode(base, base.findall('Frame')[e['index']])[0])
        row = []
        for d in J.DIRS:
            r = J.transform(ET.fromstring(xml), d)
            row.append(K.encode(r, r.findall('Frame')[e['index']])[0])
        tok.append(row)
        ents.append(dict(file=e['file'], pos=e['pos'], hwr=e['hwr'], group=groups[k] if groups else k, all4=e['all4']))
    return FakeJS(ents, tok, tok0)


class TestStats(unittest.TestCase):
    def test_need_wins_matches_agreed_table(self):
        # 판정 기준 §2: N=30이면 21승, N=18이면 14승. GPT 2차: N=19면 15승
        self.assertEqual(J.need_wins(30), 21)
        self.assertEqual(J.need_wins(18), 14)
        self.assertEqual(J.need_wins(19), 15)
        self.assertAlmostEqual(J.binom_tail(14, 18), 0.0154419, places=6)
        self.assertGreater(J.binom_tail(13, 18), J.ALPHA)

    def test_ties_and_failures_stay_in_n(self):
        r = J.sign_test([5.0, 0.2, -0.3, None, -2.0])
        self.assertEqual((r['N'], r['win'], r['tie'], r['loss'], r['fail']), (5, 1, 2, 1, 1))
        self.assertFalse(r['passed'])
        self.assertEqual(J.vote(J.TIE), 'tie')   # 경계는 동점(비승리)

    def test_health_integer_rule(self):
        mk = lambda bad, n: [dict(ans_n=3, pred_n=0 if k < bad else 3, done=True, oom=False) for k in range(n)]  # noqa: E731
        self.assertTrue(J.health(mk(2, 20))['passed'])
        self.assertFalse(J.health(mk(3, 20))['passed'])
        self.assertTrue(J.health(mk(1, 19))['passed'])
        self.assertFalse(J.health(mk(2, 19))['passed'])
        rows = mk(0, 10)
        rows[0] = dict(ans_n=3, pred_n=0, done=False, oom=True)   # OOM은 실패로 센다
        rows[1] = dict(ans_n=3, pred_n=3, done=False, oom=False)  # 길이 한도 미완료
        h = J.health(rows)
        self.assertEqual((h['oom'], h['unfinished'], h['limit'], h['passed']), (1, 1, 1, False))


class TestClip(unittest.TestCase):
    def test_circle_uses_diameter_and_ratio(self):
        self.assertTrue(J._inside([(40, 40), (60, 40)], '2', 0.5625))
        self.assertTrue(J._inside([(5, 50), (25, 50)], '2', 0.5625))
        self.assertFalse(J._inside([(-5, 50), (15, 50)], '2', 0.5625))
        # 세로: 지름 20%(가로 기준) 원이 위 가장자리 y=5%에 중심 → 반지름 10 > 5·0.5625
        self.assertFalse(J._inside([(40, 5), (60, 5)], '2', 0.5625))

    def test_already_offscreen_is_not_counted(self):
        orig = [('1', [(-10, 50), (110, 50)]), ('1', [(40, 40), (50, 50)])]
        moved = [('1', [(-5, 55), (115, 55)]), ('1', [(97, 40), (102, 50)])]
        self.assertEqual(J.clipped(orig, moved, 0.5625), 1)


class TestEvaluate(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.js = real_entries(3)

    def gen(self, f):
        return lambda i, d: (f(i, d), True, 0.01)

    def test_oracle_wins_memorizer_ties(self):
        js = self.js
        o, _ = J.evaluate(js, self.gen(lambda i, d: js.tok[i][d]), memo=J.memo_baseline(js))
        self.assertEqual((o['judge']['N'], o['judge']['win']), (3, 3))
        self.assertAlmostEqual(o['A'], 100.0)
        self.assertAlmostEqual(o['f1'], 1.0)
        self.assertTrue(o['health']['passed'])
        self.assertEqual(len(o['table16']), 4)
        m, _ = J.evaluate(js, self.gen(lambda i, d: js.tok0[i]), memo=J.memo_baseline(js))
        self.assertEqual((m['judge']['win'], m['judge']['tie']), (0, 3))
        self.assertAlmostEqual(m['B'], 100.0)
        self.assertAlmostEqual(m['A'], J.memo_baseline(js))   # 외움 AI의 A = 외움 기준선

    def test_swapped_inputs_lose(self):
        js = self.js
        o, _ = J.evaluate(js, self.gen(lambda i, d: js.tok[i][1 - d] if d < 2 else js.tok[i][d]), dirs=range(2))
        self.assertEqual(o['judge']['loss'], 3)
        self.assertNotIn('axis', o)   # 2방향이면 축별 진단 없음

    def test_group_votes_once_and_oom_fails(self):
        js = real_entries(3, groups=[0, 0, 1])
        o, _ = J.evaluate(js, self.gen(lambda i, d: js.tok[i][d]), dirs=range(2))
        self.assertEqual((o['judge']['N'], o['judge']['win']), (2, 2))
        o, _ = J.evaluate(js, lambda i, d: None if (i, d) == (2, 1) else (js.tok[i][d], True, 0.01), dirs=range(2))
        self.assertEqual((o['judge']['win'], o['judge']['fail']), (1, 1))
        self.assertEqual(o['health']['oom'], 1)


class TestManifest(unittest.TestCase):
    def test_committed_manifest_matches_tokens(self):
        """저장소 평가 목록이 지금 토큰 변환과 맞는가(바뀌면 build가 멈춘다 — 목록을 다시 만들지 결정해야 함)."""
        m = J.load_manifest()
        self.assertEqual(m['n_units'], len({e['group'] for e in m['entries']}))
        self.assertGreaterEqual(m['n_units'], 30)
        import hashlib
        import numpy as np
        for e in m['entries'][:5]:
            self.assertTrue(J.eligible(dict(dirs=e['dirs'], len0=e['len0'], n0=e['n0']), J.OFFICIAL))
            z = zipfile.ZipFile(os.path.join(V.ROOT, e['file']))
            base = ET.fromstring(z.read(z.namelist()[0]))
            t = K.encode(base, base.findall('Frame')[e['index']])[0]
            self.assertEqual(hashlib.sha1(np.array(t, np.int32).tobytes()).hexdigest()[:16], e['frame_hash'])

    def test_pick_is_reproducible(self):
        files = V.file_list()[::J.EVERY][:4]
        a = J.build_manifest(files, V.ROOT)
        b = J.build_manifest(files, V.ROOT)
        self.assertEqual([(e['file'], e['pos']) for e in a['entries']], [(e['file'], e['pos']) for e in b['entries']])
        m = J.load_manifest()
        got = {e['file']: e['pos'] for e in m['entries']}
        for e in a['entries']:
            self.assertEqual(got.get(e['file']), e['pos'])


if __name__ == '__main__':
    unittest.main()
