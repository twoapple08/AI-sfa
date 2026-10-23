#!/usr/bin/env python3
"""빛 계열 이펙트(섬광·글로우·빔·불빛)를 밝기로 뽑아 반투명 겹으로 SFA 만들기 (2026-10-23 시험).

마스크(안/밖 두 값)는 점점 옅어지는 글로우를 담지 못했다(사용자 판정). 그래서 마스크 없이:
- 배경 추정 B = 앞뒤 ±win 프레임에서 픽셀마다 가장 어두운 값(빛 이펙트는 잠깐 밝게 더해진다고 본다).
- 투명도 a = (밝기 - 배경 밝기) / (255 - 배경 밝기), 0..1. 이펙트 색 C = (I - (1-a)·B) / a.
- a를 여러 단계로 나눠 '바깥 넓고 옅게 → 안쪽 좁고 진하게' 반투명 채우기 겹으로 쌓는다(AGENTS 투명도 원칙).
  윤곽은 기존 분해기(effect_layers.outline_mask)의 곡선 조각, 쓰기는 effect_clip_sfa.frame_xml 그대로.
한계: 카메라가 크게 움직이거나 빛이 구간 내내 켜져 있으면 배경 추정이 틀린다. 어두운 선화는 담지 않는다.
사용: python tools/fx_glow_sfa.py <영상> <시작> <끝> <출력.sfa> [--win 8] [--bg 0,0,0]
"""
import argparse
import os
import sys
import zipfile

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from effect_vectorize import outline_mask  # noqa: E402
from effect_clip_sfa import H, Writer, argb, frame_xml  # noqa: E402
from effect_vectorize import read_frame  # noqa: E402

# 단계 14개(7개는 경계가 계단처럼 보였다, 2026-10-23)
LEVELS = tuple(round(x, 3) for x in np.linspace(0.06, 0.94, 14))


def is_impact_frame(img):
    """한 장이 임팩트 프레임(흑백 그래픽·흰 전면)인지 그림으로 판정. 판정표 프레임 번호가 영상과 몇 장씩 어긋나서(239055)
    범위만으로는 일반 장면(색 있는 어두운 컷)까지 칠해졌다(2026-10-23 사용자). 채도가 낮고, 흰 면이 넓거나 아주 밝은·어두운 픽셀이 대부분."""
    s = cv2.resize(img, (160, 90))
    hsv = cv2.cvtColor(s, cv2.COLOR_BGR2HSV)
    v, sat = hsv[..., 2], np.median(hsv[..., 1])
    white = (v > 215).mean()
    ext = ((v < 40) | (v > 215)).mean()
    return bool(sat < 45 and (white > 0.25 or (ext > 0.85 and white > 0.05)))


