#!/usr/bin/env python3
"""색 영역형 SFA(posterize 변환본) 가볍게 만들기: 겉모습은 그대로, 곡선 수·점 수·파일 크기를 줄인다 (2026-10-27).

대상 구조(외부 sfa-file-builder 스킬 변환본 ink_12fps.sfa로 확인): 모든 AO가 정확히 한 FR(색 영역)의 테두리이고 같은 색,
얇은 선(ThicknessScale 0.1), FR은 구멍 없이 FS Kind=0 고리 하나, 한 장 전체가 AC로 이어진 덩어리 하나(파란점 1개).
방법: 영역마다 테두리를 0.5px 간격으로 펼치고(화면 1920×1080 기준), 허용 오차(--tol px) 안에서 가장 긴 2차 곡선(직선으로
충분하면 직선)을 앞에서부터 욕심껏 다시 맞춘다. 영역 순서·색·선 굵기·글로우 속성은 그대로 두므로 칠하는 순서도 같다.
연결: 고리 이음매(끝 '9' ↔ 다음 시작 '8'), 영역 r의 첫 점 ↔ 앞 영역들의 가장 가까운 끝점(덩어리 하나 유지), 파란점(3) 1개.
좌표는 소수 3자리(0.001단위 ≈ 0.02px). 구멍(Contour)·원(TypeId 2)·FR에 안 쓰인 선이 있는 파일은 거절한다(이 도구 범위 밖).
검증: tools/sfa_render.py로 원본·결과를 렌더해 화소 차이를 잰다(앱 화면 대조는 아님).
사용: python tools/sfa_slim.py <in.sfa> <out.sfa> [--tol 0.6] [--name 이름]
"""
import argparse
import math
import os
import sys
import zipfile
import xml.etree.ElementTree as ET
from multiprocessing import Pool

import cv2
import numpy as np

SX, SY = 19.2, 10.8  # 단위 → 1920×1080 화소(여백 무시 근사, 오차 판정용)
STEP = 0.5
TS = np.linspace(0, 1, 97)


def dense_ring(segs):
    """segs: [(type, pts[unit], t0, t1)] → 화소 좌표 닫힌 고리(마지막 점 = 첫 점 제외)."""
    out = []
    for typ, P, t0, t1 in segs:
        P = np.array(P) * (SX, SY)
        if typ == '1':
            L = np.hypot(*(P[1] - P[0])) * abs(t1 - t0)
        else:
            L = (np.hypot(*(P[1] - P[0])) + np.hypot(*(P[2] - P[1]))) * abs(t1 - t0)
        n = max(2, int(math.ceil(L / STEP)) + 1)
        t = np.linspace(t0, t1, n)[:-1, None]
        if typ == '1':
            out.append(P[0] + (P[1] - P[0]) * t)
        else:
            out.append((1 - t) ** 2 * P[0] + 2 * (1 - t) * t * P[1] + t ** 2 * P[2])
    return np.vstack(out)


def quad(P0, P1, P2, t):
    t = t[:, None]
    return (1 - t) ** 2 * P0 + 2 * (1 - t) * t * P1 + t ** 2 * P2


def dmax(A, B):
    """A 각 점에서 B 점 집합까지 최소 거리의 최댓값."""
    return np.sqrt(((A[:, None, :] - B[None, :, :]) ** 2).sum(2).min(1).max())


def fit(Q, tol):
    """Q 점열을 2차 곡선 하나로. 되면 ('1'|'3', ctrl) 아니면 None. 양방향 거리(점→곡선, 곡선→점)로 판정."""
    P0, P2 = Q[0], Q[-1]
    if len(Q) <= 2:
        return '1', None
    # 직선
    C = P0 + (P2 - P0) * np.linspace(0, 1, max(2, len(Q)))[:, None]
    if dmax(Q, C) <= tol and dmax(C, Q) <= tol + STEP / 2:
        return '1', None
    d = np.r_[0, np.cumsum(np.hypot(*np.diff(Q, axis=0).T))]
    if d[-1] <= 0:
        return None
    t = d / d[-1]
    for _ in range(2):
        b1 = 2 * (1 - t) * t
        r = Q - ((1 - t) ** 2)[:, None] * P0 - (t ** 2)[:, None] * P2
        den = (b1 ** 2).sum()
        if den <= 1e-9:
            return None
        P1 = (b1[:, None] * r).sum(0) / den
        C = quad(P0, P1, P2, TS)
        t = TS[np.sqrt(((Q[:, None, :] - C[None]) ** 2).sum(2)).argmin(1)]
    if dmax(Q, C) <= tol and dmax(C, Q) <= tol + STEP / 2:
        return '3', P1
    return None


