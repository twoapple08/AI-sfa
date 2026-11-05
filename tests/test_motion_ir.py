"""움직임 중간 표현 v1: 추출 → 컴파일 왕복이 기본 11객체를 그대로 되살리는지(비공개 자료 없이 합성 장면으로)."""
import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))


def scene():
    from stickman_clip import person_aos
    import motion_ir as M
    sx, sy = 16.0, 9.0
    frames = []
    for n in range(3):
        J = dict(head_t=(8.0, 1.0 + 0.1 * n), head_b=(8.0, 2.0 + 0.1 * n), neck=(8.0, 2.4), pelvis=(8.1, 4.6),
                 elb_r=(9.0, 3.2), wri_r=(9.8, 3.0 - 0.2 * n), elb_l=(7.0, 3.3), wri_l=(6.4, 3.9),
                 kne_r=(8.8, 5.8), ank_r=(9.0, 7.2), kne_l=(7.4, 5.9), ank_l=(7.2, 7.3))
        vis = [o for o in range(1, 12) if not (n == 1 and o == 4)]          # 1장: 오른 아래팔 숨김
        xml = person_aos(n, 0, J, lambda p: (p[0] / sx * 100, p[1] / sy * 100), 'red', 1.5, visible_segments=vis)
        i = xml.find('ID="4560002" ')
        j = xml.find('ThicknessScale="', i) + len('ThicknessScale="')
        xml = xml[:j] + '2.250' + xml[xml.find('"', j):]                        # 몸통만 다른 굵기
        frames.append(f'<Frame BackgroundColor="-1" ID="{5000 + n}" Position="{n}"><LayerDef ID="0" Name="Layer 1" Visible="true" Locked="false" />{xml}</Frame>')
    root = ET.fromstring('<Sequence Name="t" HeightWidthRatio="0.5625" RatioX="16" RatioY="9" FrameCount="3" BackgroundColor="-1">' + ''.join(frames) + '</Sequence>')
    return M, root


class MotionIRTest(unittest.TestCase):
    def test_roundtrip_exact(self):
        M, root = scene()
        ir = M.extract(root)
        self.assertEqual(ir['schema'], 'motion-ir/1')
        a = ir['actors'][0]
        self.assertEqual(a['color'], 'red')
        self.assertEqual(a['hidden'][1], [4])
        self.assertEqual(a['thickness'][0]['2'], 2.25)
        self.assertEqual(sorted(a['joints']), sorted(M.JOINTS))
        out = M.compile_ir(ir)
        A, B = M.base_signature(root), M.base_signature(out)
        self.assertEqual(set(A), set(B))
        for k in A:
            self.assertEqual(A[k][:3], B[k][:3], k)
            for p, q in zip(A[k][3], B[k][3]):
                self.assertEqual((p[0], p[1], p[4]), (q[0], q[1], q[4]), k)
                self.assertLessEqual(abs(p[2] - q[2]), 0.002)
                self.assertLessEqual(abs(p[3] - q[3]), 0.002)

    def test_facing_field(self):
        """몸 방향 칸(가면 방향 1단계): 추출 시 모름(null), 값을 넣어도 컴파일 결과(기본 뼈대)는 같다."""
        M, root = scene()
        ir = M.extract(root)
        self.assertEqual(ir['actors'][0]['facing'], [None, None, None])
        a = M.base_signature(M.compile_ir(ir))
        ir['actors'][0]['facing'] = [0.0, 90.0, 180.0]
        self.assertEqual(a, M.base_signature(M.compile_ir(ir)))

    def test_smear_slot_not_drawn(self):
        """'스미어로 대체' 표시 객체는 그리지 않는다(색 0) — 관절 위치는 남는다(사용자 11-05)."""
        M, root = scene()
        ir = M.extract(root)
        ir['actors'][0]['smear'][2] = [3, 4]
        out = M.compile_ir(ir)
        f = out.findall('Frame')[2]
        col = {a.get('ID'): a.get('Color') for a in f.findall('AO')}
        self.assertEqual(col['4560003'], '0')
        self.assertEqual(col['4560004'], '0')
        self.assertNotEqual(col['4560005'], '0')
        self.assertIsNotNone(ir['actors'][0]['joints']['wri_r'][2])



