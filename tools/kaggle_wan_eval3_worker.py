#!/usr/bin/env python3
"""Kaggle T4 x2: 나카무라 Wan LoRA 평가 3판 — 여러 씨앗 + CPU 노이즈 기준선 (2026-10-28 밤).

2판에서 같은 씨앗이라도 PC(5060)와 T4의 결과가 구도부터 달랐다(GPU 난수 차이가 유력) → 씨앗 하나로는 판정 불가.
3판: 초기 노이즈를 CPU에서(--cpu_noise, 장비 무관 재현), 프롬프트 7개 × 씨앗 3개 × (학습 전 · 세기 0.6 · 0.8) = 63개.
프롬프트: 기존 p0–p3(pc_wan_lora_run.PROMPTS) + 학습 캡션 낱말로 고친 번개(1v)·임팩트 고리(3v) + 로봇(4r).
  'fork'·'shockwave'는 학습 캡션에 한 번도 없다(277컷 집계) → 1v·3v는 학습 캡션에 실제로 나오는 낱말(branches, monochrome impact inserts, rings expand)로.
  로봇은 지금 LoRA 캡션에 없는 낱말 — 인물·로봇 캡션을 넣은 재학습 뒤 같은 씨앗으로 다시 비교할 기준선.
DiT fp16(T4에서 bf16과 결과 거의 같고 5.6배 빠름, 2판), T5 PC와 같게(fp8 저장 + bf16).
도우미는 kaggle_wan_eval_worker.py(같은 브랜치)를 받아 쓴다.
사용(노트북): python kaggle_wan_eval3_worker.py [--out /kaggle/working]
"""
import argparse
import glob
import os
import subprocess
import sys
import threading
import zipfile

W = os.environ.get("WAN_DIR", "/tmp/wan")
RAW = "https://raw.githubusercontent.com/twoapple08/AI-sfa/ccr-bccf15a6-d6ee46/tools"
SEEDS = (11, 22, 33)
EXTRA = {
    "1v": "nkmr_fx, Cyan-white lightning with a pink rim appears at 0-1 and branches into several bolts at 2-7. The lightning flickers on ones at 8-15, then a thin glowing afterimage fades through 32. Fixed camera, one cut.",
    "3v": "nkmr_fx, Monochrome impact inserts alternate on ones at 0-3. Orange rings expand from the center at 4-15 with white radial lines, hold at 16-18, then break into fading streaks through 32. Fixed camera, one cut.",
    "4r": "nkmr_fx, A giant robot punches at 0-3. A white-yellow impact flash bursts at its fist at 4-6, orange sparks and gray debris scatter at 7-20, and dark smoke rises through 32. Mostly twos; fixed camera, one cut.",
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="/kaggle/working")
    ap.add_argument("--compare-only", help="시험용: 이 폴더의 영상으로 시트만")
    a = ap.parse_args()
    os.makedirs(W, exist_ok=True)
    if not a.compare_only:
        subprocess.run(["curl", "-sSL", "-o", f"{W}/kaggle_wan_eval_worker.py", f"{RAW}/kaggle_wan_eval_worker.py"], check=True)
    sys.path.insert(0, W if not a.compare_only else os.path.dirname(os.path.abspath(__file__)))
    import kaggle_wan_eval_worker as ev
    conds = ["base", "m0.6", "m0.8"]
    names = ["0", "1", "2", "3", "1v", "3v", "4r"]
    if a.compare_only:
        sheets(ev, a.compare_only, os.path.join(a.out, "compare3"), names, conds)
        return
    cap, ng, mt = ev.setup()
    sys.path.insert(0, W)
    import pc_wan_lora_run as pc
    prompts = {str(i): p for i, p in enumerate(pc.PROMPTS)}
    prompts.update(EXTRA)
    sd = os.path.join(W, "samples_v3")
    logdir = os.path.join(a.out, "logs3")
    os.makedirs(sd, exist_ok=True)
    os.makedirs(logdir, exist_ok=True)
    ev.set_t5_dtype(mt, "bfloat16")
    dit = os.path.join(W, "models", os.path.basename(ev.MODELS["dit_fp16"][0]))
    lora = pc.merge_ready(os.path.join(W, "lora", "nkmr_wan13.safetensors"), dit)
    items = [(f"{n}_s{s}", prompts[n], 1000 * (k + 1) + s) for k, n in enumerate(names) for s in SEEDS]  # 묶음 안에서 씨앗이 겹치지 않게
    half = len(items) // 2
    jobs = []
    for c in conds:
        for part, its in (("a", items[:half]), ("b", items[half:])):  # 조건마다 반씩 나눠 GPU 2장에 고르게
            jobs.append(dict(tag=c, part=part, mult=float(c[1:]) if c != "base" else None, neg=None, items=its, dit=dit,
                             lora=None if c == "base" else lora, mt=mt, sd=sd, logdir=logdir, cpu_noise=True))
    ev.say(f"평가 3판: 프롬프트 {len(names)} × 씨앗 {len(SEEDS)} × {conds} = {len(items) * len(conds)}개, GPU {ng}장")
    errs = ev.run_parallel(jobs, ng, threading.Lock())
    sheets(ev, sd, os.path.join(a.out, "compare3"), names, conds)
    zp = os.path.join(a.out, "wan_out_eval3.zip")
    with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(glob.glob(os.path.join(sd, "*.mp4"))):
            z.write(f, "samples3/" + os.path.basename(f))
        for d in ("compare3", "logs3"):
            for f in sorted(glob.glob(os.path.join(a.out, d, "*"))):
                z.write(f, os.path.relpath(f, a.out))
        z.writestr("prompts3.txt", "\n".join(f"{n}: {prompts[n]}" for n in names) + "\n")
    n = len(glob.glob(os.path.join(sd, "*.mp4")))
    ev.say(f"완료: 영상 {n}/{len(items) * len(conds)}개 → {zp}", "| 실패:" if errs else "", "; ".join(errs))
    if ev.shutil.which("rclone") and os.path.exists(os.path.expanduser("~/.config/rclone/rclone.conf")):
        r = subprocess.run(["rclone", "copy", zp, "gdrive:AI-sfa/02_분석자료/WanLoRA_평가/"], capture_output=True, text=True)
        ev.say("Drive 업로드:", "성공" if r.returncode == 0 else "실패 — Output 탭에서 받아 주세요")


