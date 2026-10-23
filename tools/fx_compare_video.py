#!/usr/bin/env python3
"""이펙트 복원 비교 영상: 원본 | 이펙트 SFA(만든 바탕) | 같은 SFA를 다른 바탕(흰·회색·유색)에 — 정상 속도로 나란히 (2026-10-23).

목적(docs/GPT-REDESIGN-REVIEW-2026-10-23.md 3-2): 사용자가 정상 속도 영상으로 복원 품질을 판단하고, 다른 바탕에 옮겼을 때
배경 오염(테두리 어두운 띠·원래 배경색 섞임)이 적은지 본다. 정확한 전경색·알파 복원을 보장하지 않는다 — 오염 정도를 보는 시험이다.
사용: python tools/fx_compare_video.py <원본 영상> <이펙트.sfa> <출력.mp4> [--start 프레임|auto] [--loops 3]
- --start auto: SFA 첫 장과 원본 각 프레임을 SFA가 그린 영역 안에서 비교해 시작 프레임을 찾는다(effect_clip_sfa는 step 1, 연속 프레임).
- 재생 속도: 원본 fps 그대로(SFA 한 장 = 원본 한 프레임). 짧은 구간이라 loops번 반복하고 사이에 0.4초 빈 화면.
원본 유래 영상이므로 결과는 Drive·서버 임시 폴더에만 둔다.
"""
import argparse
import os
import sys
import time

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sfa_render import iter_frames, render_frame  # noqa: E402

PW, PH = 480, 270
BGS = [("검정(만든 바탕)", None), ("흰색", (255, 255, 255)), ("회색", (128, 128, 128)), ("유색(하늘)", (90, 150, 210))]


def argb_int(rgb):
    v = (255 << 24) | (rgb[0] << 16) | (rgb[1] << 8) | rgb[2]
    return str(v - (1 << 32) if v >= 1 << 31 else v)


def render_all(sfa):
    """SFA 프레임마다 바탕별 그림(BGR, PW×PH) — {바탕 이름: [프레임…]}, 프레임당 렌더 ms."""
    out = {n: [] for n, _ in BGS}
    t0 = time.time()
    n = 0
    for seq, fr in iter_frames(sfa, None):
        orig = fr.get("BackgroundColor")
        for name, rgb in BGS:
            if rgb is not None:
                fr.set("BackgroundColor", argb_int(rgb))
            elif orig is not None:
                fr.set("BackgroundColor", orig)
            out[name].append(render_frame(seq, fr, PW, PH)[..., ::-1].copy())
        n += 1
    return out, (time.time() - t0) * 1000 / max(1, n * len(BGS))


def read_video(path):
    cap = cv2.VideoCapture(path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 24
    frames = []
    while True:
        ok, f = cap.read()
        if not ok:
            break
        frames.append(cv2.resize(f, (PW, PH), interpolation=cv2.INTER_AREA))
    return frames, fps


def find_start(video, sfa0):
    m = sfa0.max(-1) > 20  # SFA가 그린 곳(만든 바탕은 검정)
    if m.sum() < 50:
        return 0, float("nan")
    errs = [np.abs(v[m].astype(np.int16) - sfa0[m].astype(np.int16)).mean() for v in video]
    k = int(np.argmin(errs))
    return k, float(errs[k])


def label(img, text):
    cv2.rectangle(img, (0, 0), (PW, 22), (0, 0, 0), -1)
    cv2.putText(img, text, (6, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)
    return img


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("sfa")
    ap.add_argument("out")
    ap.add_argument("--start", default="auto")
    ap.add_argument("--loops", type=int, default=3)
    a = ap.parse_args()
    R, ms = render_all(a.sfa)
    n = len(R[BGS[0][0]])
    video, fps = read_video(a.video)
    if a.start == "auto":
        start, err = find_start(video, R[BGS[0][0]][0])
    else:
        start, err = int(a.start), float("nan")
    names = ["원본"] + [n_ for n_, _ in BGS]
    # 한글 글자는 cv2가 못 쓰므로 표시 이름은 영문
    shown = ["original", "SFA on black (as made)", "SFA on white", "SFA on gray", "SFA on sky color"]
    vw = cv2.VideoWriter(a.out, cv2.VideoWriter_fourcc(*"mp4v"), fps, (PW * 3, PH * 2))
    blank = np.zeros((PH * 2, PW * 3, 3), np.uint8)
    for _ in range(a.loops):
        for k in range(n):
            vk = video[min(start + k, len(video) - 1)].copy()
            tiles = [label(vk, f"{shown[0]}  frame {start + k}")]
            for i, (name, _) in enumerate(BGS):
                tiles.append(label(R[name][k].copy(), shown[i + 1]))
            info = np.zeros((PH, PW, 3), np.uint8)
            for j, line in enumerate([os.path.basename(a.sfa), f"SFA frames {n}  start {start}",
                                      f"file {os.path.getsize(a.sfa) / 1e6:.1f} MB", f"normal speed {fps:.2f} fps",
                                      f"match err {err:.1f}" if err == err else ""]):
                cv2.putText(info, line, (10, 40 + 30 * j), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (230, 230, 230), 1, cv2.LINE_AA)
            tiles.append(info)
            vw.write(np.vstack([np.hstack(tiles[:3]), np.hstack(tiles[3:])]))
        for _ in range(int(fps * 0.4)):
            vw.write(blank)
    vw.release()
    print(f"{os.path.basename(a.sfa)}: 시작 {start}(일치 오차 {err:.1f}), SFA {n}장, {os.path.getsize(a.sfa) / 1e6:.1f}MB, "
          f"서버 렌더 {ms:.0f}ms/장, fps {fps:.2f} → {a.out}")


if __name__ == "__main__":
    main()
