#!/usr/bin/env python3
"""영상 → SFA 선화 변환기 1판 (2026-10-29).

대상: 스틱파이터로 만든 영상처럼 '균일한 굵기 선 + 단색 바탕' 선화. 4711_2 합작 원본 SFA(정답)는
장당 오브젝트 30–80개, 굵기 전부 1.0, 채우기·반투명·글로우 없음, 흰 바탕 + 검은 선 위주(docs/VIDEO-TO-SFA-2026-10-29.md).
방법(장마다):
1. 자르기(--crop) 후 --up 배 확대, 바탕색 = 가장 흔한 색. 바탕과 Lab 거리 --ink-thr 이상이면 먹.
2. 먹 → 가운데선(뼈대) → 끝점·갈림점 사이 선(effect_vectorize.trace), 짧은 가지(선 폭 1.5배 미만)는 버림.
3. 선마다 꺾임(--corner 도 이상)으로 나누고 직선(텐션 0)/2차 곡선으로 맞춤(cube_vector_sfa.fit_run).
4. 색 = 선 위 원본 픽셀 중앙값, 채도 낮고 어두우면 검정으로 맞춤. 굵기 = 장 전체 먹 폭 중앙값 하나(원본처럼 균일).
5. 이어진 조각 끝점은 AC로 잇는다(한 획).
영상 원본·결과 SFA(다른 작가 그림)는 저장소에 넣지 않는다.
사용: python tools/video_to_sfa.py <영상> <out.sfa> --frames 19380,19383,... | --start 초 --end 초 --fps 24
"""
import argparse
import os
import subprocess
import sys
import zipfile

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cube_vector_sfa import contour_segs, corners_open, fit_run, join_lines  # noqa: E402
from effect_vectorize import trace  # noqa: E402

BASE_PX = 1.14 * 8  # 렌더러 기준: 화면 폭 1920에서 굵기 1.0 선 폭(px)
# 측정 굵기 보정: 4711_2 영상(앱 출력, 정답 굵기 전부 1.0)에서 이 측정이 1.82로 나옴 → × 0.55 (근거 영상 1개, 2026-10-29)
TS_CAL = 0.55


def read_frames(video, idxs, crop):
    """영상 장 번호 목록 → BGR 배열들(자르기 적용)."""
    w, h = (int(v) for v in subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=width,height',
                                            '-of', 'csv=p=0', video], capture_output=True, text=True).stdout.split(','))
    want = sorted(set(idxs))
    sel = '+'.join(f'eq(n\\,{i})' for i in want)
    vf = f"select='{sel}'" + (f',crop={crop}' if crop else '')
    p = subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-i', video, '-vf', vf, '-vsync', '0', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-'],
                       capture_output=True)
    cw, ch = (int(crop.split(':')[0]), int(crop.split(':')[1])) if crop else (w, h)
    a = np.frombuffer(p.stdout, np.uint8)
    n = a.size // (cw * ch * 3)
    got = dict(zip(want, a[:n * cw * ch * 3].reshape(n, ch, cw, 3)))
    return [got[i] for i in idxs if i in got]


