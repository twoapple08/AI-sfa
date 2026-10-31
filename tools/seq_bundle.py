#!/usr/bin/env python3
"""작품 묶음 변형 판정(판정 기준 §5, 2026-11-01): 평가 목록 파일끼리 같은 작품의 다른 판인지.
순서: 정확 사본(seq_judge가 이미 묶음) → 요약 특징으로 장 후보 줄이기 → 이동·같은 비율 확대로 맞춘 오브젝트 비교(sfa_objscore align)로
'같은 그림 장' 찾기 → 파일 쌍의 공유 장 비율. 한 장짜리 파일도 같은 방식(희귀 오브젝트 배치·포함 비율은 맞춘 비교 안에 들어 있다).
기준(높은 확률 후보)은 이름 묶음 쌍과 무작위 쌍의 분포를 보고 정한다(이름 묶음은 정답이 아니라 참고).
사용: python seq_bundle.py [--frames 16] [--out 결과.json]
"""
import argparse
import itertools
import json
import os
import random
import re
import sys
import time
import zipfile
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sfa_objscore as OS  # noqa: E402
import seq_judge as J  # noqa: E402
import vec_data as V  # noqa: E402

SAME_FRAME = 0.8     # 맞춘 뒤 오브젝트 F1이 이 이상이면 '같은 그림 장'
MAX_OBJ = 400        # 이보다 큰 장은 맞춘 비교를 건너뜀(시간), 수로 기록
TOP = 3              # 장마다 요약 특징이 가장 가까운 후보 몇 장만 맞춘 비교
COMMON = 2           # 참조 표본 파일 중 이만큼 이상에 같은 그림 장이 있으면 '흔한 그림'(기본 스틱맨 등) — 공유로 세지 않음
REF_FILES = 80       # 참조 표본: 평가 목록 밖 학습 파일 수(고정 난수)


def load_frames(rel, k):
    with zipfile.ZipFile(os.path.join(V.ROOT, rel)) as z:
        root = ET.fromstring(z.read(z.namelist()[0]))
    hwr = float(root.get('HeightWidthRatio') or 0.5625) or 0.5625
    frs = root.findall('Frame')
    idx = sorted(set(np.linspace(0, len(frs) - 1, min(k, len(frs))).astype(int).tolist())) if frs else []
    out = []
    for i in idx:
        fr = frs[i]
        O = OS.objs(fr, hwr)[0]
        if not O:
            continue
        tc = Counter(o['t'] for o in O)
        out.append(dict(fr=fr, n=len(O), tc=np.array([tc.get('1', 0), tc.get('2', 0), tc.get('3', 0)], float),
                        cols=Counter(o['col'] for o in O), hwr=hwr))
    return out


def desc_dist(a, b):
    """요약 특징 거리: 종류별 수의 상대 차 + 색 겹침 부족."""
    t = np.abs(a['tc'] - b['tc']).sum() / max(a['n'], b['n'])
    inter = sum((a['cols'] & b['cols']).values())
    c = 1 - inter / max(a['n'], b['n'])
    return t + c


def frame_sim(a, b):
    """이동·같은 비율 확대로 맞춘 뒤 엄격 오브젝트 F1(양쪽 비율이 다르면 a 비율로)."""
    if max(a['n'], b['n']) > MAX_OBJ:
        return None
    r = OS.score(b['fr'], a['fr'], align=True, hwr=a['hwr'])
    return OS.f1(r['match'], r['pred'], r['ans'])


def best_match(a, B, stats):
    cand = sorted(B, key=lambda b: desc_dist(a, b))[:TOP]
    best = 0.0
    for b in cand:
        if desc_dist(a, b) > 0.6:   # 종류 수·색이 크게 다르면 같은 그림일 수 없음
            continue
        s = frame_sim(a, b)
        stats['aligned'] += 1
        if s is None:
            stats['skipped'] += 1
            continue
        best = max(best, s)
        if best >= SAME_FRAME:
            break
    return best


