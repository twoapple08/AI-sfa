#!/usr/bin/env python3
"""이펙트 마스크 클릭 지정 도구 — 사용자 PC(GPU)에서 실행 (2026-10-24).

자동 마스크(Grounding DINO + SAM 2, Kaggle v3)는 불꽃을 놓치거나 연기 대신 인물·바위를 잡았다(이펙트 35 후보 시험 5개).
사람이 이펙트 위를 몇 번 클릭하면 SAM 2 영상 예측기가 그 물체만 오려 구간 끝까지(앞뒤로) 따라간다.

입력: 구간 폴더들이 든 폴더(Drive `02_분석자료/이펙트_클릭마스크/click_frames_35.zip`을 푼 `click_frames/`).
      구간 폴더 = `<번호>_<게시물>_<시작>/00000.jpg …` + `info.txt`(post_id, start, end, 종류).
출력: `<출력 폴더>/<게시물>_<시작>_click.npz` — 서버 도구(effect_clip_sfa.py --mask)가 읽는 v3와 같은 키
      (mask[T,H,W/8] packbits 합집합, frames = 원본 영상 장 번호, shape, obj_mask[물체,T,H,W/8], labels, area, det = 클릭 기록).

조작(창이 떠 있을 때)
  왼쪽 클릭  이펙트(이 부분을 잡아라)        오른쪽 클릭  아님(인물·바위·배경 — 빼라)
  A / D      앞 장 / 뒤 장 보기(이펙트가 잘 보이는 장에서 클릭)
  N          새 물체(떨어져 있는 다른 이펙트 덩어리 — 예: 불꽃 따로, 연기 따로)
  Z          마지막 클릭 취소(Ctrl+Z·백스페이스도)          R  이 구간 처음부터
  ※ 키보드를 영문 입력으로(한글 입력이면 Z가 'ㅋ'로 들어가 키가 먹지 않는다)
  Enter      확정 → 구간 전체로 따라가기 → 결과 미리 보기(아무 키: 저장, R: 다시)
  S          이 구간 건너뛰기(이펙트를 잡을 수 없음)          Q  끝내기(다음에 이어서 하면 끝난 구간은 건너뜀)
고치기 방식(--auto 자동 마스크 폴더): 자동 마스크가 먼저 깔린다. 왼쪽 클릭 = 놓친 이펙트 더하기, 오른쪽 클릭 = 잘못 잡힌 것 빼기,
  N = 다음 더하기/빼기 묶음, 클릭 없이 Enter = 자동 그대로 저장.
사용: python fx_click_mask.py <click_frames 폴더> <출력 폴더> [--auto <v3 폴더>] [--model large|base_plus|small] [--only 번호]
설치·순서: docs/PC-CLICK-MASK-GUIDE-2026-10-24.md
"""
import argparse
import glob
import json
import os
import sys

import cv2
import numpy as np

COLORS = [(0, 255, 255), (255, 0, 255), (0, 255, 0), (255, 128, 0), (0, 128, 255), (255, 255, 0)]
MODELS = {"large": "facebook/sam2.1-hiera-large", "base_plus": "facebook/sam2.1-hiera-base-plus",
          "small": "facebook/sam2.1-hiera-small"}


def read_info(d):
    info = {}
    for line in open(os.path.join(d, "info.txt"), encoding="utf-8"):
        if "=" in line:
            k, v = line.strip().split("=", 1)
            info[k] = v
    return info


