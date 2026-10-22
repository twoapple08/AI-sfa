"""P3 이펙트 분리(Kaggle GPU): 나카무라 이펙트 구간에서 이펙트 영역만 오려 낸다(배경·인물 제외).

사용(노트북이 부른다): python kaggle_fx_worker.py <작업번호> <작업수> [--model large|tiny] [--device cuda|cpu] [--limit N]
1. 구간 목록: Drive `02_분석자료/이펙트_분리/_segments.csv`(post_id,start,end,tags — 자동 태그 explosion·smoke·debris 등 ≥ 0.35 구간 ±6프레임).
2. 구간 프레임을 높이 540으로 뽑아 jpg 폴더로 둔다.
3. Grounding DINO(글자 조건 검출)로 6프레임마다 '이펙트'(explosion, smoke, debris, dust cloud, fire, shockwave, sparks)와 'person' 상자를 찾는다.
4. SAM 2 영상 예측기에 상자를 그 프레임의 물체로 넣고 구간 전체로 퍼뜨린다(앞뒤 모두).
5. 프레임별 이펙트 마스크 = 이펙트 물체 합집합 − 사람 물체 합집합.
   상자 거르기: 화면 80% 이상 상자 버림, 사람은 점수 ≥ PERSON_T이고 이펙트 상자와 IoU ≤ 0.5인 것만(같은 덩어리를 둘 다로 잡는 일이 잦다).
출력: Drive `02_분석자료/이펙트_분리/<post_id>_<start>.npz` — mask[T,H,W](packbits), frames(원 영상 번호), labels(물체별 글자),
      obj_masks_area, det(검출 상자 목록). 원본 영상 유래라 Drive에만 둔다. 끝난 구간은 건너뛴다.
"""
import argparse
import csv
import io
import json
import os
import shutil
import subprocess
import sys
import time
import traceback

import cv2
import numpy as np

SRC = "gdrive:AI-sfa/01_원본영상/yutaka_nakamura_디지털"
OUT = "gdrive:AI-sfa/02_분석자료/이펙트_분리"
FX = ["explosion", "smoke", "debris", "dust cloud", "fire", "shockwave", "sparks"]
PROMPT = ". ".join(FX + ["person"]) + "."
H = 540
EVERY = 6
BOX_T, TEXT_T = 0.3, 0.25


def rc(*a):
    return subprocess.run(["rclone", *a], capture_output=True, text=True)


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def frames_to_dir(video, a, b, d):
    os.makedirs(d, exist_ok=True)
    cap = cv2.VideoCapture(video)
    cap.set(cv2.CAP_PROP_POS_FRAMES, a)
    n = 0
    for f in range(a, b + 1):
        ok, im = cap.read()
        if not ok:
            break
        im = cv2.resize(im, (round(im.shape[1] * H / im.shape[0]), H), interpolation=cv2.INTER_AREA)
        cv2.imwrite(os.path.join(d, f"{n:05d}.jpg"), im, [cv2.IMWRITE_JPEG_QUALITY, 95])
        n += 1
    return n


class Detector:
    def __init__(self, device, tiny=False):
        import torch
        from transformers import AutoModelForZeroShotObjectDetection, AutoProcessor
        mid = "IDEA-Research/grounding-dino-tiny" if tiny else "IDEA-Research/grounding-dino-base"
        self.proc = AutoProcessor.from_pretrained(mid)
        self.model = AutoModelForZeroShotObjectDetection.from_pretrained(mid).to(device).eval()
        self.device = device
        self.torch = torch

    def __call__(self, bgr):
        from PIL import Image
        img = Image.fromarray(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))
        inp = self.proc(images=img, text=PROMPT, return_tensors="pt").to(self.device)
        with self.torch.no_grad():
            out = self.model(**inp)
        try:  # transformers 판마다 인수 이름이 다르다
            r = self.proc.post_process_grounded_object_detection(out, inp.input_ids, threshold=BOX_T, text_threshold=TEXT_T,
                                                                 target_sizes=[img.size[::-1]])[0]
        except TypeError:
            r = self.proc.post_process_grounded_object_detection(out, inp.input_ids, box_threshold=BOX_T, text_threshold=TEXT_T,
                                                                 target_sizes=[img.size[::-1]])[0]
        labels = r.get("text_labels", r.get("labels"))
        return [(str(l), float(s), [float(v) for v in b]) for l, s, b in zip(labels, r["scores"].tolist(), r["boxes"].tolist())]


PERSON_T = 0.4


def box_area(b):
    return max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])


def iou(a, b):
    x0, y0, x1, y1 = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
    inter = max(0.0, x1 - x0) * max(0.0, y1 - y0)
    return inter / max(box_area(a) + box_area(b) - inter, 1e-6)


def is_fx(label):
    """사람이 아닌 검출은 모두 이펙트로 본다('dust cloud'가 'cloud'로 잘려 나오기도 한다)."""
    return "person" not in label


