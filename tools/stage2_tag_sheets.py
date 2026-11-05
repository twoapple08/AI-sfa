"""단계 2 태깅용 구간 시트: 구간마다 한 장(원본 | 스틱맨 겹침)을 STEP장 간격으로 줄지어 놓고, 각 칸에 구간 기준 장 번호와 초를 찍는다.

장 번호는 motion-ir의 장 번호(구간 0장 = summary start)와 같다. 시트의 k = 중간 표현의 k(10-27 시트 장 번호 1장 밀림 사고 재발 방지):
칸 그림은 cap.set(start + k)로 읽은 원본과 같은 k의 SFA 장이다(위 칸 원본·아래 칸 겹침이 같은 k).
사용: python tools/stage2_tag_sheets.py <작업 폴더> <출력 폴더> [--step 3]
원본 장면이 담긴 시트는 비공개(Drive). 저장소에 넣지 않는다.
"""
import json, os, sys
import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def crop169(im):
    h, w = im.shape[:2]; vh = int(w * 0.5625); y0 = (h - vh) // 2
    if y0 >= 0:
        return im[y0:y0 + vh]
    return cv2.copyMakeBorder(im, -y0, -y0, 0, 0, cv2.BORDER_CONSTANT)


def sheet(work, s, step=3, tw=256, th=144, cols=8):
    import motion_ir as M, sfa_render as R
    R.PARAMS.update(pad=0.0, thick_mul=tw / 1920)
    sf = M.load(f"{work}/out/{s['name']}.sfa"); F = sf.findall('Frame')
    cap = cv2.VideoCapture(f"{work}/video/{s['video']}.mp4")
    tiles = []
    for k in range(0, s['frames'], step):
        cap.set(cv2.CAP_PROP_POS_FRAMES, s['start'] + k); ok, im = cap.read()
        im = cv2.resize(crop169(im), (tw, th)) if ok else np.zeros((th, tw, 3), np.uint8)
        rd = cv2.cvtColor(R.render_frame(sf, F[k], tw, th)[..., :3].astype(np.uint8), cv2.COLOR_RGB2BGR)
        ov = cv2.addWeighted(im, 0.4, rd, 0.6, 0)
        t = np.vstack([im, ov])
        cv2.rectangle(t, (0, 0), (92, 16), (0, 0, 0), -1)
        cv2.putText(t, f'{k} ({k / 24:.2f}s)', (3, 12), 0, 0.4, (255, 255, 255), 1)
        tiles.append(t)
    while len(tiles) % cols: tiles.append(np.zeros_like(tiles[0]))
    rows = [np.hstack(tiles[i:i + cols]) for i in range(0, len(tiles), cols)]
    img = np.vstack(rows)
    head = np.zeros((26, img.shape[1], 3), np.uint8)
    cv2.putText(head, f"{s['name']}  {s['frames']} frames = {s['frames'] / 24:.2f}s  (top: original / bottom: stickman)", (6, 18), 0, 0.55, (255, 255, 255), 1)
    return np.vstack([head, img])


if __name__ == '__main__':
    work, out = sys.argv[1], sys.argv[2]
    step = int(sys.argv[sys.argv.index('--step') + 1]) if '--step' in sys.argv else 3
    os.makedirs(out, exist_ok=True)
    S = json.load(open(f'{work}/out/summary.json'))['segments']
    for s in S:
        cv2.imwrite(f"{out}/{s['name']}.jpg", sheet(work, s, step), [cv2.IMWRITE_JPEG_QUALITY, 85])
    print(len(S))
