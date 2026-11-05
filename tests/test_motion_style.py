import os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))
import motion_style as MS

NAMES = ['head_t', 'head_b', 'neck', 'pelvis', 'elb_r', 'wri_r', 'elb_l', 'wri_l', 'kne_r', 'ank_r', 'kne_l', 'ank_l']


def make_ir(wri_keys, holds):
    """wri_keys[i] = i번째 그림의 오른 손목 x(%), holds[i] = 그 그림 유지 장 수. 나머지 관절은 고정."""
    frames, D, xs = 0, [], []
    for x, h in zip(wri_keys, holds):
        D.append([frames, frames + h - 1]); xs += [x] * h; frames += h
    base = dict(head_t=[50, 20], head_b=[50, 28], neck=[50, 30], pelvis=[50, 50], elb_r=[55, 35], elb_l=[45, 35],
                wri_l=[45, 45], kne_r=[52, 65], ank_r=[52, 80], kne_l=[48, 65], ank_l=[48, 80])
    J = {k: [list(base[k]) for _ in range(frames)] for k in NAMES if k != 'wri_r'}
    J['wri_r'] = [[x, 40] for x in xs]
    return dict(frames=frames, aspect=0.5625, actors=[dict(slot=0, joints=J, drawings=D)])


class MotionStyle(unittest.TestCase):
    def test_hold_counts_skip_ends(self):
        a = MS.measure(make_ir([60, 60.5, 61, 61.5, 62], [5, 2, 3, 2, 7]))['actors'][0]
        self.assertEqual(a['hold'], {'1': 0, '2': 2, '3': 1, '4+': 0})   # 첫·끝 그림(5·7장) 제외

    def test_anticipation_and_stop(self):
        # 손목이 뒤로(55) 빠졌다가 앞으로 크게(80) 치고, 그 그림을 5장 멈춘다
        a = MS.measure(make_ir([60, 60, 57, 55, 80, 80, 80], [2, 2, 2, 2, 5, 2, 2]))['actors'][0]
        self.assertGreaterEqual(a['anticipation']['with_antic'], 1)
        self.assertGreaterEqual(a['stop_after_fast']['with_stop'], 1)

    def test_no_backswing_no_anticipation(self):
        # 반례: 뒤로 빼지 않고 바로 치면 예비 동작이 없어야 한다. 유지 장이 모두 같으면 멈춤도 없어야 한다
        a = MS.measure(make_ir([60, 60, 60, 60, 80, 80, 80], [2, 2, 2, 2, 2, 2, 2]))['actors'][0]
        self.assertEqual(a['anticipation']['with_antic'], 0)
        self.assertEqual(a['stop_after_fast']['with_stop'], 0)

    def test_no_drawings(self):
        ir = make_ir([60], [10]); ir['actors'][0]['drawings'] = []
        self.assertEqual(MS.measure(ir)['actors'][0]['drawings'], 0)


if __name__ == '__main__':
    unittest.main()


class HoldDrawings(unittest.TestCase):
    def test_hold_copies_middle_and_keeps_original(self):
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))
        import motion_ir as M
        ir = make_ir([60, 70, 80], [3, 2, 3])
        # 부드러운 판처럼 그림 구간 안에서도 손목을 조금씩 움직여 둔다
        for n in range(ir['frames']): ir['actors'][0]['joints']['wri_r'][n][0] += n * 0.1
        a0 = ir['actors'][0]
        a0['thickness'] = [{'1': 1.0 + n} for n in range(ir['frames'])]
        a0['facing'] = [float(n) for n in range(ir['frames'])]
        h = M.hold_drawings(ir)['actors'][0]
        for s, e in a0['drawings']:
            m = (s + e) // 2
            for n in range(s, e + 1):
                self.assertEqual(h['joints']['wri_r'][n], a0['joints']['wri_r'][m])
                self.assertEqual(h['thickness'][n], a0['thickness'][m])
                self.assertEqual(h['facing'][n], a0['facing'][m])
        self.assertNotEqual(a0['joints']['wri_r'][0], a0['joints']['wri_r'][1])   # 원본은 바뀌지 않음

    def test_hold_without_drawings_is_identity(self):
        import motion_ir as M
        ir = make_ir([60, 70], [2, 2]); ir['actors'][0]['drawings'] = []
        self.assertEqual(M.hold_drawings(ir)['actors'][0]['joints'], ir['actors'][0]['joints'])