class CharSheetTest(unittest.TestCase):
    SHEET = Path(__file__).resolve().parents[1] / 'data' / 'templates' / 'character_sheet_v2_example.sfa'

    def test_read_example_sheet(self):
        import char_sheet as CS
        s = CS.read(str(self.SHEET))
        self.assertEqual(sorted(s['joints']), sorted(['head_t', 'head_b', 'neck', 'pelvis', 'elb_r', 'wri_r', 'elb_l', 'wri_l', 'kne_r', 'ank_r', 'kne_l', 'ank_l']))
        self.assertEqual(sorted((a['bone'], len(a['objects'])) for a in s['accessories']), [('head', 5), ('torso', 3)])   # 가면·망토

    def test_apply_follows_bone_and_keeps_ids(self):
        """액세서리는 붙은 부위를 따라 옮겨지고, 객체 ID는 모든 장에서 같고 점 ID는 장마다 새로."""
        import char_sheet as CS
        M, root = scene()
        ir = M.extract(root)
        out = M.compile_ir(ir, sheets={0: CS.read(str(self.SHEET))})
        fr = out.findall('Frame')
        acc = [[a for a in f.findall('AO') if int(a.get('ID')) >= CS.ACC_AO0] for f in fr]
        self.assertEqual(len(acc[0]), 8)
        self.assertEqual([a.get('ID') for a in acc[0]], [a.get('ID') for a in acc[2]])
        p0 = {p.get('ID') for a in acc[0] for p in a.findall('AP')}
        p2 = {p.get('ID') for a in acc[2] for p in a.findall('AP')}
        self.assertFalse(p0 & p2)
        for f in fr:   # 한 장 안 점 ID 중복 없음(액세서리 여러 개 포함)
            ids = [p.get('ID') for a in f.findall('AO') for p in a.findall('AP')]
            self.assertEqual(len(ids), len(set(ids)))
        # 인물 전체를 오른쪽으로 5% 옮기면 가면·망토도 정확히 5% 따라 옮겨진다
        for v in ir['actors'][0]['joints'].values():
            v[2] = [v[0][0] + 5.0, v[0][1]]
        out2 = M.compile_ir(ir, sheets={0: CS.read(str(self.SHEET))})
        a0 = [a for a in out2.findall('Frame')[0].findall('AO') if int(a.get('ID')) >= CS.ACC_AO0]
        a2 = [a for a in out2.findall('Frame')[2].findall('AO') if int(a.get('ID')) >= CS.ACC_AO0]
        for x, y in zip(a0, a2):
            for p, q in zip(x.findall('AP'), y.findall('AP')):
                self.assertAlmostEqual(float(q.get('X')) - float(p.get('X')), 5.0, places=2)
                self.assertAlmostEqual(float(q.get('Y')), float(p.get('Y')), places=2)
        # 머리·가면 흰 채우기(사용자 11-05): 머리 Kind 1 + 가면 고리 Kind 0(선 5개, 고리 순서로 이어짐)
        frs = fr[0].findall('FR')
        self.assertTrue(any(x.find('FS').get('Kind') == '1' and x.get('Color') == '-1' for x in frs))
        kind0 = [x for x in frs if x.find('FS').get('Kind') == '0']
        self.assertEqual(sorted(len(x.findall('FS')) for x in kind0), [3, 5])   # 망토(곡선 3) + 가면(직선 5), 11-05 망토도 흰색
        mask = [x for x in kind0 if len(x.findall('FS')) == 5]
        self.assertEqual(mask[0].get('Color'), '-1')
        fs = mask[0].findall('FS')
        self.assertEqual(len(fs), 5)
        pos = {p.get('ID'): (round(float(p.get('X')), 3), round(float(p.get('Y')), 3)) for a in fr[0].findall('AO') for p in a.findall('AP')}
        for x, y in zip(fs, fs[1:] + fs[:1]):          # 한 변의 끝 = 다음 변의 시작(같은 자리)
            ex, ey = pos[x.get('EndPtId')]; sx, sy = pos[y.get('StartPtId')]
            self.assertLess(abs(ex - sx) + abs(ey - sy), 0.01)
        body = [a for a in fr[0].findall('AO') if a.get('ID') == '4560002'][0]
        self.assertEqual(body.get('Color'), '-16777216')   # 시트 몸 색(검정)


