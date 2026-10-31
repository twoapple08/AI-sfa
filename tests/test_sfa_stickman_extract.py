import os
import sys
import unittest
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
from sfa_stickman_extract import figures  # noqa: E402


def frame_xml(linked=True):
    # 표준 스틱맨: 머리 원 + 몸통 + 팔 2(2마디) + 다리 2(2마디). linked=False면 AC 없이 끝점만 겹친다(옛 파일)
    P = {'top': (50, 10), 'neck': (50, 20), 'hip': (50, 40), 'el1': (45, 28), 'ha1': (42, 36), 'el2': (55, 28), 'ha2': (58, 36),
         'kn1': (46, 50), 'ft1': (45, 60), 'kn2': (54, 50), 'ft2': (55, 60)}
    segs = [('2', 'neck', 'top'), ('1', 'neck', 'hip'), ('1', 'neck', 'el1'), ('1', 'el1', 'ha1'), ('1', 'neck', 'el2'), ('1', 'el2', 'ha2'),
            ('1', 'hip', 'kn1'), ('1', 'kn1', 'ft1'), ('1', 'hip', 'kn2'), ('1', 'kn2', 'ft2')]
    pid, at, aos = 0, {}, []
    for t, a, b in segs:
        ids = []
        for n in (a, b):
            pid += 1
            ids.append((pid, n))
            at.setdefault(n, []).append(pid)
        aos.append((t, ids))
    out = ['<Frame ID="1" Position="0">']
    for k, (t, ids) in enumerate(aos):
        out.append(f'<AO ID="{k + 1}" TypeId="{t}" Color="-16777216">')
        for i, n in ids:
            fl = 3 if (n == 'hip' and k == 1) else 5
            conn = ''.join(f'<AC ConnPtId="{j}"/>' for j in at[n] if j != i) if linked else ''
            out.append(f'<AP ID="{i}" Flags="{fl}" Index="0" X="{P[n][0]}" Y="{P[n][1]}">{conn}</AP>')
        out.append('</AO>')
    out.append('</Frame>')
    return ET.fromstring(''.join(out))


class StickmanExtractTest(unittest.TestCase):
    def check(self, linked):
        f = figures(frame_xml(linked))
        self.assertEqual(len(f), 1)
        s = f[0]
        self.assertEqual(s['neck'], [50.0, 20.0])
        self.assertEqual(s['hip'], [50.0, 40.0])
        self.assertEqual(s['head'], [[50.0, 20.0], [50.0, 10.0]])
        self.assertEqual([len(a[1]) for a in s['arms']], [3, 3])
        self.assertEqual([len(a[1]) for a in s['legs']], [3, 3])
        self.assertEqual(s['legs'][0][1][-1], [45.0, 60.0])

    def test_linked(self):
        self.check(True)

    def test_overlapping_endpoints_without_links(self):
        self.check(False)


if __name__ == "__main__":
    unittest.main()
