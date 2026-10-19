#!/usr/bin/env python3
"""impact_feats.py 결과(npz)에서 임팩트 후보 구간을 뽑는다(2026-10-20 전수 분류, 기준 확대판).

impact_scan2.scan과 같은 흐름이지만 기준을 넓혔다.
- 단색조: rng<8 또는 (mono<MONO 그리고 chroma<CHROMA). 기본 MONO 0.18, CHROMA 35 (scan2는 0.12, 25)
- 연속 길이 상한 MAX_RUN 36 (scan2 24). 더 긴 단색조 구간은 그 안에서 극단·선 밀도가 튀는 부분만.
- 문맥 대비: 앞뒤 CTX프레임의 단색조 비율 ≤0.5 또는 선 밀도 +0.06 / 극단 +0.2 이상 (scan2 0.08 / 0.25)
- 추가: 단색조가 아니어도 앞뒤 대비 극단(ext)이 +0.35 이상 튀는 1–6프레임(색이 남은 고대비 삽입)
- 그림 없는 단색(rng<8만으로 된 구간)도 '단색' 표시로 남긴다(사용자: 단색섬광 = 맞음(단색섬광)).

사용: python tools/impact_cands.py <feats 폴더> <out.csv>
"""
import csv
import glob
import os
import sys

import numpy as np

MONO, CHROMA, MAX_RUN, CTX = 0.18, 35.0, 36, 6
I_MONO, I_CHROMA, I_EXT, I_EDGE, I_RNG, I_MEAN = range(6)


def is_mono(m):
    return m[I_RNG] < 8 or (m[I_MONO] < MONO and m[I_CHROMA] < CHROMA)


def cut_score(t, i):
    """i-1 → i 사이 32x18 색 프레임 평균 절대차(0–255)."""
    if i <= 0 or i >= len(t):
        return 0.0
    return float(np.abs(t[i].astype(np.int16) - t[i - 1].astype(np.int16)).mean())


def runs_of(flags):
    i, n = 0, len(flags)
    while i < n:
        if not flags[i]:
            i += 1
            continue
        j = i
        while j + 1 < n and flags[j + 1]:
            j += 1
        yield i, j
        i = j + 1


def salient(M, i, j):
    seg = M[i:j + 1]
    ext_med, edge_med = np.median(seg[:, I_EXT]), np.median(seg[:, I_EDGE])
    mean_med = np.median(seg[:, I_MEAN])
    # 그림 있는 프레임은 극단·선 밀도가 튀는 것, 그림 없는 단색 프레임은 밝기가 크게 튀는 것(흰·검정 번쩍임, 78337 f378-379)
    hit = [k for k in range(i, j + 1) if (M[k, I_RNG] >= 8 and (M[k, I_EXT] - ext_med >= 0.2 or M[k, I_EDGE] - edge_med >= 0.06))
           or (M[k, I_RNG] < 8 and abs(M[k, I_MEAN] - mean_med) >= 60)]
    out, s = [], None
    for n, k in enumerate(hit):
        s = k if s is None else s
        if n + 1 == len(hit) or hit[n + 1] > k + 2:
            if k - s + 1 <= MAX_RUN:
                out.append((s, k, 'long_inner'))
            s = None
    return out


def scan(M):
    mono = np.array([is_mono(m) for m in M])
    out = []
    for i, j in runs_of(mono):
        seg = M[i:j + 1]
        around = np.concatenate([M[max(0, i - CTX):i], M[j + 1:j + 1 + CTX]])
        flat = bool((seg[:, I_RNG] < 8).all())
        content = seg[(seg[:, I_RNG] >= 8) & ((seg[:, I_EDGE] >= 0.02) | (seg[:, I_EXT] >= 0.6))]
        if j - i + 1 > MAX_RUN:
            out.extend(salient(M, i, j))
            continue
        if flat:
            if len(around) and np.mean([is_mono(m) for m in around]) <= 0.5:
                out.append((i, j, 'flat'))
            continue
        if not len(content):
            continue
        ctx_mono = np.mean([is_mono(m) for m in around]) if len(around) else 0.0
        d_edge = content[:, I_EDGE].max() - (np.median(around[:, I_EDGE]) if len(around) else 0)
        d_ext = content[:, I_EXT].max() - (np.median(around[:, I_EXT]) if len(around) else 0)
        if ctx_mono <= 0.5 or d_edge >= 0.06 or d_ext >= 0.2:
            out.append((i, j, 'mono'))
    # 색이 남은 고대비 삽입
    taken = np.zeros(len(M), bool)
    for s, e, _ in out:
        taken[s:e + 1] = True
    ext = M[:, I_EXT]
    for k in range(len(M)):
        if taken[k] or mono[k]:
            continue
        for L in range(1, 7):
            e = k + L - 1
            if e >= len(M) or taken[e]:
                break
            before, after = ext[max(0, k - CTX):k], ext[e + 1:e + 1 + CTX]
            if len(before) < 2 or len(after) < 2:
                continue
            base = max(np.median(before), np.median(after))
            if ext[k:e + 1].min() - base >= 0.35:
                out.append((k, e, 'hicon'))
                taken[k:e + 1] = True
                break
    return sorted(out)


def main():
    src, dst = sys.argv[1], sys.argv[2]
    rows = []
    for p in sorted(glob.glob(os.path.join(src, '*.npz'))):
        post = os.path.basename(p)[:-4]
        z = np.load(p)
        M, T = z['m'], z['t']
        for s, e, kind in scan(M):
            seg = M[s:e + 1]
            rows.append({'key': f'{post}:{s}-{e}', 'post_id': post, 'frames': f'{s}-{e}', 'start': s, 'end': e, 'n': e - s + 1, 'kind': kind,
                         'nframes': len(M), 'cut_in': round(cut_score(T, s), 1), 'cut_out': round(cut_score(T, e + 1), 1),
                         'mono': round(float(seg[:, I_MONO].mean()), 3), 'chroma': round(float(seg[:, I_CHROMA].mean()), 1),
                         'ext': round(float(seg[:, I_EXT].mean()), 3), 'edge': round(float(seg[:, I_EDGE].mean()), 3),
                         'flat': int((seg[:, I_RNG] < 8).all())})
    with open(dst, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    from collections import Counter
    print(len(rows), Counter(r['kind'] for r in rows))


if __name__ == '__main__':
    main()
