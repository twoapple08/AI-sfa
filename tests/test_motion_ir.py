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
        body = [a for a in fr[0].findall('AO') if a.get('ID') == '4560002'][0]
        self.assertEqual(body.get('Color'), '-16777216')   # 시트 몸 색(검정)


if __name__ == '__main__':
    unittest.main()
