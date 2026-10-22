#!/usr/bin/env python3
"""임팩트·섬광 구간의 이펙트 마스크(서버, GPU 불필요): 흑백 실루엣·단색 섬광 프레임에서 먹 영역을 뗀다.

사용: python tools/fx_ink_masks.py <구간 csv> <나카무라 영상 폴더> <출력 폴더>
- 구간: data/p3/fx_segments_impact_2026-10-22.csv(impact_classify '사용' 임팩트 앞 6 · 뒤 18프레임).
  Grounding DINO는 흑백 실루엣에서 화면 전체 상자만 내 Kaggle 방식(v3)이 아무것도 못 남겼다(4장면 시험).
- 프레임이 '흑백 그래픽'인지: 채도 낮음(S 중앙 < 40)이고 회색조 픽셀의 85% 이상이 아주 어둡거나(<60) 아주 밝다(>195).
  그래픽 프레임이면 이펙트 = 바탕(화면 테두리 중앙색)과 Lab ΔE > 25인 곳(tools/fx_flipbook.py와 같은 방식).
  Otsu 먹 나누기는 흰 섬광의 잡음을 점으로 잡고 연한 노랑 빛 형태를 놓쳤다(시험 3구간). 아니면 마스크 없음(평상 장면).
- 회색조 표준편차 < 10(거의 단색)이면 단색 섬광 → 화면 전체(섬광 길이 재기용).
출력: <post_id>_<start>_ink.npz — kaggle_fx_worker v3와 같은 키(mask, shape, frames, labels=['impact_ink'], area, obj_mask, det).
인물 실루엣이 섞일 수 있다 → 형태 판정(tools/fx_shape_sheets.py + GPT)에서 거른다. 원본 유래라 Drive에만.
"""
import csv
import glob
import json
import os
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from effect_layers import delta_e  # noqa: E402

H = 540


def fx_mask(img, thr=25):
    """바탕(화면 테두리 중앙색)과 Lab ΔE > thr인 곳 = 이펙트. 화면이 거의 단색이면 단색 섬광 → 전체."""
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    if g.std() < 10:
        return np.ones(g.shape, bool)
    border = np.concatenate([img[:4].reshape(-1, 3), img[-4:].reshape(-1, 3), img[:, :4].reshape(-1, 3), img[:, -4:].reshape(-1, 3)])
    bg = np.median(border, 0).astype(np.uint8)
    return delta_e(img, np.broadcast_to(bg, img.shape).copy()) > thr


def graphic(img):
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return np.median(hsv[..., 1]) < 40 and ((g < 60) | (g > 195)).mean() >= 0.85


def main():
    seg_csv, vdir, out = sys.argv[1:4]
    os.makedirs(out, exist_ok=True)
    n_seg = n_gfx = 0
    for s in csv.DictReader(open(seg_csv, encoding="utf-8-sig")):
        if s.get("exclude"):
            continue
        dst = os.path.join(out, f"{s['post_id']}_{s['start']}_ink.npz")
        if os.path.exists(dst):
            continue
        v = glob.glob(os.path.join(vdir, s["post_id"] + "*.mp4"))
        if not v:
            continue
        a, b = int(s["start"]), int(s["end"])
        cap = cv2.VideoCapture(v[0])
        cap.set(cv2.CAP_PROP_POS_FRAMES, a)
        masks, frames = [], []
        for f in range(a, b + 1):
            ok, im = cap.read()
            if not ok:
                break
            im = cv2.resize(im, (round(im.shape[1] * H / im.shape[0]), H), interpolation=cv2.INTER_AREA)
            m = fx_mask(im) if graphic(im) else np.zeros(im.shape[:2], bool)
            m = cv2.morphologyEx(m.astype(np.uint8), cv2.MORPH_OPEN, np.ones((2, 2), np.uint8)).astype(bool)
            masks.append(m)
            frames.append(f)
        if not masks:
            continue
        M = np.array(masks)
        pk = np.packbits(M, axis=-1)
        np.savez_compressed(dst, mask=pk, shape=np.array(M.shape), frames=np.array(frames), labels=np.array(["impact_ink"]),
                            area=M.reshape(len(M), -1).mean(1).astype(np.float32), obj_mask=pk[None], det=np.array(json.dumps([])))
        n_seg += 1
        n_gfx += int((M.reshape(len(M), -1).mean(1) > 0).sum())
        print(s["post_id"], a, b, "그래픽 프레임", int((M.reshape(len(M), -1).mean(1) > 0).sum()), "/", len(M), flush=True)
    print("구간", n_seg, "그래픽 프레임 합", n_gfx)


if __name__ == "__main__":
    main()