class FacingViewTest(unittest.TestCase):
    SHEET = Path(__file__).resolve().parents[1] / 'data' / 'templates' / 'character_sheet_v2_example.sfa'

    def test_view_follows_facing(self):
        """가면 방향 2/3: 장마다 몸 방향에 가장 가까운 시트 칸. 후면이면 가면(머리 닫힌 모양·흰 채움) 없음.
        칸마다 객체 ID 구간이 달라 같은 ID가 장에 따라 다른 모양이 되지 않는다."""
        import char_sheet as CS
        M, root = scene()
        ir = M.extract(root)
        ir['actors'][0]['facing'] = [0.0, 100.0, 170.0]          # 정면 · 우측(가장 가까움) · 후면
        out = M.compile_ir(ir, sheets={0: CS.read_all(str(self.SHEET))})
        fr = out.findall('Frame')
        ids = [sorted(int(a.get('ID')) - CS.ACC_AO0 for a in f.findall('AO') if int(a.get('ID')) >= CS.ACC_AO0) for f in fr]
        self.assertTrue(all(0 <= i < 100 for i in ids[0]) and len(ids[0]) == 8)
        self.assertTrue(all(100 <= i < 200 for i in ids[1]) and len(ids[1]) == 8)
        self.assertTrue(all(200 <= i < 300 for i in ids[2]) and len(ids[2]) == 3)   # 망토만
        self.assertEqual(sorted(len(x.findall('FS')) for x in fr[2].findall('FR') if x.find('FS').get('Kind') == '0'), [3])   # 후면: 망토 채움만, 가면 없음
        kinds = {}
        for f in fr:
            for a in f.findall('AO'):
                k = (a.get('LayerId'), a.get('TypeId'))
                self.assertEqual(kinds.setdefault(a.get('ID'), k), k)
        self.assertEqual(CS.pick_view({'정면': 'f', '우측': 'r', '후면': 'b', '좌측': 'l'}, None), 'f')
        self.assertEqual(CS.pick_view({'정면': 'f', '우측': 'r', '후면': 'b', '좌측': 'l'}, 300.0), 'l')


