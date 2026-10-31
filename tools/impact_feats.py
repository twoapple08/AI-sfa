#!/usr/bin/env python3
"""임팩트 전수 분류(2026-10-20 계획)용 프레임별 지표 저장. 영상마다 한 번만 디코딩한다.

사용:
  python tools/impact_feats.py <목록.txt: post_id<TAB>경로> <출력 폴더> [--workers 3]

영상마다 <출력>/<post_id>.npz:
  m   (N,6) float32 = impact_scan2.metrics의 mono, chroma, ext, edge, rng, mean (320x180 기준)
  t   (N,18,32,3) uint8 = 32x18 축소 색 프레임(컷 경계·문맥 비교용)
기준을 바꿔 후보를 다시 뽑을 때 재디코딩하지 않으려는 것이다. 이미지 원본은 저장소에 넣지 않는다.
"""
import argparse
import os
import sys
from concurrent.futures import ProcessPoolExecutor

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import impact_scan2  # noqa: E402

KEYS = ('mono', 'chroma', 'ext', 'edge', 'rng', 'mean')


def one(job):
    post, path, out = job
    dst = os.path.join(out, post + '.npz')
    if os.path.exists(dst):
        return post, 'skip'
    try:
        M, T = [], []
        for f in impact_scan2.frames(path):
            m = impact_scan2.metrics(f)
            M.append([m[k] for k in KEYS])
            T.append(f.reshape(18, 10, 32, 10, 3).mean((1, 3)).astype(np.uint8))
        tmp = dst + '.tmp.npz'
        np.savez_compressed(tmp, m=np.asarray(M, np.float32), t=np.asarray(T, np.uint8))
        os.replace(tmp, dst)
        return post, len(M)
    except Exception as e:  # noqa: BLE001
        return post, 'error ' + str(e)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('list')
    ap.add_argument('out')
    ap.add_argument('--workers', type=int, default=3)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    jobs = [(*l.rstrip('\n').split('\t'), a.out) for l in open(a.list, encoding='utf-8') if l.strip()]
    with ProcessPoolExecutor(a.workers) as ex:
        for n, (post, r) in enumerate(ex.map(one, jobs), 1):
            print(n, len(jobs), post, r, flush=True)


if __name__ == '__main__':
    main()
