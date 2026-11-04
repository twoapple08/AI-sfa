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
import hashlib
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
import seq_coord2 as C2  # noqa: E402
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


HOLDOUT_EXCLUDE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data', 'holdout_exclude.json')


def npz_prefix(rel):
    """seq_data가 파일 하나로 만든 npz 이름의 앞부분(seq_data.save 이름 규칙과 같음)."""
    return rel.replace('/', '__').replace(' ', '_')[:-4] + '__'


def holdout_exclude():
    """새 작품 시험(sv)에서 뺄 것: {파일: 장 Position 목록 또는 None(파일 전체)}. 학습 파일과 같은 그림인 시험 장만
    (11-01: 47112(2_2)-1의 94장 중 7·8장이 학습 파일 바람1-1(1장)과 같음 — 처음엔 파일 전체를 뺐다가 장 단위로 고침)."""
    if not os.path.exists(HOLDOUT_EXCLUDE):
        return {}
    with open(HOLDOUT_EXCLUDE, encoding='utf-8') as fh:
        return {e['file']: (set(e['positions']) if e.get('positions') is not None else None) for e in json.load(fh)['exclude']}


class Data:
    """npz 전부를 메모리에. 그림은 입력 크기로 줄여 JPEG(품질 95)로 압축해 둔다(2만 장 × 640×360 원본이면 15GB → 약 1.5GB).
    이미 H.264로 압축된 장이라 JPEG 95의 추가 손실은 작다. 묶음을 만들 때 푼다."""

    def __init__(self, folder, maxlen, in_w, jpeg=True, workers=None, exclude=(), coord2=False):
        self.in_w, self.in_h = in_w, in_w * 9 // 16
        self.img, self.tok, self.fld, self.meta, self.hwr = [], [], [], [], []
        paths = sorted(glob.glob(os.path.join(folder, '*.npz')))
        exclude = exclude if isinstance(exclude, dict) else {r: None for r in exclude}
        whole = tuple(npz_prefix(r) for r, ps in exclude.items() if ps is None)
        part = {npz_prefix(r): ps for r, ps in exclude.items() if ps is not None}
        self.excluded = [p for p in paths if whole and os.path.basename(p).startswith(whole)]   # 파일 전체
        self.excluded_frames = 0                                                                # 장 단위
        paths = [p for p in paths if p not in self.excluded]
        jobs = [(p, maxlen, self.in_w, self.in_h, jpeg) for p in paths]
        video = bool(paths) and 'vid' in np.load(paths[0]).files
        workers = workers or (os.cpu_count() or 1)
        if video and workers > 1 and len(jobs) > 1:   # 순서 그대로(imap)라 결과는 한 프로세스로 읽은 것과 같다
            from multiprocessing import Pool
            with Pool(min(workers, len(jobs))) as pool:
                parts = list(pool.imap(_load_npz, jobs, chunksize=4))
        else:
            parts = map(_load_npz, jobs)
        for path, got in zip(paths, parts):
            drop = next((ps for pre_, ps in part.items() if os.path.basename(path).startswith(pre_)), set())
            for im, tk, fd, mt, hr in got:
                if mt.get('pos') in drop:
                    self.excluded_frames += 1
                    continue
                self.img.append(im)
                self.tok.append(tk)
                self.fld.append(fd)
                self.meta.append(mt)
                self.hwr.append(hr)
        if coord2:   # 두 단계 좌표(seq_coord2): 저장 자료를 불러올 때 바꾼다. 길어진 장이 한도를 넘으면 뺀다(수를 기록)
            keep = []
            for i, (tk, fd) in enumerate(zip(self.tok, self.fld)):
                t2, f2 = C2.to_two(tk, fd)
                if len(t2) <= maxlen:
                    self.tok[i], self.fld[i] = t2, f2
                    keep.append(i)
            self.coord2_dropped = len(self.tok) - len(keep)
            for name in ('img', 'tok', 'fld', 'meta', 'hwr'):
                setattr(self, name, [getattr(self, name)[i] for i in keep])
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
    def __init__(self, d=384, layers=6, heads=6, maxlen=2048, backbone='resnet34', pretrained=True, stride=16, sine=False, grid=None,
                 coord2=False):
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
        # coord2(11-04): 좌표를 거친 칸+세부 칸 두 토큰으로(seq_coord2). 어휘 뒤에 C·F 토큰을 붙인다
        self.coord2 = coord2
        self.vocab = C2.VOCAB2 if coord2 else K.VOCAB
        self.emb = nn.Embedding(self.vocab, d)
        self.fld_emb = nn.Embedding(len(K.FIELDS), d)   # 입력 토큰의 칸 종류(같은 수라도 좌표·색 구분)
        self.pos = nn.Embedding(maxlen + 1, d)
        layer = nn.TransformerDecoderLayer(d, heads, 4 * d, dropout=0.1, batch_first=True, norm_first=True)
        self.dec = nn.TransformerDecoder(layer, layers)
        self.norm = nn.LayerNorm(d)
        self.head = nn.Linear(d, self.vocab)
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
            num = (tok >= K.OFF) & (tok < K.VOCAB)
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


def token_loss(logits, tgt, fld):
    """다음 토큰 채점. 수 칸(좌표·T·굵기·색)은 정확한 칸 50% + 이웃 ±2칸 분포 50%(그 칸의 합법 범위 안에서만, 무게 다시 맞춤).
    돌려줌: 토큰별 손실, PAD 제외 마스크. 기존 학습/검증과 비교용 목적함수가 공유한다."""
    logp = F.log_softmax(logits.float(), -1)
    mask = tgt != K.TOK['PAD']
    exact = -logp.gather(-1, tgt[..., None])[..., 0]
    soft_on = SOFT.to(tgt.device)[fld] & (tgt >= K.OFF) & (tgt < K.VOCAB)   # coord2의 C·F 토큰은 정확한 칸만
    hi = SOFT_HI.to(tgt.device)[fld]
    v = tgt - K.OFF
    soft = torch.zeros_like(exact)
    wsum = torch.zeros_like(exact)
    for k, w in zip(range(-2, 3), SOFT_W):
        ok = ((v + k) >= 0) & ((v + k) <= hi)
        j = (tgt + k).clamp(K.OFF, logits.shape[-1] - 1)
        soft = soft - w * ok * logp.gather(-1, j[..., None])[..., 0]
        wsum = wsum + w * ok
    soft = soft / wsum.clamp_min(1e-6)
    per = torch.where(soft_on, 0.5 * exact + 0.5 * soft, exact)
    return per, mask


