"""2D→3D 올리기 모델 학습(GPU). 통합 모캡(tools/mocap_unify.py)을 매 단계 무작위 카메라로 투영해 학습 쌍을 만든다.

사용: python tools/lift_train.py <mocap_unified 폴더> <출력 폴더> [--steps 60000] [--batch 256] [--win 81] [--test]
입력 2D: RTMW 몸 17점(COCO 순서) [창, 17, 3] = (x, y, 보임). 골반 중심·몸 크기 1로 정규화. 빠진 점은 (0, 0, 0).
출력 3D: 공통 18관절, 카메라 좌표(미터, 골반 기준). 창 전체 프레임을 한 번에 낸다.
애니 대응 증강:
- 멈춤: 창을 2·3프레임씩 같은 포즈로 유지(애니의 2컷·3컷). 정답 3D도 같이 유지.
- 빠진 점: 관절별 무작위 제거, 하체 통째 제거(화면 밖), 손목 제거.
- 잡음: 2D 가우스 잡음(몸 크기의 0~4%), 가끔 큰 튐.
- 카메라: 방위 0~360°, 높이각 -25~50°, 거리 2~9 m, 초점 0.7~3.0.
검증: 클립 번호로 나눈 5% 클립, 고정 시드. 지표 MPJPE(mm), 골반 정렬 후.
걷기·감정 표현만 있는 클립은 덜 뽑고, 공격·피격·점프·구르기는 더 뽑는다(mocap_index 태그).
학습 결과(가중치)는 Drive에 두고 저장소에는 넣지 않는다.
"""
import argparse
import csv
import math
import os
import time
import zlib

import numpy as np
import torch
import torch.nn as nn

JN = ["pelvis", "spine", "neck", "head", "l_shoulder", "r_shoulder", "l_elbow", "r_elbow", "l_wrist", "r_wrist",
      "l_hip", "r_hip", "l_knee", "r_knee", "l_ankle", "r_ankle", "l_toe", "r_toe"]
J = {n: i for i, n in enumerate(JN)}
PAR = [-1, 0, 1, 2, 2, 2, 4, 5, 6, 7, 0, 0, 10, 11, 12, 13, 14, 15]
SOURCES = ["cmu", "lafan1", "bandai", "amass"]
BOOST = ("공격", "피격·넘어짐", "점프·공중", "구르기·바닥", "방어·회피")
BODY_ORDER = ["l_shoulder", "r_shoulder", "l_elbow", "r_elbow", "l_wrist", "r_wrist", "l_hip", "r_hip", "l_knee",
              "r_knee", "l_ankle", "r_ankle"]


def load(src_dir, index):
    tags = {}
    if index and os.path.exists(index):
        tags = {(r["자료"], r["클립"]): r["태그"] for r in csv.DictReader(open(index, encoding="utf-8"))}
    pos, clips = [], []  # clips: (전역 시작, 길이, 가중치, 검증 여부)
    off = 0
    for s in SOURCES:
        p = os.path.join(src_dir, s + ".npz")
        if not os.path.exists(p):
            continue
        z = np.load(p)
        pos.append(z["pos"])
        for ci, (st, ln, nm) in enumerate(zip(z["start"], z["length"], z["clip"])):
            t = tags.get((s, str(nm)), "")
            w = 0.25 if t and set(t.split(";")) <= {"걷기", "감정 표현"} else (2.0 if any(b in t for b in BOOST) else 1.0)
            val = zlib.crc32(f"{s}:{ci}".encode()) % 20 == 0  # 실행마다 같은 검증 클립
            clips.append((off + int(st), int(ln), w, val))
        off += len(z["pos"])
    return np.concatenate(pos), clips


def coco17(P):
    """[B,T,18,3] → [B,T,17,3]. 코·눈·귀는 머리 주변 근사점(머리 방향 기준)."""
    head, neck = P[..., J["head"], :], P[..., J["neck"], :]
    up = head - neck
    up = up / (up.norm(dim=-1, keepdim=True) + 1e-6)
    side = P[..., J["l_shoulder"], :] - P[..., J["r_shoulder"], :]
    side = side / (side.norm(dim=-1, keepdim=True) + 1e-6)
    fwd = torch.cross(side, up, dim=-1)
    fwd = fwd / (fwd.norm(dim=-1, keepdim=True) + 1e-6)
    pts = [head + 0.09 * fwd + 0.02 * up,
           head + 0.07 * fwd + 0.035 * side + 0.05 * up, head + 0.07 * fwd - 0.035 * side + 0.05 * up,
           head + 0.075 * side + 0.03 * up, head - 0.075 * side + 0.03 * up]
    return torch.cat([torch.stack(pts, -2), P[..., [J[n] for n in BODY_ORDER], :]], -2)


