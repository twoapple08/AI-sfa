#!/usr/bin/env python3
"""MoMask(공개 HumanML3D 가중치) 추가 학습 — '기초 모델 + 우리 자료' (그림체 LoRA처럼 트리거 문장 'in anime style').

사용(momask-codes 폴더 안에서): python <이 파일> <자료 폴더(tools/motion_dataset.py 출력)> [--steps 3000] [--batch 16] [--lr 2e-5]
        [--tag ft_anime] [--part both|mask|res] [--device cuda|cpu]
- VQ(동작 ↔ 토큰)는 그대로 두고, 글 → 토큰 변환기(마스크 트랜스포머)와 잔차 트랜스포머만 미세조정한다(기본기 보존).
- 정규화는 원래 가중치의 mean/std를 그대로 쓴다(새 자료도 같은 잣대).
- 결과: checkpoints/t2m/<원래 이름>_<tag>/(model/latest.tar 또는 net_best_fid.tar + opt.txt) — gen_t2m.py에 --name/--res_name으로 넣으면 된다.
  가중치는 저장소에 넣지 않는다(Drive).
- 4GB GPU(GTX 1050 Ti)용: --batch 8~16, fp32. 메모리가 모자라면 --batch를 줄인다.
"""
import argparse
import os
import random
import shutil
import sys
import time
from os.path import join as pjoin

import numpy as np
import torch

sys.path.insert(0, os.getcwd())
from gen_t2m import load_res_model, load_trans_model, load_vq_model  # noqa: E402
from utils.get_opt import get_opt  # noqa: E402

T2M = "t2m_nlayer8_nhead6_ld384_ff1024_cdp0.1_rvq6ns"
RES = "tres_nlayer8_ld384_ff1024_rvq6ns_cdp0.2_sw"


class Args:  # gen_t2m 로더가 쓰는 최소 옵션
    def __init__(self, dev):
        self.device = dev
        self.checkpoints_dir = "./checkpoints"
        self.dataset_name = "t2m"
        self.name = T2M


