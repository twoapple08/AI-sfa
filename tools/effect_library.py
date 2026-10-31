#!/usr/bin/env python3
"""나카무라 임팩트 장면을 포물선 조각(2차 베지어) 이펙트 사전으로 만든다(AGENTS.md 이펙트 그리기 원칙).

- 장면 사전(Q): 임팩트 판정 구간의 프레임들을 통째로 윤곽+채우기로 바꾼 플립북. 결정타 임팩트 프레임에 쓴다.
- 조각 사전(K): 장면 안 덩어리를 모양으로 나눈 것. spark(가시형), ring(고리), wedge(쐐기·속도선), blob(덩어리·먼지·파편).
  중심을 원점, 크기를 면적 제곱근 = 1로 맞춘다.

출력은 앱 assets용 글자 형식이다. 다른 작가 그림에서 딴 형태라 저장소에 넣지 않는다(Drive에만 둔다).
사용: python tools/effect_library.py <나카무라 영상 폴더> <판정 csv> <출력.txt> [--max-frames 6] [--max-segs 600]
"""
import argparse
import csv
import os

import cv2
import numpy as np

import effect_vectorize as ev


def person_boxes(pose_dir, vid, f, scale):
    """나카무라 포즈(YOLO)의 사람 박스. 캐릭터 조각을 이펙트로 잘못 넣지 않으려고 뺀다."""
    import gzip, json
    p = os.path.join(pose_dir, vid + '.jsonl.gz')
    if not os.path.exists(p):
        return []
    for line in gzip.open(p, 'rt'):
        x = json.loads(line)
        if x['f'] == f:
            return [[v * scale for v in q['box']] for q in x['p'] if q['conf'] > 0.25]
        if x['f'] > f:
            break
    return []


def spiky(c):
    """중심에서 본 반지름 곡선에 뾰족한 끝이 여럿이고(극대 5개 이상) 안팎 차이가 큰가(2배 이상)."""
    P = c[:, 0, :].astype(float)
    m = cv2.moments(c)
    if m['m00'] == 0:
        return False
    cx, cy = m['m10'] / m['m00'], m['m01'] / m['m00']
    ang = np.arctan2(P[:, 1] - cy, P[:, 0] - cx); r = np.hypot(P[:, 0] - cx, P[:, 1] - cy)
    bins = np.full(72, 0.0)
    for a_, r_ in zip(((ang + np.pi) / (2 * np.pi) * 72).astype(int) % 72, r):
        bins[a_] = max(bins[a_], r_)
    if (bins == 0).sum() > 6:
        return False
    sm = np.convolve(np.r_[bins[-2:], bins, bins[:2]], np.ones(3) / 3, 'same')[2:-2]
    peaks = sum(1 for i in range(72) if sm[i] > sm[i - 1] and sm[i] >= sm[(i + 1) % 72] and sm[i] > np.median(sm) * 1.15)
    return peaks >= 5 and sm.max() >= 2 * max(sm.min(), 1e-6)


