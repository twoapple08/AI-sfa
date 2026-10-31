#!/usr/bin/env python3
"""나카무라 폭발 장면에서 '실루엣과 움직임만' 남긴 블로킹(움직임만 잡은 밑그림) (2026-10-26 움직임 시험 1의 두 번째 입력).

사용자: 숫자로 만든 블로킹(tools/fx_blocking.py)은 둥근 덩어리라 엉성해 보임 → 실제 나카무라 실루엣·움직임으로 된 블로킹과 비교한다.
- 불 영역: 따뜻하고 밝은 큰 덩어리(stack_layers_sfa.regions와 같은 기준, 색으로 직접. 이펙트 분리 마스크는 라벨이 부정확해 안 씀).
- 화풍 지우기: 불 영역 안을 밝기 분위 4단계로 나누고 크게 흐려(선·붓질·잔무늬 제거) 고정 4색(검붉은 → 주황 → 노랑 → 흰 심)으로 칠한다.
  배경은 원본 대신 fx_blocking.py와 같은 밤 도시(같은 시드)로 바꿔 두 블로킹 조건을 맞춘다.
- 장 수·걸이는 원본 그대로(원본의 같은 그림 걸이 유지).
출력: <폴더>/f000.png …(1344×768). 원본 유래 그림이므로 저장소에 넣지 않는다(Drive·Kaggle 입력으로만).
사용: python tools/fx_blocking_clip.py <영상> <출력 폴더> [--start 0] [--n 12] [--seed 3]
"""
import argparse
import os
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from stack_layers_sfa import read_frames, regions  # noqa: E402

W, H = 1344, 768
COLS = [(30, 25, 150), (20, 90, 235), (60, 200, 255), (225, 250, 255)]  # BGR, fx_blocking.py와 같음


def night_city(seed):
    rng = np.random.default_rng(seed)
    for _ in range(25):  # fx_blocking.py와 같은 난수 순서를 맞출 필요는 없음(빌딩 모양만 비슷하면 됨)
        rng.uniform()
    img = np.zeros((H, W, 3), np.uint8); img[:] = (70, 30, 15)
    x = 0
    while x < W:
        w = int(rng.integers(60, 160)); h = int(rng.integers(120, 360))
        cv2.rectangle(img, (x, H - h), (x + w, H), (25, 15, 10), -1); x += w + int(rng.integers(0, 20))
    return img


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("out")
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument("--n", type=int, default=12)
    ap.add_argument("--seed", type=int, default=3)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    frames = [cv2.resize(f, (W, H), interpolation=cv2.INTER_AREA) for f in read_frames(a.video, a.start, a.n, 1)]
    bg = night_city(a.seed)
    for i, f in enumerate(frames):
        L, fire, _ = regions(f, np.zeros(f.shape[:2], np.uint8))
        img = bg.copy()
        if fire.any():
            # 앞을 가린 물체(철탑·지붕)가 뚫은 구멍·틈을 메우고 작은 조각(건물 흰 테두리 등)은 버린다 — 실루엣만 남기려고
            raw = cv2.morphologyEx(fire, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15)))  # 가는 선(건물 흰 테두리) 제거
            fire = cv2.morphologyEx(raw, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (91, 61)))
            cs, _ = cv2.findContours(fire, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            fire = np.zeros_like(fire)
            cv2.drawContours(fire, [c for c in cs if cv2.contourArea(c) > W * H * 0.004 and cv2.boundingRect(c)[3] > 40], -1, 1, -1)
            # 메운 자리(철탑 등)의 밝기는 주변 불 밝기로 채운다 — 안쪽 단계에 세로 줄무늬가 남지 않게
            hole = ((fire > 0) & (raw == 0)).astype(np.uint8)
            L8 = cv2.inpaint(np.clip(L, 0, 255).astype(np.uint8), hole, 9, cv2.INPAINT_TELEA) if hole.any() else L
            Ls = cv2.GaussianBlur(L8.astype(np.float32), (0, 0), 6)
            ts = np.percentile(Ls[fire > 0], [0, 25, 55, 85])
            for t, col in zip(ts, COLS):
                m = cv2.GaussianBlur(((fire > 0) & (Ls >= t)).astype(np.float32), (0, 0), 4) > 0.5
                img[m] = col
        cv2.imwrite(os.path.join(a.out, f"f{i:03d}.png"), img)
    print("장", len(frames), "→", a.out)


if __name__ == "__main__":
    main()
