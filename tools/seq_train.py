#!/usr/bin/env python3
"""재설계 학습(2026-10-30, docs/VIDEO-TO-SFA-REDESIGN-2026-10-30.md): 영상 장을 보고 SFA 정답 문장(sfa_tokens)을 한 토큰씩 쓰는 모델.
채점 = 원본 SFA 파일의 다음 토큰과 비교(교사 강제 교차 엔트로피). 좌표·색·굵기 같은 수 칸은 이웃 칸에도 점수를 조금 준다.
생성 때는 문법(sfa_tokens.grammar)이 허용한 토큰만 고르므로 결과는 항상 앱이 여는 SFA다.
사용:
  학습: python seq_train.py train 자료폴더 시험자료폴더 출력폴더 [--minutes 60 --plan-minutes 480] [--yield] (출력폴더에 ckpt.pt가 있으면 이어서)
  그리기: python seq_train.py draw ckpt.pt 자료폴더 시트.jpg [--n 6] [--sfa 출력.sfa]
"""
import argparse
import glob
import json
import math
import os
import random
import sys
import time
import zipfile
import xml.etree.ElementTree as ET

import cv2
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
import torchvision

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sfa_objscore as OS  # noqa: E402
import sfa_tokens as K  # noqa: E402

# 이웃 칸 부드러운 정답을 쓰는 칸과 그 칸의 합법 범위(GPT 검토 10-30: 색 255의 이웃 256·257에 정답 확률이 새던 것).
# 글로우 칸은 반경·두께·알파·색이 섞여 범위가 달라 정확한 칸만 쓴다.
_SOFT_HI = {'coord': K.NUM - 1, 't': K.NUM - 1, 'thick': K.NUM - 1, 'color': 255, 'bg': 255}
SOFT = torch.tensor([f in _SOFT_HI for f in K.FIELDS])
SOFT_HI = torch.tensor([_SOFT_HI.get(f, K.NUM - 1) for f in K.FIELDS])
TOK_EOS = K.TOK['EOS']
SOFT_W = (0.1, 0.25, 0.3, 0.25, 0.1)   # 이웃 칸 -2..+2 (정확한 칸과 반반 섞는다)


class Data:
    """npz 전부를 메모리에. 그림은 입력 크기로 줄여 JPEG(품질 95)로 압축해 둔다(2만 장 × 640×360 원본이면 15GB → 약 1.5GB).
    이미 H.264로 압축된 장이라 JPEG 95의 추가 손실은 작다. 묶음을 만들 때 푼다."""

    def __init__(self, folder, maxlen, in_w, jpeg=True):
        self.in_w, self.in_h = in_w, in_w * 9 // 16
        self.img, self.tok, self.fld, self.meta, self.hwr = [], [], [], [], []
        for p in sorted(glob.glob(os.path.join(folder, '*.npz'))):
            z = np.load(p)
            d = {k: z[k] for k in ('img', 'tok', 'fld', 'off', 'pos')}   # npz는 꺼낼 때마다 배열 전체를 다시 푼다 → 파일마다 한 번만(10-30: 장마다 풀어 1.5만 장 읽기가 30분 넘게 걸림)
            meta = json.loads(str(z['meta']))
            off = d['off']
            for i in range(len(off) - 1):
                if off[i + 1] - off[i] > maxlen:
                    continue
                im = d['img'][i]
                if im.shape[1] != in_w:
                    im = cv2.resize(im, (self.in_w, self.in_h), interpolation=cv2.INTER_AREA)
                if jpeg:
                    im = cv2.imencode('.jpg', im[..., ::-1], [cv2.IMWRITE_JPEG_QUALITY, 95])[1]
                self.img.append(im)
                self.tok.append(d['tok'][off[i]:off[i + 1]].astype(np.int64))
                self.fld.append(d['fld'][off[i]:off[i + 1]].astype(np.int64))
                self.meta.append(dict(meta, pos=int(d['pos'][i])))
                self.hwr.append(float(meta.get('hwr', 0.5625)))
        self.ntok = sum(len(t) for t in self.tok)

    def __len__(self):
        return len(self.img)

    def image(self, i):
        im = self.img[i]
        return cv2.imdecode(im, cv2.IMREAD_COLOR)[..., ::-1] if im.ndim == 1 else im

    def batch(self, idx):
        L = max(len(self.tok[i]) for i in idx)
        tok = torch.full((len(idx), L), K.TOK['PAD'], dtype=torch.long)
        fld = torch.zeros((len(idx), L), dtype=torch.long)
        for b, i in enumerate(idx):
            tok[b, :len(self.tok[i])] = torch.from_numpy(self.tok[i])
            fld[b, :len(self.fld[i])] = torch.from_numpy(self.fld[i])
        img = torch.from_numpy(np.ascontiguousarray(np.stack([self.image(i) for i in idx]))).permute(0, 3, 1, 2).float() / 255
        hwr = torch.tensor([self.hwr[i] for i in idx], dtype=torch.float32)
        return img, tok, fld, hwr


