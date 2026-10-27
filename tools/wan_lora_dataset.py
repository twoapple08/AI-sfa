#!/usr/bin/env python3
"""Wan2.1 영상 LoRA 학습 자료: 나카무라 컷(recut_shots.py) → 512×288 mp4 + 영어 캡션 + musubi-tuner dataset.toml (2026-10-27).

사용자 결정(10-27 저녁): SFA보다 먼저 나카무라 스타일 영상 AI. 인물 지우기 없이 인물 있는 컷도 쓴다(캡션에 인물을 적음).
- 고르기: 이펙트 있음, 17장 이상(Wan 학습 장수는 4N+1).
- 캡션: GPT 움직임 태깅 결과(--gpt jsonl의 caption_en)가 있으면 그것, 없으면 옛 클립 태그(gpt_LORA_TAGS)의 영어 낱말(lora_captions.caption).
- 24fps 그대로(source_fps 안 씀) — 2·3장 유지 리듬을 16fps로 솎으면 깨진다.
원본 그림이므로 결과는 Drive·scratch만(저장소에는 이 도구와 목록만).
사용: python tools/wan_lora_dataset.py <원본 폴더> <shots.csv> <out 폴더> [--gpt gpt_SHOT_MOTION.jsonl] [--size 512 288]
"""
import argparse
import csv
import json
import os
import sys

import cv2

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lora_captions import caption  # noqa: E402

TAGS = "data/style_kb/ai_results/gpt_LORA_TAGS_2026-10-25.csv"

TOML = """[general]
resolution = [{w}, {h}]
caption_extension = ".txt"
batch_size = 1
enable_bucket = false

[[datasets]]
video_directory = "{root}/video"
cache_directory = "{root}/cache"
target_frames = [17, 33]
frame_extraction = "slide"
frame_stride = 12
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("shots")
    ap.add_argument("out")
    ap.add_argument("--gpt")
    ap.add_argument("--size", type=int, nargs=2, default=[512, 288])
    ap.add_argument("--min", type=int, default=17)
    a = ap.parse_args()
    tags = {r["클립"]: r for r in csv.DictReader(open(TAGS, encoding="utf-8"))}
    gcap = {}
    if a.gpt and os.path.exists(a.gpt):
        for line in open(a.gpt, encoding="utf-8"):
            line = line.strip()
            if line.startswith("{"):
                d = json.loads(line)
                if d.get("caption_en"):
                    gcap[d["shot"]] = d["caption_en"]
    vd = os.path.join(a.out, "video")
    os.makedirs(vd, exist_ok=True)
    n = fr_total = ng = 0
    rows = []
    for s in csv.DictReader(open(a.shots, encoding="utf-8")):
        cl = [tags[c] for c in s["원래클립"].split(";")]
        L = int(s["장수"])
        if L < a.min or all(t["이펙트"] == "없음" for t in cl):
            continue
        cap = gcap.get(s["id"])
        if cap:
            ng += 1
        else:
            cap = caption(cl[0], "yutaka_nakamura") + ", hand-drawn 2D anime effects animation"
        c = cv2.VideoCapture(os.path.join(a.src, s["원본"]))
        c.set(cv2.CAP_PROP_POS_FRAMES, int(s["시작"]))
        vw = cv2.VideoWriter(os.path.join(vd, s["id"] + ".mp4"), cv2.VideoWriter_fourcc(*"mp4v"), 24.0, tuple(a.size))
        k = 0
        for _ in range(L):
            ok, f = c.read()
            if not ok:
                break
            vw.write(cv2.resize(f, tuple(a.size), interpolation=cv2.INTER_AREA))
            k += 1
        vw.release()
        open(os.path.join(vd, s["id"] + ".txt"), "w", encoding="utf-8").write(cap)
        rows.append((s["id"], k, "gpt" if s["id"] in gcap else "old_tags", cap))
        n += 1
        fr_total += k
    open(os.path.join(a.out, "dataset.toml"), "w", encoding="utf-8").write(TOML.format(w=a.size[0], h=a.size[1], root="DATA_ROOT"))
    with open(os.path.join(a.out, "captions.csv"), "w", newline="", encoding="utf-8") as fh:
        csv.writer(fh).writerows([("shot", "frames", "caption_from", "caption")] + rows)
    print(f"컷 {n} 장 {fr_total} | GPT 캡션 {ng}, 옛 태그 캡션 {n - ng} | {a.size[0]}x{a.size[1]} 24fps")


if __name__ == "__main__":
    main()
