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


def yellow_mask(img):
    """노란색 계열 픽셀(색상 30–80도, 채도 있음, 밝음). 2026-10-23 사용자: 노란색은 감지에서 뺀다."""
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    h, s, v = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    return (h >= 15) & (h <= 40) & (s >= 70) & (v >= 120)


def is_impact_frame(img, drop_yellow=True, yellow_frame=0.05, in_table=True):
    """한 장이 임팩트 프레임인지 그림으로 판정(2026-10-23, 239055·232394·123722 프레임별 눈 판정과 맞춘 규칙).
    일반 장면: 채도 높고 흰 면 7% 이하. 흑백 임팩트: 채도 50 이하에 흰 면이 조금이라도 있음(검정 바탕 흰 선 포함).
    색 임팩트(빨강·노랑)·끝의 흰 번짐: 색은 있어도 흰 면이 18% 이상으로 갑자기 늘어남.
    밝은 일반 장면(흰 하늘 등)도 흰 면이 많을 수 있어 판정표 범위 ±8 안에서만 쓴다.
    색 있는 장(채도 > 50)을 흰 면만으로 받는 것은 판정표 범위 안(in_table)일 때만 — 196873 704(분홍 구름 컬러 장면,
    채도 241·흰 면 32%)가 범위 사이 틈으로 들어왔다(2026-10-23 사용자 '핑크 부분이 들어갔음')."""
    s = cv2.resize(img, (160, 90))
    hsv = cv2.cvtColor(s, cv2.COLOR_BGR2HSV)
    v, sat = hsv[..., 2], float(np.median(hsv[..., 1]))
    bright = v > 215
    if drop_yellow:  # 노랑이 화면의 yellow_frame 이상이면 그 장은 통째로 뺀다(2026-10-23 사용자), 적으면 흰 면에서만 뺀다
        ym = yellow_mask(s)
        if ym.mean() >= yellow_frame:
            return False
        bright &= ~ym
    white = float(bright.mean())
    # 10차(2026-10-23, 다른 구간 10개 눈 판정 190장): 채도 낮은 일반 장면(회색 바위·흐린 용, 중간 밝기 면 85–99%)이
    # '평균 밝기 > 100'으로 들어오고, 검은 바탕의 가는 흰 고리(흰 면 1–4%)는 놓쳤다. 임팩트는 흑백 대비가 크다 →
    # 흰 면 15% 이상이면서 중간 밝기(60–200) 면 60% 이하, 또는 어두운 면 50% 이상에 흰 면이 조금이라도 있음.
    mid = float(((v >= 60) & (v <= 200)).mean())
    dark = float((v < 50).mean())
    # 완전한 흑백(채도 ≤ 12)은 회색 종이 연필 임팩트(239055 944, 채도 5)라 밝기만 본다 — 회색 일반 장면은 채도 20–45였다.
    low_sat = (sat <= 12 and v.mean() > 100) or (sat <= 50 and ((white >= 0.15 and mid <= 0.6) or (white >= 0.01 and dark >= 0.5)))
    return low_sat or (white >= 0.18 and (sat <= 50 or in_table))


def scene_diff(img, ref):
    """두 장의 그림 차이(작게 줄인 Lab 평균 차). 임팩트 프레임은 앞뒤 일반 장면과 크게 다르다."""
    a = cv2.cvtColor(cv2.resize(img, (96, 54)), cv2.COLOR_BGR2LAB).astype(np.float32)
    b = cv2.cvtColor(cv2.resize(ref, (96, 54)), cv2.COLOR_BGR2LAB).astype(np.float32)
    return float(np.abs(a - b).mean())


