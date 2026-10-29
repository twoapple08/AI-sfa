#!/usr/bin/env python3
"""영상 → SFA 딥러닝 학습(Kaggle GPU용, 2026-10-29).

입력: 앞·지금·뒤 3장(9채널) → 출력 21채널: 선 가운데, 점 자리(선 끝), 선 방향(cos2θ, sin2θ), 칠한 면 + 속성 16(선 굵기·선 RGBA·글로우 반경·두께·세기·색·면 RGBA·그리는 순서).
자료: tools/vec_data.py가 만든 npz(해상도별 폴더). 커리큘럼(사용자 10-29): 1920 → 1280 → 854 → 640 순, 단계마다 새 해상도 70% + 앞 단계 30%.
모델: U-Net(torchvision ResNet34 인코더, ImageNet 가중치, 첫 층 9채널로 늘림). fp16 자동 혼합 정밀도, GPU 여러 장이면 DataParallel.
손실: 가운데(3px로 넓힌 정답) BCE + Dice, 점 가중 MSE, 방향 L1(가운데 근처만), 면 BCE.
검증: 파일의 5%를 떼어 둠. 단계 끝·에폭마다 저장(best.pt, last.pt), 기록 log.jsonl.
사용: python vec_train.py --data /kaggle/tmp/vd --out /kaggle/working/vec_out --hours 4 [--smoke]
"""
import argparse
import glob
import json
import os
import random
import time

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
import torchvision

STAGES = [('1920', 0.20), ('1280', 0.25), ('854', 0.25), ('640', 0.30)]  # (해상도 폴더, 시간 몫)
CROP_W, CROP_H = 512, 256
N_ATTR = 16  # vec_data.ATTR: 선 굵기, 선 RGBA, 글로우(반경·두께·세기·RGB), 면 RGBA, 그리는 순서
# 출력 채널: 0 가운데, 1 선 끝, 2–3 방향, 4 면, 5–20 속성, 21 관절(이어진 선 끝), 22–24 종류(직선·원·곡선), 25–27 배경색(사용자 10-29)
# 정답 채널: 0–20 같음, 21 관절, 22 종류 번호(0 없음·1 직선·2 원·3 곡선), 23–25 배경색
OUT_CH = 28


def d_get(d, key, t, sl, h):
    return d[key][t][sl].astype(np.float32) if key in d.files else np.zeros((h, CROP_W), np.float32)


class DS(torch.utils.data.Dataset):
    """파일 하나에서 무작위 장 k개(앞·뒤 장 포함) 자르기."""

    def __init__(self, files, k=4, length=2000):
        self.files, self.k, self.length = files, k, length

    def __len__(self):
        return self.length

    def __getitem__(self, i):
        f = random.choice(self.files)
        d = np.load(f)
        img, center, pts, ori, fill = d['img'], d['center'], d['pts'], d['ori'], d['fill']
        attr = d['attr'] if 'attr' in d.files else None  # 속성 16채널(vec_data.ATTR)
        n, H, W = center.shape
        xs, ys = [], []
        for _ in range(self.k):
            t = random.randrange(n)
            fr = [img[max(t - 1, 0)], img[t], img[min(t + 1, n - 1)]]
            h = min(CROP_H, H)
            y0 = random.randrange(H - h + 1)
            x0 = random.randrange(W - CROP_W + 1)
            sl = (slice(y0, y0 + h), slice(x0, x0 + CROP_W))
            x = np.concatenate([q[sl] for q in fr], -1).astype(np.float32) / 255.0  # h,w,9
            c = center[t][sl].astype(np.float32)
            y = np.stack([c, pts[t][sl] / 255.0, ori[t][0][sl] / 127.0, ori[t][1][sl] / 127.0, fill[t][sl].astype(np.float32)], 0)
            at = attr[t][(slice(None),) + sl].astype(np.float32) / 255.0 if attr is not None else np.zeros((N_ATTR, h, CROP_W), np.float32)
            jt = d_get(d, 'joint', t, sl, h) / 255.0
            kd = d_get(d, 'kind', t, sl, h)
            bgc = (d['bg'][t].astype(np.float32) / 255.0 if 'bg' in d.files else np.ones(3, np.float32))[:, None, None] * np.ones((3, h, CROP_W), np.float32)
            y = np.concatenate([y, at, jt[None], kd[None], bgc], 0)
            if random.random() < 0.5:  # 좌우 뒤집기: θ → π−θ ⇒ cos2θ 그대로, sin2θ 부호 반대
                x = x[:, ::-1]
                y = y[:, :, ::-1].copy()
                y[3] = -y[3]
            if h < CROP_H:  # 높이가 모자라면 아래를 0으로
                x = np.pad(x, ((0, CROP_H - h), (0, 0), (0, 0)))
                y = np.pad(y, ((0, 0), (0, CROP_H - h), (0, 0)))
            xs.append(np.ascontiguousarray(x.transpose(2, 0, 1)))
            ys.append(np.ascontiguousarray(y))
        return torch.from_numpy(np.stack(xs)), torch.from_numpy(np.stack(ys).astype(np.float32))


