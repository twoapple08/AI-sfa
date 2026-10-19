#!/usr/bin/env python3
"""임팩트 후보를 앞뒤 문맥과 비교하는 지표. 모델 훈련 없음(고전 영상 처리만).

사용: python tools/impact_context.py <rows.csv> <원본 폴더> <out.csv> 
rows.csv 열: key,post_id,frames (그 밖의 열은 그대로 붙는다). 이어서 돌리면 out.csv에 있는 key는 건너뛴다.
IMPACT_CACHE=<폴더>를 주면 디코딩한 프레임을 npy로 보관해 재실행 때 다시 디코딩하지 않는다.

문제(2026-10-19 사용자): 32488 f120-122처럼 같은 컷 안에서 얼굴을 당겨 화면이 얼굴 면색(밝은 회색)과 남색 선만
남으면, 후보만 보는 지표(무채색·고대비·X-CLIP)는 '흑백 삽입'으로 오인한다. 원리: 임팩트는 흐름을 끊고 다른 그림
방식으로 끼워 넣은 프레임이다. 클로즈업·줌·카메라 이동·동화는 앞뒤 문맥의 면 색·선 색을 그대로 쓴다(면적 비율만
바뀐다). 그래서 면적 비율(무채색도·고대비 비율)이 아니라 '후보가 쓰는 색이 문맥에서도 쓰이던 색인가'를 잰다.

문맥: 앞쪽 = 후보 앞 3–12번째 프레임, 뒤쪽 = 후보 뒤 3–12번째 프레임(바로 붙은 2프레임은 전환·잔상이 많아 뺀다).
쪽마다 '주된 그림 방식' 색표를 만든다: 그 쪽 프레임의 40% 초과에서 화면 1% 이상을 차지한 면 색(5x5 이웃이 고른
화소, Lab 6단위 양자화) / 선 색(면이 아니고 주변보다 15 이상 어두운 국소 최저 화소, 선 화소의 5% 이상).
옆에 다른 임팩트·섬광 프레임이 몇 장 끼어 있어도 과반에 못 들면 색표에 들어가지 않는다.
지표:
- pre_fill / post_fill / pre_line / post_line: 후보의 면(선) 화소 중 그 쪽 색표의 어떤 색과도 Lab 거리 18 초과인 비율
  (후보 프레임별 값의 중앙값). 문맥 프레임이 3장 미만이면 빈 칸.
- nov_max: 위 네 값의 최대값. 작으면 '앞뒤 둘 다와 같은 그림 방식'이다.
- drawn: 그림이 있는 후보 프레임 수/후보 프레임 수(Canny 에지 화소 0.2% 이상). 그림 없는 단색 번쩍임은 그림 방식
  비교가 성립하지 않아 기존 규칙에 맡긴다(253949 f32-33처럼 흰 섬광+실루엣이 섞인 임팩트를 살리려고 전부 그림일 때만 판정).
- same_style: nov_max<0.2 이고 후보 프레임이 전부 그림 있음이고 앞뒤 두 쪽 모두 계산됨 → 1. '같은 컷 안의 클로즈업·줌·이동·동화'
  쪽 신호. 보정(2026-10-19, 확정 임팩트 63·아님 47): 임팩트 0건, 아님 8건이 1, 32488 f121-122도 1.
- invert: 후보 첫/끝 프레임과 바로 앞/뒤 프레임 반전본의 밝기 상관 최대값(참고).
시험했으나 뺀 것(2026-10-19): X-CLIP에 '앞 문맥 2+후보 4+뒤 문맥 2' 창과 '같은 장면 클로즈업' 등 반대 문구를 넣은
  점수(AUC 0.54), 면적 기반 무채색·고대비 증가량(줌에서 오판), SIFT 정합 수(AUC 0.45–0.65), 색 분포 컷 경계 자르기.
"""
import csv, glob, os, subprocess, sys
from collections import Counter
import numpy as np
import cv2

CTX, W, H = 24, 256, 144
Q, AREA, MAJ, SKIP, SIDE, MINF, DE, LM = 6.0, 0.01, 0.4, 2, 12, 3, 18.0, 15.0
NOV_T, EDGE_T = 0.2, 0.002


def frames(path, s, e):
    p = subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-i', path, '-vf',
                        f'select=between(n\\,{s}\\,{e}),scale={W}:{H}', '-vsync', '0',
                        '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], capture_output=True, stdin=subprocess.DEVNULL)
    a = np.frombuffer(p.stdout, np.uint8)
    n = a.size // (W * H * 3)
    return a[:n * W * H * 3].reshape(n, H, W, 3)


def cached(key, fn):
    d = os.environ.get('IMPACT_CACHE')
    if not d:
        return fn()
    p = os.path.join(d, key.replace(':', '_') + f'_{W}x{H}.npy')
    if os.path.exists(p):
        return np.load(p)
    F = fn()
    os.makedirs(d, exist_ok=True)
    np.save(p, F)
    return F


