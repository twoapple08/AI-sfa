#!/usr/bin/env python3
"""태그 색인: 흩어진 판정·태그 자료를 '태그 → 장면(자료, 구간)' 한 표로 묶고, 태그로 찾아 학습용 조각을 뽑는다.

사용:
  python tools/tag_index.py build                 → data/tag_index.csv (집계 메타데이터만, 원본 그림·영상 없음)
  python tools/tag_index.py tags                  → 태그별 장면 수(분류별)
  python tools/tag_index.py find <태그> [--animator 이름] [--min-weight 0.5] [--limit 30]
  python tools/tag_index.py extract <태그> <출력 폴더> --videos <영상 폴더>[,<폴더>…] [--pose <tracks 폴더>] [--pad 6]
      → 구간마다 영상 조각(mp4)과 목록 csv. 원본 유래라 저장소 밖(서버 임시·Drive)에만 둔다.
태그는 한글 기준 이름(예: 공격, 공격_킥, 임팩트_연필, 폭발)과 원래 영어 태그(explosions, impact_frames_pencil …)를 둘 다 받는다(ALIASES).

묶는 자료(출처 칸에 파일 이름):
- 동작: GPT 동작 판정 T02·T03·T04, Codex 그림 재확인 판정수정 39건 우선 적용(nian41·나카무라만 — 보충 애니메이터 몸동작은 AGENTS 규칙대로 뺀다)(data/style_kb/ai_results/gpt_T0*.csv) + 시트 목록(data/p1/action_sheets/T0*_목록.csv: post_id·시작·길이).
  '판단 불가'는 뺀다. 공격은 공격세부(킥·펀치·무기·던지기)를 '공격_킥'처럼 하위 태그로도 단다.
- 임팩트 프레임: 사용자·AI 판정(data/style_kb/judge_lists/impact_classify_2026-10-20.csv)의 '맞음' — 임팩트_실루엣/임팩트_단색섬광,
  연필 진하기 ≥ 1이면 임팩트_연필(가중 = 진하기/3). 학습 '제외'는 뺀다. 302394(비질란테)는 가중 0.3(AGENTS 기본 낮음).
- 이펙트 구간: Kaggle 분리 구간(data/p3/fx_segments_2026-10-22.csv, exclude 뺌).
- 태그 보정: data/style_kb/tag_overrides.csv(action=add, status confirmed).
- 모션캡처: data/mocap/mocap_index_2026-10-21.csv(자료 = cmu/amass/…, 클립 이름, 전체 길이).
- 원본 게시물 태그: data/catalog.csv(게시물 전체, 구간 없음 — 가중 0.3).
가중(weight): 사람 판정 1.0, AI 판정 0.8, 자동 규칙 0.5, 게시물 전체 태그 0.3(낮을수록 구간이 덜 정확).
"""
import argparse
import csv
import glob
import os
import subprocess
import sys
from collections import Counter

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
OUT = os.path.join(ROOT, "data", "tag_index.csv")
FIELDS = ["태그", "분류", "자료", "post_id", "애니메이터", "시작", "끝", "가중", "출처", "메모"]

# 한글 기준 태그 ↔ 원래 태그
ALIASES = {
    "폭발": ["explosion", "explosions"], "연기": ["smoke"], "불": ["fire"], "파편": ["debris", "rock"], "불티": ["sparks", "spark"],
    "먼지": ["dust"], "빔": ["beams"], "번개": ["lightning"], "스미어": ["smears"], "충격파": ["shockwave"],
    "임팩트": ["impact_frames"], "임팩트_연필": ["impact_frames_pencil"], "임팩트_디지털": ["impact_frames_digital"],
    "임팩트_부분": ["impact_frames_partial"], "흑백연출": ["bw_direction"], "유타폰큐브": ["yutapon_cubes"],
    "배경동화": ["background_animation"], "바람": ["wind"], "액체": ["liquid"],
    "연필질감참고": ["pencil_texture_reference"], "격투": ["fighting"], "연기연출": ["character_acting"], "달리기연출": ["running"], "이펙트전반": ["effects"],
}
REV = {v: k for k, vs in ALIASES.items() for v in vs}
NO_BODY = {"riooo", "optical-core", "yukina_kosaka"}


def norm(tag):
    return REV.get(tag, tag)


def codex_fixes():
    """Codex가 시트 그림을 다시 보고 고친 동작(메모의 '판정수정:<동작>') → {"gpt_T03:T03_011.jpg": 새 동작}."""
    import re
    p = os.path.join(ROOT, "data", "style_kb", "ai_results", "codex_action_captions_2026-10-23.csv")
    out = {}
    if os.path.exists(p):
        for r in csv.DictReader(open(p, encoding="utf-8-sig")):
            m = re.search(r"판정수정:\s*([^;,|]+)", r.get("메모") or "")
            if m:
                out[r["출처"]] = m.group(1).strip()
    return out


