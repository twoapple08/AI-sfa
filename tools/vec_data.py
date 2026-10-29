#!/usr/bin/env python3
"""영상 → SFA 딥러닝 학습 자료 만들기 (2026-10-29).

사용자 10-29: 가진 SFA 파일 전부를 영상으로 인코딩한 버전(1080p는 혼자 화질이 높아 안 맞으니 일부러 720·480으로 낮춰서)을 보고
실제 파일 배치(오브젝트를 어떻게 놓았는지)를 맞히게 학습하자.
파일마다(무작위 설정): 영상 폭 640(360p)·854(480p)·1280(720p) 중 하나, 선 굵기 배율 0.75–1.5, H.264 CRF 23–35, 24fps.
그림: 우리 렌더러(sfa_render)로 그림 → 인코딩 → 풀기 → 640 폭으로 줄임.
정답(640 폭, 파일 기하에서 직접): 오브젝트를 그리는 순서대로 번호를 칠한 번호판에서 '화면에 보이는 부분'만
- center: 선 가운데(1px)       - pts: 선 끝(점 찍을 자리, 가우스 σ 1.5)    - ori: 선 방향(cos2θ, sin2θ ×127)
- fill: 칠한 면                - cid: 가운데선 픽셀의 오브젝트 번호(장 안 순서+1, 같은 선 판단·채점용)
투명(알파 0) 선은 그리지 않는다(보이지 않음). 글로우는 그림에만 들어가고 정답에는 없다.
출력: 파일·설정마다 npz 하나(img uint8 [N,H,640,3], center/pts/fill uint8 [N,H,640], ori int8 [N,2,H,640], cid uint16).
사용: python tools/vec_data.py <out_dir> [--files 경로목록.txt] [--max-frames 40] [--workers 4] [--seed 0] [--exclude-4711]
"""
import argparse
import csv
import json
import os
import subprocess
import sys
import tempfile
import zipfile
import xml.etree.ElementTree as ET

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sfa_render as R  # noqa: E402

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data', 'user_sfa')
OUT_W = 640
HOLDOUT = ('4711', '4.7.1.1', '47112',  # 4711_2 합작: 실제 영상 + 정답이 있어 최종 시험용으로 뺀다
           # 사용자 10-29 "4711만 말고 보내 준 애니메이션 중 최상위 퀄리티 파일들을 대상으로": 영상과 함께 배포된 대표작(앱 내보내기 영상 = 진짜 시험)
           '스파 연계 교본', '묶음3_무기도구/sr.sfa', '뇌 빼고', '대홍련빙륜환', '수평선', 'S2aqoie_pt', 'kirara jump', 'ㅇㅇㅇㅇㅇㅇ (1)', '묶음3_무기도구/A.sfa')


def dense(kind, pts, step=1.0, max_n=4000):
    """오브젝트 → 표본점. 화면에서 아주 먼 좌표(일부 파일에 있음)는 점 수가 폭발하므로 max_n으로 자른다."""
    pts = [np.asarray(p, float) for p in pts]
    if not pts or not np.isfinite(np.array(pts)).all():
        return np.zeros((0, 2))
    step = max(step, (sum(np.linalg.norm(b - a) for a, b in zip(pts, pts[1:])) * (np.pi if kind == '2' else 1)) / max_n)
    if kind == '1' and len(pts) >= 2:
        n = max(2, int(np.linalg.norm(pts[1] - pts[0]) / step) + 1)
        t = np.linspace(0, 1, n)[:, None]
        return pts[0] * (1 - t) + pts[1] * t
    if kind == '3' and len(pts) >= 3:
        L = np.linalg.norm(pts[1] - pts[0]) + np.linalg.norm(pts[2] - pts[1])
        t = np.linspace(0, 1, max(3, int(L / step) + 1))[:, None]
        return (1 - t) ** 2 * pts[0] + 2 * (1 - t) * t * pts[1] + t ** 2 * pts[2]
    if kind == '2' and len(pts) >= 2:
        c = (pts[0] + pts[1]) / 2
        r = np.linalg.norm(pts[1] - pts[0]) / 2
        a = np.linspace(0, 2 * np.pi, max(12, int(2 * np.pi * r / step)))
        return c + r * np.c_[np.cos(a), np.sin(a)]
    return np.zeros((0, 2))


