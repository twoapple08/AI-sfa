#!/usr/bin/env python3
"""GPT 한국어 태그(gpt_LORA_TAGS) → 이펙트 화풍 LoRA 학습 캡션(영어, 기본 모델이 아는 낱말) (2026-10-25).

기본 모델 Illustrious-XL v1.0은 애니 그림 태그(danbooru식 영어)로 학습됐다. 정해진 한국어 낱말을 같은 영어 낱말로 늘 똑같이 바꿔야
모델이 '나카무라식 그리기'를 신호 낱말(nkmr_fx, 다른 작가는 각자 낱말)에 모은다. 인물·배경·카메라도 태그로 남겨 화풍 신호에 섞이지 않게 한다.
출력: <출력 폴더>/<클립>.jpg(대표 장 복사) + <클립>.txt(캡션). 학습 프로그램(kohya sd-scripts)이 같은 이름의 txt를 캡션으로 읽는다.
--person <인물마스크 폴더>를 주면 인물 자리를 검게 칠한 '인물 뺀' 판(<클립>_np.jpg)도 만든다(캡션은 인물 태그 대신 no humans, black background area).
사용: python tools/lora_captions.py <대표장 폴더 keys> <출력 폴더> [--person <npz 폴더>] [--tags gpt_LORA_TAGS.csv]
"""
import argparse
import csv
import os
import shutil

import cv2
import numpy as np

TAGS = "data/style_kb/ai_results/gpt_LORA_TAGS_2026-10-25.csv"
INDEX = "data/style_kb/lora_clips_index_2026-10-25.csv"
TRIGGER = {"yutaka_nakamura": "nkmr_fx", "riooo": "riooo_fx", "optical-core": "opticore_fx", "yukina_kosaka": "yukina_fx"}

EN = {
    "종류": {"폭발": "explosion", "연기": "smoke", "먼지": "dust cloud", "섬광": "flash", "빛번짐": "light bloom", "후광": "glowing aura",
           "불": "fire", "불티": "embers", "파편": "debris", "충격파": "shockwave", "빔": "energy beam", "번개": "lightning",
           "집중선": "speed lines", "임팩트프레임": "impact frame", "물보라": "water splash", "잔상": "afterimage", "궤적선": "motion trail",
           "기타": ""},
    "단계": {"발생": "effect onset", "커짐": "expanding", "정점": "peak", "흩어짐": "dispersing", "소멸": "fading", "지속": "sustained"},
    "모양": {"방사형": "radial", "버섯형": "mushroom cloud", "기둥형": "pillar", "고리형": "ring", "덩어리": "billowing mass", "줄기": "streaks",
           "띠": "band", "점무리": "particles", "화면가득": "full screen effect", "한쪽에서퍼짐": "spreading from side"},
    "채색": {"흰심주황테": "white core orange rim", "흰심청색테": "white core blue rim", "흰심분홍테": "white core pink rim", "단색": "flat color",
           "층많음": "layered cel shading", "층적음": "simple cel shading", "그림자덩어리": "dark shadow shapes", "흑백": "monochrome",
           "반전": "inverted colors"},
    "선": {"테두리선있음": "outlined", "테두리선없음": "no outline", "뾰족한끝": "sharp tips", "둥근끝": "rounded tips", "거친붓질": "rough brush strokes"},
    "움직임": {"빠르게커짐": "rapid expansion", "천천히퍼짐": "slow spread", "투스(2장마다)": "", "쓰리스(3장마다)": "", "투스": "", "쓰리스": "",
             "흔들림": "shaking", "멈춤": "hold frame", "날아감": "flying", "회전": "spinning"},
    "비중": {"작음": "small effect", "중간": "", "큼": "large effect", "전면": "full screen effect"},
    "인물": {"없음": "no humans", "실루엣": "silhouette", "애니채색": "anime character", "사실적": "realistic person", "로봇·기계": "mecha"},
    "배경": {"없음": "simple background", "하늘": "sky", "도시": "city", "우주": "space", "실내": "indoors", "땅·암석": "rocky ground",
           "숲": "forest", "물": "water", "추상": "abstract background"},
    "카메라": {"클로즈업": "close-up", "중간": "", "원경": "wide shot", "올려봄": "from below", "내려봄": "from above", "흔들림": "camera shake"},
}


def words(field, val):
    out = []
    for t in val.split(";"):
        t = t.strip()
        if not t:
            continue
        e = EN[field].get(t)
        if e is None:
            raise SystemExit(f"모르는 낱말: {field}={t}")
        if e:
            out.append(e)
    return out


def caption(r, artist, no_person=False):
    tags = [TRIGGER.get(artist, "fx_other"), "anime screencap"]
    if r["이펙트"] in ("있음", "일부"):
        for f in ("종류", "모양", "채색", "선", "단계", "움직임", "비중"):
            tags += words(f, r[f])
    else:
        tags.append("no effect")
    if no_person:
        tags += ["no humans", "black area"]
    else:
        tags += words("인물", r["인물"])
    tags += words("배경", r["배경"]) + words("카메라", r["카메라"])
    seen, out = set(), []
    for t in tags:
        if t not in seen:
            seen.add(t)
            out.append(t)
    return ", ".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("keys")
    ap.add_argument("out")
    ap.add_argument("--person")
    ap.add_argument("--tags", default=TAGS)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    art = {r["클립"]: r["작가"] for r in csv.DictReader(open(INDEX, encoding="utf-8"))}
    n = npn = skip = 0
    for r in csv.DictReader(open(a.tags, encoding="utf-8-sig")):
        cid = r["클립"]
        if r.get("장면전환") == "있음" and r["이펙트"] == "없음":
            skip += 1
            continue
        src = os.path.join(a.keys, f"{cid}.jpg")
        if not os.path.exists(src):
            continue
        shutil.copy(src, os.path.join(a.out, f"{cid}.jpg"))
        open(os.path.join(a.out, f"{cid}.txt"), "w", encoding="utf-8").write(caption(r, art.get(cid, "")))
        n += 1
        # 흑백·반전·임팩트 프레임은 인물 자르기가 획·덩어리를 사람으로 잡는 일이 많아(2026-10-25 c0219) 인물 뺀 판을 만들지 않는다
        bw = any(x in r["채색"] for x in ("흑백", "반전")) or "임팩트프레임" in r["종류"]
        if a.person and r["인물"] not in ("없음", "") and not bw:
            p = os.path.join(a.person, f"{cid}.npz")
            if os.path.exists(p):  # 대표 장 = 클립 가운데 장(lora_clips.py)
                z = np.load(p)
                T, H, W = (int(v) for v in z["shape"])
                m = np.unpackbits(z["mask"][T // 2], axis=-1)[:, :W].astype(bool)
                if 0.005 < m.mean() < 0.7:
                    img = cv2.imread(src)
                    img[m] = 0
                    cv2.imwrite(os.path.join(a.out, f"{cid}_np.jpg"), img, [cv2.IMWRITE_JPEG_QUALITY, 92])
                    open(os.path.join(a.out, f"{cid}_np.txt"), "w", encoding="utf-8").write(caption(r, art.get(cid, ""), no_person=True))
                    npn += 1
    print("그림", n, "인물 뺀 판", npn, "제외(장면전환+이펙트 없음)", skip)


if __name__ == "__main__":
    main()
