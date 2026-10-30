#!/usr/bin/env python3
"""재설계 학습(2026-10-30, docs/VIDEO-TO-SFA-REDESIGN-2026-10-30.md): 영상 장을 보고 SFA 정답 문장(sfa_tokens)을 한 토큰씩 쓰는 모델.
채점 = 원본 SFA 파일의 다음 토큰과 비교(교사 강제 교차 엔트로피). 좌표·색·굵기 같은 수 칸은 이웃 칸에도 점수를 조금 준다.
생성 때는 문법(sfa_tokens.grammar)이 허용한 토큰만 고르므로 결과는 항상 앱이 여는 SFA다.
사용:
  학습: python seq_train.py train 자료폴더 시험자료폴더 출력폴더 [--minutes 60] [--in-w 640] [--d 384 --layers 6]
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
import sfa_tokens as K  # noqa: E402

SOFT = torch.tensor([K.FID[f] in (K.FID['coord'], K.FID['t'], K.FID['thick'], K.FID['glow'], K.FID['color'], K.FID['bg'])
                     for f in K.FIELDS])
TOK_EOS = K.TOK['EOS']
SOFT_W = (0.1, 0.25, 0.3, 0.25, 0.1)   # 이웃 칸 -2..+2 (정확한 칸과 반반 섞는다)


class Data:
    """npz 전부를 메모리에(그림은 입력 크기로 줄여서)."""

    def __init__(self, folder, maxlen, in_w):
        self.in_w, self.in_h = in_w, in_w * 9 // 16
        self.img, self.tok, self.fld, self.meta = [], [], [], []
        for p in sorted(glob.glob(os.path.join(folder, '*.npz'))):
            d = np.load(p)
            meta = json.loads(str(d['meta']))
            off = d['off']
            for i in range(len(off) - 1):
                if off[i + 1] - off[i] > maxlen:
                    continue
                im = d['img'][i]
                if im.shape[1] != in_w:
                    im = cv2.resize(im, (self.in_w, self.in_h), interpolation=cv2.INTER_AREA)
                self.img.append(im)
                self.tok.append(d['tok'][off[i]:off[i + 1]].astype(np.int64))
                self.fld.append(d['fld'][off[i]:off[i + 1]].astype(np.int64))
                self.meta.append(dict(meta, pos=int(d['pos'][i])))
        self.ntok = sum(len(t) for t in self.tok)

    def __len__(self):
        return len(self.img)

    def batch(self, idx):
        L = max(len(self.tok[i]) for i in idx)
        tok = torch.full((len(idx), L), K.TOK['PAD'], dtype=torch.long)
        fld = torch.zeros((len(idx), L), dtype=torch.long)
        for b, i in enumerate(idx):
            tok[b, :len(self.tok[i])] = torch.from_numpy(self.tok[i])
            fld[b, :len(self.fld[i])] = torch.from_numpy(self.fld[i])
        img = torch.from_numpy(np.stack([self.img[i] for i in idx])).permute(0, 3, 1, 2).float() / 255
        return img, tok, fld


class Net(nn.Module):
    def __init__(self, d=384, layers=6, heads=6, maxlen=2048, backbone='resnet34', pretrained=True):
        super().__init__()
        ctor = getattr(torchvision.models, backbone)
        try:
            bb = ctor(weights='DEFAULT' if pretrained else None)
        except Exception as e:  # 내려받기 실패 → 처음부터(기록만)
            print('사전학습 가중치 못 받음:', type(e).__name__, flush=True)
            bb = ctor(weights=None)
        self.enc = nn.Sequential(bb.conv1, bb.bn1, bb.relu, bb.maxpool, bb.layer1, bb.layer2, bb.layer3)   # 1/16, 256채널
        self.proj = nn.Conv2d(256, d, 1)
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
        self.register_buffer('mean', torch.tensor([0.485, 0.456, 0.406]).view(1, 3, 1, 1))
        self.register_buffer('std', torch.tensor([0.229, 0.224, 0.225]).view(1, 3, 1, 1))

    def memory(self, img):
        f = self.proj(self.enc((img - self.mean) / self.std))
        B, C, H, W = f.shape
        pe = self.row.weight[:H, None, :] + self.col.weight[None, :W, :]
        return (f.flatten(2).transpose(1, 2) + pe.reshape(H * W, C)[None])

    def step(self, mem, tok, fld):
        T = tok.shape[1]
        x = self.emb(tok) + self.fld_emb(fld) + self.pos.weight[:T][None]
        causal = torch.triu(torch.full((T, T), float('-inf'), device=tok.device), 1)
        h = self.dec(x, mem, tgt_mask=causal, tgt_key_padding_mask=(tok == K.TOK['PAD']), tgt_is_causal=True)
        return self.head(self.norm(h))

    def forward(self, img, tok, fld):
        return self.step(self.memory(img), tok, fld)


def loss_fn(logits, tgt, fld):
    """다음 토큰 채점. 수 칸(좌표·색·굵기·글로우·T)은 정확한 칸 50% + 이웃 칸 분포 50%."""
    logp = F.log_softmax(logits.float(), -1)
    mask = tgt != K.TOK['PAD']
    exact = -logp.gather(-1, tgt[..., None])[..., 0]
    soft_on = SOFT.to(tgt.device)[fld] & (tgt >= K.OFF)
    soft = torch.zeros_like(exact)
    for k, w in zip(range(-2, 3), SOFT_W):
        j = (tgt + k).clamp(K.OFF, K.VOCAB - 1)
        soft = soft - w * logp.gather(-1, j[..., None])[..., 0]
    per = torch.where(soft_on, 0.5 * exact + 0.5 * soft, exact)
    m = mask.float()
    acc = ((logits.argmax(-1) == tgt) & mask).float().sum() / m.sum()
    return (per * m).sum() / m.sum(), acc


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
def generate(net, img, maxlen=None, temp=0.0):
    """문법 강제 생성(한 장, KV 캐시)."""
    dev = img.device
    maxlen = maxlen or net.maxlen
    mem = net.memory(img[None])
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


def lr_at(step, total, base, warm=300):
    if step < warm:
        return base * (step + 1) / warm
    return base * 0.5 * (1 + math.cos(math.pi * min(1.0, (step - warm) / max(1, total - warm))))


def train(a):
    torch.manual_seed(0)
    random.seed(0)
    dev = 'cuda' if torch.cuda.is_available() else 'cpu'
    if dev == 'cpu':
        torch.set_num_threads(os.cpu_count() or 4)
    t0 = time.time()
    tr = Data(a.data, a.maxlen, a.in_w)
    va = Data(a.val, a.maxlen, a.in_w)
    print(f'자료 학습 {len(tr)}장 {tr.ntok}토큰 · 시험 {len(va)}장 ({time.time() - t0:.0f}초)', flush=True)
    os.makedirs(a.out, exist_ok=True)
    net = Net(a.d, a.layers, a.heads, a.maxlen, a.backbone).to(dev)
    print('변수', sum(p.numel() for p in net.parameters()) // 1000, '천', flush=True)
    opt = torch.optim.AdamW(net.parameters(), lr=a.lr, weight_decay=0.01)
    amp = dev == 'cuda'
    dt = torch.bfloat16 if amp and torch.cuda.get_device_capability(0)[0] >= 8 else torch.float16
    scaler = torch.amp.GradScaler('cuda', enabled=amp and dt == torch.float16)
    step, best = 0, 1e9
    ck = os.path.join(a.out, 'ckpt.pt')
    if os.path.exists(ck):
        s = torch.load(ck, map_location=dev, weights_only=False)
        net.load_state_dict(s['model'])
        opt.load_state_dict(s['opt'])
        step, best = s['step'], s['best']
        print('이어하기', step, flush=True)
    cfg = dict(d=a.d, layers=a.layers, heads=a.heads, maxlen=a.maxlen, backbone=a.backbone, in_w=a.in_w)
    total = a.steps
    log = os.path.join(a.out, 'log.jsonl')
    tstart = time.time()
    last_val = time.time()
    order = []
    run, racc = [], []
    while step < total and (time.time() - tstart) / 60 < a.minutes:
        if not order:
            # 길이가 비슷한 장끼리 묶어 덧댐을 줄인다
            idx = list(range(len(tr)))
            random.shuffle(idx)
            chunks = [sorted(idx[i:i + a.batch * 50], key=lambda k: len(tr.tok[k])) for i in range(0, len(idx), a.batch * 50)]
            order = [c[i:i + a.batch] for c in chunks for i in range(0, len(c), a.batch)]
            random.shuffle(order)
        img, tok, fld = (x.to(dev) for x in tr.batch(order.pop()))
        for g in opt.param_groups:
            g['lr'] = lr_at(step, total, a.lr)
        with torch.autocast(dev, dtype=dt, enabled=amp):
            lg = net(img, tok[:, :-1], fld[:, :-1])
        loss, acc = loss_fn(lg, tok[:, 1:], fld[:, 1:])
        if not torch.isfinite(loss):
            opt.zero_grad(set_to_none=True)
            step += 1
            continue
        opt.zero_grad(set_to_none=True)
        scaler.scale(loss).backward()
        scaler.unscale_(opt)
        nn.utils.clip_grad_norm_(net.parameters(), 1.0)
        scaler.step(opt)
        scaler.update()
        step += 1
        run.append(loss.item())
        racc.append(acc.item())
        if step % a.log_every == 0:
            print(f'{step}/{total} 손실 {np.mean(run):.3f} 맞힘 {np.mean(racc) * 100:.1f}% ({(time.time() - tstart) / 60:.1f}분)', flush=True)
            run, racc = [], []
        if time.time() - last_val > a.val_minutes * 60 or step >= total:
            last_val = time.time()
            net.eval()
            vl, vc, n = 0.0, 0.0, 0
            with torch.no_grad():
                for i in range(0, min(len(va), a.val_n), a.batch):
                    im, tk, fd = (x.to(dev) for x in va.batch(list(range(i, min(i + a.batch, len(va), a.val_n)))))
                    with torch.autocast(dev, dtype=dt, enabled=amp):
                        lg = net(im, tk[:, :-1], fd[:, :-1])
                    l_, c_ = loss_fn(lg, tk[:, 1:], fd[:, 1:])
                    vl += l_.item()
                    vc += c_.item()
                    n += 1
            net.train()
            vl, vc = vl / max(n, 1), vc / max(n, 1)
            rec = dict(step=step, val=vl, val_acc=vc, minutes=(time.time() - tstart) / 60)
            print('검증', rec, flush=True)
            with open(log, 'a', encoding='utf-8') as fh:
                fh.write(json.dumps(rec) + '\n')
            state = dict(model=net.state_dict(), opt=opt.state_dict(), step=step, best=min(best, vl), cfg=cfg)
            torch.save(state, ck + '.tmp')
            os.replace(ck + '.tmp', ck)
            if vl < best:
                best = vl
                torch.save(dict(model=net.state_dict(), cfg=cfg, step=step, val=vl), os.path.join(a.out, 'best.pt'))
    print('끝', step, '걸음 best', round(best, 4), flush=True)


def load(path, dev='cpu'):
    s = torch.load(path, map_location=dev, weights_only=False)
    c = s['cfg']
    net = Net(c['d'], c['layers'], c['heads'], c['maxlen'], c['backbone'], pretrained=False)
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
    W, H = 640, 360
    R.PARAMS['thick_mul'] = W / 1920
    rows = []
    out_seq = None
    ids = K.Ids()
    for k, i in enumerate(pick):
        t0 = time.time()
        img = torch.from_numpy(ds.img[i]).permute(2, 0, 1).float().to(dev) / 255
        toks, done = generate(net, img, c['maxlen'])
        seq = seq_xml(ds.meta[i]['hwr'])
        pred = K.decode(toks, fid=k + 1, pos=k, ids=ids)
        ans = K.decode(ds.tok[i].tolist())
        im_p = R.render_frame(seq, pred, W, H)
        im_a = R.render_frame(seq, ans, W, H)
        src = cv2.resize(ds.img[i], (W, H))
        dif = float((np.abs(im_p.astype(int) - src.astype(int)).max(-1) > 40).mean() * 100)
        n_p, n_a = len(pred.findall('AO')), len(ans.findall('AO'))
        l_p = sum(len(p.findall('AC')) for p in pred.iter('AP')) // 2
        l_a = sum(len(p.findall('AC')) for p in ans.iter('AP')) // 2
        print(f'{ds.meta[i]["file"]} 장 {ds.meta[i]["pos"]}: 토큰 {len(toks)}/{len(ds.tok[i])} 끝냄 {done} | 오브젝트 {n_p}/{n_a} 연결 {l_p}/{l_a} | 입력과 다른 픽셀 {dif:.1f}% ({time.time() - t0:.0f}초)', flush=True)
        cells = [src.copy(), im_p, im_a]
        for im, lab in zip(cells, ('input video', 'AI made SFA', 'answer SFA')):
            cv2.putText(im, lab, (6, 18), 0, 0.55, (255, 0, 0), 1)
        rows.append(np.hstack(cells))
        if out_seq is None:
            out_seq = seq_xml(ds.meta[i]['hwr'])
        out_seq.append(pred)
    cv2.imwrite(a.sheet, cv2.cvtColor(np.vstack(rows), cv2.COLOR_RGB2BGR))
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
    t.add_argument('--minutes', type=float, default=60)
    t.add_argument('--steps', type=int, default=20000)
    t.add_argument('--batch', type=int, default=8)
    t.add_argument('--lr', type=float, default=3e-4)
    t.add_argument('--maxlen', type=int, default=2048)
    t.add_argument('--in-w', type=int, default=640)
    t.add_argument('--d', type=int, default=384)
    t.add_argument('--layers', type=int, default=6)
    t.add_argument('--heads', type=int, default=6)
    t.add_argument('--backbone', default='resnet34')
    t.add_argument('--log-every', type=int, default=20)
    t.add_argument('--val-minutes', type=float, default=10)
    t.add_argument('--val-n', type=int, default=256)
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