class RigTurnTest(unittest.TestCase):
    SHEET = Path(__file__).resolve().parents[1] / 'data' / 'templates' / 'character_sheet_v2_example.sfa'

    def test_continuous_turn(self):
        """연속 방향(11-05): 칸 사이는 두 칸 모양을 섞고, 후면에 없는 가면은 투명해진다. 객체 ID는 칸과 상관없이 하나이고
        첫 장부터 항상 나온다(앱 '처음 나온 순서' 레이어 버그 방지). 망토(곡선 3개 고리)도 흰 채우기."""
        import char_sheet as CS
        M, root = scene()
        ir = M.extract(root)
        ir['actors'][0]['facing'] = [0.0, 45.0, 170.0]
        out = M.compile_ir(ir, sheets={0: CS.rig(CS.read_all(str(self.SHEET)))})
        fr = out.findall('Frame')
        ids = [[a.get('ID') for a in f.findall('AO') if int(a.get('ID')) >= CS.ACC_AO0] for f in fr]
        self.assertEqual(ids[0], ids[1]); self.assertEqual(ids[0], ids[2])
        self.assertEqual(len(ids[0]), 35)   # 망토 뒤·앞 사본 (채우기 전용 투명 테두리 12 + 곡선 3) × 2 + 가면 5
        # 망토 채우기는 그 장 모양을 따른 투명 테두리를 가리키고, 테두리는 망토 선보다 먼저(아래) 나온다(11-05 페인트가 선을 가림)
        aos = fr[0].findall('AO')
        pos = {a.get('ID'): i for i, a in enumerate(aos)}
        cape_fr = [x for x in fr[0].findall('FR') if len(x.findall('FS')) == 12]
        self.assertEqual(len(cape_fr), 2)
        for x in cape_fr:
            hid = [fs.get('ObjId') for fs in x.findall('FS')]
            self.assertTrue(all(next(a for a in aos if a.get('ID') == h).get('Color') == '0' for h in hid))
            base = 500 if int(hid[0]) - CS.ACC_AO0 >= 500 else 0
            self.assertLess(max(pos[h] for h in hid), pos[str(CS.ACC_AO0 + base)])
        frs = [x for x in fr[0].findall('FR') if x.get('ID').startswith('790')]
        self.assertEqual(len(frs), 3)                                     # 망토 두 사본·가면 모두 채움
        self.assertEqual(sorted(len(x.findall('FS')) for x in frs), [5, 12, 12])
        alpha = lambda c: (int(c) & 0xFFFFFFFF) >> 24
        mask = lambda f: [a for a in f.findall('AO') if int(a.get('ID')) >= CS.ACC_AO0 and (int(a.get('Color')) & 0xFFFFFF) == 0xFF0000]
        self.assertEqual({alpha(a.get('Color')) for a in mask(fr[0])}, {255})
        self.assertEqual({alpha(a.get('Color')) for a in mask(fr[2])}, {0})     # 170°: 가면 사라짐(후면 쪽)
        # 45°: 정면·우측 모양의 중간(정면 0° 결과와 다르고, 90° 결과와도 다름)
        ir['actors'][0]['facing'] = [0.0, 45.0, 90.0]
        for v in ir['actors'][0]['joints'].values():
            v[1] = v[0]; v[2] = v[0]
        o2 = M.compile_ir(ir, sheets={0: CS.rig(CS.read_all(str(self.SHEET)))}).findall('Frame')
        xs = [[float(p.get('X')) for a in mask(f) for p in a.findall('AP')] for f in o2]
        for i in range(len(xs[0])):
            lo, hi = sorted((xs[0][i], xs[2][i]))
            self.assertTrue(lo - 1e-6 <= xs[1][i] <= hi + 1e-6)


