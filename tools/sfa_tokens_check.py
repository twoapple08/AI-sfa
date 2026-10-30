#!/usr/bin/env python3
"""정답 문장 왕복 검사(2026-10-30): SFA 장 → 토큰 → SFA 장 → 렌더해서 원본 렌더와 비교한다.
숫자: 토큰 길이 분위, 오브젝트·연결·면 보존, 화면 픽셀 차이(채널 차 > 24인 픽셀 비율).
사용: python sfa_tokens_check.py [--every 1] [--render-every 15] [--sheet 시트.jpg]
"""
import argparse
import os
import sys
import zipfile
import xml.etree.ElementTree as ET

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sfa_render as R  # noqa: E402
import sfa_tokens as K  # noqa: E402
import vec_data as V  # noqa: E402


def links(fr):
    return sum(len(p.findall('AC')) for p in fr.iter('AP'))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--every', type=int, default=1, help='파일 몇 개마다 하나')
    ap.add_argument('--render-every', type=int, default=15, help='장 몇 개마다 렌더 비교')
    ap.add_argument('--W', type=int, default=640)
    ap.add_argument('--sheet')
    a = ap.parse_args()
    H = a.W * 9 // 16
    L, diffs, worst, tot = [], [], [], dict(objs=0, links_in=0, links_out=0, fills_in=0, fills_out=0, drop_invis=0, drop_far=0, clamp=0, link_fwd=0)
    k = 0
    for rel in V.file_list()[::a.every]:
        z = zipfile.ZipFile('data/user_sfa/' + rel)
        root = ET.fromstring(z.read(z.namelist()[0]))
        for fr in root.findall('Frame'):
            toks, st = K.encode(root, fr)
            L.append(len(toks))
            for key in ('objs', 'drop_invis', 'drop_far', 'clamp', 'link_fwd'):
                tot[key] += st[key]
            d = K.decode(toks)
            tot['links_out'] += links(d) // 2
            tot['links_in'] += st['links']
            tot['fills_in'] += st['fills']
            tot['fills_out'] += len(d.findall('FR'))
            k += 1
            if k % a.render_every == 0:
                im0 = R.render_frame(root, fr, a.W, H).astype(np.int16)
                im1 = R.render_frame(root, d, a.W, H).astype(np.int16)
                dif = float((np.abs(im0 - im1).max(-1) > 24).mean() * 100)
                diffs.append(dif)
                worst.append((dif, rel, fr.get('Position'), len(toks), im0, im1))
                worst = sorted(worst, key=lambda w: -w[0])[:6]
    L = np.array(L)
    print('장', len(L), '| 토큰 길이 분위(50/75/90/95/99):', np.percentile(L, [50, 75, 90, 95, 99]).astype(int), '최대', L.max())
    for c in (1024, 2048, 4096, 8192):
        print(f'  {c} 이하 {np.mean(L <= c) * 100:.1f}%')
    print('오브젝트', tot['objs'], '버림(안 보임)', tot['drop_invis'], '버림(화면 밖)', tot['drop_far'], '좌표 범위 넘김', tot['clamp'])
    print('연결(적음→복원)', tot['links_in'], '→', tot['links_out'], '| 면', tot['fills_in'], '→', tot['fills_out'])
    D = np.array(diffs)
    print('렌더 비교', len(D), '장 | 다른 픽셀 % 분위(50/90/99/최대):', np.percentile(D, [50, 90, 99, 100]).round(3), '| 0.5% 넘는 장', int((D > 0.5).sum()))
    for w in worst:
        print('  최악', round(w[0], 3), w[1], '장', w[2], '토큰', w[3])
    if a.sheet:
        import cv2
        rows = [np.hstack([w[4], w[5], np.abs(w[4] - w[5]).clip(0, 255) * 4]).clip(0, 255).astype(np.uint8) for w in worst]
        cv2.imwrite(a.sheet, cv2.cvtColor(np.vstack(rows), cv2.COLOR_RGB2BGR))
        print('시트', a.sheet)


if __name__ == '__main__':
    main()