class CalmLimbs(unittest.TestCase):
    def _ir(self, body_move=0.0):
        xs = [60, 75, 58, 76, 57, 74, 59, 77, 60, 75]   # 손목이 장마다 앞뒤로 진동
        ir = make_ir(xs, [1] * len(xs))
        J = ir['actors'][0]['joints']
        for n in range(ir['frames']):
            for k in J:
                J[k][n][0] += body_move * n
        return ir

    def test_low_score_oscillation_is_calmed(self):
        import motion_ir as M
        ir = self._ir()
        ws = {0: {'r': [2.0] * ir['frames'], 'l': [5.0] * ir['frames']}}
        _, ch = M.calm_limbs(ir, wrist_score=ws)
        self.assertTrue(any(k == 'wri_r' for _, _, k in ch))

    def test_high_score_or_moving_body_kept(self):
        import motion_ir as M
        ir = self._ir()
        ws = {0: {'r': [5.0] * ir['frames'], 'l': [5.0] * ir['frames']}}
        self.assertEqual(M.calm_limbs(ir, wrist_score=ws)[1], [])          # 반례: 점수 높은 진짜 팔 동작
        ir2 = self._ir(body_move=3.0)
        ws2 = {0: {'r': [2.0] * ir2['frames'], 'l': [2.0] * ir2['frames']}}
        self.assertEqual(M.calm_limbs(ir2, wrist_score=ws2)[1], [])        # 반례: 몸 전체가 움직임


class ApplyEdits(unittest.TestCase):
    def test_ops(self):
        import motion_ir as M
        ir = make_ir([60, 70, 80, 90, 100], [2, 2, 2, 2, 2])
        a = ir['actors'][0]; N = ir['frames']
        a['hidden'] = [[] for _ in range(N)]; a['smear'] = [[] for _ in range(N)]
        a['joints']['wri_r'][4] = [200.0, 40.0]                       # 4장 튐
        out = M.apply_edits(ir, [dict(frames=[2, 3], op='smear', objs=[7, 8], cause='스미어'),
                                 dict(frames=[4, 4], op='bridge', joints=['wri_r'], cause='오검출'),
                                 dict(frames=[9, 9], op='drop', cause='판독 불가'),
                                 dict(frames=[0, 0], op='hide', objs=[3])])
        b = out['actors'][0]
        self.assertEqual(b['smear_mark'][2], [7, 8]); self.assertEqual(b['smear'][2], []); self.assertEqual(b['hidden'][0], [3])
        self.assertAlmostEqual(b['joints']['wri_r'][4][0], (70 + 80) / 2)
        self.assertFalse(b['train_mask'][9]); self.assertTrue(b['train_mask'][8])
        self.assertEqual(a['joints']['wri_r'][4][0], 200.0)           # 원본 불변

    def test_bad_ops_rejected(self):
        import motion_ir as M
        ir = make_ir([60, 70], [2, 2])
        with self.assertRaises(ValueError): M.apply_edits(ir, [dict(frames=[0, 0], op='bridge', joints=['wri_r'])])
        with self.assertRaises(ValueError): M.apply_edits(ir, [dict(frames=[0, 9], op='hide', objs=[3])])
        with self.assertRaises(ValueError): M.apply_edits(ir, [dict(frames=[0, 0], op='move')])


class UserSfaIr(unittest.TestCase):
    def test_built_file(self):
        import gzip, json
        p = os.path.join(os.path.dirname(__file__), '..', 'data', 'stage2', 'user_sfa_ir_2026-11-05.jsonl.gz')
        segs = [json.loads(l) for l in gzip.open(p, 'rt', encoding='utf-8')]
        self.assertGreater(len(segs), 100)
        for s in segs[:50]:
            self.assertTrue(s['source']['reference'])                     # 참고용 표시(조건 29 ②)
            self.assertGreaterEqual(s['frames'], 8)
            self.assertEqual(len(s['actors'][0]['joints']['neck']), s['frames'])

    def test_linking_keeps_fig_first(self):
        import user_sfa_to_ir as U
        r = dict(head=[[0, 0], [0, -5]], neck=[0, 0], hip=[0, 10], arms=[['2', [[0, 0], [3, 3], [6, 6]]], ['3', [[0, 0], [-3, 3], [-6, 6]]]],
                 legs=[['4', [[0, 10], [2, 15], [2, 20]]], ['5', [[0, 10], [-2, 15], [-2, 20]]]])
        j = U.joints_of(r)
        self.assertEqual(j['elb_r'], [3, 3]); self.assertEqual(j['ank_l'], [-2, 20])
        r2 = dict(r, arms=r['arms'][:1]); self.assertIsNone(U.joints_of(r2))   # 팔 하나면 표준 뼈대 아님


