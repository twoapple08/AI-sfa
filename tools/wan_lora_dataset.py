#!/usr/bin/env python3
"""Wan2.1 영상 LoRA 학습 자료: 나카무라 컷(recut_shots.py) → 512×288 mp4 + 영어 캡션 + musubi-tuner dataset.toml (2026-10-27).

사용자 결정(10-27 저녁): SFA보다 먼저 나카무라 스타일 영상 AI. 인물 지우기 없이 인물 있는 컷도 쓴다(캡션에 인물을 적음).
- 고르기: 이펙트 있음, 17장 이상(Wan 학습 장수는 4N+1).
- 캡션: GPT 움직임 태깅 결과(--gpt jsonl의 caption_en)가 있으면 그것, 없으면 옛 클립 태그(gpt_LORA_TAGS)의 영어 낱말(lora_captions.caption).
- 24fps 그대로(source_fps 안 씀) — 2·3장 유지 리듬을 16fps로 솎으면 깨진다.
- 장 위치(10-27 밤 정정): 시트(shot_sheets.py)는 cv2 set(POS_FRAMES, a) 뒤 차례로 읽었고 GPT 장 번호는 그 시트 기준이다.
  예전엔 '탐색이 항상 a+1을 준다'고 보고 시트 k = a+1+k로 고정했으나 틀렸다(29컷 중 27컷은 a 그대로) → 컷마다 sheet_offset으로
  탐색 첫 장과 같은 차례 장을 찾아 맞춘다(sheet_offsets.csv). 원본을 처음부터 순서대로 읽어, GPT 태그가 있으면 시트 기준 그대로 맞추고
  GPT 컷 경계로 앞뒤 1–2장 옆 컷 조각을 자르며(가장 긴 컷 구간 묶음 유지), 태그가 없으면 원본 a..b(검출 컷 그대로)를 쓴다.
  GPT가 이펙트 없음으로 본 컷도 빼지 않고 넣는다(사용자 10-27: 애니메이션 스타일 전체가 목표, 옛 태그와 판정이 엇갈림) → no_effect_shots.csv에 기록.
- 조각(10-27 밤, 기본 --chunk 33): 예전 slide(17·33장 창, 12장 간격)는 창 1,213개 중 64%가 0번이 아닌 장에서 시작해 캡션 장 번호와 어긋났다.
  이제 컷을 17–33장(4N+1) 조각으로 고르게 나누고 caption_window.window_caption으로 조각 캡션을 만들며(조각 안 GPT 문장 + 구조 태그 교집합), 학습은 조각 통째(full, max_frames).
원본 그림이므로 결과는 Drive·scratch만(저장소에는 이 도구와 목록만).
사용: python tools/wan_lora_dataset.py <원본 폴더> <shots.csv> <out 폴더> [--gpt gpt_SHOT_MOTION.jsonl] [--size 512 288]
"""
import argparse
import csv
import json
import os
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lora_captions import caption  # noqa: E402
from caption_window import normalize, window_caption  # noqa: E402

TAGS = "data/style_kb/ai_results/gpt_LORA_TAGS_2026-10-25.csv"

TOML = """[general]
resolution = [{w}, {h}]
caption_extension = ".txt"
batch_size = 1
enable_bucket = false

[[datasets]]
video_directory = "{root}/video"
cache_directory = "{root}/cache"
{extract}
"""
SLIDE = 'target_frames = [17, 33]\nframe_extraction = "slide"\nframe_stride = 12'
FULL = 'frame_extraction = "full"\nmax_frames = {chunk}'


_CACHE = {}


def read_range(path, s0, s1, size):
    """처음부터 순서대로 읽어 [s0, s1] 장을 돌려준다(장 번호를 탐색이 아니라 차례 읽기로 고정). 같은 원본은 한 번만 읽는다."""
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


