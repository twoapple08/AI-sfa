#!/usr/bin/env python3
"""PC ProPainter 배치 결과(ppb_out.zip) 확인: log.csv 집계 + 원본·인물 마스크·메운 결과 나란히 시트 (2026-10-27).

사용: python ppb_review.py <ppb 입력 폴더(clips·masks·order.txt)> <결과 폴더(out·log.csv) 또는 ppb_out.zip> <시트 폴더> [--n 24] [--dilate 6]
- 집계: 끝난/실패/남은 클립 수, 클립당·장당 평균 시간, 남은 클립 예상 시간(장수 비례)
- 시트: 한 줄 = 클립 하나, [원본 | 마스크(빨강=입력 마스크, 노랑=넓힌 부분) | 메운 결과 | 마스크 안 확대 차이] × 가운데 장.
  고르는 순서: 마스크 면적 큰 것·작은 것·무작위를 섞어 치우치지 않게. 판정은 눈으로 한다(숫자는 참고).
- 참고 지표(자동, 판정 아님): 마스크 안 '남은 피부·머리색 비율'이 아니라, 메운 자리와 바로 바깥 띠의 밝기 차(경계 티)만 잰다.
"""
import argparse
import csv
import os
import random
import zipfile

import cv2
import numpy as np


def load_log(path):
    rows = []
    with open(path, encoding="utf-8") as fh:
        for r in csv.reader(fh):
            if r:
                rows.append(r)
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("inp")
    ap.add_argument("res")
    ap.add_argument("sheets")
    ap.add_argument("--n", type=int, default=24)
    ap.add_argument("--dilate", type=int, default=6)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    res = a.res
    if res.endswith(".zip"):
        d = res[:-4]
        if not os.path.isdir(d):
            zipfile.ZipFile(res).extractall(d)
        res = d
    order = [l.strip() for l in open(os.path.join(a.inp, "order.txt"), encoding="utf-8") if l.strip()]
    nframes = {}
    for c in order:
        z = np.load(os.path.join(a.inp, "masks", c + ".npz"))
        cap = cv2.VideoCapture(os.path.join(a.inp, "clips", c + ".mp4"))
        nframes[c] = min(int(z["shape"][0]), int(cap.get(cv2.CAP_PROP_FRAME_COUNT)))
    rows = load_log(os.path.join(res, "log.csv"))
    ok = [r for r in rows if len(r) > 3 and r[3] == "ok"]
    fail = [r for r in rows if len(r) > 3 and r[3] == "fail"]
    okset = {r[0] for r in ok}
    on_disk = {c for c in order if os.path.isdir(os.path.join(res, "out", c)) and os.listdir(os.path.join(res, "out", c))}
    left = [c for c in order if c not in on_disk]
    sec = np.array([float(r[2]) for r in ok]) if ok else np.zeros(0)
    fr = np.array([int(r[1]) for r in ok]) if ok else np.zeros(0)
    print(f"전체 {len(order)} | 끝남(log ok) {len(ok)} | 폴더 있음 {len(on_disk)} | 실패 {len(fail)} | 남음 {len(left)}")
    if len(sec):
        print(f"클립당 평균 {sec.mean():.1f}초 (중앙 {np.median(sec):.1f}, 최소 {sec.min():.1f}, 최대 {sec.max():.1f}) | 장당 {sec.sum() / fr.sum():.2f}초")
        # 장수에 비례하는 부분 + 고정 부분을 최소제곱으로 나눠 본다(클립마다 프로세스를 새로 띄운 비용 추정)
        if len(set(fr.tolist())) > 1:
            A = np.vstack([np.ones_like(fr, dtype=float), fr.astype(float)]).T
            c0, c1 = np.linalg.lstsq(A, sec, rcond=None)[0]
            print(f"  추정: 고정 {c0:.1f}초/클립 + {c1:.2f}초/장")
        rest_fr = sum(nframes[c] for c in left)
        print(f"남은 {len(left)}개 {rest_fr}장 → 같은 속도면 약 {rest_fr * sec.sum() / fr.sum() / 60:.0f}분")
    if fail:
        print("실패 목록:", " ".join(r[0] for r in fail[:40]))
    # 시트
    os.makedirs(a.sheets, exist_ok=True)
    done = [c for c in order if c in on_disk]
    if not done:
        return
    area = {}
    for c in done:
        z = np.load(os.path.join(a.inp, "masks", c + ".npz"))
        area[c] = float(np.unpackbits(z["mask"], axis=-1)[..., :int(z["shape"][2])].mean())
    rnd = random.Random(a.seed)
    by = sorted(done, key=lambda c: area[c])
    pick = []
    for c in by[-a.n // 3:] + by[:a.n // 3] + rnd.sample(done, min(len(done), a.n)):
        if c not in pick:
            pick.append(c)
        if len(pick) >= a.n:
            break
    k = np.ones((2 * a.dilate + 1, 2 * a.dilate + 1), np.uint8)
    rows_img, stats = [], []
    tw = 320
    for c in pick:
        files = sorted(f for f in os.listdir(os.path.join(res, "out", c)) if f.endswith((".jpg", ".png")))
        i = len(files) // 2
        cap = cv2.VideoCapture(os.path.join(a.inp, "clips", c + ".mp4"))
        cap.set(cv2.CAP_PROP_POS_FRAMES, i)
        _, o = cap.read()
        z = np.load(os.path.join(a.inp, "masks", c + ".npz"))
        T, H, W = [int(v) for v in z["shape"]]
        m = np.unpackbits(z["mask"], axis=-1)[i, :, :W]
        md = cv2.dilate(m, k)
        f = cv2.imread(os.path.join(res, "out", c, files[i]))
        f = cv2.resize(f, (W, H), interpolation=cv2.INTER_CUBIC)
        ov = o.copy()
        ov[md > 0] = (0.5 * ov[md > 0] + [0, 110, 128]).astype(np.uint8)
        ov[m > 0] = (0.5 * o[m > 0] + [0, 0, 128]).astype(np.uint8)
        diff = cv2.absdiff(o, f)
        ring = cv2.dilate(md, np.ones((15, 15), np.uint8)) - md
        g = cv2.cvtColor(f, cv2.COLOR_BGR2GRAY).astype(float)
        seam = abs(g[md > 0].mean() - g[ring > 0].mean()) if md.any() and ring.any() else 0
        stats.append((c, area[c], seam))
        th = int(tw * H / W)
        cells = [cv2.resize(x, (tw, th)) for x in (o, ov, f, cv2.convertScaleAbs(diff, alpha=2))]
        row = np.hstack(cells)
        cv2.putText(row, f"{c} area {area[c] * 100:.0f}% seam {seam:.0f}", (6, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)
        rows_img.append(row)
    per = 6
    for s in range(0, len(rows_img), per):
        cv2.imwrite(os.path.join(a.sheets, f"sheet_{s // per + 1:02d}.jpg"), np.vstack(rows_img[s:s + per]), [cv2.IMWRITE_JPEG_QUALITY, 90])
    with open(os.path.join(a.sheets, "picked.csv"), "w", newline="", encoding="utf-8") as fh:
        csv.writer(fh).writerows([("cid", "mask_area", "seam_brightness_gap")] + stats)
    print("시트:", a.sheets, "열 = 원본 | 마스크(빨강 입력, 노랑 넓힘) | 메운 결과 | 차이×2")


if __name__ == "__main__":
    main()
