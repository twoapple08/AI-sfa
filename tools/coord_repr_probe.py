"""좌표 표현 비교 소규모 CPU 시험(2026-11-04).

변환기 진단(docs/SEQ-CONVERTER-DIAGNOSIS-2026-11-04.md)에서 초미세 8192칸 좌표가 확률을 흩어
탐욕 생성이 무너지는 것을 확인했다. 같은 작은 모델·자료·걸음으로 좌표 표현만 바꿔 비교한다.

- flat: 8192칸 한 토큰. 손실 = 정확한 칸 50% + 이웃 ±2칸 50%(seq_train.token_loss와 같은 방식)
- two: 거친 128칸 → 세부 64칸 두 토큰(128×64=8192). 손실 = 보통 교차 엔트로피
- flat1k: 1024칸 한 토큰(칸 8배 큼, 문장 길이 그대로). 손실은 flat과 같은 정확50%+이웃±2칸50%

과제: 160×90 그림의 직선 1~3개 끝점을 적는다. 그림은 매 묶음 새로 만든다(외우기 아님).
선 순서는 정해진 규칙(왼쪽 끝 먼저, 선은 시작 x 순)이다. 실제 SFA/학습 자료와 무관한 진단 도구이며
실제 변환기 성능이나 합격을 뜻하지 않는다.
"""
import argparse
import json
import math
import time

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

W, H = 160, 90
Q = 8192
COARSE, FINE = 128, 64
BOS, EOS, LINE = 0, 1, 2
SPECIAL = 3


Q1K = 1024
SINGLE = {'flat': Q, 'flat1k': Q1K}   # 한 토큰 표현의 칸 수


def vocab(mode):
    return SPECIAL + (SINGLE[mode] if mode in SINGLE else COARSE + FINE)


def sample(rng, n_max=3):
    n = int(rng.integers(1, n_max + 1))
    lines = []
    for _ in range(n):
        a = rng.uniform(5, 95, 2)
        b = rng.uniform(5, 95, 2)
        if a[0] > b[0]:
            a, b = b, a
        lines.append((a[0], a[1], b[0], b[1], int(rng.integers(1, 4))))
    lines.sort(key=lambda l: l[0])
    return lines


def render(lines):
    import cv2
    im = np.full((H, W), 255, np.uint8)
    for x0, y0, x1, y1, th in lines:
        cv2.line(im, (round(x0 / 100 * (W - 1) * 16), round(y0 / 100 * (H - 1) * 16)),
                 (round(x1 / 100 * (W - 1) * 16), round(y1 / 100 * (H - 1) * 16)), 0, th, cv2.LINE_AA, shift=4)
    return im


def quant(v, n=Q):
    return int(np.clip(round(v / 100 * (n - 1)), 0, n - 1))


def dequant(q, n=Q):
    return q / (n - 1) * 100


