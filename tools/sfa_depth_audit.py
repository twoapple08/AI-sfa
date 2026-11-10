"""깊이 칸 SFA의 그리기 순서 검사(앱 기준). 서버 렌더가 아니라 앱 규칙을 흉내 낸 숫자 검사다(앱 확인 아님).

앱 규칙(docs/FORMAT.md): 레이어는 번호 오름차순, 같은 레이어 안은 객체 ID의 파일 전체 첫 등장 순서. DrawOrder는 무시.

  order      같은 장·같은 레이어 안 의도 순서(원본 SFA 첫 등장, 복사본은 원래 ID)와 앱 순서가 뒤집힌 쌍
  head-under 같은 인물 몸 조각이 자기 머리 원 안을 지나며 머리보다 위에 그려지는 장(뒷모습 구간은 정상일 수 있음)
  cross-flip 두 깊이 칸 SFA 사이, 다른 인물끼리 겹치는 조각의 실제 그리기 순서가 뒤집힌 장

예:
  python tools/sfa_depth_audit.py order 원본.sfa 깊이칸.sfa 깊이칸_report.json
  python tools/sfa_depth_audit.py head-under 깊이칸.sfa 깊이칸_report.json --frame-base 1032
  python tools/sfa_depth_audit.py cross-flip 이전.sfa 이전.json 새.sfa 새.json --frame-base 1032
"""
import argparse
import json
import os
import sys
import zipfile
import xml.etree.ElementTree as E

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sfa_depth_layers as D  # noqa: E402


def load(p):
    z = zipfile.ZipFile(p)
    return E.fromstring(z.read(z.namelist()[0]))


def id_map(rep):
    return {str(v): str(o) for o, k, v in json.load(open(rep))['id_map']} if rep and rep != '-' else {}


def first_seen(root):
    app = {}
    for f in root.findall('Frame'):
        for a in f.findall('AO'):
            app.setdefault(a.get('ID'), len(app))
    return app


def order(src, out, rep):
    S, O = load(src), load(out)
    base = first_seen(S)
    rev = id_map(rep)
    app = first_seen(O)
    bad = {}
    for i, f in enumerate(O.findall('Frame')):
        by = {}
        for a in f.findall('AO'):
            by.setdefault(a.get('LayerId'), []).append(a.get('ID'))
        inv = 0
        for ids in by.values():
            ids = [x for x in ids if rev.get(x, x) in base]
            for x in range(len(ids)):
                for y in range(x + 1, len(ids)):
                    a, b = ids[x], ids[y]
                    inv += (base[rev.get(a, a)] < base[rev.get(b, b)]) != (app[a] < app[b])
        if inv:
            bad[i] = inv
    return dict(inverted_pairs=sum(bad.values()), frames=len(bad), worst=sorted(bad.items(), key=lambda t: -t[1])[:12])


def _parts(root, rev, n):
    f = root.findall('Frame')[n]
    app = first_seen(root)
    heads, parts = {}, []
    for a in f.findall('AO'):
        if a.get('Color') == '0':
            continue
        o = int(rev.get(a.get('ID'), a.get('ID')))
        if not D.BASE < o < D.BASE + 200:
            continue
        sl, k = divmod(o - D.BASE, 100)
        p = D.pts(a)
        rank = (int(a.get('LayerId')), app[a.get('ID')])
        if k == 1:
            heads[sl] = ((p[0] + p[1]) / 2, np.linalg.norm(p[0] - p[1]) / 2, rank)
        elif a.get('TypeId') == '1' and k != 11:
            parts.append((sl, k, p, rank))
    return heads, parts


def head_under(sfa, rep, frame_base):
    r = load(sfa)
    rev = id_map(rep)
    bad = {}
    for n in range(len(r.findall('Frame'))):
        heads, parts = _parts(r, rev, n)
        for sl, k, p, rank in parts:
            if sl not in heads:
                continue
            c, rad, hr = heads[sl]
            q = [p[0] + t * (p[1] - p[0]) for t in np.linspace(.15, 1, 12)] + [p[1] + t * (p[0] - p[1]) for t in np.linspace(.15, 1, 12)]
            if rank > hr and min(np.linalg.norm(x - c) for x in q) < .85 * rad:
                bad.setdefault(n + frame_base, []).append([sl, k])
    return dict(frames=len(bad), list=bad)


def cross_flip(a, ra, b, rb, frame_base, near=20):
    A, B = load(a), load(b)
    ma, mb = id_map(ra), id_map(rb)
    bad = {}
    for n in range(len(A.findall('Frame'))):
        pa = {(sl, k): (rank, p) for sl, k, p, rank in _parts(A, ma, n)[1]}
        pb = {(sl, k): (rank, p) for sl, k, p, rank in _parts(B, mb, n)[1]}
        for x in pa:
            for y in pa:
                if x[0] == y[0] or x not in pb or y not in pb:
                    continue
                if pa[x][0] > pa[y][0] and pb[x][0] < pb[y][0]:
                    p, q = pa[x][1], pa[y][1]
                    if D.seg_closest(p[0], p[1], q[0], q[1])[0] < near:
                        bad.setdefault(n + frame_base, []).append([list(x), list(y)])
    return dict(frames=len(bad), list=bad)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    o = sub.add_parser('order'); o.add_argument('src'); o.add_argument('out'); o.add_argument('report')
    h = sub.add_parser('head-under'); h.add_argument('sfa'); h.add_argument('report'); h.add_argument('--frame-base', type=int, default=1)
    c = sub.add_parser('cross-flip')
    for k in ('a', 'ra', 'b', 'rb'):
        c.add_argument(k)
    c.add_argument('--frame-base', type=int, default=1)
    x = ap.parse_args()
    if x.cmd == 'order':
        r = order(x.src, x.out, x.report)
    elif x.cmd == 'head-under':
        r = head_under(x.sfa, x.report, x.frame_base)
    else:
        r = cross_flip(x.a, x.ra, x.b, x.rb, x.frame_base)
    print(json.dumps(r, ensure_ascii=False))


if __name__ == '__main__':
    main()
