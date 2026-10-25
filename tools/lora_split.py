#!/usr/bin/env python3
"""이펙트 LoRA 학습 자료를 '컬러 이펙트'와 '임팩트 프레임' 둘로 나눈다 (2026-10-25 2차).

1차(한 LoRA, 1,032장)는 자료의 40%가 저채도(흑백 임팩트 프레임·회색 연기)라 '흰 심 주황 테'를 지시해도 회색으로 그렸다.
사용자: "나카무라의 강점 중 하나가 화려한 색감" → 임팩트 프레임과 일반 이펙트를 쪼갠다.
- 임팩트 쪽: 캡션에 impact frame / monochrome / inverted colors 가 있으면. 신호 낱말 *_fx → *_impact.
- 컬러 쪽: 나머지. 실제 채도(HSV S 평균)로 muted colors(<40) / vivid colors(>110) 태그를 신호 낱말 바로 뒤에 붙여
  옅은 장면이 기본값을 회색으로 끌지 않게 하고, 생성 때 vivid colors로 색을 끌어올릴 수 있게 한다.
- 인물 뺀 판(<클립>_np)은 원래 그림을 따라간다.
- 컬러 쪽 옅은 그림(muted)은 color_muted 폴더로 따로 둔다. 학습 설정에서 color는 2번, color_muted는 1번 보게 해 저채도 비중을 30% → 약 18%로 낮춘다.
사용: python tools/lora_split.py <캡션 폴더(jpg+txt)> <출력 폴더>  → <출력>/color, color_muted, impact
"""
import glob
import os
import shutil
import sys

import cv2

IMPACT = ("impact frame", "monochrome", "inverted colors")
MUTED, VIVID = 40, 110


def main():
    src, out = sys.argv[1], sys.argv[2]
    for d in ("color", "color_muted", "impact"):
        os.makedirs(os.path.join(out, d), exist_ok=True)
    n = {"color": 0, "color_muted": 0, "impact": 0, "vivid": 0}
    for t in sorted(glob.glob(os.path.join(src, "*.txt"))):
        cid = os.path.basename(t)[:-4]
        cap = open(t, encoding="utf-8").read().strip()
        base = cid[:-3] if cid.endswith("_np") else cid
        base_cap = open(os.path.join(src, base + ".txt"), encoding="utf-8").read()
        tags = [s.strip() for s in cap.split(",")]
        if any(w in base_cap for w in IMPACT):
            kind = "impact"
            tags[0] = tags[0].replace("_fx", "_impact")
        else:
            kind = "color"
            s = cv2.cvtColor(cv2.imread(os.path.join(src, base + ".jpg")), cv2.COLOR_BGR2HSV)[..., 1].mean()
            if s < MUTED:
                tags.insert(1, "muted colors")
                kind = "color_muted"
            elif s > VIVID:
                tags.insert(1, "vivid colors")
                n["vivid"] += 1
        d = os.path.join(out, kind)
        shutil.copy(os.path.join(src, cid + ".jpg"), os.path.join(d, cid + ".jpg"))
        open(os.path.join(d, cid + ".txt"), "w", encoding="utf-8").write(", ".join(tags))
        n[kind] += 1
    print(n)


if __name__ == "__main__":
    main()