def color_groups(C, hue_bins=12):
    """픽셀마다 색 묶음 번호: 0 = 흰색·회색(채도 낮음), 1.. = 색상 구간(노랑·주황·빨강 등). 작은 얼룩은 이웃 묶음에 붙인다."""
    hsv = cv2.cvtColor(C.astype(np.uint8), cv2.COLOR_BGR2HSV)
    h, s = hsv[..., 0].astype(int), hsv[..., 1]
    g = np.where(s < 60, 0, 1 + (h * hue_bins // 180) % hue_bins).astype(np.uint8)
    return cv2.medianBlur(g, 5)


def glow_doc(img, bgimg, tol=1.0, min_area=30, floor=0.0, drop_yellow=True, white=255.0, full_top=False):
    I = img.astype(np.float32)
    B = bgimg.astype(np.float32)
    v, vb = I.max(-1), B.max(-1)
    # white: 원본의 흰색(약 244)을 완전한 흰색으로 본다 — 255 기준이면 흰 면이 회색으로 나왔다(2026-10-23 사용자 '더 밝게')
    a = np.clip((v - vb) / np.maximum(white - vb, 8), 0, 1)
    if floor > 0:  # 이 밝기 아래는 완전히 검정(임팩트 프레임: 흰색·포인트색만 남기고 나머지는 검정)
        a = np.clip((a - floor) / (1 - floor), 0, 1)
    if drop_yellow:  # 노란 부분은 검정으로(뽑지 않는다)
        a[yellow_mask(img)] = 0
    a = cv2.GaussianBlur(a, (0, 0), 1.2)
    C = np.clip((I - (1 - a[..., None]) * B) / np.maximum(a[..., None], 0.05), 0, 255)
    groups = color_groups(C)
    # full_top: 맨 위 단계가 완전히 덮이게(겹을 다 쌓아도 94%만 덮여 흰색이 회색이 되던 문제)
    cov = (lambda x: min(1.0, x / LEVELS[-1])) if full_top else (lambda x: x)
    layers, prev = [], 0.0
    for lv in LEVELS:
        m = (a >= lv).astype(np.uint8)
        m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
        if m.sum() < min_area:
            break
        # 한 층을 색 하나(중앙값)로 칠하면 노랑 빛이 흰색으로, 흰 중심이 노랑으로 묻혔다(2026-10-23 사용자) → 색 묶음별로 나눠 칠한다
        for g in np.unique(groups[m > 0]):
            mg = (m > 0) & (groups == g)
            if mg.sum() < min_area:
                continue
            col = np.median(C[mg], 0)
            # 묶음 경계에 검은 틈이 보였다(167784 번개, 2026-10-23 사용자 '검은 선') → 같은 층 영역 안에서 1화소 넓혀 이웃 묶음과 겹치게
            mg = cv2.dilate(mg.astype(np.uint8), np.ones((3, 3), np.uint8), iterations=1).astype(bool) & (m > 0)
            _, sh = outline_mask(mg.astype(np.uint8) * 255, tol, min_area)
            if sh:
                layers.append({"kind": "shade", "color": col.round(1).tolist(),
                               "alpha": round(1 - (1 - cov(lv)) / (1 - cov(prev)), 4), "level": lv, "shapes": sh})
        prev = lv
    return {"layers": layers, "lines": [], "stats": {"layers": len(layers), "a_max": round(float(a.max()), 2)}}


def wash_doc(img, scene_dark, white=240.0, min_area=30):
    """임팩트와 일반 장면이 섞인 장(흰 막이 옅어지며 장면이 비침, 167784 318–343)에서 장면은 빼고 흰 막만 화면 전체 반투명 한 겹으로.
    흰 막 진하기 = (어두운 쪽 2% 밝기 − 장면 자체의 어두운 쪽 밝기) / (흰색 − 장면 어두운 쪽). 2026-10-23 사용자: '섞인 것', 이 기술은 임팩트 프레임에만."""
    v = cv2.resize(img, (160, 90)).max(-1).astype(np.float32)
    p2 = float(np.percentile(v, 2))
    alpha = float(np.clip((p2 - scene_dark) / max(white - scene_dark, 8), 0, 1))
    full = np.full(img.shape[:2], 255, np.uint8)
    _, sh = outline_mask(full, 1.0, min_area)
    layers = [{"kind": "shade", "color": [255.0, 255.0, 255.0], "alpha": round(alpha, 4), "level": 1.0, "shapes": sh}] if alpha > 0.02 else []
    return {"layers": layers, "lines": [], "stats": {"wash": round(alpha, 3)}}


def fit_16_9(img, mode):
    """4:3 등 16:9가 아닌 원본을 16:9 화면에 맞춘다(2026-10-23 사용자: 목표는 16:9 고정). crop = 위아래를 잘라 꽉 채움, pad = 양옆 검정."""
    h, w = img.shape[:2]
    tw = round(h * 16 / 9)
    if mode == "none" or abs(w - tw) <= 2:
        return img
    if mode == "pad":
        if w < tw:
            l = (tw - w) // 2
            return cv2.copyMakeBorder(img, 0, 0, l, tw - w - l, cv2.BORDER_CONSTANT, value=(0, 0, 0))
        th = round(w * 9 / 16)
        t = (h - th) // 2 if th < h else 0
        return img[t:t + th]
    th = round(w * 9 / 16)  # crop
    if th < h:
        t = (h - th) // 2
        return cv2.resize(img[t:t + th], (tw, h), interpolation=cv2.INTER_AREA)
    l = (w - tw) // 2
    return img[:, l:l + tw]


def parse_ranges(s):
    out = set()
    for part in s.split(","):
        x, y = (part.split("-") + [part])[:2]
        out |= set(range(int(x), int(y) + 1))
    return out


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
    ap.add_argument("--white", type=float, default=240.0, help="--black-key일 때 이 밝기 이상을 완전한 흰색으로 본다")
    ap.add_argument("--keep-yellow", action="store_true", help="노란색도 감지·추출(기본은 뺀다, 2026-10-23 사용자)")
    ap.add_argument("--yellow-frame", type=float, default=0.05, help="노랑이 화면의 이 비율 이상인 장은 통째로 뺀다")
    ap.add_argument("--frames", help="이 프레임만(쉼표) — 예: 임팩트 마스크(*_ink.npz)의 그래픽 프레임")
    ap.add_argument("--auto-impact", action="store_true",
                    help="장마다 그림으로 임팩트 프레임인지 판정해 아닌 장은 빈 장으로(--only와 함께 쓰면 그 범위 ±8 안에서만)")
    ap.add_argument("--fit", choices=["crop", "pad", "none"], default="crop",
                    help="16:9가 아닌 원본(4:3 등)을 16:9로: crop = 위아래 자르기(기본), pad = 양옆 검정, none = 원본 비율")
    ap.add_argument("--skip", help="임팩트가 아닌 장(번개 연출 등) 범위 — 판정과 상관없이 빈 장(사람이 지정)")
    ap.add_argument("--wash", help="임팩트와 일반 장면이 섞인 장(흰 막이 옅어지는 전환) 범위 — 장면은 빼고 흰 막만 반투명 한 겹으로(사람이 지정)")
    ap.add_argument("--tail", type=int, default=0,
                    help="--auto-impact: 판정표 마지막 범위 끝 뒤로 몇 장까지 허용할지(기본 0 — 끝에서 자름)")
    ap.add_argument("--impact-diff", type=float, default=18.0, help="--auto-impact: 앞뒤 일반 장면과의 차이가 이보다 크면 임팩트")
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
    raw = imgs  # 임팩트 판정은 원본 비율 그대로(잘라 낸 뒤 판정하면 167784 302가 다시 들어왔다)
    imgs = {f: fit_16_9(x, a.fit) for f, x in imgs.items()}
    only = parse_ranges(a.only) if a.only else None
    skip_set = parse_ranges(a.skip) if a.skip else set()
    wash = parse_ranges(a.wash) if a.wash else set()
    scene_dark = 0.0
    if wash:  # 섞인 구간 바로 뒤 장(일반 장면만 남은 장)의 어두운 쪽 밝기 = 장면 자체의 어두움
        after = max(wash) + 1
        if after in imgs:
            scene_dark = float(np.percentile(cv2.resize(imgs[after], (160, 90)).max(-1), 2))
    wr = Writer()
    body = []
    W = None
    frames = [int(x) for x in a.frames.split(",")] if a.frames else list(range(a.start, a.end + 1))
    for pos, f in enumerate(frames):
        img = imgs[f]
        W = img.shape[1]
        if f in wash:
            doc = wash_doc(img, scene_dark, a.white)
            body.append(frame_xml(doc, pos, wr, W, argb(bg)))
            print(f, doc["stats"], flush=True)
            continue
        skip = only is not None and f not in only
        if f in skip_set:  # 사람이 임팩트가 아니라고 지정한 장(예: 167784 309–310 번개 연출)
            body.append(frame_xml({"layers": [], "lines": []}, pos, wr, W, argb(bg)))
            print(f, "빈 장(지정 제외)", flush=True)
            continue
        if a.auto_impact:
            # 판정표 마지막 범위 뒤로는 넘기지 않는다: 232394 487–489(다음 장면의 역광 파편)가 흰 면 규칙으로 들어와
            # 몸통이 뚫린 주황 고리로 그려졌다(2026-10-23 사용자 '가' 선택). 앞쪽·범위 사이의 ±8 허용은 그대로.
            near_only = only is None or (f <= max(only) + a.tail and any(g in only for g in range(f - 8, f + 9)))
            # 앞뒤 장면과의 차이로 판정해 보았으나 앞뒤가 다른 컷이면 일반 장면까지 들어가 쓰지 않는다(2026-10-23)
            skip = not (near_only and is_impact_frame(raw[f], not a.keep_yellow, a.yellow_frame, only is None or f in only))
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
                       floor=a.floor if a.black_key else 0.0, drop_yellow=not a.keep_yellow,
                       white=a.white if a.black_key else 255.0, full_top=a.black_key)
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
