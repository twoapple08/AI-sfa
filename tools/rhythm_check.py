#!/usr/bin/env python3
"""GPT 작화 리듬 판정(rhythm 구간)을 픽셀 측정으로 교차 확인 (2026-10-27).

시트와 같은 장(원본 a+1+k, shot_sheets/wan_lora_dataset 참고)을 순서대로 읽고, 앞 장과 '같은 그림'인지 잰다:
427×240 회색에서 10 넘게 다른 픽셀이 0.05% 미만이면 같은 그림(홀드). 카메라가 움직이면 같은 그림도 픽셀이 바뀌므로
GPT가 camera=["고정"]이라고 한 구간만 비교한다. 리듬별 기대 '같은 그림' 비율: 1s 0, 2s 0.5, 3s 0.67, 홀드N 1.
측정 비율을 가장 가까운 리듬으로 분류해 GPT 판정과의 일치표를 낸다(4장 이상 구간만). 판정 보조 지표이지 정답이 아니다.
결과(2026-10-27, GPT 75컷): 픽셀 기준 고정 카메라 80구간 일치 42% — GPT 1s는 20/20 일치, 2s·3s·홀드는 판별 불가.
나카무라 장면은 그림을 유지해도 섬광 밝기·글로우 깜빡임·미세 이동이 매 장 겹치고(s0037: 번개는 눈으로 2s 확인, 픽셀은 매 장 변화),
느린 연기의 새 그림은 잡음 수준이라(s0056 3s ≈ s0083 정지) --edge(새 선 비율)로도 구분되지 않았다.
→ 리듬은 GPT 눈 판정을 쓰고, 이 도구는 명백한 모순(예: GPT 1s인데 화면 정지) 경고용.
사용: python tools/rhythm_check.py <원본 폴더> <shots.csv> <gpt jsonl...> [--out rhythm_check.csv]
"""
import argparse
import collections
import csv
import json
import os

import cv2
import numpy as np

EXPECT = {"1s": 0.0, "2s": 0.5, "3s": 2 / 3, "hold": 1.0}


def new_line_frac(a, b):
    """같은 그림 판정용 '새 선 비율': 밝기 정규화 → 위상 상관으로 작은 이동 보정 → Canny 윤곽 → 2px 허용 오차로
    서로 덮이지 않는 윤곽 비율(양방향 평균). 섬광 밝기 변화·카메라 미세 이동은 무시하고 그림 자체의 변화만 본다."""
    fa, fb = [((x - x.mean()) / (x.std() + 1e-3)).astype(np.float32) for x in (a.astype(np.float32), b.astype(np.float32))]
    (dx, dy), _ = cv2.phaseCorrelate(fa, fb)
    M = np.float32([[1, 0, dx], [0, 1, dy]])
    a2 = cv2.warpAffine(a.astype(np.uint8), M, (a.shape[1], a.shape[0]), borderMode=cv2.BORDER_REPLICATE)
    ea, eb = [cv2.Canny(cv2.GaussianBlur(x.astype(np.uint8), (3, 3), 0), 40, 100) > 0 for x in (a2, b)]
    k = np.ones((5, 5), np.uint8)
    da, db = [cv2.dilate(e.astype(np.uint8), k) > 0 for e in (ea, eb)]
    na = (eb & ~da).sum() / max(eb.sum(), 1)
    nb = (ea & ~db).sum() / max(ea.sum(), 1)
    return (na + nb) / 2


def cls(r):
    return "hold" if r.startswith("홀드") else r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("shots")
    ap.add_argument("gpt", nargs="+")
    ap.add_argument("--out", default="")
    ap.add_argument("--min", type=int, default=4)
    ap.add_argument("--edge", action="store_true", help="새 선 비율 측정(밝기·작은 이동 보정, 팬 구간도 비교)")
    ap.add_argument("--thr", type=float, default=0.03, help="--edge: 새 선 비율이 이보다 작으면 같은 그림")
    a = ap.parse_args()
    shots = {r["id"]: r for r in csv.DictReader(open(a.shots, encoding="utf-8"))}
    tags = {}
    for p in a.gpt:
        for line in open(p, encoding="utf-8"):
            if line.strip():
                d = json.loads(line)
                tags[d["shot"]] = d
    cache_path, frames = None, None
    rows, conf = [], collections.Counter()
    for sid, d in sorted(tags.items(), key=lambda x: (shots[x[0]]["원본"], x[0])):
        s = shots[sid]
        if cache_path != s["원본"]:
            c = cv2.VideoCapture(os.path.join(a.src, s["원본"]))
            frames = []
            while True:
                ok, f = c.read()
                if not ok:
                    break
                frames.append(cv2.cvtColor(cv2.resize(f, (427, 240), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY).astype(np.int16))
            cache_path = s["원본"]
        base = int(s["시작"]) + 1  # 시트 k = 원본 a+1+k
        for seg in d["segments"]:
            if not a.edge and seg.get("camera") != ["고정"]:
                continue
            for r in seg.get("rhythm", []):
                k0, k1, lab = r[0], r[1], r[2]
                if lab not in ("1s", "2s", "3s") and not lab.startswith("홀드"):
                    continue
                if k1 - k0 + 1 < a.min:
                    continue
                same = []
                for k in range(k0 + 1, k1 + 1):
                    i = base + k
                    if i >= len(frames):
                        break
                    if a.edge:
                        same.append(new_line_frac(frames[i - 1], frames[i]) < a.thr)
                    else:
                        dd = np.abs(frames[i] - frames[i - 1])
                        same.append((dd > 10).mean() * 100 < 0.05)
                if not same:
                    continue
                frac = float(np.mean(same))
                meas = min(EXPECT, key=lambda c: abs(EXPECT[c] - frac))
                conf[(cls(lab), meas)] += 1
                rows.append((sid, k0, k1, lab, round(frac, 2), meas))
    if a.out:
        with open(a.out, "w", newline="", encoding="utf-8") as fh:
            csv.writer(fh).writerows([("shot", "k0", "k1", "gpt", "same_frac", "measured")] + rows)
    labs = ["1s", "2s", "3s", "hold"]
    n = sum(conf.values())
    agree = sum(conf[(l, l)] for l in labs)
    print(f"{'새 선 비율(전 구간)' if a.edge else '고정 카메라'} 구간 {n}개, 일치 {agree} ({agree / max(n, 1) * 100:.0f}%)")
    print("GPT\\측정 " + " ".join(f"{l:>5}" for l in labs))
    for l in labs:
        print(f"{l:>8} " + " ".join(f"{conf[(l, m)]:>5}" for m in labs))


if __name__ == "__main__":
    main()
