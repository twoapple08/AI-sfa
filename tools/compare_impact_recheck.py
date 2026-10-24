#!/usr/bin/env python3
"""임팩트 최종본과 GPT 전체 재판정 비교 (2026-10-24, 사용자: "최종 기준으로 싹 한번 훑고 비교").

입력
- 최종본 목록: data/style_kb/impact_final_index_2026-10-24.csv (구간, 시작, 끝, 그린장목록)
- GPT 재판정: data/style_kb/ai_results/gpt_IMPACT_RECHECK_2026-10-24.csv (구간,프레임,판정,이유,확신,메모)
- 사용자 판정: data/style_kb/ai_results/user_IMPACT_overrides_2026-10-24.csv (살림·확인 = 남김, 뺌 = 뺌; 뒤 줄이 앞 줄을 덮음)
출력(표준 출력 요약 + CSV)
- 바뀌는 장: GPT 재판정을 따르면 지금 최종본에서 빠지거나 들어오는 장(사용자가 정한 장은 제외 — 사용자 결정 우선)
- 사용자와 다른 장: 사용자가 정한 장인데 GPT 재판정이 반대(정확도 근거)
- 판정 없는 구간: GPT가 빠뜨린 구간
사용: python tools/compare_impact_recheck.py [--out 비교.csv]
"""
import argparse
import csv
from collections import defaultdict

IDX = "data/style_kb/impact_final_index_2026-10-24.csv"
GPT = "data/style_kb/ai_results/gpt_IMPACT_RECHECK_2026-10-24.csv"
USER = "data/style_kb/ai_results/user_IMPACT_overrides_2026-10-24.csv"


def frames(s):
    s = s.strip().replace(" ", "")
    out = set()
    if s in ("", "-"):
        return out
    for part in s.split(","):
        a, b = (part.split("-") + [part])[:2]
        out |= set(range(int(a), int(b) + 1))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", default=IDX)
    ap.add_argument("--gpt", default=GPT)
    ap.add_argument("--user", default=USER)
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    sec = {}
    for r in csv.DictReader(open(a.index, encoding="utf-8")):
        sec[r["구간"]] = (int(r["시작"]), int(r["끝"]), {int(x) for x in r["그린장목록"].split()})
    user = defaultdict(dict)  # 구간 → {장: 남김/뺌}
    for r in csv.DictReader(open(a.user, encoding="utf-8-sig")):
        v = "남김" if r["판정"].strip() in ("살림", "확인") else "뺌"
        for f in frames(r["프레임"]):
            user[r["구간"].strip()][f] = v
    gcut, gkeep, glow, seen = defaultdict(set), defaultdict(set), defaultdict(set), set()
    for r in csv.DictReader(open(a.gpt, encoding="utf-8-sig")):
        s = r["구간"].strip()
        seen.add(s)
        fr = frames(r["프레임"])
        if r["판정"].strip() == "뺌":
            gcut[s] |= fr
        elif r["판정"].strip() == "살림":
            gkeep[s] |= fr
        if r.get("확신", "").strip() == "낮음":
            glow[s] |= fr
    rows, n_out, n_in, dis, agree = [], 0, 0, [], 0
    for s, (lo, hi, drawn) in sorted(sec.items()):
        u = user.get(s, {})
        for f in sorted(gcut[s] | gkeep[s]):
            if not lo <= f <= hi:
                continue
            want = "뺌" if f in gcut[s] else "남김"
            if f in u:  # 사용자가 정한 장: 비교만
                if u[f] != want:
                    dis.append((s, f, u[f], want))
                else:
                    agree += 1
                continue
            now = "남김" if f in drawn else "뺌"
            if now != want:
                rows.append({"구간": s, "프레임": f, "지금": now, "GPT재판정": want, "확신낮음": "예" if f in glow[s] else ""})
                n_out += want == "뺌"
                n_in += want == "남김"
    unseen = sorted(set(sec) - seen)
    print(f"구간 {len(sec)} · GPT 판정 있는 구간 {len(seen & set(sec))} · 판정 없는 구간 {len(unseen)}")
    print(f"바뀌는 장(사용자 결정 제외): 빠짐 {n_out} · 들어옴 {n_in} · 그중 확신 낮음 {sum(1 for r in rows if r['확신낮음'])}")
    print(f"사용자가 정한 장 비교: 같음 {agree} · 다름 {len(dis)}")
    for s, f, uv, gv in dis:
        print(f"  다름 {s} {f}: 사용자 {uv} / GPT {gv}")
    if unseen:
        print("판정 없는 구간:", " ".join(unseen))
    if a.out:
        with open(a.out, "w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=["구간", "프레임", "지금", "GPT재판정", "확신낮음"], lineterminator="\n")
            w.writeheader()
            w.writerows(rows)


if __name__ == "__main__":
    main()
