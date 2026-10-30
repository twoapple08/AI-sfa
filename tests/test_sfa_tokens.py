import os
import sys
import unittest
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))
import sfa_tokens as K  # noqa: E402


def frame():
    seq = ET.fromstring('<Sequence Name="t" HeightWidthRatio="0.5625" FrameCount="1" BackgroundColor="-1"/>')
    fr = ET.fromstring(
        '<Frame ID="1" Position="0" BackgroundColor="-1">'
        '<LayerDef ID="0" Name="L1" Visible="true" Locked="false"/>'
        '<LayerDef ID="1" Name="L2" Visible="false" Locked="false"/>'
        '<AO ID="10" TypeId="1" Color="-16777216" LayerId="0" DrawOrder="0" ThicknessScale="1.0">'
        '<AP ID="11" Flags="3" Index="0" X="10" Y="20"/><AP ID="12" Flags="9" Index="1" X="-2000000000" Y="30"><AC ConnPtId="21"/></AP></AO>'
        '<AO ID="20" TypeId="3" Color="-65536" LayerId="0" DrawOrder="1" ThicknessScale="0.5" GlowRadius="8" GlowThickness="20" GlowAlpha="200" GlowColor="-1">'
        '<AP ID="21" Flags="8" Index="0" X="40" Y="30"><AC ConnPtId="12"/></AP><AP ID="22" Flags="9" Index="1" X="50" Y="10"/>'
        '<AP ID="23" Flags="9" Index="2" X="60" Y="30"/></AO>'
        '<AO ID="30" TypeId="2" Color="0" LayerId="0" DrawOrder="2"><AP ID="31" Flags="3" Index="0" X="70" Y="40"/><AP ID="32" Flags="9" Index="1" X="80" Y="40"/></AO>'
        '<AO ID="40" TypeId="1" Color="-16777216" LayerId="1" DrawOrder="3"><AP ID="41" Flags="3" Index="0" X="1" Y="1"/><AP ID="42" Flags="9" Index="1" X="2" Y="2"/></AO>'
        '<AO ID="50" TypeId="1" Color="0" LayerId="0" DrawOrder="4"><AP ID="51" Flags="3" Index="0" X="5" Y="5"/><AP ID="52" Flags="9" Index="1" X="6" Y="6"/></AO>'
        '<FR Color="-16711936"><FS Kind="1" ObjId="30"/></FR>'
        '<FR Color="-16711936"><FS Kind="0" ObjId="20" StartPtId="21" EndPtId="23" StartT="0.25" EndT="1.0"/></FR>'
        '</Frame>')
    return seq, fr


