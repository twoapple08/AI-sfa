#!/usr/bin/env python3
"""선으로 덧칠한 면 → 채우기(FR) 교체 (2026-10-29, 첫 대상: 도시 v6 — AI 생성 파일, 검은 선 7,248개로 빌딩 칠).
한 장짜리·흰 바탕 파일용 첫 판. 순서:
1) 지정한 색(기본 검정)의 선만 렌더 → 그 색 영역의 윤곽(바깥 + 구멍)을 딴다.
2) 윤곽을 직선으로 단순화(--eps 화소@1920) → 투명 테두리 선(Color 0)을 끝점끼리 AC로 잇고, FR이 그 선들을 FS로 가리킨다(앱 파일과 같은 구조).
3) 구멍은 흰 면으로 덮는다(바탕이 흰색일 때만 맞음 — 구멍 Contour는 실제 파일 예가 없어 쓰지 않음).
4) 그 색 선은 모두 지우고, 나머지 선은 가려져 안 보이는 것·완전 중복만 빼고 남긴다.
5) 원본과 렌더 차이를 출력.
사용: python sfa_linefill_to_fill.py 원본.sfa 출력.sfa [--color -16777216] [--eps 1.2]
결과(도시 v6): 오브젝트 8,693 → 2,242, 렌더 차이 1.4% 픽셀(경계 가장자리), 사용자 확인 10-29.
"""
import argparse
import copy
import os
import sys
import xml.etree.ElementTree as ET
import zipfile

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sfa_render as R  # noqa: E402

W, H = 1920, 1080


