#!/usr/bin/env python3
"""LoRA 클립에서 인물만 찾아 빼는 마스크 (2026-10-25, 사용자: "이펙트를 자르기보다 인물만큼 빼는 게 깔끔").

이펙트는 경계가 흐려 오리기 어렵지만 사람은 윤곽이 뚜렷하다. 사람 분할 모델(YOLO 분할, 사람 종류만)로 장마다 인물 마스크를 만든다.
결과는 '인물 뺀 장면'(인물 자리 = 검정) 학습 예시와, 생성 결과에서 인물을 빼는 데 쓴다. 애니 인물은 실사보다 덜 잡힐 수 있어 시트로 확인한다.
출력: <출력>/<클립>.npz (mask[T,H,W/8] packbits, 인물=1) + --sheet 이면 확인 그림(인물 자리 빨강)
사용: python tools/lora_person_mask.py <클립 폴더> <출력 폴더> [--only c0001,c0002] [--model mix|gdino|florence|isnetis.onnx|yolo11l-seg.pt] [--conf 0.5] [--sheet 그림.jpg]
  --model mix = gdino(+--clean) 결과 + 애니 전용(--anime isnetis.onnx)으로 인물 안 구멍 메우기 — 권장
  --model gdino = 글로 찾기(Grounding DINO, conf = 상자 문턱 0.3 권장) + SAM 2 오리기
  --model *.onnx = 애니 캐릭터 전용(권장, conf = 마스크 문턱), 그 밖 = YOLO 사람 분할(conf = 검출 신뢰도)
"""
import argparse
import glob
import os

import cv2
import numpy as np


