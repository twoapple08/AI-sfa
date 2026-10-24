#!/usr/bin/env python3
"""임팩트 장별 판정(GPT·사람 CSV)을 반영해 SFA를 다시 만든다 (2026-10-24).

판정 CSV(docs/GPT-PROMPT-IMPACT-REVIEW-2026-10-24.md): 구간,프레임,판정,이유,확신,메모
- 뺌 → `fx_glow_sfa.py --skip`, 살림 → `--keep`(메모에 갈색·금빛이 있으면 `--warm`도), 확인 → 바꾸지 않음.
- 확신 '낮음'은 반영하지 않고 사용자 확인 목록으로만 출력한다(기본, --apply-low로 반영).
묶음 목록(runs) 한 줄 = `<영상 파일명> <시작> <끝> <판정표 범위>`(서버 scratch의 batchN.txt 형식).
원본 영상·결과는 저장소 밖(서버 scratch·Drive)에만 둔다.
사용: python tools/apply_impact_review.py <판정.csv> <runs.txt> <영상 폴더> <출력 폴더> [--override 사용자.csv] [--compare] [--only-changed]
사용자 판정 파일: data/style_kb/ai_results/user_IMPACT_overrides_2026-10-24.csv
"""
import argparse
import csv
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def load_review(path):
    out = {}
    with open(path, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            sec = r["구간"].strip()
            d = out.setdefault(sec, {"뺌": [], "살림": [], "warm": [], "낮음": [], "seen": True})
            fr, verdict, conf = r["프레임"].strip(), r["판정"].strip(), r.get("확신", "").strip()
            if fr in ("", "-") or verdict == "확인":
                continue
            if conf == "낮음":
                d["낮음"].append((fr, verdict, r.get("이유", ""), r.get("메모", "")))
                continue
            if verdict in ("뺌", "살림"):
                d[verdict].append(fr.replace(" ", ""))
            if verdict == "살림" and any(w in r.get("메모", "") for w in ("갈색", "금빛")):
                d["warm"].append(fr.replace(" ", ""))  # 갈색·금빛 섬광은 노랑 화소를 지우지 않는다(--warm)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("review")
    ap.add_argument("runs")
    ap.add_argument("vid")
    ap.add_argument("out")
    ap.add_argument("--override", help="사용자 판정 CSV(같은 칸) — 같은 구간·프레임은 GPT 판정을 덮어쓴다")
    ap.add_argument("--apply-low", action="store_true", help="확신 낮음도 반영")
    ap.add_argument("--compare", action="store_true", help="비교 mp4도 다시 만든다")
    ap.add_argument("--only-changed", action="store_true", help="바뀐 구간만 다시 만든다")
    a = ap.parse_args()
    rev = load_review(a.review)
    if a.override:  # 사용자 판정: 같은 프레임 문자열의 GPT 판정(낮음 포함)을 지우고 사용자 것을 넣는다
        with open(a.override, encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                d = rev.setdefault(r["구간"].strip(), {"뺌": [], "살림": [], "warm": [], "낮음": []})
                fr, v = r["프레임"].strip().replace(" ", ""), r["판정"].strip()
                for k in ("뺌", "살림", "warm"):
                    d[k] = [x for x in d[k] if x != fr]
                d["낮음"] = [x for x in d["낮음"] if x[0].replace(" ", "") != fr]
                if v in ("뺌", "살림"):
                    d[v].append(fr)
                if v == "살림" and any(w in r.get("메모", "") for w in ("갈색", "금빛")):
                    d["warm"].append(fr)
    os.makedirs(a.out, exist_ok=True)
    unseen, low = [], []
    for line in open(a.runs, encoding="utf-8"):
        parts = line.split()
        if len(parts) < 4:
            continue
        f, s, e, only = parts[:4]
        sec = f"{f.split('_')[0]}_{s}"
        d = rev.get(sec)
        if d is None:
            unseen.append(sec)
            d = {"뺌": [], "살림": [], "warm": [], "낮음": []}
        if a.apply_low:
            for fr, v, _, _ in d["낮음"]:
                d[v].append(fr)
        else:
            low += [(sec, *x) for x in d["낮음"]]
        if a.only_changed and not d["뺌"] and not d["살림"]:
            continue
        sfa = os.path.join(a.out, f"imp_{sec}.sfa")
        cmd = [sys.executable, os.path.join(HERE, "fx_glow_sfa.py"), os.path.join(a.vid, f), s, e, sfa,
               "--black-key", "--auto-impact", "--only", only, *parts[4:]]
        if d["뺌"]:
            cmd += ["--skip", ",".join(d["뺌"])]
        if d["살림"]:
            cmd += ["--keep", ",".join(d["살림"])]
        if d.get("warm"):
            cmd += ["--warm", ",".join(d["warm"])]
        log = subprocess.run(cmd, capture_output=True, text=True)
        open(os.path.join(a.out, f"log_{sec}.txt"), "w", encoding="utf-8").write(log.stdout + log.stderr)
        if log.returncode:
            print(sec, "실패", log.stderr[-300:])
            continue
        drawn = [ln.split()[0] for ln in log.stdout.splitlines() if " {" in ln]
        print(sec, "뺌", ",".join(d["뺌"]) or "-", "살림", ",".join(d["살림"]) or "-", "그린 장", len(drawn))
        if a.compare:
            subprocess.run([sys.executable, os.path.join(HERE, "fx_compare_video.py"), os.path.join(a.vid, f), sfa,
                            os.path.join(a.out, f"임팩트_{sec}.mp4"), "--start", s], capture_output=True)
    if unseen:
        print("판정 없는 구간(GPT가 빠뜨림):", " ".join(unseen))
    if low:
        print("확신 낮음(사용자 확인):")
        for x in low:
            print(" ", *x)


if __name__ == "__main__":
    main()