def cameras(B, g, dev):
    az = torch.rand(B, generator=g, device=dev) * 2 * math.pi
    el = torch.deg2rad(torch.rand(B, generator=g, device=dev) * 75 - 25)
    dist = torch.rand(B, generator=g, device=dev) * 7 + 2
    foc = torch.rand(B, generator=g, device=dev) * 2.3 + 0.7
    c = torch.stack([torch.sin(az) * torch.cos(el), torch.sin(el), torch.cos(az) * torch.cos(el)], -1) * dist[:, None]
    f = -c / c.norm(dim=-1, keepdim=True)
    upv = torch.tensor([0.0, 1.0, 0.0], device=dev).expand_as(f)
    r = torch.cross(f, upv, dim=-1)
    r = r / (r.norm(dim=-1, keepdim=True) + 1e-6)
    u = torch.cross(r, f, dim=-1)
    return torch.stack([r, u, f], 1), c, foc  # R [B,3,3]


def make_batch(pos, idx, win, g, dev, train=True):
    """idx: 창 시작 전역 프레임 [B]. 반환 x2d [B,T,17,3], y3d [B,T,18,3]."""
    B = len(idx)
    ar = torch.arange(win, device=dev)
    P = pos[(idx[:, None] + ar[None]).reshape(-1)].reshape(B, win, 18, 3).float()
    if train:  # 멈춤(2·3컷): 창의 일부 표본에서 프레임을 k개씩 묶어 첫 프레임으로 유지
        k = torch.randint(1, 4, (B,), generator=g, device=dev)
        hold = (torch.rand(B, generator=g, device=dev) < 0.5)
        src = (ar[None] // k[:, None]) * k[:, None]
        src = torch.where(hold[:, None], src, ar[None].expand(B, -1))
        P = torch.gather(P, 1, src[:, :, None, None].expand(-1, -1, 18, 3))
    root = P[:, win // 2, J["pelvis"]].clone()
    root[:, 1] += (torch.rand(B, generator=g, device=dev) * 0.9 - 0.3)
    R, c, foc = cameras(B, g, dev)
    Pc = torch.einsum("bij,btkj->btki", R, P - (root + c)[:, None, None])
    ok = (Pc[..., 2] > 0.3).all(-1).all(-1)
    C = coco17(Pc)
    X = foc[:, None, None, None] * C[..., :2] / C[..., 2:3].clamp(min=0.3)
    X[..., 1] = -X[..., 1]
    hip = (X[:, :, 11] + X[:, :, 12]) / 2
    sh = (X[:, :, 5] + X[:, :, 6]) / 2
    s = (sh - hip).norm(dim=-1).median(dim=1).values.clamp(min=1e-3)
    X = (X - hip[:, :, None]) / s[:, None, None, None]
    vis = torch.ones(*X.shape[:3], 1, device=dev)
    if train:
        X = X + torch.randn(X.shape, generator=g, device=dev) * (torch.rand(B, 1, 1, 1, generator=g, device=dev) * 0.04)
        spike = torch.rand(X.shape[:3], generator=g, device=dev) < 0.005
        X = X + spike[..., None] * torch.randn(X.shape, generator=g, device=dev) * 0.3
        drop = torch.rand(X.shape[:3], generator=g, device=dev) < torch.rand(B, 1, 1, generator=g, device=dev) * 0.2
        legs = (torch.rand(B, generator=g, device=dev) < 0.1)[:, None, None] & (torch.arange(17, device=dev) >= 13)
        vis = (~(drop | legs)).float()[..., None]
        X = X * vis
    Y = Pc - Pc[:, :, :1]
    return torch.cat([X, vis], -1)[ok], Y[ok]


class Lifter(nn.Module):
    def __init__(self, win, d=256, layers=6, heads=8):
        super().__init__()
        self.inp = nn.Linear(17 * 3, d)
        self.pos = nn.Parameter(torch.zeros(1, win, d))
        enc = nn.TransformerEncoderLayer(d, heads, d * 4, dropout=0.1, batch_first=True, norm_first=True)
        self.enc = nn.TransformerEncoder(enc, layers)
        self.out = nn.Linear(d, 18 * 3)

    def forward(self, x):
        B, T = x.shape[:2]
        h = self.enc(self.inp(x.reshape(B, T, -1)) + self.pos[:, :T])
        return self.out(h).reshape(B, T, 18, 3)


def losses(pred, y):
    mpjpe = (pred - y).norm(dim=-1).mean()
    vel = ((pred[:, 1:] - pred[:, :-1]) - (y[:, 1:] - y[:, :-1])).norm(dim=-1).mean()
    bp = (pred[:, :, 1:] - pred[:, :, PAR[1:]]).norm(dim=-1)
    by = (y[:, :, 1:] - y[:, :, PAR[1:]]).norm(dim=-1)
    bone = (bp - by).abs().mean()
    return mpjpe, vel, bone


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("out")
    ap.add_argument("--index", default="data/mocap/mocap_index_2026-10-21.csv")
    ap.add_argument("--steps", type=int, default=60000)
    ap.add_argument("--batch", type=int, default=256)
    ap.add_argument("--win", type=int, default=81)
    ap.add_argument("--lr", type=float, default=3e-4)
    ap.add_argument("--test", action="store_true", help="CPU로 몇 단계만 돌려 확인")
    a = ap.parse_args()
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    os.makedirs(a.out, exist_ok=True)
    pos_np, clips = load(a.src, a.index)
    pos = torch.from_numpy(pos_np.astype(np.float32)).to(dev)
    win = a.win
    tr = [(s, n, w) for s, n, w, v in clips if not v and n >= win]
    va = [(s, n) for s, n, w, v in clips if v and n >= win]
    w = np.array([wt * (n - win + 1) for s, n, wt in tr], np.float64)
    w /= w.sum()
    print(f"프레임 {len(pos_np)} 학습 클립 {len(tr)} 검증 클립 {len(va)} 장치 {dev}", flush=True)
    rng = np.random.default_rng(0)

    def sample(n):
        ci = rng.choice(len(tr), n, p=w)
        return torch.tensor([tr[i][0] + rng.integers(0, tr[i][1] - win + 1) for i in ci], device=dev)

    vidx = torch.tensor([s + o for s, n in va for o in range(0, n - win + 1, 60)][:4096], device=dev)
    gv = torch.Generator(device=dev).manual_seed(123)
    vx, vy = make_batch(pos, vidx, win, gv, dev, train=False)
    g = torch.Generator(device=dev).manual_seed(1)
    model = Lifter(win).to(dev)
    opt = torch.optim.AdamW(model.parameters(), lr=a.lr, weight_decay=0.01)
    steps = 3 if a.test else a.steps
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, a.lr, total_steps=steps, pct_start=0.05)
    ck = os.path.join(a.out, "lifter.pt")
    start = 0
    if os.path.exists(ck) and not a.test:
        st = torch.load(ck, map_location=dev)
        model.load_state_dict(st["model"])
        opt.load_state_dict(st["opt"])
        sched.load_state_dict(st["sched"])
        start = st["step"]
        print("이어서", start, flush=True)
    bs = 4 if a.test else a.batch
    t0 = time.time()
    for step in range(start, steps):
        model.train()
        x, y = make_batch(pos, sample(bs), win, g, dev)
        m, v, b = losses(model(x), y)
        loss = m + 0.5 * v + 0.2 * b
        opt.zero_grad()
        loss.backward()
        nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step()
        sched.step()
        if (step + 1) % (1 if a.test else 1000) == 0 or step + 1 == steps:
            model.eval()
            with torch.no_grad():
                errs = [losses(model(vx[i:i + 512]), vy[i:i + 512])[0].item() for i in range(0, len(vx), 512)]
            print(f"{step + 1} 학습 {m.item() * 1000:.0f}mm 검증 MPJPE {np.mean(errs) * 1000:.1f}mm "
                  f"{(time.time() - t0) / 60:.1f}분", flush=True)
            if not a.test:
                torch.save({"model": model.state_dict(), "opt": opt.state_dict(), "sched": sched.state_dict(),
                            "step": step + 1, "win": win, "joints": JN}, ck)


if __name__ == "__main__":
    main()
