#!/usr/bin/env python3
"""영상 스타일 학습용: 짧은 LoRA 클립(6–12장)을 원본에서 '그 클립이 들어 있는 컷 전체'로 다시 자른다 (2026-10-27).

사용자 결정(10-27 저녁): SFA보다 먼저 나카무라 스타일 영상 AI. 영상 LoRA는 발생→팽창→정점→소멸을 담은 1.5–4초 클립이 필요한데
기존 781 클립은 대표 장 주변 0.5초뿐이다. 원본(Drive 01_원본영상/yutaka_nakamura_디지털)에서 컷 경계를 찾아 길게 자른다.

컷 경계: 64×36 회색 평균 차 + 색 히스토그램 차가 주변보다 크게 튀는 장. 단, 섬광·임팩트 프레임(번쩍 뒤 원래 그림으로 돌아옴)은
앞 장과 1–12장 뒤를 비교해 비슷하면 경계로 보지 않는다.
출력: shots.csv(새 id, 게시물, 시작, 끝(포함), 장수, 원래 클립들, 잘림 여부). 영상 파일은 --write 때만(학습용은 Drive·scratch만).
사용: python tools/recut_shots.py <원본 폴더> <out 폴더> [--index data/style_kb/lora_clips_index_2026-10-25.csv] [--artist yutaka_nakamura]
      [--max 97] [--min 17] [--write]
"""
import argparse
import csv
import glob
import os

import cv2
import numpy as np


def feats(path):
    cap = cv2.VideoCapture(path)
    g, h = [], []
    while True:
        ok, f = cap.read()
        if not ok:
            break
        s = cv2.resize(f, (64, 36), interpolation=cv2.INTER_AREA)
        g.append(cv2.cvtColor(s, cv2.COLOR_BGR2GRAY).astype(np.float32))
        hs = cv2.calcHist([cv2.cvtColor(s, cv2.COLOR_BGR2HSV)], [0, 1], None, [16, 8], [0, 180, 0, 256]).ravel()
        h.append(hs / max(hs.sum(), 1))
    return np.array(g), np.array(h), cap.get(cv2.CAP_PROP_FPS)


def cuts(g, h):
    n = len(g)
    if n < 2:
        return []
    d = np.zeros(n)
    for i in range(1, n):
        d[i] = np.abs(g[i] - g[i - 1]).mean() / 255 + 0.5 * np.abs(h[i] - h[i - 1]).sum()
    out = []
    for i in range(1, n):
        win = d[max(1, i - 12):i + 13]
        base = np.median(win)
        if d[i] < max(0.15, 3 * base):
            continue
        # 섬광: 바로 앞 장과 1–3장 뒤가 서로 비슷하면 경계 아님
        flash = False
        bright = g[i].mean() - g[i - 1].mean() > 25 or g[i].mean() > 225  # 섬광 판정은 실제로 밝아진(하얘진) 장에만
        for k in (range(1, 13) if bright else ()):  # 폭발 섬광이 10장 넘게 화면을 덮었다가 같은 장면으로 돌아오는 경우(123722 85–94)
            j = i + k
            if j < n:
                dj = np.abs(g[j] - g[i - 1]).mean() / 255 + 0.5 * np.abs(h[j] - h[i - 1]).sum()
                if dj < 0.4 * d[i]:
                    flash = True
                    break
        if not flash and (not out or i - out[-1] > 2):
            out.append(i)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("out")
    ap.add_argument("--index", default="data/style_kb/lora_clips_index_2026-10-25.csv")
    ap.add_argument("--artist", default="yutaka_nakamura")
    ap.add_argument("--max", type=int, default=97, help="최대 장수(넘으면 원래 클립 중심으로 자름)")
    ap.add_argument("--min", type=int, default=17)
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    rows = [r for r in csv.DictReader(open(a.index, encoding="utf-8")) if r["작가"] == a.artist]
    by_post = {}
    for r in rows:
        by_post.setdefault(r["게시물"], []).append(r)
    shots, missing = [], []
    for post, rs in sorted(by_post.items()):
        vids = glob.glob(os.path.join(a.src, f"{post}_*.mp4"))
        if not vids:
            missing.append(post)
            continue
        g, h, fps = feats(vids[0])
        n = len(g)
        bounds = [0] + cuts(g, h) + [n]
        seen = {}
        for r in rs:
            s, e = int(r["시작"]), int(r["끝"])
            k = max(i for i in range(len(bounds) - 1) if bounds[i] <= s)
            a0, b0 = bounds[k], bounds[k + 1] - 1
            seen.setdefault((a0, b0), []).append((r["클립"], s, e))
        for (a0, b0), cl in sorted(seen.items()):
            L = b0 - a0 + 1
            clipped = False
            if L > a.max:  # 원래 클립들의 중심 주변으로
                c = int(np.mean([(s + e) / 2 for _, s, e in cl]))
                a1 = max(a0, min(c - a.max // 2, b0 - a.max + 1))
                a0, b0, clipped = a1, a1 + a.max - 1, True
            L = b0 - a0 + 1
            shots.append({"id": f"s{len(shots) + 1:04d}", "게시물": post, "시작": a0, "끝": b0, "장수": L, "fps": round(fps, 3),
                          "원래클립": ";".join(c for c, _, _ in cl), "잘림": int(clipped), "짧음": int(L < a.min),
                          "원본": os.path.basename(vids[0])})
        print(post, "장", n, "경계", len(bounds) - 2, "컷", len(seen), flush=True)
    with open(os.path.join(a.out, "shots.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(shots[0].keys()))
        w.writeheader()
        w.writerows(shots)
    L = np.array([s["장수"] for s in shots])
    print(f"컷 {len(shots)} | 장수 평균 {L.mean():.1f} 중앙 {np.median(L):.0f} | {a.min}장 미만 {(L < a.min).sum()} | 잘림 {sum(s['잘림'] for s in shots)} "
          f"| 총 {L.sum()}장({L.sum() / 23.976 / 60:.1f}분) | 원본 없음 {missing}")
    if a.write:
        vd = os.path.join(a.out, "clips")
        os.makedirs(vd, exist_ok=True)
        for s in shots:
            cap = cv2.VideoCapture(os.path.join(a.src, s["원본"]))
            cap.set(cv2.CAP_PROP_POS_FRAMES, s["시작"])
            fr = [cap.read()[1] for _ in range(s["장수"])]
            fr = [f for f in fr if f is not None]
            vw = cv2.VideoWriter(os.path.join(vd, s["id"] + ".mp4"), cv2.VideoWriter_fourcc(*"mp4v"), s["fps"], (fr[0].shape[1], fr[0].shape[0]))
            for f in fr:
                vw.write(f)
            vw.release()


if __name__ == "__main__":
    main()
