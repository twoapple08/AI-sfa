#!/usr/bin/env python3
"""LoRA 클립에서 인물만 찾아 빼는 마스크 (2026-10-25, 사용자: "이펙트를 자르기보다 인물만큼 빼는 게 깔끔").

이펙트는 경계가 흐려 오리기 어렵지만 사람은 윤곽이 뚜렷하다. 사람 분할 모델(YOLO 분할, 사람 종류만)로 장마다 인물 마스크를 만든다.
결과는 '인물 뺀 장면'(인물 자리 = 검정) 학습 예시와, 생성 결과에서 인물을 빼는 데 쓴다. 애니 인물은 실사보다 덜 잡힐 수 있어 시트로 확인한다.
출력: <출력>/<클립>.npz (mask[T,H,W/8] packbits, 인물=1) + --sheet 이면 확인 그림(인물 자리 빨강)
사용: python tools/lora_person_mask.py <클립 폴더> <출력 폴더> [--only c0001,c0002] [--model yolo11l-seg.pt] [--conf 0.25] [--sheet 그림.jpg]
"""
import argparse
import glob
import os

import cv2
import numpy as np


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("clips")
    ap.add_argument("out")
    ap.add_argument("--only")
    ap.add_argument("--model", default="yolo11l-seg.pt")
    ap.add_argument("--conf", type=float, default=0.25)
    ap.add_argument("--grow", type=int, default=3, help="인물 마스크 넓히기(px) — 머리카락·옷 가장자리 잔여 줄이기")
    ap.add_argument("--sheet")
    a = ap.parse_args()
    from ultralytics import YOLO
    model = YOLO(a.model)
    os.makedirs(a.out, exist_ok=True)
    only = set(a.only.split(",")) if a.only else None
    rows = []
    for p in sorted(glob.glob(os.path.join(a.clips, "c*.mp4"))):
        cid = os.path.splitext(os.path.basename(p))[0]
        if only and cid not in only:
            continue
        cap = cv2.VideoCapture(p)
        frames = []
        while True:
            ok, x = cap.read()
            if not ok:
                break
            frames.append(x)
        H, W = frames[0].shape[:2]
        M = np.zeros((len(frames), H, W), np.uint8)
        k = np.ones((2 * a.grow + 1, 2 * a.grow + 1), np.uint8)
        for i, f in enumerate(frames):
            r = model.predict(f, classes=[0], conf=a.conf, retina_masks=True, verbose=False)[0]
            if r.masks is not None:
                m = (r.masks.data.cpu().numpy() > 0.5).any(0).astype(np.uint8)
                if m.shape != (H, W):
                    m = cv2.resize(m, (W, H), interpolation=cv2.INTER_NEAREST)
                M[i] = cv2.dilate(m, k)
        np.savez_compressed(os.path.join(a.out, f"{cid}.npz"), mask=np.packbits(M, axis=-1), shape=np.array(M.shape))
        print(cid, "인물 면적", f"{M.mean() * 100:.1f}%", flush=True)
        if a.sheet:
            pick = np.linspace(0, len(frames) - 1, 4).round().astype(int)
            th = []
            for j in pick:
                im = frames[j].copy()
                mm = M[j] > 0
                im[mm] = (im[mm] * 0.4 + np.array([0, 0, 255]) * 0.6).astype(np.uint8)
                th.append(cv2.resize(im, (240, 135)))
            bar = np.zeros((18, 960, 3), np.uint8)
            cv2.putText(bar, f"{cid}  person {M.mean() * 100:.1f}%", (4, 13), 0, 0.45, (255, 255, 255), 1)
            rows.append(np.vstack([bar, np.hstack(th)]))
    if a.sheet and rows:
        cv2.imwrite(a.sheet, np.vstack(rows), [cv2.IMWRITE_JPEG_QUALITY, 82])


if __name__ == "__main__":
    main()
