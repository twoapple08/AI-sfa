#!/usr/bin/env python3
"""이펙트 플립북: 단순한 바탕 위 이펙트 장면(예: 충격파 고리)을 프레임마다 층 형태로 뽑아 생성기(tools/fx_gen.py)가 그대로 재생하게 한다.

사용: python tools/fx_flipbook.py <영상> <시작> <끝(포함)> <종류> <출력 txt(덧붙임)> [--thr 30]
- 이펙트 영역 = 바탕색(화면 테두리 픽셀 중앙값)과 Lab ΔE가 thr 넘게 다른 픽셀(바탕이 단색에 가까운 장면만). Kaggle 분리 불필요.
- 프레임마다 tools/effect_layers.py로 층 분해(밑색 + 반투명 명암 겹, 포물선 조각). 좌표는 화면 높이 1, 화면 가운데 원점.
출력(Drive만, 다른 작가 그림 유래):
  B <종류> <출처 post:start-end> <프레임 수> <화면 폭/높이>
  F <층 수>
  Y <B> <G> <R> <알파> <윤곽 수>
  C <구멍> x0 y0 cx cy x1 y1 …
"""
import argparse
import os
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from effect_layers import decompose, delta_e  # noqa: E402
from effect_vectorize import read_frame  # noqa: E402

H = 540


def fmt(v):
    return f"{v:.4f}".rstrip("0").rstrip(".")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("start", type=int)
    ap.add_argument("end", type=int)
    ap.add_argument("kind")
    ap.add_argument("out")
    ap.add_argument("--thr", type=float, default=30)
    a = ap.parse_args()
    pid = os.path.basename(a.video).split("_")[0]
    lines = []
    n = 0
    W = None
    for f in range(a.start, a.end + 1):
        img = read_frame(a.video, f, H)
        W = img.shape[1]
        border = np.concatenate([img[:4].reshape(-1, 3), img[-4:].reshape(-1, 3), img[:, :4].reshape(-1, 3), img[:, -4:].reshape(-1, 3)])
        bg = np.median(border, 0).astype(np.uint8)
        de = delta_e(img, np.broadcast_to(bg, img.shape).copy())
        valid = cv2.morphologyEx((de > a.thr).astype(np.uint8), cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
        doc, _ = decompose(img, valid=valid)
        layers = [L for L in doc["layers"] if L["shapes"]]
        lines.append(f"F {len(layers)}")
        for L in layers:
            lines.append(f"Y {' '.join(str(int(round(x))) for x in L['color'][:3])} {fmt(L['alpha'])} {len(L['shapes'])}")
            for sh in L["shapes"]:
                seg = (np.array(sh["segs"], float).reshape(-1, 2) - [W / 2, H / 2]) / H
                lines.append(f"C {int(sh['hole'])} " + " ".join(fmt(x) for x in seg.reshape(-1)))
        n += 1
        print(f, "층", len(layers), "이펙트 면적", round(float(valid.mean()), 3), "ΔE", doc["stats"]["dE_mean"], flush=True)
    with open(a.out, "a", encoding="utf-8") as fh:
        fh.write(f"B {a.kind} {pid}:{a.start}-{a.end} {n} {fmt(W / H)}\n" + "\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