def refit_ring(D, tol, free=None, area_ok=None, outward=None):
    """닫힌 화소 고리 D → [(type, [P0, (P1), P2])] 화소 좌표.
    free[i]: 그 점 바깥쪽이 나중 영역에 깊이 덮임(보이지 않는 경계). area_ok(loop): 원래 경계와 새 곡선 사이 넓이가
    전부 '나중 영역 깊은 안쪽 또는 원래 경계 1px 띠'이면 True. 둘 다 없으면 보이는 경계 기준(tol)만 쓴다."""
    N = len(D)
    if free is None:
        free = np.zeros(N, bool)
    k = 3
    v1 = D - np.roll(D, k, 0)
    v2 = np.roll(D, -k, 0) - D
    ang = np.abs(np.arctan2(v1[:, 0] * v2[:, 1] - v1[:, 1] * v2[:, 0], (v1 * v2).sum(1)))
    vis = ~free & ~np.roll(free, 1) & ~np.roll(free, -1)
    s = int(np.where(vis, ang, -1).argmax()) if vis.any() else int(ang.argmax())  # 보이는 가장 뾰족한 점에서 시작
    order = np.r_[np.arange(s, N), np.arange(0, s), s]
    R, F = D[order], free[order]
    O = outward[order] if outward is not None else None
    cap = max(2, int(math.ceil(N / 2)))  # 곡선 하나로 고리 전체를 덮지 않게(최소 2개)

    def ok(i, j):
        r = fit(R[i:j + 1], tol)
        if r is not None or area_ok is None or not F[i + 1:j].any():
            return r
        Q = R[i:j + 1]
        v = ~F[i:j + 1]
        cands = [('1', None)]
        r2 = fit_ls(Q)
        if r2 is not None:
            cands.append(('3', r2))
        ch = Q[-1] - Q[0]
        L = np.hypot(*ch)
        if O is not None and L > 0:  # 나중 영역 쪽으로 부풀려 원래 경계를 감싸는 곡선
            nn = np.array([-ch[1], ch[0]]) / L
            if (O[i:j + 1][F[i:j + 1]] @ nn).mean() < 0:
                nn = -nn
            h = ((Q - Q[0]) @ nn).max()
            if h > 0:
                mid = (Q[0] + Q[-1]) / 2
                cands += [('3', mid + nn * h * f) for f in (2.0, 2.6, 3.4)]
        for typ, P1 in cands:
            C = Q[0] + (Q[-1] - Q[0]) * TS[:, None] if typ == '1' else quad(Q[0], P1, Q[-1], TS)
            if v.any() and dmax(Q[v], C) > tol:
                continue
            if area_ok(np.vstack([Q, C[::-1]])):
                return typ, P1
        return None

    segs, i = [], 0
    while i < N:
        hi = min(N, i + cap)
        best = (i + 1, ('1', None))
        step, last_ok = 2, i + 1
        j = i + step
        while j <= hi:  # 늘려 가며
            r = ok(i, j)
            if r is None:
                break
            last_ok, best = j, (j, r)
            step *= 2
            j = i + step
        lo, top = last_ok, min(j, hi + 1)
        while top - lo > 1:  # 이분
            m = (lo + top) // 2
            r = ok(i, m)
            if r is None:
                top = m
            else:
                lo, best = m, (m, r)
        j, (typ, P1) = best
        segs.append((typ, [R[i], R[j]] if typ == '1' else [R[i], P1, R[j]]))
        i = j
    return segs


def fit_ls(Q):
    """Q에 최소제곱으로 맞춘 2차 곡선의 제어점(판정 없음)."""
    P0, P2 = Q[0], Q[-1]
    d = np.r_[0, np.cumsum(np.hypot(*np.diff(Q, axis=0).T))]
    if d[-1] <= 0:
        return None
    t = d / d[-1]
    b1 = 2 * (1 - t) * t
    den = (b1 ** 2).sum()
    if den <= 1e-9:
        return None
    r = Q - ((1 - t) ** 2)[:, None] * P0 - (t ** 2)[:, None] * P2
    return (b1[:, None] * r).sum(0) / den


W_, H_ = 1920, 1080
K3 = np.ones((3, 3), np.uint8)


def ring_mask(D):
    m = np.zeros((H_, W_), np.uint8)
    cv2.fillPoly(m, [np.round(D * 4).astype(np.int32)], 1, shift=2)
    return m


