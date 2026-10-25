#!/usr/bin/env python3
"""이펙트 화풍 LoRA 학습 자료: 원본 구간을 짧은 클립으로 쪼개고 GPT 태깅 시트를 만든다 (2026-10-25).

사용자 결정(2026-10-25): 그림체 LoRA처럼 클립을 잘게 쪼개 장면마다 태그를 단다. 원본(자르지 않은 장면)도 쓴다 —
이펙트가 아닌 것(인물·배경·카메라)에도 태그를 달아 화풍 트리거에 섞이지 않게 한다. 진짜 사람 같은 인물도 나중에 그릴 수 있게 인물 태그를 남긴다.
- 대상: GPT 이펙트 구간 판정에서 '이펙트아님'이 아닌 구간 + 나카무라 임팩트 212구간 + 다른 작가 임팩트 88구간. 같은 영상에서 겹치는 구간은 합친다.
- 쪼개기: --len 장씩(끝에 --min 장 이상 남으면 따로 한 클립). 클립 = 원본 해상도 16:9(4:3은 가운데 자름) 960x540 mp4 + 가운데 장 jpg(이미지 LoRA용).
- 태깅 시트: 클립마다 고르게 4장(작게) + 클립 번호, 한 장에 8클립.
출력(원본 그림이라 Drive에만): <출력>/clips/c<번호>.mp4, <출력>/keys/c<번호>.jpg, <출력>/sheets/sheet_<시작>-<끝>.jpg
색인(저장소에 넣어도 되는 메타데이터): <색인.csv> = 클립,작가,게시물,시작,끝,출처(fx·impact·other),구간
사용: python tools/lora_clips.py <영상 폴더> <출력 폴더> <색인.csv> [--len 12] [--min 6]
"""
import argparse
import csv
import glob
import os

import cv2
import numpy as np

FXJ = "data/p3/fx_judge_index_2026-10-23.csv"
FXG = "data/style_kb/ai_results/gpt_FXSEG_2026-10-23.csv"
IMP = "data/style_kb/impact_final_index_2026-10-24.csv"
IMO = "data/style_kb/impact_other_index_2026-10-24.csv"


def segments():
    g = {r["번호"]: r for r in csv.DictReader(open(FXG, encoding="utf-8-sig"))}
    out = []
    for r in csv.DictReader(open(FXJ, encoding="utf-8-sig")):
        if g.get(r["번호"], {}).get("종류") in (None, "이펙트아님"):
            continue
        out.append(("yutaka_nakamura", r["post_id"], int(r["시작"]), int(r["끝"]), "fx", "fx" + r["번호"]))
    for r in csv.DictReader(open(IMP, encoding="utf-8")):
        out.append((r["작가"], r["게시물"], int(r["시작"]), int(r["끝"]), "impact", r["구간"]))
    for r in csv.DictReader(open(IMO, encoding="utf-8")):
        out.append((r["작가"], r["게시물"], int(r["시작"]), int(r["끝"]), "other", r["구간"]))
    # 같은 영상에서 겹치거나 맞닿는 구간은 합친다(같은 장면을 두 번 학습하지 않게)
    out.sort(key=lambda x: (x[0], x[1], x[2]))
    merged = []
    for s in out:
        if merged and merged[-1][0] == s[0] and merged[-1][1] == s[1] and s[2] <= merged[-1][3] + 1:
            m = merged[-1]
            merged[-1] = (m[0], m[1], m[2], max(m[3], s[3]), m[4] if m[4] == s[4] else m[4] + "+" + s[4], m[5] + "+" + s[5])
        else:
            merged.append(s)
    return merged


def find_video(root, artist, post):
    pats = [os.path.join(root, f"{post}_*.mp4")] if artist == "yutaka_nakamura" else [os.path.join(root, artist, f"{post}_*.mp4")]
    for p in pats:
        v = sorted(glob.glob(p))
        if v:
            return v[0]
    return None


def crop169(img):
    h, w = img.shape[:2]
    th = round(w * 9 / 16)
    if abs(th - h) > 2 and th < h:
        y0 = (h - th) // 2
        img = img[y0:y0 + th]
    elif abs(th - h) > 2:
        tw = round(h * 16 / 9)
        x0 = (w - tw) // 2
        img = img[:, x0:x0 + tw]
    return cv2.resize(img, (960, 540), interpolation=cv2.INTER_AREA)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("videos")
    ap.add_argument("out")
    ap.add_argument("index")
    ap.add_argument("--len", type=int, default=12)
    ap.add_argument("--min", type=int, default=6)
    a = ap.parse_args()
    for d in ("clips", "keys", "sheets"):
        os.makedirs(os.path.join(a.out, d), exist_ok=True)
    rows, strips, cid, miss = [], [], 0, set()
    for artist, post, s, e, src, name in segments():
        v = find_video(a.videos, artist, post)
        if not v:
            miss.add(f"{artist}/{post}")
            continue
        cap = cv2.VideoCapture(v)
        fps = cap.get(cv2.CAP_PROP_FPS) or 24
        n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        e = min(e, n - 1)
        frames, i = [], 0
        while i <= e:  # 앞에서부터 차례로 읽는다(일부 영상은 위치 이동이 틀렸다)
            ok, x = cap.read()
            if not ok:
                break
            if i >= s:
                frames.append(crop169(x))
            i += 1
        cuts = list(range(0, len(frames), a.len))
        for k, c0 in enumerate(cuts):
            seg = frames[c0:c0 + a.len]
            if len(seg) < a.min:
                if k and len(seg):  # 짧은 꼬리는 앞 클립에 붙이지 않고 버린다(앞 클립 길이를 고르게)
                    pass
                continue
            cid += 1
            vw = cv2.VideoWriter(os.path.join(a.out, "clips", f"c{cid:04d}.mp4"), cv2.VideoWriter_fourcc(*"mp4v"), fps, (960, 540))
            for f in seg:
                vw.write(f)
            vw.release()
            cv2.imwrite(os.path.join(a.out, "keys", f"c{cid:04d}.jpg"), seg[len(seg) // 2], [cv2.IMWRITE_JPEG_QUALITY, 92])
            rows.append({"클립": f"c{cid:04d}", "작가": artist, "게시물": post, "시작": s + c0, "끝": s + c0 + len(seg) - 1,
                         "출처": src, "구간": name})
            pick = np.linspace(0, len(seg) - 1, 4).round().astype(int)
            th = [cv2.resize(seg[j], (240, 135)) for j in pick]
            for j, im in zip(pick, th):
                cv2.putText(im, str(s + c0 + j), (3, 13), 0, 0.4, (0, 255, 0), 1)
            bar = np.zeros((20, 960, 3), np.uint8)
            cv2.putText(bar, f"c{cid:04d}  {artist}  {post}  {s + c0}-{s + c0 + len(seg) - 1}  ({len(seg)}f)", (4, 14), 0, 0.45, (255, 255, 255), 1)
            strips.append((cid, np.vstack([bar, np.hstack(th)])))
    for p in range(0, len(strips), 8):
        g = strips[p:p + 8]
        cv2.imwrite(os.path.join(a.out, "sheets", f"sheet_{g[0][0]:04d}-{g[-1][0]:04d}.jpg"),
                    np.vstack([x for _, x in g]), [cv2.IMWRITE_JPEG_QUALITY, 82])
    with open(a.index, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    print("클립", cid, "시트", (len(strips) + 7) // 8, "영상 없음", sorted(miss))


if __name__ == "__main__":
    main()
