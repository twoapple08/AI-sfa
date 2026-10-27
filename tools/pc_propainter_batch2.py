#!/usr/bin/env python3
"""PC방 5060 2일차: pc_propainter_batch.py와 같은 ProPainter 계산을 모델을 한 번만 올려 돈다 (2026-10-27).

1일차 배치는 클립(6–12장)마다 inference_propainter.py를 새로 띄워 torch import·CUDA 준비·모델 3개 로딩을 매번 했고,
쓰지 않는 masked_in.mp4·inpaint_out.mp4도 저장했다. 이 스크립트는 그 고정 비용을 한 번으로 줄인다.
계산식(RAFT fp32 → 흐름 완성 → 이미지 전파 → 특징 전파·transformer → 원본 합성)은 ProPainter v0.1.0
inference_propainter.py의 video_inpainting 경로를 그대로 옮겼다. 서버 CPU에서 원래 방식과 같은 입력으로 결과를 대조했다.

입력·출력·이어하기는 1일차와 같다: clips/<cid>.mp4, masks/<cid>.npz, order.txt → out/<cid>/0000.jpg…(JPG 95), log.csv.
log.csv에 1일차 열(cid, 장수, 초, ok|fail) 뒤에 단계(prep·infer·save 초)를 덧붙인다. 이미 out/<cid>가 있으면 건너뛴다.
사용: python pc_propainter_batch2.py <작업 폴더> <ProPainter 폴더> [--limit 분] [--dilate px] [--mask_dilation n] [--width W --height H]
"""
import argparse
import csv
import os
import sys
import time

import cv2
import numpy as np


def load_models(pp, device, use_half):
    sys.path.insert(0, pp)
    from model.modules.flow_comp_raft import RAFT_bi
    from model.recurrent_flow_completion import RecurrentFlowCompleteNet
    from model.propainter import InpaintGenerator
    from utils.download_util import load_file_from_url
    url = 'https://github.com/sczhou/ProPainter/releases/download/v0.1.0/'
    wdir = os.path.join(pp, 'weights')
    raft = RAFT_bi(load_file_from_url(url=url + 'raft-things.pth', model_dir=wdir, progress=True, file_name=None), device)
    fc = RecurrentFlowCompleteNet(load_file_from_url(url=url + 'recurrent_flow_completion.pth', model_dir=wdir, progress=True, file_name=None))
    for p in fc.parameters():
        p.requires_grad = False
    fc.to(device)
    fc.eval()
    model = InpaintGenerator(model_path=load_file_from_url(url=url + 'ProPainter.pth', model_dir=wdir, progress=True, file_name=None)).to(device)
    model.eval()
    if use_half:  # 원본은 클립 안에서 RAFT 뒤에 half()로 바꾼다. 결과는 같고 한 번만 바꾼다.
        fc = fc.half()
        model = model.half()
    return raft, fc, model


