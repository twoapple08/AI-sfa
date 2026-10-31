"""CLIP 점수 기준 맞추기: clip_score.py 점수를 GPT 판정(G15–G17·H01–H04, 이름:초:주|배 형식)과 맞대어 요소별 z 임계를 정한다.

사용: python tools/clip_calibrate.py <CLIP 점수 npz> <출력 csv>
- 정답: 판정 파일에서 요소가 적힌 영상 = 있음, 같은 파일이 다룬 분류 칸에 그 요소가 없는 영상 = 없음('열람불가' 행 제외).
  분류 칸 안에서 이름을 찾는다(element_aggregate.judgments와 같은 규칙).
- 영상 점수: z ≥ T인 프레임 수. T 후보 1.0–3.0(0.5 간격)마다 '프레임 2개 이상이면 있음'으로 보고 F1이 가장 높은 T를 고른다.
- AUC: 영상의 상위 3프레임 z 평균으로 계산한다.
- 양성이 3개 미만인 요소는 보정하지 않는다('표본 부족'). 그런 요소는 element_rank.py가 기본 임계를 쓴다.
"""
import csv
import glob
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
from element_aggregate import KB, SEC_COLS, TERM, read  # noqa: E402

TS = [1.0, 1.5, 2.0, 2.5, 3.0]
MIN_FRAMES = 2


def labels(tree):
    parent = {r['번호']: r['부모번호'] for r in tree}
    name = {r['번호']: r['요소'] for r in tree}
    by_cat = {}
    for r in tree:
        k = r['번호']
        while parent[k]:
            k = parent[k]
        by_cat[(name[k], r['요소'])] = r['번호']
    pos, seen_cols = {}, {}
    for f in glob.glob(os.path.join(KB, 'ai_results', 'gpt_[GH]*.csv')):
        for r in csv.DictReader(open(f, encoding='utf-8-sig')):
            if '열람불가' in (r.get('특이사항') or ''):
                continue
            cols = [c for c in SEC_COLS if c in r]
            if not cols:
                continue
            seen_cols.setdefault(r['post_id'], set()).update(cols)
            for c in cols:
                for t in (r.get(c) or '').split(';'):
                    t = t.strip()
                    if t.count(':') >= 2:
                        nm = t.rsplit(":", 2)[0]
                        n = by_cat.get((c, nm)) or by_cat.get((c, TERM.get(nm, nm)))
                        if n:
                            pos.setdefault(n, set()).add(r['post_id'])
    return pos, seen_cols, by_cat


def auc(p, n):
    if not p or not n:
        return float('nan')
    p, n = np.array(p), np.array(n)
    return float(((p[:, None] > n[None]).sum() + 0.5 * (p[:, None] == n[None]).sum()) / (len(p) * len(n)))


def main():
    npz, out = sys.argv[1:3]
    tree = read(os.path.join(KB, 'element_tree_2026-10-20.csv'))
    cat_of = {}
    parent = {r['번호']: r['부모번호'] for r in tree}
    name = {r['번호']: r['요소'] for r in tree}
    for r in tree:
        k = r['번호']
        while parent[k]:
            k = parent[k]
        cat_of[r['번호']] = name[k]
    pos, seen_cols, _ = labels(tree)
    d = np.load(npz)
    z = d['score'].astype(np.float32)
    span = {str(p): (a, b) for (a, b), p in zip(d['t_index'], d['post_ids'])}
    rows = []
    for j, n in enumerate(d['elements']):
        n = str(n)
        vids = [p for p, cols in seen_cols.items() if cat_of.get(n) in cols and p in span]
        y = [p in pos.get(n, ()) for p in vids]
        npos = sum(y)
        row = {'번호': n, '요소': name[n], '분류': cat_of[n], '정답_있음': npos, '정답_없음': len(y) - npos}
        if npos < 3 or len(y) - npos < 3:
            row['상태'] = '표본 부족'
            rows.append(row)
            continue
        top3 = [float(np.sort(z[span[p][0]:span[p][1], j])[-3:].mean()) for p in vids]
        row['AUC'] = f"{auc([s for s, t in zip(top3, y) if t], [s for s, t in zip(top3, y) if not t]):.2f}"
        best = (-1, None, 0, 0)
        for T in TS:
            hit = [int((z[span[p][0]:span[p][1], j] >= T).sum()) >= MIN_FRAMES for p in vids]
            tp = sum(h and t for h, t in zip(hit, y))
            fp = sum(h and not t for h, t in zip(hit, y))
            fn = sum((not h) and t for h, t in zip(hit, y))
            pr = tp / (tp + fp) if tp + fp else 0
            rc = tp / (tp + fn) if tp + fn else 0
            f1 = 2 * pr * rc / (pr + rc) if pr + rc else 0
            if f1 > best[0]:
                best = (f1, T, pr, rc)
        row.update({'임계_z': best[1], '정밀도': f'{best[2]:.2f}', '재현율': f'{best[3]:.2f}', 'F1': f'{best[0]:.2f}', '상태': '보정됨'})
        rows.append(row)
    with open(out, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, ['번호', '요소', '분류', '정답_있음', '정답_없음', 'AUC', '임계_z', '정밀도', '재현율', 'F1', '상태'])
        w.writeheader()
        w.writerows(rows)
    ok = [r for r in rows if r.get('상태') == '보정됨']
    print('요소', len(rows), '보정됨', len(ok), '표본 부족', len(rows) - len(ok))


if __name__ == '__main__':
    main()