def sheets(ev, sd, outdir, names, conds):
    """프롬프트마다 (1) 줄 = 조건×씨앗, 칸 = 장 0·8·16·24·32 시트 JPG (2) 3×3 나란히 재생 mp4(열 = 조건, 줄 = 씨앗)."""
    import cv2
    import numpy as np
    os.makedirs(outdir, exist_ok=True)
    tw, th = 256, 144

    def lab(img, s):
        img = cv2.resize(img, (tw, th))
        cv2.rectangle(img, (0, 0), (8 + 8 * len(s), 18), (0, 0, 0), -1)
        cv2.putText(img, s, (3, 13), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (255, 255, 255), 1, cv2.LINE_AA)
        return img

    for n in names:
        vids = {}
        for c in conds:
            for s in SEEDS:
                f = os.path.join(sd, f"p{n}_s{s}_{c}.mp4")
                if os.path.exists(f):
                    vids[(c, s)] = ev.frames(f)
        if not vids:
            continue
        rows = []
        for c in conds:
            for s in SEEDS:
                v = vids.get((c, s))
                if v:
                    rows.append(np.hstack([lab(v[min(k, len(v) - 1)].copy(), f"{c} s{s} f{k}" if k == 0 else f"f{k}") for k in (0, 8, 16, 24, 32)]))
        cv2.imwrite(os.path.join(outdir, f"p{n}_sheet.jpg"), np.vstack(rows), [cv2.IMWRITE_JPEG_QUALITY, 85])
        nf = max(len(v) for v in vids.values())
        vw = cv2.VideoWriter(os.path.join(outdir, f"p{n}_grid.mp4"), cv2.VideoWriter_fourcc(*"mp4v"), 24, (tw * len(conds), th * len(SEEDS)))
        for k in range(nf):
            grid = [[lab(vids[(c, s)][min(k, len(vids[(c, s)]) - 1)].copy(), f"{c} s{s}") if (c, s) in vids else np.zeros((th, tw, 3), np.uint8)
                     for c in conds] for s in SEEDS]
            vw.write(np.vstack([np.hstack(r) for r in grid]))
        vw.release()


if __name__ == "__main__":
    main()