def inpaint(frames_rgb, masks_u8, raft, fc, model, device, use_half, mask_dilation=4,
            ref_stride=10, neighbor_length=10, subvideo_length=80, raft_iter=20):
    """frames_rgb: [T,h,w,3] uint8 RGB(h,w는 8의 배수), masks_u8: [T,h,w] 0/255. 반환: [T,h,w,3] uint8 RGB."""
    import scipy.ndimage
    import torch
    from core.utils import to_tensors
    from PIL import Image
    from inference_propainter import get_ref_index
    video_length = len(frames_rgb)
    h, w = frames_rgb[0].shape[:2]
    frames = [Image.fromarray(f) for f in frames_rgb]
    flow_masks, masks_dilated = [], []
    for m in masks_u8:
        flow_masks.append(Image.fromarray(scipy.ndimage.binary_dilation(m, iterations=mask_dilation).astype(np.uint8) * 255)
                          if mask_dilation > 0 else Image.fromarray((m > 0.1).astype(np.uint8) * 255))
        masks_dilated.append(Image.fromarray(scipy.ndimage.binary_dilation(m, iterations=mask_dilation).astype(np.uint8) * 255)
                             if mask_dilation > 0 else Image.fromarray((m > 0.1).astype(np.uint8) * 255))
    ori_frames = [np.array(f).astype(np.uint8) for f in frames]
    frames = to_tensors()(frames).unsqueeze(0) * 2 - 1
    flow_masks = to_tensors()(flow_masks).unsqueeze(0)
    masks_dilated = to_tensors()(masks_dilated).unsqueeze(0)
    frames, flow_masks, masks_dilated = frames.to(device), flow_masks.to(device), masks_dilated.to(device)
    with torch.no_grad():
        if frames.size(-1) <= 640:
            short_clip_len = 12
        elif frames.size(-1) <= 720:
            short_clip_len = 8
        elif frames.size(-1) <= 1280:
            short_clip_len = 4
        else:
            short_clip_len = 2
        if frames.size(1) > short_clip_len:
            ff, fb = [], []
            for f in range(0, video_length, short_clip_len):
                end_f = min(video_length, f + short_clip_len)
                a, b = raft(frames[:, f:end_f] if f == 0 else frames[:, f - 1:end_f], iters=raft_iter)
                ff.append(a)
                fb.append(b)
                torch.cuda.empty_cache()
            gt_flows_bi = (torch.cat(ff, dim=1), torch.cat(fb, dim=1))
        else:
            gt_flows_bi = raft(frames, iters=raft_iter)
            torch.cuda.empty_cache()
        if use_half:
            frames, flow_masks, masks_dilated = frames.half(), flow_masks.half(), masks_dilated.half()
            gt_flows_bi = (gt_flows_bi[0].half(), gt_flows_bi[1].half())
        flow_length = gt_flows_bi[0].size(1)
        if flow_length > subvideo_length:
            pf, pb = [], []
            pad_len = 5
            for f in range(0, flow_length, subvideo_length):
                s_f = max(0, f - pad_len)
                e_f = min(flow_length, f + subvideo_length + pad_len)
                pad_len_s = max(0, f) - s_f
                pad_len_e = e_f - min(flow_length, f + subvideo_length)
                sub, _ = fc.forward_bidirect_flow((gt_flows_bi[0][:, s_f:e_f], gt_flows_bi[1][:, s_f:e_f]), flow_masks[:, s_f:e_f + 1])
                sub = fc.combine_flow((gt_flows_bi[0][:, s_f:e_f], gt_flows_bi[1][:, s_f:e_f]), sub, flow_masks[:, s_f:e_f + 1])
                pf.append(sub[0][:, pad_len_s:e_f - s_f - pad_len_e])
                pb.append(sub[1][:, pad_len_s:e_f - s_f - pad_len_e])
                torch.cuda.empty_cache()
            pred_flows_bi = (torch.cat(pf, dim=1), torch.cat(pb, dim=1))
        else:
            pred_flows_bi, _ = fc.forward_bidirect_flow(gt_flows_bi, flow_masks)
            pred_flows_bi = fc.combine_flow(gt_flows_bi, pred_flows_bi, flow_masks)
            torch.cuda.empty_cache()
        masked_frames = frames * (1 - masks_dilated)
        sub_len = min(100, subvideo_length)
        if video_length > sub_len:
            uf, um = [], []
            pad_len = 10
            for f in range(0, video_length, sub_len):
                s_f = max(0, f - pad_len)
                e_f = min(video_length, f + sub_len + pad_len)
                pad_len_s = max(0, f) - s_f
                pad_len_e = e_f - min(video_length, f + sub_len)
                b, t, _, _, _ = masks_dilated[:, s_f:e_f].size()
                sub = (pred_flows_bi[0][:, s_f:e_f - 1], pred_flows_bi[1][:, s_f:e_f - 1])
                prop, upd = model.img_propagation(masked_frames[:, s_f:e_f], sub, masks_dilated[:, s_f:e_f], 'nearest')
                ufs = frames[:, s_f:e_f] * (1 - masks_dilated[:, s_f:e_f]) + prop.view(b, t, 3, h, w) * masks_dilated[:, s_f:e_f]
                uf.append(ufs[:, pad_len_s:e_f - s_f - pad_len_e])
                um.append(upd.view(b, t, 1, h, w)[:, pad_len_s:e_f - s_f - pad_len_e])
                torch.cuda.empty_cache()
            updated_frames, updated_masks = torch.cat(uf, dim=1), torch.cat(um, dim=1)
        else:
            b, t, _, _, _ = masks_dilated.size()
            prop, upd = model.img_propagation(masked_frames, pred_flows_bi, masks_dilated, 'nearest')
            updated_frames = frames * (1 - masks_dilated) + prop.view(b, t, 3, h, w) * masks_dilated
            updated_masks = upd.view(b, t, 1, h, w)
            torch.cuda.empty_cache()
    comp = [None] * video_length
    neighbor_stride = neighbor_length // 2
    ref_num = subvideo_length // ref_stride if video_length > subvideo_length else -1
    for f in range(0, video_length, neighbor_stride):
        nids = [i for i in range(max(0, f - neighbor_stride), min(video_length, f + neighbor_stride + 1))]
        rids = get_ref_index(f, nids, video_length, ref_stride, ref_num)
        with torch.no_grad():
            pred = model(updated_frames[:, nids + rids], (pred_flows_bi[0][:, nids[:-1]], pred_flows_bi[1][:, nids[:-1]]),
                         masks_dilated[:, nids + rids], updated_masks[:, nids + rids], len(nids))
            pred = ((pred.view(-1, 3, h, w) + 1) / 2).cpu().permute(0, 2, 3, 1).numpy() * 255
            bm = masks_dilated[0, nids].cpu().permute(0, 2, 3, 1).numpy().astype(np.uint8)
            for i, idx in enumerate(nids):
                img = np.array(pred[i]).astype(np.uint8) * bm[i] + ori_frames[idx] * (1 - bm[i])
                comp[idx] = img if comp[idx] is None else comp[idx].astype(np.float32) * 0.5 + img.astype(np.float32) * 0.5
                comp[idx] = comp[idx].astype(np.uint8)
        torch.cuda.empty_cache()
    return comp


