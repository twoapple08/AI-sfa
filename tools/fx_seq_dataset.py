#!/usr/bin/env python3
"""이펙트 시퀀스 학습 자료(2D, 2026-10-23 — docs/FX-LEARNING-PLAN-2026-10-23.md 1단계).

Kaggle 이펙트 분리 마스크(*_v3.npz: 물체별 마스크·라벨, *_ink.npz: 임팩트 먹)에서 물체 하나의 시간 변화를 잘라
128×128×16 알파 시퀀스로 만든다. 사람 물체는 뺀다. 원본 유래라 결과는 Drive·서버에만(저장소에는 이 도구만).
사용: python tools/fx_seq_dataset.py <마스크 폴더> <출력 npz> [--size 128] [--frames 16] [--preview 미리보기.mp4]
"""
import argparse
import glob
import os

import cv2
import numpy as np

# 라벨 낱말 → 종류(앞에 있는 것이 먼저 맞음). 'person'은 없으므로 빠진다
KIND = {"explosion": "explosion", "shockwave": "explosion", "flash": "flash", "fire": "fire", "flame": "fire",
        "smoke": "smoke", "dust": "smoke", "cloud": "smoke", "rock": "debris", "stone": "debris", "rubble": "debris",
        "debris": "debris", "spark": "spark", "lightning": "spark"}


def unpack(m, width):
    """비트 압축(가로 8픽셀 = 1바이트) → 0/1."""
    return np.unpackbits(m, axis=-1)[..., :width]


def crop_seq(seq, size, frames):
    """[T,H,W] 0/1 → 시간 전체 bbox(정사각, 여유 10%)로 잘라 size², frames 장으로."""
    ys, xs = np.nonzero(seq.any(0))
    if len(ys) == 0:
        return None
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    c = ((y0 + y1) / 2, (x0 + x1) / 2)
    r = max(y1 - y0, x1 - x0) * 0.55 + 2
    Y0, X0 = int(c[0] - r), int(c[1] - r)
    S = int(2 * r)
    pad = np.zeros((seq.shape[0], S, S), np.uint8)
    sy0, sx0 = max(0, Y0), max(0, X0)
    sy1, sx1 = min(seq.shape[1], Y0 + S), min(seq.shape[2], X0 + S)
    pad[:, sy0 - Y0:sy1 - Y0, sx0 - X0:sx1 - X0] = seq[:, sy0:sy1, sx0:sx1]
    t = np.linspace(0, seq.shape[0] - 1, frames).round().astype(int)
    out = np.stack([cv2.resize(pad[k].astype(np.float32), (size, size), interpolation=cv2.INTER_AREA) for k in t])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("masks")
    ap.add_argument("out")
    ap.add_argument("--size", type=int, default=128)
    ap.add_argument("--frames", type=int, default=16)
    ap.add_argument("--min-frac", type=float, default=0.002, help="화면 대비 최대 면적이 이보다 작은 물체는 뺌")
    ap.add_argument("--preview")
    a = ap.parse_args()
    X, Y, src = [], [], []
    for f in sorted(glob.glob(os.path.join(a.masks, "*_v3.npz"))):
        z = np.load(f, allow_pickle=True)
        h, w8 = z["obj_mask"].shape[-2:]
        width = w8 * 8
        for j, lab in enumerate(z["labels"]):
            kind = next((v for k, v in KIND.items() if k in str(lab).lower()), None)
            if kind is None:
                continue
            seq = unpack(z["obj_mask"][j], width)
            if seq.sum(axis=(1, 2)).max() < a.min_frac * h * width:
                continue
            c = crop_seq(seq, a.size, a.frames)
            if c is not None:
                X.append(c)
                Y.append(kind)
                src.append(f"{os.path.basename(f)}:{lab}")
    for f in sorted(glob.glob(os.path.join(a.masks, "*_ink.npz"))):
        z = np.load(f, allow_pickle=True)
        m = z["mask"]
        width = m.shape[-1] * 8 if m.dtype == np.uint8 and m.max() > 1 else m.shape[-1]
        seq = unpack(m, width) if width != m.shape[-1] else (m > 0).astype(np.uint8)
        if seq.sum(axis=(1, 2)).max() < a.min_frac * seq.shape[1] * seq.shape[2]:
            continue
        c = crop_seq(seq, a.size, a.frames)
        if c is not None:
            X.append(c)
            Y.append("impact")
            src.append(os.path.basename(f))
    X = np.stack(X).astype(np.float16)
    np.savez_compressed(a.out, x=X, kind=np.array(Y), src=np.array(src))
    kinds, cnt = np.unique(Y, return_counts=True)
    print("시퀀스", len(X), dict(zip(kinds.tolist(), cnt.tolist())), "모양", X.shape)
    if a.preview:  # 종류별 앞 6개를 격자로 움직이는 미리보기
        rows = []
        for k in kinds:
            idx = [i for i, y in enumerate(Y) if y == k][:6]
            rows.append((k, idx + [None] * (6 - len(idx))))
        s = a.size
        vw = cv2.VideoWriter(a.preview, cv2.VideoWriter_fourcc(*"mp4v"), 8, (6 * s + 90, len(rows) * s))
        for rep in range(3):
            for t in range(a.frames):
                img = np.full((len(rows) * s, 6 * s + 90, 3), 255, np.uint8)
                for r, (k, idx) in enumerate(rows):
                    cv2.putText(img, k, (4, r * s + s // 2), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
                    for c, i in enumerate(idx):
                        if i is not None:
                            img[r * s:(r + 1) * s, 90 + c * s:90 + (c + 1) * s] = (255 - X[i, t].astype(np.float32) * 230).astype(np.uint8)[..., None]
                vw.write(img)
        vw.release()


if __name__ == "__main__":
    main()
