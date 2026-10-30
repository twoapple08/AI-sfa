#!/usr/bin/env python3
"""재설계 학습 자료(2026-10-30, docs/VIDEO-TO-SFA-REDESIGN-2026-10-30.md): SFA 장 → (압축 영상 장, 정답 토큰열).
그림은 앱처럼 렌더(굵기는 1920 기준 비율 그대로 — 정답 파일과 같은 굵기)한 뒤 H.264로 압축·복원한다.
정답 = sfa_tokens.encode 토큰열 + 토큰마다 칸 번호(fields). 파일마다 npz 하나: img (n,H,W,3), tok/fld (이어 붙임), off (n+1).
사용: python seq_data.py 출력폴더 [--maxlen 2048] [--max-frames 200] [--every 1] [--holdout]
"""
import argparse
import json
import os
import sys
import zipfile
import xml.etree.ElementTree as ET
from multiprocessing import Pool

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sfa_render as R  # noqa: E402
import sfa_tokens as K  # noqa: E402
import vec_data as V  # noqa: E402

ROOT = V.ROOT


def one(job):
    rel, out_dir, seed, a = job
    rng = np.random.default_rng(seed)
    try:
        z = zipfile.ZipFile(os.path.join(ROOT, rel))
        root = ET.fromstring(z.read(z.namelist()[0]))
    except Exception as e:
        return rel, 'err:' + type(e).__name__
    frs = root.findall('Frame')
    if len(frs) > a['max_frames']:
        s = int(rng.integers(0, len(frs) - a['max_frames'] + 1))
        frs = frs[s:s + a['max_frames']]
    W, H = a['W'], a['W'] * 9 // 16
    R.PARAMS['pad'] = 0.0
    R.PARAMS['thick_mul'] = W / 1920
    imgs, toks, flds, pos = [], [], [], []
    for fr in frs:
        t, _ = K.encode(root, fr)
        if len(t) > a['maxlen']:
            continue
        try:
            f = K.fields(t)
        except ValueError:
            continue
        imgs.append(R.render_frame(root, fr, W, H))
        toks.append(t)
        flds.append(f)
        pos.append(int(fr.get('Position')))
    if not imgs:
        return rel, 'none'
    crf = int(rng.integers(23, 36))
    dec = V.encode_decode(imgs, crf)
    if len(dec) != len(imgs):
        return rel, f'err:frames {len(dec)}/{len(imgs)}'
    off = np.cumsum([0] + [len(t) for t in toks])
    name = rel.replace('/', '__').replace(' ', '_')[:-4] + f'__c{crf}.npz'
    tmp = os.path.join(out_dir, name + '.tmp')
    with open(tmp, 'wb') as fh:
        np.savez_compressed(fh, img=dec, tok=np.concatenate(toks).astype(np.int16), fld=np.concatenate(flds).astype(np.int8),
                            off=off.astype(np.int64), pos=np.array(pos),
                            meta=json.dumps(dict(file=rel, crf=crf, W=W, H=H, vocab=K.VOCAB, xstep=K.XSTEP,
                                                 hwr=float(root.get('HeightWidthRatio') or 0.5625) or 0.5625)))
    os.replace(tmp, os.path.join(out_dir, name))
    return rel, f'ok {len(imgs)}'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('out_dir')
    ap.add_argument('--maxlen', type=int, default=2048)
    ap.add_argument('--max-frames', type=int, default=200)
    ap.add_argument('--W', type=int, default=640)
    ap.add_argument('--every', type=int, default=1, help='파일 몇 개마다 하나(시험용)')
    ap.add_argument('--holdout', action='store_true', help='시험용 파일만')
    ap.add_argument('--workers', type=int, default=max(1, (os.cpu_count() or 2) - 1))
    a = ap.parse_args()
    os.makedirs(a.out_dir, exist_ok=True)
    files = V.file_list(only='holdout') if a.holdout else V.file_list()
    files = files[::a.every]
    cfg = dict(maxlen=a.maxlen, max_frames=a.max_frames, W=a.W)
    jobs = [(rel, a.out_dir, 1000 + i, cfg) for i, rel in enumerate(files)]
    n = 0
    with Pool(a.workers) as p:
        for rel, st in p.imap_unordered(one, jobs):
            n += st.startswith('ok') and int(st.split()[1])
            if not st.startswith('ok'):
                print(rel, st, flush=True)
    print('파일', len(files), '장', n, flush=True)


if __name__ == '__main__':
    main()
