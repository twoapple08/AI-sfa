#!/usr/bin/env python3
"""인물 그림 → 부위 지도(머리카락·얼굴·눈·눈동자·속눈썹·입·선글라스·옷·배경) (2026-10-25).

사용자: "일반적인 그림처럼 머리카락, 눈, 눈동자, 속눈썹 등 레이어를 쪼개 봐". SFA 선을 부위 레이어로 나누려고 부위 지도를 만든다.
1. 큰 부위: Grounding DINO(글로 찾기) 상자 → SAM 2 마스크(인물 자르기 tools/lora_person_mask.py와 같은 모델).
2. 눈 안쪽: 눈 상자 안에서 색과 위치로 나눔 — 눈동자 = 채도 높은 원(구멍 메움), 속눈썹 = 눈 위쪽 절반의 진한 곳, 나머지 = 눈.
겹치면 작은(구체적인) 부위가 이긴다. 출력 npz: label(H,W uint8), names(번호 순 이름).
사용(samenv): python tools/part_masks.py <그림> <출력.npz> [--sheet 확인.jpg]
"""
import argparse

import cv2
import numpy as np
import torch
from PIL import Image
from sam2.sam2_image_predictor import SAM2ImagePredictor
from transformers import AutoModelForZeroShotObjectDetection, AutoProcessor

# (이름, 찾는 글, 여러 개 허용) — 뒤에 올수록 덮어씀(더 구체적)
PARTS = [("배경", None, False), ("옷", "clothes. coat. turtleneck sweater.", True), ("머리카락", "hair.", False),
         ("얼굴", "face.", False), ("선글라스", "sunglasses.", False), ("입", "mouth.", False), ("눈", "eye.", True)]
# 얼굴 위로 내려온 앞머리는 지도로는 가를 수 없다(흰 머리·흰 피부, 머리카락 마스크가 얼굴을 통째로 덮음).
# 선 단위로 effect_clip_sfa --parts가 고친다: 머리카락에서 시작해 얼굴로 들어온 선은 통째로 머리카락
EYE_SUB = ["눈동자", "속눈썹"]
NAMES = [p[0] for p in PARTS] + EYE_SUB


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("out")
    ap.add_argument("--sheet")
    ap.add_argument("--box-thr", type=float, default=0.3)
    ap.add_argument("--prompts", help="인물 대신 다른 부위(예: 폭발=explosion. fire.;로봇=robot. mecha.) — 뒤에 적을수록 위(덮어씀). 눈·옷 후처리 안 함")
    a = ap.parse_args()
    person = not a.prompts
    parts = PARTS if person else [("배경", None, False)] + [(kv.split("=", 1)[0], kv.split("=", 1)[1], True) for kv in a.prompts.split(";")]
    names = NAMES if person else [p[0] for p in parts]
    img = cv2.imread(a.image)
    H, W = img.shape[:2]
    pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    gid = "IDEA-Research/grounding-dino-base"
    proc = AutoProcessor.from_pretrained(gid)
    det = AutoModelForZeroShotObjectDetection.from_pretrained(gid).eval()
    sam = SAM2ImagePredictor.from_pretrained("facebook/sam2.1-hiera-small", device="cpu")
    sam.set_image(np.array(pil))
    label = np.zeros((H, W), np.uint8)
    eye_boxes, face_box = [], None
    for li, (name, text, multi) in enumerate(parts):
        if text is None:
            continue
        inp = proc(images=pil, text=text, return_tensors="pt")
        with torch.no_grad():
            o = det(**inp)
        r = proc.post_process_grounded_object_detection(o, inp.input_ids, box_threshold=a.box_thr, text_threshold=0.25,
                                                        target_sizes=[(H, W)])[0]
        boxes = r["boxes"].numpy()
        if len(boxes) == 0:
            print(name, "못 찾음")
            continue
        order = np.argsort(-r["scores"].numpy())
        boxes = boxes[order] if multi else boxes[order[:1]]
        if name == "눈":
            boxes = [b for b in boxes if (b[2] - b[0]) < W * 0.25][:2]  # 두 눈(얼굴 전체 상자 제외)
            eye_boxes = boxes
        if name == "얼굴":
            face_box = boxes[0]
        for b in boxes:
            m, _, _ = sam.predict(box=np.array(b), multimask_output=False)
            m = m[0] > 0
            if name == "눈":  # 눈은 상자 자체가 더 정확(SAM이 흰자만 잡기도 함)
                x0, y0, x1, y1 = (int(round(v)) for v in b)
                m = np.zeros((H, W), bool); m[y0:y1, x0:x1] = True
            label[m] = li
        print(name, len(boxes), "개")
    # 옷 상자가 그림 전체를 덮어 뒤쪽 노란 원 가장자리가 옷으로 잡혔다 → 턱보다 위의 옷은 배경으로
    if person and face_box is not None:
        top = int(face_box[3] * 0.97)
        label[:top][label[:top] == NAMES.index("옷")] = 0
    # 눈 안쪽: 눈동자(채도 높은 둥근 덩어리) / 속눈썹(눈 위쪽 절반의 진한 곳)
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    ie, ii, il = (NAMES.index("눈"), NAMES.index("눈동자"), NAMES.index("속눈썹")) if person else (0, 0, 0)
    for b in (eye_boxes if person else []):
        x0, y0, x1, y1 = (int(round(v)) for v in b)
        sub = np.zeros((H, W), np.uint8); sub[y0:y1, x0:x1] = 1
        iris = ((hsv[..., 1] > 70) & (hsv[..., 2] > 50) & (sub > 0)).astype(np.uint8)
        n, lab, st, _ = cv2.connectedComponentsWithStats(iris)
        if n > 1:
            k = 1 + int(np.argmax(st[1:, cv2.CC_STAT_AREA]))
            iris = (lab == k).astype(np.uint8)
            cs, _ = cv2.findContours(iris, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            hull = np.zeros_like(iris); cv2.drawContours(hull, [cv2.convexHull(np.vstack(cs))], -1, 1, -1)
            iris = cv2.dilate(hull, np.ones((5, 5), np.uint8))  # 둘레 선까지
            label[(iris > 0) & (label == ie)] = ii
            cy = int(np.mean(np.nonzero(iris)[0]))
        else:
            cy = (y0 + y1) // 2
        lash = (gray < 90) & (sub > 0) & (np.arange(H)[:, None] < cy) & (label == ie)
        label[cv2.dilate(lash.astype(np.uint8), np.ones((3, 3), np.uint8)) > 0 & (label == ie)] = il
    np.savez_compressed(a.out, label=label, names=np.array(names))
    print({n: int((label == i).sum()) for i, n in enumerate(names)})
    if a.sheet:
        rng = np.random.RandomState(3)
        pal = rng.randint(40, 255, (len(names), 3)).astype(np.uint8); pal[0] = 0
        cv2.imwrite(a.sheet, np.hstack([img, (img * 0.4 + pal[label] * 0.6).astype(np.uint8)]))


if __name__ == "__main__":
    main()
