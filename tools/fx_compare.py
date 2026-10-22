#!/usr/bin/env python3
"""생성 이펙트(SFA)를 실제 나카무라 이펙트와 같은 잣대로 잰다(tools/fx_timing.py와 같은 지표).

사용: python tools/fx_compare.py <생성.sfa> <출력 json> [--real 실제_timing.json --type explosion]
- SFA를 서버 렌더러(tools/sfa_render.py)로 960×540에 그린다. 이펙트 영역 = 바탕색과 Lab ΔE > 8인 픽셀.
- 지표: 프레임별 면적·덩어리 수·밝기·채도·무게중심·새 그림 여부 → 수명별 길이·정점까지·정점 면적·면적곡선·밝기곡선·그림 유지.
- --real을 주면 fx_timing 결과의 같은 종류와 나란히 찍는다(중앙값끼리, 곡선은 칸별 차이).
"""
import argparse
import json
import os
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from effect_layers import delta_e  # noqa: E402
from fx_timing import frame_stats, life_stats, lives, q  # noqa: E402
from sfa_render import iter_frames, render_frame  # noqa: E402

W, H = 960, 540


def measure(sfa):
    imgs, masks = [], []
    for seq, fr in iter_frames(sfa):
        im = render_frame(seq, fr, W, H)[..., ::-1].copy()  # RGB → BGR
        bgv = int(fr.get("BackgroundColor", seq.get("BackgroundColor", "-1"))) & 0xFFFFFFFF
        bg = np.array([bgv & 255, (bgv >> 8) & 255, (bgv >> 16) & 255], np.uint8)
        masks.append(delta_e(im, np.broadcast_to(bg, im.shape).copy()) > 8)
        imgs.append(im)
    F = frame_stats(np.array(masks), imgs)
    L = [life_stats(F, a, b) for a, b in lives(F)]
    hold = np.array([h for x in L for h in x["holds"]], int)
    return {"수명수": len(L), "길이(프레임)": q([x["len"] for x in L]), "정점까지(프레임)": q([x["to_peak"] for x in L]),
            "정점면적(화면비)": q([x["peak_area"] for x in L]), "갈라짐(덩어리 증가 횟수)": q([x["splits"] for x in L]),
            "무게중심 이동(화면높이/프레임)": q([x["move_per_frame"] for x in L]),
            "면적곡선(정점=1, 수명 10칸)": np.round(np.nanmean([x["curve"] for x in L], 0), 3).tolist() if L else None,
            "밝기곡선(V, 수명 10칸)": np.round(np.nanmean([x["bright"] for x in L], 0), 1).tolist() if L else None,
            "그림유지": ({f"{k}s": round(float((hold == k).mean()), 3) for k in (1, 2, 3, 4)} |
                       {"5s+": round(float((hold >= 5).mean()), 3), "n": int(len(hold))}) if len(hold) else None,
            "프레임별면적": F[:, 0].round(4).tolist()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("sfa")
    ap.add_argument("out")
    ap.add_argument("--real")
    ap.add_argument("--type", default="explosion")
    a = ap.parse_args()
    gen = measure(a.sfa)
    json.dump(gen, open(a.out, "w"), ensure_ascii=False, indent=1)
    keys = ["길이(프레임)", "정점까지(프레임)", "정점면적(화면비)", "갈라짐(덩어리 증가 횟수)", "무게중심 이동(화면높이/프레임)"]
    real = json.load(open(a.real))["types"].get(a.type) if a.real else None
    for k in keys:
        g = gen.get(k)
        r = real.get(k) if real else None
        print(f"{k:28s} 생성 {g['중앙'] if g else '-':>8}   실제 {r['중앙'] if r else '-':>8}")
    for k in ("면적곡선(정점=1, 수명 10칸)", "밝기곡선(V, 수명 10칸)"):
        print(k, "생성", gen.get(k))
        if real:
            print(" " * len(k), "실제", real.get(k))
    print("그림유지 생성", gen.get("그림유지"), "\n그림유지 실제", real.get("그림유지") if real else "-")


if __name__ == "__main__":
    main()