def draw_order(fr):
    """렌더러와 같은 순서: 레이어 순(숨긴 레이어 제외) → DrawOrder(없으면 ID). 채우기는 주인 곡선 앞."""
    aos = fr.findall('AO')
    layers = fr.findall('LayerDef')
    if layers:
        lay = [l.get('ID') for l in layers if l.get('Visible') != 'false']
    else:
        lay = list(dict.fromkeys(a.get('LayerId', '0') for a in aos))
    out = []
    for L in lay:
        out += sorted((a for a in aos if a.get('LayerId', '0') == L), key=lambda a: int(a.get('DrawOrder') or a.get('ID')))
    return out


ATTR = ['thick', 'lr', 'lg', 'lb', 'la', 'g_rad', 'g_thick', 'g_alpha', 'gr', 'gg', 'gb', 'fr', 'fg', 'fb', 'fa', 'order']
# 속성 정답(사용자 10-29 "페인트·글로우·투명도·선 굵기·색·레이어까지 모든 기능을 적재적소에"): uint8 16채널
# thick = 선 폭(px@640) log1p(w)/log1p(256)*255, lr..la = 선 RGBA, g_rad·g_thick = log1p(값)/log1p(300)*255, g_alpha = GlowAlpha,
# gr..gb = 글로우 색, fr..fa = 칠한 면 RGBA, order = 그 픽셀 맨 위 것(가운데선 픽셀은 그 선 자신)의 그리는 순서/전체*255 → 레이어·앞뒤.
# 선 속성·글로우는 가운데선 픽셀에만, 면 속성은 면 픽셀에만 의미가 있다(학습 손실도 그 자리만).


def _argb(v):
    v = int(v) & 0xFFFFFFFF
    return (v >> 16) & 255, (v >> 8) & 255, v & 255, v >> 24


def _lg(x, top):
    return int(round(255 * np.log1p(max(min(x, top), 0)) / np.log1p(top)))


