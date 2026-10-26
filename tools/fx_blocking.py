#!/usr/bin/env python3
"""움직임 시험용 '거친 폭발' 블로킹 애니메이션 (2026-10-26 움직임 방법 시험 1).

목적: AI가 정한 거친 움직임(덩어리 크기·위치·타이밍)을 LoRA 그림→그림으로 장마다 나카무라 화풍으로 다시 그릴 수 있는지 본다.
나카무라 영상을 넣으면 이미 화풍이 있어 시험이 안 되므로, 화풍 없는 단순한 그림을 만든다.
- 밤 도시(남색 하늘 + 검은 빌딩 실루엣) 위에 폭발: 울퉁불퉁한 덩어리(둘레 반지름에 무작위 고조파)를
  바깥 검붉은색 → 주황 → 노랑 → 흰 심 순서로 겹침. 면적은 빠르게 커져 수명 약 30%에 정점(fx_gen 가정과 같음), 심은 정점 뒤 줄어듦.
- 파편 점 몇 개가 바깥으로 날아감(속도 반감).
- 2장 걸이(나카무라 기본): 그림 12장을 2번씩 → 24장(1초, (24,24)).
출력: <폴더>/f000.png … (그림 12장, 1344×768) — 생성은 그림마다 한 번, SFA로 옮길 때 2번씩 쓴다.
사용: python tools/fx_blocking.py <출력 폴더> [--draws 12] [--seed 3]
"""
import argparse
import os

import cv2
import numpy as np

W, H = 1344, 768


def lumpy(cx, cy, r, phase, rng_h, n=360):
    t = np.linspace(0, 2 * np.pi, n, endpoint=False)
    rr = r * (1 + sum(a * np.sin(k * t + p + phase * (0.3 + 0.1 * k)) for k, a, p in rng_h))
    return np.stack([cx + rr * np.cos(t), cy + rr * np.sin(t) * 0.85], 1).astype(np.int32)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--draws", type=int, default=12)
    ap.add_argument("--seed", type=int, default=3)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    rng = np.random.default_rng(a.seed)
    harm = [(k, rng.uniform(0.04, 0.12) / (1 + 0.15 * k), rng.uniform(0, 6.3)) for k in (3, 5, 7, 9, 13)]
    city = []
    x = 0
    while x < W:  # 빌딩 실루엣(고정)
        w = int(rng.integers(60, 160)); h = int(rng.integers(120, 360))
        city.append((x, H - h, x + w, H)); x += w + int(rng.integers(0, 20))
    debris = [(rng.uniform(0, 2 * np.pi), rng.uniform(18, 40), rng.uniform(4, 9)) for _ in range(14)]
    cx, cy = W * 0.52, H * 0.55
    layers = [(1.0, (30, 25, 150)), (0.82, (20, 90, 235)), (0.62, (60, 200, 255)), (0.4, (225, 250, 255))]  # BGR
    for i in range(a.draws):
        u = i / (a.draws - 1)
        grow = min(1.0, u / 0.3) ** 0.6 if u < 0.3 else 1.0 + 0.25 * (u - 0.3)
        R = 330 * grow
        img = np.zeros((H, W, 3), np.uint8)
        img[:] = (70, 30, 15)  # 남색 밤하늘
        for (x0, y0, x1, y1) in city:
            cv2.rectangle(img, (x0, y0), (x1, y1), (25, 15, 10), -1)
        # 사그라짐: 검게 만들지 않고 배경 위로 투명해짐(바깥 검붉은 층은 연기처럼 조금 남음)
        fade = 1.0 if u < 0.55 else max(0.0, 1 - (u - 0.55) / 0.45)
        for s, col in layers:
            ss = s if s > 0.5 else s * (1.0 if u < 0.3 else max(0.25, 1 - (u - 0.3) * 1.2))  # 심은 정점 뒤 줄어듦
            al = fade if s < 1.0 else 0.35 + 0.65 * fade
            if al <= 0.02:
                continue
            ov = img.copy()
            cv2.fillPoly(ov, [lumpy(cx, cy - 40 * u, R * ss, u * 3, harm)], col, cv2.LINE_AA)
            img = cv2.addWeighted(ov, al, img, 1 - al, 0)
        for ang, v0, size in debris:  # 파편: 덩어리 가장자리에서 튀어나가 속도 반감(그림 1.5장)
            d = v0 * (1 - 0.5 ** (i / 1.5)) / (1 - 0.5 ** (1 / 1.5)) * 4
            p = (int(cx + (R * 0.9 + d) * np.cos(ang)), int(cy + (R * 0.9 + d) * np.sin(ang) * 0.85))
            cv2.circle(img, p, int(size * 1.6), (60, 160, 255), -1, cv2.LINE_AA)
        cv2.imwrite(os.path.join(a.out, f"f{i:03d}.png"), img)
    print("그림", a.draws, "장 →", a.out)


if __name__ == "__main__":
    main()
