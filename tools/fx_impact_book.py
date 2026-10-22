#!/usr/bin/env python3
"""임팩트 프레임 플립북 v2: 임팩트 장면을 프레임마다 전체 층 분해(밑색 + 반투명 명암 + 선 획)해 생성기가 그대로 재생하게 한다.

사용: python tools/fx_impact_book.py <effects.txt(Q 장면 목록)> <영상 폴더> <출력 txt> [--only 이름,이름]
- 장면 목록은 이펙트 사전의 Q 장면(이름 post:start, 장수 n)을 그대로 쓴다(51개, 사람 판정 임팩트에서 뽑은 것).
- 이전 Q 플립북은 흑백 2단계 먹 윤곽이라 연필 해칭 결·옅은 연필선·색 포인트가 뭉개졌다(2026-10-22 점검).
  여기서는 tools/effect_layers.py decompose를 화면 전체에 돌려 해칭을 선 획(획별 굵기·색)으로, 연필 회색을 반투명 명암 층으로 담는다.
- 구멍은 자기 바깥 윤곽(parent)에 붙인다(fx_flipbook 형식은 구멍을 첫 윤곽에만 붙여 윤곽이 많은 층에서 어긋난다).
출력(Drive만, 다른 작가 그림 유래). 좌표는 화면 높이 1, 왼쪽 위 원점:
  B impact <출처 post:start> <프레임 수> <화면 폭/높이>
  F <층 수> <획 수>
  Y <B> <G> <R> <알파> <윤곽 수>
  C <구멍> <부모 윤곽 번호(층 안, 없으면 -1)> x0 y0 cx cy x1 y1 …
  S <B> <G> <R> <굵기(화면 높이 비율)> x0 y0 cx cy x1 y1
"""
import argparse
import glob
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from effect_layers import decompose  # noqa: E402
from effect_vectorize import read_frame  # noqa: E402
from fx_gen import load_scenes  # noqa: E402

H = 540


def fmt(v):
    return f"{v:.4f}".rstrip("0").rstrip(".")


def frame_lines(doc):
    layers = [L for L in doc["layers"] if L["shapes"]]
    strokes = [(seg, ln["color"]) for ln in doc["lines"] for seg in ln["segs"]]
    out = [f"F {len(layers)} {len(strokes)}"]
    for L in layers:
        out.append(f"Y {' '.join(str(int(round(x))) for x in L['color'][:3])} {fmt(L.get('alpha', 1.0))} {len(L['shapes'])}")
        idx = {sh.get("cid", i): i for i, sh in enumerate(L["shapes"])}
        for sh in L["shapes"]:
            par = idx.get(sh.get("parent", -1), -1) if sh["hole"] else -1
            out.append(f"C {int(sh['hole'])} {par} " + " ".join(fmt(x / H) for x in sh["segs"] for x in x[:6]))
    for seg, col in strokes:
        c = seg[7:10] if len(seg) >= 10 else col
        out.append(f"S {' '.join(str(int(round(x))) for x in c[:3])} {fmt(seg[6] / H)} " + " ".join(fmt(x / H) for x in seg[:6]))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("fx")
    ap.add_argument("videos")
    ap.add_argument("out")
    ap.add_argument("--only", default="")
    a = ap.parse_args()
    only = {x for x in a.only.split(",") if x}
    done = set()
    if os.path.exists(a.out):  # 이어 하기
        done = {l.split()[2] for l in open(a.out, encoding="utf-8") if l.startswith("B ")}
    for name, frs in load_scenes(a.fx):
        if (only and name not in only) or name in done:
            continue
        pid, start = name.split(":")
        v = glob.glob(os.path.join(a.videos, pid + "*.mp4"))
        if not v:
            print(name, "영상 없음", flush=True)
            continue
        t0, lines, W = time.time(), [], None
        for f in range(int(start), int(start) + len(frs)):
            img = read_frame(v[0], f, H)
            W = img.shape[1]
            doc, _ = decompose(img)
            lines += frame_lines(doc)
        with open(a.out, "a", encoding="utf-8") as fh:
            fh.write(f"B impact {name} {len(frs)} {fmt(W / H)}\n" + "\n".join(lines) + "\n")
        print(name, "장수", len(frs), "초", round(time.time() - t0), flush=True)


if __name__ == "__main__":
    main()
