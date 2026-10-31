"""toklen.json 요약. 사용: python analyze_toklen.py toklen.json"""
import json
import sys
from collections import Counter

import numpy as np

d = json.load(open(sys.argv[1], encoding='utf-8'))
errs = [k for k, v in d.items() if v['rows'] is None]
print('파일', len(d), '읽기 실패', len(errs))
for split in ('train', 'holdout'):
    files = {k: v['rows'] for k, v in d.items() if v['split'] == split and v['rows']}
    rows = [r for rs in files.values() for r in rs]
    n = np.array([r['n'] for r in rows])
    print(f'\n== {split}: 파일 {len(files)} 장 {len(n)}')
    for lim in (1024, 2048, 3072, 4096, 6144, 8192, 16384, 32768):
        print(f'  ≤{lim}: {(n <= lim).mean() * 100:5.1f}%  ({(n <= lim).sum()}장)')
    long_ = n[n > 2048]
    if len(long_):
        print('  2048 초과', len(long_), '장 · 백분위 50/75/90/99/최대', [int(np.percentile(long_, q)) for q in (50, 75, 90, 99)], int(long_.max()))
    whole = [k for k, rs in files.items() if all(r['n'] > 2048 for r in rs)]
    part = [k for k, rs in files.items() if any(r['n'] > 2048 for r in rs) and not all(r['n'] > 2048 for r in rs)]
    print('  모든 장이 2048 초과인 파일', len(whole), '· 일부만 초과', len(part))
    # 긴 장을 가장 많이 가진 파일
    top = sorted(((sum(r['n'] > 2048 for r in rs), len(rs), int(max(r['n'] for r in rs)), k) for k, rs in files.items()), reverse=True)[:12]
    print('  긴 장 많은 파일(초과 장/전체 장/최대 길이):')
    for c, tot, mx, k in top:
        if c:
            print(f'    {c}/{tot} 최대{mx}  {k[:60]}')
    # 단어 종류 비중: 짧은 장 vs 긴 장
    for name, sel in (('≤2048', [r for r in rows if r['n'] <= 2048]), ('>2048', [r for r in rows if r['n'] > 2048])):
        if not sel:
            continue
        fc, kc = Counter(), Counter()
        for r in sel:
            fc.update(r['f'])
            kc.update(r['k'])
        tot = sum(fc.values())
        nobj = sum(r['obj'] for r in sel)
        ntok = sum(r['n'] for r in sel)
        print(f'  [{name}] 장 {len(sel)} · 장당 오브젝트 중앙값 {int(np.median([r["obj"] for r in sel]))} · 오브젝트당 단어 {ntok / max(nobj, 1):.1f}'
              f' · 문법 확인 실패 {sum(not r["ok"] for r in sel)}')
        print('    단어 종류 %:', ', '.join(f'{k} {v / tot * 100:.1f}' for k, v in fc.most_common()))
        kt = sum(kc.values())
        print('    오브젝트 종류 %:', ', '.join(f'{k} {v / kt * 100:.1f}' for k, v in kc.most_common()))