class Net(nn.Module):
    def __init__(self, d=384, layers=6, heads=6, maxlen=2048, backbone='resnet34', pretrained=True, stride=16):
        super().__init__()
        ctor = getattr(torchvision.models, backbone)
        try:
            bb = ctor(weights='DEFAULT' if pretrained else None)
        except Exception as e:  # 내려받기 실패 → 처음부터(기록만)
            print('사전학습 가중치 못 받음:', type(e).__name__, flush=True)
            bb = ctor(weights=None)
        self.enc8 = nn.Sequential(bb.conv1, bb.bn1, bb.relu, bb.maxpool, bb.layer1, bb.layer2)   # 1/8, 128채널
        self.enc16 = bb.layer3                                                                  # 1/16, 256채널
        self.proj = nn.Conv2d(256, d, 1)
        self.stride = stride
        if stride == 8:   # 1/8 칸(640폭 → 80×45)에 1/16 특징을 올려 더한다 — 선 위치를 더 촘촘히(테스트의 20×11칸은 너무 성겼다)
            self.proj8 = nn.Conv2d(128, d, 1)
        self.ratio = nn.Linear(1, d)   # 화면 비율(높이/폭) — 입력은 늘여 넣으므로 원이 타원으로 보이는 정도를 알려 준다
        self.row = nn.Embedding(128, d)
        self.col = nn.Embedding(128, d)
        self.emb = nn.Embedding(K.VOCAB, d)
        self.fld_emb = nn.Embedding(len(K.FIELDS), d)   # 입력 토큰의 칸 종류(같은 수라도 좌표·색 구분)
        self.pos = nn.Embedding(maxlen + 1, d)
        layer = nn.TransformerDecoderLayer(d, heads, 4 * d, dropout=0.1, batch_first=True, norm_first=True)
        self.dec = nn.TransformerDecoder(layer, layers)
        self.norm = nn.LayerNorm(d)
        self.head = nn.Linear(d, K.VOCAB)
        self.maxlen = maxlen
        self.grad_ckpt = False
        self.register_buffer('mean', torch.tensor([0.485, 0.456, 0.406]).view(1, 3, 1, 1))
        self.register_buffer('std', torch.tensor([0.229, 0.224, 0.225]).view(1, 3, 1, 1))

    def memory(self, img, hwr):
        f8 = self.enc8((img - self.mean) / self.std)
        f = self.proj(self.enc16(f8))
        if self.stride == 8:
            f = self.proj8(f8) + F.interpolate(f, size=f8.shape[-2:], mode='bilinear', align_corners=False)
        B, C, H, W = f.shape
        pe = self.row.weight[:H, None, :] + self.col.weight[None, :W, :]
        r = self.ratio(torch.log(hwr.view(-1, 1) / 0.5625))[:, None, :]
        return f.flatten(2).transpose(1, 2) + pe.reshape(H * W, C)[None] + r

    def step(self, mem, tok, fld):
        T = tok.shape[1]
        x = self.emb(tok) + self.fld_emb(fld) + self.pos.weight[:T][None]
        causal = torch.triu(torch.full((T, T), float('-inf'), device=tok.device), 1)
        pad = tok == K.TOK['PAD']
        if self.grad_ckpt and self.training:   # 메모리 부족 대책: 층마다 중간값을 버리고 역전파 때 다시 계산(약 30% 느림)
            from torch.utils.checkpoint import checkpoint
            h = x
            for ly in self.dec.layers:
                h = checkpoint(ly, h, mem, tgt_mask=causal, tgt_key_padding_mask=pad, tgt_is_causal=True, use_reentrant=False)
        else:
            h = self.dec(x, mem, tgt_mask=causal, tgt_key_padding_mask=pad, tgt_is_causal=True)
        return self.head(self.norm(h))

    def forward(self, img, tok, fld, hwr):
        return self.step(self.memory(img, hwr), tok, fld)


def loss_fn(logits, tgt, fld):
    """다음 토큰 채점. 수 칸(좌표·T·굵기·색)은 정확한 칸 50% + 이웃 ±2칸 분포 50%(그 칸의 합법 범위 안에서만, 무게 다시 맞춤).
    돌려줌: 평균 손실, 맞힘 비율, 토큰 수(검증을 토큰 수로 가중 합산하려고)."""
    logp = F.log_softmax(logits.float(), -1)
    mask = tgt != K.TOK['PAD']
    exact = -logp.gather(-1, tgt[..., None])[..., 0]
    soft_on = SOFT.to(tgt.device)[fld] & (tgt >= K.OFF)
    hi = SOFT_HI.to(tgt.device)[fld]
    v = tgt - K.OFF
    soft = torch.zeros_like(exact)
    wsum = torch.zeros_like(exact)
    for k, w in zip(range(-2, 3), SOFT_W):
        ok = ((v + k) >= 0) & ((v + k) <= hi)
        j = (tgt + k).clamp(K.OFF, K.VOCAB - 1)
        soft = soft - w * ok * logp.gather(-1, j[..., None])[..., 0]
        wsum = wsum + w * ok
    soft = soft / wsum.clamp_min(1e-6)
    per = torch.where(soft_on, 0.5 * exact + 0.5 * soft, exact)
    m = mask.float()
    n = m.sum()
    acc = ((logits.argmax(-1) == tgt) & mask).float().sum() / n
    return (per * m).sum() / n, acc, n


