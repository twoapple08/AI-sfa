"""동작 구간(tools/pose_actions.py 출력) 눈 검사 시트를 만든다(GPT T02 판정용).

사용: python tools/action_sheets.py <pose_actions.csv> <tracks_all 폴더> <원본 영상 루트> <출력 폴더> [--n 100] [--seed 0]
- 규칙 동작 × 애니메이터 층마다 고르게 뽑는다.
- 시트: 구간의 4프레임(처음·1/3·2/3·끝)에 대상 인물 몸 뼈대(빨강)와 상자(노랑)를 겹쳐 가로로 붙인 jpg.
- 목록 csv에는 규칙 동작을 넣지 않는다(GPT가 규칙 답을 보고 따라가지 않도록). 대조용 정답 표는 별도 파일(_규칙.csv).
시트는 다른 작가 영상 프레임이므로 저장소에 넣지 않고 Drive에만 올린다.
"""
import argparse
import csv
import glob
import os
from collections import defaultdict

import cv2
import numpy as np

SK = [(5, 7), (7, 9), (6, 8), (8, 10), (5, 6), (11, 12), (5, 11), (6, 12), (11, 13), (13, 15), (12, 14), (14, 16),
      (0, 5), (0, 6)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("actions")
    ap.add_argument("tracks")
    ap.add_argument("videos")
    ap.add_argument("out")
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    rng = np.random.default_rng(a.seed)
    rows = list(csv.DictReader(open(a.actions, encoding="utf-8")))
    strata = defaultdict(list)
    for r in rows:
        strata[(r["동작"], r["애니메이터"])].append(r)
    per = max(1, a.n // len(strata))
    pick = []
    for k in sorted(strata):
        v = strata[k]
        pick += [v[i] for i in rng.choice(len(v), min(per, len(v)), replace=False)]
    rng.shuffle(pick)
    pick = pick[:a.n]
    os.makedirs(a.out, exist_ok=True)
    lst, ans = [], []
    for k, r in enumerate(pick):
        an, pid, ti, st, L = r["애니메이터"], r["post_id"], int(r["추적"]), int(r["시작프레임"]), int(r["길이"])
        z = np.load(os.path.join(a.tracks, an, pid + ".npz"))
        K = z["kp"][ti]
        t0 = st - int(z["start"][ti])
        d = "yutaka_nakamura_디지털" if an == "yutaka_nakamura" else an
        v = (glob.glob(os.path.join(a.videos, d, "**", f"{pid}_*.mp4"), recursive=True) +
             glob.glob(os.path.join(a.videos, d, "**", f"{pid}.mp4"), recursive=True))
        if not v:
            continue
        cap = cv2.VideoCapture(v[0])
        tiles = []
        for t in np.linspace(0, L - 1, 4).astype(int):
            cap.set(cv2.CAP_PROP_POS_FRAMES, st + t)
            ok, im = cap.read()
            if not ok:
                continue
            kk = K[t0 + t]
            pts = kk[:17, :2][np.isfinite(kk[:17, 0])]
            if len(pts):
                x0, y0 = pts.min(0) - 15
                x1, y1 = pts.max(0) + 15
                cv2.rectangle(im, (int(x0), int(y0)), (int(x1), int(y1)), (0, 220, 255), 2)
            for p, q in SK:
                if np.isfinite(kk[p, 0]) and np.isfinite(kk[q, 0]):
                    cv2.line(im, tuple(map(int, kk[p, :2])), tuple(map(int, kk[q, :2])), (0, 0, 255), 2)
            tiles.append(cv2.resize(im, (int(im.shape[1] * 240 / im.shape[0]), 240)))
        if len(tiles) < 4:
            continue
        name = f"T02_{k + 1:03d}.jpg"
        cv2.imwrite(os.path.join(a.out, name), np.hstack(tiles), [cv2.IMWRITE_JPEG_QUALITY, 80])
        lst.append([name, an, pid, st, L])
        ans.append([name, r["동작"]])
    with open(os.path.join(a.out, "T02_목록.csv"), "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["시트", "애니메이터", "post_id", "시작프레임", "길이"])
        w.writerows(lst)
    with open(os.path.join(os.path.dirname(a.out.rstrip("/")), "T02_규칙.csv"), "w", encoding="utf-8-sig",
              newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["시트", "규칙동작"])
        w.writerows(ans)
    print(len(lst), "시트")


if __name__ == "__main__":
    main()
