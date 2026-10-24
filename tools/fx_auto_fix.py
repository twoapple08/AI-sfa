#!/usr/bin/env python3
"""이펙트 자동 마스크를 서버에서 고친다 — 창 없이 SAM 2 (2026-10-24, 사용자: "그냥 알아서 잘라").

fx_click_mask.py의 고치기 방식과 같은 계산을 클릭 대신 지시 파일로 한다.
지시 파일(JSON): {"<번호>": [물체, …], …}. 물체 하나 =
  {"op": "add"|"remove", "frame": 구간 안 장 순서(0부터), "pts": [[x%, y%], …], "neg": [[x%, y%], …], "box": [x0%, y0%, x1%, y1%]}
    — 그 장에서 점(·상자)으로 물체를 잡아 SAM 2가 구간 앞뒤로 따라간다. pts·box 중 하나는 있어야 한다.
  {"op": "color", "mode": "add"|"remove", "hue": [도, 도], "sat"/"val": 최소, "satmax"/"valmax": 최대(0–255), "box": [x0%, y0%, x1%, y1%], "frames": [첫, 끝]}
    — 색으로 고른다(빛 번짐·후광처럼 SAM 2가 물체와 한 덩어리로 잡는 것). hue는 0–360도, box·frames는 생략하면 전체.
  {"op": "full", "frames": [첫 장, 끝 장]} — 화면 전체가 이펙트인 장(전면 섬광·전면 집중선)은 그 장 전체를 마스크로.
  {"op": "clear", "frames": [첫 장, 끝 장]} — 그 장의 마스크를 비운다(이펙트가 없는 장).
  {"op": "auto_off"} — 자동 마스크를 버리고 지시한 물체만 쓴다.
좌표는 화면 비율(%)이라 장면 사진 크기와 무관하다. 최종 = (((자동 ∪ full) ∪ add) − remove) → color(적은 순서) → clear.
출력: `<출력 폴더>/<게시물>_<시작>_click.npz`(v3와 같은 키) → effect_clip_sfa.py --mask로 SFA.
사용: python tools/fx_auto_fix.py <click_frames 폴더> <v3 폴더> <지시.json> <출력 폴더> [--model large|base_plus|small] [--only 번호]
"""
import argparse
import glob
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fx_click_mask import MODELS, compose, load_auto, read_info  # noqa: E402


