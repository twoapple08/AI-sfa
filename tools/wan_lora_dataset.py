#!/usr/bin/env python3
"""Wan2.1 영상 LoRA 학습 자료: 나카무라 컷(recut_shots.py) → 512×288 mp4 + 영어 캡션 + musubi-tuner dataset.toml (2026-10-27).

사용자 결정(10-27 저녁): SFA보다 먼저 나카무라 스타일 영상 AI. 인물 지우기 없이 인물 있는 컷도 쓴다(캡션에 인물을 적음).
- 고르기: 이펙트 있음, 17장 이상(Wan 학습 장수는 4N+1).
- 캡션: GPT 움직임 태깅 결과(--gpt jsonl의 caption_en)가 있으면 그것, 없으면 옛 클립 태그(gpt_LORA_TAGS)의 영어 낱말(lora_captions.caption).
- 24fps 그대로(source_fps 안 씀) — 2·3장 유지 리듬을 16fps로 솎으면 깨진다.
- 장 위치(2026-10-27 확인): cv2 set(POS_FRAMES, a)는 a+1번째 장을 준다(1장 밀림). 시트(shot_sheets.py)와 GPT 장 번호는
  이 밀린 기준(시트 k = 원본 a+1+k)이다. 여기서는 원본을 처음부터 순서대로 읽어, GPT 태그가 있으면 시트 기준 그대로 맞추고
  GPT 컷 경계로 앞뒤 1–2장 옆 컷 조각을 자르며(가장 긴 컷 구간 묶음 유지), 태그가 없으면 원본 a..b(검출 컷 그대로)를 쓴다.
  GPT가 이펙트 없음으로 본 컷도 빼지 않고 넣는다(사용자 10-27: 애니메이션 스타일 전체가 목표, 옛 태그와 판정이 엇갈림) → no_effect_shots.csv에 기록.
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


_CACHE = {}


def read_range(path, s0, s1, size):
    """처음부터 순서대로 읽어 [s0, s1] 장을 돌려준다(cv2 탐색의 1장 밀림을 피함). 같은 원본은 한 번만 읽는다."""
    if path not in _CACHE:
        _CACHE.clear()
        c = cv2.VideoCapture(path)
        fr = []
        while True:
            ok, f = c.read()
            if not ok:
                break
            fr.append(cv2.resize(f, tuple(size), interpolation=cv2.INTER_AREA))  # 메모리: 학습 크기로 줄여 보관
        _CACHE[path] = fr
    return _CACHE[path][s0:s1 + 1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("shots")
    ap.add_argument("out")
    ap.add_argument("--gpt")
    ap.add_argument("--size", type=int, nargs=2, default=[512, 288])
    ap.add_argument("--min", type=int, default=17)
    ap.add_argument("--exclude", default="", help="쉼표로 뺄 컷 id(예: 움직임 없는 홀드 컷)")
    a = ap.parse_args()
    tags = {r["클립"]: r for r in csv.DictReader(open(TAGS, encoding="utf-8"))}
    gcap, gobj = {}, {}
    if a.gpt and os.path.exists(a.gpt):
        for line in open(a.gpt, encoding="utf-8"):
            line = line.strip()
            if line.startswith("{"):
                d = json.loads(line)
                if d.get("caption_en"):
                    gcap[d["shot"]] = d["caption_en"]
                    gobj[d["shot"]] = d
    vd = os.path.join(a.out, "video")
    os.makedirs(vd, exist_ok=True)
    n = fr_total = ng = 0
    rows, no_fx = [], []
    for s in csv.DictReader(open(a.shots, encoding="utf-8")):
        cl = [tags[c] for c in s["원래클립"].split(";")]
        L = int(s["장수"])
        if L < a.min or all(t["이펙트"] == "없음" for t in cl) or s["id"] in a.exclude.split(","):
            continue
        cap = gcap.get(s["id"])
        if not cap:
            cap = caption(cl[0], "yutaka_nakamura") + ", hand-drawn 2D anime effects animation"
        g = gobj.get(s["id"])
        if g is not None and not any(seg["targets"] for seg in g["segments"]):
            no_fx.append((s["id"], ";".join(t["이펙트"] for t in cl)))  # 넣되 기록(옛 태그와 판정 엇갈림 확인용)
        if g is not None:  # 시트 기준(원본 a+1+k), 앞뒤 1–2장 옆 컷 조각 제거
            segs = [seg["frames"] for seg in g["segments"]]
            while len(segs) > 1 and segs[0][1] - segs[0][0] < 2:
                segs = segs[1:]
            while len(segs) > 1 and segs[-1][1] - segs[-1][0] < 2:
                segs = segs[:-1]
            k0, k1 = segs[0][0], segs[-1][1]
            s0, s1 = int(s["시작"]) + 1 + k0, int(s["시작"]) + 1 + k1
        else:
            s0, s1 = int(s["시작"]), int(s["끝"])
        if s1 - s0 + 1 < a.min:
            continue
        frames = read_range(os.path.join(a.src, s["원본"]), s0, s1, a.size)
        vw = cv2.VideoWriter(os.path.join(vd, s["id"] + ".mp4"), cv2.VideoWriter_fourcc(*"mp4v"), 24.0, tuple(a.size))
        k = 0
        for f in frames:
            vw.write(f)
            k += 1
        vw.release()
        open(os.path.join(vd, s["id"] + ".txt"), "w", encoding="utf-8").write(cap)
        rows.append((s["id"], k, "gpt" if s["id"] in gcap else "old_tags", cap))
        n += 1
        ng += s["id"] in gcap
        fr_total += k
    open(os.path.join(a.out, "dataset.toml"), "w", encoding="utf-8").write(TOML.format(w=a.size[0], h=a.size[1], root="DATA_ROOT"))
    with open(os.path.join(a.out, "captions.csv"), "w", newline="", encoding="utf-8") as fh:
        csv.writer(fh).writerows([("shot", "frames", "caption_from", "caption")] + rows)
    with open(os.path.join(a.out, "no_effect_shots.csv"), "w", newline="", encoding="utf-8") as fh:
        csv.writer(fh).writerows([("shot", "old_tag_이펙트")] + no_fx)
    print(f"GPT 이펙트 없음(포함함) {len(no_fx)}: {[x[0] for x in no_fx]}")
    print(f"컷 {n} 장 {fr_total} | GPT 캡션 {ng}, 옛 태그 캡션 {n - ng} | {a.size[0]}x{a.size[1]} 24fps")


if __name__ == "__main__":
    main()
