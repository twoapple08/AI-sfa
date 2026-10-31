"""Kaggle 자료 미리 만들기(10-31): 작업자 CONFIG 바꿔 넣기, 자료 커널·학습 커널 설정 일치, seq_data --check."""
import ast
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1] / 'tools'
sys.path.insert(0, str(TOOLS))

import kaggle_seq_remote as KR  # noqa: E402
import kaggle_seq_worker as KW  # noqa: E402


def config_of(src):
    for node in ast.parse(src).body:
        if isinstance(node, ast.Assign) and getattr(node.targets[0], 'id', '') == 'CONFIG':
            return ast.literal_eval(node.value)
    raise AssertionError('CONFIG 없음')


class TestPrebuilt(unittest.TestCase):
    def test_worker_config_replaced(self):
        # 여러 줄 CONFIG도 통째로 바뀌고, 결과가 실행 가능한 파이썬이어야 한다
        for cfg in (dict(branch='b', smoke=False, mode='data'),
                    dict(branch='b', session_minutes=30, plan_minutes=0, tok_budget=100, extra='--x "y"', smoke=True,
                         mode='train', prebuilt=True, prebuilt_any_code=False)):
            src = KR.worker_src(cfg)
            self.assertEqual(config_of(src), cfg)
            compile(src, 'kernel.py', 'exec')
            self.assertEqual(src.count('CONFIG = '), 1)

    def test_same_args_both_modes(self):
        # 학습 커널의 --check가 자료 커널과 같은 옵션을 보게(작업자 수만 다를 수 있음)
        for smoke in (False, True):
            a = KW.data_args(dict(smoke=smoke), 4)
            b = KW.data_args(dict(smoke=smoke, mode='train', prebuilt=True), 2)
            self.assertEqual(set(a), set(KW.SPLITS))
            for k in a:
                self.assertEqual(a[k].replace('--workers 4', ''), b[k].replace('--workers 2', ''))
        full = KW.data_args(dict(smoke=False), 4)   # 이전 작업자와 같은 본 자료 설정
        self.assertIn('--max-frames 300', full['sd'])
        self.assertIn('--aug 1', full['sd'])
        self.assertNotIn('--every', full['sd'])
        self.assertIn('--holdout', full['sv'])
        self.assertIn('--fixed 6,4,1.05', full['ss'])

    def test_check_flag(self):
        # 맞으면 0, 판이 다르거나 폴더가 없으면 3 — 읽기 전용이라 아무것도 만들지 않는다
        import seq_data as D
        args = ['--maxlen', '2048', '--max-frames', '4', '--holdout']
        with tempfile.TemporaryDirectory() as td:
            missing = os.path.join(td, 'none')
            r = subprocess.run([sys.executable, str(TOOLS / 'seq_data.py'), missing, *args, '--check'], capture_output=True)
            self.assertEqual(r.returncode, 3)
            self.assertFalse(os.path.exists(missing))
            ns = type('A', (), dict(maxlen=2048, max_frames=4, W=640, every=1, holdout=True, aug=0, fixed=''))
            want = dict(D.config(ns), files=len(D.V.file_list(only='holdout')))
            Path(td, 'a.npz').touch()
            Path(td, 'done.json').write_text(json.dumps(dict(want, frames=5, npz=1, fails=[])))
            r = subprocess.run([sys.executable, str(TOOLS / 'seq_data.py'), td, *args, '--check'], capture_output=True)
            self.assertEqual(r.returncode, 0)
            Path(td, 'done.json').write_text(json.dumps(dict(want, version=want['version'] - 1, frames=5, npz=1, fails=[])))
            r = subprocess.run([sys.executable, str(TOOLS / 'seq_data.py'), td, *args, '--check'], capture_output=True)
            self.assertEqual(r.returncode, 3)
            self.assertEqual(sorted(os.listdir(td)), ['a.npz', 'done.json'])


if __name__ == '__main__':
    unittest.main()
