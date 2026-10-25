#!/usr/bin/env python3
"""LoRA 클립에서 인물만 찾아 빼는 마스크 (2026-10-25, 사용자: "이펙트를 자르기보다 인물만큼 빼는 게 깔끔").

이펙트는 경계가 흐려 오리기 어렵지만 사람은 윤곽이 뚜렷하다. 사람 분할 모델(YOLO 분할, 사람 종류만)로 장마다 인물 마스크를 만든다.
결과는 '인물 뺀 장면'(인물 자리 = 검정) 학습 예시와, 생성 결과에서 인물을 빼는 데 쓴다. 애니 인물은 실사보다 덜 잡힐 수 있어 시트로 확인한다.
출력: <출력>/<클립>.npz (mask[T,H,W/8] packbits, 인물=1) + --sheet 이면 확인 그림(인물 자리 빨강)
사용: python tools/lora_person_mask.py <클립 폴더> <출력 폴더> [--only c0001,c0002] [--model gdino|florence|isnetis.onnx|yolo11l-seg.pt] [--conf 0.5] [--sheet 그림.jpg]
  --model gdino = 글로 찾기(Grounding DINO, conf = 상자 문턱 0.3 권장) + SAM 2 오리기
  --model *.onnx = 애니 캐릭터 전용(권장, conf = 마스크 문턱), 그 밖 = YOLO 사람 분할(conf = 검출 신뢰도)
"""
import argparse
import glob
import os

