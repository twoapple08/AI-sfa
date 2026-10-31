#!/usr/bin/env python3
"""이펙트 구간 판정 시트(사람·GPT 확인용, 2026-10-23).

자동 검출 구간 목록(data/p3/fx_segments_*.csv)은 사람이 확인하지 않아 틀린 것이 섞여 있다(예: 폭발이 아닌 장면이 폭발로).
구간마다 시작→끝 6장을 한 줄로 놓고 번호를 크게 적은 시트를 만들어, 사람이나 GPT가 종류·맞음/아님을 판정하게 한다.
사용: python tools/fx_judge_sheets.py <구간 csv> <영상 폴더(post_id_*.mp4)> <출력 폴더> [--per 6] [--cols 6]
출력: <출력>/판정시트_01.jpg …, <출력>/구간목록.csv(번호, post_id, 시작, 끝, 자동 태그)
원본 영상에서 나온 그림이므로 결과는 Drive에만 둔다.
"""
import argparse
import csv
import glob
import os

import cv2
import numpy as np

from fx_compare_video import put_text

TW, TH = 300, 169


def frames(path, s, e, n):
    cap = cv2.VideoCapture(path)
    out = []
    for f in np.linspace(s, e, n).round().astype(int):
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(f))
        ok, img = cap.read()
        out.append(cv2.resize(img, (TW, TH), interpolation=cv2.INTER_AREA) if ok else np.zeros((TH, TW, 3), np.uint8))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("segments")
    ap.add_argument("videos")
    ap.add_argument("out")
    ap.add_argument("--per", type=int, default=6, help="시트 한 장의 구간 수")
    ap.add_argument("--cols", type=int, default=6, help="구간 하나의 장 수(시작→끝)")
    ap.add_argument("--show-tags", action="store_true", help="구간 번호 아래에 tags 칸(판정된 종류)을 적는다")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    rows = [r for r in csv.DictReader(open(a.segments, encoding="utf-8")) if not r.get("exclude")]
    index = []
    sheet, page = [], 1
    head_w = 170
    for i, r in enumerate(rows, 1):
        vs = glob.glob(os.path.join(a.videos, r["post_id"] + "_*.mp4"))
        if not vs:
            continue
        s, e = int(r["start"]), int(r["end"])
        tiles = frames(vs[0], s, e, a.cols)
        head = np.full((TH, head_w, 3), 255, np.uint8)
        put_text(head, f"{i:03d}", (14, 40), 52, (0, 0, 0))
        put_text(head, f"{e - s + 1}프레임", (16, 100), 18, (90, 90, 90))
        if a.show_tags and r.get("tags"):  # 판정된 종류를 보여 줄 때(자동 태그 목록에는 쓰지 않는다)
            put_text(head, r["tags"].split(";")[0][:8], (16, 128), 20, (190, 60, 40))
        row = np.hstack([head] + tiles)
        cv2.line(row, (0, TH - 1), (row.shape[1], TH - 1), (180, 180, 180), 2)
        sheet.append(row)
        index.append((f"{i:03d}", r["post_id"], s, e, r.get("tags", "")))
        if len(sheet) == a.per:
            cv2.imwrite(os.path.join(a.out, f"판정시트_{page:02d}.jpg"), np.vstack(sheet), [cv2.IMWRITE_JPEG_QUALITY, 88])
            sheet, page = [], page + 1
    if sheet:
        cv2.imwrite(os.path.join(a.out, f"판정시트_{page:02d}.jpg"), np.vstack(sheet), [cv2.IMWRITE_JPEG_QUALITY, 88])
    with open(os.path.join(a.out, "구간목록.csv"), "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["번호", "post_id", "시작", "끝", "자동태그(믿지 말 것)"])
        w.writerows(index)
    print("구간", len(index), "시트", page if sheet else page - 1, "→", a.out)


if __name__ == "__main__":
    main()