def encode(lines, mode):
    toks = [BOS]
    for x0, y0, x1, y1, _ in lines:
        toks.append(LINE)
        for v in (x0, y0, x1, y1):
            if mode in SINGLE:
                toks.append(SPECIAL + quant(v, SINGLE[mode]))
            else:
                q = quant(v)
                toks += [SPECIAL + q // FINE, SPECIAL + COARSE + q % FINE]
    return toks + [EOS]


def grammar_masks(mode, prefix_len_after_line):
    """LINE 뒤 몇 번째 토큰인지로 허용 토큰 범위를 정한다."""
    V = vocab(mode)
    m = torch.full((V,), float('-inf'))
    per = 4 if mode in SINGLE else 8
    k = prefix_len_after_line
    if k is None or k == per:          # 선 시작 전/끝난 뒤: LINE 또는 EOS
        m[LINE] = m[EOS] = 0
    elif mode in SINGLE:
        m[SPECIAL:SPECIAL + SINGLE[mode]] = 0
    elif k % 2 == 0:
        m[SPECIAL:SPECIAL + COARSE] = 0
    else:
        m[SPECIAL + COARSE:SPECIAL + COARSE + FINE] = 0
    return m


class Net(nn.Module):
    def __init__(self, mode, d=128, layers=3, heads=4, maxlen=40):
        super().__init__()
        self.mode = mode
        self.enc = nn.Sequential(
            nn.Conv2d(1, 32, 3, 2, 1), nn.ReLU(), nn.Conv2d(32, 64, 3, 1, 1), nn.ReLU(),
            nn.Conv2d(64, 96, 3, 2, 1), nn.ReLU(), nn.Conv2d(96, d, 3, 1, 1), nn.ReLU())
        self.row = nn.Embedding(32, d)
        self.col = nn.Embedding(48, d)
        self.emb = nn.Embedding(vocab(mode), d)
        self.pos = nn.Embedding(maxlen, d)
        layer = nn.TransformerDecoderLayer(d, heads, 4 * d, 0.0, batch_first=True, norm_first=True)
        self.dec = nn.TransformerDecoder(layer, layers)
        self.norm = nn.LayerNorm(d)
        self.head = nn.Linear(d, vocab(mode))

    def memory(self, img):
        f = self.enc(img)
        B, C, h, w = f.shape
        pe = self.row.weight[:h, None] + self.col.weight[None, :w]
        return f.flatten(2).transpose(1, 2) + pe.reshape(h * w, C)[None]

    def forward(self, img, tok):
        T = tok.shape[1]
        x = self.emb(tok) + self.pos.weight[:T][None]
        causal = torch.triu(torch.full((T, T), float('-inf')), 1)
        return self.head(self.norm(self.dec(x, self.memory(img), tgt_mask=causal, tgt_is_causal=True)))


def batch(rng, n, mode):
    data = [sample(rng) for _ in range(n)]
    seqs = [encode(l, mode) for l in data]
    L = max(map(len, seqs))
    tok = torch.full((n, L), EOS, dtype=torch.long)
    mask = torch.zeros((n, L), dtype=torch.bool)
    for i, s in enumerate(seqs):
        tok[i, :len(s)] = torch.tensor(s)
        mask[i, :len(s)] = True
    img = torch.from_numpy(np.stack([render(l) for l in data])).float()[:, None] / 255
    return img, tok, mask, data


def loss_fn(logits, tgt, mask, mode):
    logp = F.log_softmax(logits, -1)
    exact = -logp.gather(-1, tgt[..., None])[..., 0]
    if mode in SINGLE:
        # 실제 변환기의 수 칸 손실처럼: 정확한 칸 50% + 이웃 ±2칸 분포 50%
        is_num = tgt >= SPECIAL
        off = torch.arange(-2, 3)
        nb = (tgt[..., None] + off).clamp(SPECIAL, SPECIAL + SINGLE[mode] - 1)
        soft = -logp.gather(-1, nb).mean(-1)
        exact = torch.where(is_num, 0.5 * exact + 0.5 * soft, exact)
    m = mask.float()
    return (exact * m).sum() / m.sum()


@torch.no_grad()
def generate(net, img, maxlen=40):
    mode = net.mode
    toks, k = [BOS], None
    mem = net.memory(img[None])
    while len(toks) < maxlen:
        T = len(toks)
        x = net.emb(torch.tensor(toks)[None]) + net.pos.weight[:T][None]
        causal = torch.triu(torch.full((T, T), float('-inf')), 1)
        lg = net.head(net.norm(net.dec(x, mem, tgt_mask=causal, tgt_is_causal=True)))[0, -1]
        t = int((lg + grammar_masks(mode, k)).argmax())
        toks.append(t)
        if t == EOS:
            break
        k = 0 if t == LINE else k + 1
    return toks


def decode(toks, mode):
    vals, lines = [], []
    i = 0
    while i < len(toks):
        t = toks[i]
        if t == LINE:
            vals = []
        elif t >= SPECIAL:
            if mode in SINGLE:
                vals.append(dequant(t - SPECIAL, SINGLE[mode]))
            elif t < SPECIAL + COARSE and i + 1 < len(toks) and toks[i + 1] >= SPECIAL + COARSE:
                vals.append(dequant((t - SPECIAL) * FINE + toks[i + 1] - SPECIAL - COARSE))
                i += 1
            if len(vals) == 4:
                lines.append(tuple(vals))
        i += 1
    return lines


def endpoint_error_px(a, b):
    """선 하나의 두 끝점 평균 오차(1920×1080 화면 기준 픽셀), 끝점 순서 무관."""
    def d(p, q):
        return math.hypot((p[0] - q[0]) * 19.2, (p[1] - q[1]) * 10.8)
    A0, A1, B0, B1 = (a[0], a[1]), (a[2], a[3]), (b[0], b[1]), (b[2], b[3])
    return min(d(A0, B0) + d(A1, B1), d(A0, B1) + d(A1, B0)) / 2


def evaluate(net, n, seed):
    from scipy.optimize import linear_sum_assignment
    rng = np.random.default_rng(seed)
    errs, count_ok = [], 0
    net.eval()
    for _ in range(n):
        truth = sample(rng)
        img = torch.from_numpy(render(truth)).float()[None] / 255
        pred = decode(generate(net, img), net.mode)
        count_ok += len(pred) == len(truth)
        if pred:
            cost = np.array([[endpoint_error_px(t, p) for p in pred] for t in truth])
            r, c = linear_sum_assignment(cost)
            errs += cost[r, c].tolist()
        errs += [1e4] * (len(truth) - min(len(truth), len(pred)))   # 못 그린 선
    net.train()
    e = np.array(errs)
    return dict(lines=len(e), median_px=float(np.median(e)), within20=float(np.mean(e <= 20)),
                within50=float(np.mean(e <= 50)), count_correct=count_ok / n)


def run(mode, steps, bs, seed, eval_n, eval_every):
    torch.manual_seed(seed)
    rng = np.random.default_rng(seed)
    net = Net(mode)
    opt = torch.optim.AdamW(net.parameters(), lr=3e-4)
    hist, t0 = [], time.time()
    for step in range(1, steps + 1):
        img, tok, mask, _ = batch(rng, bs, mode)
        lg = net(img, tok[:, :-1])
        loss = loss_fn(lg, tok[:, 1:], mask[:, 1:], mode)
        opt.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(net.parameters(), 1.0)
        opt.step()
        if step % eval_every == 0 or step == steps:
            ev = evaluate(net, eval_n, 12345)
            hist.append(dict(step=step, loss=float(loss), seconds=round(time.time() - t0, 1), **ev))
            print(mode, json.dumps(hist[-1], ensure_ascii=False), flush=True)
    return hist


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--modes', nargs='+', default=['flat', 'two'])
    p.add_argument('--steps', type=int, default=3000)
    p.add_argument('--bs', type=int, default=32)
    p.add_argument('--seed', type=int, default=0)
    p.add_argument('--eval-n', type=int, default=100)
    p.add_argument('--eval-every', type=int, default=500)
    p.add_argument('--out')
    a = p.parse_args()
    torch.set_num_threads(4)
    res = {m: run(m, a.steps, a.bs, a.seed, a.eval_n, a.eval_every) for m in a.modes}
    if a.out:
        with open(a.out, 'w', encoding='utf-8') as f:
            json.dump(res, f, ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()