def fill_outline(m):
    """인물 덩어리를 닫고 속을 채운 영역 — 애니 전용 결과는 이 안에서만 더한다(얼굴 구멍은 메우고 손 옆 섬광은 안 더함)."""
    c = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((25, 25), np.uint8))
    cs, _ = cv2.findContours(c, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    o = np.zeros_like(m)
    cv2.drawContours(o, cs, -1, 1, -1)
    return o


def clean(M, min_part, persist):
    """작은 덩어리(화면 대비 min_part 미만)와 앞뒤 ±2장 어디에도 겹치는 게 없는 덩어리(한두 장에만 반짝 나타남)를 버린다."""
    T, H, W = M.shape
    out = np.zeros_like(M)
    for i in range(T):
        k, cc, st, _ = cv2.connectedComponentsWithStats(M[i], 8)
        near = np.zeros((H, W), np.uint8)
        for j in range(max(0, i - 2), min(T, i + 3)):
            if j != i:
                near |= M[j]
        for c in range(1, k):
            if st[c, cv2.CC_STAT_AREA] < min_part * H * W:
                continue
            part = cc == c
            if persist and T >= 3 and (near[part] > 0).mean() < 0.2:
                continue
            out[i][part] = 1
    return out


def ram():
    """이 프로그램이 쓰는 메모리(커밋, GB) — 클립마다 늘어나는지 보려고(psutil 없으면 빈칸)."""
    try:
        import psutil
        mi = psutil.Process().memory_info()
        return f"[메모리 {getattr(mi, 'private', mi.rss) / 1e9:.1f}GB]"
    except Exception:
        return ""


def free_mem():
    import gc
    gc.collect()
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:
        pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("clips")
    ap.add_argument("out")
    ap.add_argument("--only")
    ap.add_argument("--model", default="yolo11l-seg.pt")
    ap.add_argument("--conf", type=float, default=0.25)
    ap.add_argument("--grow", type=int, default=3, help="인물 마스크 넓히기(px) — 머리카락·옷 가장자리 잔여 줄이기")
    ap.add_argument("--sheet")
    ap.add_argument("--anime", default="isnetis.onnx", help="--model mix 때 애니 전용 모델 파일")
    ap.add_argument("--clean", action="store_true", help="작은 덩어리·한두 장에만 나타나는 덩어리 버리기")
    ap.add_argument("--min-part", type=float, default=0.005)
    ap.add_argument("--persist", type=int, default=1)
    ap.add_argument("--stage", choices=["all", "gdino", "anime"], default="all")
    ap.add_argument("--raw", help="--stage anime 때 gdino 단계 결과 폴더")
    ap.add_argument("--half", type=int, default=1, help="GPU 반정밀도(bf16) 1/0")
    ap.add_argument("--resume", action="store_true", help="이미 있는 결과 파일은 건너뜀")
    a = ap.parse_args()
    if a.model == "mix":  # 섞기(2026-10-25 사용자 "잘 적용된 부분만 모아서"): Grounding DINO 개선판 + 애니 전용으로 인물 안 구멍 메우기
        a.model, anime_path = "gdino", a.anime
    else:
        anime_path = None
    # 단계 나누기(2026-10-25 PC방: 한 프로그램에 GPU 모델 둘 + CPU 애니 모델을 함께 켜니 윈도 pagefile이 C에서 8GB 넘게 늘었다)
    #   --stage gdino: GPU 모델만 켜서 원본 마스크(--clean 반영, 넓히기 전)를 저장하고 끝낸다
    #   --stage anime: 그 결과(--raw 폴더)를 읽어 애니 모델로 인물 안 구멍을 메우고 넓혀 최종 저장(torch를 켜지 않는다)
    if a.stage == "gdino":
        anime_path = None
    elif a.stage == "anime":
        a.model = "none"
    if a.model == "gdino":  # 글로 사람 형체를 찾고(Grounding DINO) 상자 안을 SAM 2로 오린다 — 2026-10-25 도구 4종 비교에서 가장 나음
        import torch
        from transformers import AutoProcessor, AutoModelForZeroShotObjectDetection
        from sam2.sam2_image_predictor import SAM2ImagePredictor
        dev = "cuda" if torch.cuda.is_available() else "cpu"
        gid = "IDEA-Research/grounding-dino-base"
        proc = AutoProcessor.from_pretrained(gid)
        det = AutoModelForZeroShotObjectDetection.from_pretrained(gid).to(dev).eval()
        sam = SAM2ImagePredictor.from_pretrained("facebook/sam2.1-hiera-small", device=dev)
        PERSON = ("person", "character", "human silhouette", "humanoid robot")
        # 반대 낱말: 같은 덩어리를 이쪽으로 더 높게 보면 사람 상자를 버린다(연기 덩어리·섬광·파편을 사람으로 잡았다, c0200·c0100·c0720)
        NEG = ("smoke", "explosion", "flash of light", "debris", "fire", "dust cloud")
        prompt = ". ".join(PERSON + NEG) + "."

        def iou(p, q):
            x0, y0, x1, y1 = max(p[0], q[0]), max(p[1], q[1]), min(p[2], q[2]), min(p[3], q[3])
            inter = max(0, x1 - x0) * max(0, y1 - y0)
            return inter / max((p[2] - p[0]) * (p[3] - p[1]) + (q[2] - q[0]) * (q[3] - q[1]) - inter, 1e-6)

        half = a.half and dev == "cuda"

        def amp():  # 반정밀도(bf16): GPU 메모리와 윈도 예약 메모리를 줄인다
            return torch.autocast("cuda", dtype=torch.bfloat16, enabled=half)

        def segment(img):
            h, w = img.shape[:2]
            rgb = img[..., ::-1].copy()
            with torch.inference_mode(), amp():
                inp = proc(images=rgb, text=prompt, return_tensors="pt").to(dev)
                out = det(**inp)
                r = proc.post_process_grounded_object_detection(out, inp.input_ids, box_threshold=a.conf, text_threshold=a.conf,
                                                                target_sizes=[(h, w)])[0]
            dets = [(b.tolist(), float(s), str(l)) for b, s, l in zip(r["boxes"], r["scores"], r["labels"])]
            pos = [d for d in dets if any(x in d[2] for x in ("person", "character", "silhouette", "robot", "human"))]
            neg = [d for d in dets if d not in pos]
            boxes = []
            for b, s, _ in pos:
                if (b[2] - b[0]) * (b[3] - b[1]) >= 0.9 * h * w:  # 화면 전체 상자 = 장면 전체를 사람으로 본 것
                    continue
                if any(iou(b, nb) > 0.5 and ns >= s for nb, ns, _ in neg):
                    continue
                boxes.append(b)
            m = np.zeros((h, w), np.uint8)
            if not boxes:
                return m
            with torch.inference_mode(), amp():
                sam.set_image(rgb)
                ms, _, _ = sam.predict(box=np.array(boxes, np.float32), multimask_output=False)
            m = (np.asarray(ms, np.float32).reshape(-1, h, w) > 0).any(0).astype(np.uint8)
            hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
            # 손에 붙은 흰 섬광은 인물이 아니다(c0004). 단 인물 안에만 있는 흰 부분(얼굴·옷 밝은 면)은 남긴다(c0100 얼굴에 구멍)
            bright = ((hsv[..., 2] > 235) & (hsv[..., 1] < 40)).astype(np.uint8)
            kb, cb, sb, _ = cv2.connectedComponentsWithStats(bright, 8)
            for c in range(1, kb):
                part = cb == c
                if (m[part] == 0).mean() > 0.3:  # 인물 밖으로 크게 번진 흰 덩어리 = 섬광
                    m[part] = 0
            return m
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
    elif a.model == "none":
        segment = None
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
    anime = None
    if anime_path:
        import onnxruntime as ort
        asess = ort.InferenceSession(anime_path, providers=["CUDAExecutionProvider", "CPUExecutionProvider"])

        def anime(img):
            s = 1024
            h, w = img.shape[:2]
            r = s / max(h, w)
            nh, nw = int(h * r), int(w * r)
            x = np.zeros((s, s, 3), np.float32)
            ph, pw = (s - nh) // 2, (s - nw) // 2
            x[ph:ph + nh, pw:pw + nw] = cv2.resize(img[..., ::-1], (nw, nh)).astype(np.float32) / 255
            m = asess.run(None, {asess.get_inputs()[0].name: x.transpose(2, 0, 1)[None]})[0][0, 0]
            return (cv2.resize(m[ph:ph + nh, pw:pw + nw], (w, h)) > 0.5).astype(np.uint8)
    os.makedirs(a.out, exist_ok=True)
    only = set(a.only.split(",")) if a.only else None
    rows = []
    for p in sorted(glob.glob(os.path.join(a.clips, "c*.mp4"))):
        cid = os.path.splitext(os.path.basename(p))[0]
        if only and cid not in only:
            continue
        out_path = os.path.join(a.out, f"{cid}.npz")
        if a.resume and os.path.exists(out_path) and not a.sheet:  # 이어 하기: 끝난 클립은 건너뜀
            continue
        if a.stage == "anime" and not os.path.exists(os.path.join(a.raw, f"{cid}.npz")):
            continue
        cap = cv2.VideoCapture(p)
        frames = []
        while True:
            ok, x = cap.read()
            if not ok:
                break
            frames.append(x)
        H, W = frames[0].shape[:2]
        k = np.ones((2 * a.grow + 1, 2 * a.grow + 1), np.uint8)
        if a.stage == "anime":
            z = np.load(os.path.join(a.raw, f"{cid}.npz"))
            M = np.unpackbits(z["mask"], axis=-1)[..., :W].copy()
        else:
            M = np.zeros((len(frames), H, W), np.uint8)
            for i, f in enumerate(frames):
                M[i] = segment(f)
            if a.clean:
                M = clean(M, a.min_part, a.persist)
        if a.stage == "gdino":  # 원본 마스크만 저장(넓히기·구멍 메우기는 anime 단계에서)
            np.savez_compressed(out_path, mask=np.packbits(M, axis=-1), shape=np.array(M.shape))
            print(cid, "인물 면적", f"{M.mean() * 100:.1f}%", ram(), flush=True)
            free_mem()
            continue
        if anime is not None:
            for i, f in enumerate(frames):
                if not M[i].any():  # 사람이 안 잡힌 장은 메울 구멍도 없다(애니 모델은 CPU라 느려서 건너뜀)
                    continue
                am = anime(f)
                if am.mean() < 0.8:  # 화면 대부분 = 임팩트 프레임을 인물로 본 것
                    M[i] |= am & fill_outline(M[i])
        for i in range(len(M)):
            M[i] = cv2.dilate(M[i], k)
        np.savez_compressed(out_path, mask=np.packbits(M, axis=-1), shape=np.array(M.shape))
        print(cid, "인물 면적", f"{M.mean() * 100:.1f}%", ram(), flush=True)
        free_mem()
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
    if a.sheet and rows:  # JPG 높이 한계(65,535px) 때문에 50클립씩 나눠 저장: 그림.jpg, 그림_02.jpg …
        base, ext = os.path.splitext(a.sheet)
        for k in range(0, len(rows), 50):
            name = a.sheet if k == 0 else f"{base}_{k // 50 + 1:02d}{ext}"
            cv2.imwrite(name, np.vstack(rows[k:k + 50]), [cv2.IMWRITE_JPEG_QUALITY, 82])


if __name__ == "__main__":
    main()