def run_segment(det, pred, video, a, b, tmp):
    d = os.path.join(tmp, "fr")
    shutil.rmtree(d, ignore_errors=True)
    n = frames_to_dir(video, a, b, d)
    if n == 0:
        return None
    dets = []
    W = cv2.imread(os.path.join(d, "00000.jpg")).shape[1]
    for i in range(0, n, EVERY):
        im = cv2.imread(os.path.join(d, f"{i:05d}.jpg"))
        found = [(l, s, b) for l, s, b in det(im) if box_area(b) < 0.8 * W * H]  # 화면 전체 상자는 버린다
        fxb = [b for l, s, b in found if is_fx(l)]
        for lab, sc, box in found:
            # 같은 덩어리를 'explosion'과 'person'으로 둘 다 잡는 일이 잦다(구름이 통째로 지워졌다) → 이펙트 우선
            if not is_fx(lab) and (sc < PERSON_T or any(iou(box, b) > 0.5 for b in fxb)):
                continue
            dets.append((i, lab, sc, box))
    mask = np.zeros((n, H, W), bool)
    labels = []
    if any(is_fx(l) for _, l, _, _ in dets):
        import torch
        # SAM 2 영상 예측기는 기억 특징을 bfloat16으로 저장한다(autocast 전제). 감싸지 않으면 dtype 오류
        with torch.inference_mode(), torch.autocast(pred.device.type, dtype=torch.bfloat16):
            st = pred.init_state(video_path=d, offload_video_to_cpu=True, offload_state_to_cpu=True)
            for k, (i, lab, sc, box) in enumerate(dets):
                pred.add_new_points_or_box(st, frame_idx=i, obj_id=k, box=np.array(box, np.float32))
                labels.append(lab)
            fxid = np.array([is_fx(l) for l in labels])
            seen = set()
            for rev in (False, True):  # 상자를 넣은 프레임 앞쪽으로도 퍼뜨린다
                for fi, ids, logits in pred.propagate_in_video(st, reverse=rev):
                    m = (logits[:, 0] > 0).cpu().numpy()
                    ids = np.asarray(ids)
                    sel = fxid[ids]
                    e = m[sel].any(0) if sel.any() else np.zeros((H, W), bool)
                    p = m[~sel].any(0) if (~sel).any() else np.zeros((H, W), bool)
                    v = e & ~p
                    mask[fi] = (mask[fi] | v) if fi in seen else v
                    seen.add(fi)
            pred.reset_state(st)
    return {"mask": np.packbits(mask, axis=-1), "shape": np.array(mask.shape), "frames": np.arange(a, a + n),
            "labels": np.array(labels), "area": mask.reshape(n, -1).mean(1).astype(np.float32),
            "det": np.array(json.dumps(dets))}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("wid", type=int)
    ap.add_argument("nw", type=int)
    ap.add_argument("--model", default="large")
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--segments", default="")
    a = ap.parse_args()
    tmp = f"/tmp/fx{a.wid}"
    os.makedirs(tmp, exist_ok=True)
    seg_csv = a.segments or os.path.join(tmp, "_segments.csv")
    if not a.segments:
        rc("copyto", f"{OUT}/_segments.csv", seg_csv)
    segs = list(csv.DictReader(open(seg_csv, encoding="utf-8")))
    done = set(rc("lsf", OUT).stdout.split())
    todo = [s for s in segs if f"{s['post_id']}_{s['start']}.npz" not in done][a.wid::a.nw]
    if a.limit:
        todo = todo[:a.limit]
    log("남은 구간", len(todo))
    from sam2.sam2_video_predictor import SAM2VideoPredictor
    pred = SAM2VideoPredictor.from_pretrained("facebook/sam2.1-hiera-" + ("tiny" if a.model == "tiny" else "large"),
                                              device=a.device)
    det = Detector(a.device, tiny=a.model == "tiny")
    vids = {os.path.basename(p).split("_")[0]: p for p in rc("lsf", "--files-only", "--include", "*.mp4", SRC).stdout.split()}
    cur = None
    t0 = time.time()
    for k, s in enumerate(todo):
        try:
            pid, st, en = s["post_id"], int(s["start"]), int(s["end"])
            if pid not in vids:
                log("영상 없음", pid)
                continue
            loc = os.path.join(tmp, "cur.mp4")
            if cur != pid:
                rc("copyto", f"{SRC}/{vids[pid]}", loc)
                cur = pid
            r = run_segment(det, pred, loc, st, en, tmp)
            if r is None:
                continue
            buf = io.BytesIO()
            np.savez_compressed(buf, **r)
            p = os.path.join(tmp, "out.npz")
            open(p, "wb").write(buf.getvalue())
            up = rc("copyto", p, f"{OUT}/{pid}_{st}.npz")
            if up.returncode:
                log("올리기 실패", up.stderr[-200:])
            log(k + 1, "/", len(todo), pid, st, en, "물체", len(r["labels"]), "이펙트 면적 평균", round(float(r["area"].mean()), 3),
                "누적", round((time.time() - t0) / 60, 1), "분")
        except Exception:
            traceback.print_exc()
    log("끝")


if __name__ == "__main__":
    main()