class Up(nn.Module):
    def __init__(self, cin, cskip, cout):
        super().__init__()
        self.conv = nn.Sequential(nn.Conv2d(cin + cskip, cout, 3, padding=1), nn.BatchNorm2d(cout), nn.ReLU(inplace=True),
                                  nn.Conv2d(cout, cout, 3, padding=1), nn.BatchNorm2d(cout), nn.ReLU(inplace=True))

    def forward(self, x, skip):
        x = F.interpolate(x, size=skip.shape[-2:], mode='bilinear', align_corners=False)
        return self.conv(torch.cat([x, skip], 1))


class Net(nn.Module):
    def __init__(self, in_ch=9, out_ch=OUT_CH, pretrained=True):
        super().__init__()
        r = torchvision.models.resnet34(weights='IMAGENET1K_V1' if pretrained else None)
        w = r.conv1.weight.data
        self.conv1 = nn.Conv2d(in_ch, 64, 7, 2, 3, bias=False)
        self.conv1.weight.data = w.repeat(1, in_ch // 3, 1, 1) / (in_ch // 3)
        self.bn1, self.relu, self.pool = r.bn1, r.relu, r.maxpool
        self.l1, self.l2, self.l3, self.l4 = r.layer1, r.layer2, r.layer3, r.layer4
        self.full = nn.Sequential(nn.Conv2d(in_ch, 32, 3, padding=1), nn.BatchNorm2d(32), nn.ReLU(inplace=True),
                                  nn.Conv2d(32, 32, 3, padding=1), nn.BatchNorm2d(32), nn.ReLU(inplace=True))
        self.u4, self.u3, self.u2 = Up(512, 256, 256), Up(256, 128, 128), Up(128, 64, 64)
        self.u1, self.u0 = Up(64, 64, 64), Up(64, 32, 48)
        self.head = nn.Conv2d(48, out_ch, 1)

    def forward(self, x):
        x0 = self.full(x)                                       # 1/1 (가는 선은 원래 크기 특징이 필요)
        x1 = self.relu(self.bn1(self.conv1(x)))                 # 1/2
        x2 = self.l1(self.pool(x1))                             # 1/4
        x3 = self.l2(x2)                                        # 1/8
        x4 = self.l3(x3)                                        # 1/16
        x5 = self.l4(x4)                                        # 1/32
        y = self.u4(x5, x4)
        y = self.u3(y, x3)
        y = self.u2(y, x2)
        y = self.u1(y, x1)
        y = self.u0(y, x0)
        return self.head(y)


class Amp(nn.Module):
    """DataParallel은 GPU마다 다른 스레드에서 돌고 autocast는 스레드마다 따로라, 모델 안에서 켠다."""

    def __init__(self, net, on):
        super().__init__()
        self.net, self.on = net, on

    def forward(self, x):
        with torch.autocast(device_type='cuda', dtype=torch.float16, enabled=self.on):
            return self.net(x)


def loss_fn(p, y):
    c = (F.max_pool2d(y[:, 0:1], 3, 1, 1) > 0).float()       # 가운데 정답을 3px로
    lc = F.binary_cross_entropy_with_logits(p[:, 0:1], c, pos_weight=torch.tensor(5.0, device=p.device))
    s = torch.sigmoid(p[:, 0:1])
    dice = 1 - (2 * (s * c).sum() + 1) / (s.sum() + c.sum() + 1)
    hp = torch.sigmoid(p[:, 1:2])
    lp = ((hp - y[:, 1:2]) ** 2 * (1 + 20 * y[:, 1:2])).mean()
    m = c
    lo = ((torch.tanh(p[:, 2:4]) - y[:, 2:4]).abs() * m).sum() / (m.sum() * 2 + 1)
    lf = F.binary_cross_entropy_with_logits(p[:, 4:5], y[:, 4:5])
    # 속성(사용자 10-29: 페인트·글로우·투명도·선 굵기·색·레이어): 선 속성·글로우는 정답 가운데선 픽셀에서, 면 속성은 면 픽셀에서, 순서는 무언가 있는 픽셀에서
    a, ya = torch.sigmoid(p[:, 5:]), y[:, 5:]
    on_line = (y[:, 0:1] > 0).float()
    on_fill = (y[:, 4:5] > 0).float()
    on_any = (ya[:, 15:16] > 0).float()
    l1 = lambda sl, m: ((a[:, sl] - ya[:, sl]).abs() * m).sum() / (m.sum() * (sl.stop - sl.start) + 1)
    ll = l1(slice(0, 5), on_line)      # 굵기 + 선 RGBA
    lg = l1(slice(5, 11), on_line)     # 글로우
    lfa = l1(slice(11, 15), on_fill)   # 면 RGBA
    lo2 = l1(slice(15, 16), on_any)    # 그리는 순서(레이어·앞뒤)
    hj = torch.sigmoid(p[:, 21:22])
    lj = ((hj - y[:, 21:22]) ** 2 * (1 + 20 * y[:, 21:22])).mean()           # 관절
    kt = y[:, 22].long()
    km = kt > 0
    lk = F.cross_entropy(p[:, 22:25].permute(0, 2, 3, 1)[km], kt[km] - 1) if km.any() else p.sum() * 0  # 종류(가운데선 픽셀)
    lb = (torch.sigmoid(p[:, 25:28]) - y[:, 23:26]).abs().mean()             # 배경색(모든 픽셀, 쓸 때는 중앙값)
    tot = lc + dice + 10 * lp + lo + lf + 2 * ll + 2 * lg + lfa + lo2 + 10 * lj + 0.5 * lk + lb
    return tot, dict(c=lc.item(), dice=dice.item(), p=lp.item(), o=lo.item(), f=lf.item(), line=ll.item(), glow=lg.item(), fill_rgba=lfa.item(),
                     order=lo2.item(), joint=lj.item(), kind=lk.item(), bg=lb.item())


def save(obj, path):
    """다 쓴 뒤 한 번에 바꿔치기 — Drive로 올리는 도중에 반쯤 쓴 파일이 올라가지 않게."""
    tmp = path + '.tmp'
    if isinstance(obj, dict) and 'stage' in obj:
        json.dump(obj, open(tmp, 'w'))
    else:
        torch.save(obj, tmp)
    os.replace(tmp, path)


def files_of(data, res):
    return sorted(glob.glob(os.path.join(data, res, '*.npz')))


def split(fs, val_frac=0.05):
    """같은 SFA 파일은 모두 같은 쪽(해상도·반복 상관없이)."""
    if not fs:  # 그 해상도 자료가 없음(빠른 확인은 1080·360만 만든다 — 1050 Ti 확인에서 여기서 멈춤, 10-29)
        return [], []
    key = lambda f: os.path.basename(f).split('__w')[0]
    names = sorted({key(f) for f in fs})
    rng = random.Random(0)
    val = set(rng.sample(names, max(1, int(len(names) * val_frac))))
    return [f for f in fs if key(f) not in val], [f for f in fs if key(f) in val]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--hours', type=float, default=4.0)
    ap.add_argument('--batch', type=int, default=4, help='DataLoader 묶음(묶음마다 파일 하나에서 4조각 → 실제 배치 = ×4)')
    ap.add_argument('--lr', type=float, default=1e-3)
    ap.add_argument('--workers', type=int, default=4)
    ap.add_argument('--smoke', action='store_true', help='단계마다 몇 걸음만(문법·메모리 확인)')
    ap.add_argument('--resume', default='')
    ap.add_argument('--start-stage', type=int, default=1, help='이어서 학습할 때 시작 단계(1–4). 앞 단계 파일은 섞기용으로만 쓴다')
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    dev = 'cuda' if torch.cuda.is_available() else 'cpu'
    net = Net(pretrained=not a.smoke or dev == 'cuda').to(dev)
    if a.resume:
        net.load_state_dict(torch.load(a.resume, map_location=dev))
    amp = Amp(net, dev == 'cuda')
    model = nn.DataParallel(amp) if torch.cuda.device_count() > 1 else amp
    opt = torch.optim.AdamW(net.parameters(), lr=a.lr, weight_decay=1e-4)
    scaler = torch.amp.GradScaler('cuda', enabled=dev == 'cuda')
    log = open(os.path.join(a.out, 'log.jsonl'), 'a')
    total = a.hours * 3600
    t0 = time.time()
    best = 1e9
    allv = []
    seen = []
    step = 0
    max_n = 10 ** 9  # 한 번에 보는 조각 수 상한(메모리 부족 때 줄어듦)
    last = (float('nan'), {})  # 마지막으로 성공한 걸음의 손실
    for si, (res, frac) in enumerate(STAGES):
        tr, va = split(files_of(a.data, res))
        if not tr:
            print('자료 없음', res)
            continue
        allv += va
        prev = seen[:]
        seen += tr
        if si + 1 < a.start_stage:
            continue
        mix = [tr, prev] if prev else [tr]
        budget = total * frac / sum(f for _, f in STAGES[a.start_stage - 1:])  # 이어서 할 때는 남은 단계끼리 시간을 나눔
        ts = time.time()
        print(f'단계 {si + 1} 해상도 {res}: 학습 파일 {len(tr)} (앞 단계 {len(prev)}), 검증 {len(va)}, 시간 {budget / 60:.0f}분', flush=True)
        ds_new = DS(tr)
        dl_new = torch.utils.data.DataLoader(ds_new, batch_size=a.batch, num_workers=a.workers, persistent_workers=a.workers > 0)
        dl_old = torch.utils.data.DataLoader(DS(prev), batch_size=a.batch, num_workers=max(1, a.workers // 2)) if prev else None
        it_new, it_old = iter(dl_new), iter(dl_old) if dl_old else None
        ep = 0
        while time.time() - ts < budget:
            model.train()
            for _ in range(5 if a.smoke else 200):
                if it_old is not None and random.random() < 0.3:
                    try:
                        x, y = next(it_old)
                    except StopIteration:
                        it_old = iter(dl_old)
                        x, y = next(it_old)
                else:
                    try:
                        x, y = next(it_new)
                    except StopIteration:
                        it_new = iter(dl_new)
                        x, y = next(it_new)
                x = x.flatten(0, 1)[:max_n].to(dev, non_blocking=True)
                y = y.flatten(0, 1)[:max_n].to(dev, non_blocking=True)
                # 학습률: 전체 시간에 걸쳐 코사인
                frac_t = min((time.time() - t0) / total, 1.0)
                for g in opt.param_groups:
                    g['lr'] = a.lr * (0.05 + 0.95 * 0.5 * (1 + np.cos(np.pi * frac_t)))
                try:
                    p = model(x)
                    l, parts = loss_fn(p.float(), y)
                    opt.zero_grad(set_to_none=True)
                    scaler.scale(l).backward()
                    scaler.step(opt)
                    scaler.update()
                    last = (l.item(), parts)
                except torch.cuda.OutOfMemoryError:  # 8GB 5060 대비: 멈추지 않고 한 번에 보는 조각을 절반으로
                    opt.zero_grad(set_to_none=True)
                    p = l = None
                    torch.cuda.empty_cache()
                    max_n = max(1, x.shape[0] // 2)
                    print('GPU 메모리 부족 → 조각 수', max_n, flush=True)
                    continue
                step += 1
            # 검증(지금까지 나온 모든 해상도의 검증 파일)
            model.eval()
            vl, n = 0.0, 0
            with torch.no_grad():
                st = random.getstate()
                random.seed(1234)  # 모의고사는 늘 같은 문제(같은 파일·장·자리) — 점수 비교가 공정하게
                vds = DS(allv, k=4, length=8 if a.smoke else 40)
                for i in range(len(vds)):
                    x, y = vds[i]
                    x, y = torch.as_tensor(x)[:max_n].to(dev), torch.as_tensor(y)[:max_n].to(dev)
                    p = model(x)
                    vl += loss_fn(p.float(), y)[0].item()
                    n += 1
                random.setstate(st)
            vl /= max(n, 1)
            ep += 1
            rec = dict(stage=si + 1, res=res, ep=ep, step=step, train=round(last[0], 4), val=round(vl, 4), parts={k: round(v, 4) for k, v in last[1].items()},
                       lr=opt.param_groups[0]['lr'], min=round((time.time() - t0) / 60, 1))
            print(json.dumps(rec, ensure_ascii=False), flush=True)
            log.write(json.dumps(rec, ensure_ascii=False) + '\n')
            log.flush()
            save(net.state_dict(), os.path.join(a.out, 'last.pt'))
            save(dict(stage=si + 1, res=res, ep=ep, step=step, val=vl, min=rec['min']), os.path.join(a.out, 'state.json'))
            if si == len(STAGES) - 1 and vl < best:  # 최종 단계(모든 해상도 검증)에서 가장 좋은 것
                best = vl
                save(net.state_dict(), os.path.join(a.out, 'best.pt'))
            if a.smoke:
                break
        save(net.state_dict(), os.path.join(a.out, f'stage{si + 1}_{res}.pt'))
        del it_new, it_old, dl_new, dl_old  # 단계마다 자료 읽기 프로세스가 쌓이지 않게
    print('끝', round((time.time() - t0) / 60, 1), '분', flush=True)


if __name__ == '__main__':
    main()