def loss_fn(logits, tgt, fld):
    """기존 토큰 평균 손실·맞힘·토큰 수. 기존 판정/학습의 기본 동작은 유지한다."""
    per, mask = token_loss(logits, tgt, fld)
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


def allowed_mask(al, dev, vocab=None):
    specs, lo, hi, _ = al
    m = torch.full((vocab or K.VOCAB,), float('-inf'), device=dev)
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
        if net.sine and K.OFF <= tok < K.VOCAB:
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
def answer_tokens(tok):
    """자료의 정답 토큰열을 기존 토큰 공간으로(coord2 자료면 C·F를 합친다). 기존 자료는 그대로."""
    tok = [int(t) for t in tok]
    return C2.merge(tok) if any(t >= K.VOCAB for t in tok) else tok


def coord_errors(lg, tk, fd, coord2=False):
    """교사 강제 좌표 오차(%, 칸×XSTEP). 기존: 좌표 자리 argmax. coord2: C 자리가 틀리면 거친 칸 차×FINE,
    맞으면 이어지는 F 자리의 세부 칸 차(정답 C를 넣은 상태의 F 예측)."""
    tgt, mk = tk[:, 1:], fd[:, 1:] == K.FID['coord']
    if not coord2:
        return ((lg[..., K.OFF:].argmax(-1) + K.OFF - tgt).abs()[mk].float() * K.XSTEP).tolist()
    pc = lg[..., C2.C0:C2.F0].argmax(-1) + C2.C0
    pf = lg[..., C2.F0:C2.VOCAB2].argmax(-1) + C2.F0
    out = []
    t, c_, f_ = tgt[0].tolist(), pc[0].tolist(), pf[0].tolist()
    for j, v in enumerate(t):
        if C2.C0 <= v < C2.F0 and j + 1 < len(t):
            if c_[j] != v:
                out.append(abs(c_[j] - v) * C2.FINE * K.XSTEP)
            else:
                out.append(abs(f_[j + 1] - t[j + 1]) * K.XSTEP)
    return out


def mass_pick(lg, al, big_mass=False, coord_window=0):
    """선택 기능(2026-11-04 진단): 수 자리에서 확률 합으로 고른다. 기본값(False, 0)이면 기존 argmax와 같다.
    big_mass: BIG 한 토큰을 범위 안 수 전체 확률 합과 비교해, 합이 크면 BIG을 고르지 않는다.
    coord_window: 좌표 자리에서 ±창 칸 확률 합이 가장 큰 곳을 찾고 그 창 안의 최고 칸을 고른다.
    근거: 0.025% 초미세 칸에 확률이 흩어져 BIG 하나가 탐욕 선택을 이기던 문제(docs/SEQ-CONVERTER-DIAGNOSIS-2026-11-04.md)."""
    specs, lo, hi, field = al
    big = K.TOK['BIG']
    if big_mass and big in specs and hi >= lo:
        p = F.softmax(lg, -1)
        if p[big] < p[K.OFF + lo:K.OFF + hi + 1].sum():
            lg = lg.clone()
            lg[big] = float('-inf')
    t = int(lg.argmax())
    if coord_window and field == 'coord' and t >= K.OFF and hi - lo > 4 * coord_window:
        a0, b0 = K.OFF + lo, K.OFF + hi + 1
        p = F.softmax(lg, -1)[a0:b0]
        sm = F.avg_pool1d(p[None, None], 2 * coord_window + 1, 1, coord_window, count_include_pad=False)[0, 0]
        c = int(sm.argmax())
        a, b = max(0, c - coord_window), min(len(p), c + coord_window + 1)
        t = a0 + a + int(p[a:b].argmax())
    return t


def generate(net, img, hwr, maxlen=None, temp=0.0, reason=False, big_mass=False, coord_window=0):
    """문법 강제 생성(한 장, KV 캐시). 돌려주는 끝냄은 '스스로 끝냄'만 참(GPT 1라운드 ⑤: 한도 64단어 전 강제 끝냄도 참이던 것).
    reason=True면 (토큰, 끝냄, 사유) — 사유 'eos'(스스로)·'forced'(한도 가까이 강제)·'limit'(한도에서 끊김).
    big_mass/coord_window: 탐욕 생성의 수 선택 보정(mass_pick). 기본은 꺼짐이라 기존 결과와 같다.
    coord2 모델: 좌표를 C→F 두 단계로 고르고, 돌려주는 토큰은 기존 토큰열로 합친 것(판정·채점은 그대로).
    maxlen은 합친 토큰 수 기준이고, 안쪽 두 단계 토큰 수는 모델 한도(net.maxlen)를 넘지 않는다."""
    dev = img.device
    maxlen = maxlen or net.maxlen
    two = getattr(net, 'coord2', False)
    vocab = getattr(net, 'vocab', K.VOCAB)
    if two:
        coord_window = 0   # 좌표 자리가 C(128칸)·F(64칸)로 나뉘어 창 선택이 필요 없다
    inner_cap = net.maxlen if two else maxlen
    mem = net.memory(img[None], torch.tensor([hwr], dtype=torch.float32, device=dev))
    cache = Cache(net, mem)
    g = C2.grammar2() if two else K.grammar()
    al = next(g)
    toks, flds = [], []
    merged = 0   # 합친 토큰 수(C 토큰은 다음 F와 하나)
    forced = False

    def out(done, why):
        res = C2.merge(toks) if two else toks
        return (res, done, why) if reason else (res, done)
    while merged < maxlen and len(toks) < inner_cap:
        if toks:
            lg = cache.step(toks[-1], flds[-1])
        else:
            lg = torch.zeros(vocab, device=dev)
        lg = lg + allowed_mask(al, dev, vocab)
        if (merged >= maxlen - 64 or len(toks) >= inner_cap - 96) and TOK_EOS in al[0]:   # 길이 한도 가까우면 끝낼 수 있는 자리에서 끝낸다
            forced = int(lg.argmax()) != TOK_EOS   # 모델이 원래도 끝내려 했으면 강제가 아니다
            lg = torch.full_like(lg, float('-inf'))
            lg[TOK_EOS] = 0
        t = int(torch.multinomial(F.softmax(lg / temp, -1), 1)) if temp > 0 else mass_pick(lg, al, big_mass, coord_window)
        toks.append(t)
        flds.append(K.FID[al[3]] if t >= K.OFF else K.FID['spec'])
        merged += not (C2.C0 <= t < C2.F0)
        try:
            al = g.send(t)
        except StopIteration:
            return out(not forced, 'forced' if forced else 'eos')
    return out(False, 'limit')


