#!/usr/bin/env python3
"""그림 → 선화 지도(흰 바탕 검은 선, 원본 크기) — ControlNet lineart 추출기(lllyasviel/Annotators sk_model.pth) (2026-10-25).

규칙(주변보다 어두운 가는 선)으로 선을 찾으니 굵은 테·칠한 눈·색 경계를 놓쳐 선글라스·눈·입이 통째로 빠졌다(광사 시험).
학습된 추출기는 색 경계까지 원본 선화처럼 잡는다. 애니 전용(netG.pth)은 선이 이중으로 나와 일반판을 쓴다.
결과는 tools/effect_clip_sfa.py --line-map 으로 넘겨 붓선 면(--line-brush)으로 옮긴다.
필요: torch, controlnet_aux(0.0.9, --no-deps + einops·scikit-image), 가중치 sk_model.pth(약 17MB).
사용: python tools/lineart_map.py <그림> <출력.png> <sk_model.pth>
"""
import sys

import cv2
import numpy as np
import torch
from controlnet_aux.lineart import Generator


def main():
    img = cv2.imread(sys.argv[1])
    g = Generator(3, 1, 3)
    g.load_state_dict(torch.load(sys.argv[3], map_location="cpu"))
    g.eval()
    x = torch.from_numpy(cv2.cvtColor(img, cv2.COLOR_BGR2RGB)).float().permute(2, 0, 1)[None] / 255.0
    with torch.no_grad():
        z = g(x)[0, 0].clamp(0, 1).numpy()
    cv2.imwrite(sys.argv[2], (z * 255).astype(np.uint8))


if __name__ == "__main__":
    main()