def refit_frame(regions, tol, stack=True):
    """한 장의 영역들(칠하는 순서) → 새 곡선. stack: 나중 영역에 덮이는 경계는 지름길 허용."""
    rings = [dense_ring(segs) for _, _, segs in regions]
    out = [None] * len(rings)
    cover = np.zeros((H_, W_), np.uint8)
    dropped = 0
    for ri in range(len(rings) - 1, -1, -1):
        D = rings[ri]
        own = ring_mask(D)
        if not stack or not cover.any():
            out[ri] = refit_ring(D, tol)
            cover |= own
            continue
        C2 = cv2.erode(cover, K3)  # 나중 영역 안쪽 1px(가장자리 번짐·선 반폭 여유)
        if not (own & (1 - C2)).any():  # 완전히 덮임 → 지움
            out[ri] = None
            dropped += 1
            cover |= own
            continue
        T = np.roll(D, -1, 0) - np.roll(D, 1, 0)
        n = np.c_[T[:, 1], -T[:, 0]] / (np.hypot(T[:, 0], T[:, 1])[:, None] + 1e-9)
        lim = np.array([W_ - 1, H_ - 1])
        a = np.clip(np.round(D + 1.5 * n).astype(int), 0, lim)
        b = np.clip(np.round(D - 1.5 * n).astype(int), 0, lim)
        outward = np.where((own[a[:, 1], a[:, 0]] == 0)[:, None], n, -n)
        p3 = np.clip(np.round(D + 2.5 * outward).astype(int), 0, lim)
        free = C2[p3[:, 1], p3[:, 0]] > 0
        x0, y0 = np.maximum(np.floor(D.min(0)).astype(int) - 6, 0)
        x1, y1 = np.minimum(np.ceil(D.max(0)).astype(int) + 7, lim + 1)
        band = np.full((y1 - y0, x1 - x0), 255, np.uint8)
        cv2.polylines(band, [np.round((D - (x0, y0)) * 4).astype(np.int32)], True, 0, 1, shift=2)
        okm = (C2[y0:y1, x0:x1] > 0) | (cv2.distanceTransform(band, cv2.DIST_L2, 3) <= 1.0)

        def area_ok(loop):
            lp = loop - (x0, y0)
            lx0, ly0 = np.floor(lp.min(0)).astype(int)
            lx1, ly1 = np.ceil(lp.max(0)).astype(int) + 1
            if lx0 < 0 or ly0 < 0 or lx1 > okm.shape[1] or ly1 > okm.shape[0]:
                return False
            m = np.zeros((ly1 - ly0, lx1 - lx0), np.uint8)
            cv2.fillPoly(m, [np.round((lp - (lx0, ly0)) * 4).astype(np.int32)], 1, shift=2)
            return not (m.astype(bool) & ~okm[ly0:ly1, lx0:lx1]).any()

        out[ri] = refit_ring(D, tol, free, area_ok, outward)
        cover |= own
    return out, dropped


def parse(path):
    z = zipfile.ZipFile(path)
    name = z.namelist()[0]
    seq_attr, frames = None, []
    for ev, el in ET.iterparse(z.open(name), events=('start', 'end')):
        if ev == 'start':
            if el.tag == 'Sequence' and seq_attr is None:
                seq_attr = dict(el.attrib)
            continue
        if el.tag != 'Frame':
            continue
        aos = {a.get('ID'): a for a in el.findall('AO')}
        used = set()
        regions = []
        for f in el.findall('FR'):
            segs, attr = [], None
            for s in f.findall('FS'):
                if s.get('Kind', '0') != '0' or s.get('Contour'):
                    sys.exit('구멍(Contour)·Kind=1 채우기는 범위 밖')
                a = aos[s.get('ObjId')]
                if a.get('TypeId') not in ('1', '3'):
                    sys.exit('원(TypeId 2)은 범위 밖')
                used.add(a.get('ID'))
                attr = attr or {k: v for k, v in a.attrib.items() if k not in ('ID', 'DrawOrder')}
                P = [(float(p.get('X')), float(p.get('Y'))) for p in sorted(a.findall('AP'), key=lambda p: int(p.get('Index')))]
                segs.append((a.get('TypeId'), P, float(s.get('StartT')), float(s.get('EndT'))))
            regions.append((f.get('Color'), attr, segs))
        if used != set(aos):
            sys.exit(f'FR에 안 쓰인 선 {len(set(aos) - used)}개(프레임 {el.get("Position")}) — 범위 밖')
        frames.append((dict(el.attrib), [dict(l.attrib) for l in el.findall('LayerDef')], regions, len(aos)))
        el.clear()
    return seq_attr, frames


def work(job):
    regions, tol, stack = job
    segs, dropped = refit_frame(regions, tol, stack)
    return [(c, a, [(t, [tuple(p / (SX, SY)) for p in P]) for t, P in sg]) for (c, a, _), sg in zip(regions, segs) if sg is not None], dropped


def q(v):
    return f'{v:.3f}'


