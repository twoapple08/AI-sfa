#!/usr/bin/env python3
"""선 칠 → 면 교체, 여러 장·여러 색판 (2026-10-29, 첫 대상: 갈아엎기 전 1-2 — 원 하나를 같은 색 직선 360개로 칠한 숲 그림).
`sfa_linefill_to_fill.py`(한 장·한 색·흰 바탕)의 확장. 장마다:
1) 그리는 순서대로 같은 색 선이 이어진 묶음(run)을 찾는다(--min-run 이상).
2) 묶음만 흰 바탕에 렌더 → 덮인 영역 윤곽 → 직선으로 단순화한 면(FR, 같은 색) + 투명 테두리 선.
3) 판정: 면으로 그린 묶음과 선으로 그린 묶음을 비교해 다른 픽셀이 묶음 넓이의 --max-diff 이하일 때만 교체
   (빗금 사이로 바탕이 보이는 '질감 칠'·반투명 겹침으로 색이 달라지는 칠은 자동으로 남는다).
4) 점 표시(docs/REF-SFA-FILE-BUILDER-2026-10-27.md 파란점 규칙): 테두리 고리마다 파란점(Flags 3) 1개, 꼭짓점마다 겹친 두 끝점 중 하나만 표시(9, 다른 쪽 8).
   파란점 자리의 다른 끝점도 8(9면 주황점이 파란점을 덮는다).
5) 테두리 선은 지운 선들의 ID·점 ID를 다시 써서 그리는 순서를 그대로 유지한다(채우기는 주인 선 자리에 그려짐).
사용: python sfa_linefill_runs.py 원본.sfa 출력.sfa [--eps 1.2] [--min-run 20] [--max-diff 0.03]
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


def key(o):
    return int(o.get('DrawOrder') or o.get('ID'))


def alone(root, f, objs, frs=()):
    """이 오브젝트(와 면)만 흰 바탕에 그린 그림."""
    r2 = ET.Element('Sequence', dict(root.attrib))  # 렌더는 시퀀스 속성만 읽는다(전체 복사는 큰 파일에서 느림)
    r2.set('BackgroundColor', '-1')
    f2 = ET.SubElement(ET.Element('x'), 'Frame', dict(f.attrib))
    f2.set('BackgroundColor', '-1')
    for c in f:
        if c.tag == 'LayerDef':
            f2.append(copy.deepcopy(c))
    for o in objs:
        f2.append(o)
    for r in frs:
        f2.append(r)
    return np.asarray(R.render_frame(r2, f2, W, H))[..., :3].astype(int)


def quick_ok(run, geo, sc=0.25):
    """빠른 거르기(저해상도 근사): 선끼리 많이 겹치고(덧칠) 윤곽 안에 빈틈이 거의 없어야 정밀 비교로 넘긴다."""
    w0, h0 = int(W * sc), int(H * sc)
    m = np.zeros((h0, w0), np.uint8)
    tot = 0
    for o in run:
        p = np.array(R.obj_points(o, geo)) * sc
        w = max(1, int(round(1.14 * 8 * geo.S * float(o.get('ThicknessScale') or 1) * sc)))
        one = np.zeros_like(m)
        q0, q1 = tuple(np.round(p[0]).astype(int)), tuple(np.round(p[-1]).astype(int))
        cv2.line(one, q0, q1, 1, w)
        tot += int(one.sum())
        m |= one
    area = int(m.sum())
    if area < 50:
        return False
    cs, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    full = np.zeros_like(m)
    cv2.drawContours(full, cs, -1, 1, -1)
    return tot / area >= 1.3 and (int(full.sum()) - area) / area < 0.05


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('src')
    ap.add_argument('out')
    ap.add_argument('--eps', type=float, default=1.2)
    ap.add_argument('--min-run', type=int, default=20)
    ap.add_argument('--max-diff', type=float, default=0.03)
    a = ap.parse_args()
    z = zipfile.ZipFile(a.src)
    name = z.namelist()[0]
    root = ET.fromstring(z.read(name))
    R.PARAMS['pad'] = 6.0
    R.PARAMS['thick_mul'] = 1.0
    geo = R.Geo(root, W, H)
    tot0 = tot1 = 0
    rep = []
    for fi, f in enumerate(root.findall('Frame')):
        aos = f.findall('AO')
        order = sorted(aos, key=key)
        runs = []
        for o in order:
            if runs and runs[-1][0].get('Color') == o.get('Color') and o.get('TypeId') == '1':
                runs[-1].append(o)
            else:
                runs.append([o])
        ok = rej = 0
        for run in runs:
            if len(run) < a.min_run or R.alpha(run[0].get('Color')) == 0 or not quick_ok(run, geo):
                continue
            img = alone(root, f, [copy.deepcopy(o) for o in run])
            mask = (np.abs(img - 255).max(-1) > 20).astype(np.uint8)
            cs, h = cv2.findContours(mask, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
            if h is None:
                continue
            outer = [cs[i] for i in range(len(cs)) if h[0][i][3] < 0 and cv2.contourArea(cs[i]) >= 4]
            polys = [cv2.approxPolyDP(c, a.eps, True)[:, 0, :].astype(float) for c in outer]
            polys = [p for p in polys if len(p) >= 3]
            nseg = sum(len(p) for p in polys)
            ids = sorted(int(o.get('ID')) for o in run)
            pids = sorted(int(p.get('ID')) for o in run for p in o.findall('AP'))
            if not polys or nseg > len(ids) or 2 * nseg > len(pids):  # 테두리 선이 원래 선보다 많으면 이득 없음
                rej += 1
                continue
            new, frs = [], []
            k = 0
            for p in polys:
                objs = []
                for j in range(len(p)):
                    p0, p1 = p[j], p[(j + 1) % len(p)]
                    oid = ids[k]
                    o = ET.Element('AO', dict(ID=str(oid), TypeId='1', Color='0'))
                    for attr in ('LayerId', 'DrawOrder', 'ThicknessScale', 'ObjectScale', 'GlowRadius', 'GlowThickness', 'GlowColor', 'GlowAlpha'):
                        if run[0].get(attr) is not None:
                            o.set(attr, run[0].get(attr))
                    if o.get('DrawOrder') is not None:
                        o.set('DrawOrder', str(oid))
                    pp = []
                    for t, q in enumerate((p0, p1)):
                        x, y = (q[0] - geo.ox) / geo.uw * 100, (q[1] - geo.oy) / geo.uh * 100
                        pid = pids[2 * k + t]
                        ET.SubElement(o, 'AP', dict(ID=str(pid), Flags=('3' if j == 0 else '8') if t == 0 else ('8' if j == len(p) - 1 else '9'), Index=str(t), X=str(round(float(x), 4)), Y=str(round(float(y), 4))))
                        pp.append(pid)
                    objs.append((o, pp))
                    k += 1
                n = len(objs)
                for j, (o, pp) in enumerate(objs):
                    ET.SubElement(o.findall('AP')[1], 'AC', dict(ConnPtId=str(objs[(j + 1) % n][1][0])))
                    ET.SubElement(o.findall('AP')[0], 'AC', dict(ConnPtId=str(objs[(j - 1) % n][1][1])))
                fr = ET.Element('FR', dict(Color=str(int(run[0].get('Color')) & 0xFFFFFFFF)))
                for o, pp in objs:
                    ET.SubElement(fr, 'FS', dict(Kind='0', ObjId=o.get('ID'), StartPtId=str(pp[0]), EndPtId=str(pp[1]), StartT='0.0', EndT='1.0'))
                new += [o for o, _ in objs]
                frs.append(fr)
            img2 = alone(root, f, [copy.deepcopy(o) for o in new], [copy.deepcopy(r) for r in frs])
            d = (np.abs(img2 - img).max(-1) > 30).sum() / max(mask.sum(), 1)
            if d > a.max_diff:
                rej += 1
                continue
            pos = list(f).index(run[0])
            for o in run:
                f.remove(o)
            for j, o in enumerate(new):
                f.insert(pos + j, o)
            for r in frs:
                f.append(r)
            ok += 1
        n1 = len(f.findall('AO'))
        tot0 += len(aos)
        tot1 += n1
        rep.append(f'장 {fi + 1}: 묶음 교체 {ok}, 남김 {rej}, 선 {len(aos)} → {n1}')
    print('\n'.join(rep))
    print(f'전체 오브젝트 {tot0} → {tot1}')
    xml = ET.tostring(root, encoding='unicode')
    with zipfile.ZipFile(a.out, 'w', zipfile.ZIP_DEFLATED) as zz:
        zz.writestr(name, '<?xml version="1.0" encoding="UTF-8" ?>' + xml)


if __name__ == '__main__':
    main()
