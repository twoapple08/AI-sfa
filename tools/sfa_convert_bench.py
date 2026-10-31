#!/usr/bin/env python3
"""수집 SFA로 영상 → SFA 변환기 채점하기 (2026-10-29).

사용자 10-29: "스파 파일을 많이 줬는데 그걸 기반으로 고쳐볼 수 없어?" → SFA 장을 그려서 4711 영상처럼 망가뜨린 그림을
변환기에 넣고, 원래 SFA(정답)와 비교한다. 정답 붙은 시험 문제를 파일 수만큼 만들 수 있다.
망가뜨리기(4711_2 영상 ↔ 정답 SFA 먹 양 비교로 맞춤, 근거 장 5개): 1280 폭·굵기 1.1배로 그림 → 640 폭으로 줄임 → 가우스 0.8 → JPEG 품질 35.
채점(장마다):
- 오브젝트 수 우리/정답
- F1: 정답 그림과 변환 그림의 가운데선이 3px 안에서 겹치는 정도
- 쪼개짐: 정답 오브젝트 하나를 덮는(표본점 50% 이상이 그 오브젝트 3px 안) 우리 오브젝트 수의 평균(1에 가까울수록 '한 선 = 한 오브젝트')
- 놓침: 정답 오브젝트 중 표본점 50% 이상이 우리 선에서 3px 밖인 비율
사용: python tools/sfa_convert_bench.py <out.jsonl> [--files N] [--frames-per-file 3] [--only-lines]
"""
import argparse
import csv
import json
import os
import sys
import zipfile
import xml.etree.ElementTree as ET

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sfa_render as R  # noqa: E402
import video_to_sfa as V  # noqa: E402

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data', 'user_sfa')
W = 640


def degrade(img_rgb, Wout=W, blur=0.8, jpeg=35):
    h = int(round(img_rgb.shape[0] * Wout / img_rgb.shape[1]))
    g = cv2.resize(cv2.cvtColor(img_rgb, cv2.COLOR_RGB2BGR), (Wout, h), interpolation=cv2.INTER_AREA)
    if blur:
        g = cv2.GaussianBlur(g, (0, 0), blur)
    ok, b = cv2.imencode('.jpg', g, [cv2.IMWRITE_JPEG_QUALITY, jpeg])
    return cv2.imdecode(b, 1)


def dense(kind, pts, step=2.0):
    """오브젝트 기하 → 2px 간격 표본점."""
    pts = [np.asarray(p, float) for p in pts]
    if kind in ('1', 1) and len(pts) >= 2:
        n = max(2, int(np.linalg.norm(pts[1] - pts[0]) / step) + 1)
        t = np.linspace(0, 1, n)[:, None]
        return pts[0] * (1 - t) + pts[1] * t
    if kind in ('3', 3) and len(pts) >= 3:
        L = np.linalg.norm(pts[1] - pts[0]) + np.linalg.norm(pts[2] - pts[1])
        t = np.linspace(0, 1, max(3, int(L / step) + 1))[:, None]
        return (1 - t) ** 2 * pts[0] + 2 * (1 - t) * t * pts[1] + t ** 2 * pts[2]
    if kind in ('2', 2) and len(pts) >= 2:
        c = (pts[0] + pts[1]) / 2
        r = np.linalg.norm(pts[1] - pts[0]) / 2
        a = np.linspace(0, 2 * np.pi, max(8, int(2 * np.pi * r / step)))
        return c + r * np.c_[np.cos(a), np.sin(a)]
    return np.zeros((0, 2))


def gt_objects(seq, fr, Wr, Hr):
    geo = R.Geo(seq, Wr, Hr)
    out = []
    for ao in fr.findall('AO'):
        k = ao.get('TypeId')
        P = dense(k, R.obj_points(ao, geo))
        if len(P):
            out.append(P * (W / Wr))
    return out


def our_objects(regions, strokes):
    out = []
    for group, _ in regions:
        for _, segs in group:
            out += [dense(k, pts) for k, pts, _ in segs]
    for segs, _ in strokes:
        out += [dense(k, pts) for k, pts, _ in segs]
    return [o for o in out if len(o)]