def merge_strokes(out, gap, ang=8.0, off=1.5):
    """갈림점에서 끊긴 곧은 선을 같은 색끼리 다시 잇는다(cube_vector_sfa.join_lines, 색은 1/32 단위로 묶음)."""
    groups = {}
    for segs, col in out:
        groups.setdefault(tuple((np.asarray(col) // 32).astype(int)), []).append((segs, 1.0, col))
    res = []
    for g in groups.values():
        res += [(segs, col) for segs, _, col in join_lines(g, gap=gap, ang=ang, off=off)]
    return res


def mass_regions(big, lab, mass, up, corner, line_tol, quad_tol, k=4, merge_de=15.0, min_area=30):
    """덩어리 픽셀을 Lab k-평균 색(가까운 색 합침)으로 나눠 색마다 윤곽 → [(넓이, [(hole, segs)...], bgr)]."""
    ys, xs = np.nonzero(mass)
    X = lab[ys, xs]
    k = min(k, len(X))
    _, lb, cen = cv2.kmeans(X, k, None, (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 0.5), 2, cv2.KMEANS_PP_CENTERS)
    lb = lb.ravel()
    for i in range(k):  # 가까운 색 합치기
        for j in range(i):
            if np.linalg.norm(cen[i] - cen[j]) < merge_de:
                lb[lb == i] = j
    out = []
    for c in np.unique(lb):
        mm = np.zeros(mass.shape, np.uint8)
        mm[ys[lb == c], xs[lb == c]] = 1
        mm = cv2.morphologyEx(mm, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
        mm = (cv2.GaussianBlur(mm.astype(np.float32), (0, 0), 1.5 * up) > 0.5).astype(np.uint8)  # 압축 계단 윤곽 다듬기
        bgr = np.median(big[ys[lb == c], xs[lb == c]], axis=0)
        cnts, hier = cv2.findContours(mm, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
        if hier is None:
            continue
        hier = hier[0]
        for i, cn in enumerate(cnts):
            if hier[i][3] != -1 or cv2.contourArea(cn) < min_area * up * up:
                continue
            group = [(False, contour_segs(cn[:, 0, :].astype(np.float64) / up, 1.5, corner, 2 * line_tol, 2 * quad_tol))]
            j = hier[i][2]
            while j != -1:
                if cv2.contourArea(cnts[j]) >= min_area * up * up:
                    group.append((True, contour_segs(cnts[j][:, 0, :].astype(np.float64) / up, 1.5, corner, 2 * line_tol, 2 * quad_tol)))
                j = hier[j][0]
            out.append((cv2.contourArea(cn), group, bgr))
    out.sort(key=lambda r: -r[0])
    return [(g, c) for _, g, c in out]


def frame_strokes(img, up=2, ink_thr=28.0, corner=35.0, line_tol=1.0, quad_tol=1.4, min_len=6, join=True, mass_px=10.0):
    from skimage.morphology import skeletonize
    big = cv2.resize(img, None, fx=up, fy=up, interpolation=cv2.INTER_CUBIC)
    lab = cv2.cvtColor(big, cv2.COLOR_BGR2LAB).astype(np.float32)
    q = (big // 16).reshape(-1, 3)
    vals, cnt = np.unique(q, axis=0, return_counts=True)
    bgq = vals[cnt.argmax()]
    bg_lab = lab.reshape(-1, 3)[(q == bgq).all(1)].mean(0)
    d = np.linalg.norm(lab - bg_lab, axis=2)
    m = (d > ink_thr).astype(np.uint8)
    e = 2 * up  # 자른 가장자리(검은 띠와 섞인 줄)는 버림
    m[:e], m[-e:], m[:, :e], m[:, -e:] = 0, 0, 0, 0
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
    n, cc, st, _ = cv2.connectedComponentsWithStats(m, 8)
    small = np.where(st[:, cv2.CC_STAT_AREA] < 4 * up * up)[0]
    m[np.isin(cc, small)] = 0
    # 굵은 덩어리(먹 폭 10px@640 이상 — 흐린 360p에선 보통 선도 먹 폭 약 6.5px, 뭉개진 빗금·칠한 면은 14px 이상) → 채우기 면, 나머지 → 선
    R = int(mass_px * up / 2)
    core = (cv2.distanceTransform(m, cv2.DIST_L2, 3) >= R).astype(np.uint8)
    n, cc, st, _ = cv2.connectedComponentsWithStats(core, 8)  # 선이 겹친 갈림점의 작은 핵은 덩어리가 아님
    core[np.isin(cc, np.where(st[:, cv2.CC_STAT_AREA] < 20 * up * up)[0])] = 0
    ker = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * R + 3, 2 * R + 3))
    mass = cv2.dilate(core, ker) & m
    regions = mass_regions(big, lab, mass, up, corner, line_tol, quad_tol) if mass.sum() else []
    m = m & (1 - cv2.dilate(mass, np.ones((3, 3), np.uint8)))
    dist = cv2.distanceTransform(m, cv2.DIST_L2, 3)
    sk = skeletonize(m > 0)
    paths = trace(sk)
    # 굵기: 흐림은 먹 총량을 바꾸지 않는다 → 선마다 (먹 진하기 합 ÷ 선 대비) ÷ 길이. 대비 = 선 위 거리값 상위 90%
    widths = []
    for pth in paths:
        if len(pth) < 10:
            continue
        ys, xs = np.array(pth).T
        c = float(np.percentile(d[ys, xs], 90))
        box = np.zeros_like(m)
        box[ys, xs] = 1
        box = cv2.dilate(box, np.ones((int(4 * up) | 1, int(4 * up) | 1), np.uint8)) & m
        widths.append(float(np.clip(d[box > 0] / max(c, 1), 0, 1).sum()) / len(pth))
    width = float(np.median(widths)) if widths else 2.0 * up
    out = []
    for pth in paths:
        if len(pth) < max(min_len, int(1.5 * width)):
            continue
        P = np.array([(x, y) for y, x in pth], np.float64) / up
        cols = np.array([big[y, x] for y, x in pth])
        col = np.median(cols, axis=0)
        hsv = cv2.cvtColor(np.uint8([[col]]), cv2.COLOR_BGR2HSV)[0, 0]
        if hsv[1] < 70 and hsv[2] < 110:
            col = np.zeros(3)
        cs = corners_open(P, 1.0, corner)
        segs = []
        for i, k in zip(cs[:-1], cs[1:]):
            if k - i >= 1:
                fit_run(P[i:k + 1], line_tol, quad_tol, segs)
        segs = [sg for sg in segs if np.linalg.norm(np.asarray(sg[1][-1]) - np.asarray(sg[1][0])) >= 0.75 * width / up or len(segs) == 1]
        if segs:
            out.append((segs, col))
    if join:
        out = merge_strokes(out, gap=1.5 * width / up)
    return (regions, out), width / up, bg_lab


def argb(bgr, a=255):
    b, g, r = (int(round(v)) for v in bgr)
    v = (a << 24) | (r << 16) | (g << 8) | b
    return v - (1 << 32) if v >= 1 << 31 else v


def write_sfa(path, frames, W, H, ts, bg=-1, name=None):
    """frames: [(regions, strokes), ...] → 여러 장 SFA(레이어 1개). 면(FR)이 아래, 선(굵기 균일)이 위."""
    name = name or os.path.splitext(os.path.basename(path))[0]
    oid = pid = 1
    body = []
    for k, (regions, strokes) in enumerate(frames):
        o = [f'<Frame ID="{k + 1}" Position="{k}" BackgroundColor="{bg}"><LayerDef ID="0" Name="Layer 1" Visible="true" Locked="false"/>']
        for group, col in regions:  # 채우기 면: 윤곽 조각을 AC로 잇고 FS로 묶음(cube_vector_sfa.Writer.region과 같은 형식), 테두리는 같은 색 가는 선
            c = argb(col)
            fs = []
            for ci, (_, segs) in enumerate(group):
                prev = None
                for kind, pts, _ in segs:
                    s = [f'<AO ID="{oid}" TypeId="{kind}" Color="{c}" LayerId="0" DrawOrder="{oid}" ThicknessScale="0.100" ObjectScale="1.0" '
                         'GlowRadius="0" GlowThickness="0" GlowColor="4294967295" GlowAlpha="0">']
                    for i, (x, y) in enumerate(pts):
                        ac = f'<AC ConnPtId="{prev}"/>' if (i == 0 and prev) else ''
                        s.append(f'<AP ID="{pid + i}" Flags="{8 if i == 0 else 9}" Index="{i}" X="{x / W * 100:.3f}" Y="{y / H * 100:.3f}">{ac}</AP>')
                    o.append(''.join(s) + '</AO>')
                    fs.append(f'<FS Kind="0" ObjId="{oid}" StartPtId="{pid}" EndPtId="{pid + len(pts) - 1}" StartT="0.0" EndT="1.0" Contour="{ci}"/>')
                    prev = pid + len(pts) - 1
                    oid += 1
                    pid += len(pts)
            o.append(f'<FR Color="{c}">' + ''.join(fs) + '</FR>')
        for segs, col in strokes:
            prev = None
            c = argb(col)
            for kind, pts, _ in segs:
                s = [f'<AO ID="{oid}" TypeId="{kind}" Color="{c}" LayerId="0" DrawOrder="{oid}" ThicknessScale="{ts:.3f}" ObjectScale="1.0" '
                     'GlowRadius="0" GlowThickness="0" GlowColor="4294967295" GlowAlpha="0">']
                for i, (x, y) in enumerate(pts):
                    ac = f'<AC ConnPtId="{prev}"/>' if (i == 0 and prev) else ''
                    s.append(f'<AP ID="{pid + i}" Flags="{8 if i == 0 else 9}" Index="{i}" X="{x / W * 100:.3f}" Y="{y / H * 100:.3f}">{ac}</AP>')
                o.append(''.join(s) + '</AO>')
                prev = pid + len(pts) - 1
                oid += 1
                pid += len(pts)
        body.append(''.join(o) + '</Frame>')
    xml = (f"<?xml version='1.0' encoding='utf-8'?>\n<Sequence Name=\"{name}\" HeightWidthRatio=\"{H / W:.6f}\" FrameCount=\"{len(frames)}\" "
           f"BackgroundColor=\"{bg}\">\n" + '\n'.join(body) + '\n</Sequence>\n')
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(name + '.xml', xml)
    return oid - 1


def convert(video, idxs, out, crop=None, **kw):
    imgs = read_frames(video, idxs, crop)
    H, W = imgs[0].shape[:2]
    frames, widths, bgs = [], [], []
    for im in imgs:
        s, w, bgl = frame_strokes(im, **kw)
        frames.append(s)
        widths.append(w)
        bgs.append(bgl)
    ts = max(0.05, float(np.median(widths)) * (1920 / W) / BASE_PX * TS_CAL)
    bg_bgr = cv2.cvtColor(np.uint8([[np.median(bgs, axis=0)]]), cv2.COLOR_LAB2BGR)[0, 0]
    n = write_sfa(out, frames, W, H, ts, bg=argb(bg_bgr))
    return dict(frames=len(frames), objects=n, per_frame=[sum(len(sg) for g, _ in f[0] for _, sg in g) + sum(len(s[0]) for s in f[1]) for f in frames], ts=round(ts, 3))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('video')
    ap.add_argument('out')
    ap.add_argument('--frames', help='영상 장 번호(쉼표)')
    ap.add_argument('--start', type=float)
    ap.add_argument('--end', type=float)
    ap.add_argument('--fps', type=float, default=24)
    ap.add_argument('--crop', help='w:h:x:y')
    ap.add_argument('--ink-thr', type=float, default=28.0)
    ap.add_argument('--corner', type=float, default=50.0)
    ap.add_argument('--line-tol', type=float, default=1.5)
    ap.add_argument('--quad-tol', type=float, default=2.0)
    a = ap.parse_args()
    if a.frames:
        idxs = [int(x) for x in a.frames.split(',')]
    else:
        vf = eval(subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=r_frame_rate', '-of', 'csv=p=0', a.video],
                                 capture_output=True, text=True).stdout.strip())
        idxs = [int(round(t * vf)) for t in np.arange(a.start, a.end, 1 / a.fps)]
    r = convert(a.video, idxs, a.out, a.crop, ink_thr=a.ink_thr, corner=a.corner, line_tol=a.line_tol, quad_tol=a.quad_tol)
    print(r['frames'], '장, 오브젝트', r['objects'], '장당 중앙', int(np.median(r['per_frame'])), '굵기', r['ts'])


if __name__ == '__main__':
    main()
