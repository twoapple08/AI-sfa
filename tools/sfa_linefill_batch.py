#!/usr/bin/env python3
"""선 칠 → 면 교체를 학습 파일 전체에 (2026-10-29 사용자 "전체적으로 처리"). 파일마다 sfa_linefill_runs.py를 따로 돌린다(4개씩 병렬).
결과: <출력>/<원래 경로> 와 <출력>/report.json(파일·오브젝트 전후·교체 묶음 수·전체 장 렌더 차이 표본).
사용: python sfa_linefill_batch.py <출력 폴더> [--workers 4]
"""
import argparse
import json
import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
import zipfile
from multiprocessing import Pool

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sfa_render as R  # noqa: E402
import vec_data as V  # noqa: E402

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data', 'user_sfa')


def diff_sample(a, b, k=3):
    """원본·변환본의 장 k개(처음·가운데·끝)를 렌더해 30 넘게 다른 픽셀 비율의 최댓값."""
    ra = ET.fromstring(zipfile.ZipFile(a).read(zipfile.ZipFile(a).namelist()[0]))
    rb = ET.fromstring(zipfile.ZipFile(b).read(zipfile.ZipFile(b).namelist()[0]))
    fa, fb = ra.findall('Frame'), rb.findall('Frame')
    R.PARAMS['pad'] = 6.0
    R.PARAMS['thick_mul'] = 1.0
    worst = 0.0
    for i in sorted({0, len(fa) // 2, len(fa) - 1})[:k]:
        x = np.asarray(R.render_frame(ra, fa[i], 960, 540))[..., :3].astype(int)
        y = np.asarray(R.render_frame(rb, fb[i], 960, 540))[..., :3].astype(int)
        worst = max(worst, float((np.abs(x - y).max(-1) > 30).mean()))
    return worst


def one(job):
    rel, out = job
    dst = os.path.join(out, rel)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    p = subprocess.run([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sfa_linefill_runs.py'), os.path.join(ROOT, rel), dst],
                       capture_output=True, text=True, timeout=3600)
    if p.returncode != 0:
        return dict(file=rel, error=p.stderr[-300:])
    m = re.search(r'전체 오브젝트 (\d+) → (\d+)', p.stdout)
    runs = sum(int(x) for x in re.findall(r'묶음 교체 (\d+)', p.stdout))
    n0, n1 = int(m.group(1)), int(m.group(2))
    r = dict(file=rel, before=n0, after=n1, runs=runs)
    if n1 < n0:
        r['diff'] = round(diff_sample(os.path.join(ROOT, rel), dst), 4)
    else:
        os.remove(dst)
    return r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('out')
    ap.add_argument('--workers', type=int, default=4)
    ap.add_argument('--files', default='', help='후보 목록 json([[경로, ...], ...]); 없으면 학습 파일 전체')
    a = ap.parse_args()
    files = [r[0] for r in json.load(open(a.files, encoding='utf-8'))] if a.files else V.file_list()
    res = []
    with Pool(a.workers) as pool:
        for i, r in enumerate(pool.imap_unordered(one, [(f, a.out) for f in files])):
            res.append(r)
            if 'error' in r:
                print(i + 1, len(files), r['file'], '오류', flush=True)
            elif r['after'] < r['before']:
                print(i + 1, len(files), r['file'], r['before'], '→', r['after'], '차이', r.get('diff'), flush=True)
            json.dump(res, open(os.path.join(a.out, 'report.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
    ch = [r for r in res if r.get('after', 0) < r.get('before', 0)]
    print('바뀐 파일', len(ch), '오브젝트', sum(r['before'] for r in ch), '→', sum(r['after'] for r in ch))


if __name__ == '__main__':
    main()