class SfaTokensTest(unittest.TestCase):
    def test_roundtrip_structure(self):
        seq, fr = frame()
        toks, st = K.encode(seq, fr)
        self.assertTrue(all(0 <= t < K.VOCAB for t in toks))
        d = K.decode(toks)
        aos = d.findall('AO')
        # 숨긴 레이어(40)·안 보이고 면에도 안 쓰인 것(50)은 빠지고, 투명한 원(30)은 면이 쓰므로 남는다
        self.assertEqual([a.get('TypeId') for a in aos], ['1', '3', '2'])
        self.assertEqual(st['drop_invis'], 1)
        self.assertEqual(aos[1].get('Color'), '-65536')
        self.assertAlmostEqual(float(aos[1].get('ThicknessScale')), 0.5, delta=0.002)
        self.assertEqual(aos[1].get('GlowAlpha'), '200')
        # 아주 먼 직선 끝은 상자로 정확히 잘린다(방향 유지)
        p = aos[0].findall('AP')
        self.assertAlmostEqual(float(p[1].get('X')), K.CLIP[0], delta=0.05)
        # 연결은 양방향으로 복원, 파란점 규칙
        self.assertEqual(p[1].find('AC').get('ConnPtId'), aos[1].findall('AP')[0].get('ID'))
        self.assertEqual(aos[1].findall('AP')[0].find('AC').get('ConnPtId'), p[1].get('ID'))
        self.assertEqual(p[0].get('Flags'), '3')
        self.assertEqual(aos[1].findall('AP')[0].get('Flags'), '8')
        frs = d.findall('FR')
        self.assertEqual(len(frs), 2)
        # 면은 주인 오브젝트 순(곡선 20 → 원 30)으로 정렬된다(면 칠 순서는 중요하지 않음, 사용자 10-30)
        self.assertEqual(frs[1].find('FS').get('Kind'), '1')
        s = frs[0].find('FS')
        self.assertEqual(s.get('EndPtId'), aos[1].findall('AP')[2].get('ID'))
        self.assertAlmostEqual(float(s.get('StartT')), 0.25, delta=1e-6)

    def test_big_numbers(self):
        for v in (-5, 0, K.NUM - 1, K.NUM, 10 ** 9, -10 ** 9):
            t = K.num(v)
            seq = [K.TOK['BOS'], K.TOK['LINE'], K.TOK['SAME']] + t + K.num(0) + [K.TOK['PT'], K.TOK['EOS']]
            d = K.decode(seq)
            x = float(d.find('AO').find('AP').get('X'))
            self.assertAlmostEqual(x, K.XMIN + v * K.XSTEP, delta=1e-3)

    def test_gpt_review_counterexamples(self):
        """GPT 검토(10-30) 반례: 윤곽 0,1,0 묶음 / 면이 쓰는 직선 자르기 / 참조 범위 / 점 번호 / 원 크기 화면 밖 판정."""
        seq = ET.fromstring('<Sequence Name="t" HeightWidthRatio="0.45" FrameCount="1" BackgroundColor="-1"/>')
        fr = ET.fromstring(
            '<Frame ID="1" Position="0"><LayerDef ID="0" Name="L" Visible="true" Locked="false"/>'
            '<AO ID="1" TypeId="1" Color="-16777216" LayerId="0" DrawOrder="0"><AP ID="2" Index="0" X="20" Y="50"/><AP ID="3" Index="1" X="-5000" Y="50"/></AO>'
            '<AO ID="4" TypeId="1" Color="-16777216" LayerId="0" DrawOrder="1"><AP ID="5" Index="0" X="10" Y="10"/><AP ID="6" Index="1" X="30" Y="10"/></AO>'
            '<AO ID="7" TypeId="2" Color="-16777216" LayerId="0" DrawOrder="2"><AP ID="8" Index="0" X="40" Y="-20"/><AP ID="9" Index="1" X="60" Y="-20"/></AO>'
            '<FR Color="-65536"><FS Kind="0" ObjId="1" StartPtId="2" EndPtId="3" StartT="0" EndT="0.004"/>'
            '<FS Kind="0" ObjId="4" StartPtId="5" EndPtId="6" StartT="0" EndT="1" Contour="1"/>'
            '<FS Kind="0" ObjId="4" StartPtId="6" EndPtId="5" StartT="0" EndT="1"/></FR></Frame>')
        toks, st = K.encode(seq, fr)
        K.fields(toks)
        d = K.decode(toks)
        # 면이 쓰는 직선은 자르지 않는다(끝점 -5000 보존)
        self.assertAlmostEqual(float(d.findall('AO')[0].findall('AP')[1].get('X')), -5000, delta=0.05)
        # 윤곽 0 조각 2개가 한 묶음(0), 구멍(1)은 뒤로
        cont = [int(x.get('Contour') or 0) for x in d.find('FR').findall('FS')]
        self.assertEqual(sorted(cont), [0, 0, 1])
        self.assertEqual(cont[-1], 1)
        # 원: 비율 0.45, 가로 지름 20 → 화면 화소 기준 세로 반지름 22%(단순 계산 10%) → 중심 y=-20이어도 화면에 걸친다 → 남아야 한다
        self.assertEqual(st['drop_far'], 0)
        self.assertEqual(len(d.findall('AO')), 3)
        # 참조 범위: LINK BIG(-1), 2점 선의 점 번호 2는 정답 검사에서 거부
        base = [K.TOK['BOS'], K.TOK['BG']] + K.num(255) * 4 + [K.TOK['LAYER'], K.TOK['LINE'], K.TOK['COLOR']] + K.num(255) + K.num(0) * 3 \
            + [K.TOK['THICK']] + K.num(400) + K.num(1000) + K.num(1000) + [K.TOK['PT']] + K.num(1200) + K.num(1000) + [K.TOK['PT']]
        bad_link = base + [K.TOK['LINK'], K.TOK['BIG']] + K.num((K.BIGOFF - 1) // K.NUM ** 2) + K.num((K.BIGOFF - 1) // K.NUM % K.NUM) + K.num((K.BIGOFF - 1) % K.NUM) + [K.TOK['EOS']]
        with self.assertRaises(ValueError):
            K.fields(bad_link)
        bad_pt = base + [K.TOK['FILL']] + K.num(255) * 4 + [K.TOK['SEG']] + K.num(1) + K.num(2) + K.num(0) + K.num(1000) + K.num(2000) + [K.TOK['EOS']]
        with self.assertRaises(ValueError):
            K.fields(bad_pt)
        ok_pt = base + [K.TOK['FILL']] + K.num(255) * 4 + [K.TOK['SEG']] + K.num(1) + K.num(1) + K.num(0) + K.num(1000) + K.num(2000) + [K.TOK['EOS']]
        K.fields(ok_pt)


if __name__ == '__main__':
    unittest.main()