def rows_actions():
    out = []
    fixes = codex_fixes()
    for t, by in (("T02", "gpt_T02_2026-10-21"), ("T03", "gpt_T03_2026-10-22"), ("T04", "gpt_T04_2026-10-22")):
        lst = os.path.join(ROOT, "data", "p1", "action_sheets", f"{t}_목록.csv")
        lab = os.path.join(ROOT, "data", "style_kb", "ai_results", f"{by}.csv")
        if not (os.path.exists(lst) and os.path.exists(lab)):
            continue
        L = {r["시트"]: r for r in csv.DictReader(open(lst, encoding="utf-8-sig"))}
        for r in csv.DictReader(open(lab, encoding="utf-8-sig")):
            s = L.get(r["시트"])
            act = (r.get("동작") or "").strip()
            src = f"gpt_{t}:{r['시트']}"
            if src in fixes:  # Codex 그림 재확인 결과가 우선(공격이 아니게 바뀌면 공격세부도 버린다)
                act = fixes[src]
                if act != "공격":
                    r = dict(r, 공격세부="")
            if not s or not act or act in ("판단 불가", "뼈대 틀림"):
                continue
            if s["애니메이터"] in NO_BODY:  # 몸동작은 nian41·나카무라만(AGENTS: riooo·optical-core·yukina 몸동작은 세지 않음)
                continue
            a = int(s["시작프레임"]); b = a + int(s["길이"]) - 1
            base = dict(분류="동작", 자료="sakuga", post_id=s["post_id"], 애니메이터=s["애니메이터"], 시작=a, 끝=b, 가중=0.8,
                        출처=f"{by}:{r['시트']}", 메모=(r.get("메모") or "")[:60])
            out.append(dict(base, 태그=act))
            sub = (r.get("공격세부") or "").strip()
            if act == "공격" and sub:
                out.append(dict(base, 태그=f"공격_{sub}"))
    return out


def rows_impact():
    p = os.path.join(ROOT, "data", "style_kb", "judge_lists", "impact_classify_2026-10-20.csv")
    out = []
    for r in csv.DictReader(open(p, encoding="utf-8-sig")):
        v = r["verdict"]
        if not v.startswith("맞음") or r.get("training") == "제외":
            continue
        fr = (r["frames"] or r.get("orig_frames") or "").split(";")[0]
        a, _, b = fr.partition("-")
        if not a.isdigit():
            continue
        w = (1.0 if "사용자" in r.get("judged_by", "") or r.get("judged_by") == "육안" else 0.8)
        if r["post_id"] == "302394":
            w = 0.3
        base = dict(분류="임팩트", 자료="sakuga", post_id=r["post_id"], 애니메이터=r["animator"], 시작=int(a), 끝=int(b or a),
                    출처="impact_classify_2026-10-20", 메모=(r.get("reason") or r.get("user_note") or "")[:60])
        out.append(dict(base, 태그="임팩트_실루엣" if "실루엣" in v else "임팩트_단색섬광", 가중=w))
        ps = r.get("pencil_strength") or "0"
        if ps.isdigit() and int(ps) >= 1:
            out.append(dict(base, 태그="임팩트_연필", 가중=round(w * int(ps) / 3, 2)))
        if (r.get("medium_note") or "").find("색") >= 0 or "포인트" in (r.get("user_note") or ""):
            out.append(dict(base, 태그="임팩트_색포인트", 가중=w))
    return out


def rows_fx():
    p = os.path.join(ROOT, "data", "p3", "fx_segments_2026-10-22.csv")
    out = []
    for r in csv.DictReader(open(p, encoding="utf-8-sig")):
        if r.get("exclude"):
            continue
        for t in r["tags"].split(";"):
            if t:
                out.append(dict(태그=norm(t), 분류="이펙트", 자료="sakuga", post_id=r["post_id"], 애니메이터="yutaka_nakamura",
                                시작=int(r["start"]), 끝=int(r["end"]), 가중=0.5, 출처="fx_segments_2026-10-22", 메모="자동 검출 구간"))
    return out


def rows_overrides():
    p = os.path.join(ROOT, "data", "style_kb", "tag_overrides.csv")
    out = []
    for r in csv.DictReader(open(p, encoding="utf-8-sig")):
        if r["action"] != "add" or r.get("status") not in ("confirmed", ""):
            continue
        for fr in (r["frames"] or "").split(";"):
            a, _, b = fr.strip().partition("-")
            if not a.isdigit():
                continue
            t = norm(r["tag"])
            out.append(dict(태그=t, 분류="임팩트" if t.startswith("임팩트") else "이펙트·연출", 자료="sakuga", post_id=r["post_id"],
                            애니메이터="", 시작=int(a), 끝=int(b or a), 가중=1.0 if "사용자" in (r.get("grade") or "") else 0.8,
                            출처="tag_overrides", 메모=(r.get("basis") or "")[:60]))
    return out


