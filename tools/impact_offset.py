#!/usr/bin/env python3
"""임팩트 판정표(impact_classify)의 프레임 번호와 실제 영상 프레임 번호 차이 찾기 (2026-10-23).

판정표 범위를 그대로 쓰면 영상에 따라 몇 프레임씩 어긋났다(239055: 표 935–941 흰 섬광, 영상은 942부터).
프레임마다 '임팩트다움' = 채도 낮음 + 아주 밝거나 어두운 픽셀 비율(흑백 그래픽)을 재고, 판정 범위(맞음=1)와 가장 잘 맞는 이동량을 고른다.
사용: python tools/impact_offset.py <영상> <범위들(예 935-941,943-945)> [--search 15]
출력: 이동량(영상 프레임 = 표 프레임 + 이동량)과 일치 점수
"""
import argparse

import cv2
import numpy as np


def impactness(path, lo, hi):
    cap = cv2.VideoCapture(path)
    cap.set(cv2.CAP_PROP_POS_FRAMES, lo)
    out = []
    for _ in range(lo, hi + 1):
        ok, f = cap.read()
        if not ok:
            out.append(0.0)
            continue
        s = cv2.resize(f, (160, 90))
        hsv = cv2.cvtColor(s, cv2.COLOR_BGR2HSV)
        v = hsv[..., 2]
        ext = ((v < 40) | (v > 215)).mean()
        sat = np.median(hsv[..., 1]) / 255
        white = (v > 215).mean()
        out.append(float(ext * (1 - sat) + 0.5 * white))
    return np.array(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("ranges")
    ap.add_argument("--search", type=int, default=15)
    a = ap.parse_args()
    rs = [tuple(map(int, (p.split("-") + [p])[:2])) for p in a.ranges.split(",")]
    lo, hi = min(r[0] for r in rs), max(r[1] for r in rs)
    L, H = lo - a.search - 4, hi + a.search + 4
    sc = impactness(a.video, max(0, L), H)
    base = max(0, L)
    best = None
    for off in range(-a.search, a.search + 1):
        lab = np.zeros(len(sc))
        for x, y in rs:
            lab[max(0, x + off - base): y + off - base + 1] = 1
        win = slice(max(0, lo + off - 4 - base), hi + off + 5 - base)
        s, l = sc[win], lab[win]
        if l.sum() == 0 or l.sum() == len(l):
            continue
        score = s[l > 0].mean() - s[l == 0].mean()
        if best is None or score > best[1]:
            best = (off, score)
    print(best[0], round(best[1], 3))


if __name__ == "__main__":
    main()