def targets(seq, fr, W, H, thick_mul):
    """정답 지도들(W×H). 번호판 buf = 그리는 순서 번호(선·면 공통, 0 = 바탕) → 화면에 보이는 부분만 정답."""
    geo = R.Geo(seq, W, H)
    S = geo.S
    order = draw_order(fr)
    by_id = {a.get('ID'): a for a in fr.findall('AO')}
    owner = {}
    for r in fr.findall('FR'):
        first = next((s.get('ObjId') for s in r.findall('FS') if s.get('ObjId') in by_id), None)
        owner.setdefault(first, []).append(r)
    buf = np.zeros((H, W), np.int32)
    items = [None]  # 번호 → ('fill', rgba) | ('line', dict)
    objs = []  # (번호, kind, 표본점, 보이는 선인지)
    for a in order:
        for r in owner.get(a.get('ID'), []):
            polys = {}
            for s in r.findall('FS'):
                o = by_id.get(s.get('ObjId'))
                if o is None:
                    continue
                k = o.get('TypeId')
                t0 = float(s.get('StartT') or 0)
                t1 = float(s.get('EndT') if s.get('EndT') is not None else 1)
                if k == '3':
                    t0, t1 = min(max(t0, 0), 1), min(max(t1, 0), 1)
                polys.setdefault(s.get('Contour', '0'), []).extend(R.seg_points(k, R.obj_points(o, geo), t0, t1))
            cs = [np.round(np.clip(np.array(p), -20 * W, 20 * W)).astype(np.int32) for p in polys.values() if len(p) >= 3]
            if cs and R.alpha(r.get('Color')) > 0:
                items.append(('fill', _argb(r.get('Color'))))
                m = np.zeros((H, W), np.uint8)
                cv2.fillPoly(m, cs, 1)  # 여러 윤곽은 짝홀(cv2 기본)
                buf[m > 0] = len(items) - 1
        la = R.alpha(a.get('Color'))
        ga, gt = float(a.get('GlowAlpha') or 0), float(a.get('GlowThickness') or 0)
        glow = ga > 0 and gt > 0
        if la == 0 and not glow:
            continue  # 선도 글로우도 안 보임
        k = a.get('TypeId')
        P = dense(k, R.obj_points(a, geo))
        if len(P) < 2 or np.abs(P).max() > 20 * W:  # 화면에서 아주 먼 오브젝트(보이지 않음)
            continue
        T = min(float(a.get('ThicknessScale') or 1), 1000.0)
        w = R.PARAMS['base'] * max(S * T, 0) * thick_mul * R.PARAMS['stab']
        r, g, b, _ = _argb(a.get('Color'))
        gr, gg, gb, _ = _argb(a.get('GlowColor') or 4294967295)
        att = dict(thick=_lg(w, 256), lr=r, lg=g, lb=b, la=la, g_rad=_lg(float(a.get('GlowRadius') or 0) * S, 300),
                   g_thick=_lg(gt, 300) if glow else 0, g_alpha=int(min(ga, 255)) if glow else 0, gr=gr, gg=gg, gb=gb)
        items.append(('line', att))
        i = len(items) - 1
        if la > 0 and w > 0:  # 글로우만 있는 투명 선은 아래를 가리지 않는다
            cv2.polylines(buf, [np.round(P).astype(np.int32)], k == '2', int(i), max(1, int(round(min(w, 4 * W)))), lineType=cv2.LINE_8)
        objs.append((i, k, P, la > 0 and w > 0))
    N = max(len(items) - 1, 1)
    center = np.zeros((H, W), np.uint8)
    cid = np.zeros((H, W), np.uint16)
    ori = np.zeros((2, H, W), np.int8)
    attr = np.zeros((len(ATTR), H, W), np.uint8)
    # 면 속성·순서(맨 위 것)
    for j, it in enumerate(items):
        if it is None:
            continue
        m = buf == j
        if not m.any():
            continue
        attr[15][m] = int(round(255 * j / N))
        if it[0] == 'fill':
            for c, v in zip((11, 12, 13, 14), it[1]):
                attr[c][m] = v
    pts = []
    for i, k, P, opaque in objs:
        q = np.round(P).astype(int)
        ok = (q[:, 0] >= 0) & (q[:, 0] < W) & (q[:, 1] >= 0) & (q[:, 1] < H)
        if not ok.any():
            continue
        d = np.gradient(P, axis=0)
        th = np.arctan2(d[:, 1], d[:, 0])
        vis = np.zeros(len(P), bool)
        bq = buf[q[ok, 1], q[ok, 0]]
        vis[ok] = (bq == i) if opaque else (bq <= i)  # 투명 선(글로우만)은 뒤에 그린 것에 덮이지 않은 곳
        if not vis.any():
            continue
        ys, xs = q[vis, 1], q[vis, 0]
        center[ys, xs] = 1
        cid[ys, xs] = min(i, 65535)
        ori[0, ys, xs] = np.round(np.cos(2 * th[vis]) * 127).astype(np.int8)
        ori[1, ys, xs] = np.round(np.sin(2 * th[vis]) * 127).astype(np.int8)
        att = items[i][1]
        for c, key in enumerate(ATTR[:11]):
            attr[c, ys, xs] = att[key]
        attr[15, ys, xs] = int(round(255 * i / N))
        if k in ('1', '3'):
            for e in (0, len(P) - 1):
                x, y = q[e]
                if 0 <= x < W and 0 <= y < H:
                    win = buf[max(0, y - 2):y + 3, max(0, x - 2):x + 3]
                    if (win == i).any() or (not opaque and (win <= i).all()):
                        pts.append((P[e][0], P[e][1]))
    heat = np.zeros((H, W), np.float32)
    if pts:
        yy, xx = np.mgrid[0:H, 0:W]
        for x, y in pts:
            x0, x1, y0, y1 = int(max(0, x - 5)), int(min(W, x + 6)), int(max(0, y - 5)), int(min(H, y + 6))
            if x0 >= x1 or y0 >= y1:
                continue
            g = np.exp(-((xx[y0:y1, x0:x1] - x) ** 2 + (yy[y0:y1, x0:x1] - y) ** 2) / (2 * 1.5 ** 2))
            heat[y0:y1, x0:x1] = np.maximum(heat[y0:y1, x0:x1], g)
    fill = np.zeros((H, W), np.uint8)
    for j, it in enumerate(items):
        if it is not None and it[0] == 'fill':
            fill[buf == j] = 1
    return dict(center=center, pts=np.round(heat * 255).astype(np.uint8), ori=ori, fill=fill, cid=cid, attr=attr)


def encode_decode(frames_rgb, crf, fps=24):
    """그림들 → H.264 → 다시 풀기."""
    H, W = frames_rgb[0].shape[:2]
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, 'v.mp4')
        enc = subprocess.Popen(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(fps),
                                '-i', '-', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', str(crf), '-pix_fmt', 'yuv420p', p], stdin=subprocess.PIPE)
        for f in frames_rgb:
            enc.stdin.write(np.ascontiguousarray(f).tobytes())
        enc.stdin.close()
        enc.wait()
        out = subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-i', p, '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], capture_output=True).stdout
    a = np.frombuffer(out, np.uint8)
    n = a.size // (W * H * 3)
    return a[:n * W * H * 3].reshape(n, H, W, 3)


