import math, os, sys, unittest
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



class UpperOffFrame(unittest.TestCase):
    """11-05 사용자 '다리밖에 없는데 뭉개진 사람' → '고쳐서라도 사용': 화면 위 밖 상체를 위 바깥 예상 위치로."""
    def _case(self, sh=5):
        import numpy as np
        N, W, H = 6, 800, 450
        def kp(neck_y, pel_y, sh_y=None, hip_y=None):
            K = np.zeros((23, 3)); K[:, 2] = 3.0
            sy = neck_y if sh_y is None else sh_y; hy = pel_y if hip_y is None else hip_y
            K[5] = [390, sy, 3]; K[6] = [410, sy, 3]; K[11] = [392, hy, 3]; K[12] = [408, hy, 3]
            K[0] = [400, sy - 20, 3]
            K[13] = [395, pel_y + 90, 3]; K[14] = [405, pel_y + 90, 3]; K[15] = [395, pel_y + 170, 3]; K[16] = [405, pel_y + 170, 3]
            return K
        frames = list(range(N))
        # 0–1장: 어깨·골반이 화면 위 끝(y 5–15)에 몰림, 2–5장 정상(목 100 → 골반 200)
        t = {0: (None, kp(5, 15, sh_y=sh)), 1: (None, kp(5, 15, sh_y=sh))}
        for f in range(2, N): t[f] = (None, kp(100 + 0 * f, 200))
        B = {k: np.zeros((N, 2)) for k in ('head_t', 'head_b', 'neck', 'pelvis', 'elb_r', 'wri_r', 'elb_l', 'wri_l')}
        for i in range(N):
            ny, py = (5, 15) if i < 2 else (100, 200)
            B['neck'][i] = [400, ny]; B['pelvis'][i] = [400, py]; B['head_t'][i] = [400, ny - 70]; B['head_b'][i] = [400, ny - 5]
            for k, dx in (('elb_r', 30), ('wri_r', 40), ('elb_l', -30), ('wri_l', -40)): B[k][i] = [400 + dx, ny + (40 if 'elb' in k else 90)]
        S = np.full(N, 100.0)
        return t, frames, B, S, W, H

    def test_upper_moves_above_frame(self):
        import numpy as np, stage2_extract as X
        t, frames, B, S, W, H = self._case()
        inf = X.estimate_upper(t, frames, B, S, W, H, 0.0)
        self.assertIn(2, inf[0]); self.assertEqual(inf[3], [])
        # 지어낸 골반(y 15)은 가까운 정상 장 속도로 이어 놓고(여기선 정지 → 200), 몸통 길이 = 정상 장(100), 머리는 목 위
        self.assertEqual(list(B['pelvis'][0]), [400, 200])
        self.assertAlmostEqual(float(np.linalg.norm(B['neck'][0] - B['pelvis'][0])), 100.0, places=3)
        self.assertLess(B['head_t'][0][1], B['neck'][0][1]); self.assertLess(B['neck'][0][1], B['pelvis'][0][1])
        # 정상 장은 그대로
        self.assertEqual(list(B['neck'][4]), [400, 100])

    def test_small_figure_not_triggered(self):
        """멀리 작은 인물(몸통 배율 작음)이 위 끝에 닿은 정도는 건드리지 않는다(nkm_15 0장)."""
        import numpy as np, stage2_extract as X
        t, frames, B, S, W, H = self._case(sh=8)   # 어깨 y 8 > 0.6 × 몸통 10
        S = np.full(len(frames), 10.0)
        self.assertEqual(sum(map(len, X.estimate_upper(t, frames, B, S, W, H, 0.0))), 0)