def regions(f):
    """(Lab, 면 마스크, 선 마스크)."""
    lab = cv2.cvtColor(f, cv2.COLOR_RGB2LAB).astype(np.float32)
    lab[..., 0] *= 100 / 255
    lab[..., 1:] -= 128
    mean = cv2.blur(lab, (5, 5))
    var = cv2.blur(lab * lab, (5, 5)) - mean * mean
    flat = var.sum(-1) < 12
    L = lab[..., 0]
    dark = (L < cv2.blur(L, (9, 9)) - LM) & (L <= cv2.erode(L, np.ones((3, 3), np.uint8)) + 1)
    return lab, flat, (~flat) & dark


def frame_pal(reg, kind):
    lab, fl, li = reg
    m = fl if kind == 'fill' else li
    pts = lab[m]
    if len(pts) == 0:
        return set()
    k, c = np.unique(np.round(pts / Q).astype(np.int32), axis=0, return_counts=True)
    thr = AREA * m.size if kind == 'fill' else max(5, 0.05 * len(pts))
    return {tuple(x) for x in k[c >= thr]}


def side_pal(regs, kind):
    cnt = Counter()
    for r in regs:
        cnt.update(frame_pal(r, kind))
    need = int(np.floor(MAJ * len(regs))) + 1
    return np.array([k for k, v in cnt.items() if v >= need], np.float32).reshape(-1, 3) * Q


def novel(lab, mask, pal):
    pts = lab[mask]
    if len(pts) == 0:
        return 0.0
    if len(pal) == 0:
        return 1.0
    k, inv = np.unique(np.round(pts / 3).astype(np.int32), axis=0, return_inverse=True)
    d = np.sqrt(((k[:, None, :] * 3.0 - pal[None]) ** 2).sum(-1)).min(1)
    return float((d[inv.ravel()] > DE).mean())


def corr(x, y):
    x, y = x - x.mean(), y - y.mean()
    d = np.sqrt((x * x).sum() * (y * y).sum())
    return float((x * y).sum() / d) if d > 1e-6 else 0.0


def features(F, a, s, b):
    n = b - a + 1
    i0, i1 = a - s, a - s + n
    cand = list(F[i0:i1])
    edge = [float((cv2.Canny(f, 60, 150) > 0).mean()) for f in cand]
    drawn = [f for f, e in zip(cand, edge) if e >= EDGE_T]
    creg = [regions(f) for f in (drawn or cand)]
    r = {}
    for side, ctx in (('pre', F[max(0, i0 - SIDE):max(0, i0 - SKIP)]), ('post', F[i1 + SKIP:i1 + SIDE])):
        if len(ctx) < MINF:
            r[side + '_fill'] = r[side + '_line'] = ''
            continue
        regs = [regions(f) for f in ctx]
        for kind, j in (('fill', 1), ('line', 2)):
            pal = side_pal(regs, kind)
            r[f'{side}_{kind}'] = round(float(np.median([novel(c[0], c[j], pal) for c in creg])), 3)
    vals = [r[k] for k in ('pre_fill', 'post_fill', 'pre_line', 'post_line') if r[k] != '']
    r['nov_max'] = max(vals) if vals else ''
    r['drawn'] = f'{len(drawn)}/{len(cand)}'
    r['same_style'] = int(vals != [] and r['pre_fill'] != '' and r['post_fill'] != ''
                          and r['nov_max'] < NOV_T and len(drawn) == len(cand))
    g = lambda f: cv2.cvtColor(f, cv2.COLOR_RGB2GRAY).astype(np.float32)
    inv = [corr(g(c), 255 - g(F[j])) for c, j in ((cand[0], i0 - 1), (cand[-1], i1)) if 0 <= j < len(F)]
    r['invert'] = round(max(inv), 3) if inv else ''
    return r



def main():
    rows_csv, src, out_csv = sys.argv[1:4]
    files = {os.path.basename(f).split('.')[0]: f for f in glob.glob(src + '/*')}
    rows = list(csv.DictReader(open(rows_csv, encoding='utf-8-sig')))
    done = set()
    if os.path.exists(out_csv):
        done = {r['key'] for r in csv.DictReader(open(out_csv, encoding='utf-8'))}
    cols = ['pre_fill', 'post_fill', 'pre_line', 'post_line', 'nov_max', 'drawn', 'same_style', 'invert']
    fo = open(out_csv, 'a', newline='', encoding='utf-8')
    w = csv.DictWriter(fo, fieldnames=list(rows[0]) + [c for c in cols if c not in rows[0]])
    if not done:
        w.writeheader()
    for n, r in enumerate(rows):
        fr = r['frames']
        if r['key'] in done or r['post_id'] not in files or not fr[:1].isdigit():
            continue
        a, b = [int(v) for v in (fr.split('-') + [fr])[:2]]
        s = max(0, a - CTX)
        F = cached(r['key'], lambda: frames(files[r['post_id']], s, b + CTX))
        if len(F) < (a - s) + 1:
            continue
        b = min(b, s + len(F) - 1)
        res = dict(r)
        res.update(features(F, a, s, b))
        w.writerow(res)
        fo.flush()
        if n % 50 == 0:
            print('progress', n, len(rows), flush=True)
    print('DONE', flush=True)


if __name__ == '__main__':
    main()
