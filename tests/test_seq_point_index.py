"""좌표 첫 점 / 이어지는 점 진단(11-01, 판정 기준 §2-3): 토큰마다 오브젝트 안 점 번호."""
import os
import sys
import unittest
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))

import torch  # noqa: E402
import seq_train as ST  # noqa: E402
import sfa_tokens as K  # noqa: E402
import seq_judge as J  # noqa: E402
import vec_data as V  # noqa: E402


class PointIndexTest(unittest.TestCase):
    def test_first_point_coords_match_objects(self):
        m = J.load_manifest()
        for e in m['entries'][:5]:
            with zipfile.ZipFile(os.path.join(V.ROOT, e['file'])) as z:
                root = ET.fromstring(z.read(z.namelist()[0]))
            t = K.encode(root, root.findall('Frame')[e['index']])[0]
            f = K.fields(t)
            tok, fld = torch.tensor(t), torch.tensor(f)
            pi = ST.point_index(tok)
            co = (fld == K.FID['coord'])
            n_obj = J.n_objs(t)
            # 첫 점은 오브젝트마다 x·y 두 칸(BIG 없이 적힌 값만 센다)
            self.assertEqual(int((co & (pi == 0)).sum()), 2 * n_obj - int(((fld == K.FID['big']) & (pi == 0)).sum()))
            # 오브젝트마다 점 수(직선·원 2, 곡선 3) − 1개가 이어지는 점
            npts = sum(K.NPTS[K.SPECIAL[x]] for x in t if x in J.TYPE_TOKS)
            self.assertEqual(int((tok == K.TOK['PT']).sum()), npts)

    def test_field_hits_extra_rows(self):
        t = [K.TOK['BOS'], K.TOK['BG'], K.OFF, K.OFF, K.OFF, K.OFF, K.TOK['LAYER'], K.TOK['LINE'], K.TOK['SAME'],
             K.OFF + 1, K.OFF + 2, K.TOK['PT'], K.OFF + 3, K.OFF + 4, K.TOK['PT']]
        f = [K.FID['spec']] * 2 + [K.FID['bg']] * 4 + [K.FID['spec']] * 3 + [K.FID['coord']] * 2 + [K.FID['spec']] + [K.FID['coord']] * 2 + [K.FID['spec']]
        tgt, fld = torch.tensor([t]), torch.tensor([f])
        lg = torch.nn.functional.one_hot(tgt, K.VOCAB).float()
        lg[0, 9, :] = 0   # 첫 점 x 하나를 틀리게
        lg[0, 9, K.OFF + 50] = 1
        hn = ST.field_hits(lg, tgt, fld)
        self.assertEqual(hn.shape, (ST.NROW, 2))
        self.assertEqual(tuple(hn[-2]), (1.0, 2.0))   # 첫 점: 2칸 중 1 맞음
        self.assertEqual(tuple(hn[-1]), (2.0, 2.0))   # 이어지는 점: 2칸 모두
        rec, txt = ST.field_report(hn)
        self.assertEqual(rec['coord_first'], 50.0)
        self.assertIn('이어지는 점 100', txt)


if __name__ == '__main__':
    unittest.main()
