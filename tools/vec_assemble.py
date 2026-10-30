#!/usr/bin/env python3
"""조립(2026-10-30): 학습 모델의 지도 → 실제 SFA 오브젝트. 영상 → .sfa 변환의 마지막 단계.

장마다:
1) 모델(fp32)로 지도: 가운데선·선 끝·면·속성(굵기·선 RGBA·글로우·면 RGBA·그리는 순서)·배경색.
2) 면: 면 지도(>0.5) 덩어리마다 윤곽 → 다각형(투명 테두리 선 + FR), 색·투명도 = 덩어리 안 예측 중앙값.
3) 선: 가운데선 지도(>0.5)를 2배로 키워 뼈대 → 조각 → 갈림점에서 곧게 이어지는 가지끼리 잇기(video_to_sfa.chain_paths)
   → 고리는 원, 나머지는 모서리에서 끊어 직선·2차 곡선(fit_rel). 굵기·색·글로우 = 선 위 예측 중앙값.
4) 순서: 오브젝트마다 '그리는 순서' 예측 중앙값으로 정렬(앱은 DrawOrder가 아니라 처음 나온 순서를 쓰므로 XML도 그 순서로).
5) 배경색 = 예측 중앙값. 레이어 하나. ID는 파일 전체에서 겹치지 않게(장마다 새 ID — 같은 ID가 장마다 다른 종류가 되지 않게, docs/FORMAT.md).
   점 표시는 파란점 규칙(묶음마다 Flags 3 하나, 이어진 꼭짓점은 한쪽만 표시).
6) --check: 만든 SFA를 다시 렌더해 원본 장과 비교(다른 픽셀 %), 나란히 시트.
속성 되돌리기는 vec_data.targets의 부호화를 거꾸로: 굵기 w(px@640) = expm1(v·log1p(256)), ThicknessScale = w / (8·1.14·640/1920).
사용: python vec_assemble.py 모델.pt 영상.mp4 출력.sfa [--frames 0-23] [--check 시트.jpg]
"""
import argparse
import os
import subprocess
import sys
import xml.etree.ElementTree as ET
import zipfile

import cv2
import numpy as np
import torch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vec_train as T  # noqa: E402
from cube_vector_sfa import corners_open  # noqa: E402
from effect_vectorize import trace  # noqa: E402
from video_to_sfa import chain_paths, fit_circle, fit_rel, smooth_open  # noqa: E402

W = 640
TS_PX = 8 * 1.14 * W / 1920  # ThicknessScale 1 = 640 폭에서 약 3.04px


def sig(a):
    return 1 / (1 + np.exp(-np.clip(a, -60, 60)))


def unlg(v, top):
    return float(np.expm1(v * np.log1p(top)))


def read_frames(video, H):
    p = subprocess.run(['ffmpeg', '-v', 'error', '-i', video, '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], capture_output=True)
    w0, h0 = map(int, subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=width,height',
                                      '-of', 'csv=p=0', video], capture_output=True, text=True).stdout.strip().split(',')[:2])
    fr = np.frombuffer(p.stdout, np.uint8).reshape(-1, h0, w0, 3)
    return fr, w0, h0


def maps(net, prev, cur, nxt):
    x = torch.from_numpy(np.concatenate([prev, cur, nxt], -1).astype(np.float32).transpose(2, 0, 1) / 255.0)[None]
    with torch.no_grad():
        return net(x)[0].numpy()


class Ids:
    def __init__(self):
        self.ao, self.ap = 1, 1000000


def ao_el(ids, type_id, color, ts=1.0, glow=None):
    g = glow or (0, 0, 4294967295, 0)
    o = ET.Element('AO', dict(ID=str(ids.ao), TypeId=str(type_id), Color=str(color), LayerId='0', DrawOrder=str(ids.ao), ThicknessScale=f'{ts:.3f}',
                              ObjectScale='1.0', GlowRadius=str(int(g[0])), GlowThickness=str(int(g[1])), GlowColor=str(g[2]), GlowAlpha=str(int(g[3]))))
    ids.ao += 1
    return o


def add_ap(ids, o, idx, xy, flags, W_, H_):
    ap = ET.SubElement(o, 'AP', dict(ID=str(ids.ap), Flags=str(flags), Index=str(idx), X=f'{xy[0] / W_ * 100:.4f}', Y=f'{xy[1] / H_ * 100:.4f}'))
    ids.ap += 1
    return ap


def argb(r, g, b, a=255):
    return (int(a) << 24) | (int(r) << 16) | (int(g) << 8) | int(b)


def connect(a, b):
    ET.SubElement(a, 'AC', dict(ConnPtId=b.get('ID')))
    ET.SubElement(b, 'AC', dict(ConnPtId=a.get('ID')))