def allowed_mask(al, dev):
    specs, lo, hi, _ = al
    m = torch.full((K.VOCAB,), float('-inf'), device=dev)
    for s in specs:
        m[s] = 0
    if hi >= lo:
        m[K.OFF + lo:K.OFF + hi + 1] = 0
    return m


class Cache:
    """디코더 증분 계산(KV 캐시). nn.TransformerDecoderLayer(norm_first, batch_first)와 같은 가중치·식을 한 토큰씩."""

    def __init__(self, net, mem):
        self.net = net
        self.kv = []
        self.mkv = []
        for ly in net.dec.layers:
            W, b = ly.multihead_attn.in_proj_weight, ly.multihead_attn.in_proj_bias
            d = W.shape[1]
            self.mkv.append((F.linear(mem, W[d:2 * d], b[d:2 * d]), F.linear(mem, W[2 * d:], b[2 * d:])))
            self.kv.append(None)
        self.t = 0

    @staticmethod
    def _attn(mha, q_in, k, v):
        W, b = mha.in_proj_weight, mha.in_proj_bias
        d = W.shape[1]
        h = mha.num_heads
        q = F.linear(q_in, W[:d], b[:d])
        B, T, _ = q.shape
        sp = lambda x: x.view(B, x.shape[1], h, d // h).transpose(1, 2)  # noqa: E731
        o = F.scaled_dot_product_attention(sp(q), sp(k), sp(v))
        return mha.out_proj(o.transpose(1, 2).reshape(B, T, d))

    def step(self, tok, fld):
        net = self.net
        x = net.emb.weight[tok][None, None] + net.fld_emb.weight[fld][None, None] + net.pos.weight[self.t][None, None]
        self.t += 1
        for li, ly in enumerate(net.dec.layers):
            W, b = ly.self_attn.in_proj_weight, ly.self_attn.in_proj_bias
            d = W.shape[1]
            y = ly.norm1(x)
            k, v = F.linear(y, W[d:2 * d], b[d:2 * d]), F.linear(y, W[2 * d:], b[2 * d:])
            if self.kv[li] is not None:
                k, v = torch.cat([self.kv[li][0], k], 1), torch.cat([self.kv[li][1], v], 1)
            self.kv[li] = (k, v)
            x = x + self._attn(ly.self_attn, y, k, v)
            x = x + self._attn(ly.multihead_attn, ly.norm2(x), *self.mkv[li])
            x = x + ly.linear2(ly.activation(ly.linear1(ly.norm3(x))))
        return net.head(net.norm(x))[0, 0]


@torch.no_grad()
def generate(net, img, hwr, maxlen=None, temp=0.0):
    """문법 강제 생성(한 장, KV 캐시)."""
    dev = img.device
    maxlen = maxlen or net.maxlen
    mem = net.memory(img[None], torch.tensor([hwr], dtype=torch.float32, device=dev))
    cache = Cache(net, mem)
    g = K.grammar()
    al = next(g)
    toks, flds = [], []
    while len(toks) < maxlen:
        if toks:
            lg = cache.step(toks[-1], flds[-1])
        else:
            lg = torch.zeros(K.VOCAB, device=dev)
        lg = lg + allowed_mask(al, dev)
        if len(toks) >= maxlen - 64 and TOK_EOS in al[0]:   # 길이 한도 가까우면 끝낼 수 있는 자리에서 끝낸다
            lg = torch.full_like(lg, float('-inf'))
            lg[TOK_EOS] = 0
        t = int(torch.multinomial(F.softmax(lg / temp, -1), 1)) if temp > 0 else int(lg.argmax())
        toks.append(t)
        flds.append(K.FID[al[3]] if t >= K.OFF else K.FID['spec'])
        try:
            al = g.send(t)
        except StopIteration:
            return toks, True
    return toks, False


def lr_at(step, prog, base, warm=500):
    """예열(걸음) 뒤 진행률(쓴 시간 / 계획 시간) 기준 코사인 — 끊어서 돌려도 계획대로 이어진다."""
    w = min(1.0, (step + 1) / warm)
    return base * w * (0.05 + 0.95 * 0.5 * (1 + math.cos(math.pi * min(1.0, prog))))


def make_batches(ds, max_n, budget):
    """길이가 비슷한 장끼리 묶되 한 묶음의 토큰 합이 budget을 넘지 않게(긴 장이 몰려도 메모리 일정)."""
    idx = list(range(len(ds)))
    random.shuffle(idx)
    out = []
    for c0 in range(0, len(idx), max_n * 64):
        chunk = sorted(idx[c0:c0 + max_n * 64], key=lambda k: len(ds.tok[k]))
        cur, L = [], 0
        for k in chunk:
            l = len(ds.tok[k])
            if l > budget:   # 토큰 한도보다 긴 장은 뺀다(메모리 부족으로 한도가 줄었을 때)
                continue
            if cur and (len(cur) >= max_n or max(L, l) * (len(cur) + 1) > budget):
                out.append(cur)
                cur, L = [], 0
            cur.append(k)
            L = max(L, l)
        if cur:
            out.append(cur)
    random.shuffle(out)
    return out


def train(a):
    import vec_train as VT   # 양보 모드·저장 재시도(Windows 파일 잠금)를 같이 쓴다
    torch.manual_seed(0)
    random.seed(0)
    dev = 'cuda' if torch.cuda.is_available() else 'cpu'
    if dev == 'cpu':
        torch.set_num_threads(os.cpu_count() or 4)
    if a.yield_:
        VT.low_priority()
        if dev == 'cuda':
            torch.cuda.set_per_process_memory_fraction(0.75)
    yl = VT.Yielder(a.yield_)
    os.makedirs(a.out, exist_ok=True)
    ck = os.path.join(a.out, 'ckpt.pt')
    cfg = dict(d=a.d, layers=a.layers, heads=a.heads, maxlen=a.maxlen, backbone=a.backbone, in_w=a.in_w, stride=a.stride)
    st = dict(step=0, best=1e9, done_min=0.0, plan_min=a.plan_minutes or a.minutes, budget=a.tok_budget, grad_ckpt=a.grad_ckpt)
    saved = torch.load(ck, map_location='cpu', weights_only=False) if os.path.exists(ck) else None
    if saved:
        cfg = saved['cfg']   # 이어하기: 처음 정한 모델 크기·입력 크기·계획 그대로(명령줄 값보다 우선)
        st.update(saved['state'])
        if a.plan_minutes > st['plan_min']:   # 계획을 더 길게 다시 정함
            st['plan_min'] = a.plan_minutes
        elif not a.plan_minutes and st['done_min'] + a.minutes > st['plan_min']:
            # 계획을 안 정했으면 이번 실행 시간만큼 늘린다(5060을 여러 번 나눠 돌릴 때 '이미 100%'로 끝나지 않게).
            # 재시작이 아니라 계획 분모 연장: 진행률이 줄어든 만큼 코사인 중간 위치에서 이어진다(GPT 2차: 60분씩 늘리면 시작 학습률 0.53→0.29→0.19배)
            st['plan_min'] = st['done_min'] + a.minutes
            print(f"계획을 {st['plan_min']:.0f}분으로 늘림(이번 실행 {a.minutes:.0f}분, 학습률은 늘어난 계획의 코사인 위치에서)", flush=True)
    t0 = time.time()
    tr = Data(a.data, cfg['maxlen'], cfg['in_w'])
    va = Data(a.val, cfg['maxlen'], cfg['in_w'])
    print(f'자료 학습 {len(tr)}장 {tr.ntok}토큰 · 시험 {len(va)}장 ({time.time() - t0:.0f}초)', flush=True)
    net = Net(cfg['d'], cfg['layers'], cfg['heads'], cfg['maxlen'], cfg['backbone'], pretrained=not saved, stride=cfg.get('stride', 16)).to(dev)
    opt = torch.optim.AdamW(net.parameters(), lr=a.lr, weight_decay=0.01)
    net.grad_ckpt = bool(st.get('grad_ckpt'))
    if saved:
        net.load_state_dict(saved['model'])
        opt.load_state_dict(saved['opt'])
        print(f"이어하기: {st['step']}걸음, 진행 {st['done_min']:.0f}/{st['plan_min']:.0f}분, best {st['best']:.4f}", flush=True)
    print('변수', sum(p.numel() for p in net.parameters()) // 1000, '천 · 설정', cfg, flush=True)
    amp = dev == 'cuda'
    dt = torch.bfloat16 if amp and torch.cuda.get_device_capability(0)[0] >= 8 else torch.float16
    scaler = torch.amp.GradScaler('cuda', enabled=amp and dt == torch.float16)
    if saved:   # 이어하기: 배율·난수 상태도(GPT 검토 10-30)
        if saved.get('scaler'):
            scaler.load_state_dict(saved['scaler'])
        rs = saved.get('rng')
        if rs:
            random.setstate(rs['py'])
            torch.set_rng_state(rs['torch'])
            if dev == 'cuda' and rs.get('cuda') is not None:
                torch.cuda.set_rng_state(rs['cuda'])
    base_lr = st.setdefault('base_lr', a.lr)   # 처음 정한 학습률(이어하기에서 명령줄 값으로 바뀌지 않게)
    if not len(tr):
        raise SystemExit('학습 자료 0장 — 자료 폴더 확인')
    log = os.path.join(a.out, 'log.jsonl')
    t_sess = time.time()
    p_sess = yl.paused
    done0 = st['done_min']
    # 검증 대상 고정: 시험 자료에서 고르게 val_n장, 묶음은 처음 토큰 한도로(학습 한도가 줄어도 같은 대상, GPT 검토 10-30)
    v_idx = sorted(set(np.linspace(0, len(va) - 1, min(a.val_n, len(va))).astype(int).tolist())) if len(va) else []
    v_batches = make_batches_fixed(va, a.max_batch, a.tok_budget, v_idx)
    g_idx = v_idx[::max(1, len(v_idx) // a.gen_n)][:a.gen_n]   # 생성 채점용 고정 장

    def active_min():
        return (time.time() - t_sess - (yl.paused - p_sess)) / 60

    def save_ckpt():
        st['done_min'] = done0 + active_min()
        rng = dict(py=random.getstate(), torch=torch.get_rng_state(), cuda=torch.cuda.get_rng_state() if dev == 'cuda' else None)
        VT.save(dict(model=net.state_dict(), opt=opt.state_dict(), scaler=scaler.state_dict(), rng=rng, cfg=cfg, state=dict(st)), ck)

    def val_batch(b):
        """한 묶음의 (손실 합, 맞힘 합, 토큰 수, 못 잰 장 수). 메모리 부족이면 오류 처리를 벗어난 뒤 반으로 나눠 다시(GPT 2차)."""
        oom_ = False
        try:
            im, tk, fd, hr = (x.to(dev) for x in va.batch(b))
            with torch.autocast(dev, dtype=dt, enabled=amp):
                lg = net(im, tk[:, :-1], fd[:, :-1], hr)
            l_, c_, n_ = loss_fn(lg, tk[:, 1:], fd[:, 1:])
            if not torch.isfinite(l_):
                return 0.0, 0.0, 0.0, len(b)
            return l_.item() * n_.item(), c_.item() * n_.item(), n_.item(), 0
        except torch.OutOfMemoryError:
            oom_ = True
        im = tk = fd = hr = lg = None
        if dev == 'cuda':
            torch.cuda.empty_cache()
        if len(b) == 1:
            return 0.0, 0.0, 0.0, 1
        x, y = val_batch(b[:len(b) // 2]), val_batch(b[len(b) // 2:])
        return tuple(p + q for p, q in zip(x, y))

    def validate():
        """토큰 수로 가중한 시험 손실·맞힘. 못 잰 장이 있으면 불완전(best 갱신 안 함)."""
        net.eval()
        tl = tc = tn = 0.0
        bad = 0
        try:
            with torch.no_grad():
                for b in v_batches:
                    l_, c_, n_, f_ = val_batch(b)
                    tl, tc, tn, bad = tl + l_, tc + c_, tn + n_, bad + f_
        finally:
            net.train()
        return (tl / tn if tn else float('nan')), (tc / tn if tn else 0.0), int(tn), bad

    def gen_eval():
        """고정 장을 실제로 그려 보고 오브젝트 채점(GPT 검토 10-30: 다음 토큰 맞힘과 실제 생성은 다르다)."""
        net.eval()
        sums = dict(ans=0, pred=0, match=0, link_tp=0, link_pred=0, link_ans=0, fill_tp=0, fill_pred=0, fill_ans=0, perfect=0, done=0, frames=0, oom=0)
        t0_ = time.time()
        try:
            for i in g_idx:
                gen_one(i, sums)
        finally:
            net.train()
            if dev == 'cuda':
                torch.cuda.empty_cache()
        return dict(gen_recall=sums['match'] / max(sums['ans'], 1), gen_precision=sums['match'] / max(sums['pred'], 1),
                    gen_link_f1=OS.f1(sums['link_tp'], sums['link_pred'], sums['link_ans']),
                    gen_fill_f1=OS.f1(sums['fill_tp'], sums['fill_pred'], sums['fill_ans']),
                    gen_perfect=sums['perfect'], gen_done=sums['done'], gen_frames=sums['frames'], gen_oom=sums['oom'],
                    gen_sec=round(time.time() - t0_))

    def gen_one(i, sums):
        """한 장 생성 채점. 메모리 부족이면 그 장만 건너뛰고 센다(학습은 계속)."""
        try:
            img = torch.from_numpy(np.ascontiguousarray(va.image(i))).permute(2, 0, 1).float().to(dev) / 255
            with torch.autocast(dev, dtype=dt, enabled=amp):
                toks, done = generate(net, img, va.hwr[i], cfg['maxlen'])
            sc = OS.score(K.decode(toks), K.decode(va.tok[i].tolist()), hwr=va.hwr[i])
            for k_ in ('ans', 'pred', 'match', 'link_tp', 'link_pred', 'link_ans', 'fill_tp', 'fill_pred', 'fill_ans'):
                sums[k_] += sc[k_]
            sums['perfect'] += sc['perfect']
            sums['done'] += done
            sums['frames'] += 1
        except torch.OutOfMemoryError:
            sums['oom'] += 1

    batches = []
    run, racc = [], []
    last_val = last_save = last_gen = time.time()
    oom = skipped = 0
    while active_min() < a.minutes and done0 + active_min() < st['plan_min']:
        yl.tick()
        if not batches:
            batches = make_batches(tr, a.max_batch, st['budget'])
            if not batches:
                raise SystemExit(f"토큰 한도 {st['budget']} 안에 드는 학습 장이 없음")
        b = batches.pop()
        prog = (done0 + active_min()) / st['plan_min']
        for g in opt.param_groups:
            g['lr'] = lr_at(st['step'], prog, base_lr)
        img = tok = fld = hwr = lg = loss = acc = None
        unscaled = False
        try:   # GPU로 옮기기부터 한 걸음 전체를 보호(GPT 검토 10-30)
            img, tok, fld, hwr = (x.to(dev) for x in tr.batch(b))
            with torch.autocast(dev, dtype=dt, enabled=amp):
                lg = net(img, tok[:, :-1], fld[:, :-1], hwr)
            loss, acc, _ = loss_fn(lg, tok[:, 1:], fld[:, 1:])
            if not torch.isfinite(loss):
                skipped += 1
                opt.zero_grad(set_to_none=True)
                continue
            opt.zero_grad(set_to_none=True)
            scaler.scale(loss).backward()
            scaler.unscale_(opt)
            unscaled = True
            nn.utils.clip_grad_norm_(net.parameters(), 1.0)
            scaler.step(opt)
            scaler.update()
        except torch.OutOfMemoryError:
            # 메모리 부족: 그래프를 붙든 텐서를 모두 놓고 이 묶음을 버린다(양보 모드에서 게임이 메모리를 잡은 경우면 1분 쉬고, 쉰 시간은 학습 시간에서 뺀다)
            img = tok = fld = hwr = lg = loss = acc = None
            opt.zero_grad(set_to_none=True)
            if scaler.is_enabled() and unscaled:
                scaler.update()   # unscale_ 뒤(step 중)에 넘친 경우만 — inf 검사가 기록돼 update가 안전. 그 전 단계면 아무것도 하지 않는다(GPT 2차: 무조건 update는 AssertionError)
            if dev == 'cuda':
                torch.cuda.empty_cache()
            oom += 1
            if not net.grad_ckpt:   # 1단계: 체크포인팅 켜기(긴 장도 그대로 학습)
                net.grad_ckpt = st['grad_ckpt'] = True
                print(time.strftime('%H:%M'), '메모리 부족 → 체크포인팅 켬(느려지지만 메모리 크게 줄임)', flush=True)
            else:                   # 2단계: 토큰 한도 줄이기(한도보다 긴 장은 학습에서 빠진다)
                st['budget'] = max(1024, int(st['budget'] * 0.8))
                drop = sum(len(t) > st['budget'] for t in tr.tok)
                print(time.strftime('%H:%M'), f'메모리 부족 → 토큰 한도 {st["budget"]} (이보다 긴 장 {drop}/{len(tr)} 빠짐)', flush=True)
            batches = []
            if a.yield_:
                time.sleep(60)
                yl.paused += 60
            continue
        st['step'] += 1
        run.append(loss.item())
        racc.append(acc.item())
        if st['step'] % a.log_every == 0:
            mem = f' GPU {torch.cuda.max_memory_allocated() / 2**30:.1f}GB' if dev == 'cuda' else ''
            print(f"{st['step']} 손실 {np.mean(run):.3f} 맞힘 {np.mean(racc) * 100:.1f}% 진행 {prog * 100:.1f}% "
                  f"학습률 {opt.param_groups[0]['lr']:.2e} ({active_min():.1f}분){mem}", flush=True)
            run, racc = [], []
        if time.time() - last_val > a.val_minutes * 60:
            last_val = time.time()
            vl, vc, n, vbad = validate()
            rec = dict(step=st['step'], val=vl, val_acc=vc, val_tokens=n, val_failed=vbad, minutes=done0 + active_min(), prog=prog,
                       oom=oom, skipped=skipped, budget=st['budget'], grad_ckpt=net.grad_ckpt, paused_min=yl.paused / 60)
            if n and not vbad and vl < st['best']:   # 못 잰 장이 있으면 best 안 바꿈(GPT 2차)
                st['best'] = vl
                VT.save(dict(model=net.state_dict(), cfg=cfg, step=st['step'], val=vl), os.path.join(a.out, 'best.pt'))
            save_ckpt()   # 생성 채점 전에 저장(GPT 2차: 생성 중 문제가 생겨도 학습 상태는 남게)
            last_save = time.time()
            if a.gen_minutes and time.time() - last_gen > a.gen_minutes * 60:
                last_gen = time.time()
                rec.update(gen_eval())
            print('검증', rec, flush=True)
            with open(log, 'a', encoding='utf-8') as fh:
                fh.write(json.dumps(rec) + '\n')
        elif time.time() - last_save > a.save_minutes * 60:
            save_ckpt()
            last_save = time.time()
    vl, vc, n, vbad = validate()
    rec = dict(step=st['step'], val=vl, val_acc=vc, val_tokens=n, val_failed=vbad, final=True)
    if n and not vbad and vl < st['best']:
        st['best'] = vl
        VT.save(dict(model=net.state_dict(), cfg=cfg, step=st['step'], val=vl), os.path.join(a.out, 'best.pt'))
    save_ckpt()
    if a.gen_minutes:
        rec.update(gen_eval())
    print('마지막 검증', rec, flush=True)
    with open(log, 'a', encoding='utf-8') as fh:
        fh.write(json.dumps(rec) + '\n')
    print(f"끝 {st['step']}걸음 · 진행 {st['done_min']:.0f}/{st['plan_min']:.0f}분 · best {st['best']:.4f} · 메모리 부족 {oom} · 건너뜀 {skipped}", flush=True)


def make_batches_fixed(ds, max_n, budget, idx):
    """검증용: 고정 장 목록, 같은 묶음 규칙(무작위 없음). 한도보다 긴 장도 혼자 한 묶음으로 넣는다(검증 대상이 바뀌지 않게)."""
    idx = sorted(idx, key=lambda k: len(ds.tok[k]))
    out, cur, L = [], [], 0
    for k in idx:
        l = len(ds.tok[k])
        if cur and (len(cur) >= max_n or max(L, l) * (len(cur) + 1) > budget):
            out.append(cur)
            cur, L = [], 0
        cur.append(k)
        L = max(L, l)
    if cur:
        out.append(cur)
    return out


def load(path, dev='cpu'):
    s = torch.load(path, map_location=dev, weights_only=False)
    c = s['cfg']
    net = Net(c['d'], c['layers'], c['heads'], c['maxlen'], c['backbone'], pretrained=False, stride=c.get('stride', 16))
    net.load_state_dict(s['model'])
    return net.eval().to(dev), c


def seq_xml(hwr, bg='-1'):
    return ET.Element('Sequence', dict(Name='seq', HeightWidthRatio=repr(hwr), FrameCount='1', BackgroundColor=bg))


def draw(a):
    import sfa_render as R
    dev = 'cuda' if torch.cuda.is_available() else 'cpu'
    net, c = load(a.ckpt, dev)
    ds = Data(a.data, c['maxlen'], c['in_w'])
    rng = random.Random(a.seed)
    pick = rng.sample(range(len(ds)), min(a.n, len(ds)))
    R.PARAMS['pad'] = 0.0
    W = 640
    R.PARAMS['thick_mul'] = W / 1920
    rows = []
    scores = []
    out_seq = None
    ids = K.Ids()
    for k, i in enumerate(pick):
        t0 = time.time()
        img = torch.from_numpy(np.ascontiguousarray(ds.image(i))).permute(2, 0, 1).float().to(dev) / 255
        hwr = ds.hwr[i]
        toks, done = generate(net, img, hwr, c['maxlen'])
        seq = seq_xml(hwr)
        H = max(2, int(round(W * hwr)))   # 보여 줄 때는 파일 비율 그대로
        pred = K.decode(toks, fid=k + 1, pos=k, ids=ids)
        ans = K.decode(ds.tok[i].tolist())
        im_p = R.render_frame(seq, pred, W, H)
        im_a = R.render_frame(seq, ans, W, H)
        src = cv2.resize(ds.image(i), (W, H))
        sc = OS.score(pred, ans, hwr=hwr)                    # 제자리 오브젝트 채점(주 지표)
        sc0 = OS.score(pred, ans, align=True, hwr=hwr)       # 구조 채점(이동·같은 비율로 맞춘 뒤, 보조)
        scores.append(sc)
        f = lambda v: '-' if v is None else f'{v * 100:.0f}%'  # noqa: E731
        print(f'{ds.meta[i]["file"]} 장 {ds.meta[i]["pos"]}: 토큰 {len(toks)}/{len(ds.tok[i])} 끝냄 {done} | '
              f'오브젝트 AI {sc["pred"]} 원본 {sc["ans"]} 맞음 {sc["match"]} (원본 중 {f(sc["recall"])}, AI 중 {f(sc["precision"])}) '
              f'점 오차 {"-" if sc["pt_err"] is None else round(sc["pt_err"], 2)} 색 {f(sc["color"])} 굵기 {f(sc["thick"])} '
              f'연결 F1 {f(sc["link_f1"])} 면 F1 {f(sc["fill_f1"])} 순서 {f(sc["order"])} 배경 {sc["bg"]} 만점 {sc["perfect"]} | 구조 맞음 {sc0["match"]} 배율 {sc0["scale"]:.2f} ({time.time() - t0:.0f}초)', flush=True)
        cells = [src.copy(), im_p, im_a]
        for im, lab in zip(cells, ('input video', 'AI made SFA', 'answer SFA')):
            cv2.putText(im, lab, (6, 18), 0, 0.55, (255, 0, 0), 1)
        rows.append(np.hstack(cells))
        if out_seq is None:
            out_seq = seq_xml(hwr)   # 시험용 묶음: 첫 장의 비율(다른 비율 장도 같은 파일에 들어가므로 앱에서 보면 늘어나 보일 수 있다)
        out_seq.append(pred)
    cv2.imwrite(a.sheet, cv2.cvtColor(np.vstack(rows), cv2.COLOR_RGB2BGR))
    S_ = lambda k: sum(x[k] for x in scores)  # noqa: E731
    tot_m, tot_a, tot_p = S_('match'), S_('ans'), S_('pred')
    print(f'합계({len(scores)}장): 원본 오브젝트 {tot_a} 중 맞힘 {tot_m} ({tot_m / max(tot_a, 1) * 100:.1f}%), AI 오브젝트 {tot_p} 중 맞음 {tot_m / max(tot_p, 1) * 100:.1f}%, '
          f'연결 F1 {OS.f1(S_("link_tp"), S_("link_pred"), S_("link_ans")) * 100:.1f}%, 면 F1 {OS.f1(S_("fill_tp"), S_("fill_pred"), S_("fill_ans")) * 100:.1f}%, '
          f'만점 장 {S_("perfect")}')
    print('시트', a.sheet)
    if a.sfa:
        out_seq.set('FrameCount', str(len(pick)))
        with zipfile.ZipFile(a.sfa, 'w', zipfile.ZIP_DEFLATED) as z:
            z.writestr(os.path.splitext(os.path.basename(a.sfa))[0] + '.xml',
                       '<?xml version="1.0" encoding="UTF-8" ?>' + ET.tostring(out_seq, encoding='unicode'))
        print('SFA', a.sfa)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='cmd', required=True)
    t = sub.add_parser('train')
    t.add_argument('data')
    t.add_argument('val')
    t.add_argument('out')
    t.add_argument('--minutes', type=float, default=60, help='이번 실행에서 학습할 시간(양보로 쉰 시간은 빼고 셈)')
    t.add_argument('--plan-minutes', type=float, default=0, help='전체 학습 계획 시간(학습률 계획 기준, 처음 시작할 때만). 0이면 --minutes')
    t.add_argument('--max-batch', type=int, default=16, help='한 묶음 최대 장 수')
    t.add_argument('--tok-budget', type=int, default=12288, help='한 묶음 토큰 한도(가장 긴 장 길이 × 장 수). 메모리 부족이면 자동으로 줄인다')
    t.add_argument('--lr', type=float, default=3e-4)
    t.add_argument('--maxlen', type=int, default=2048)
    t.add_argument('--in-w', type=int, default=640)
    t.add_argument('--stride', type=int, default=8, choices=(8, 16))
    t.add_argument('--d', type=int, default=512)
    t.add_argument('--layers', type=int, default=8)
    t.add_argument('--heads', type=int, default=8)
    t.add_argument('--backbone', default='resnet34')
    t.add_argument('--log-every', type=int, default=50)
    t.add_argument('--val-minutes', type=float, default=20)
    t.add_argument('--save-minutes', type=float, default=10)
    t.add_argument('--val-n', type=int, default=400)
    t.add_argument('--gen-n', type=int, default=20, help='생성 채점에 쓰는 고정 시험 장 수')
    t.add_argument('--gen-minutes', type=float, default=60, help='생성 채점 간격(분). 0이면 안 함')
    t.add_argument('--yield', dest='yield_', action='store_true', help='양보 모드(게임 실행 중이면 멈추거나 천천히)')
    t.add_argument('--grad-ckpt', action='store_true', help='처음부터 체크포인팅(메모리 절약, 느림). 꺼 두면 메모리 부족 때 자동으로 켠다')
    d = sub.add_parser('draw')
    d.add_argument('ckpt')
    d.add_argument('data')
    d.add_argument('sheet')
    d.add_argument('--n', type=int, default=6)
    d.add_argument('--seed', type=int, default=0)
    d.add_argument('--sfa')
    a = ap.parse_args()
    train(a) if a.cmd == 'train' else draw(a)


if __name__ == '__main__':
    main()
