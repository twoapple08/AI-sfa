"""포즈 추적(tools/pose_tracks.py 출력) 눈 검사용 시트를 만든다(GPT 판정용).

사용: python tools/track_sheets.py <tracks_all 폴더> <원본 영상 루트> <출력 폴더> [--n 120] [--seed 0]
- 길이 12프레임 이상인 추적을 사람다움 지표(몸점수_중앙·팔다리비_이탈) 4분위 층마다 고르게 뽑는다.
- 시트: 추적 구간의 4프레임(처음·1/3·2/3·끝)에 몸 17점 뼈대(빨강)·손발 점(초록)을 겹쳐 가로로 붙인 jpg.
- 목록 csv: 시트, 애니메이터, post_id, 추적번호, 시작 프레임, 길이, 지표 3개.
시트는 다른 작가 영상 프레임이므로 저장소에 넣지 않고 Drive에만 올린다.
"""
import argparse
import csv
import glob
import os

import cv2
import numpy as np

SK = [(5, 7), (7, 9), (6, 8), (8, 10), (5, 6), (11, 12), (5, 11), (6, 12), (11, 13), (13, 15), (12, 14), (14, 16),
      (0, 5), (0, 6)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("tracks")
    ap.add_argument("videos")
    ap.add_argument("out")
    ap.add_argument("--n", type=int, default=120)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    rng = np.random.default_rng(a.seed)
    cand = []
    for f in sorted(glob.glob(os.path.join(a.tracks, "*", "*.npz"))):
        z = np.load(f)
        for i, (L, q) in enumerate(zip(z["length"], z["quality"])):
            if L >= 12 and np.isfinite(q).all():
                cand.append((f, i, int(z["start"][i]), int(L), q))
    sc = np.array([c[4][0] for c in cand])
    dv = np.array([c[4][2] for c in cand])
    strata = (np.digitize(sc, np.percentile(sc, [25, 50, 75])) * 4 + np.digitize(dv, np.percentile(dv, [25, 50, 75])))
    pick = []
    for s in np.unique(strata):
        idx = np.where(strata == s)[0]
        pick += list(rng.choice(idx, min(len(idx), max(1, a.n // len(np.unique(strata)))), replace=False))
    pick = sorted(pick)[:a.n]
    os.makedirs(a.out, exist_ok=True)
    rows = []
    for k, ci in enumerate(pick):
        f, i, st, L, q = cand[ci]
        an, pid = os.path.basename(os.path.dirname(f)), os.path.basename(f)[:-4]
        d = "yutaka_nakamura_디지털" if an == "yutaka_nakamura" else an
        v = (glob.glob(os.path.join(a.videos, d, "**", f"{pid}_*.mp4"), recursive=True) +
             glob.glob(os.path.join(a.videos, d, "**", f"{pid}.mp4"), recursive=True))
        if not v:
            continue
        K = np.load(f)["kp"][i]
        cap = cv2.VideoCapture(v[0])
        tiles = []
        for t in np.linspace(0, L - 1, 4).astype(int):
            cap.set(cv2.CAP_PROP_POS_FRAMES, st + t)
            ok, im = cap.read()
            if not ok:
                continue
            kk = K[t]
            for p, r in SK:
                if np.isfinite(kk[p, 0]) and np.isfinite(kk[r, 0]):
                    cv2.line(im, tuple(map(int, kk[p, :2])), tuple(map(int, kk[r, :2])), (0, 0, 255), 2)
            for j in list(range(17, 23)) + list(range(91, 133)):
                if np.isfinite(kk[j, 0]):
                    cv2.circle(im, tuple(map(int, kk[j, :2])), 2, (0, 255, 0), -1)
            h = 240
            tiles.append(cv2.resize(im, (int(im.shape[1] * h / im.shape[0]), h)))
        if not tiles:
            continue
        name = f"T01_{k + 1:03d}.jpg"
        cv2.imwrite(os.path.join(a.out, name), np.hstack(tiles), [cv2.IMWRITE_JPEG_QUALITY, 80])
        rows.append([name, an, pid, i, st, L, *[round(float(x), 3) for x in q]])
    with open(os.path.join(a.out, "T01_목록.csv"), "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["시트", "애니메이터", "post_id", "추적", "시작프레임", "길이", "몸점수_중앙", "몸점_보임비율", "팔다리비_이탈"])
        w.writerows(rows)
    print(len(rows), "시트")


if __name__ == "__main__":
    main()