class MotionTokens(unittest.TestCase):
    def test_roundtrip(self):
        import motion_tokens as MT, math
        ir = make_ir([60, 70, 80, 75], [2, 2, 2, 2])
        t = MT.encode(ir)
        self.assertEqual(t[0], '<motion>'); self.assertEqual(t[-1], '</motion>')
        self.assertTrue(all(x in MT.VOCAB for x in t))
        out = MT.decode(t)
        a, b = ir['actors'][0]['joints'], out['actors'][0]['joints']
        k0 = MT.keyframes(ir['actors'][0], ir['frames'])[0]
        T = math.hypot(a['neck'][k0][0] - a['pelvis'][k0][0], (a['neck'][k0][1] - a['pelvis'][k0][1]) * 0.5625)
        for n in ('wri_r', 'ank_l', 'neck'):
            self.assertLess(math.hypot(a[n][k0][0] - b[n][0][0], (a[n][k0][1] - b[n][0][1]) * 0.5625) / T, 0.15)

    def test_bad_tokens_skipped(self):
        import motion_tokens as MT
        self.assertIsNone(MT.decode(['<motion>', '<a3>', '</motion>']))


class Stage4Plausible(unittest.TestCase):
    def test_plausible(self):
        import motion_tokens as MT, stage4_pack as P
        ir = make_ir([60], [1])
        self.assertTrue(P.plausible(MT.decode(P.one(ir, 0))))
        bad = make_ir([60], [1]); bad['actors'][0]['joints']['kne_r'][0] = [50, 50.5]; bad['actors'][0]['joints']['ank_r'][0] = [50, 51]
        self.assertFalse(P.plausible(MT.decode(P.one(bad, 0))))   # 반례: 다리가 몸통 쪽으로 접힘


class Stage5(unittest.TestCase):
    def test_continuation_pairs(self):
        import stage5_pack as P
        ir = make_ir([60, 62, 64, 66, 68, 70, 72, 74, 76, 78, 80, 82, 84, 86, 88, 90, 92, 94, 96, 98], [2] * 20)
        rows = P.pairs(ir, None, '글', 'style', 's')
        self.assertEqual(rows[0]['kind'], 'start'); self.assertTrue(any(r['kind'] == 'cont' for r in rows))
        for r in rows:
            if r['kind'] == 'cont': self.assertEqual(len(r['context']) % P.K, 0); self.assertGreater(len(r['context']), 0)

    def test_style_score_separates(self):
        import motion_tokens as MT, stage5_score as S
        two = make_ir([60, 70] * 6, [2] * 12); one = make_ir([60, 70] * 12, [1] * 24)
        a, b = S.style_score([MT.encode(two)]), S.style_score([MT.encode(one)])
        self.assertLess(a['hold_l1'], b['hold_l1'])   # nian41(2장 유지 61%)에 2장 유지가 더 가깝다


class TokensToSfaCape(unittest.TestCase):
    def test_cape_behind_body_front_view(self):
        """11-05 사용자 '망토 레이어가 이상함': 연결부가 read_all만 넘겨 망토가 늘 몸 앞(뒤 사본 없음)이었다.
        정면(facing 없음)에서는 망토 뒤 사본이 있고, 그 DrawOrder가 몸 객체보다 작아야 한다."""
        import motion_tokens as MT, tokens_to_sfa as T, char_sheet as CS, motion_ir as M
        sheet = os.path.join(os.path.dirname(__file__), '..', 'data', 'templates', 'character_sheet_v3_example.sfa')
        ir = make_ir([60, 62, 64, 66, 68, 70, 72, 74, 76, 78, 80, 82], [2] * 12)
        _, root = T.build(MT.encode(ir), sheet, center=True)
        f0 = root.findall('Frame')[0]
        do = {int(a.get('ID')): int(a.get('DrawOrder')) for a in f0.findall('AO')}
        body = [v for k, v in do.items() if 0 <= k - M.AO0 < 100]
        back = [v for k, v in do.items() if 500 <= k - CS.ACC_AO0 < 1000]
        self.assertTrue(body and back)
        self.assertLess(max(back), min(body))

    def test_facing_back_puts_cape_front(self):
        """--facing 180(후면): 가면이 사라지고 망토 앞 사본이 보인다(뒤 사본은 투명)."""
        import motion_tokens as MT, tokens_to_sfa as T, char_sheet as CS
        sheet = os.path.join(os.path.dirname(__file__), '..', 'data', 'templates', 'character_sheet_v3_example.sfa')
        ir = make_ir([60, 62, 64, 66, 68, 70, 72, 74, 76, 78, 80, 82], [2] * 12)
        out, root = T.build(MT.encode(ir), sheet, center=True, facing=180)
        self.assertEqual(out['actors'][0]['facing'][0], 180.0)
        f0 = root.findall('Frame')[0]
        def alpha(fr): return (int(fr.get('Color')) & 0xFFFFFFFF) >> 24
        frs = {int(x.get('ID')) % 10: alpha(x) for x in f0.findall('FR') if 7900000 <= int(x.get('ID')) < 8000000}
        self.assertGreater(frs[0], 0)    # 망토 앞 사본 채움 보임(ID 끝 0)
        self.assertEqual(frs[5], 0)      # 몸 뒤 사본(ID 끝 5) 투명
        self.assertEqual(frs[1], 0)      # 가면 채움 투명(후면)