def glow_doc(img, bgimg, tol=1.0, min_area=30, floor=0.0):
    I = img.astype(np.float32)
    B = bgimg.astype(np.float32)
    v, vb = I.max(-1), B.max(-1)
    a = np.clip((v - vb) / np.maximum(255 - vb, 8), 0, 1)
    if floor > 0:  # 이 밝기 아래는 완전히 검정(임팩트 프레임: 흰색·포인트색만 남기고 나머지는 검정)
        a = np.clip((a - floor) / (1 - floor), 0, 1)
    a = cv2.GaussianBlur(a, (0, 0), 1.2)
    C = np.clip((I - (1 - a[..., None]) * B) / np.maximum(a[..., None], 0.05), 0, 255)
    layers, prev = [], 0.0
    for lv in LEVELS:
        m = (a >= lv).astype(np.uint8)
        m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
        if m.sum() < min_area:
            break
        _, sh = outline_mask(m * 255, tol, min_area)
        if sh:
            col = np.median(C[m > 0], 0)
            layers.append({"kind": "shade", "color": col.round(1).tolist(), "alpha": round(1 - (1 - lv) / (1 - prev), 4),
                           "level": lv, "shapes": sh})
        prev = lv
    return {"layers": layers, "lines": [], "stats": {"layers": len(layers), "a_max": round(float(a.max()), 2)}}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("start", type=int)
    ap.add_argument("end", type=int)
    ap.add_argument("out")
    ap.add_argument("--win", type=int, default=8, help="배경 추정에 쓰는 앞뒤 프레임 수")
    ap.add_argument("--pre", type=int, default=16,
                    help="구간 시작 전 프레임 수 — 이펙트가 나오기 전 화면도 배경 후보에 넣는다(오래 켜진 빛의 중심이 배경으로 착각돼 비던 문제)")
    ap.add_argument("--bg", default="0,0,0")
    ap.add_argument("--black-key", action="store_true",
                    help="임팩트 프레임용(2026-10-23 사용자 제안): 배경 추정 없이 검정과 비교 — 흰색·포인트색(파·초·빨)만 잡고 나머지는 검정")
    ap.add_argument("--floor", type=float, default=0.35, help="--black-key일 때 이 밝기(0–1) 아래는 버림")
    ap.add_argument("--frames", help="이 프레임만(쉼표) — 예: 임팩트 마스크(*_ink.npz)의 그래픽 프레임")
    ap.add_argument("--auto-impact", action="store_true",
                    help="장마다 그림으로 임팩트 프레임인지 판정해 아닌 장은 빈 장으로(--only와 함께 쓰면 그 범위 ±8 안에서만)")
    ap.add_argument("--only", help="이 범위(예: 207-215,219-227)만 그리고 나머지 프레임은 빈 장으로 — 시간은 그대로. "
                                   "임팩트 판정표(impact_classify)의 '맞음' 범위를 넣어 일반 프레임에 넘쳐 적용되지 않게 한다(2026-10-23 사용자)")
    a = ap.parse_args()
    bg = [int(x) for x in a.bg.split(",")]
    lo, hi = max(0, a.start - max(a.win, a.pre)), a.end + a.win
    imgs = {}
    for f in range(lo, hi + 1):
        try:
            imgs[f] = read_frame(a.video, f, H)
        except BaseException:  # 영상 끝을 넘는 프레임은 배경 추정에서 뺀다(read_frame은 실패하면 종료한다)
            if f <= a.end:
                raise
    only = None
    if a.only:
        only = set()
        for part in a.only.split(","):
            x, y = (part.split("-") + [part])[:2]
            only |= set(range(int(x), int(y) + 1))
    wr = Writer()
    body = []
    W = None
    frames = [int(x) for x in a.frames.split(",")] if a.frames else list(range(a.start, a.end + 1))
    for pos, f in enumerate(frames):
        img = imgs[f]
        W = img.shape[1]
        skip = only is not None and f not in only
        if a.auto_impact:
            near_only = only is None or any(g in only for g in range(f - 8, f + 9))
            skip = not (near_only and is_impact_frame(img))
        if skip:
            body.append(frame_xml({"layers": [], "lines": []}, pos, wr, W, argb(bg)))
            print(f, "빈 장(판정 범위 밖)", flush=True)
            continue
        if a.black_key:
            bgimg = None
        else:
            cand = set(range(f - a.win, f + a.win + 1)) | set(range(a.start - a.pre, a.start))
            near = np.stack([imgs[g] for g in sorted(cand) if g in imgs])
            lum = near.max(-1)
            bgimg = np.take_along_axis(near, lum.argmin(0)[None, ..., None].repeat(3, -1), 0)[0]
        doc = glow_doc(img, np.zeros_like(img) if a.black_key else bgimg,
                       floor=a.floor if a.black_key else 0.0)
        body.append(frame_xml(doc, pos, wr, W, argb(bg)))
        print(f, doc["stats"], flush=True)
    name = os.path.splitext(os.path.basename(a.out))[0]
    xml = (f"<?xml version='1.0' encoding='utf-8'?>\n<Sequence Name=\"{name}\" HeightWidthRatio=\"{H / W:.4f}\" "
           f"RatioX=\"16\" RatioY=\"9\" FrameCount=\"{len(frames)}\" BackgroundColor=\"{argb(bg)}\">\n"
           + "\n".join(body) + "\n</Sequence>\n")
    with zipfile.ZipFile(a.out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(name + ".xml", xml)
    print("프레임", len(frames), "AO", wr.oid - 1, "크기MB", round(os.path.getsize(a.out) / 1e6, 1))


if __name__ == "__main__":
    main()
