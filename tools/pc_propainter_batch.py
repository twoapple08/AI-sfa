#!/usr/bin/env python3
"""PC방 5060: 나카무라 이펙트 클립에서 인물을 ProPainter로 지워 '깨끗한 이펙트 판'을 만든다 (2026-10-27).

GPT 계획 4단계(레이어 분리: 분할 + 배경 메우기). 불 벽 시험에서 ProPainter가 LaMa보다 원래 불 모양·바위 경계를 이어 메웠다.
입력: clips/<cid>.mp4 (LoRA 클립 781개 중 고른 것), masks/<cid>.npz (인물 마스크, tools/lora_person_mask.py --model mix 결과; mask[T,H,W/8] packbits)
순서: order.txt (인물 면적 3–30% 먼저 — 너무 작으면 지울 게 적고 너무 크면 메울 근거가 적다)
출력: out/<cid>/00000.png… (메운 장), log.csv (cid, 장수, 초). 이미 끝난 클립은 건너뜀(다시 실행해도 이어서).
사용: python pc_propainter_batch.py <작업 폴더> <ProPainter 폴더> [--limit 분]
"""
import argparse
import csv
import os
import shutil
import subprocess
import sys
import time

import cv2
import numpy as np


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("work")
    ap.add_argument("pp")
    ap.add_argument("--limit", type=float, default=0, help="이 분이 지나면 멈춤(0이면 끝까지)")
    ap.add_argument("--dilate", type=int, default=6, help="인물 마스크 넓히기(px, 머리카락·외곽선 잔여 덮기)")
    a = ap.parse_args()
    work = os.path.abspath(a.work)
    order = [l.strip() for l in open(os.path.join(work, "order.txt"), encoding="utf-8") if l.strip()]
    os.makedirs(os.path.join(work, "out"), exist_ok=True)
    log = os.path.join(work, "log.csv")
    t_start = time.time()
    k = np.ones((2 * a.dilate + 1, 2 * a.dilate + 1), np.uint8)
    for n, cid in enumerate(order):
        if a.limit and time.time() - t_start > a.limit * 60:
            print("시간 제한으로 멈춤", flush=True)
            break
        dst = os.path.join(work, "out", cid)
        if os.path.isdir(dst) and os.listdir(dst):
            continue
        cap = cv2.VideoCapture(os.path.join(work, "clips", cid + ".mp4"))
        frames = []
        while True:
            ok, f = cap.read()
            if not ok:
                break
            frames.append(f)
        z = np.load(os.path.join(work, "masks", cid + ".npz"))
        T, H, W = [int(v) for v in z["shape"]]
        M = np.unpackbits(z["mask"], axis=-1)[..., :W]
        T = min(T, len(frames))
        if T < 3:
            continue
        h8, w8 = H // 8 * 8, W // 8 * 8
        tmp = os.path.join(work, "tmp", cid)
        shutil.rmtree(tmp, ignore_errors=True)
        os.makedirs(os.path.join(tmp, "f"))
        os.makedirs(os.path.join(tmp, "m"))
        for i in range(T):
            cv2.imwrite(os.path.join(tmp, "f", f"{i:05d}.png"), cv2.resize(frames[i], (w8, h8), interpolation=cv2.INTER_AREA))
            cv2.imwrite(os.path.join(tmp, "m", f"{i:05d}.png"),
                        cv2.resize(cv2.dilate(M[i], k) * 255, (w8, h8), interpolation=cv2.INTER_NEAREST))
        t0 = time.time()
        r = subprocess.run([sys.executable, "inference_propainter.py", "-i", os.path.join(tmp, "f"), "-m", os.path.join(tmp, "m"),
                            "-o", os.path.join(tmp, "res"), "--height", str(h8), "--width", str(w8), "--fp16", "--save_frames"],
                           cwd=a.pp, capture_output=True, text=True)
        sec = time.time() - t0
        got = os.path.join(tmp, "res", "f", "frames")
        if r.returncode != 0 or not os.path.isdir(got):
            print(cid, "실패", r.stderr[-400:], flush=True)
            with open(log, "a", newline="", encoding="utf-8") as fh:
                csv.writer(fh).writerow([cid, T, round(sec, 1), "fail"])
            continue
        shutil.move(got, dst)
        shutil.rmtree(tmp, ignore_errors=True)
        with open(log, "a", newline="", encoding="utf-8") as fh:
            csv.writer(fh).writerow([cid, T, round(sec, 1), "ok"])
        print(f"[{n + 1}/{len(order)}] {cid} {T}장 {sec:.0f}초 (누적 {(time.time() - t_start) / 60:.1f}분)", flush=True)


if __name__ == "__main__":
    main()
