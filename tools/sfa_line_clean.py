#!/usr/bin/env python3
"""SFA의 불필요한 직선 지우기: 겉모습은 그대로 두고 0길이 직선·다른 직선 위에 통째로 덮인 직선(중복 포함)을 없앤다 (2026-10-28).

동기: 사용자가 받은 창작 SFA(배경이 좋은 상자형 그림)에서 곧은 테두리 위에 짧은 직선 조각들이 따로따로(각각 파란·빨간 점) 겹쳐 있었다.
나중에 '직선 몇 개로 된 상자'(유타퐁 큐브)를 만들 때도 같은 정리가 필요하다.
지우는 조건(모두 만족):
- 직선(TypeId 1)이고, 길이가 0이거나, 색·굵기·레이어·글로우가 같은 더 긴(같으면 나중에 그려지는) 직선 B에서 두 끝점이 모두 --tol 이내.
- 다른 오브젝트와 연결(AC)이 없다 — 관절·연결 그룹(그리기 순서 단위)을 건드리지 않는다.
- 채우기(FS ObjId)가 쓰지 않는다.
- 트위닝(장 사이 같은 ID 보간)을 깨지 않도록, 그 ID가 나오는 모든 장에서 위 조건이 성립할 때만 지운다.
단위: 좌표 0–100. --tol 0.05 ≈ 1920 폭 화면에서 1화소. 검증은 tools/sfa_render.py로 지우기 전후 렌더 비교.
사용: python tools/sfa_line_clean.py in.sfa out.sfa [--tol 0.05]
"""
import argparse
import collections
import os
import zipfile
import xml.etree.ElementTree as ET

import numpy as np

KEYS = ('Color', 'ThicknessScale', 'LayerId', 'GlowRadius', 'GlowThickness', 'GlowColor', 'GlowAlpha')


def candidates(frame, tol):
    """이 장에서 지워도 겉모습이 같은 직선 AO ID 집합."""
    used = {s.get('ObjId') for s in frame.iter('FS')}
    lines = []
    for a in frame.findall('AO'):
        if a.get('TypeId') != '1':
            continue
        aps = a.findall('AP')
        if len(aps) != 2:
            continue
        lines.append((a, np.array([[float(p.get('X')), float(p.get('Y'))] for p in aps]),
                      any(p.find('AC') is not None for p in aps)))
    out = set()
    if not lines:
        return out
    P0 = np.array([l[1][0] for l in lines]); P1 = np.array([l[1][1] for l in lines])
    L = np.linalg.norm(P1 - P0, axis=1)
    order = np.array([int(l[0].get('DrawOrder') or l[0].get('ID')) for l in lines])
    keys = [tuple(l[0].get(k) for k in KEYS) for l in lines]
    groups = collections.defaultdict(list)
    for i, k in enumerate(keys):
        groups[k].append(i)

    def dist(p, a, b):  # 점 p(n,2) ↔ 선분 a,b(m,2) 거리 (n,m)
        ab = b - a
        t = ((p[:, None, :] - a[None]) * ab[None]).sum(-1) / np.maximum((ab * ab).sum(-1), 1e-12)[None]
        t = np.clip(t, 0, 1)
        return np.linalg.norm(p[:, None, :] - (a[None] + t[..., None] * ab[None]), axis=-1)

    for idx in groups.values():
        idx = np.array(idx)
        d0, d1 = dist(P0[idx], P0[idx], P1[idx]), dist(P1[idx], P0[idx], P1[idx])
        La, Lb = L[idx][:, None], L[idx][None, :]
        Oa, Ob = order[idx][:, None], order[idx][None, :]
        longer = (Lb > La + 1e-9) | ((np.abs(Lb - La) <= 1e-9) & (Ob > Oa))  # 같은 길이(중복)는 나중에 그려지는 쪽을 남김
        cov = (d0 <= tol) & (d1 <= tol) & longer
        np.fill_diagonal(cov, False)
        for n, i in enumerate(idx):
            a, _, linked = lines[i]
            if linked or a.get('ID') in used:
                continue
            if L[i] < 1e-9 or cov[n].any():
                out.add(a.get('ID'))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('inp')
    ap.add_argument('out')
    ap.add_argument('--tol', type=float, default=0.05)
    a = ap.parse_args()
    z = zipfile.ZipFile(a.inp)
    name = next(n for n in z.namelist() if n.lower().endswith('.xml'))
    root = ET.fromstring(z.read(name))
    frames = root.findall('Frame')
    cand = [candidates(f, a.tol) for f in frames]
    seen = collections.defaultdict(int); ok = collections.defaultdict(int)
    for f, c in zip(frames, cand):
        for ao in f.findall('AO'):
            seen[ao.get('ID')] += 1
            ok[ao.get('ID')] += ao.get('ID') in c
    drop = {i for i in seen if ok[i] == seen[i] and seen[i] > 0}
    before = after = 0
    per_frame_cand = sum(len(c) for c in cand)
    for f in frames:
        aos = f.findall('AO'); before += len(aos)
        for ao in aos:
            if ao.get('ID') in drop:
                f.remove(ao)
        after += len(f.findall('AO'))
    raw = ET.tostring(root, encoding='utf-8', xml_declaration=True)
    with zipfile.ZipFile(a.out, 'w', zipfile.ZIP_DEFLATED) as zo:
        zo.writestr(name, raw)
    print(f'오브젝트 {before} → {after} ({before - after}개 지움, 장별 후보 {per_frame_cand} 중 모든 장에서 성립한 ID {len(drop)}개) '
          f'| 압축 {os.path.getsize(a.inp) / 1e6:.2f} → {os.path.getsize(a.out) / 1e6:.2f}MB')


if __name__ == '__main__':
    main()