import cv2
import numpy as np


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("clips")
    ap.add_argument("out")
    ap.add_argument("--only")
    ap.add_argument("--model", default="yolo11l-seg.pt")
    ap.add_argument("--conf", type=float, default=0.25)
    ap.add_argument("--grow", type=int, default=3, help="인물 마스크 넓히기(px) — 머리카락·옷 가장자리 잔여 줄이기")
    ap.add_argument("--sheet")
    a = ap.parse_args()
    if a.model == "gdino":  # 글로 사람 형체를 찾고(Grounding DINO) 상자 안을 SAM 2로 오린다 — 2026-10-25 시험
        import torch
        from transformers import AutoProcessor, AutoModelForZeroShotObjectDetection
        from sam2.sam2_image_predictor import SAM2ImagePredictor
        gid = "IDEA-Research/grounding-dino-base"
        proc = AutoProcessor.from_pretrained(gid)
        det = AutoModelForZeroShotObjectDetection.from_pretrained(gid).eval()
        sam = SAM2ImagePredictor.from_pretrained("facebook/sam2.1-hiera-small", device="cpu")
        prompt = "person. character. human silhouette. humanoid robot."

        def segment(img):
            h, w = img.shape[:2]
            rgb = img[..., ::-1].copy()
            with torch.inference_mode():
                inp = proc(images=rgb, text=prompt, return_tensors="pt")
                out = det(**inp)
                r = proc.post_process_grounded_object_detection(out, inp.input_ids, box_threshold=a.conf, text_threshold=a.conf,
                                                                target_sizes=[(h, w)])[0]
            boxes = [b.tolist() for b in r["boxes"] if (b[2] - b[0]) * (b[3] - b[1]) < 0.9 * h * w]  # 화면 전체 상자 = 장면 전체를 사람으로 본 것
            m = np.zeros((h, w), np.uint8)
            if not boxes:
                return m
            with torch.inference_mode():
                sam.set_image(rgb)
                ms, _, _ = sam.predict(box=np.array(boxes, np.float32), multimask_output=False)
            ms = ms.reshape(-1, h, w)
            return (ms > 0).any(0).astype(np.uint8)
    elif a.model == "florence":  # Florence-2 글 지시 검출(사람 형체) + SAM 2 오리기 — 2026-10-25 비교 시험
        import torch
        from unittest.mock import patch
        from transformers import AutoModelForCausalLM, AutoProcessor
        from transformers.dynamic_module_utils import get_imports
        from sam2.sam2_image_predictor import SAM2ImagePredictor
        fid = "microsoft/Florence-2-large"

        def no_flash(path):  # CPU에는 flash_attn이 없다 — 원격 코드의 선택 의존성을 뺀다
            return [i for i in get_imports(path) if i != "flash_attn"]
        with patch("transformers.dynamic_module_utils.get_imports", no_flash):
            fm = AutoModelForCausalLM.from_pretrained(fid, trust_remote_code=True, attn_implementation="eager").eval()
            fp = AutoProcessor.from_pretrained(fid, trust_remote_code=True)
        sam = SAM2ImagePredictor.from_pretrained("facebook/sam2.1-hiera-small", device="cpu")

        def segment(img):
            h, w = img.shape[:2]
            rgb = img[..., ::-1].copy()
            boxes = []
            for q in ("person", "human silhouette", "robot"):
                task = "<OPEN_VOCABULARY_DETECTION>"
                with torch.inference_mode():
                    inp = fp(text=task + q, images=rgb, return_tensors="pt")
                    ids = fm.generate(input_ids=inp["input_ids"], pixel_values=inp["pixel_values"], max_new_tokens=256, num_beams=3)
                txt = fp.batch_decode(ids, skip_special_tokens=False)[0]
                r = fp.post_process_generation(txt, task=task, image_size=(w, h))[task]
                boxes += [b for b in r.get("bboxes", []) if (b[2] - b[0]) * (b[3] - b[1]) < 0.9 * h * w]
            m = np.zeros((h, w), np.uint8)
            if not boxes:
                return m
            with torch.inference_mode():
                sam.set_image(rgb)
                ms, _, _ = sam.predict(box=np.array(boxes, np.float32), multimask_output=False)
            return (ms.reshape(-1, h, w) > 0).any(0).astype(np.uint8)
    elif a.model.endswith(".onnx"):  # 애니 캐릭터 전용 분할(skytnt anime-segmentation, isnetis.onnx) — 2026-10-25 YOLO가 애니 인물을 놓쳐 교체
        import onnxruntime as ort
        sess = ort.InferenceSession(a.model, providers=["CPUExecutionProvider"])

        def segment(img):
            s = 1024
            h, w = img.shape[:2]
            r = s / max(h, w)
            nh, nw = int(h * r), int(w * r)
            x = np.zeros((s, s, 3), np.float32)
            ph, pw = (s - nh) // 2, (s - nw) // 2
            x[ph:ph + nh, pw:pw + nw] = cv2.resize(img[..., ::-1], (nw, nh)).astype(np.float32) / 255
            m = sess.run(None, {sess.get_inputs()[0].name: x.transpose(2, 0, 1)[None]})[0][0, 0]
            m = cv2.resize(m[ph:ph + nh, pw:pw + nw], (w, h))
            return (m > a.conf).astype(np.uint8)
    else:
        from ultralytics import YOLO
        model = YOLO(a.model)

        def segment(img):
            r = model.predict(img, classes=[0], conf=a.conf, retina_masks=True, verbose=False)[0]
            if r.masks is None:
                return np.zeros(img.shape[:2], np.uint8)
            m = (r.masks.data.cpu().numpy() > 0.5).any(0).astype(np.uint8)
            return cv2.resize(m, (img.shape[1], img.shape[0]), interpolation=cv2.INTER_NEAREST) if m.shape != img.shape[:2] else m
    os.makedirs(a.out, exist_ok=True)
    only = set(a.only.split(",")) if a.only else None
    rows = []
    for p in sorted(glob.glob(os.path.join(a.clips, "c*.mp4"))):
        cid = os.path.splitext(os.path.basename(p))[0]
        if only and cid not in only:
            continue
        cap = cv2.VideoCapture(p)
        frames = []
        while True:
            ok, x = cap.read()
            if not ok:
                break
            frames.append(x)
        H, W = frames[0].shape[:2]
        M = np.zeros((len(frames), H, W), np.uint8)
        k = np.ones((2 * a.grow + 1, 2 * a.grow + 1), np.uint8)
        for i, f in enumerate(frames):
            M[i] = cv2.dilate(segment(f), k)
        np.savez_compressed(os.path.join(a.out, f"{cid}.npz"), mask=np.packbits(M, axis=-1), shape=np.array(M.shape))
        print(cid, "인물 면적", f"{M.mean() * 100:.1f}%", flush=True)
        if a.sheet:
            pick = np.linspace(0, len(frames) - 1, 4).round().astype(int)
            th = []
            for j in pick:
                im = frames[j].copy()
                mm = M[j] > 0
                im[mm] = (im[mm] * 0.4 + np.array([0, 0, 255]) * 0.6).astype(np.uint8)
                th.append(cv2.resize(im, (240, 135)))
            bar = np.zeros((18, 960, 3), np.uint8)
            cv2.putText(bar, f"{cid}  person {M.mean() * 100:.1f}%", (4, 13), 0, 0.45, (255, 255, 255), 1)
            rows.append(np.vstack([bar, np.hstack(th)]))
    if a.sheet and rows:
        cv2.imwrite(a.sheet, np.vstack(rows), [cv2.IMWRITE_JPEG_QUALITY, 82])


if __name__ == "__main__":
    main()