def render(root, fr):
    return np.asarray(R.render_frame(root, fr, W, H))[..., :3]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('src')
    ap.add_argument('out')
    ap.add_argument('--color', default='-16777216', help='면으로 바꿀 선 색(Color 값 그대로)')
    ap.add_argument('--eps', type=float, default=1.2)
    ap.add_argument('--min-area', type=float, default=30)
    a = ap.parse_args()
    z = zipfile.ZipFile(a.src)
    name = z.namelist()[0]
    root = ET.fromstring(z.read(name))
    frs_ = root.findall('Frame')
    assert len(frs_) == 1, '첫 판은 한 장짜리 파일만'
    R.PARAMS['pad'] = 6.0
    R.PARAMS['thick_mul'] = 1.0
    geo = R.Geo(root, W, H)
    f = frs_[0]
    orig = render(root, f)
    # 1) 그 색 선만 렌더
    r2 = copy.deepcopy(root)
    f2 = r2.find('Frame')
    for o in list(f2.findall('AO')):
        if o.get('Color') != a.color:
            f2.remove(o)
    only = render(r2, f2).astype(int)
    mask = (np.abs(only - 255).max(-1) > 127).astype(np.uint8)  # 흰 바탕과 다른 곳
    cs, h = cv2.findContours(mask, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
    h = h[0]
    outer = [i for i in range(len(cs)) if h[i][3] < 0 and cv2.contourArea(cs[i]) >= a.min_area]
    holes = [i for i in range(len(cs)) if h[i][3] >= 0 and cv2.contourArea(cs[i]) >= a.min_area]
    # 보이는지(근사 래스터: 마지막에 덮은 선 번호)
    aos = f.findall('AO')
    order = sorted(aos, key=lambda o: int(o.get('DrawOrder') or o.get('ID')))
    own = np.full((H, W), -1, np.int32)
    for i, o in enumerate(order):
        p = np.array(R.obj_points(o, geo))
        w = max(1, int(round(1.14 * 8 * geo.S * float(o.get('ThicknessScale') or 1))))
        m = np.zeros((H, W), np.uint8)
        q0, q1 = tuple(np.round(p[0]).astype(int)), tuple(np.round(p[-1]).astype(int))
        cv2.line(m, q0, q1, 1, w)
        cv2.circle(m, q0, w // 2, 1, -1)
        cv2.circle(m, q1, w // 2, 1, -1)
        own[m > 0] = i
    vis = np.bincount(own[own >= 0].ravel(), minlength=len(order))
    for o in aos:
        f.remove(o)
    for r in f.findall('FR'):
        f.remove(r)
    aid = [max(int(o.get('ID')) for o in aos) + 1]
    pid = [max(int(p.get('ID')) for o in aos for p in o.findall('AP')) + 1]
    new = []

    def inv(x, y):
        return (x - geo.ox) / geo.uw * 100, (y - geo.oy) / geo.uh * 100

    def poly(cnt, color):
        pts = cv2.approxPolyDP(cnt, a.eps, True)[:, 0, :].astype(float)
        if len(pts) < 3:
            return None
        objs = []
        for k in range(len(pts)):
            p0, p1 = pts[k], pts[(k + 1) % len(pts)]
            o = ET.Element('AO', dict(ID=str(aid[0]), TypeId='1', Color='0', LayerId='0', DrawOrder=str(aid[0]), ThicknessScale='1.0', ObjectScale='1.0',
                                      GlowRadius='0', GlowThickness='0', GlowColor='4294967295', GlowAlpha='0'))
            aid[0] += 1
            ids = []
            for j, q in enumerate((p0, p1)):
                x, y = inv(*q)
                ET.SubElement(o, 'AP', dict(ID=str(pid[0]), Flags='8' if j == 0 else '9', Index=str(j), X=str(round(float(x), 4)), Y=str(round(float(y), 4))))
                ids.append(pid[0])
                pid[0] += 1
            objs.append((o, ids))
        n = len(objs)
        for k, (o, ids) in enumerate(objs):  # 끝점끼리 연결(앱 파일과 같은 방식)
            ET.SubElement(o.findall('AP')[1], 'AC', dict(ConnPtId=str(objs[(k + 1) % n][1][0])))
            ET.SubElement(o.findall('AP')[0], 'AC', dict(ConnPtId=str(objs[(k - 1) % n][1][1])))
        new.extend(o for o, _ in objs)
        fr = ET.Element('FR', dict(Color=color))
        for o, ids in objs:
            ET.SubElement(fr, 'FS', dict(Kind='0', ObjId=o.get('ID'), StartPtId=str(ids[0]), EndPtId=str(ids[1]), StartT='0.0', EndT='1.0'))
        return fr

    fill_color = str(int(a.color) & 0xFFFFFFFF)
    # 면 테두리 선이 다른 선보다 먼저 그려지도록 DrawOrder를 맨 앞으로
    frs = [r for r in (poly(cs[i], fill_color) for i in outer) if r is not None]
    frs += [r for r in (poly(cs[i], '4294967295') for i in holes) if r is not None]
    base = min(int(o.get('DrawOrder') or o.get('ID')) for o in aos) - len(new) - 1
    for k, o in enumerate(new):
        o.set('DrawOrder', str(base + k))
    seen, kept = set(), 0
    for i, o in enumerate(order):
        if o.get('Color') == a.color or vis[i] == 0:
            continue
        key = (tuple(round(float(p.get(k)), 2) for p in o.findall('AP') for k in ('X', 'Y')), o.get('Color'), o.get('ThicknessScale'), o.get('GlowAlpha'))
        if key in seen:
            continue
        seen.add(key)
        new.append(o)
        kept += 1
    li = list(f).index(f.find('LayerDef')) + 1 if f.find('LayerDef') is not None else 0
    for k, o in enumerate(new):
        f.insert(li + k, o)
    for r in frs:
        f.append(r)
    xml = ET.tostring(root, encoding='unicode')
    with zipfile.ZipFile(a.out, 'w', zipfile.ZIP_DEFLATED) as zz:
        zz.writestr(name, '<?xml version="1.0" encoding="UTF-8" ?>' + xml)
    d = np.abs(render(ET.fromstring(xml), ET.fromstring(xml).find('Frame')).astype(int) - orig.astype(int)).max(-1)
    print(f'면 {len(frs)}(바깥 {len(outer)}, 흰 구멍 {len(holes)}), 오브젝트 {len(aos)} → {len(new)}(남긴 선 {kept}), 렌더 차이 {(d > 30).mean() * 100:.2f}% 픽셀')


if __name__ == '__main__':
    main()