def max_rss_gb():
    """이 프로세스의 최대 상주 메모리(GB, 리눅스 ru_maxrss는 KB). 측정 못 하면 None."""
    try:
        import resource
        return round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 2 ** 20, 2)
    except Exception:
        return None


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
    if a.coord2:
        cfg['coord2'] = True
    stage_dirs = [x for x in a.stages.split(',') if x] if a.stages else []
    if stage_dirs:   # 해상도 단계(사용자 10-29·10-31 복원): 깨끗한 1080부터 720·480을 거쳐 기본 입력(360)으로 — 화질 나쁜 애니 자료도 깔끔하게 옮기는 실력
        frac = [float(v) for v in a.stage_frac.split(',')]
        if len(frac) != len(stage_dirs) + 1 or abs(sum(frac) - 1) > 1e-6:
            raise SystemExit(f'--stage-frac은 단계 {len(stage_dirs) + 1}개(고해상도 {len(stage_dirs)} + 기본)이고 합이 1이어야 함: {a.stage_frac}')
        cfg['stages'] = dict(w=[npz_width(d) for d in stage_dirs], frac=frac, mix=a.stage_mix)
    # 시계 셋(GPT 2라운드 3-1, 11-01): done_min = 벽시계 사용 분(기록·예산), train_min = 학습 진행(학습 걸음에 쓴 시간 — 자료 읽기·검증·
    # 생성·저장 제외), plan_min = 학습 진행 계획(분). 학습률·해상도 단계·쉬운 것부터·공식 판정의 '계획 끝'은 모두 train_min / plan_min.
    st = dict(step=0, best=1e9, done_min=0.0, train_min=0.0, plan_min=a.plan_minutes or a.minutes, budget=a.tok_budget, grad_ckpt=a.grad_ckpt,
              px=a.px_budget, stage=0)
    cands = [p_ for p_ in (ck, ck + '.fallback') if os.path.exists(p_)]   # 예비 파일이 더 새것이면 그것(저장 실패 대비, I-08)
    src_ck = max(cands, key=os.path.getmtime) if cands else None
    saved = torch.load(src_ck, map_location='cpu', weights_only=False) if src_ck else None
    if src_ck and src_ck != ck:
        print('이어하기: 예비 저장본에서', flush=True)
    if saved:
        cfg = saved['cfg']   # 이어하기: 처음 정한 모델 크기·입력 크기·계획 그대로(명령줄 값보다 우선)
        st.update(saved['state'])
        if 'train_min' not in saved['state']:   # 11-01 이전 저장본(벽시계 진행): 그 값을 학습 진행으로 넘겨받는다
            st['train_min'] = st['done_min']
            print(f"옛 저장본: 학습 진행을 벽시계 {st['done_min']:.0f}분으로 시작", flush=True)
        if a.plan_minutes and a.plan_minutes < st['plan_min']:
            print(f"계획 축소 요청({a.plan_minutes:.0f} < 저장 계획 {st['plan_min']:.0f}분)은 하지 않음 — 계획은 첫 회차에 고정, 연장만 가능", flush=True)
        if a.plan_minutes > st['plan_min']:   # 계획을 더 길게 다시 정함(연장 — 단계는 되돌아가지 않고, 단계마다 도달한 길이 분위도 내려가지 않는다)
            st['plan_min'] = a.plan_minutes
        elif not a.plan_minutes and st['train_min'] + a.minutes > st['plan_min']:
            # 계획을 안 정했으면 이번 실행 시간만큼 늘린다(5060을 여러 번 나눠 돌릴 때 '이미 100%'로 끝나지 않게).
            # 재시작이 아니라 계획 분모 연장: 진행률이 줄어든 만큼 코사인 중간 위치에서 이어진다(GPT 2차: 60분씩 늘리면 시작 학습률 0.53→0.29→0.19배)
            st['plan_min'] = st['train_min'] + a.minutes
            print(f"계획을 {st['plan_min']:.0f}분으로 늘림(이번 실행 {a.minutes:.0f}분, 학습률은 늘어난 계획의 코사인 위치에서)", flush=True)
    t0 = time.time()
    c2 = cfg.get('coord2', False)
    va = Data(a.val, cfg['maxlen'], cfg['in_w'], exclude=holdout_exclude(), coord2=c2)
    if va.excluded or va.excluded_frames:
        print(f'새 작품 시험에서 뺀 것: 파일 묶음 {len(va.excluded)}개·장 {va.excluded_frames}개(학습 파일과 같은 그림, data/holdout_exclude.json)', flush=True)
    sv = Data(a.shift_val, cfg['maxlen'], cfg['in_w'], coord2=c2) if a.shift_val else None   # 위치 시험(학습 파일 + 학습에 없던 고정 이동)
    js = J.JudgeSet(a.judge, cfg['in_w']) if a.judge else None   # 판정 장치(11-01): 평가 목록 고정 장 × 이동 4방향
    js_reduced = False
    if js is not None:   # 공식 자격 = 저장소 고정 평가 목록과 같은 자료(GPT 코드 검토 I-06: 판·어휘만 보고, 다른·축소 자료도 '전체 목록'으로 공식이 될 수 있었다)
        list_ok = judge_list_ok(js.meta, J.load_manifest())
        c_ok, c_why = J.content_ok(js, J.load_manifest())   # 내용도 목록과 맞는지(GPT 재확인 R-04)
        if not c_ok:
            print('주의: 판정 자료 내용이 평가 목록과 다름:', c_why, flush=True)
            list_ok = False
        judge_id = f"{js.meta.get('manifest_sha')}:{js.meta.get('version')}"
        if st.setdefault('judge_id', judge_id) != judge_id:   # 첫 회차와 다른 평가 목록이면 공식 아님(같은 학습의 판정끼리 같은 목록)
            list_ok = False
        if not list_ok:
            js_reduced = True
            print('주의: 판정 자료가 저장소 고정 평가 목록(또는 첫 회차 목록)과 다름 — 공식 판정 없음(추세만)', flush=True)
    if js is not None and a.judge_n:
        js_reduced = js_reduced or a.judge_n < len(js)
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
            sets[i] = Data(stage_dirs[i] if i < len(stage_dirs) else a.data, cfg['maxlen'], widths[i], coord2=c2)
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
              sine=cfg.get('sine', False), grid=cfg.get('grid'), coord2=cfg.get('coord2', False)).to(dev)
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
        print(f"이어하기: {st['step']}걸음, 학습 진행 {st['train_min']:.2f}/{st['plan_min']:.0f}분(벽시계 누적 {st['done_min']:.0f}분), best {st['best']:.4f}", flush=True)
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
    # 회차 마감(GPT 2라운드 3-2): 작업자가 준 절대 시각(작업자 시작 기준). 없으면 이번 실행 --minutes.
    deadline = a.deadline if a.deadline else t_sess + a.minutes * 60
    rate = st.setdefault('rate', {})   # 실측 속도(저장본에 남아 다음 회차 예상에 쓴다): val=[초, 토큰], gen={폭: [초, 토큰, 장]}, save=[초, 번]
    # 검증 대상 고정: 시험 자료에서 고르게 val_n장, 묶음은 처음 토큰 한도로(학습 한도가 줄어도 같은 대상, GPT 검토 10-30)
    v_idx = sorted(set(np.linspace(0, len(va) - 1, min(a.val_n, len(va))).astype(int).tolist())) if len(va) else []
    v_batches = make_batches_fixed(va, a.max_batch, a.tok_budget, v_idx)
    vk, vk_batches = None, {}
    if a.val_kind:   # 실제·조합 고정 검증 자료(같은 해상도 640, 정답 길이 셋으로 나눔)
        vk = Data(a.val_kind, cfg['maxlen'], cfg['in_w'], coord2=c2)
        kinds = ['real' if kind_of(vk, k).startswith('real') else 'comp' for k in range(len(vk))]
        L = np.array([len(t) for t in vk.tok])
        q1, q2 = np.quantile(L, [1 / 3, 2 / 3]) if len(L) else (0, 0)
        for k in range(len(vk)):
            band = 'short' if L[k] <= q1 else ('mid' if L[k] <= q2 else 'long')
            vk_batches.setdefault(f'{kinds[k]}_{band}', []).append(k)
        vk_batches = {key: make_batches_fixed(vk, a.max_batch, a.tok_budget, idx) for key, idx in sorted(vk_batches.items())}
        print('종류별 검증 자료', {key: sum(len(b) for b in bs) for key, bs in vk_batches.items()}, flush=True)
    v_tok = sum(len(va.tok[x]) for b in v_batches for x in b)
    vk_tok = sum(len(vk.tok[x]) for bs in vk_batches.values() for b in bs for x in b) if vk is not None else 0
    # 검증 목록 식별(GPT 2라운드 6-3): 제외·자료 판에 따라 고른 장이 달라지면 해시가 달라진다 — 다른 목록의 성적을 같은 장의 개선처럼 비교하지 않게
    val_list = dict(n=len(v_idx), hash=hashlib.sha1(json.dumps([[va.meta[x].get('file'), va.meta[x].get('pos')] for x in v_idx]).encode()).hexdigest()[:12])
    print('검증 목록', val_list, flush=True)
    g_idx = v_idx[::max(1, len(v_idx) // a.gen_n)][:a.gen_n]   # 생성 채점용 고정 장
    s_idx = (sorted(set(np.linspace(0, len(sv) - 1, min(a.gen_n, len(sv))).astype(int).tolist())) if sv is not None and len(sv) else [])

    def active_min():
        return (time.time() - t_sess - (yl.paused - p_sess)) / 60

    def final_plan(final=True):
        """평가에서 할 생성 목록 [(입력 폭, 길이 상한)] — 판정은 공식이면 상한 없음(모델 최대), 추세면 장마다 네 방향 정답 최대 × 배수.
        final=False면 중간 평가(판정 방향 --judge-dirs, 추세)."""
        out = [(cfg['in_w'], gen_cap(len(va.tok[i]))) for i in g_idx]
        out += [(cfg['in_w'], gen_cap(len(sv.tok[i]))) for i in s_idx]
        if js is not None:
            w = widths[st['stage']]
            w = w if w in js.stage else cfg['in_w']
            nd_ = a.judge_dirs_final if final else a.judge_dirs
            for w_, nd in [(w, nd_)] + ([(cfg['in_w'], 2)] if final and w != cfg['in_w'] else []):
                off = final and official_judgment(True, st['plan_min'], st['plan_min'], js_reduced, w_, cfg['in_w'])
                out += [(w_, cfg['maxlen'] if off else gen_cap(max(len(t) for t in js.tok[i]))) for i in range(len(js)) for _ in range(nd)]
        return out

    def gen_model():
        """생성 한 장 시간 = 폭별 고정 비용 a_w + 토큰당 비용 b × 토큰 수. b는 폭 공통(디코더 그림 특징 칸이 폭과 상관없이 45×80).
        같은 폭 안 표본으로 절편·기울기를 함께 추정한다(폭별 평균을 뺀 회귀, b = Σ(t−t̄_w)(s−s̄_w) / Σ(t−t̄_w)², a_w = s̄_w − b·t̄_w).
        식별 조건: 같은 폭 안에 길이가 2배 이상·64토큰 이상 다른 표본이 있어야 한다. 아니면 None → 기본 몫(--final-reserve-min).
        (GPT 확인 11-01: 예전 식은 가장 짧은 장 시간을 고정 비용으로 통째로 빼 선형 모의 표본 T=1+0.01L에서 2,048토큰을 6.76초로
        예상했다(참값 21.48). 표본 하나면 기울기 0.)"""
        gs = {int(w): v for w, v in rate.get('gen_s', {}).items() if v}
        num = den = 0.0
        ok = False
        means = {}
        for w, v in gs.items():
            t = np.array([x[0] for x in v], float)
            y = np.array([x[1] for x in v], float)
            means[w] = (t.mean(), y.mean())
            num += float(((t - t.mean()) * (y - y.mean())).sum())
            den += float(((t - t.mean()) ** 2).sum())
            ok |= len(v) >= 2 and t.max() >= 2 * t.min() and t.max() - t.min() >= 64
        if not ok or den <= 0:
            return None
        b = max(num / den, 0.0)
        a_w = {w: max(ym - b * tm_, 0.0) for w, (tm_, ym) in means.items()}
        return a_w, b

    def gen_cost(final):
        """생성 평가 예상 초 — 모든 장이 길이 상한까지 간다고 보는 보수적 값. 실측이 없으면 None.
        실측이 없는 폭의 고정 비용은 아는 폭에서 화소 수 비례로 올려 잡는다."""
        m = gen_model()
        if m is None:
            return None
        a_w, b = m

        def a_of(w):
            return a_w[w] if w in a_w else max(a * max(1.0, (w / k) ** 2) for k, a in a_w.items())
        return sum(a_of(w) + b * cap for w, cap in final_plan(final))

    def final_cost():
        """마지막 평가(교사 강제 검증·종류별 검증·생성 채점·판정·저장) 예상 초 — 보수적: 생성은 상한까지 간다고 본다.
        실측이 없으면 --final-reserve-min. 실측 속도는 회차마다 갱신해 저장본에 남긴다(첫 GPU 회차의 중간 평가부터)."""
        rv = rate.get('val')
        if not rv or (a.gen_minutes and gen_model() is None):
            return a.final_reserve_min * 60
        spt_v = rv[0] / max(rv[1], 1)
        gen = gen_cost(True) if a.gen_minutes else 0.0
        sv_ = rate.get('save', [30.0, 1])
        return a.reserve_margin * ((v_tok + vk_tok) * spt_v + gen + 2 * sv_[0] / sv_[1]) + 60

    def save_ckpt(final=False):
        """저장. 성공하면 True. 본 파일을 못 바꾸면(Windows 파일 잠금 등) 예비 파일(ckpt.pt.fallback)에 쓴다 — 이어하기는 둘 중 새것을 읽는다.
        마지막 저장(final)이 둘 다 실패하면 멈춘다: 공식 결과(official_n 등)가 저장본에 없는 채로 '정상 끝'이 되지 않게(GPT 코드 검토 I-08)."""
        t_s = time.time()
        st['done_min'] = done0 + active_min()
        rng = dict(py=random.getstate(), torch=torch.get_rng_state(), cuda=torch.cuda.get_rng_state() if dev == 'cuda' else None)
        obj = dict(model=net.state_dict(), opt=opt.state_dict(), scaler=scaler.state_dict(), rng=rng, cfg=cfg, state=dict(st))
        ok = VT.save(obj, ck) is not False
        if not ok:
            ok = VT.save(obj, ck + '.fallback', tries=5) is not False
            print('저장: 본 파일 실패 → 예비 파일', '성공' if ok else '도 실패', flush=True)
            st['save_failed'] = st.get('save_failed', 0) + 1
        if ok:
            r_ = rate.setdefault('save', [0.0, 0])
            r_[0] += time.time() - t_s
            r_[1] += 1
        elif final:
            raise SystemExit('마지막 저장 실패(본·예비 모두) — 이 회차 결과가 저장본에 없음. 출력 폴더 잠금을 풀고 다시 실행')
        return ok

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
        t_v = time.time()
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
        r_ = rate.setdefault('val', [0.0, 0])
        r_[0] += time.time() - t_v
        r_[1] += int(tn)
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
            r_ = rate.setdefault('gen', {}).setdefault(str(int(im.shape[1])), [0.0, 0, 0])   # 폭별 생성 합계(기록용)
            r_[0] += time.time() - t1
            r_[1] += len(toks) + 1
            r_[2] += 1
            gs = rate.setdefault('gen_s', {}).setdefault(str(int(im.shape[1])), [])   # 장마다 (토큰, 초) 최근 64개 — 고정 비용과 토큰당 비용을 나눠 잡는다
            gs.append([len(toks) + 1, time.time() - t1])
            del gs[:-64]
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

    def official_gate(final, w):
        """공식 판정 자격과 횟수(GPT 코드 검토 P-02). 조건(official_judgment)을 만족해도, 같은 계획 끝에서 이미 공식 판정을 했으면
        재계산(공식 아님, 'repeat'), 이미 두 번(최초 끝·연장 끝) 했으면 셋째(공식 아님, 'third'). → (공식인가, 막힌 이유)"""
        if not official_judgment(final, st['train_min'], st['plan_min'], js_reduced, w, cfg['in_w']):
            return False, None
        plans = st.setdefault('official_plans', [])
        if st['plan_min'] in plans:
            return False, 'repeat'
        if st.get('official_n', 0) >= 2:
            return False, 'third'
        st['official_n'] = st.get('official_n', 0) + 1
        plans.append(st['plan_min'])
        return True, None

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
            official, blocked = official_gate(final, w)
            reasons.clear()
            cap_of = (lambda i: None) if official else (lambda i: max(len(t) for t in js.tok[i]))
            res, gens = J.evaluate(js, lambda i, d: gen_img(js.image(i, d, w), js.ents[i]['hwr'], cap_of(i)), dirs=range(nd),
                                   memo=memo[2], memo4=memo[4])
            rec_ = J.flat(res)
            rec_.update(judge_dirs=nd, judge_w=w, judge_official=official, judge_official_blocked=blocked, judge_official_n=st.get('official_n', 0) if official else None,
                        judge_reduced=js_reduced, judge_end=dict(reasons),
                        judge_cap='max' if official or not a.gen_len_mult else f'ans4x{a.gen_len_mult:g}+128')   # 생성 길이 상한(추세 비교 조건, GPT 재확인 R-06)
            print(f'[{w}폭 {"공식" if official else "추세"}]', J.summary_line(res, official), f"({round(time.time() - t1)}초, {nd}방향, 끝냄 {dict(reasons)})", flush=True)
            judge_sheet(gens, w)
            if final and w != cfg['in_w']:
                t2 = time.time()
                reasons.clear()
                off360, blocked360 = official_gate(final, cfg['in_w'])
                cap360 = (lambda i: None) if off360 else (lambda i: max(len(t) for t in js.tok[i]))
                r2, _ = J.evaluate(js, lambda i, d: gen_img(js.image(i, d), js.ents[i]['hwr'], cap360(i)), dirs=range(2), memo=memo[2])
                rec_.update(J.flat(r2, 'judge360_'))
                rec_.update(judge360_end=dict(reasons), judge360_official=off360, judge360_official_blocked=blocked360, judge360_official_n=st.get('official_n', 0) if off360 else None)
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
            sums['errs'] += coord_errors(lg, tk, fd, getattr(net, 'coord2', False))
            sc = OS.score(K.decode(toks), K.decode(answer_tokens(ds_.tok[i])), hwr=ds_.hwr[i])
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
    # 중간 검증·생성 채점 간격은 학습 진행 분(train_min)으로 잰다(Kaggle CPU 점검 11-02: 1080 자료 읽기 16분이 '지난 시간'으로 잡혀
    # 첫 걸음 직후 33분짜리 검증이 돌고 마감을 넘었다). 저장 간격만 벽시계.
    val_at = gen_at = st['train_min']
    last_v = None   # 마지막 중간 검증 결과(걸음, 결과) — 모델이 그대로면 마지막 검증에서 다시 재지 않는다
    oom = skipped = 0
    step_s = [0.0]   # 최근 한 걸음 벽시계(초) — 마감 전에 다음 걸음을 시작할지
    stop_why = 'plan'
    fails_in_row = 0

    def train_tick(t_it, l0, p0, ok=True):
        """이번 반복의 시간(반복 시작부터 지금까지 − 자료 읽기 − 양보로 쉰 시간). 성공한 업데이트면 학습 진행(train_min)과
        tm['train']에, 실패한 시도(메모리 부족·비정상 손실)면 fail_min에만 더한다 — 실패는 예산(벽시계)에는 들어가도 학습률·단계·분위·
        공식 계획 끝을 진행시키지 않는다(GPT 확인 11-01). 검증·생성·저장은 이 구간 밖이다."""
        dt_ = max(0.0, time.time() - t_it - (tm_load[0] - l0) - (yl.paused - p0))
        if ok:
            st['train_min'] += dt_ / 60
            tm['train'] += dt_
        else:
            st['fail_min'] = st.get('fail_min', 0.0) + dt_ / 60
        step_s[0] = dt_
    while st['train_min'] < st['plan_min']:
        if time.time() + final_cost() + 2 * step_s[0] > deadline:   # 마지막 평가 몫을 남기고 멈춘다(GPT 2라운드 3-2)
            stop_why = 'deadline'
            break
        yl.tick()
        t_it, l0, p0 = time.time(), tm_load[0], yl.paused
        prog = st['train_min'] / st['plan_min']
        k = len(widths) - 1
        if stg:
            k = max(st['stage'], stage_of(prog, stg['frac']))   # 단계는 되돌아가지 않는다(이어하기로 계획이 늘어 진행률이 줄어도)
            if k != st['stage']:
                print(time.strftime('%H:%M'), f"해상도 단계 {widths[st['stage']]} → {widths[k]}폭 (진행 {prog * 100:.1f}%)", flush=True)
                st['stage'] = k
            for j in [j for j in sets if j not in (k, k - 1, len(widths) - 1)]:
                sets.pop(j)
                bq.pop(j, None)   # 지난 단계 자료는 메모리에서 내린다
        i = k - 1 if k > 0 and stg and random.random() < stg['mix'] else k   # 새 해상도 70% + 앞 단계 30%(반복마다 묶음 선택 확률)
        sel = st.setdefault('sel', {}).setdefault(f"{widths[i]}|{'cur' if i == k else 'mix'}", [0, 0, 0, 0.0])   # [선택, 성공 업데이트, 실패, 학습 초](GPT 2라운드 3-4)
        sel[0] += 1
        ds = stage_set(i)
        if time.time() + final_cost() + 2 * step_s[0] > deadline:   # 자료 읽기(1080 약 15분) 뒤 다시 확인(GPT 확인 11-01)
            sel[0] -= 1
            stop_why = 'deadline'
            break
        lv = 1.0
        if not a.no_curriculum and i == k:   # 쉬운 것부터(11-01): 지금 단계 자료는 정답 길이 분위를 단계 진행에 따라 늘린다. 앞 단계 섞기는 전체
            lv = cur_quantile(stage_progress(prog, stg['frac'] if stg else [1.0], k))
            cm = st.setdefault('cur_max', {})   # 연장 정책(GPT 2라운드 3-3): 계획을 늘려 진행률이 줄어도 이 단계에서 도달한 분위 아래로 내려가지 않는다
            lv = max(lv, cm.get(str(k), 0.0))
            cm[str(k)] = lv
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
            if a.objective != 'token-v1':   # 종료·첫 객체·외형 보조 손실(seq_objective, 11-05). 기록용 맞힘(acc)은 기존 손실 기준 그대로
                from seq_objective import objective
                loss, _parts = objective(lg, tok[:, 1:], fld[:, 1:], [ds.tok[x] for x in b], a.objective)
            fh = field_hits(lg.detach(), tok[:, 1:], fld[:, 1:])
            if not torch.isfinite(loss):
                skipped += 1
                sel[2] += 1
                opt.zero_grad(set_to_none=True)
                train_tick(t_it, l0, p0, ok=False)
                sel[3] += step_s[0]
                fails_in_row += 1
                if fails_in_row >= a.max_fail_row:
                    stop_why = 'failures'
                    break
                continue
            opt.zero_grad(set_to_none=True)
            scaler.scale(loss).backward()
            scaler.unscale_(opt)
            unscaled = True
            gnorm = nn.utils.clip_grad_norm_(net.parameters(), 1.0)
            if not torch.isfinite(gnorm):
                # 기울기 넘침(GPT 코드 검토 I-01): GradScaler는 step을 건너뛰고 배율만 줄인다. 배율이 없는 경로(CPU·bf16)는 그대로면
                # 비유한 기울기가 옵티마이저에 들어간다 — 둘 다 업데이트 없음으로 보고 실패로 센다(학습 진행·성공 기록에 넣지 않는다)
                # step(opt)는 부르지 않는다(GPT 재확인 R-01): 기울기 값은 유한한데 노름 계산만 넘친 경우 GradScaler는 넘침을 모르므로
                # step이 실제로 옵티마이저를 돌린다(클리핑 0 기울기 + weight decay). update()는 unscale_ 상태 정리용 — 실제 inf면 배율을 줄인다
                if scaler.is_enabled():
                    scaler.update()
                opt.zero_grad(set_to_none=True)
                skipped += 1
                sel[2] += 1
                train_tick(t_it, l0, p0, ok=False)
                sel[3] += step_s[0]
                fails_in_row += 1
                if fails_in_row >= a.max_fail_row:
                    stop_why = 'failures'
                    break
                continue
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
            sel[2] += 1
            train_tick(t_it, l0, p0, ok=False)
            sel[3] += step_s[0]
            fails_in_row += 1
            if fails_in_row >= a.max_fail_row:   # 실패만 이어지면 원인 조사로 멈춘다(학습 진행은 늘지 않으므로 끝없이 돌 수 있다)
                stop_why = 'failures'
                break
            continue
        st['step'] += 1
        sel[1] += 1
        fails_in_row = 0
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
        run.append(loss.item())   # .item()이 GPU를 기다리므로 여기까지의 시간이 실제 계산을 포함한다
        racc.append(acc.item())
        rhn = rhn + fh
        train_tick(t_it, l0, p0)
        sel[3] += step_s[0]
        if st['step'] % a.log_every == 0:
            mem = f' GPU {torch.cuda.max_memory_allocated() / 2**30:.1f}GB' if dev == 'cuda' else ''
            print(f"{st['step']} 손실 {np.mean(run):.3f} 맞힘 {np.mean(racc) * 100:.1f}% 진행 {prog * 100:.1f}% {widths[k]}폭 "
                  f"학습률 {opt.param_groups[0]['lr']:.2e} ({active_min():.1f}분){mem} | 분야 {field_report(rhn)[1]}", flush=True)
            run, racc = [], []
            rhn = np.zeros((NROW, 2))
        mid_cost = a.reserve_margin * (v_tok + vk_tok) * rate['val'][0] / max(rate['val'][1], 1) if rate.get('val') else 0.0
        val_due = st['train_min'] - val_at >= a.val_minutes
        if val_due and time.time() + mid_cost + final_cost() > deadline:
            print(time.strftime('%H:%M'), '중간 검증 건너뜀: 마감 전에 마지막 평가 몫이 모자람', flush=True)
            val_at = st['train_min']
        elif val_due:
            val_at = st['train_min']
            last_val = time.time()
            vl, vc, n, vbad, vhn = validate()
            vkr = validate_kind() if vk is not None else {}
            last_v = (st['step'], (vl, vc, n, vbad, vhn), vkr)
            tm['val'] += time.time() - last_val
            rec = dict(step=st['step'], val=vl, val_acc=vc, val_tokens=n, val_failed=vbad, val_sec=round(time.time() - last_val), stage_steps=dict(st.get('stage_steps', {})),
                       minutes=done0 + active_min(), train_min=st['train_min'], prog=prog, val_list=val_list,
                       oom=oom, skipped=skipped, budget=st['budget'], grad_ckpt=net.grad_ckpt, paused_min=yl.paused / 60,
                       stage_w=widths[k], px=st['px'], **field_report(vhn, 'val_')[0])
            if n and not vbad and vl < st['best']:   # 못 잰 장이 있으면 best 안 바꿈(GPT 2차)
                if VT.save(dict(model=net.state_dict(), cfg=cfg, step=st['step'], val=vl), os.path.join(a.out, 'best.pt')) is not False:
                    st['best'] = vl   # 저장된 뒤에만(GPT 코드 검토 I-08)
            save_ckpt()   # 생성 채점 전에 저장(GPT 2차: 생성 중 문제가 생겨도 학습 상태는 남게)
            last_save = time.time()
            rec.update(vkr)
            g_c = gen_cost(False)
            gen_due = a.gen_minutes and st['train_min'] - gen_at >= a.gen_minutes
            if gen_due and g_c is not None and time.time() + a.reserve_margin * g_c + final_cost() > deadline:
                print(time.strftime('%H:%M'), '중간 생성 평가 건너뜀: 마감 전에 마지막 평가 몫이 모자람', flush=True)
                gen_at = st['train_min']
            elif gen_due:
                gen_at = st['train_min']
                last_gen = time.time()
                rec.update(gen_eval())
                tm['gen'] += time.time() - last_gen
            rec.update(time_sec=dict(tm, load=tm_load[0], wall=time.time() - t_run), expo=dict(st.get('expo', {})), sel=dict(st.get('sel', {})),
                       rss_gb=max_rss_gb(), sets_loaded=sorted(widths[j] for j in sets))   # 메모리(코드 검토 11-01: 1080 단계 4만 장 + 섞기 자료)
            print('검증', rec, flush=True)
            print('검증 분야(100점 만점):', field_report(vhn)[1], flush=True)
            with open(log, 'a', encoding='utf-8') as fh:
                fh.write(json.dumps(rec) + '\n')
        elif time.time() - last_save > a.save_minutes * 60:
            save_ckpt()
            last_save = time.time()
    est_final = final_cost()   # 예상과 실제를 함께 남겨 다음 회차 몫을 맞춘다(GPT 2라운드 3-2 측정)
    t_final = time.time()
    t_v = time.time()   # 마지막 검증 시간도 시간 내역에 넣는다(11-01 흐름 시험: 중간 검증이 없던 회차의 val이 0으로 나왔다)
    same = last_v is not None and last_v[0] == st['step']   # 중간 검증 뒤 업데이트가 없었으면 같은 모델 — 다시 재지 않는다(Kaggle CPU 점검 11-02: 35분 중복)
    vl, vc, n, vbad, vhn = last_v[1] if same else validate()
    if same:
        print('마지막 검증: 중간 검증 뒤 업데이트가 없어 그 결과를 씀', flush=True)
    tm['val'] += time.time() - t_v
    rec = dict(step=st['step'], val=vl, val_acc=vc, val_tokens=n, val_failed=vbad, final=True, minutes=done0 + active_min(),
               train_min=st['train_min'], plan_min=st['plan_min'], stop=stop_why, val_list=val_list,
               stage_steps=dict(st.get('stage_steps', {})), **field_report(vhn, 'val_')[0])
    if n and not vbad and vl < st['best']:
        if VT.save(dict(model=net.state_dict(), cfg=cfg, step=st['step'], val=vl), os.path.join(a.out, 'best.pt')) is not False:
            st['best'] = vl
    save_ckpt(final=not a.gen_minutes)   # 생성 판정이 없으면 이것이 마지막 저장
    if vk is not None:
        t_v = time.time()
        rec.update(last_v[2] if same and last_v[2] else validate_kind())
        tm['val'] += time.time() - t_v
    if a.gen_minutes:
        t_g = time.time()
        rec.update(gen_eval(final=True))
        tm['gen'] += time.time() - t_g
        save_ckpt(final=True)   # 마지막 판정이 올린 공식 횟수(official_n)를 저장본에 남긴다 — 연장 회차가 2로 이어지게(GPT 확인 11-01: 저장 뒤 올려 연장이 다시 1이던 것)
    rec.update(minutes=st['done_min'], fail_min=st.get('fail_min', 0.0), rss_gb=max_rss_gb())   # 마지막 평가·저장 뒤 값(GPT 확인 11-01: 예전엔 교사 검증 직후 값)
    rec.update(time_sec=dict(tm, load=tm_load[0], wall=time.time() - t_run), expo=dict(st.get('expo', {})), sel=dict(st.get('sel', {})),
               cur_max=dict(st.get('cur_max', {})), plan_reached=bool(st['train_min'] >= st['plan_min'] - 1e-6),
               final_est_sec=round(est_final), final_sec=round(time.time() - t_final), deadline_over_sec=round(time.time() - deadline))
    print('마지막 검증', rec, flush=True)
    print('마지막 검증 분야(100점 만점):', field_report(vhn)[1], flush=True)
    with open(log, 'a', encoding='utf-8') as fh:
        fh.write(json.dumps(rec) + '\n')
    print(f"끝 {st['step']}걸음 · 학습 진행 {st['train_min']:.0f}/{st['plan_min']:.0f}분(벽시계 누적 {st['done_min']:.0f}분, 멈춘 이유 {stop_why}) · best {st['best']:.4f} · 메모리 부족 {oom} · 건너뜀 {skipped}", flush=True)


OFFICIAL_W = 640   # 공식 판정 폭 = 360(640×360) 고정(판정 기준 §2·사용자 11-01: 최종적으로 360에서도 잘하나)


def judge_list_ok(meta, manifest):
    """판정 자료가 저장소 고정 평가 목록 그대로인가(GPT 코드 검토 I-06): 목록 해시·(파일, 장, 묶음) 순서·방향 4개·기본 폭 640."""
    key = lambda es: [(e['file'], e['pos'], e['group']) for e in es]  # noqa: E731
    return (meta.get('manifest_sha') == J.manifest_sha(manifest) and key(meta['entries']) == key(manifest['entries'])
            and [list(d) for d in meta['dirs']] == [list(d) for d in J.DIRS] and meta.get('W') == 640)


def official_judgment(final, done_min, plan_min, reduced, w, in_w):
    """공식 판정인가(판정 기준 §2, GPT 1라운드 A·재확인·확인 11-01): 마지막 판정 + 계획 끝 도달 + 고정 평가 목록 전체(--judge-n으로
    줄이지 않음) + 360(640폭) — 판정 폭과 기본 입력 폭이 모두 640이어야 한다(기본 입력을 854 등으로 바꿔 시작한 학습은 공식 판정 없음).
    고해상도 단계 판정·축소 목록 흐름 시험은 계획이 끝나도 추세."""
    return bool(final and done_min >= plan_min - 1e-6 and not reduced and w == in_w == OFFICIAL_W)


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
              grid=c.get('grid'), coord2=c.get('coord2', False))
    net.load_state_dict(s['model'])
    return net.eval().to(dev), c


def seq_xml(hwr, bg='-1'):
    return ET.Element('Sequence', dict(Name='seq', HeightWidthRatio=repr(hwr), FrameCount='1', BackgroundColor=bg))


def draw(a):
    import sfa_render as R
    dev = 'cuda' if torch.cuda.is_available() else 'cpu'
    net, c = load(a.ckpt, dev)
    ds = Data(a.data, c['maxlen'], c['in_w'], coord2=c.get('coord2', False))
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
        ans = K.decode(answer_tokens(ds.tok[i]))
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
    t.add_argument('--minutes', type=float, default=60, help='이번 실행 시간(벽시계, --deadline이 없을 때 마감 = 시작 + 이 값). 계획을 안 정한 이어하기에서는 계획을 이만큼 늘린다')
    t.add_argument('--plan-minutes', type=float, default=0, help='전체 학습 계획(학습 진행 분 — 학습 걸음에 쓴 시간, 읽기·평가 제외). 학습률·단계·쉬운 것부터·공식 판정의 계획 끝 기준. 0이면 --minutes')
    t.add_argument('--deadline', type=float, default=0, help='이번 회차 절대 마감(유닉스 초, 작업자가 줌). 마지막 평가 예상 몫을 남기고 학습을 멈춘다. 0이면 시작 + --minutes')
    t.add_argument('--final-reserve-min', type=float, default=20, help='속도 실측이 없을 때 마지막 평가 몫(분). 실측이 생기면 폭·길이별 예상으로 바뀐다')
    t.add_argument('--max-fail-row', type=int, default=200, help='실패(메모리 부족·비정상 손실)만 이만큼 이어지면 멈춤')
    t.add_argument('--reserve-margin', type=float, default=1.25, help='평가 예상 시간에 곱하는 안전 여유')
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
    t.add_argument('--val-minutes', type=float, default=20, help='중간 검증 간격(학습 진행 분 — 자료 읽기·평가 시간은 세지 않음)')
    t.add_argument('--save-minutes', type=float, default=10)
    t.add_argument('--val-n', type=int, default=400)
    t.add_argument('--gen-n', type=int, default=20, help='생성 채점에 쓰는 고정 시험 장 수')
    t.add_argument('--shift-val', default='', help='위치 시험 자료 폴더(seq_data --fixed) — 생성 채점에 같이')
    t.add_argument('--gen-minutes', type=float, default=60, help='생성 채점 간격(학습 진행 분). 0이면 안 함')
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
    t.add_argument('--objective', default='token-v1', choices=('token-v1', 'balanced-v1'), help='학습 목적함수. balanced-v1 = 종료 균형·첫 객체·외형 보조 손실(seq_objective)')
    t.add_argument('--coord2', action='store_true', help='두 단계 좌표 표현(거친128+세부64, docs/SEQ-COORD-TWO-LEVEL-DESIGN-2026-11-04.md). maxlen은 3072 권장')
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