class ExtrapolateEdit(unittest.TestCase):
    def test_extrapolate_last_frame(self):
        import motion_ir as M
        ir = make_ir([60, 62, 64, 66], [1, 1, 1, 1]); a = ir['actors'][0]; N = ir['frames']
        a['joints']['pelvis'] = [[10 * n, 50] for n in range(N)]
        for k in ('hidden', 'smear', 'thickness'): a[k] = [[] for _ in range(N)]
        out = M.apply_edits(ir, [dict(frames=[3, 3], op='extrapolate')])
        self.assertEqual(out['actors'][0]['joints']['pelvis'][3], [30, 50])   # 10·2 + (20−10)
        self.assertEqual(out['actors'][0]['inferred'][3], list(range(1, 11)))


class Stage5Report(unittest.TestCase):
    def test_seam_ratio_continuous_vs_jump(self):
        """이음매 비율: 실제로 이어진 동작을 조각낸 것은 작고, 같은 조각을 반복(끝 → 처음으로 튐)하면 크다."""
        import motion_tokens as MT, stage5_report as RP
        from stage3_pack import _slice
        xs = [50 + 3 * (i % 10) for i in range(40)]
        ir = make_ir(xs, [1] * 40)
        a = ir['actors'][0]; J = a['joints']; N = ir['frames']
        J['pelvis'] = [[30 + n, 50] for n in range(N)]
        for k in J:
            if k != 'pelvis': J[k] = [[p[0] + n, p[1]] for n, p in enumerate(J[k])]
        J['wri_l'] = [[40 + n + 4 * ((n // 5) % 2), 45] for n in range(N)]
        cont = [MT.encode(_slice(ir, s, e)) for s, e in ((0, 14), (14, 26), (26, 40))]
        jump = [MT.encode(_slice(ir, 0, 14))] * 3
        rc, rj = RP.seam_ratio(cont), RP.seam_ratio(jump)
        self.assertTrue(rc and rj)
        self.assertLess(max(rc), min(rj))

    def test_copy_score(self):
        """외우기 검사: 학습 동작 그대로면 베낌 1, 다른 동작이면 0."""
        import motion_tokens as MT, stage5_report as RP
        a = make_ir([50 + 4 * (i % 6) for i in range(30)], [1] * 30)
        b = make_ir([50 + 4 * (i % 6) for i in range(30)], [1] * 30)
        b['actors'][0]['joints']['ank_r'] = [[60 + 3 * (n % 5), 70] for n in range(30)]
        b['actors'][0]['joints']['wri_l'] = [[30, 30 + 2 * (n % 7)] for n in range(30)]
        ta, tb = MT.encode(a), MT.encode(b)
        self.assertEqual(RP.copy_score([ta], [ta])['copy_rate'], 1.0)
        self.assertEqual(RP.copy_score([tb], [ta])['copy_rate'], 0.0)


class Retime(unittest.TestCase):
    def test_retime_matches_target_share_and_holds(self):
        """nian41 리듬 입히기: 그림 안 장은 같은 자세, 그림 유지 비율이 목표에 가깝다."""
        import retime as RT
        xs = [50 + 6 * math.sin(i / 3) + (i % 7) for i in range(120)]
        ir = make_ir(xs, [1] * 120)
        r = RT.retime(ir)
        D = r['actors'][0]['drawings']; J = r['actors'][0]['joints']
        self.assertEqual(D[0][0], 0); self.assertEqual(D[-1][1], 119)
        for s, e in D:
            for n in range(s + 1, e + 1): self.assertEqual(J['wri_r'][n], J['wri_r'][s])
        hs = RT.hold_share(r); tg = RT.target_share()
        self.assertLess(abs(hs['2'] - tg[2]), 0.2)


class Compose(unittest.TestCase):
    def test_compose_loops_and_blends(self):
        """실제 동작 조각 잇기: 짧은 조각은 반복해 MIN_LEN 이상, 이음매 BLEND장, 몸통 크기 T0로 맞춤."""
        import compose as C, math as m
        def clip(verb, src, dx):
            ir = make_ir([60 + (i % 3) for i in range(8)], [1] * 8)
            J = ir['actors'][0]['joints']
            for k in J: J[k] = [[p[0] + dx * n, p[1]] for n, p in enumerate(J[k])]
            return dict(layer='ref', src=src, verb=verb, detail='', quality='좋음', frames=8, aspect=0.5625, joints=J)
        lib = [clip('걷기', 'a', 1.0), clip('펀치', 'b', 0.0)]
        ir, picks = C.compose([('걷기', ''), ('펀치', '')], lib, synth=False)
        self.assertEqual([p['src'] for p in picks], ['a', 'b'])
        self.assertEqual(ir['frames'], 24 + C.BLEND + 8)   # 걷기: 8장 × 3번 반복 = 24 ≥ 20 · 펀치: 반복하지 않음(11-06)
        J = ir['actors'][0]['joints']
        H = max(m.hypot(J['head_t'][0][0] - J[a][0][0], (J['head_t'][0][1] - J[a][0][1]) * 0.5625) for a in ('ank_r', 'ank_l'))
        self.assertAlmostEqual(H, C.T0 * C.H_PER_T, places=3)   # 키(머리 위 ~ 먼 발목)를 맞춘다


class GaitCycle(unittest.TestCase):
    """11-06 걷기 출처 선택 1: 애니메이션 원리로 계산한 걷기·달리기 주기."""
    def test_cycle_is_gait_and_feet_stay_planted(self):
        import gait_cycle as GC, gait_eval as G
        for verb, P in (('걷기', 24), ('달리기', 16)):
            c = GC.cycle(verb, cycles=3)
            m = G.metrics(dict(frames=c['frames'], aspect=c['aspect'], actors=[dict(joints=c['joints'])]))
            self.assertTrue(m['gait_like'], verb)
            self.assertEqual(m['period'], P)
            self.assertEqual(m['slide'], 0.0)   # 지지 중 발은 땅에 고정
            J = c['joints']   # 다리 길이 유지(두 뼈 역기구학)
            for n in range(c['frames']):
                for sd in 'rl':
                    th = math.hypot(J['pelvis'][n][0] - J['kne_' + sd][n][0], (J['pelvis'][n][1] - J['kne_' + sd][n][1]) * c['aspect']) / 4.0
                    self.assertAlmostEqual(th, GC.THIGH, places=6)

    def test_speed_words(self):
        import gait_cycle as GC
        self.assertGreater(GC.params('걷기', '천천히 걷는다')['period'], GC.params('걷기', '')['period'])
        self.assertLess(GC.params('달리기', '전력으로 달린다')['period'], GC.params('달리기', '')['period'])

    def test_compose_uses_synth_and_camera_keeps_on_screen(self):
        import compose as C
        ir, picks = C.compose([('걷기', ''), ('달리기', '')], [])
        self.assertEqual([p['src'] for p in picks], ['synth_걷기', 'synth_달리기'])
        xs = [p[0] for p in ir['actors'][0]['joints']['pelvis']]
        self.assertLessEqual(max(xs) - min(xs), C.CAM_HI - C.CAM_LO + 2)   # 따라가는 카메라: 골반이 화면 가운데 띠 안


class ComposeMargin(unittest.TestCase):
    def test_margin_stops_at_next_action(self):
        """펀치 앞뒤 여유는 '자세 잡기'까지만, 다른 동작(킥) 앞에서 멈춘다."""
        import compose as C
        acts = [dict(verb='착지', **{'from': 0, 'to': 6}), dict(verb='펀치', **{'from': 9, 'to': 15}),
                dict(verb='자세 잡기', **{'from': 18, 'to': 18}), dict(verb='킥', **{'from': 21, 'to': 33})]
        lo, hi = C._bounds(acts, 1)
        self.assertEqual((lo, hi), (6, 21))
        ir = make_ir([60] * 40, [1] * 40)
        s, t, core = C._margin(ir, [True] * 40, 9, 15, '펀치', lo, hi)
        self.assertEqual((s, t, core), (7, 20, 2))
        self.assertEqual(C._margin(ir, [True] * 40, 9, 15, '걷기', lo, hi), (9, 15, 0))   # 걷기·달리기는 늘리지 않음
