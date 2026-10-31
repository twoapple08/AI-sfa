#!/usr/bin/env python3
"""층 형태 사전(tools/fx_shapes.py) 확인 시트: 종류별로 형태를 번호와 함께 그려 '그 종류 이펙트가 맞는지' 판정받는다.

사용: python tools/fx_shape_sheets.py <형태 txt> <출력 폴더> [--per-sheet 40]
- 형태마다 층(밑색 + 반투명 명암)을 그대로 그린 칸(검은 바탕), 왼쪽 위에 번호(전체 순번), 시트 위에 종류.
- 판정 목록 csv(출력 폴더/판정목록.csv: 번호,종류,출처)를 같이 만든다. 판정 결과(번호,판정[맞음/아님/애매])는
  fx_gen.py --approved 로 넘겨 '맞음'만 쓴다.
시트는 다른 작가 그림 유래라 Drive에만 둔다.
"""
import argparse
import csv
import os
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fx_gen import load_layered_with_src  # noqa: E402

CELL = 160


def draw(layers):
    im = np.zeros((CELL, CELL, 3), np.float32)
    for col, a, cs in layers:
        m = np.zeros((CELL, CELL), np.uint8)
        for hole, segs in cs:
            P = []
            for x0, y0, cx, cy, x1, y1 in segs:
                t = np.linspace(0, 1, 8)[:, None]
                P.append((1 - t) ** 2 * [x0, y0] + 2 * t * (1 - t) * [cx, cy] + t ** 2 * [x1, y1])
            if P:
                l = np.zeros_like(m)
                cv2.fillPoly(l, [np.round(np.vstack(P) * CELL * 0.42 + CELL / 2).astype(np.int32)], 1)
                m ^= l
        mm = m.astype(np.float32)[..., None] * a
        im = im * (1 - mm) + np.array(col, np.float32) * mm
    return np.clip(im, 0, 255).astype(np.uint8)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("shapes")
    ap.add_argument("out")
    ap.add_argument("--per-sheet", type=int, default=40)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    items = load_layered_with_src(a.shapes)  # [(번호, 종류, 출처, 층)]
    with open(os.path.join(a.out, "판정목록.csv"), "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["번호", "종류", "출처", "시트"])
        for kind in sorted({k for _, k, _, _ in items}):
            sel = [x for x in items if x[1] == kind]
            for si in range(0, len(sel), a.per_sheet):
                part = sel[si:si + a.per_sheet]
                tiles = []
                for num, _, src, layers in part:
                    t = draw(layers)
                    cv2.putText(t, str(num), (3, 14), 0, 0.45, (0, 0, 255), 1)
                    tiles.append(t)
                    w.writerow([num, kind, src, f"{kind}_{si // a.per_sheet + 1:02d}.jpg"])
                while len(tiles) % 8:
                    tiles.append(np.zeros((CELL, CELL, 3), np.uint8))
                sheet = np.vstack([np.hstack(tiles[i:i + 8]) for i in range(0, len(tiles), 8)])
                head = np.zeros((30, sheet.shape[1], 3), np.uint8)
                cv2.putText(head, f"{kind}  ({si + 1}-{si + len(part)} / {len(sel)})", (6, 22), 0, 0.7, (255, 255, 255), 2)
                cv2.imwrite(os.path.join(a.out, f"{kind}_{si // a.per_sheet + 1:02d}.jpg"), np.vstack([head, sheet]),
                            [cv2.IMWRITE_JPEG_QUALITY, 85])
    print("형태", len(items), "시트 폴더", a.out)


if __name__ == "__main__":
    main()
