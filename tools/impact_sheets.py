#!/usr/bin/env python3
"""후보 구간 검토용 띠 묶음 이미지(비공개, 서버·Drive 전용).

띠 1줄 = 앞 3프레임 | 후보(최대 4장, 길면 고르게) | 뒤 3프레임, 각 160x90. 후보 칸은 주황 테두리.
한 장에 ROWS줄. 줄 왼쪽에 번호를 쓴다(판정표와 연결).

사용: python tools/impact_sheets.py <cands.csv> <목록.tsv: post_id<TAB>경로> <출력 폴더> [--rows 10] [--filter 열=값]
출력: <출력>/sheet_###.png 와 <출력>/index.csv(sheet,row,key,cells: 칸 이름(b앞·c후보·a뒤)=프레임 번호)
"""
import argparse
import csv
import os
import subprocess

import numpy as np
from PIL import Image, ImageDraw

FW, FH, LBL = 160, 90, 64


def grab(path, idx):
    """프레임 번호 목록을 한 번의 디코딩으로 가져온다(select 필터)."""
    idx = sorted(set(i for i in idx if i >= 0))
    if not idx:
        return {}
    expr = '+'.join(f'eq(n\\,{i})' for i in idx)
    p = subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-i', path, '-vf', f"select='{expr}',scale={FW}:{FH}",
                        '-vsync', '0', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], capture_output=True)
    buf, n = p.stdout, FW * FH * 3
    out = {}
    for k, i in enumerate(idx):
        if (k + 1) * n <= len(buf):
            out[i] = np.frombuffer(buf[k * n:(k + 1) * n], np.uint8).reshape(FH, FW, 3)
    return out


def pick(s, e, k=4):
    if e - s + 1 <= k:
        return list(range(s, e + 1))
    return sorted(set(int(round(x)) for x in np.linspace(s, e, k)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('cands')
    ap.add_argument('targets')
    ap.add_argument('out')
    ap.add_argument('--rows', type=int, default=10)
    ap.add_argument('--filter', action='append', default=[])
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    paths = dict(l.rstrip('\n').split('\t') for l in open(a.targets, encoding='utf-8') if l.strip())
    rows = list(csv.DictReader(open(a.cands, encoding='utf-8')))
    for flt in a.filter:
        k, v = flt.split('=', 1)
        rows = [r for r in rows if r.get(k) == v]
    # 영상별로 모아 한 번씩 디코딩
    by = {}
    for r in rows:
        by.setdefault(r['post_id'], []).append(r)
    strips, cells = {}, {}
    for post, rs in by.items():
        want = {}
        for r in rs:
            s, e, nf = int(r['start']), int(r['end']), int(r['nframes'])
            want[r['key']] = ([i for i in range(s - 3, s) if i >= 0], pick(s, e), [i for i in range(e + 1, e + 4) if i < nf])
        got = grab(paths[post], [i for b, c, d in want.values() for i in b + c + d])
        for key, (b, c, d) in want.items():
            strips[key] = ([None] * (3 - len(b)) + [got.get(i) for i in b], [got.get(i) for i in c], [got.get(i) for i in d])
            cells[key] = ' '.join(f'{t}{k + 1}={i}' for t, g in (('b', b), ('c', c), ('a', d)) for k, i in enumerate(g))
    idx = []
    blank = np.full((FH, FW, 3), 128, np.uint8)  # 없는 칸(영상 처음·끝)은 중간 회색
    for sh in range(0, len(rows), a.rows):
        part = rows[sh:sh + a.rows]
        W = LBL + 10 * (FW + 2) + 12
        img = Image.new('RGB', (W, len(part) * (FH + 6)), (255, 255, 255))
        dr = ImageDraw.Draw(img)
        for ri, r in enumerate(part):
            y = ri * (FH + 6) + 3
            n = sh + ri + 1
            dr.text((4, y + 30), str(n), fill=(0, 0, 0))
            b, c, d = strips.get(r['key'], ([], [], []))
            x = LBL
            for grp, hl in ((b, False), (c, True), (d, False)):
                for fr in grp:
                    img.paste(Image.fromarray(fr if fr is not None else blank), (x, y))
                    if hl:
                        dr.rectangle([x - 1, y - 1, x + FW, y + FH], outline=(255, 120, 0), width=2)
                    x += FW + 2
                x += 6
            idx.append({'sheet': sh // a.rows + 1, 'row': n, 'key': r['key'], 'cells': cells.get(r['key'], '')})
        img.save(os.path.join(a.out, f'sheet_{sh // a.rows + 1:03d}.png'))
    with open(os.path.join(a.out, 'index.csv'), 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=['sheet', 'row', 'key', 'cells'])
        w.writeheader()
        w.writerows(idx)
    print('sheets', (len(rows) + a.rows - 1) // a.rows, 'rows', len(rows))


if __name__ == '__main__':
    main()
