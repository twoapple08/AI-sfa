#!/usr/bin/env python3
"""컬러 이펙트 LoRA 3차 자료 (2026-10-26, 프롬프트 조합 시험 2회차 결과 반영).

2차 컬러 LoRA는 강도·부정어와 상관없이 '폭발 = 회색 연기'로 그렸다(HANDOFF 2회차). 원인 두 가지를 자료에서 고친다.
1. 회색 연기 태그: 캡션에 연기 표시가 없는 폭발 그림이 많아 연기가 '폭발'이라는 낱말에 붙어 버렸다.
   그림에서 회색 연기 면적(채도 < 45, 밝기 70–230, 인물 자리 제외)을 재서 넓으면 `grey smoke`를 신호 낱말 바로 뒤에 붙인다.
   그러면 생성 때 부정어 `grey smoke`로 연기만 뺄 수 있다(학습 안 된 낱말을 부정어에 넣으면 엉뚱한 물체가 끼었다).
2. 인물 자리 검게 칠하기 → 마스크 손실(GPT 실험 2): 인물 뺀 판(<클립>_np)은 인물 자리를 검게 칠해서 '검은 덩어리'도 배웠다.
   원본 그림을 RGBA PNG로 쓰고 인물 자리 알파 = 0으로 두어 그 자리는 학습에서 뺀다(sd-scripts `alpha_mask = true` + `--masked_loss`;
   알파 없는 그림은 전체 1로 처리됨 — library/train_util.py). 인물 자리는 '_np가 검고 원본은 검지 않은 곳'에서 다시 얻는다.
   캡션의 `black area`는 지운다.
임팩트 쪽은 그대로 복사한다.
사용: python tools/lora_v3_data.py <2차 split 폴더(color, color_muted, impact)> <출력 폴더> [--smoke 0.25]
"""
import argparse
import glob
import os
import shutil

import cv2
import numpy as np


def person_alpha(orig, np_img):
    """_np 판에서 검게 칠한 인물 자리 → 알파(255 = 학습, 0 = 뺌). 경계는 넉넉히(JPEG 번짐)."""
    m = (np_img.max(2) < 10) & (orig.max(2) > 25)
    m = cv2.morphologyEx(m.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))
    n, cc, st, _ = cv2.connectedComponentsWithStats(m)
    keep = np.isin(cc, [i for i in range(1, n) if st[i, cv2.CC_STAT_AREA] > m.size * 0.002])
    keep = cv2.dilate(keep.astype(np.uint8), np.ones((9, 9), np.uint8))
    return np.where(keep > 0, 0, 255).astype(np.uint8)


def grey_frac(img, alpha=None):
    h = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    g = (h[..., 1] < 45) & (h[..., 2] >= 70) & (h[..., 2] <= 230)
    valid = np.ones(g.shape, bool) if alpha is None else alpha > 0
    return float((g & valid).sum() / max(1, valid.sum()))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("out")
    ap.add_argument("--smoke", type=float, default=0.25, help="회색 연기 면적 비율이 이 이상이면 grey smoke 태그")
    a = ap.parse_args()
    n = {"grey smoke": 0, "masked": 0, "copied": 0}
    for d in ("color", "color_muted"):
        os.makedirs(os.path.join(a.out, d), exist_ok=True)
        for t in sorted(glob.glob(os.path.join(a.src, d, "*.txt"))):
            cid = os.path.basename(t)[:-4]
            tags = [s.strip() for s in open(t, encoding="utf-8").read().split(",") if s.strip()]
            img = cv2.imread(os.path.join(a.src, d, cid + ".jpg"))
            alpha = None
            if cid.endswith("_np"):
                orig = cv2.imread(os.path.join(a.src, d, cid[:-3] + ".jpg"))
                alpha = person_alpha(orig, img)
                img = orig
                tags = [s for s in tags if s != "black area"]
            if "grey smoke" not in tags and grey_frac(img, alpha) >= a.smoke:
                tags.insert(1, "grey smoke")
                n["grey smoke"] += 1
            if alpha is not None:
                cv2.imwrite(os.path.join(a.out, d, cid + ".png"), np.dstack([img, alpha]))
                n["masked"] += 1
            else:
                shutil.copy(os.path.join(a.src, d, cid + ".jpg"), os.path.join(a.out, d, cid + ".jpg"))
            open(os.path.join(a.out, d, cid + ".txt"), "w", encoding="utf-8").write(", ".join(tags))
    shutil.copytree(os.path.join(a.src, "impact"), os.path.join(a.out, "impact"), dirs_exist_ok=True)
    n["copied"] = len(glob.glob(os.path.join(a.out, "impact", "*.txt")))
    print(n)


if __name__ == "__main__":
    main()