def write(path, seq_attr, frames, fitted, name):
    ao_id, ap_id = 100001, 1000001
    xs = [f'<?xml version="1.0" encoding="UTF-8" ?><Sequence Name="{name}" HeightWidthRatio="{seq_attr.get("HeightWidthRatio", "0.5625")}" '
          f'RatioX="{seq_attr.get("RatioX", "16")}" RatioY="{seq_attr.get("RatioY", "9")}" FrameCount="{len(frames)}" '
          f'BackgroundColor="{seq_attr.get("BackgroundColor", "-1")}">']
    n_ao = 0
    for (fattr, layers, _, _), regs in zip(frames, fitted):
        xs.append('<Frame ' + ' '.join(f'{k}="{v}"' for k, v in fattr.items()) + '>')
        xs += ['<LayerDef ' + ' '.join(f'{k}="{v}"' for k, v in l.items()) + ' />' for l in layers]
        objs, links = [], {}
        prev_pts = []  # (ap_id, x, y) 앞 영역 끝점
        fr_xml = []
        for ri, (color, attr, segs) in enumerate(regs):
            ring = []
            for typ, P in segs:
                aps = []
                for k, (x, y) in enumerate(P):
                    aps.append([ap_id, x, y, '8' if k == 0 else '9'])
                    ap_id += 1
                ring.append((ao_id, typ, aps))
                ao_id += 1
            m = len(ring)
            for k in range(m):  # 고리 이음매
                a_end, b_start = ring[k][2][-1][0], ring[(k + 1) % m][2][0][0]
                links.setdefault(a_end, []).append(b_start)
                links.setdefault(b_start, []).append(a_end)
            first_ap = ring[0][2][0]
            if prev_pts:  # 덩어리 하나: 앞 영역의 가장 가까운 끝점과 잇기
                arr = np.array([(x * 16, y * 9) for _, x, y in prev_pts])
                j = int(((arr - (first_ap[1] * 16, first_ap[2] * 9)) ** 2).sum(1).argmin())
                links.setdefault(first_ap[0], []).append(prev_pts[j][0])
                links.setdefault(prev_pts[j][0], []).append(first_ap[0])
            else:
                ring[0][2][-1][3] = '3'  # 파란점 1개
            prev_pts += [(aps[0][0], aps[0][1], aps[0][2]) for _, _, aps in ring]
            fs = []
            for oid, typ, aps in ring:
                fs.append(f'<FS Kind="0" ObjId="{oid}" StartPtId="{aps[0][0]}" EndPtId="{aps[-1][0]}" StartT="0.0" EndT="1.0" />')
            fr_xml.append(f'<FR Color="{color}">' + ''.join(fs) + '</FR>')
            objs.append((attr, ring))
        for attr, ring in objs:
            for oid, typ, aps in ring:
                at = ' '.join(f'{k}="{v}"' for k, v in attr.items() if k != 'TypeId')
                body = ''.join(f'<AP ID="{i}" Flags="{fl}" Index="{k}" X="{q(x)}" Y="{q(y)}">' + ''.join(f'<AC ConnPtId="{c}" />' for c in links.get(i, [])) + '</AP>'
                               if links.get(i) else f'<AP ID="{i}" Flags="{fl}" Index="{k}" X="{q(x)}" Y="{q(y)}" />'
                               for k, (i, x, y, fl) in enumerate(aps))
                xs.append(f'<AO ID="{oid}" TypeId="{typ}" {at} DrawOrder="{oid}">' + body + '</AO>')
                n_ao += 1
        xs += fr_xml
        xs.append('</Frame>')
    xs.append('</Sequence>')
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr(name + '.xml', ''.join(xs).encode('utf-8'))
    return n_ao


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('src')
    ap.add_argument('dst')
    ap.add_argument('--tol', type=float, default=0.6, help='허용 오차(1920×1080 화소)')
    ap.add_argument('--name', default='')
    ap.add_argument('--frames', default='', help='시험용: 앞 N장만 또는 쉼표 목록')
    ap.add_argument('--no-stack', action='store_true', help='덮이는 경계 지름길 끄기(보이는 경계 오차만)')
    a = ap.parse_args()
    seq_attr, frames = parse(a.src)
    if a.frames:
        frames = [frames[int(x)] for x in a.frames.split(',')] if ',' in a.frames else frames[:int(a.frames)]
        for i, f in enumerate(frames):
            f[0]['Position'] = str(i)
    with Pool(os.cpu_count()) as pool:
        res = pool.map(work, [(regs, a.tol, not a.no_stack) for _, _, regs, _ in frames])
    fitted = [r[0] for r in res]
    name = a.name or os.path.splitext(os.path.basename(a.dst))[0]
    n_new = write(a.dst, seq_attr, frames, fitted, name)
    n_old = sum(f[3] for f in frames)
    print(f'완전히 덮여 지운 영역 {sum(r[1] for r in res)}')
    print(f'곡선 {n_old} → {n_new} ({n_new / n_old * 100:.0f}%) | 파일 {os.path.getsize(a.src) / 1e6:.1f}MB → {os.path.getsize(a.dst) / 1e6:.1f}MB')


if __name__ == '__main__':
    main()