def read_clip(work, cid, dilate, size):
    cap = cv2.VideoCapture(os.path.join(work, "clips", cid + ".mp4"))
    frames = []
    while True:
        ok, f = cap.read()
        if not ok:
            break
        frames.append(f)
    z = np.load(os.path.join(work, "masks", cid + ".npz"))
    T, H, W = [int(v) for v in z["shape"]]
    M = np.unpackbits(z["mask"], axis=-1)[..., :W]
    T = min(T, len(frames))
    w8, h8 = size if size else (W // 8 * 8, H // 8 * 8)
    w8, h8 = w8 // 8 * 8, h8 // 8 * 8
    k = np.ones((2 * dilate + 1, 2 * dilate + 1), np.uint8)
    fr = [cv2.cvtColor(cv2.resize(frames[i], (w8, h8), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2RGB) for i in range(T)]
    ms = [cv2.resize((cv2.dilate(M[i], k) if dilate > 0 else M[i]) * 255, (w8, h8), interpolation=cv2.INTER_NEAREST) for i in range(T)]
    return fr, ms


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("work")
    ap.add_argument("pp")
    ap.add_argument("--limit", type=float, default=0, help="이 분이 지나면 새 클립을 시작하지 않음(0이면 끝까지)")
    ap.add_argument("--dilate", type=int, default=6, help="인물 마스크 넓히기(원본 해상도 px). 1일차와 같은 기본 6")
    ap.add_argument("--mask_dilation", type=int, default=4, help="ProPainter 자체 추가 넓히기(반복 횟수). 원본 기본 4")
    ap.add_argument("--width", type=int, default=0)
    ap.add_argument("--height", type=int, default=0)
    ap.add_argument("--fp32", action="store_true", help="fp16 끄기(1일차는 --fp16)")
    ap.add_argument("--only", default="", help="쉼표로 cid 지정(시험용)")
    a = ap.parse_args()
    work, pp = os.path.abspath(a.work), os.path.abspath(a.pp)
    t_start = time.time()
    import torch
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    use_half = (not a.fp32) and device.type == "cuda"
    os.chdir(pp)
    raft, fc, model = load_models(pp, device, use_half)
    print(f"모델 준비 {time.time() - t_start:.1f}초 ({device}, fp16={use_half})", flush=True)
    order = a.only.split(",") if a.only else [l.strip() for l in open(os.path.join(work, "order.txt"), encoding="utf-8") if l.strip()]
    os.makedirs(os.path.join(work, "out"), exist_ok=True)
    log = os.path.join(work, "log.csv")
    size = (a.width, a.height) if a.width and a.height else None
    done = 0
    for n, cid in enumerate(order):
        if a.limit and time.time() - t_start > a.limit * 60:
            print("시간 제한으로 멈춤", flush=True)
            break
        dst = os.path.join(work, "out", cid)
        if os.path.isdir(dst) and os.listdir(dst):
            continue
        t0 = time.time()
        try:
            fr, ms = read_clip(work, cid, a.dilate, size)
            if len(fr) < 3:
                continue
            t1 = time.time()
            comp = inpaint(fr, ms, raft, fc, model, device, use_half, a.mask_dilation)
            t2 = time.time()
            os.makedirs(dst + ".part", exist_ok=True)
            for i, f in enumerate(comp):
                cv2.imwrite(os.path.join(dst + ".part", f"{i:04d}.jpg"), cv2.cvtColor(f, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 95])
            os.replace(dst + ".part", dst)  # 중간에 끊겨도 반쯤 쓴 폴더를 '끝남'으로 보지 않게
            t3 = time.time()
            row = [cid, len(fr), round(t3 - t0, 1), "ok", round(t1 - t0, 1), round(t2 - t1, 1), round(t3 - t2, 1)]
        except Exception as e:  # 메모리 부족 등: 기록하고 다음 클립
            import torch as _t
            _t.cuda.empty_cache()
            print(cid, "실패", repr(e)[-300:], flush=True)
            row = [cid, 0, round(time.time() - t0, 1), "fail", repr(e)[-120:]]
        with open(log, "a", newline="", encoding="utf-8") as fh:
            csv.writer(fh).writerow(row)
        done += 1
        print(f"[{n + 1}/{len(order)}] {cid} {row[1]}장 {row[2]}초 (누적 {(time.time() - t_start) / 60:.1f}분, 이번 실행 {done}개)", flush=True)


if __name__ == "__main__":
    main()
