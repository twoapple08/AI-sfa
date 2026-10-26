#!/usr/bin/env python3
"""장면 → 레이어 나누기(배경 / 선화 / 불 / 번개). 나카무라 불 벽 장면(히어로즈 라이징 1128–1159장)으로 맞춘 첫판 (2026-10-26).

사용자: "레이어부터 쪼개. 배경과 물체와 이펙트 등 딱 봐도 나눌 수 있는 건 나눠 봐."
색 규칙(서버 표본 HSV, OpenCV 0–180 색상):
- 번개: 하늘색(색상 78–118, 채도 > 50, 밝기 > 90) + 그 옆 9px 안의 흰 심(밝기 > 215, 채도 < 70).
- 불: 밝기 ≥ 125(빨강 불 (5,254,236), 노랑 심 밝기 250대) + 이력 문턱: 밝기 90–125라도 채도 > 200이고 불에 이어지면 불.
- 배경: 나머지(어두운 바위 밝기 20–90).
- 선화: 배경 안에서 주변보다 어두운 가는 선(블랙햇 > 10, 밝기 < 60).
번개 밑의 불은 가려진 부분을 주변 불로 메운다(번개를 끄면 구멍이 안 보이게).
출력: <out>/layers.npz (장별 마스크), <out>/sheet.jpg, <out>/layers.mp4(원본 | 배경 | 선화 | 불 | 번개).
사용: python tools/scene_layers.py <영상> <out폴더> --clip 1128 32
"""
import argparse
import os

import cv2
import numpy as np


def split(im):
    h = cv2.cvtColor(im, cv2.COLOR_BGR2HSV).astype(int)
    H, S, V = h[..., 0], h[..., 1], h[..., 2]
    cyan = ((H > 78) & (H < 118) & (S > 50) & (V > 90)).astype(np.uint8)
    white = (V > 215) & (S < 70) & (cv2.dilate(cyan, np.ones((9, 9), np.uint8)) > 0)
    light = (cyan > 0) | white
    strong = ((V >= 125) & ~light).astype(np.uint8)
    weak = ((V >= 90) & (S > 200) & ~light).astype(np.uint8)
    n, lab = cv2.connectedComponents(weak | strong)
    keep = np.unique(lab[strong > 0])
    fire = np.isin(lab, keep[keep > 0])
    fire = cv2.morphologyEx(fire.astype(np.uint8), cv2.MORPH_OPEN, np.ones((3, 3), np.uint8)) > 0
    g = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)
    bh = cv2.morphologyEx(g, cv2.MORPH_BLACKHAT, np.ones((7, 7), np.uint8))
    bg = ~fire & ~light
    line = (bh > 10) & (V < 60) & cv2.erode(bg.astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool)
    # 번개 밑 불 메우기: 번개 자리 중 둘레가 불이면 불로(번개를 지워도 불 벽이 이어지게)
    under = cv2.dilate(light.astype(np.uint8), np.ones((15, 15), np.uint8)) > 0
    fire_full = fire | (light & (cv2.blur(fire.astype(np.float32), (31, 31)) > 0.35))
    return dict(bg=bg, line=line, fire=fire, fire_full=fire_full, light=light)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("out")
    ap.add_argument("--clip", type=int, nargs=2, default=(1128, 32))
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    c = cv2.VideoCapture(a.video)
    c.set(1, a.clip[0])
    frames = [c.read()[1] for _ in range(a.clip[1])]
    masks = {k: [] for k in ("bg", "line", "fire", "fire_full", "light")}
    h, w = frames[0].shape[:2]
    vw = cv2.VideoWriter(os.path.join(a.out, "layers.mp4"), cv2.VideoWriter_fourcc(*"mp4v"), 24, (5 * 427, 240))
    sheet = []
    for i, im in enumerate(frames):
        m = split(im)
        for k in masks:
            masks[k].append(m[k])
        lay = lambda mm: np.where(mm[..., None], im, 0).astype(np.uint8)
        ln = np.full_like(im, 255); ln[m["line"]] = 0
        cells = [cv2.resize(x, (427, 240)) for x in (im, lay(m["bg"]), ln, lay(m["fire"]), lay(m["light"]))]
        for x, t in zip(cells, ("original", "background", "lines", "fire", "lightning")):
            cv2.putText(x, t, (6, 22), 0, 0.6, (0, 255, 0), 2)
        row = np.hstack(cells)
        vw.write(row)
        if i in (0, len(frames) // 3, 2 * len(frames) // 3, len(frames) - 1):
            sheet.append(row)
    vw.release()
    cv2.imwrite(os.path.join(a.out, "sheet.jpg"), np.vstack(sheet), [cv2.IMWRITE_JPEG_QUALITY, 88])
    np.savez_compressed(os.path.join(a.out, "layers.npz"), **{k: np.stack(v) for k, v in masks.items()})
    print({k: round(float(np.stack(v).mean()), 3) for k, v in masks.items()})


if __name__ == "__main__":
    main()