def fill_items(p, H_, img=None, min_area=30, eps=1.2):
    """면 지도 → [(순서, [AO들], FR)] 만들 재료: (윤곽 점들, 색 RGBA, 순서)."""
    f = sig(p[4]) > 0.5
    a = sig(p[5:21])
    out = []
    n, lab, st, _ = cv2.connectedComponentsWithStats(f.astype(np.uint8), 8)
    for k in range(1, n):
        if st[k, cv2.CC_STAT_AREA] < min_area:
            continue
        m = lab == k
        # 윤곽은 3px 넓혀서: 면 지도는 선·흐린 가장자리를 빼고 잡혀 면과 선 사이에 바탕이 틈으로 보였다(오버드라이브 시험). 선이 위에 그려지니 넓혀도 덮인다
        mw = cv2.dilate(m.astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7)))
        cs, _ = cv2.findContours(mw, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        c = max(cs, key=cv2.contourArea)
        poly = cv2.approxPolyDP(c, eps, True)[:, 0, :].astype(float)
        if len(poly) < 3:
            continue
        rgba = [int(round(np.median(a[i][m]) * 255)) for i in (11, 12, 13, 14)]
        if img is not None:  # 색은 영상에서(모델 색 예측이 아직 약함, 2차 시험 10-30) — 테두리 2px 안쪽 화소 중앙값, 투명도만 모델
            mi = cv2.erode(m.astype(np.uint8), np.ones((5, 5), np.uint8)) > 0
            if mi.sum() < 10:
                mi = m
            rgba[:3] = [int(v) for v in np.median(img[mi], axis=0)]
            rgba[3] = 255  # 영상 화소는 이미 겹친 결과 색 — 투명도를 또 주면 바탕과 섞여 옅어진다(오버드라이브 회색 면이 밝게 나옴)
        out.append(dict(kind='fill', order=float(np.median(a[15][m])), poly=poly, rgba=rgba))
    return out


def line_items(p, img=None, up=2, corner=35.0, min_len=4.0):
    from skimage.morphology import skeletonize
    c = sig(p[0])
    a = sig(p[5:21])
    big = cv2.resize(c, None, fx=up, fy=up, interpolation=cv2.INTER_LINEAR)
    m = (big > 0.5).astype(np.uint8)
    if not m.any():
        return []
    dist = cv2.distanceTransform(m, cv2.DIST_L2, 3)
    sk = skeletonize(m > 0)
    paths = [pth for pth in trace(sk) if len(pth) >= 2]
    if not paths:
        return []
    A = [cv2.resize(a[i], None, fx=up, fy=up, interpolation=cv2.INTER_LINEAR) for i in range(16)]
    cols = [tuple(float(np.median(A[i][tuple(np.array(pth).T)])) * 255 for i in (1, 2, 3)) for pth in paths]
    mask_w = 2 * float(np.median(dist[sk])) if sk.any() else 4.0 * up
    chains = chain_paths(paths, cols, node_r=0.7 * mask_w, spur=1.2 * mask_w)
    out = []
    for pts, col in chains:
        P = pts / up
        L = float(np.linalg.norm(np.diff(P, axis=0), axis=1).sum())
        if L < min_len:
            continue
        q = np.clip(np.round(pts).astype(int), 0, [A[0].shape[1] - 1, A[0].shape[0] - 1])
        med = [float(np.median(A[i][q[:, 1], q[:, 0]])) for i in range(16)]
        w = unlg(med[0], 256)  # 선 폭 px@640
        rgba = [int(round(v * 255)) for v in med[1:5]]
        if img is not None:  # 색은 영상의 가운데선 화소에서(먹 쪽: 배경과 가장 다른 절반의 중앙값)
            qq = np.clip(np.round(pts / up).astype(int), 0, [img.shape[1] - 1, img.shape[0] - 1])
            px = img[qq[:, 1], qq[:, 0]].astype(float)
            rgba[:3] = [int(v) for v in np.median(px, axis=0)]
            if rgba[3] >= 128:
                rgba[3] = 255
        att = dict(ts=max(w / TS_PX, 0.05), rgba=rgba, order=med[15],
                   glow=(unlg(med[5], 300), unlg(med[6], 300), argb(*[int(round(v * 255)) for v in med[8:11]]), int(round(med[7] * 255))))
        circ = fit_circle(P)
        if circ is not None:
            (cx, cy), r = circ
            out.append(dict(kind='circle', segs=[(2, (np.array([cx, cy - r]), np.array([cx, cy + r])))], **att))
            continue
        P = smooth_open(P, 1.0)
        cs = corners_open(P, 1.5, corner)
        segs = []
        for i, k in zip(cs[:-1], cs[1:]):
            if k - i >= 1:
                for sg in fit_rel(P[i:k + 1]):
                    segs.append((sg[0], sg[1]))
        if segs:
            out.append(dict(kind='line', segs=segs, **att))
    return out


def frame_xml(items, bg, ids, W_, H_, fid, pos):
    fr = ET.Element('Frame', dict(BackgroundColor=str(argb(*bg)), ID=str(fid), Position=str(pos)))
    ET.SubElement(fr, 'LayerDef', dict(ID='0', Name='Layer 1', Visible='true', Locked='false'))
    frs = []
    for it in sorted(items, key=lambda t: t['order']):
        if it['kind'] == 'fill':
            poly = it['poly']
            objs = []
            n = len(poly)
            for k in range(n):
                o = ao_el(ids, 1, 0)
                a0 = add_ap(ids, o, 0, poly[k], 3 if k == 0 else 8, W_, H_)
                a1 = add_ap(ids, o, 1, poly[(k + 1) % n], 8 if k == n - 1 else 9, W_, H_)
                objs.append((o, a0, a1))
                fr.append(o)
            for k in range(n):
                connect(objs[k][2], objs[(k + 1) % n][1])
            r = ET.Element('FR', dict(Color=str(argb(*it['rgba'][:3], it['rgba'][3]))))
            for o, a0, a1 in objs:
                ET.SubElement(r, 'FS', dict(Kind='0', ObjId=o.get('ID'), StartPtId=a0.get('ID'), EndPtId=a1.get('ID'), StartT='0.0', EndT='1.0'))
            frs.append(r)
            continue
        col = argb(*it['rgba'][:3], it['rgba'][3])
        g = it['glow'] if it['glow'][3] > 20 and it['glow'][1] > 1 else None
        prev_end = None
        for si, (tid, pts) in enumerate(it['segs']):
            o = ao_el(ids, tid, col, it['ts'], g)
            aps = []
            for j, xy in enumerate(pts):
                if j == 0:
                    fl = 3 if si == 0 else 8   # 묶음 첫 점 = 파란점, 이어지는 꼭짓점은 앞 선 끝(9)만 표시
                else:
                    fl = 9
                aps.append(add_ap(ids, o, j, xy, fl, W_, H_))
            if prev_end is not None:
                connect(prev_end, aps[0])
            prev_end = aps[-1] if tid != 2 else None
            fr.append(o)
    for r in frs:
        fr.append(r)
    return fr


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('model')
    ap.add_argument('video')
    ap.add_argument('out')
    ap.add_argument('--frames', default='', help='예: 0-23 또는 5,7 (비우면 전부)')
    ap.add_argument('--check', default='', help='다시 렌더해 원본과 비교한 시트(jpg)')
    a = ap.parse_args()
    ck = torch.load(a.model, map_location='cpu', weights_only=False)
    net = T.Net(pretrained=False)
    net.load_state_dict(ck['model'] if isinstance(ck, dict) and 'model' in ck else ck)
    net.eval()
    frs0, w0, h0 = read_frames(a.video, None)
    H = max(32, int(round(W * h0 / w0 / 32)) * 32)
    frs = np.stack([cv2.resize(f, (W, H), interpolation=cv2.INTER_AREA) for f in frs0])
    idx = list(range(len(frs)))
    if a.frames:
        idx = [i for part in a.frames.split(',') for i in (range(int(part.split('-')[0]), int(part.split('-')[1]) + 1) if '-' in part else [int(part)])]
    seq = ET.Element('Sequence', dict(Name=os.path.splitext(os.path.basename(a.out))[0], HeightWidthRatio=f'{h0 / w0:.6f}', FrameCount=str(len(idx)), BackgroundColor='-1'))
    ids = Ids()
    stats = []
    for pos, i in enumerate(idx):
        p = maps(net, frs[max(i - 1, 0)], frs[i], frs[min(i + 1, len(frs) - 1)])
        bg = [int(round(v * 255)) for v in np.median(sig(p[25:28]).reshape(3, -1), 1)]
        items = fill_items(p, H, frs[i]) + line_items(p, frs[i])
        seq.append(frame_xml(items, bg, ids, W, H, 100 + pos, pos))
        nf = sum(1 for t in items if t['kind'] == 'fill')
        nl = sum(len(t['segs']) for t in items if t['kind'] != 'fill')
        stats.append((i, nf, nl))
        print(f'장 {i}: 면 {nf}, 선 오브젝트 {nl}, 배경 {tuple(bg)}', flush=True)
    xml = ET.tostring(seq, encoding='unicode')
    name = os.path.splitext(os.path.basename(a.out))[0] + '.xml'
    with zipfile.ZipFile(a.out, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr(name, '<?xml version="1.0" encoding="UTF-8" ?>' + xml)
    print('저장:', a.out, '장', len(idx), '오브젝트', ids.ao - 1)
    if a.check:
        import sfa_render as R
        R.PARAMS['pad'] = 0.0
        R.PARAMS['thick_mul'] = W / 1920
        root = ET.fromstring(xml)
        rows, diffs = [], []
        for pos, i in enumerate(idx):
            im = np.asarray(R.render_frame(root, root.findall('Frame')[pos], W, H))[..., :3]
            d = np.abs(im.astype(int) - frs[i].astype(int)).max(-1)
            diffs.append(float((d > 40).mean() * 100))
            if pos < 6:
                rows.append(np.hstack([frs[i], im]))
        print('다시 렌더 비교(다른 픽셀 %, 기준 40):', [round(x, 1) for x in diffs], '평균', round(float(np.mean(diffs)), 1))
        cv2.imwrite(a.check, cv2.cvtColor(np.vstack(rows), cv2.COLOR_RGB2BGR))


if __name__ == '__main__':
    main()