def rows_mocap():
    p = os.path.join(ROOT, "data", "mocap", "mocap_index_2026-10-21.csv")
    out = []
    for r in csv.DictReader(open(p, encoding="utf-8-sig")):
        for t in (r["태그"] or "").split(";"):
            if t:
                out.append(dict(태그=t, 분류="모션캡처", 자료=r["자료"], post_id=r["클립"], 애니메이터="", 시작=0,
                                끝=int(r["프레임"]) - 1, 가중=0.5, 출처="mocap_index_2026-10-21", 메모=(r["설명"] or "")[:60]))
    return out


def rows_catalog():
    p = os.path.join(ROOT, "data", "catalog.csv")
    out = []
    keep = set(REV) | {"fighting", "character_acting", "running", "effects", "impact_frames"}
    for r in csv.DictReader(open(p, encoding="utf-8-sig")):
        for t in (r["tags"] or "").split():
            if t in keep:
                out.append(dict(태그=norm(t), 분류="게시물태그", 자료="sakuga", post_id=r["post_id"], 애니메이터=r["artists"], 시작="",
                                끝="", 가중=0.3, 출처="catalog", 메모="게시물 전체(구간 없음)"))
    return out


def build():
    rows = rows_actions() + rows_impact() + rows_fx() + rows_overrides() + rows_mocap() + rows_catalog()
    with open(OUT, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    c = Counter(r["분류"] for r in rows)
    print("행", len(rows), dict(c), "→", os.path.relpath(OUT, ROOT))


def load():
    if not os.path.exists(OUT):
        build()
    return list(csv.DictReader(open(OUT, encoding="utf-8")))


def match(rows, tag, animator=None, min_w=0.0):
    want = {tag, norm(tag)} | set(ALIASES.get(tag, []))
    return [r for r in rows if (r["태그"] in want or r["태그"].startswith(tag + "_")) and
            (not animator or r["애니메이터"] == animator) and float(r["가중"]) >= min_w]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["build", "tags", "find", "extract"])
    ap.add_argument("tag", nargs="?")
    ap.add_argument("out", nargs="?")
    ap.add_argument("--animator")
    ap.add_argument("--min-weight", type=float, default=0.0)
    ap.add_argument("--limit", type=int, default=30)
    ap.add_argument("--videos", default="")
    ap.add_argument("--pad", type=int, default=6, help="구간 앞뒤로 더 자를 프레임")
    a = ap.parse_args()
    if a.cmd == "build":
        return build()
    rows = load()
    if a.cmd == "tags":
        c = Counter((r["분류"], r["태그"]) for r in rows)
        for (k, t), n in sorted(c.items(), key=lambda x: (x[0][0], -x[1])):
            print(f"{k}\t{t}\t{n}")
        return
    sel = match(rows, a.tag, a.animator, a.min_weight)
    sel.sort(key=lambda r: -float(r["가중"]))
    if a.cmd == "find":
        print(f"'{a.tag}' {len(sel)}개 (자료별 {dict(Counter(r['자료'] for r in sel))})")
        for r in sel[:a.limit]:
            print(f"  {r['분류']}\t{r['태그']}\t{r['자료']}:{r['post_id']}\t{r['시작']}-{r['끝']}\t가중 {r['가중']}\t{r['애니메이터']}\t{r['메모']}")
        return
    # extract: 영상 조각(애니 자료만). 모션캡처는 목록만 쓴다(원본 파일 위치가 자료마다 다름)
    os.makedirs(a.out, exist_ok=True)
    dirs = [d for d in a.videos.split(",") if d]
    n = 0
    with open(os.path.join(a.out, "목록.csv"), "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS + ["파일"])
        w.writeheader()
        for r in sel:
            f = ""
            if r["자료"] == "sakuga" and r["시작"] != "":
                v = [p for d in dirs for p in glob.glob(os.path.join(d, r["post_id"] + "*.mp4"))]
                if v:
                    s0, e0 = max(0, int(r["시작"]) - a.pad), int(r["끝"]) + a.pad
                    f = f"{r['태그']}_{r['post_id']}_{s0}-{e0}.mp4"
                    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", v[0], "-vf",
                                    f"select='between(n\\,{s0}\\,{e0})',setpts=N/FRAME_RATE/TB", "-an",
                                    os.path.join(a.out, f)], check=False)
                    n += 1
            w.writerow(dict(r, 파일=f))
    print(f"'{a.tag}' {len(sel)}개 중 영상 조각 {n}개 → {a.out}")


if __name__ == "__main__":
    main()
