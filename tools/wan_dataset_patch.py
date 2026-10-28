#!/usr/bin/env python3
"""Wan LoRA 학습 자료(wanlora.zip) 고치기: 효과 없는 조각 빼기 + 인물·로봇 문장 덧붙이기 (2026-10-28, 사용자 결정 3번).

문제: 학습 캡션에 인물 낱말이 거의 없어(인물이 크게 나오는 109조각 중 4) `nkmr_fx`가 인물을 흡수 → 프롬프트에 없는 인물이 생김.
해결: GPT 인물 태그(docs/GPT-PROMPT-PERSON-TAGS-2026-10-28.md 형식 JSONL)를 정해진 영어 문장으로 바꿔 캡션 끝에 붙인다.
  로봇은 나카무라의 주요 소재라 지우지 않고 'giant robot'으로 따로 부를 수 있게 한다(10-28 사용자).
  unsure=true는 붙이지 않는다(틀린 문장이 섞이는 것보다 원래대로가 낫다).
사용: python tools/wan_dataset_patch.py wanlora.zip --exclude data/style_kb/wan_exclude_no_effect_2026-10-28.txt --tags person_tags.jsonl -o wanlora_v2.zip
"""
import argparse
import csv
import io
import json
import zipfile

NOUN = {"face": "character's face", "fist_arm": "character's fist", "body": "character", "several": "characters",
        "silhouette": "dark character silhouette", "creature": "creature", "robot": "giant robot", "robot_part": "giant robot's arm"}
CLOSE = {"face", "fist_arm", "robot_part"}


def person_sentence(t):
    """GPT 태그 한 줄 → 캡션 끝에 붙일 문장(없으면 '')."""
    if t.get("unsure") or t.get("person", "none") == "none" or t.get("kind") not in NOUN:
        return ""
    kind, size = t["kind"], t["person"]
    noun = NOUN[kind]
    plural = kind == "several"
    if size == "large" and kind in CLOSE:
        subj = f"A close-up of a {noun}"
        plural = False
    else:
        adj = {"small": "small, distant ", "large": "" if kind == "robot" else "large "}.get(size, "")  # 'large giant robot' 피함
        subj = f"{'Several' if plural else 'A'} {adj}{noun}"
    brief = "briefly " if t.get("frames") == "some" else ""
    link = t.get("fx_link", "none")
    if link == "emits":
        verb = f"{brief}{'emit' if plural else 'emits'} the effect"
    elif link == "hit":
        verb = f"{'are' if plural else 'is'} {brief}hit by the effect"
    elif link == "strike":
        verb = f"{brief}{'strike' if plural else 'strikes'} with the impact"
    else:
        verb = f"{'are' if plural else 'is'} {brief}visible"
    return f"{subj} {verb}."


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("zip")
    ap.add_argument("--exclude", required=True)
    ap.add_argument("--tags", required=True)
    ap.add_argument("-o", required=True)
    a = ap.parse_args()
    ex = {x.strip() for x in open(a.exclude, encoding="utf-8") if x.strip()}
    tags = {}
    for line in open(a.tags, encoding="utf-8"):
        line = line.strip()
        if line.startswith("{"):
            t = json.loads(line)
            tags[t["clip"]] = t
    zin = zipfile.ZipFile(a.zip)
    clips = sorted(n[len("video/"):-4] for n in zin.namelist() if n.startswith("video/") and n.endswith(".mp4"))
    keep = [c for c in clips if c not in ex]
    miss = [c for c in keep if c not in tags]
    extra = sorted(set(tags) - set(clips))
    if miss or extra:
        raise SystemExit(f"태그 빠짐 {len(miss)} {miss[:8]} / 자료에 없는 태그 {len(extra)} {extra[:8]}")
    new_cap, added, words = {}, {}, []
    for c in keep:
        cap = zin.read(f"video/{c}.txt").decode("utf-8").strip()
        s = person_sentence(tags[c])
        if s:
            cap = f"{cap} {s}"
            added[c] = s
        new_cap[c] = cap
        words.append(len(cap.split()))
    rows = list(csv.DictReader(io.StringIO(zin.read("captions.csv").decode("utf-8"))))
    with zipfile.ZipFile(a.o, "w", zipfile.ZIP_DEFLATED) as zo:
        for n in zin.namelist():
            if n.startswith("video/") and n != "video/":
                c = n[len("video/"):].rsplit(".", 1)[0]
                if c in ex:
                    continue
                if n.endswith(".txt"):
                    zo.writestr(n, new_cap[c] + "\n")
                    continue
                zo.writestr(zin.getinfo(n), zin.read(n))
            elif n == "captions.csv":
                buf = io.StringIO()
                w = csv.DictWriter(buf, fieldnames=list(rows[0].keys()), lineterminator="\n")
                w.writeheader()
                for r in rows:
                    if r["shot"] in ex:
                        continue
                    r["caption"] = new_cap[r["shot"]]
                    if r["shot"] in added:
                        r["caption_from"] += "+person"
                    w.writerow(r)
                zo.writestr(n, buf.getvalue())
            else:
                zo.writestr(zin.getinfo(n), zin.read(n))
    from collections import Counter
    kinds = Counter(tags[c]["kind"] for c in added)
    print(f"조각 {len(clips)} → {len(keep)}(제외 {len(clips) - len(keep)}), 인물 문장 {len(added)}개 {dict(kinds)}, "
          f"unsure로 건너뜀 {sum(1 for c in keep if tags[c].get('unsure') and tags[c].get('person') != 'none')}, 캡션 최대 {max(words)}단어 → {a.o}")


if __name__ == "__main__":
    main()