class CapeSimTest(unittest.TestCase):
    SHEET = Path(__file__).resolve().parents[1] / 'data' / 'templates' / 'character_sheet_v2_example.sfa'

    def compile(self, shift, facing):
        import char_sheet as CS
        M, root = scene()
        ir = M.extract(root)
        a = ir['actors'][0]
        for v in a['joints'].values():                       # 같은 자세로 오른쪽으로 장마다 shift만큼 이동
            for n in range(3): v[n] = [v[0][0] + shift * n, v[0][1]]
        a['facing'] = facing
        return CS, M.compile_ir(ir, sheets={0: CS.rig(CS.read_all(str(self.SHEET)))}).findall('Frame')

    def test_cape_lags_and_depth(self):
        """망토(11-05): 몸이 움직이면 밑단이 늦게 따라온다(관성), 고정점(목)은 따라간다. 정면 쪽은 몸 뒤 사본만, 후면 쪽은 앞 사본만 보인다.
        뒤 사본은 인물 기본 뼈대보다 파일에서 먼저 나온다(앱 '처음 나온 순서' = 뒤)."""
        CS, fr = self.compile(2.0, [0.0, 0.0, 180.0])
        def cape(f, base):
            return [a for a in f.findall('AO') if CS.ACC_AO0 + base <= int(a.get('ID')) < CS.ACC_AO0 + base + 3]
        alpha = lambda a: (int(a.get('Color')) & 0xFFFFFFFF) >> 24
        self.assertEqual({alpha(a) for a in cape(fr[0], 500)}, {255}); self.assertEqual({alpha(a) for a in cape(fr[0], 0)}, {0})
        self.assertEqual({alpha(a) for a in cape(fr[2], 0)}, {255}); self.assertEqual({alpha(a) for a in cape(fr[2], 500)}, {0})
        order = [a.get('ID') for a in fr[0].findall('AO')]
        self.assertLess(order.index(str(CS.ACC_AO0 + 500)), order.index('4560002'))
        xs = lambda f: [float(p.get('X')) for a in cape(f, 500) for p in a.findall('AP')]
        moved = [x1 - x0 for x0, x1 in zip(xs(fr[0]), xs(fr[1]))]
        self.assertAlmostEqual(max(moved), 2.0, places=2)      # 고정점(목)은 몸과 같이 2%
        self.assertLess(min(moved), 1.9)                         # 밑단은 늦게(관성)

    def test_face_visible_cape_behind(self):
        """11-05 '망토가 몸을 뚫음': 가면(얼굴)이 조금이라도 보이는 각도에서는 망토 앞 사본이 완전히 투명(몸 뒤 사본만)."""
        import char_sheet as CS
        for yaw in range(0, 360, 5):
            m = CS.rig(CS.read_all(str(self.SHEET)))
            have = [v for v in CS.VIEW_ANGLE if v in m['views']]
            va, vb, t = CS._neighbors(float(yaw), have)
            A, B = m['accs'][1]['per'].get(va), m['accs'][1]['per'].get(vb)   # 가면
            mask_a = 1.0 if (A is not None and B is not None) else (max(0.0, 1 - t / 0.6) if A is not None else max(0.0, (t - 0.4) / 0.6) if B is not None else 0.0)
            if mask_a > 0:
                self.assertEqual(CS._depth_alpha(float(yaw)), 0.0, yaw)

    def test_hem_stays(self):
        """11-05 '망토 아랫선이 자꾸 사라짐'(밑단 두 끝이 같은 점이 됨): 밑단 끝은 시트 연결대로 이어진 가장자리 아래 끝과 같고, 길이가 0이 되지 않는다."""
        import math as m
        CS, fr = self.compile(2.0, [0.0, 0.0, 0.0])
        info = CS.flex_info(CS.rig(CS.read_all(str(self.SHEET)))['accs'][0]['ref'])
        for f in fr:
            ao = {a.get('ID'): [(float(p.get('X')), float(p.get('Y'))) for p in a.findall('AP')] for a in f.findall('AO')}
            hem = ao[str(CS.ACC_AO0 + 500 + info['hem'])]
            self.assertGreater(m.dist(CS.iso(hem[0]), CS.iso(hem[2])), 0.3)
            for e in (0, 2):
                oi, pj = info['hem_conn'][e]
                self.assertEqual(hem[e], ao[str(CS.ACC_AO0 + 500 + oi)][pj])

    def test_same_fill_color_no_underlay(self):
        """11-05 사용자: 채우기 색이 테두리 색과 같으면 선 아래 따로 까는 작업 없이 망토 곡선에 바로 채운다."""
        import char_sheet as CS
        M, root = scene()
        ir = M.extract(root)
        rg = CS.rig(CS.read_all(str(self.SHEET)))
        cape = rg['accs'][0]['ref']
        self.assertEqual(cape['fill_color'], '-1')                 # 시트에 채우기가 없으면 흰색
        cape['fill_color'] = cape['objects'][0]['color']           # 테두리와 같은 색
        fr = M.compile_ir(ir, sheets={0: rg}).findall('Frame')[0]
        helpers = [a for a in fr.findall('AO') if 300 <= (int(a.get('ID')) - CS.ACC_AO0) % 500 < 400]
        self.assertEqual(helpers, [])
        cape_fr = [x for x in fr.findall('FR') if len(x.findall('FS')) == 3]
        self.assertEqual(len(cape_fr), 2)
        rgb = lambda c: int(c) & 0xFFFFFF
        self.assertEqual({rgb(x.get('Color')) for x in cape_fr}, {rgb(cape['objects'][0]['color'])})   # 채우기 = 테두리 색
        self.assertTrue(all(int(fs.get('ObjId')) - CS.ACC_AO0 in (0, 1, 2, 500, 501, 502) for x in cape_fr for fs in x.findall('FS')))

    def test_hem_min_width(self):
        """11-05 사용자: 밑단은 '지금 크기'(칸별 기준, 몸통 길이 대비)가 최소. 시트가 더 크면 시트 크기, 작으면 기준 크기."""
        import copy as cp, math as m
        import char_sheet as CS
        M, root = scene()
        base_ir = M.extract(root)
        def hem_ratio(scale):
            rg = CS.rig(CS.read_all(str(self.SHEET)))
            for v, acc in rg['accs'][0]['per'].items():
                if acc is None: continue
                for o in acc['objects']:
                    for p in o['pts']: p['uv'] = (p['uv'][0], p['uv'][1] * scale)   # 옆으로 넓히기/좁히기
            ir = cp.deepcopy(base_ir); ir['actors'][0]['facing'] = [0.0, 0.0, 0.0]
            fr = M.compile_ir(ir, sheets={0: rg}).findall('Frame')[0]
            info = CS.flex_info(rg['accs'][0]['ref'])
            ao = {a.get('ID'): [(float(p.get('X')), float(p.get('Y'))) for p in a.findall('AP')] for a in fr.findall('AO')}
            hem = ao[str(CS.ACC_AO0 + 500 + info['hem'])]
            J = ir['actors'][0]['joints']; L = m.dist(CS.iso(J['neck'][0]), CS.iso(J['pelvis'][0]))
            sheet_w = m.dist(*[rg['accs'][0]['per']['정면']['objects'][oi]['pts'][bot]['uv'] for oi, top, bot in info['edges']])
            return m.dist(CS.iso(hem[0]), CS.iso(hem[2])) / L, sheet_w
        w_big, s_big = hem_ratio(3.0)
        self.assertGreater(s_big, CS.HEM_MIN['정면'])
        self.assertAlmostEqual(w_big, s_big, delta=0.1 * s_big)                   # 크면 시트 그대로
        w_small, s_small = hem_ratio(0.3)
        self.assertLess(s_small, CS.HEM_MIN['정면'])
        self.assertAlmostEqual(w_small, CS.HEM_MIN['정면'], delta=0.1)            # 작으면 기준 크기

    def test_reset_on_cut(self):
        """컷 등으로 몸통 길이의 1.2배 넘게 뛰면 처음부터(망토가 날아가지 않는다)."""
        CS, fr = self.compile(60.0, [0.0, 0.0, 0.0])
        xs = lambda f: [float(p.get('X')) for a in f.findall('AO') if CS.ACC_AO0 + 500 <= int(a.get('ID')) < CS.ACC_AO0 + 503 for p in a.findall('AP')]
        moved = [x1 - x0 for x0, x1 in zip(xs(fr[0]), xs(fr[1]))]
        for m in moved: self.assertAlmostEqual(m, 60.0, places=2)