def run(pred, torch, d, auto_dir, objs, out_dir):
    import cv2
    info = read_info(d)
    frames = sorted(glob.glob(os.path.join(d, "*.jpg")))
    n = len(frames)
    H, W = cv2.imread(frames[0]).shape[:2]
    start = int(info["start"])
    name = f"{info['post_id']}_{start}"
    A = load_auto(auto_dir, name, start, n, H, W)
    if A is None or any(o["op"] == "auto_off" for o in objs):
        A = np.zeros((n, H, W), bool)
    for o in objs:  # 전체 = 바탕에 깐 뒤 SAM 2 빼기로 인물·땅을 도려낼 수 있게 먼저 적용
        if o["op"] == "full":
            a, b = o["frames"]
            A[max(0, a):min(n, b + 1)] = True
    seg = [o for o in objs if o["op"] in ("add", "remove")]
    oids = [2 * i + (0 if o["op"] == "add" else 1) for i, o in enumerate(seg)]  # compose: 짝수 = 더하기, 홀수 = 빼기
    masks = np.zeros((len(seg), n, H, W), bool)
    out = os.path.join(out_dir, f"{name}_click.npz")
    seg_done = False
    if seg and os.path.exists(out):  # SAM 2 물체 지시가 지난번과 같으면 그 결과를 다시 쓴다(색·전체 지시만 바꿀 때)
        z = np.load(out)
        old = [o for o in json.loads(str(z["det"])) if o["op"] in ("add", "remove")]
        if old == seg and z["obj_mask"].shape[0] == len(seg):
            masks = np.unpackbits(z["obj_mask"], axis=-1)[..., :W].astype(bool)
            seg_done = True
    if seg and not seg_done:
        # SAM 2 영상 예측기는 기억 특징을 bfloat16으로 저장해 CPU float32 계산과 자료형이 어긋난다(물체 2개 이상에서 오류).
        # CPU autocast는 매우 느려서, 서버 venv의 sam2_video_predictor.py에서 그 변환을 float32로 바꿔 쓴다.
        with torch.inference_mode(), torch.autocast("cuda", dtype=torch.bfloat16, enabled=torch.cuda.is_available()):
            state = pred.init_state(video_path=d)
            for o, oid in zip(seg, oids):
                pts = [[x * W / 100, y * H / 100] for x, y in o.get("pts", [])]
                labs = [1] * len(pts) + [0] * len(o.get("neg", []))
                pts += [[x * W / 100, y * H / 100] for x, y in o.get("neg", [])]
                kw = {}
                if pts:
                    kw["points"] = np.array(pts, np.float32)
                    kw["labels"] = np.array(labs, np.int32)
                if "box" in o:
                    x0, y0, x1, y1 = o["box"]
                    kw["box"] = np.array([x0 * W / 100, y0 * H / 100, x1 * W / 100, y1 * H / 100], np.float32)
                pred.add_new_points_or_box(inference_state=state, frame_idx=int(o["frame"]), obj_id=oid, **kw)
            for rev in (False, True):
                for fi, ids, logits in pred.propagate_in_video(state, reverse=rev):
                    for k, oid in enumerate(ids):
                        masks[oids.index(int(oid)), fi] = (logits[k, 0] > 0).cpu().numpy()
    union = np.stack([compose(A[fi], {oid: masks[j, fi] for j, oid in enumerate(oids)}) for fi in range(n)])
    for o in objs:
        if o["op"] != "color":
            continue
        a, b = o.get("frames", [0, n - 1])
        x0, y0, x1, y1 = o.get("box", [0, 0, 100, 100])
        h0, h1 = o["hue"]
        for fi in range(max(0, a), min(n, b + 1)):
            hsv = cv2.cvtColor(cv2.imread(frames[fi]), cv2.COLOR_BGR2HSV)
            hue = hsv[..., 0].astype(np.int32) * 2
            m = ((hue >= h0) & (hue <= h1)) if h0 <= h1 else ((hue >= h0) | (hue <= h1))
            m &= (hsv[..., 1] >= o.get("sat", 60)) & (hsv[..., 2] >= o.get("val", 60))
            m &= (hsv[..., 1] <= o.get("satmax", 255)) & (hsv[..., 2] <= o.get("valmax", 255))
            r = np.zeros_like(m)
            r[int(y0 * H / 100):int(y1 * H / 100), int(x0 * W / 100):int(x1 * W / 100)] = True
            m &= r
            if o.get("mode", "add") == "add":
                if not o.get("over_remove"):  # SAM 2 '빼기'(인물·물체)는 색으로 더한 것보다 우선(후광처럼 몸 위에 겹친 빛만 over_remove)
                    for j, oid in enumerate(oids):
                        if oid % 2 == 1:
                            m &= ~masks[j, fi]
                union[fi] |= m
            else:
                union[fi] &= ~m
    for o in objs:
        if o["op"] == "clear":
            a, b = o["frames"]
            union[max(0, a):min(n, b + 1)] = False
    np.savez_compressed(
        out, mask=np.packbits(union, axis=-1), shape=np.array([n, H, W]), frames=np.arange(start, start + n),
        obj_mask=np.packbits(masks, axis=-1), labels=np.array([f"{o['op']}{i + 1}" for i, o in enumerate(seg)] or ["auto"]),
        area=union.reshape(n, -1).mean(1).astype(np.float32), det=np.array(json.dumps(objs, ensure_ascii=False)))
    a = union.reshape(n, -1).mean(1) * 100
    print(f"{os.path.basename(d)}: 물체 {len(seg)} · 빈 장 {(a < 0.3).sum()}/{n} · 평균 면적 {a.mean():.1f}% → {out}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("frames_root")
    ap.add_argument("auto_dir")
    ap.add_argument("plan")
    ap.add_argument("out_dir")
    ap.add_argument("--model", default="large", choices=list(MODELS))
    ap.add_argument("--only")
    a = ap.parse_args()
    import torch
    from sam2.sam2_video_predictor import SAM2VideoPredictor
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    pred = SAM2VideoPredictor.from_pretrained(MODELS[a.model], device=dev)
    plan = json.load(open(a.plan, encoding="utf-8"))
    # GPT 지시 파일(docs/GPT-PROMPT-FX35-MASK-PLAN-2026-10-24.md)은 {"번호": {"확신", "설명", "지시": [...]}} 꼴
    plan = {k: (v["지시"] if isinstance(v, dict) else v) for k, v in plan.items()}
    only = set(a.only.split(",")) if a.only else None
    os.makedirs(a.out_dir, exist_ok=True)
    for d in sorted(x for x in glob.glob(os.path.join(a.frames_root, "*")) if os.path.isdir(x)):
        num = os.path.basename(d).split("_")[0]
        if num in plan and (not only or num in only):
            run(pred, torch, d, a.auto_dir, plan[num], a.out_dir)


if __name__ == "__main__":
    main()