def load_data(root, split, mean, std):
    ids = [l.strip() for l in open(pjoin(root, split + ".txt")) if l.strip()]
    out = []
    for i in ids:
        m = (np.load(pjoin(root, "new_joint_vecs", i + ".npy")) - mean) / std
        cap = open(pjoin(root, "texts", i + ".txt"), encoding="utf-8").readline().split("#")[0]
        n = (min(len(m), 196) // 4) * 4
        if n >= 40:
            out.append((m[:n].astype(np.float32), cap))
    return out


def batches(data, bs, rng):
    while True:
        rng.shuffle(data)
        for k in range(0, len(data) - bs + 1, bs):
            part = data[k:k + bs]
            L = np.array([len(m) for m, _ in part])
            M = np.zeros((bs, 196, part[0][0].shape[1]), np.float32)
            for j, (m, _) in enumerate(part):
                M[j, :len(m)] = m
            yield torch.from_numpy(M), [c for _, c in part], torch.from_numpy(L // 4)


def save_like(src_name, tag, key, model, fname, step):
    dst = pjoin("checkpoints", "t2m", f"{src_name}_{tag}")
    os.makedirs(pjoin(dst, "model"), exist_ok=True)
    txt = open(pjoin("checkpoints", "t2m", src_name, "opt.txt")).read().replace(f"name: {src_name}", f"name: {src_name}_{tag}")
    open(pjoin(dst, "opt.txt"), "w").write(txt)
    sd = {k: v for k, v in model.state_dict().items() if not k.startswith("clip_model.")}
    torch.save({key: sd, "ep": step}, pjoin(dst, "model", fname))
    return dst


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("data")
    ap.add_argument("--steps", type=int, default=3000)
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--lr", type=float, default=2e-5)
    ap.add_argument("--tag", default="ft_anime")
    ap.add_argument("--part", default="both", choices=["both", "mask", "res"])
    ap.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    ap.add_argument("--val-every", type=int, default=250)
    ap.add_argument("--style-rep", type=int, default=4, help="트리거 문장(in anime style) 자료를 학습에서 몇 배로 볼지(애니 자료가 적어서)")
    a = ap.parse_args()
    dev = torch.device(a.device)
    opt = Args(dev)
    model_opt = get_opt(pjoin("checkpoints", "t2m", T2M, "opt.txt"), device=dev)
    vq_opt = get_opt(pjoin("checkpoints", "t2m", model_opt.vq_name, "opt.txt"), device=dev)
    vq_opt.dim_pose = 263
    vq, vq_opt = load_vq_model(vq_opt)
    model_opt.num_tokens, model_opt.num_quantizers, model_opt.code_dim = vq_opt.nb_code, vq_opt.num_quantizers, vq_opt.code_dim
    res_opt = get_opt(pjoin("checkpoints", "t2m", RES, "opt.txt"), device=dev)
    mask_t = load_trans_model(model_opt, opt, "latest.tar")
    res_t = load_res_model(res_opt, vq_opt, opt)
    vq.to(dev).eval()
    mean = np.load(pjoin("checkpoints", "t2m", model_opt.vq_name, "meta", "mean.npy"))
    std = np.load(pjoin("checkpoints", "t2m", model_opt.vq_name, "meta", "std.npy"))
    tr, va = load_data(a.data, "train", mean, std), load_data(a.data, "val", mean, std)
    na = sum("anime style" in c for _, c in tr)
    tr = tr + [x for x in tr if "anime style" in x[1]] * (a.style_rep - 1)
    print("학습", len(tr), f"(애니 {na}×{a.style_rep})", "검증", len(va), "장치", dev)
    models = {"mask": mask_t, "res": res_t}
    use = ["mask", "res"] if a.part == "both" else [a.part]
    opts = {}
    for k in use:
        models[k].to(dev).train()
        opts[k] = torch.optim.AdamW(models[k].parameters_wo_clip(), lr=a.lr, betas=(0.9, 0.99), weight_decay=1e-5)
    rng = random.Random(0)
    it = batches(tr, a.batch, rng)

    def step_loss(k, M, caps, L):
        with torch.no_grad():
            code_idx, _ = vq.encode(M.to(dev))
        if k == "mask":
            loss, _, acc = models[k](code_idx[..., 0], caps, L.to(dev))
        else:
            loss, _, acc = models[k](code_idx, caps, L.to(dev))
        return loss, acc

    t0 = time.time()
    for s in range(1, a.steps + 1):
        M, caps, L = next(it)
        msg = []
        for k in use:
            loss, acc = step_loss(k, M, caps, L)
            opts[k].zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(models[k].parameters_wo_clip(), 1.0)
            opts[k].step()
            msg.append(f"{k} {loss.item():.3f}/{acc:.3f}")
        if s % 50 == 0 or s == 1:
            print(f"단계 {s} {' '.join(msg)} {time.time() - t0:.0f}s", flush=True)
        if s % a.val_every == 0 or s == a.steps:
            for k in use:
                models[k].eval()
            vl = {k: [] for k in use}
            with torch.no_grad():
                for j in range(0, len(va) - a.batch + 1, a.batch):
                    M, caps, L = next(batches(va[j:j + a.batch], a.batch, random.Random(j)))
                    for k in use:
                        vl[k].append(step_loss(k, M, caps, L)[0].item())
            print("검증", {k: round(float(np.mean(v)), 3) if v else None for k, v in vl.items()}, flush=True)
            for k in use:
                models[k].train()
            if "mask" in use:
                d = save_like(T2M, a.tag, "t2m_transformer", mask_t, "latest.tar", s)
            if "res" in use:
                d = save_like(RES, a.tag, "res_transformer", res_t, "net_best_fid.tar", s)
            print("저장", d, flush=True)


if __name__ == "__main__":
    main()
