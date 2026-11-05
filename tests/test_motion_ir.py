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
        self.assertEqual(ids[0], ids[1]); self.assertEqual(ids[0], ids[2]); self.assertEqual(len(ids[0]), 8)
        frs = [x for x in fr[0].findall('FR') if x.get('ID').startswith('790')]
        self.assertEqual(len(frs), 2)                                     # 망토·가면 둘 다 채움
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


if __name__ == '__main__':
    unittest.main()
