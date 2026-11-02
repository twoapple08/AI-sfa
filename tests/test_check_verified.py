"""GPT 8차 §4의 9가지 입력 변형을 check_verified에 직접 적용한다(필수 필드 누락도 거부)."""
import copy
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))
from drawing_segments import check_verified  # noqa: E402

P = os.path.join(os.path.dirname(__file__), '..', 'data', 'stickman_motion', 'verified_boundaries_1913_2026-11-02.json')


class TestCheckVerified(unittest.TestCase):
    def setUp(self):
        self.ver = json.load(open(P, encoding='utf-8'))
        self.sha = self.ver['video_sha256']

    def bad(self, v, sha=None, color='blue'):
        with self.assertRaises(ValueError):
            check_verified(v, sha or self.sha, color)

    def test_real_file_passes(self):
        check_verified(self.ver, self.sha, 'blue')

    def test_rejections(self):
        v = self.ver
        self.bad(v, sha='0' * 64)
        self.bad(v, color='red')
        for mut in (lambda d: d['not_boundaries'].append(328),
                    lambda d: d['same_pairs'].append([325, 327]),
                    lambda d: d['same_pairs'].append([327, 328]),
                    lambda d: d.pop('target_color'),
                    lambda d: d.pop('frame_index_base'),
                    lambda d: d.update(frame_order='presentation')):
            d = copy.deepcopy(v)
            mut(d)
            self.bad(d)


if __name__ == '__main__':
    unittest.main()