def sheet_offset(path, a, size):
    """시트(shot_sheets.py)는 cv2 set(POS_FRAMES, a) 뒤 차례로 읽었다. 그 첫 장이 처음부터 차례로 읽은 몇 번째 장인지(a+off) 컷마다 잰다.
    2026-10-27 밤 재확인: 29컷 중 27컷 off=0, 2컷 off=1 — 예전의 '항상 a+1' 보정이 틀려 대부분 1장 뒤로 밀려 있었다."""
    c = cv2.VideoCapture(path)
    c.set(cv2.CAP_PROP_POS_FRAMES, a)
    ok, f = c.read()
    if not ok:
        return 0, None
    f = cv2.resize(f, tuple(size), interpolation=cv2.INTER_AREA).astype(np.int16)
    seq = _CACHE[path]
    d = {o: float(np.abs(seq[a + o].astype(np.int16) - f).mean()) for o in (-1, 0, 1, 2) if 0 <= a + o < len(seq)}
    off = min(d, key=d.get)
    return off, d[off]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("shots")
    ap.add_argument("out")
    ap.add_argument("--gpt")
    ap.add_argument("--size", type=int, nargs=2, default=[512, 288])
    ap.add_argument("--min", type=int, default=17)
    ap.add_argument("--exclude", default="", help="쉼표로 뺄 컷 id(예: 움직임 없는 홀드 컷)")
    ap.add_argument("--window-captions", help="GPT가 쓴 조각 캡션 JSONL({shot,w0,w1,caption}, 시트 장 번호). 있으면 그 조각은 이것을 씀(tools/window_factsheet.py check로 검사한 것)")
    ap.add_argument("--chunk", type=int, default=33, help="컷을 17..이 값(4N+1)장 조각으로 나눠 조각마다 캡션 장 번호를 다시 매김(full 추출). 0이면 예전 slide")
    a = ap.parse_args()
    tags = {r["클립"]: r for r in csv.DictReader(open(TAGS, encoding="utf-8"))}
    gcap, gobj, wcap = {}, {}, {}
    if a.window_captions:
        for line in open(a.window_captions, encoding="utf-8"):
            if line.strip():
                d = json.loads(line)
                wcap[(d["shot"], d["w0"], d["w1"])] = d["caption"]
    if a.gpt and os.path.exists(a.gpt):
        for line in open(a.gpt, encoding="utf-8"):
            line = line.strip()
            if line.startswith("{"):
                d = json.loads(line)
                if d.get("caption_en"):
                    gcap[d["shot"]] = normalize(d["caption_en"])
                    gobj[d["shot"]] = d
    vd = os.path.join(a.out, "video")
    os.makedirs(vd, exist_ok=True)
    n = fr_total = ng = 0
    rows, no_fx, offs = [], [], []
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
        if g is not None:  # 시트 기준(원본 a+off+k, off는 컷마다 측정), 앞뒤 1–2장 옆 컷 조각 제거
            segs = [seg["frames"] for seg in g["segments"]]
            while len(segs) > 1 and segs[0][1] - segs[0][0] < 2:
                segs = segs[1:]
            while len(segs) > 1 and segs[-1][1] - segs[-1][0] < 2:
                segs = segs[:-1]
            k0, k1 = segs[0][0], segs[-1][1]
            path = os.path.join(a.src, s["원본"])
            read_range(path, 0, 0, a.size)  # 원본 차례 읽기 캐시
            off, err = sheet_offset(path, int(s["시작"]), a.size)
            offs.append((s["id"], off, round(err, 3) if err is not None else None))
            s0, s1 = int(s["시작"]) + off + k0, int(s["시작"]) + off + k1
        else:
            k0 = None
            s0, s1 = int(s["시작"]), int(s["끝"])
        if s1 - s0 + 1 < a.min:
            continue
        frames = read_range(os.path.join(a.src, s["원본"]), s0, s1, a.size)
        L = len(frames)
        if a.chunk:  # 조각: 고르게 나눠 각 4N+1장(17..chunk), 캡션 번호는 조각 기준
            m = -(-L // a.chunk)
            starts = [round(i * L / m) for i in range(m)] + [L]
            pieces = [(starts[i], (starts[i + 1] - starts[i] - 1) // 4 * 4 + 1) for i in range(m)]
        else:
            pieces = [(0, L)]
        for ci, (st, ln) in enumerate(pieces):
            if ln < a.min:
                continue
            name = s["id"] if len(pieces) == 1 and not a.chunk else f'{s["id"]}_c{ci}'
            c = cap
            if a.chunk and g is not None:
                c = wcap.get((s["id"], k0 + st, k0 + st + ln - 1)) or window_caption(g, cap, k0 + st, k0 + st + ln - 1)  # GPT 조각 캡션 우선, 없으면 구조 태그 기반
            vw = cv2.VideoWriter(os.path.join(vd, name + ".mp4"), cv2.VideoWriter_fourcc(*"mp4v"), 24.0, tuple(a.size))
            for f in frames[st:st + ln]:
                vw.write(f)
            vw.release()
            open(os.path.join(vd, name + ".txt"), "w", encoding="utf-8").write(c)
            rows.append((name, ln, "gpt_window" if (s["id"], (k0 or 0) + st, (k0 or 0) + st + ln - 1) in wcap else "gpt" if s["id"] in gcap else "old_tags", c))
            fr_total += ln
        n += 1
        ng += s["id"] in gcap
    ext = FULL.format(chunk=a.chunk) if a.chunk else SLIDE
    open(os.path.join(a.out, "dataset.toml"), "w", encoding="utf-8").write(TOML.format(w=a.size[0], h=a.size[1], root="DATA_ROOT", extract=ext))
    with open(os.path.join(a.out, "captions.csv"), "w", newline="", encoding="utf-8") as fh:
        csv.writer(fh).writerows([("shot", "frames", "caption_from", "caption")] + rows)
    with open(os.path.join(a.out, "no_effect_shots.csv"), "w", newline="", encoding="utf-8") as fh:
        csv.writer(fh).writerows([("shot", "old_tag_이펙트")] + no_fx)
    with open(os.path.join(a.out, "sheet_offsets.csv"), "w", newline="", encoding="utf-8") as fh:
        csv.writer(fh).writerows([("shot", "offset", "match_err")] + offs)
    import collections
    print(f"시트 위치 보정 off 분포 {dict(collections.Counter(o for _, o, _ in offs))}, 일치 오차 최대 {max((e for *_, e in offs if e is not None), default=0)}")
    print(f"GPT 이펙트 없음(포함함) {len(no_fx)}: {[x[0] for x in no_fx]}")
    print(f"컷 {n} 조각 {len(rows)} 장 {fr_total} | GPT 캡션 컷 {ng}, 옛 태그 캡션 컷 {n - ng} | {a.size[0]}x{a.size[1]} 24fps")


if __name__ == "__main__":
    main()
