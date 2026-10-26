#!/usr/bin/env python3
"""움직임 시험 결과 zip(motion1_result.zip / motion2_result.zip) 정리 (2026-10-26).

- 압축을 풀고 깜빡임 수치(json)를 표로 출력.
- 장별 비교 시트: 줄 = 방식(블로킹·강도 또는 V1/V2/V3), 칸 = 장(최대 8장 고르게).
- --sfa 방식이름: 그 방식의 장들을 이어 SFA 영상으로 변환(stack_layers_sfa.py --clip, 이펙트 기본값), 서버 렌더 확인 그림.
사용: python tools/motion_review.py <결과.zip> <출력 폴더> [--sfa "clip s0.55"]
결과 그림은 원본 유래·생성물이라 저장소에 넣지 않는다(출력 폴더는 scratch).
"""
import argparse
import glob
import json
import os
import subprocess
import sys
import zipfile

import cv2
import numpy as np


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("zip")
    ap.add_argument("out")
    ap.add_argument("--sfa", action="append", default=[], help='"블로킹이름 방식" 예: "clip s0.55" 또는 "num V2"')
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    zipfile.ZipFile(a.zip).extractall(a.out)
    root = next(d for d in (os.path.join(a.out, "m"), os.path.join(a.out, "m2")) if os.path.isdir(d))
    for j in glob.glob(os.path.join(a.out, "*flicker.json")):
        for k, v in json.load(open(j, encoding="utf-8")).items():
            print(f"깜빡임 {k}: {v}")
    for name in sorted(os.listdir(root)):
        rows = []
        for v in sorted(os.listdir(os.path.join(root, name)), key=lambda s: (s != "blocking", s)):
            fs = sorted(glob.glob(os.path.join(root, name, v, "*.png")))
            if not fs:
                continue
            idx = np.linspace(0, len(fs) - 1, min(8, len(fs))).astype(int)
            r = np.hstack([cv2.resize(cv2.imread(fs[i]), (288, 164)) for i in idx])
            cv2.putText(r, f"{name} {v}", (6, 20), 0, 0.6, (255, 255, 255), 2)
            rows.append(r)
        w = max(r.shape[1] for r in rows)
        rows = [np.pad(r, ((0, 0), (0, w - r.shape[1]), (0, 0))) for r in rows]
        p = os.path.join(a.out, f"sheet_{name}.jpg")
        cv2.imwrite(p, np.vstack(rows), [cv2.IMWRITE_JPEG_QUALITY, 85])
        print("시트", p)
    tools = os.path.dirname(os.path.abspath(__file__))
    for spec in a.sfa:
        name, v = spec.split()
        fs = sorted(glob.glob(os.path.join(root, name, v, "*.png")))
        vid = os.path.join(a.out, f"{name}_{v}.mp4")
        h, w = cv2.imread(fs[0]).shape[:2]
        vw = cv2.VideoWriter(vid, cv2.VideoWriter_fourcc(*"mp4v"), 24, (w, h))
        for f in fs:
            vw.write(cv2.imread(f))
        vw.release()
        out = os.path.join(a.out, f"{name}_{v}.sfa")
        r = subprocess.run([sys.executable, os.path.join(tools, "stack_layers_sfa.py"), vid, out, "--clip", "0", str(len(fs)),
                            "--feather", "6", "--glow", "10", "--bg-k", "9", "--tips", "--fire-levels", "10",
                            "--check", os.path.join(a.out, f"{name}_{v}_check")], capture_output=True, text=True)
        print(spec, (r.stdout.strip().splitlines() or [r.stderr[-300:]])[-2:])


if __name__ == "__main__":
    main()
