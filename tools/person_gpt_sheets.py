"""GPT 인물 판정용 시트: 학습 조각마다 처음·가운데·끝 3장을 한 줄로, 시트 한 장에 36조각(3열 × 12줄) (2026-10-28).

검출 상자는 그리지 않는다(GPT 판정을 끌지 않도록). 시트는 학습 원본 장면이라 저장소에 넣지 않는다.
사용: python -I tools/person_gpt_sheets.py <조각 폴더> <조각 이름 목록.txt> <출력 폴더>
"""
import os
import sys

import cv2
import numpy as np

TW, TH, BAR = 200, 113, 22
COLS, ROWS = 3, 12


def tile(path, name):
    c = cv2.VideoCapture(path)
    n = int(c.get(cv2.CAP_PROP_FRAME_COUNT))
    fr = []
    for k in (0, n // 2, n - 1):
        c.set(cv2.CAP_PROP_POS_FRAMES, k)
        ok, im = c.read()
        fr.append(cv2.resize(im, (TW, TH)) if ok else np.zeros((TH, TW, 3), np.uint8))
    bar = np.full((BAR, TW * 3, 3), 255, np.uint8)
    cv2.putText(bar, name, (4, 17), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2, cv2.LINE_AA)
    t = np.vstack([bar, np.hstack(fr)])
    return cv2.copyMakeBorder(t, 0, 4, 0, 6, cv2.BORDER_CONSTANT, value=(40, 40, 40))


def main():
    vdir, lst, odir = sys.argv[1:4]
    names = [x.strip() for x in open(lst, encoding="utf-8") if x.strip()]
    os.makedirs(odir, exist_ok=True)
    per = COLS * ROWS
    for si in range(0, len(names), per):
        tiles = [tile(os.path.join(vdir, n + ".mp4"), n) for n in names[si:si + per]]
        while len(tiles) % COLS:
            tiles.append(np.zeros_like(tiles[0]))
        rows = [np.hstack(tiles[i:i + COLS]) for i in range(0, len(tiles), COLS)]
        cv2.imwrite(os.path.join(odir, f"person_sheet_{si // per + 1:02d}.jpg"), np.vstack(rows), [cv2.IMWRITE_JPEG_QUALITY, 85])
    print(f"{len(names)}조각 → 시트 {-(-len(names) // per)}장")


if __name__ == "__main__":
    main()
