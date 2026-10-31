#!/usr/bin/env python3
"""재설계 학습(2026-10-30, docs/VIDEO-TO-SFA-REDESIGN-2026-10-30.md): 영상 장을 보고 SFA 정답 문장(sfa_tokens)을 한 토큰씩 쓰는 모델.
채점 = 원본 SFA 파일의 다음 토큰과 비교(교사 강제 교차 엔트로피). 좌표·색·굵기 같은 수 칸은 이웃 칸에도 점수를 조금 준다.
생성 때는 문법(sfa_tokens.grammar)이 허용한 토큰만 고르므로 결과는 항상 앱이 여는 SFA다.
사용:
  학습: python seq_train.py train 자료폴더 시험자료폴더 출력폴더 [--minutes 60 --plan-minutes 480] [--yield] (출력폴더에 ckpt.pt가 있으면 이어서)
        해상도 단계(10-31): --stages sd1920,sd1280,sd854 → 1080(20%) → 720(25%) → 480(25%) → 기본 360(30%), 단계마다 앞 단계 30% 섞음.
        단계는 전체 계획(--plan-minutes) 기준이라 처음 시작할 때 전체 계획 시간을 주는 게 맞다. 시험·생성 채점은 항상 기본 입력(360)
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
import seq_judge as J  # noqa: E402

# 이웃 칸 부드러운 정답을 쓰는 칸과 그 칸의 합법 범위(GPT 검토 10-30: 색 255의 이웃 256·257에 정답 확률이 새던 것).
# 글로우 칸은 반경·두께·알파·색이 섞여 범위가 달라 정확한 칸만 쓴다.
_SOFT_HI = {'coord': K.NUM - 1, 't': K.NUM - 1, 'thick': K.NUM - 1, 'color': 255, 'bg': 255}
SOFT = torch.tensor([f in _SOFT_HI for f in K.FIELDS])
SOFT_HI = torch.tensor([_SOFT_HI.get(f, K.NUM - 1) for f in K.FIELDS])
TOK_EOS = K.TOK['EOS']
SOFT_W = (0.1, 0.25, 0.3, 0.25, 0.1)   # 이웃 칸 -2..+2 (정확한 칸과 반반 섞는다)


def _load_npz(job):
    """npz 하나 → [(그림, tok, fld, meta, hwr)]. 고해상도 영상 자료는 풀기가 느려(1080 약 3만 장 17분) 여러 프로세스로 부른다."""
    p, maxlen, in_w, in_h, jpeg = job
    z = np.load(p)
    d = {k: z[k] for k in ('tok', 'fld', 'off', 'pos')}   # npz는 꺼낼 때마다 배열 전체를 다시 푼다 → 파일마다 한 번만(10-30: 장마다 풀어 1.5만 장 읽기가 30분 넘게 걸림)
    meta = json.loads(str(z['meta']))
    if 'vid' in z.files:   # 고해상도 단계 자료(seq_data --video): mp4를 여기서 푼다
        import vec_data as V
        frames = V.decode_video(z['vid'], meta['W'], meta['render_h'])
    else:
        frames = z['img']
    off = d['off']
    out = []
    for i in range(len(off) - 1):
        if off[i + 1] - off[i] > maxlen:
            continue
        im = frames[i]
        if im.shape[:2] != (in_h, in_w):   # 파일 비율로 렌더된 영상 자료는 높이도 다르다
            im = cv2.resize(im, (in_w, in_h), interpolation=cv2.INTER_AREA if im.shape[1] > in_w else cv2.INTER_LINEAR)
        if jpeg:
            im = cv2.imencode('.jpg', im[..., ::-1], [cv2.IMWRITE_JPEG_QUALITY, 95])[1]
        out.append((im, d['tok'][off[i]:off[i + 1]].astype(np.int64), d['fld'][off[i]:off[i + 1]].astype(np.int64),
                    dict(meta, pos=int(d['pos'][i])), float(meta.get('hwr', 0.5625))))
    return out


class Data:
    """npz 전부를 메모리에. 그림은 입력 크기로 줄여 JPEG(품질 95)로 압축해 둔다(2만 장 × 640×360 원본이면 15GB → 약 1.5GB).
    이미 H.264로 압축된 장이라 JPEG 95의 추가 손실은 작다. 묶음을 만들 때 푼다."""

    def __init__(self, folder, maxlen, in_w, jpeg=True, workers=None):
        self.in_w, self.in_h = in_w, in_w * 9 // 16
        self.img, self.tok, self.fld, self.meta, self.hwr = [], [], [], [], []
        paths = sorted(glob.glob(os.path.join(folder, '*.npz')))
        jobs = [(p, maxlen, self.in_w, self.in_h, jpeg) for p in paths]
        video = bool(paths) and 'vid' in np.load(paths[0]).files
        workers = workers or (os.cpu_count() or 1)
        if video and workers > 1 and len(jobs) > 1:   # 순서 그대로(imap)라 결과는 한 프로세스로 읽은 것과 같다
            from multiprocessing import Pool
            with Pool(min(workers, len(jobs))) as pool:
                parts = list(pool.imap(_load_npz, jobs, chunksize=4))
        else:
            parts = map(_load_npz, jobs)
        for part in parts:
            for im, tk, fd, mt, hr in part:
                self.img.append(im)
                self.tok.append(tk)
                self.fld.append(fd)
                self.meta.append(mt)
                self.hwr.append(hr)
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
    def __init__(self, d=384, layers=6, heads=6, maxlen=2048, backbone='resnet34', pretrained=True, stride=16, sine=False, grid=None):
        super().__init__()
        # 그림 칸 고정(10-31 해상도 단계): 1080·720·480 입력도 끝까지 그 해상도로 읽고 마지막 특징만 이 칸 수로 모은다 →
        # 글자 쪽 메모리는 해상도와 무관, 같은 칸 = 같은 화면 위치(단계가 바뀌어도 위치 칸의 뜻이 같다). None이면 예전처럼 입력 크기 그대로
        self.grid = tuple(grid) if grid else None
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
        # 고정 sin 위치 신호(10-30 이동 시험 뒤): ① 그림 칸마다 화면 위치(가로·세로 0–1) ② 수 토큰마다 값(0–8191) —
        # 수 토큰은 원래 서로 무관한 단어라 '1000칸과 1001칸이 가깝다'를 자료에서 배워야 했다
        self.sine = sine
        if sine:
            self.register_buffer('val_pe', sine_table(np.arange(K.NUM) / K.NUM, d))
        self.register_buffer('mean', torch.tensor([0.485, 0.456, 0.406]).view(1, 3, 1, 1))
        self.register_buffer('std', torch.tensor([0.229, 0.224, 0.225]).view(1, 3, 1, 1))

    def memory(self, img, hwr):
        f8 = self.enc8((img - self.mean) / self.std)
        f = self.proj(self.enc16(f8))
        if self.stride == 8:
            f = self.proj8(f8) + F.interpolate(f, size=f8.shape[-2:], mode='bilinear', align_corners=False)
        if self.grid and tuple(f.shape[-2:]) != self.grid:
            f = F.adaptive_avg_pool2d(f, self.grid)
        B, C, H, W = f.shape
        pe = self.row.weight[:H, None, :] + self.col.weight[None, :W, :]
        if self.sine:
            ys = sine_table((np.arange(H) + 0.5) / H, C // 2).to(f.device)
            xs = sine_table((np.arange(W) + 0.5) / W, C - C // 2).to(f.device)
            pe = pe + torch.cat([ys[:, None, :].expand(H, W, -1), xs[None, :, :].expand(H, W, -1)], -1)
        r = self.ratio(torch.log(hwr.view(-1, 1) / 0.5625))[:, None, :]
        return f.flatten(2).transpose(1, 2) + pe.reshape(H * W, C)[None] + r

    def step(self, mem, tok, fld):
        T = tok.shape[1]
        x = self.emb(tok) + self.fld_emb(fld) + self.pos.weight[:T][None]
        if self.sine:
            num = tok >= K.OFF
            x = x + self.val_pe[(tok - K.OFF).clamp(0, K.NUM - 1)] * num[..., None]
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


def sine_table(v, d):
    """값 v(0–1) → d차원 sin/cos(주기 1 ~ 1/1000). 가까운 값은 가까운 벡터."""
    v = torch.as_tensor(np.asarray(v, np.float32))[:, None]
    k = torch.arange(d // 2, dtype=torch.float32)
    freq = torch.exp(k / max(d // 2 - 1, 1) * math.log(1000.0)) * math.pi
    out = torch.cat([torch.sin(v * freq), torch.cos(v * freq)], -1)
    return out if out.shape[1] == d else torch.cat([out, torch.zeros(len(out), d - out.shape[1])], -1)


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


# 분야별 점수(사용자 10-31: 분야마다 100점 만점) — 구조 단어는 문법상 거의 정해져 있어 전체 맞힘에 섞으면 좌표 실력이 가려진다
GROUPS = (('struct', '구조', ('spec',)), ('coord', '좌표', ('coord', 'big')), ('color', '색', ('color', 'bg')), ('thick', '굵기', ('thick',)),
          ('glow', '글로우', ('glow',)), ('link', '연결', ('link',)), ('fill', '면', ('obj', 'ptidx', 't')))
GROUP_OF = torch.tensor([next(g for g, (_, _, fs) in enumerate(GROUPS) if f in fs) for f in K.FIELDS])
# 좌표를 오브젝트의 첫 점 / 이어지는 점으로 나눈 진단(판정 기준 §2-3, 11-01). 분야 표 뒤에 두 줄 더
EXTRA = (('coord_first', '첫 점'), ('coord_rest', '이어지는 점'))
NROW = len(GROUPS) + len(EXTRA)
TYPE_IDS = torch.tensor(sorted(K.TOK[v] for v in K.TYPES.values()))
COORD_FIDS = torch.tensor([K.FID['coord'], K.FID['big']])


def point_index(tok):
    """토큰마다 '이 오브젝트에서 몇 번째 점인가'(종류 토큰 뒤 PT 수). 좌표 칸에서만 의미가 있다."""
    pt = torch.cumsum((tok == K.TOK['PT']).long(), -1)
    typ = torch.isin(tok, TYPE_IDS.to(tok.device))
    start = torch.cummax(torch.where(typ, pt, torch.zeros_like(pt)), -1).values
    return pt - start


def field_hits(logits, tgt, fld):
    """분야마다 (맞힘 수, 단어 수) — (분야 수, 2) 배열."""
    mask = tgt != K.TOK['PAD']
    g = GROUP_OF.to(tgt.device)[fld][mask]
    hit = (logits.argmax(-1) == tgt)[mask].float()
    n = torch.bincount(g, minlength=len(GROUPS)).float()
    h = torch.bincount(g, weights=hit, minlength=len(GROUPS))
    co = torch.isin(fld, COORD_FIDS.to(fld.device))[mask]
    first = (point_index(tgt) == 0)[mask]
    ex = [(hit[co & first].sum(), (co & first).sum()), (hit[co & ~first].sum(), (co & ~first).sum())]
    h = torch.cat([h, torch.stack([x[0].float() for x in ex])])
    n = torch.cat([n, torch.stack([x[1].float() for x in ex])])
    return torch.stack([h, n], 1).cpu().numpy()


def field_report(hn, prefix=''):
    """(분야 수, 2) → 기록용 {접두+이름: 0–100점}, 화면용 글. 좌표는 '몇 개마다 지적'(= 1 / 틀림 비율)도."""
    rec, txt = {}, []
    for (key, name, *_), (h, n) in zip(list(GROUPS) + list(EXTRA), hn):
        if n <= 0:
            continue
        sc = 100.0 * h / n
        rec[f'{prefix}{key}'] = round(sc, 2)
        txt.append(f'{name} {sc:.0f}')
        if key == 'coord':
            every = n / max(n - h, 1e-9)
            rec[f'{prefix}coord_every'] = round(float(every), 2)
            txt[-1] += f'({every:.1f}개마다 지적)'
    return rec, ' '.join(txt)


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
        if net.sine and tok >= K.OFF:
            x = x + net.val_pe[tok - K.OFF][None, None]
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
def generate(net, img, hwr, maxlen=None, temp=0.0, reason=False):
    """문법 강제 생성(한 장, KV 캐시). 돌려주는 끝냄은 '스스로 끝냄'만 참(GPT 1라운드 ⑤: 한도 64단어 전 강제 끝냄도 참이던 것).
    reason=True면 (토큰, 끝냄, 사유) — 사유 'eos'(스스로)·'forced'(한도 가까이 강제)·'limit'(한도에서 끊김)."""
    dev = img.device
    maxlen = maxlen or net.maxlen
    mem = net.memory(img[None], torch.tensor([hwr], dtype=torch.float32, device=dev))
    cache = Cache(net, mem)
    g = K.grammar()
    al = next(g)
    toks, flds = [], []
    forced = False
    while len(toks) < maxlen:
        if toks:
            lg = cache.step(toks[-1], flds[-1])
        else:
            lg = torch.zeros(K.VOCAB, device=dev)
        lg = lg + allowed_mask(al, dev)
        if len(toks) >= maxlen - 64 and TOK_EOS in al[0]:   # 길이 한도 가까우면 끝낼 수 있는 자리에서 끝낸다
            forced = int(lg.argmax()) != TOK_EOS   # 모델이 원래도 끝내려 했으면 강제가 아니다
            lg = torch.full_like(lg, float('-inf'))
            lg[TOK_EOS] = 0
        t = int(torch.multinomial(F.softmax(lg / temp, -1), 1)) if temp > 0 else int(lg.argmax())
        toks.append(t)
        flds.append(K.FID[al[3]] if t >= K.OFF else K.FID['spec'])
        try:
            al = g.send(t)
        except StopIteration:
            return (toks, not forced, 'forced' if forced else 'eos') if reason else (toks, not forced)
    return (toks, False, 'limit') if reason else (toks, False)


def lr_at(step, prog, base, warm=500):
    """예열(걸음) 뒤 진행률(쓴 시간 / 계획 시간) 기준 코사인 — 끊어서 돌려도 계획대로 이어진다."""
    w = min(1.0, (step + 1) / warm)
    return base * w * (0.05 + 0.95 * 0.5 * (1 + math.cos(math.pi * min(1.0, prog))))


def make_batches(ds, max_n, budget, cap=None):
    """길이가 비슷한 장끼리 묶되 한 묶음의 토큰 합이 budget을 넘지 않게(긴 장이 몰려도 메모리 일정).
    cap: 쉬운 것부터(11-01) — 정답 길이가 이 이하인 장만."""
    idx = [k for k in range(len(ds)) if cap is None or len(ds.tok[k]) <= cap]
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


VEC_MAP = (('bn1.', 'enc8.1.'), ('l1.', 'enc8.4.'), ('l2.', 'enc8.5.'), ('l3.', 'enc16.'))   # 이전 픽셀 지도 모델(vec_train) → 이 모델 인코더


def vec_encoder(src, dst):
    """이전 픽셀 지도 모델(vec_train, 10-29: SFA 그림에서 선·끝점·방향·면을 찾도록 학습)의 ResNet34 인코더를 이 모델 이름으로 바꿔 저장(10-31 사용자: 이어 쓰기).
    첫 층: 이전은 앞·지금·뒤 3장 9채널, 입력 0–1 그대로 / 이 모델은 1장 3채널, ImageNet 평균·표준편차 정규화.
    → 같은 그림 3장일 때와 같게 세 장 몫 가중치를 더하고, 정규화 차이는 가중치(×표준편차)와 BN 이동 평균(−평균 몫)으로 옮긴다(가장자리 0 채움 몫만 다름)."""
    sd = torch.load(src, map_location='cpu', weights_only=False)
    sd = sd.get('model', sd) if isinstance(sd, dict) and 'model' in sd else sd
    mean = torch.tensor([0.485, 0.456, 0.406]).view(1, 3, 1, 1)
    std = torch.tensor([0.229, 0.224, 0.225]).view(1, 3, 1, 1)
    w9 = sd['conv1.weight'].float()
    k = w9.shape[1] // 3
    wsum = sum(w9[:, 3 * i:3 * i + 3] for i in range(k))
    out = {'enc8.0.weight': wsum * std}
    for a_, b_ in VEC_MAP:
        out.update({b_ + key[len(a_):]: v for key, v in sd.items() if key.startswith(a_)})
    out['enc8.1.running_mean'] = sd['bn1.running_mean'].float() - (wsum * mean).sum((1, 2, 3))
    torch.save(dict(model=out, src=os.path.basename(os.path.dirname(os.path.abspath(src))) + '/' + os.path.basename(src)), dst)
    print('인코더', len(out), '항목 →', dst, flush=True)


def feat_grid(in_w, stride):
    """기본 입력(in_w × in_w·9/16)에서 ResNet 특징 칸 수 — conv1·maxpool·layer2(·layer3)가 각각 올림 반."""
    h, w = in_w * 9 // 16, in_w
    for _ in range(3 if stride == 8 else 4):
        h, w = -(-h // 2), -(-w // 2)
    return [h, w]


def npz_width(folder):
    p = sorted(glob.glob(os.path.join(folder, '*.npz')))
    if not p:
        raise SystemExit(f'자료 없음: {folder}')
    return int(json.loads(str(np.load(p[0])['meta']))['W'])


CUR_Q0, CUR_RAMP, CUR_STEPS = 0.2, 0.8, 20   # 쉬운 것부터: 단계 시작에 짧은 20%, 단계의 80% 지점에 전체, 5% 칸으로 늘림


def cur_quantile(sp):
    """단계 안 진행(0–1) → 허용할 정답 길이 분위(사용자 11-01: 단계마다 적은 단어부터 최대치까지)."""
    q = CUR_Q0 + (1 - CUR_Q0) * min(1.0, max(0.0, sp) / CUR_RAMP)
    return math.ceil(q * CUR_STEPS - 1e-9) / CUR_STEPS


def stage_progress(prog, frac, k):
    """전체 진행률 → 단계 k 안의 진행(0–1)."""
    start = sum(frac[:k])
    return min(1.0, max(0.0, (prog - start) / frac[k])) if frac[k] > 0 else 1.0


def stage_of(prog, frac):
    """진행률 → 단계 번호(시간 비율 frac 누적 경계)."""
    acc = 0.0
    for i, f in enumerate(frac):
        acc += f
        if prog < acc:
            return i
    return len(frac) - 1


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
    cfg = dict(d=a.d, layers=a.layers, heads=a.heads, maxlen=a.maxlen, backbone=a.backbone, in_w=a.in_w, stride=a.stride, sine=a.sine,
               grid=feat_grid(a.in_w, a.stride))
    stage_dirs = [x for x in a.stages.split(',') if x] if a.stages else []
    if stage_dirs:   # 해상도 단계(사용자 10-29·10-31 복원): 깨끗한 1080부터 720·480을 거쳐 기본 입력(360)으로 — 화질 나쁜 애니 자료도 깔끔하게 옮기는 실력
        frac = [float(v) for v in a.stage_frac.split(',')]
        if len(frac) != len(stage_dirs) + 1 or abs(sum(frac) - 1) > 1e-6:
            raise SystemExit(f'--stage-frac은 단계 {len(stage_dirs) + 1}개(고해상도 {len(stage_dirs)} + 기본)이고 합이 1이어야 함: {a.stage_frac}')
        cfg['stages'] = dict(w=[npz_width(d) for d in stage_dirs], frac=frac, mix=a.stage_mix)
    st = dict(step=0, best=1e9, done_min=0.0, plan_min=a.plan_minutes or a.minutes, budget=a.tok_budget, grad_ckpt=a.grad_ckpt,
              px=a.px_budget, stage=0)
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
    va = Data(a.val, cfg['maxlen'], cfg['in_w'])
    sv = Data(a.shift_val, cfg['maxlen'], cfg['in_w']) if a.shift_val else None   # 위치 시험(학습 파일 + 학습에 없던 고정 이동)
    js = J.JudgeSet(a.judge, cfg['in_w']) if a.judge else None   # 판정 장치(11-01): 평가 목록 고정 장 × 이동 4방향
    js_reduced = False
    if js is not None and a.judge_n:
        js_reduced = a.judge_n < len(js)
        js.keep(a.judge_n)
        print(f'주의: 판정 장을 앞 {len(js)}장으로 줄임(흐름 시험용 — 공식 판정 아님)', flush=True)
    memo = {}
    if js is not None:
        memo = {nd: J.memo_baseline(js, range(nd)) for nd in (2, 4)}   # 이 평가 목록·방향으로 다시 계산한 외움 기준선
        print(f"판정 자료 {len(js)}장 · 독립 단위 {len({e['group'] for e in js.ents})} · 외움 기준선 공식 2방향 {memo[2]:.2f} / 4방향 {memo[4]:.2f}점", flush=True)
    if saved and a.sine and not cfg.get('sine'):
        print('주의: 이어하기는 저장된 설정을 따른다 — --sine을 줘도 이 학습은 sin 없이 계속(비교하려면 새 출력 폴더에서 처음부터)', flush=True)
    stg = cfg.get('stages')
    if stg:
        if len(stage_dirs) != len(stg['w']):
            raise SystemExit(f"이 학습은 해상도 단계 {stg['w']}로 시작했다 — 같은 순서의 --stages 자료 폴더 {len(stg['w'])}개가 필요")
        got = [npz_width(d) for d in stage_dirs]
        if got != stg['w']:
            raise SystemExit(f"--stages 자료 폭 {got}이 학습 설정 {stg['w']}과 다름")
    elif stage_dirs:
        print('주의: 이어하기는 저장된 설정을 따른다 — 해상도 단계 없이 시작한 학습이라 --stages를 무시(단계 학습은 새 출력 폴더에서 처음부터)', flush=True)
        stage_dirs = []
    st.setdefault('px', a.px_budget)
    st.setdefault('stage', 0)
    widths = (stg['w'] if stg else []) + [cfg['in_w']]
    sets = {}   # 단계 번호 → 자료(마지막 = 기본 입력 자료). 모두 필요할 때 읽고 지난 단계는 내린다
    tm_load = [0.0]
    # (11-01 Kaggle CPU 실측: 기본 자료 읽기 8분·1080 15분 — 1080 단계 회차에 기본 자료를 미리 읽지 않는다)

    def stage_set(i):
        if i not in sets:
            t1 = time.time()
            sets[i] = Data(stage_dirs[i] if i < len(stage_dirs) else a.data, cfg['maxlen'], widths[i])
            print(f'단계 자료 {widths[i]}폭 {len(sets[i])}장 {sets[i].ntok}토큰 ({time.time() - t1:.0f}초)', flush=True)
            tm_load[0] += time.time() - t1
            if not len(sets[i]):
                raise SystemExit(f'학습 자료 0장({widths[i]}폭) — 자료 폴더 확인')
        return sets[i]

    def max_n(i):
        w = widths[i]
        return min(a.max_batch, max(1, int(st['px'] * 1e6 // (w * (w * 9 // 16)))))
    print(f'시험 자료 {len(va)}장 ({time.time() - t0:.0f}초) · 학습 자료는 단계마다 필요할 때 읽음', flush=True)
    net = Net(cfg['d'], cfg['layers'], cfg['heads'], cfg['maxlen'], cfg['backbone'], pretrained=not saved, stride=cfg.get('stride', 16),
              sine=cfg.get('sine', False), grid=cfg.get('grid')).to(dev)
    opt = torch.optim.AdamW(net.parameters(), lr=a.lr, weight_decay=0.01)
    net.grad_ckpt = bool(st.get('grad_ckpt'))
    if a.init_encoder and not saved:   # 이전 픽셀 지도 모델 인코더에서 출발(새로 시작할 때만, 이어하기는 저장본 그대로)
        enc = torch.load(a.init_encoder, map_location='cpu', weights_only=False)
        own = net.state_dict()
        bad = [key for key, v in enc['model'].items() if key not in own or own[key].shape != v.shape]
        if bad:
            raise SystemExit(f'인코더 파일이 이 모델과 안 맞음: {bad[:5]}')
        net.load_state_dict(enc['model'], strict=False)
        cfg['init_encoder'] = enc.get('src', os.path.basename(a.init_encoder))
        print('인코더 이어 쓰기:', cfg['init_encoder'], len(enc['model']), '항목', flush=True)
    elif a.init_encoder:
        print('주의: 이어하기라 --init-encoder 무시(저장본 그대로)', flush=True)
    if saved:
        net.load_state_dict(saved['model'])
        opt.load_state_dict(saved['opt'])
        print(f"이어하기: {st['step']}걸음, 진행 {st['done_min']:.0f}/{st['plan_min']:.0f}분, best {st['best']:.4f}", flush=True)
    print('변수', sum(p.numel() for p in net.parameters()) // 1000, '천 · 설정', cfg, flush=True)
    amp = dev == 'cuda'
    dt = torch.bfloat16 if amp and torch.cuda.get_device_capability(0)[0] >= 8 else torch.float16
    scaler = torch.amp.GradScaler('cuda', enabled=amp and dt == torch.float16)
    if saved:   # 이어하기: 배율·난수 상태도(GPT 검토 10-30)
        # 다른 GPU에서 이어하기(10-30: Kaggle T4 fp16 ↔ 4060 bf16): bf16 쪽 배율 상태는 비어 있어 fp16에서 불러오면 오류 → 비었으면 새 배율로.
        # 난수 상태도 기기가 달라 맞지 않으면 건너뛴다(학습에는 영향 없음)
        if saved.get('scaler') and scaler.is_enabled():
            scaler.load_state_dict(saved['scaler'])
        rs = saved.get('rng')
        if rs:
            try:
                random.setstate(rs['py'])
                torch.set_rng_state(rs['torch'])
                if dev == 'cuda' and rs.get('cuda') is not None:
                    torch.cuda.set_rng_state(rs['cuda'])
            except Exception as e:
                print('난수 상태 복원 건너뜀(다른 기기):', type(e).__name__, flush=True)
    base_lr = st.setdefault('base_lr', a.lr)   # 처음 정한 학습률(이어하기에서 명령줄 값으로 바뀌지 않게)
    log = os.path.join(a.out, 'log.jsonl')
    t_sess = time.time()
    p_sess = yl.paused
    done0 = st['done_min']
    # 검증 대상 고정: 시험 자료에서 고르게 val_n장, 묶음은 처음 토큰 한도로(학습 한도가 줄어도 같은 대상, GPT 검토 10-30)
    v_idx = sorted(set(np.linspace(0, len(va) - 1, min(a.val_n, len(va))).astype(int).tolist())) if len(va) else []
    v_batches = make_batches_fixed(va, a.max_batch, a.tok_budget, v_idx)
    vk, vk_batches = None, {}
    if a.val_kind:   # 실제·조합 고정 검증 자료(같은 해상도 640, 정답 길이 셋으로 나눔)
        vk = Data(a.val_kind, cfg['maxlen'], cfg['in_w'])
        kinds = ['real' if kind_of(vk, k).startswith('real') else 'comp' for k in range(len(vk))]
        L = np.array([len(t) for t in vk.tok])
        q1, q2 = np.quantile(L, [1 / 3, 2 / 3]) if len(L) else (0, 0)
        for k in range(len(vk)):
            band = 'short' if L[k] <= q1 else ('mid' if L[k] <= q2 else 'long')
            vk_batches.setdefault(f'{kinds[k]}_{band}', []).append(k)
        vk_batches = {key: make_batches_fixed(vk, a.max_batch, a.tok_budget, idx) for key, idx in sorted(vk_batches.items())}
        print('종류별 검증 자료', {key: sum(len(b) for b in bs) for key, bs in vk_batches.items()}, flush=True)
    g_idx = v_idx[::max(1, len(v_idx) // a.gen_n)][:a.gen_n]   # 생성 채점용 고정 장
    s_idx = (sorted(set(np.linspace(0, len(sv) - 1, min(a.gen_n, len(sv))).astype(int).tolist())) if sv is not None and len(sv) else [])

    def active_min():
        return (time.time() - t_sess - (yl.paused - p_sess)) / 60

    def save_ckpt():
        st['done_min'] = done0 + active_min()
        rng = dict(py=random.getstate(), torch=torch.get_rng_state(), cuda=torch.cuda.get_rng_state() if dev == 'cuda' else None)
        VT.save(dict(model=net.state_dict(), opt=opt.state_dict(), scaler=scaler.state_dict(), rng=rng, cfg=cfg, state=dict(st)), ck)

    def val_batch(b, ds_=None):
        """한 묶음의 (손실 합, 맞힘 합, 토큰 수, 못 잰 장 수). 메모리 부족이면 오류 처리를 벗어난 뒤 반으로 나눠 다시(GPT 2차).
        ds_ = 다른 고정 검증 자료(--val-kind), 없으면 시험 자료."""
        oom_ = False
        try:
            im, tk, fd, hr = (x.to(dev) for x in (ds_ if ds_ is not None else va).batch(b))
            with torch.autocast(dev, dtype=dt, enabled=amp):
                lg = net(im, tk[:, :-1], fd[:, :-1], hr)
            l_, c_, n_ = loss_fn(lg, tk[:, 1:], fd[:, 1:])
            if not torch.isfinite(l_):
                return 0.0, 0.0, 0.0, len(b), np.zeros((NROW, 2))
            return l_.item() * n_.item(), c_.item() * n_.item(), n_.item(), 0, field_hits(lg, tk[:, 1:], fd[:, 1:])
        except torch.OutOfMemoryError:
            oom_ = True
        im = tk = fd = hr = lg = None
        if dev == 'cuda':
            torch.cuda.empty_cache()
        if len(b) == 1:
            return 0.0, 0.0, 0.0, 1, np.zeros((NROW, 2))
        x, y = val_batch(b[:len(b) // 2], ds_), val_batch(b[len(b) // 2:], ds_)
        return tuple(p + q for p, q in zip(x, y))

    def validate():
        """토큰 수로 가중한 시험 손실·맞힘. 못 잰 장이 있으면 불완전(best 갱신 안 함)."""
        net.eval()
        tl = tc = tn = 0.0
        bad = 0
        hn = np.zeros((NROW, 2))
        try:
            with torch.no_grad():
                for b in v_batches:
                    l_, c_, n_, f_, h_ = val_batch(b)
                    tl, tc, tn, bad, hn = tl + l_, tc + c_, tn + n_, bad + f_, hn + h_
        finally:
            net.train()
        return (tl / tn if tn else float('nan')), (tc / tn if tn else 0.0), int(tn), bad, hn

    def validate_kind():
        """실제 장 대 조합 장(GPT 1라운드 D): 고정 검증 자료를 종류 × 정답 길이 셋(짧은·중간·긴)으로 나눠 교사 강제 손실·맞힘."""
        out = {}
        net.eval()
        try:
            with torch.no_grad():
                for key, bs in vk_batches.items():
                    tl = tc = tn = 0.0
                    for b in bs:
                        l_, c_, n_, f_, _ = val_batch(b, vk)
                        tl, tc, tn = tl + l_, tc + c_, tn + n_
                    out[f'valk_{key}_loss'] = tl / tn if tn else None
                    out[f'valk_{key}_acc'] = tc / tn if tn else None
                    out[f'valk_{key}_n'] = sum(len(b) for b in bs)
        finally:
            net.train()
        return out

    def gen_eval(final=False):
        """두 고정 집합을 실제로 그려 보고 오브젝트 채점: 시험 파일(새 파일 일반화) + 학습 파일의 학습에 없던 이동(위치 읽기, GPT 3차).
        판정 자료가 있으면 입력 교환 생성 대조(판정 기준 §2)도. 마지막(공식 시점)은 4방향."""
        out = gen_set(va, g_idx, 'gen')
        if s_idx:
            out.update(gen_set(sv, s_idx, 'shift'))
        if js is not None:
            out.update(judge_eval(a.judge_dirs_final if final else a.judge_dirs, final))
        return out

    def gen_img(im, hwr, n_ans=None):
        """그림 한 장 생성 → (토큰, 끝냄, 초) 또는 None(메모리 부족). n_ans가 있으면 길이 상한 적용(gen_cap).
        종료 사유는 reasons에 센다(스스로·강제·한도, 상한이 모델 최대보다 짧았는지)."""
        t1 = time.time()
        try:
            x = torch.from_numpy(np.ascontiguousarray(im)).permute(2, 0, 1).float().to(dev) / 255
            cap = gen_cap(n_ans)
            with torch.no_grad(), torch.autocast(dev, dtype=dt, enabled=amp):
                toks, done, why = generate(net, x, hwr, cap, reason=True)
            reasons[why + ('_cap' if why != 'eos' and cap < cfg['maxlen'] else '')] += 1
            if dev == 'cuda':
                torch.cuda.synchronize()
            return toks, done, time.time() - t1
        except torch.OutOfMemoryError:
            if dev == 'cuda':
                torch.cuda.empty_cache()
            return None

    from collections import Counter
    reasons = Counter()

    def gen_cap(n_ans):
        """생성 길이 상한(11-01, Kaggle CPU 실측: 학습 초반 엉터리 출력이 2,048단어까지 가 한 장 54초). 정답 길이 × 배수 + 128을 넘으면
        끊고 미완료로 센다 — 건전성에서 어차피 실패라 판정은 같고 시간만 준다. 0이면 상한 없음(모델 최대 길이)."""
        if not a.gen_len_mult or n_ans is None:
            return cfg['maxlen']
        return min(cfg['maxlen'], int(a.gen_len_mult * n_ans + 128))

    def judge_eval(nd, final=False):
        """판정(판정 기준 §2). 그때 배우는 해상도 단계 폭의 그림으로 묻는다(11-01: 1080 단계에 360 영상을 넣으면 위치를 못 읽는 것과
        처음 보는 화질을 구분할 수 없다). 마지막 판정이 고해상도 단계면 기본 입력(360) 공식 2방향도 따로(judge360_)."""
        net.eval()
        t1 = time.time()
        w = widths[st['stage']]
        w = w if w in js.stage else cfg['in_w']
        try:
            # 공식 판정(판정 기준 §2, GPT 1라운드 A·⑤): 계획 끝에 도달한 마지막 판정만. 길이 상한 없이(모델 최대 길이, 모든 방향 같음).
            # 추세 판정: 길이 상한은 장마다 네 방향 정답 중 가장 긴 것 기준 — 입력 방향에 따라 상한이 달라지지 않게
            official = official_judgment(final, st['done_min'], st['plan_min'], js_reduced, w, cfg['in_w'])
            if official:   # 사전 지정 기회는 최초 끝·연장 끝 두 번 — 몇 번째 공식 판정인지 남긴다(셋째부터는 기준 밖)
                st['official_n'] = st.get('official_n', 0) + 1
            reasons.clear()
            cap_of = (lambda i: None) if official else (lambda i: max(len(t) for t in js.tok[i]))
            res, gens = J.evaluate(js, lambda i, d: gen_img(js.image(i, d, w), js.ents[i]['hwr'], cap_of(i)), dirs=range(nd),
                                   memo=memo[2], memo4=memo[4])
            rec_ = J.flat(res)
            rec_.update(judge_dirs=nd, judge_w=w, judge_official=official, judge_official_n=st.get('official_n', 0) if official else None,
                        judge_reduced=js_reduced, judge_end=dict(reasons))
            print(f'[{w}폭 {"공식" if official else "추세"}]', J.summary_line(res, official), f"({round(time.time() - t1)}초, {nd}방향, 끝냄 {dict(reasons)})", flush=True)
            judge_sheet(gens, w)
            if final and w != cfg['in_w']:
                t2 = time.time()
                reasons.clear()
                off360 = official_judgment(final, st['done_min'], st['plan_min'], js_reduced, cfg['in_w'], cfg['in_w'])
                cap360 = (lambda i: None) if off360 else (lambda i: max(len(t) for t in js.tok[i]))
                if off360:
                    st['official_n'] = st.get('official_n', 0) + 1
                r2, _ = J.evaluate(js, lambda i, d: gen_img(js.image(i, d), js.ents[i]['hwr'], cap360(i)), dirs=range(2), memo=memo[2])
                rec_.update(J.flat(r2, 'judge360_'))
                rec_.update(judge360_end=dict(reasons), judge360_official=off360, judge360_official_n=st.get('official_n', 0) if off360 else None)
                print(f"[{cfg['in_w']}폭 {'공식' if off360 else '추세'}]", J.summary_line(r2, off360), f"({round(time.time() - t2)}초, 2방향)", flush=True)
            rec_['judge_sec'] = round(time.time() - t1)
        finally:
            net.train()
            if dev == 'cuda':
                torch.cuda.empty_cache()
        return rec_

    def judge_sheet(gens, w=None):
        """고정 그림 시트: 평가 목록 앞 sheet_n장의 공식 방향 0 — 입력 영상 | AI SFA | 정답 SFA(골라 보여 주지 않음)."""
        try:
            import sfa_render as R
            Wd = 480
            R.PARAMS['pad'] = 0.0
            R.PARAMS['thick_mul'] = Wd / 1920
            rows_ = []
            for i in range(min(a.sheet_n, len(js))):
                hwr = js.ents[i]['hwr']
                Hd = max(2, int(round(Wd * hwr)))
                seq = seq_xml(hwr)
                p_ = gens.get((i, 0))
                im_p = R.render_frame(seq, K.decode(p_), Wd, Hd) if p_ is not None else np.zeros((Hd, Wd, 3), np.uint8)
                im_a = R.render_frame(seq, K.decode([int(t) for t in js.tok[i][0]]), Wd, Hd)
                src = cv2.resize(js.image(i, 0, w), (Wd, Hd))
                row = np.hstack([src, im_p[..., :3], im_a[..., :3]])
                rows_.append(cv2.resize(row, (3 * Wd, int(round(Wd * 9 / 16)))))
            if rows_:
                cv2.imwrite(os.path.join(a.out, f"judge_sheet_{st['step']:07d}.png"), np.vstack(rows_)[..., ::-1])
        except Exception as e:   # 시트 실패가 학습을 멈추지 않게(기록만)
            print('판정 그림 시트 실패:', type(e).__name__, e, flush=True)

    def gen_set(ds_, idx_, pre):
        net.eval()
        sums = dict(ans=0, pred=0, match=0, link_tp=0, link_pred=0, link_ans=0, fill_tp=0, fill_pred=0, fill_ans=0, perfect=0, done=0, frames=0, oom=0, errs=[],
                    partial_sum=0.0, partial_n=0)
        t0_ = time.time()
        try:
            for i in idx_:
                gen_one(ds_, i, sums)
        finally:
            net.train()
            if dev == 'cuda':
                torch.cuda.empty_cache()
        return {f'{pre}_recall': sums['match'] / max(sums['ans'], 1), f'{pre}_precision': sums['match'] / max(sums['pred'], 1),
                f'{pre}_partial': sums['partial_sum'] / max(sums['partial_n'], 1),   # 부분 점수(가까울수록, 사용자 10-31)
                f'{pre}_link_f1': OS.f1(sums['link_tp'], sums['link_pred'], sums['link_ans']),
                f'{pre}_fill_f1': OS.f1(sums['fill_tp'], sums['fill_pred'], sums['fill_ans']),
                f'{pre}_coord_err': float(np.median(sums['errs'])) if sums['errs'] else None,
                f'{pre}_perfect': sums['perfect'], f'{pre}_done': sums['done'], f'{pre}_frames': sums['frames'], f'{pre}_oom': sums['oom'],
                f'{pre}_sec': round(time.time() - t0_)}

    def gen_one(ds_, i, sums):
        """한 장 생성 채점. 메모리 부족이면 그 장만 건너뛰고 센다(학습은 계속)."""
        try:
            img = torch.from_numpy(np.ascontiguousarray(ds_.image(i))).permute(2, 0, 1).float().to(dev) / 255
            with torch.no_grad(), torch.autocast(dev, dtype=dt, enabled=amp):
                toks, done = generate(net, img, ds_.hwr[i], gen_cap(len(ds_.tok[i])))
                # 근접 정도(GPT 3차: 생성 맞힘 0이어도 가까워지는지): 교사 강제 좌표 오차(%) 중앙값
                tk = torch.from_numpy(ds_.tok[i])[None].to(dev)
                fd = torch.from_numpy(ds_.fld[i])[None].to(dev)
                lg = net(img[None], tk[:, :-1], fd[:, :-1], torch.tensor([ds_.hwr[i]], device=dev))
            mk = fd[:, 1:] == K.FID['coord']
            sums['errs'] += ((lg[..., K.OFF:].argmax(-1) + K.OFF - tk[:, 1:]).abs()[mk].float() * K.XSTEP).tolist()
            sc = OS.score(K.decode(toks), K.decode(ds_.tok[i].tolist()), hwr=ds_.hwr[i])
            for k_ in ('ans', 'pred', 'match', 'link_tp', 'link_pred', 'link_ans', 'fill_tp', 'fill_pred', 'fill_ans', 'partial_sum', 'partial_n'):
                sums[k_] += sc[k_]
            sums['perfect'] += sc['perfect']
            sums['done'] += done
            sums['frames'] += 1
        except torch.OutOfMemoryError:
            sums['oom'] += 1

    tm = dict(load=0.0, train=0.0, val=0.0, gen=0.0)   # 시간 내역(초, GPT 1라운드 G): 자료 읽기·학습 계산·검증·생성 채점
    t_run = time.time()
    bq = {}   # 단계 번호 → 남은 묶음
    bq_lv = {}   # 단계 번호 → 그 묶음을 만든 쉬운 것부터 분위
    lens = {}

    def ds_len(i):
        if i not in lens:
            lens[i] = np.array([len(t) for t in stage_set(i).tok])
        return lens[i]
    run, racc = [], []
    rhn = np.zeros((NROW, 2))
    last_val = last_save = last_gen = time.time()
    oom = skipped = 0
    while active_min() < a.minutes and done0 + active_min() < st['plan_min']:
        yl.tick()
        prog = (done0 + active_min()) / st['plan_min']
        k = len(widths) - 1
        if stg:
            k = max(st['stage'], stage_of(prog, stg['frac']))   # 단계는 되돌아가지 않는다(이어하기로 계획이 늘어 진행률이 줄어도)
            if k != st['stage']:
                print(time.strftime('%H:%M'), f"해상도 단계 {widths[st['stage']]} → {widths[k]}폭 (진행 {prog * 100:.1f}%)", flush=True)
                st['stage'] = k
            for j in [j for j in sets if j not in (k, k - 1, len(widths) - 1)]:
                sets.pop(j)
                bq.pop(j, None)   # 지난 단계 자료는 메모리에서 내린다
        i = k - 1 if k > 0 and stg and random.random() < stg['mix'] else k   # 새 해상도 70% + 앞 단계 30%
        ds = stage_set(i)
        lv = 1.0
        if not a.no_curriculum and i == k:   # 쉬운 것부터(11-01): 지금 단계 자료는 정답 길이 분위를 단계 진행에 따라 늘린다. 앞 단계 섞기는 전체
            lv = cur_quantile(stage_progress(prog, stg['frac'] if stg else [1.0], k))
        if bq_lv.get(i) != lv:
            bq.pop(i, None)
            bq_lv[i] = lv
            if lv < 1.0:
                print(time.strftime('%H:%M'), f"쉬운 것부터: {widths[i]}폭 정답 길이 하위 {lv * 100:.0f}%", flush=True)
        if not bq.get(i):
            cap = None if lv >= 1.0 else float(np.quantile(ds_len(i), lv))
            bq[i] = make_batches(ds, max_n(i), st['budget'], cap)
            if not bq[i]:
                raise SystemExit(f"토큰 한도 {st['budget']} 안에 드는 학습 장이 없음({widths[i]}폭)")
        b = bq[i].pop()
        for g in opt.param_groups:
            g['lr'] = lr_at(st['step'], prog, base_lr)
        img = tok = fld = hwr = lg = loss = acc = None
        unscaled = False
        t_step = time.time()
        try:   # GPU로 옮기기부터 한 걸음 전체를 보호(GPT 검토 10-30)
            img, tok, fld, hwr = (x.to(dev) for x in ds.batch(b))
            with torch.autocast(dev, dtype=dt, enabled=amp):
                lg = net(img, tok[:, :-1], fld[:, :-1], hwr)
            loss, acc, _ = loss_fn(lg, tok[:, 1:], fld[:, 1:])
            fh = field_hits(lg.detach(), tok[:, 1:], fld[:, 1:])
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
            elif widths[i] > cfg['in_w'] and max_n(i) > 1:   # 고해상도 단계: 한 묶음 그림 수(화소 예산)부터 줄인다
                st['px'] = st['px'] * 0.75
                print(time.strftime('%H:%M'), f"메모리 부족 → 화소 예산 {st['px']:.1f}M ({widths[i]}폭 한 묶음 {max_n(i)}장)", flush=True)
            else:                   # 2단계: 토큰 한도 줄이기(한도보다 긴 장은 학습에서 빠진다)
                st['budget'] = max(1024, int(st['budget'] * 0.8))
                drop = sum(len(t) > st['budget'] for t in ds.tok)
                print(time.strftime('%H:%M'), f'메모리 부족 → 토큰 한도 {st["budget"]} (이보다 긴 장 {drop}/{len(ds)} 빠짐, {widths[i]}폭)', flush=True)
            bq = {}
            if a.yield_:
                time.sleep(60)
                yl.paused += 60
            continue
        st['step'] += 1
        tm['train'] += time.time() - t_step
        ss_ = st.setdefault('stage_steps', {})
        ss_[str(widths[i])] = ss_.get(str(widths[i]), 0) + 1   # 단계(자료 해상도)별 업데이트 수
        ex = st.setdefault('expo', {})   # 실제 노출(GPT 1라운드 D·E): 해상도|쉬운 것부터 분위|장 종류 → [장, 단어, 업데이트]
        for kk in set(kind_of(ds, x) for x in b):
            key = f'{widths[i]}|{lv:.2f}|{kk}'
            e_ = ex.setdefault(key, [0, 0, 0])
            e_[2] += 1
        for x in b:
            e_ = ex[f'{widths[i]}|{lv:.2f}|{kind_of(ds, x)}']
            e_[0] += 1
            e_[1] += len(ds.tok[x])
        run.append(loss.item())
        racc.append(acc.item())
        rhn = rhn + fh
        if st['step'] % a.log_every == 0:
            mem = f' GPU {torch.cuda.max_memory_allocated() / 2**30:.1f}GB' if dev == 'cuda' else ''
            print(f"{st['step']} 손실 {np.mean(run):.3f} 맞힘 {np.mean(racc) * 100:.1f}% 진행 {prog * 100:.1f}% {widths[k]}폭 "
                  f"학습률 {opt.param_groups[0]['lr']:.2e} ({active_min():.1f}분){mem} | 분야 {field_report(rhn)[1]}", flush=True)
            run, racc = [], []
            rhn = np.zeros((NROW, 2))
        if time.time() - last_val > a.val_minutes * 60:
            last_val = time.time()
            vl, vc, n, vbad, vhn = validate()
            vkr = validate_kind() if vk is not None else {}
            tm['val'] += time.time() - last_val
            rec = dict(step=st['step'], val=vl, val_acc=vc, val_tokens=n, val_failed=vbad, val_sec=round(time.time() - last_val), stage_steps=dict(st.get('stage_steps', {})),
                       minutes=done0 + active_min(), prog=prog,
                       oom=oom, skipped=skipped, budget=st['budget'], grad_ckpt=net.grad_ckpt, paused_min=yl.paused / 60,
                       stage_w=widths[k], px=st['px'], **field_report(vhn, 'val_')[0])
            if n and not vbad and vl < st['best']:   # 못 잰 장이 있으면 best 안 바꿈(GPT 2차)
                st['best'] = vl
                VT.save(dict(model=net.state_dict(), cfg=cfg, step=st['step'], val=vl), os.path.join(a.out, 'best.pt'))
            save_ckpt()   # 생성 채점 전에 저장(GPT 2차: 생성 중 문제가 생겨도 학습 상태는 남게)
            last_save = time.time()
            rec.update(vkr)
            if a.gen_minutes and time.time() - last_gen > a.gen_minutes * 60:
                last_gen = time.time()
                rec.update(gen_eval())
                tm['gen'] += time.time() - last_gen
            rec.update(time_sec=dict(tm, load=tm_load[0], wall=time.time() - t_run), expo=dict(st.get('expo', {})))
            print('검증', rec, flush=True)
            print('검증 분야(100점 만점):', field_report(vhn)[1], flush=True)
            with open(log, 'a', encoding='utf-8') as fh:
                fh.write(json.dumps(rec) + '\n')
        elif time.time() - last_save > a.save_minutes * 60:
            save_ckpt()
            last_save = time.time()
    vl, vc, n, vbad, vhn = validate()
    rec = dict(step=st['step'], val=vl, val_acc=vc, val_tokens=n, val_failed=vbad, final=True, minutes=done0 + active_min(),
               stage_steps=dict(st.get('stage_steps', {})), **field_report(vhn, 'val_')[0])
    if n and not vbad and vl < st['best']:
        st['best'] = vl
        VT.save(dict(model=net.state_dict(), cfg=cfg, step=st['step'], val=vl), os.path.join(a.out, 'best.pt'))
    save_ckpt()
    if vk is not None:
        rec.update(validate_kind())
    if a.gen_minutes:
        t_g = time.time()
        rec.update(gen_eval(final=True))
        tm['gen'] += time.time() - t_g
    rec.update(time_sec=dict(tm, load=tm_load[0], wall=time.time() - t_run), expo=dict(st.get('expo', {})),
               plan_reached=bool(st['done_min'] >= st['plan_min'] - 1e-6))
    print('마지막 검증', rec, flush=True)
    print('마지막 검증 분야(100점 만점):', field_report(vhn)[1], flush=True)
    with open(log, 'a', encoding='utf-8') as fh:
        fh.write(json.dumps(rec) + '\n')
    print(f"끝 {st['step']}걸음 · 진행 {st['done_min']:.0f}/{st['plan_min']:.0f}분 · best {st['best']:.4f} · 메모리 부족 {oom} · 건너뜀 {skipped}", flush=True)


def official_judgment(final, done_min, plan_min, reduced, w, in_w):
    """공식 판정인가(판정 기준 §2, GPT 1라운드 A·재확인 11-01): 마지막 판정 + 계획 끝 도달 + 고정 평가 목록 전체(--judge-n으로
    줄이지 않음) + 기본 입력 해상도(360 = in_w 폭). 고해상도 단계 판정·축소 목록 흐름 시험은 계획이 끝나도 추세."""
    return bool(final and done_min >= plan_min - 1e-6 and not reduced and w == in_w)


def kind_of(ds, k):
    """장 종류: 조합 문제 자료의 장마다 출처(items) — 'comp'·'real'·'real_crop', 예전 자료는 'orig'."""
    m = ds.meta[k]
    it = m.get('items')
    if it and m.get('pos') is not None and m['pos'] < len(it):
        return it[m['pos']].get('kind', m.get('compose') or 'orig')
    return m.get('compose') or 'orig'


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
    net = Net(c['d'], c['layers'], c['heads'], c['maxlen'], c['backbone'], pretrained=False, stride=c.get('stride', 16), sine=c.get('sine', False),
              grid=c.get('grid'))
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
    t.add_argument('--shift-val', default='', help='위치 시험 자료 폴더(seq_data --fixed) — 생성 채점에 같이')
    t.add_argument('--gen-minutes', type=float, default=60, help='생성 채점 간격(분). 0이면 안 함')
    t.add_argument('--judge', default='', help='판정 자료 폴더(seq_judge build — 입력 교환 생성 대조·건전성·A/B/외움, 판정 기준 §2)')
    t.add_argument('--judge-dirs', type=int, default=2, choices=(2, 4), help='중간 판정의 이동 방향 수(2 = 공식 쌍만)')
    t.add_argument('--judge-dirs-final', type=int, default=4, choices=(2, 4), help='마지막(공식 시점) 판정의 방향 수(4 = 축별 진단 16칸 표 포함)')
    t.add_argument('--gen-len-mult', type=float, default=2.0, help='생성 채점 길이 상한 = 정답 길이 × 이 배수 + 128(넘으면 끊고 미완료). 0이면 모델 최대 길이')
    t.add_argument('--val-kind', default='', help='실제·조합 고정 검증 자료(seq_data --compose, 다른 씨앗) — 종류 × 길이 셋별 교사 강제 손실(GPT 1라운드 D)')
    t.add_argument('--no-curriculum', action='store_true', help='쉬운 것부터(단계마다 짧은 정답부터 최대치까지, 11-01) 끄기')
    t.add_argument('--judge-n', type=int, default=0, help='판정 장 수를 평가 목록 앞 n장으로 줄임(CPU 흐름 시험용, 0 = 전부 — 공식 판정은 전부)')
    t.add_argument('--sheet-n', type=int, default=6, help='판정 때마다 저장하는 고정 그림 시트 장 수(평가 목록 앞에서부터, 골라 보여 주지 않음)')
    t.add_argument('--yield', dest='yield_', action='store_true', help='양보 모드(게임 실행 중이면 멈추거나 천천히)')
    t.add_argument('--sine', action='store_true', help='고정 sin 위치 신호(그림 칸 위치 + 수 토큰 값)')
    t.add_argument('--stages', default='', help='해상도 단계 자료 폴더(쉼표, 높은 해상도부터: 1920,1280,854폭 seq_data --video). 마지막 단계는 data(기본 입력)')
    t.add_argument('--stage-frac', default='0.2,0.25,0.25,0.3', help='단계별 학습 시간 비율(고해상도들 + 기본, 합 1)')
    t.add_argument('--stage-mix', type=float, default=0.3, help='각 단계에서 앞 단계 자료를 섞는 비율')
    t.add_argument('--px-budget', type=float, default=8.0, help='한 묶음 그림 화소 한도(백만). 1080은 3장·720은 8장. 메모리 부족이면 자동으로 줄인다')
    t.add_argument('--init-encoder', default='', help='vec-encoder로 만든 인코더 파일에서 출발(새로 시작할 때만)')
    t.add_argument('--grad-ckpt', action='store_true', help='처음부터 체크포인팅(메모리 절약, 느림). 꺼 두면 메모리 부족 때 자동으로 켠다')
    d = sub.add_parser('draw')
    d.add_argument('ckpt')
    d.add_argument('data')
    d.add_argument('sheet')
    d.add_argument('--n', type=int, default=6)
    d.add_argument('--seed', type=int, default=0)
    d.add_argument('--sfa')
    v = sub.add_parser('vec-encoder', help='이전 픽셀 지도 모델(vec_train best.pt) → 인코더 파일')
    v.add_argument('src')
    v.add_argument('dst')
    a = ap.parse_args()
    if a.cmd == 'vec-encoder':
        vec_encoder(a.src, a.dst)
    else:
        train(a) if a.cmd == 'train' else draw(a)


if __name__ == '__main__':
    main()