def one(job):
    rel, out_dir, seed, max_frames, res = job
    rng = np.random.default_rng(seed)
    path = os.path.join(ROOT, rel)
    try:
        z = zipfile.ZipFile(path)
        root = ET.fromstring(z.read(z.namelist()[0]))
    except Exception as e:
        return rel, 'err:' + type(e).__name__
    frs = root.findall('Frame')
    if not frs:
        return rel, 'empty'
    hwr = float(root.get('HeightWidthRatio') or 0.5625) or 0.5625
    W_enc = int(res) if res else int(rng.choice([640, 854, 1280], p=[0.2, 0.5, 0.3]))  # 커리큘럼(사용자 10-29): 1920 → 1280 → 854 → 640 단계별로 따로 만든다
    u = float(rng.uniform(0.75, 1.5))
    crf = int(rng.integers(23, 36))
    n = len(frs)
    if n > max_frames:  # 이어진 구간 하나(앞뒤 장을 함께 보게)
        s = int(rng.integers(0, n - max_frames + 1))
        frs = frs[s:s + max_frames]
    H_enc = int(round(W_enc * hwr / 2)) * 2
    H = int(round(OUT_W * hwr))
    R.PARAMS['pad'] = 0.0
    imgs, tg = [], []
    try:
        for fr in frs:
            R.PARAMS['thick_mul'] = W_enc / 1920 * u
            imgs.append(R.render_frame(root, fr, W_enc, H_enc))
            tg.append(targets(root, fr, OUT_W, H, OUT_W / 1920 * u))
    except Exception as e:
        return rel, 'err:' + type(e).__name__
    dec = encode_decode(imgs, crf)
    dec = np.stack([cv2.resize(f, (OUT_W, H), interpolation=cv2.INTER_AREA) for f in dec[:len(tg)]])
    name = rel.replace('/', '__').replace(' ', '_')[:-4] + f'__w{W_enc}_c{crf}.npz'
    np.savez_compressed(os.path.join(out_dir, name), img=dec,
                        center=np.stack([t['center'] for t in tg]), pts=np.stack([t['pts'] for t in tg]),
                        ori=np.stack([t['ori'] for t in tg]), fill=np.stack([t['fill'] for t in tg]), cid=np.stack([t['cid'] for t in tg]),
                        attr=np.stack([t['attr'] for t in tg]),
                        meta=json.dumps(dict(file=rel, W_enc=W_enc, thick=u, crf=crf, hwr=hwr, frames=len(tg), attr=ATTR)))
    return rel, f'ok {len(tg)}'


def file_list(exclude_holdout=True, only=None):
    rows = list(csv.DictReader(open(os.path.join(ROOT, 'index.csv'), encoding='utf-8-sig')))
    out = []
    for r in rows:
        if r['상태'] or not r['장']:
            continue
        hold = any(k in r['경로'] for k in HOLDOUT)
        if only == 'holdout' and not hold:
            continue
        if only != 'holdout' and exclude_holdout and hold:
            continue
        out.append(r['경로'])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('out_dir')
    ap.add_argument('--max-frames', type=int, default=40)
    ap.add_argument('--workers', type=int, default=4)
    ap.add_argument('--seed', type=int, default=0)
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--repeat', type=int, default=1, help='파일마다 다른 무작위 설정으로 몇 번 만들지')
    ap.add_argument('--res', type=int, default=0, help='영상 폭 고정(1920·1280·854·640). 0이면 무작위')
    a = ap.parse_args()
    os.makedirs(a.out_dir, exist_ok=True)
    files = file_list()
    if a.limit:
        files = files[:a.limit]
    jobs = [(f, a.out_dir, a.seed * 100003 + i * 7919 + r, a.max_frames, a.res) for r in range(a.repeat) for i, f in enumerate(files)]
    from multiprocessing import Pool
    with Pool(a.workers) as pool:
        for k, (rel, st) in enumerate(pool.imap_unordered(one, jobs)):
            if not st.startswith('ok') or k % 25 == 0:
                print(k + 1, '/', len(jobs), rel, st, flush=True)
    print('끝', len(jobs))


if __name__ == '__main__':
    main()