def overlay(img, masks, clicks, cur_obj, idx, n, title, fix=False):
    out = img.copy()
    for oid, m in masks.items():
        if m is None:
            continue
        col = np.array(COLORS[oid % len(COLORS)], np.uint8)
        out[m] = (out[m] * 0.45 + col * 0.55).astype(np.uint8)
    for (oid, fi, x, y, lab) in clicks:
        if fi != idx:
            continue
        red = lab == 0 or (fix and oid % 2 == 1)  # 고치기 방식의 '뺄 것'도 빨간 점
        cv2.circle(out, (x, y), 6, (0, 0, 255) if red else (0, 255, 0), -1)
        cv2.circle(out, (x, y), 7, (0, 0, 0), 1)
    # 창 제목은 영어만(윈도에서 OpenCV 창 제목의 한글이 깨질 수 있다). 조작 설명은 안내서에 있다.
    bar = f"{title}  frame {idx + 1}/{n}  obj {cur_obj + 1}  L:effect R:not A/D:frame N:new obj Z:undo Enter:ok S:skip Q:quit"
    cv2.rectangle(out, (0, 0), (out.shape[1], 24), (0, 0, 0), -1)
    cv2.putText(out, f"frame {idx + 1}/{n}  obj {cur_obj + 1}  clicks {sum(1 for c in clicks if c[1] == idx)}",
                (6, 17), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
    return out, bar


def compose(auto_m, objs):
    """고치기 방식 합성: 자동 ∪ 더할 것(짝수 물체) − 뺄 것(홀수 물체)."""
    out = auto_m.copy()
    for oid, m in objs.items():
        if m is not None and oid % 2 == 0:
            out |= m
    for oid, m in objs.items():
        if m is not None and oid % 2 == 1:
            out &= ~m
    return out


def load_auto(auto_dir, name, start, n, H, W):
    """자동 마스크(Kaggle v3 `<게시물>_<시작>_v3.npz`)를 구간 장 순서로 [n,H,W] bool로. 없으면 None."""
    if not auto_dir:
        return None
    p = os.path.join(auto_dir, f"{name}_v3.npz")
    if not os.path.exists(p):
        return None
    z = np.load(p)
    M = np.unpackbits(z["mask"], axis=-1)[..., :W].astype(bool)
    A = np.zeros((n, H, W), bool)
    for i, f in enumerate(z["frames"]):
        k = int(f) - start
        if 0 <= k < n and M[i].shape[0] == H:
            A[k] = M[i]
    return A


def run_segment(pred, torch, d, out_dir, auto_dir=None):
    info = read_info(d)
    frames = sorted(glob.glob(os.path.join(d, "*.jpg")))
    n = len(frames)
    imgs = [cv2.imread(f) for f in frames]
    H, W = imgs[0].shape[:2]
    start = int(info["start"])
    name = f"{info['post_id']}_{start}"
    out_path = os.path.join(out_dir, f"{name}_click.npz")
    title = f"{info.get('번호', '')} {name}"
    A = load_auto(auto_dir, name, start, n, H, W)
    # 자동 마스크가 있으면 '고치기' 방식: 왼쪽 클릭 = 더할 것(놓친 이펙트), 오른쪽 클릭 = 뺄 것(잘못 잡힌 인물·바위).
    # 클릭한 물체를 SAM 2가 구간 전체로 따라가고, 최종 = (자동 ∪ 더할 것) − 뺄 것. 클릭 없이 Enter면 자동 그대로 저장.
    win = "fx_click_mask"
    cv2.namedWindow(win, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(win, min(W, 1280), min(H, 720) + 24)

    with torch.inference_mode(), torch.autocast("cuda", dtype=torch.bfloat16, enabled=torch.cuda.is_available()):
        state = pred.init_state(video_path=d)
        clicks = []  # (물체, 장, x, y, 1=이펙트/0=아님)
        cur_obj, idx = 0, 0
        shown = {}  # 장 → {물체: 마스크}

        def replay():
            pred.reset_state(state)
            shown.clear()
            groups = {}
            for (oid, fi, x, y, lab) in clicks:
                groups.setdefault((oid, fi), []).append((x, y, lab))
            for (oid, fi), pts in groups.items():
                _, ids, logits = pred.add_new_points_or_box(
                    inference_state=state, frame_idx=fi, obj_id=oid,
                    points=np.array([[p[0], p[1]] for p in pts], np.float32),
                    labels=np.array([p[2] for p in pts], np.int32))
                shown[fi] = {int(i): (logits[k, 0] > 0).cpu().numpy() for k, i in enumerate(ids)}

        def on_mouse(ev, x, y, flags, param):
            if ev in (cv2.EVENT_LBUTTONDOWN, cv2.EVENT_RBUTTONDOWN):
                if A is not None:  # 고치기: 짝수 물체 = 더할 것, 홀수 물체 = 뺄 것(둘 다 그 물체를 잡는 양성 점)
                    oid = cur_obj * 2 + (0 if ev == cv2.EVENT_LBUTTONDOWN else 1)
                    clicks.append((oid, idx, int(x), int(y), 1))
                else:
                    clicks.append((cur_obj, idx, int(x), int(y), 1 if ev == cv2.EVENT_LBUTTONDOWN else 0))
                replay()

        cv2.setMouseCallback(win, on_mouse)
        while True:
            if A is not None:
                img, bar = overlay(imgs[idx], {0: compose(A[idx], shown.get(idx, {}))}, clicks, cur_obj, idx, n, title, True)
                bar = bar.replace("L:effect R:not", "AUTO+fix L:add R:remove")
            else:
                img, bar = overlay(imgs[idx], shown.get(idx, {}), clicks, cur_obj, idx, n, title)
            cv2.setWindowTitle(win, bar)
            cv2.imshow(win, img)
            k = cv2.waitKey(30) & 0xFF
            if k in (ord("a"), ord("A")):
                idx = max(0, idx - 1)
            elif k in (ord("d"), ord("D")):
                idx = min(n - 1, idx + 1)
            elif k in (ord("n"), ord("N")):
                cur_obj += 1
            elif k in (ord("z"), ord("Z"), 26, 8) and clicks:  # Z, Ctrl+Z(26), 백스페이스(8)
                clicks.pop()
                replay()
            elif k in (ord("r"), ord("R")):
                clicks.clear()
                cur_obj = 0
                replay()
            elif k in (ord("s"), ord("S")):
                open(os.path.join(out_dir, f"{name}_skip.txt"), "w", encoding="utf-8").write("건너뜀\n")
                return "skip"
            elif k in (ord("q"), ord("Q")):
                return "quit"
            elif k in (13, 10) and (clicks or A is not None):
                # 구간 전체로 따라가기(앞으로 + 뒤로)
                objs = sorted({c[0] for c in clicks})
                masks = np.zeros((len(objs), n, H, W), bool)
                for rev in ((False, True) if clicks else ()):
                    for fi, ids, logits in pred.propagate_in_video(state, reverse=rev):
                        for kk, oid in enumerate(ids):
                            masks[objs.index(int(oid)), fi] = (logits[kk, 0] > 0).cpu().numpy()
                # 미리 보기: 결과를 한 바퀴 재생
                redo = False
                for fi in list(range(n)) * 2:
                    if A is not None:
                        pv, _ = overlay(imgs[fi], {0: compose(A[fi], {o: masks[j, fi] for j, o in enumerate(objs)})}, [], cur_obj, fi, n, title)
                    else:
                        pv, _ = overlay(imgs[fi], {o: masks[j, fi] for j, o in enumerate(objs)}, [], cur_obj, fi, n, title)
                    cv2.setWindowTitle(win, f"{title}  PREVIEW - any key: save / R: redo")
                    cv2.imshow(win, pv)
                    kk = cv2.waitKey(60) & 0xFF
                    if kk in (ord("r"), ord("R")):
                        redo = True
                        break
                    if kk != 255:
                        break
                if redo:
                    replay()
                    continue
                if A is not None:
                    union = np.stack([compose(A[fi], {o: masks[j, fi] for j, o in enumerate(objs)}) for fi in range(n)])
                else:
                    union = masks.any(0)
                np.savez_compressed(
                    out_path,
                    mask=np.packbits(union, axis=-1), shape=np.array([n, H, W]),
                    frames=np.arange(start, start + n), obj_mask=np.packbits(masks, axis=-1),
                    labels=np.array([(f"add{o // 2 + 1}" if o % 2 == 0 else f"remove{o // 2 + 1}") if A is not None else f"click_obj{o + 1}" for o in objs] or ["auto"]), area=union.reshape(n, -1).mean(1).astype(np.float32),
                    det=np.array(json.dumps([{"obj": c[0], "frame": c[1] + start, "x": c[2], "y": c[3], "label": c[4]} for c in clicks])))
                print(f"저장: {out_path}  (물체 {len(objs)}, 평균 면적 {union.mean() * 100:.1f}%)")
                return "done"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("frames_root")
    ap.add_argument("out_dir")
    ap.add_argument("--model", default="large", choices=list(MODELS))
    ap.add_argument("--only", help="이 번호 구간만(예: 001,008)")
    ap.add_argument("--auto", help="자동 마스크(v3 npz) 폴더 — 주면 자동 마스크 위에서 고치기 방식")
    a = ap.parse_args()
    import torch
    from sam2.sam2_video_predictor import SAM2VideoPredictor
    if not torch.cuda.is_available():
        print("경고: GPU(cuda)를 찾지 못했다 — 매우 느리다. 안내서의 PyTorch 설치(cu124)를 확인할 것.")
    pred = SAM2VideoPredictor.from_pretrained(MODELS[a.model], device="cuda" if torch.cuda.is_available() else "cpu")
    os.makedirs(a.out_dir, exist_ok=True)
    only = set(a.only.split(",")) if a.only else None
    segs = sorted(d for d in glob.glob(os.path.join(a.frames_root, "*")) if os.path.isdir(d))
    for d in segs:
        num = os.path.basename(d).split("_")[0]
        if only and num not in only:
            continue
        info = read_info(d)
        base = f"{info['post_id']}_{info['start']}"
        if os.path.exists(os.path.join(a.out_dir, f"{base}_click.npz")) or os.path.exists(os.path.join(a.out_dir, f"{base}_skip.txt")):
            continue
        print(f"구간 {os.path.basename(d)} ({info.get('종류', '')})")
        if run_segment(pred, torch, d, a.out_dir, a.auto) == "quit":
            break
    cv2.destroyAllWindows()
    done = len(glob.glob(os.path.join(a.out_dir, "*_click.npz")))
    print(f"끝난 구간 {done}개 — 출력 폴더를 Drive `AI-sfa/02_분석자료/이펙트_클릭마스크/결과/`에 올려 주세요.")


if __name__ == "__main__":
    sys.exit(main())