def components(m, tol, boxes=()):
    """그림 덩어리별(바깥 윤곽 + 구멍) 포물선 조각과 모양 수치."""
    cs, hier = cv2.findContours(m, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
    if hier is None:
        return []
    H, W = m.shape
    out = []
    for i, c in enumerate(cs):
        if hier[0][i][3] >= 0:
            continue
        area = cv2.contourArea(c)
        if area < 30:
            continue
        holes = [cs[j] for j in range(len(cs)) if hier[0][j][3] == i and cv2.contourArea(cs[j]) > 12]
        hull = cv2.contourArea(cv2.convexHull(c))
        (_, _), (rw, rh), _ = cv2.minAreaRect(c)
        hole_area = sum(cv2.contourArea(h) for h in holes)
        x, y, w, h = cv2.boundingRect(c)
        touches = x <= 1 or y <= 1 or x + w >= W - 1 or y + h >= H - 1
        cx0, cy0 = x + w / 2, y + h / 2
        if any(b[0] <= cx0 <= b[2] and b[1] <= cy0 <= b[3] for b in boxes):
            continue
        if area / max(w * h, 1) > 0.93 and n_rect(c):
            continue
        sub = np.zeros_like(m)
        cv2.drawContours(sub, [c], -1, 1, -1)
        for hc in holes:
            cv2.drawContours(sub, [hc], -1, 0, -1)
        _, shapes = ev.outline_mask(sub, tol)
        shapes.sort(key=lambda sh: sh['hole'])   # 바깥 윤곽이 먼저(윤곽 0)
        n_corner = len(ev.corners(c[:, 0, :].astype(float)))
        out.append({'area': (area - hole_area) / (H * W), 'solid': area / max(hull, 1), 'aspect': max(rw, rh) / max(1, min(rw, rh)),
                    'hole': hole_area / max(area, 1), 'corners': n_corner, 'touch': touches, 'shapes': shapes,
                    'c': (x + w / 2, y + h / 2), 'scale': np.sqrt(max(area - hole_area, 1)), 'spiky': spiky(c)})
    return out


def scene_groups(m, tol):
    """장면 전체: 바깥 윤곽마다 [바깥, 구멍…] 묶음."""
    cs, hier = cv2.findContours(m, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
    out = []
    if hier is None:
        return out
    for i, c in enumerate(cs):
        if hier[0][i][3] >= 0 or cv2.contourArea(c) < 12:
            continue
        sub = np.zeros_like(m)
        cv2.drawContours(sub, [c], -1, 1, -1)
        for j in range(len(cs)):
            if hier[0][j][3] == i:
                cv2.drawContours(sub, [cs[j]], -1, 0, -1)
        _, shapes = ev.outline_mask(sub, tol)
        if shapes:
            shapes.sort(key=lambda sh: sh['hole'])   # 바깥이 먼저(윤곽 0)
            out.append(shapes)
    return out


def n_rect(c):
    return len(cv2.approxPolyDP(c, 0.02 * cv2.arcLength(c, True), True)) <= 5


def kind(cp):
    if cp['touch']:
        return None
    if cp['aspect'] > 5 and cp['area'] > 0.0005:
        return 'wedge'
    if cp['solid'] > 0.85 and 0.0005 < cp['area'] < 0.05 and not (cp['aspect'] < 1.5 and cp['solid'] > 0.95):
        return 'blob'
    return None


def fmt(v):
    return f'{v:.4f}'.rstrip('0').rstrip('.') if v else '0'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('vids'); ap.add_argument('judge'); ap.add_argument('out')
    ap.add_argument('--max-frames', type=int, default=6)
    ap.add_argument('--max-segs', type=int, default=600)
    ap.add_argument('--tol', type=float, default=1.0)
    ap.add_argument('--poses', help='나카무라 포즈 폴더(사람 박스로 캐릭터 조각 제외)')
    a = ap.parse_args()
    rows = [r for r in csv.DictReader(open(a.judge, encoding='utf-8')) if r['animator'] == 'yutaka_nakamura' and r['claude_visual'] == '임팩트']
    lines, nq, nk = [], 0, {}
    for r in rows:
        f0, f1 = (int(x) for x in (r['frames'].split('-') + [r['frames']])[:2])
        path = os.path.join(a.vids, r['post_id'] + '.mp4')
        if not os.path.exists(path):
            continue
        frames = []
        for f in range(f0, min(f1, f0 + a.max_frames - 1) + 1):
            try:
                img = ev.read_frame(path, f)
            except SystemExit:
                break
            m = ev.ink(img)
            m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
            tol = a.tol
            groups = scene_groups(m, tol)
            while sum(len(sh['segs']) for g in groups for sh in g) > a.max_segs and tol < 6:
                tol *= 1.6
                groups = scene_groups(m, tol)
            if sum(len(sh['segs']) for g in groups for sh in g) > a.max_segs:
                continue
            shapes = groups
            g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            white_ink = int(np.median(g[m == 1]) > np.median(g[m == 0])) if m.any() and (m == 0).any() else 0
            H = m.shape[0]; W = m.shape[1]
            frames.append((white_ink, W / H, shapes, H))
            oh = cv2.VideoCapture(path).get(cv2.CAP_PROP_FRAME_HEIGHT) or H
            boxes = person_boxes(a.poses, r['post_id'], f, H / oh) if a.poses else []
            for cp in components(m, a.tol, boxes):
                k = kind(cp)
                if not k or sum(len(sh['segs']) for sh in cp['shapes']) > 80:   # 앱 ID 간격·가벼움
                    continue
                nk[k] = nk.get(k, 0) + 1
                cx, cy = cp['c']; s = cp['scale']
                lines.append(f"K {k} {r['post_id']}:{f} {len(cp['shapes'])}")
                for sh in cp['shapes']:
                    lines.append(f"C {int(sh['hole'])} " + ' '.join(fmt(v) for seg in sh['segs'] for v in
                                 ((seg[0] - cx) / s, (seg[1] - cy) / s, (seg[2] - cx) / s, (seg[3] - cy) / s, (seg[4] - cx) / s, (seg[5] - cy) / s)))
        if not frames:
            continue
        nq += 1
        lines.append(f"Q {r['post_id']}:{f0} {len(frames)}")
        for white, w, groups, H in frames:
            lines.append(f"F {white} {fmt(w)} {len(groups)}")
            for g in groups:
                lines.append(f"G {len(g)}")
                for sh in g:
                    lines.append(f"C {int(sh['hole'])} " + ' '.join(fmt(v / H) for seg in sh['segs'] for v in seg))
    with open(a.out, 'w', encoding='utf-8') as fh:
        fh.write('\n'.join(lines) + '\n')
    print('장면', nq, '조각', nk, '크기', os.path.getsize(a.out))


if __name__ == '__main__':
    main()
