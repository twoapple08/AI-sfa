"""꺾은선 과제로 '앞 좌표 베끼기' 재현·대책 비교(2026-11-05).

직선 1~3개 과제(coord_repr_probe)에서는 실제 변환기의 끝점 붕괴(two 모델 87%)가 1% 정도만 나와 대책을 가를 수 없었다.
실제 SFA 객체처럼 점 여러 개가 이어지고, 이웃 점이 가깝거나 X·Y 하나를 공유(가로·세로 꺾임)하는 꺾은선으로 바꾼다.
모델·표현(two/two_w/ptr/flat1k)은 coord_repr_probe의 것을 그대로 쓴다.

지표: 생성 꺾은선의 점 대응 오차, 길이 비(붕괴), **교사 강제 베끼기율**(정답이 같은 축 앞 값과 다른 자리에서
예측이 앞 값을 그대로 고른 비율 — 실제 변환기 진단의 0.38과 같은 정의).
실제 변환기 성능을 뜻하지 않는 진단 도구다.
"""
import argparse
import json
import math
import time

import numpy as np
import torch

import coord_repr_probe as P

MAXLEN = 64


def sample(rng):
    """꺾은선 1~2개, 점 2~6개. 이웃 점: 30% 같은 X, 20% 같은 Y, 나머지 짧은(5~25%) 이동."""
    objs = []
    for _ in range(int(rng.integers(1, 3))):
        n = int(rng.integers(2, 7))
        x, y = rng.uniform(10, 90, 2)
        pts = [(x, y)]
        for _ in range(n - 1):
            r, step = rng.random(), rng.uniform(5, 25)
            ang = rng.uniform(0, 2 * math.pi)
            if r < 0.3:
                y = y + step * (1 if rng.random() < .5 else -1)
            elif r < 0.5:
                x = x + step * (1 if rng.random() < .5 else -1)
            else:
                x, y = x + step * math.cos(ang), y + step * math.sin(ang)
            x, y = float(np.clip(x, 3, 97)), float(np.clip(y, 3, 97))
            pts.append((x, y))
        objs.append((pts, int(rng.integers(1, 3))))
    objs.sort(key=lambda o: o[0][0][0])
    return objs


def render(objs):
    import cv2
    im = np.full((P.H, P.W), 255, np.uint8)
    for pts, th in objs:
        q = np.array([[round(x / 100 * (P.W - 1) * 16), round(y / 100 * (P.H - 1) * 16)] for x, y in pts], np.int32)
        cv2.polylines(im, [q], False, 0, th, cv2.LINE_AA, shift=4)
    return im