def common_count(a, ref, stats, memo):
    """참조 표본 파일 중 a와 같은 그림 장을 가진 파일 수(COMMON에서 멈춤)."""
    k = id(a)
    if k not in memo:
        n = 0
        for frs in ref:
            n += best_match(a, frs, stats) >= SAME_FRAME
            if n >= COMMON:
                break
        memo[k] = n
    return memo[k]


def share(A, B, stats, ref=None, memo=None):
    """A의 장 중 B에 같은 그림 장이 있는 비율(후보는 요약 특징으로 줄임). ref가 있으면 흔한 그림 장은 공유로 세지 않는다."""
    if not A or not B:
        return 0.0
    hit = 0
    for a in A:
        if best_match(a, B, stats) >= SAME_FRAME:
            if ref is not None and common_count(a, ref, stats, memo) >= COMMON:
                stats['common'] += 1
                continue
            hit += 1
    return hit / len(A)


def pair_score(fa, fb, frames, stats, ref=None, memo=None):
    """두 방향 공유 비율 중 큰 쪽(한쪽이 발췌본이어도 잡게 — 합치는 근거는 내용 중복 — '합치면 보수적'은 틀린 설명이라 철회(GPT 1라운드 F))."""
    ref_ = [frames[f] for f in ref if f not in (fa, fb)] if ref is not None else None
    return max(share(frames[fa], frames[fb], stats, ref_, memo), share(frames[fb], frames[fa], stats, ref_, memo))


def name_key(f):
    b = os.path.basename(f)[:-4]
    b = re.sub(r'\s*\(\d+\)$', '', b)
    return re.sub(r'[\s_-]*\d+$', '', b)