class FirstOrderTest(unittest.TestCase):
    SHEET = Path(__file__).resolve().parents[1] / 'data' / 'templates' / 'character_sheet_v2_example.sfa'

    def test_absent_actor_declared_first(self):
        """11-05 망토 레이어 버그: 첫 장에 없던 인물도 첫 장에 투명하게 미리 등록 → 파일 전체 '처음 나온 순서'가 인물 순서와 같다
        (인물 0의 망토 뒤 사본·몸·액세서리가 모두 인물 1보다 먼저)."""
        import copy as cp
        import char_sheet as CS
        M, root = scene()
        ir = M.extract(root)
        b = cp.deepcopy(ir['actors'][0]); b['slot'] = 1; b['color'] = 'blue'
        for v in b['joints'].values():
            for n in range(3): v[n] = [v[n][0] + 30, v[n][1]]
        a = ir['actors'][0]
        for v in a['joints'].values(): v[0] = None          # 인물 0은 첫 장에 없음
        ir['actors'].append(b)
        sh = CS.rig(CS.read_all(str(self.SHEET)))
        out = M.compile_ir(ir, sheets={0: sh, 1: sh})
        seen = []
        for f in out.findall('Frame'):
            for x in f.findall('AO'):
                if x.get('ID') not in seen: seen.append(x.get('ID'))
        slots = [M._slot_of(i) for i in seen]
        self.assertEqual(slots, sorted(slots))
        f0 = out.findall('Frame')[0]
        self.assertTrue(all(x.get('Color') == '0' for x in f0.findall('AO') if M._slot_of(x.get('ID')) == 0))
        ids = [p.get('ID') for x in f0.findall('AO') for p in x.findall('AP')]
        self.assertEqual(len(ids), len(set(ids)))


if __name__ == '__main__':
    unittest.main()