def point_tokens(x, y, mode):
    if mode == 'ptr':
        c, fx, fy = P.cell_of(x, y)
        return [P.SPECIAL + c, P.SPECIAL + P.NCELL + fx, P.SPECIAL + P.NCELL + P.PF + fy]
    if mode in P.SINGLE:
        return [P.SPECIAL + P.quant(v, P.SINGLE[mode]) for v in (x, y)]
    out = []
    for v in (x, y):
        q = P.quant(v)
        out += [P.SPECIAL + q // P.FINE, P.SPECIAL + P.COARSE + q % P.FINE]
    return out


def per_point(mode):
    return 3 if mode == 'ptr' else 2 if mode in P.SINGLE else 4


def encode(objs, mode):
    toks = [P.BOS]
    for pts, _ in objs:
        toks.append(P.LINE)
        for x, y in pts:
            toks += point_tokens(x, y, mode)
    return toks + [P.EOS]


def component_range(mode, k):
    """점 안 k번째 토큰의 허용 범위 [lo, hi)."""
    S = P.SPECIAL
    if mode == 'ptr':
        return [(S, S + P.NCELL), (S + P.NCELL, S + P.NCELL + P.PF), (S + P.NCELL + P.PF, S + P.NCELL + 2 * P.PF)][k]
    if mode in P.SINGLE:
        return (S, S + P.SINGLE[mode])
    return (S, S + P.COARSE) if k % 2 == 0 else (S + P.COARSE, S + P.COARSE + P.FINE)


class Grammar:
    """시작 → LINE → 점(2개 이상) → [점 | LINE | EOS]."""

    def __init__(self, mode):
        self.mode, self.k, self.n, self.started = mode, 0, 0, False

    def mask(self):
        m = torch.full((P.vocab(self.mode),), float('-inf'))
        if not self.started:
            m[P.LINE] = 0
            return m
        lo, hi = component_range(self.mode, self.k)
        m[lo:hi] = 0
        if self.k == 0 and self.n >= 2:
            m[P.LINE] = m[P.EOS] = 0
        return m

    def push(self, t):
        if t == P.LINE:
            self.started, self.k, self.n = True, 0, 0
        elif t != P.EOS:
            self.k += 1
            if self.k == per_point(self.mode):
                self.k, self.n = 0, self.n + 1


def decode(toks, mode):
    objs, cur, i = [], None, 0
    pp = per_point(mode)
    while i < len(toks):
        t = toks[i]
        if t == P.LINE:
            cur = []
            objs.append(cur)
            i += 1
            continue
        if t in (P.BOS, P.EOS) or cur is None:
            i += 1
            continue
        g = toks[i:i + pp]
        if len(g) < pp:
            break
        S = P.SPECIAL
        if mode == 'ptr':
            cur.append(P.point_of(g[0] - S, g[1] - S - P.NCELL, g[2] - S - P.NCELL - P.PF))
        elif mode in P.SINGLE:
            cur.append(tuple(P.dequant(v - S, P.SINGLE[mode]) for v in g))
        else:
            cur.append(tuple(P.dequant((g[2 * a] - S) * P.FINE + g[2 * a + 1] - S - P.COARSE) for a in range(2)))
        i += pp
    return [o for o in objs if len(o) >= 2]


@torch.no_grad()
def generate(net, img):
    g, toks = Grammar(net.mode), [P.BOS]
    mem = net.memory(img[None])
    while len(toks) < MAXLEN:
        T = len(toks)
        x = net.embed(torch.tensor(toks)[None], mem)
        causal = torch.triu(torch.full((T, T), float('-inf')), 1)
        lg = net.logits(net.norm(net.dec(x, mem, tgt_mask=causal, tgt_is_causal=True)), mem)[0, -1]
        t = int((lg + g.mask()).argmax())
        toks.append(t)
        g.push(t)
        if t == P.EOS:
            break
    return toks


def px(a, b):
    return math.hypot((a[0] - b[0]) * 19.2, (a[1] - b[1]) * 10.8)


def poly_len(pts):
    return sum(px(a, b) for a, b in zip(pts, pts[1:]))


def poly_err(t, p):
    """점 대응 평균 오차(px): 짧은 쪽 점 수만큼 순서대로(방향 둘 중 작은 쪽), 남는 점은 가장 가까운 점까지."""
    def one(a, b):
        n = min(len(a), len(b))
        e = [px(a[i], b[i]) for i in range(n)]
        e += [min(px(q, r) for r in a) for q in b[n:]] + [min(px(q, r) for r in b) for q in a[n:]]
        return float(np.mean(e))
    return min(one(t, p), one(t, p[::-1]))


def copy_rate(net, n, seed):
    """교사 강제: 같은 축 바로 앞 좌표와 정답이 다른 자리에서 예측이 앞 값을 고른 비율과 맞힌 비율."""
    rng = np.random.default_rng(seed)
    copies = hits = total = 0
    mode = net.mode
    net.eval()
    with torch.no_grad():
        for _ in range(n):
            objs = sample(rng)
            img = torch.from_numpy(render(objs)).float()[None, None] / 255
            tok = torch.tensor([encode(objs, mode)])
            pred = net(img, tok[:, :-1]).argmax(-1)[0].tolist()
            tgt = tok[0, 1:].tolist()
            if mode == 'ptr':
                lo, hi = P.SPECIAL, P.SPECIAL + P.NCELL                 # 칸 토큰(점마다 하나): 앞 점의 칸
                pos = [j for j, v in enumerate(tgt) if lo <= v < hi]
                pairs = zip(pos, pos[1:])
            else:
                lo, hi = component_range(mode, 0)                       # 거친 칸(two) 또는 수(single): 같은 축 = 2칸 앞
                pos = [j for j, v in enumerate(tgt) if lo <= v < hi]
                pairs = zip(pos, pos[2:])
            for a, b in pairs:
                if tgt[b] != tgt[a]:
                    total += 1
                    copies += pred[b] == tgt[a]
                    hits += pred[b] == tgt[b]
    net.train()
    return dict(copy=copies / max(total, 1), hit=hits / max(total, 1), n=total)


def evaluate(net, n, seed):
    from scipy.optimize import linear_sum_assignment
    rng = np.random.default_rng(seed)
    errs, ratios, count_ok = [], [], 0
    net.eval()
    for _ in range(n):
        objs = sample(rng)
        truth = [pts for pts, _ in objs]
        img = torch.from_numpy(render(objs)).float()[None] / 255
        pred = decode(generate(net, img), net.mode)
        count_ok += len(pred) == len(truth)
        if pred:
            cost = np.array([[poly_err(t, p) for p in pred] for t in truth])
            r, c = linear_sum_assignment(cost)
            errs += cost[r, c].tolist()
            ratios += [poly_len(pred[j]) / poly_len(truth[i]) for i, j in zip(r, c) if poly_len(truth[i]) > 100]
        errs += [1e4] * (len(truth) - min(len(truth), len(pred)))
    net.train()
    e, rt = np.array(errs), np.array(ratios)
    return dict(median_px=float(np.median(e)), within20=float(np.mean(e <= 20)), within50=float(np.mean(e <= 50)),
                count_correct=count_ok / n, collapsed=float(np.mean(rt < 0.3)) if len(rt) else None,
                length_ratio_median=float(np.median(rt)) if len(rt) else None)


def batch(rng, n, mode):
    data = [sample(rng) for _ in range(n)]
    seqs = [encode(o, mode) for o in data]
    L = max(map(len, seqs))
    tok = torch.full((n, L), P.EOS, dtype=torch.long)
    mask = torch.zeros((n, L), dtype=torch.bool)
    for i, s in enumerate(seqs):
        tok[i, :len(s)] = torch.tensor(s)
        mask[i, :len(s)] = True
    img = torch.from_numpy(np.stack([render(o) for o in data])).float()[:, None] / 255
    return img, tok, mask


def run(mode, steps, bs, seed, eval_n, eval_every):
    torch.manual_seed(seed)
    rng = np.random.default_rng(seed)
    net = P.Net(mode, maxlen=MAXLEN)
    opt = torch.optim.AdamW(net.parameters(), lr=3e-4)
    hist, t0 = [], time.time()
    for step in range(1, steps + 1):
        img, tok, mask = batch(rng, bs, mode)
        loss = P.loss_fn(net(img, tok[:, :-1]), tok[:, 1:], mask[:, 1:], mode)
        opt.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(net.parameters(), 1.0)
        opt.step()
        if step % eval_every == 0 or step == steps:
            row = dict(step=step, loss=float(loss), seconds=round(time.time() - t0, 1), **evaluate(net, eval_n, 12345),
                       **{'copy_' + k: v for k, v in copy_rate(net, 60, 777).items()})
            hist.append(row)
            print(mode, json.dumps(row, ensure_ascii=False), flush=True)
    return hist


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--modes', nargs='+', default=['two', 'two_w', 'ptr'])
    p.add_argument('--steps', type=int, default=3000)
    p.add_argument('--bs', type=int, default=32)
    p.add_argument('--seed', type=int, default=0)
    p.add_argument('--eval-n', type=int, default=100)
    p.add_argument('--eval-every', type=int, default=1000)
    p.add_argument('--out')
    a = p.parse_args()
    torch.set_num_threads(4)
    res = {m: run(m, a.steps, a.bs, a.seed, a.eval_n, a.eval_every) for m in a.modes}
    if a.out:
        with open(a.out, 'w', encoding='utf-8') as f:
            json.dump(res, f, ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()