def score(gt, ours, shape, tol=3.0):
    H, Wd = shape
    def canvas(objs):
        m = np.zeros((H, Wd), np.uint8)
        for P in objs:
            q = np.round(P).astype(int)
            ok = (q[:, 0] >= 0) & (q[:, 0] < Wd) & (q[:, 1] >= 0) & (q[:, 1] < H)
            m[q[ok, 1], q[ok, 0]] = 1
        return m
    mg, mo = canvas(gt), canvas(ours)
    dg = cv2.distanceTransform((1 - mg).astype(np.uint8), cv2.DIST_L2, 3)
    do = cv2.distanceTransform((1 - mo).astype(np.uint8), cv2.DIST_L2, 3)
    look = lambda d, P: d[np.clip(np.round(P[:, 1]).astype(int), 0, H - 1), np.clip(np.round(P[:, 0]).astype(int), 0, Wd - 1)]
    p = float(np.mean([v for P in ours for v in (look(dg, P) <= tol)])) if ours else 0.0
    r = float(np.mean([v for P in gt for v in (look(do, P) <= tol)])) if gt else 0.0
    f1 = 2 * p * r / max(p + r, 1e-9)
    # 쪼개짐·놓침: 정답 오브젝트마다 덮는 우리 오브젝트 수
    frag, miss = [], 0
    for G in gt:
        if len(G) < 4:
            continue
        mG = canvas([G])
        dG = cv2.distanceTransform((1 - mG).astype(np.uint8), cv2.DIST_L2, 3)
        if (look(do, G) <= tol).mean() < 0.5:
            miss += 1
            continue
        frag.append(sum(1 for O in ours if (look(dG, O) <= tol).mean() >= 0.5))
    return dict(f1=round(f1, 3), n_gt=len(gt), n_ours=len(ours), frag=round(float(np.mean(frag)), 2) if frag else None,
                miss=round(miss / max(len([G for G in gt if len(G) >= 4]), 1), 3))


def pick_files(n, only_lines, seed=0):
    rows = list(csv.DictReader(open(os.path.join(ROOT, 'index.csv'), encoding='utf-8-sig')))
    ok = []
    for r in rows:
        if r['상태'] or not r['장']:
            continue
        if only_lines and (r['글로우'] not in ('0', '') or r['채우기'] not in ('0', '')):
            continue
        ok.append(r['경로'])
    rng = np.random.default_rng(seed)
    rng.shuffle(ok)
    return ok[:n]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('out')
    ap.add_argument('--files', type=int, default=60)
    ap.add_argument('--frames-per-file', type=int, default=3)
    ap.add_argument('--only-lines', action='store_true')
    ap.add_argument('--kw', default='{}', help='frame_strokes 설정(JSON)')
    a = ap.parse_args()
    kw = dict(corner=50, line_tol=1.5, quad_tol=2.0)
    kw.update(json.loads(a.kw))
    R.PARAMS['pad'] = 0.0
    R.PARAMS['thick_mul'] = 1.1
    res = []
    with open(a.out, 'w', encoding='utf-8') as fh:
        for rel in pick_files(a.files, a.only_lines):
            path = os.path.join(ROOT, rel)
            try:
                z = zipfile.ZipFile(path)
                head = z.open(z.namelist()[0]).read(800).decode('utf-8', 'replace')
                import re
                n = int(re.search(r'FrameCount="(\d+)"', head).group(1))
            except Exception:
                continue
            want = set(np.linspace(0, n - 1, min(a.frames_per_file, n)).astype(int).tolist())
            try:
                for seq, fr in R.iter_frames(path, want):
                    hwr = float(seq.get('HeightWidthRatio') or 0.5625) or 0.5625
                    Wr, Hr = 1280, int(round(1280 * hwr))
                    img = degrade(R.render_frame(seq, fr, Wr, Hr))
                    gt = gt_objects(seq, fr, Wr, Hr)
                    if not gt:
                        continue
                    (reg, st), _, _ = V.frame_strokes(img, **kw)
                    s = score(gt, our_objects(reg, st), img.shape[:2])
                    s.update(file=rel, frame=int(fr.get('Position')))
                    fh.write(json.dumps(s, ensure_ascii=False) + '\n')
                    fh.flush()
                    res.append(s)
            except Exception as e:
                print('건너뜀', rel, type(e).__name__, e, file=sys.stderr)
    if res:
        f1 = np.mean([r['f1'] for r in res])
        ratio = np.median([r['n_ours'] / max(r['n_gt'], 1) for r in res])
        frag = np.mean([r['frag'] for r in res if r['frag'] is not None])
        miss = np.mean([r['miss'] for r in res])
        print(f'장 {len(res)}  F1 {f1:.3f}  오브젝트 우리/정답 중앙 {ratio:.2f}  쪼개짐 {frag:.2f}  놓침 {miss:.3f}')


if __name__ == '__main__':
    main()