def apply(bundles_path, manifest_path=J.MANIFEST):
    """높은 확률 후보 쌍을 평가 목록의 같은 묶음(한 표)으로 합친다. 정확 사본 묶음은 그대로. 근거는 내용 중복(합치면 통과가 쉬워질 수도 있다, GPT 1라운드 F)."""
    with open(bundles_path, encoding='utf-8') as fh:
        b = json.load(fh)
    with open(manifest_path, encoding='utf-8') as fh:
        m = json.load(fh)
    ents = m['entries']
    gid = {e['file']: e['group'] for e in ents}
    par = {g: g for g in set(gid.values())}

    def find(g):
        while par[g] != g:
            g = par[g]
        return g
    for h in b['high']:
        if h['a'] in gid and h['b'] in gid:
            par[find(gid[h['a']])] = find(gid[h['b']])
    roots = {}
    for e in ents:
        e['group'] = roots.setdefault(find(e['group']), len(roots))
    groups = []
    for g in range(len(roots)):
        files = [e['file'] for e in ents if e['group'] == g]
        if len(files) == 1:
            st = '단독(변형 미발견, 미확정)'
        elif any(h['a'] in files and h['b'] in files for h in b['high']):
            st = '높은 확률 후보(§5 같은 그림 장 공유)'
        else:
            st = '정확 사본'
        groups.append(dict(id=g, files=files, status=st))
    m['groups'], m['n_units'] = groups, len(groups)
    m['bundle_check'] = dict(tool='seq_bundle.py', threshold=b['threshold'], high=b['high'], weak=b['weak'], frames_per_file=b['frames_per_file'],
                             note='약한 공유는 미확정으로 두고 합치지 않음. 회전·반전·다시 그린 변형은 못 찾을 수 있음')
    with open(manifest_path, 'w', encoding='utf-8') as fh:
        json.dump(m, fh, ensure_ascii=False, indent=1)
    print(f"평가 목록 묶음 갱신: 독립 단위 {m['n_units']} (필요 {J.need_wins(m['n_units'])}승)", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--frames', type=int, default=16)
    ap.add_argument('--apply', default='', help='판정 결과 json의 높은 확률 후보를 평가 목록 묶음에 반영하고 끝냄')
    ap.add_argument('--random-pairs', type=int, default=150)
    ap.add_argument('--out', default=os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data', 'judge_bundles.json'))
    a = ap.parse_args()
    if a.apply:
        return apply(a.apply)
    t0 = time.time()
    m = J.load_manifest()
    ev = [e['file'] for e in m['entries']]
    allf = V.file_list()   # 학습 파일(보정용 쌍도 여기서)
    keys = defaultdict(list)
    for f in allf:
        keys[name_key(f)].append(f)
    name_pairs = [p for v in keys.values() if len(v) > 1 for p in itertools.combinations(sorted(v), 2)]
    rng = random.Random(J.SEED)
    rand_pairs = set()
    while len(rand_pairs) < a.random_pairs:
        x, y = sorted(rng.sample(allf, 2))
        if name_key(x) != name_key(y):
            rand_pairs.add((x, y))
    rest = sorted(set(allf) - set(ev))
    ref = random.Random(J.SEED + 1).sample(rest, min(REF_FILES, len(rest)))
    need = set(ev) | set(ref) | {f for p in name_pairs for f in p} | {f for p in rand_pairs for f in p}
    frames = {}
    for f in sorted(need):
        try:
            frames[f] = load_frames(f, a.frames)
        except Exception as e:
            print('읽기 실패', f, type(e).__name__, flush=True)
            frames[f] = []
    print(f'파일 {len(frames)}개 장 읽기 {time.time() - t0:.0f}초', flush=True)
    stats = Counter()
    memo = {}
    res = dict(name=[], random=[], eval=[])
    for kind, pairs in (('name', name_pairs), ('random', sorted(rand_pairs)), ('eval', list(itertools.combinations(ev, 2)))):
        t1 = time.time()
        for x, y in pairs:
            res[kind].append((x, y, round(pair_score(x, y, frames, stats, ref, memo), 3)))
        print(kind, len(pairs), f'{time.time() - t1:.0f}초', flush=True)
    dist = {k: sorted(v[2] for v in res[k]) for k in ('name', 'random')}

    def q(v, p):
        return float(np.quantile(v, p)) if v else None
    rmax = max(dist['random']) if dist['random'] else 0.0
    # 높은 확률 후보: 무작위 쌍의 최댓값을 넘고 0.5 이상(장 절반 이상을 맞춘 같은 그림으로 공유)
    thr = max(0.5, rmax + 1e-9)
    cand = [r for r in res['eval'] if r[2] >= thr]
    weak = [r for r in res['eval'] if 0 < r[2] < thr]
    out = dict(version=1, frames_per_file=a.frames, same_frame_f1=SAME_FRAME, top=TOP, max_obj=MAX_OBJ, threshold=thr,
               aligned=stats['aligned'], skipped_big=stats['skipped'], common_frames=stats['common'], ref_files=len(ref), common_at=COMMON, seconds=round(time.time() - t0),
               calib=dict(name_pairs=len(dist['name']), random_pairs=len(dist['random']),
                          name_q=[q(dist['name'], p) for p in (0.1, 0.25, 0.5, 0.75, 0.9)],
                          random_q=[q(dist['random'], p) for p in (0.5, 0.9, 0.99)], random_max=rmax,
                          name_ge_thr=sum(v >= thr for v in dist['name'])),
               eval_pairs=len(res['eval']), high=[dict(a=x, b=y, share=s) for x, y, s in sorted(cand, key=lambda r: -r[2])],
               weak=[dict(a=x, b=y, share=s) for x, y, s in sorted(weak, key=lambda r: -r[2])],
               name_pairs=[dict(a=x, b=y, share=s) for x, y, s in res['name']])
    with open(a.out, 'w', encoding='utf-8') as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    print(json.dumps({k: out[k] for k in ('threshold', 'aligned', 'skipped_big', 'common_frames', 'seconds', 'calib', 'eval_pairs')}, ensure_ascii=False), flush=True)
    print('높은 확률 후보', len(cand), cand[:10], flush=True)
    print('약한 공유', len(weak), weak[:10], flush=True)


if __name__ == '__main__':
    main()
