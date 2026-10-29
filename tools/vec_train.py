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
import hashlib
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
BOUNDS = np.cumsum([f for _, f in STAGES])  # 단계 끝 = 전체 진행의 20·45·70·100%
N_ATTR = 16  # vec_data.ATTR: 선 굵기, 선 RGBA, 글로우(반경·두께·세기·RGB), 면 RGBA, 그리는 순서
# 출력 채널: 0 가운데, 1 선 끝, 2–3 방향, 4 면, 5–20 속성, 21 관절(이어진 선 끝), 22–24 종류(직선·원·곡선), 25–27 배경색(사용자 10-29)
# 정답 채널: 0–20 같음, 21 관절, 22 종류 번호(0 없음·1 직선·2 원·3 곡선), 23–25 배경색
OUT_CH = 28


def arr(d, key, n, shape, dtype=np.uint8):
    return d[key] if key in d.files else np.zeros((n,) + shape, dtype)


class DS(torch.utils.data.Dataset):
    """파일 하나에서 무작위 장 k개(앞·뒤 장 포함) 자르기. 압축 파일은 한 번만 풀어 k조각을 뽑는다(GPT 검토 13)."""

    def __init__(self, files, k=8, length=2000):
        self.files, self.k, self.length = files, k, length

    def __len__(self):
        return self.length

    def __getitem__(self, i):
        f = random.choice(self.files)
        d = np.load(f)
        img, center, pts, ori, fill = d['img'], d['center'], d['pts'], d['ori'], d['fill']
        n, H, W = center.shape
        attr = arr(d, 'attr', n, (N_ATTR, H, W))  # 속성 16채널(vec_data.ATTR)
        joint, kind = arr(d, 'joint', n, (H, W)), arr(d, 'kind', n, (H, W))
        bg = d['bg'] if 'bg' in d.files else np.full((n, 3), 255, np.uint8)
        xs, ys = [], []
        for _ in range(self.k):
            t = random.randrange(n)
            fr = [img[max(t - 1, 0)], img[t], img[min(t + 1, n - 1)]]
            h = min(CROP_H, H)
            y0 = random.randrange(H - h + 1)
            x0 = random.randrange(W - CROP_W + 1)
            sl = (slice(y0, y0 + h), slice(x0, x0 + CROP_W))
            x = np.concatenate([q[sl] for q in fr], -1).astype(np.float32) / 255.0  # h,w,9
            y = np.concatenate([
                np.stack([center[t][sl], pts[t][sl] / 255.0, ori[t][0][sl] / 127.0, ori[t][1][sl] / 127.0, fill[t][sl]], 0).astype(np.float32),
                attr[t][(slice(None),) + sl].astype(np.float32) / 255.0,
                (joint[t][sl] / 255.0)[None].astype(np.float32), kind[t][sl][None].astype(np.float32),
                (bg[t].astype(np.float32) / 255.0)[:, None, None] * np.ones((3, h, CROP_W), np.float32),
                np.ones((1, h, CROP_W), np.float32)], 0)  # 마지막 = 실제 그림이 있는 자리(아래 채움 빈칸은 0)
            if random.random() < 0.5:  # 좌우 뒤집기: θ → π−θ ⇒ cos2θ 그대로, sin2θ 부호 반대
                x = x[:, ::-1]
                y = y[:, :, ::-1].copy()
                y[3] = -y[3]
            if h < CROP_H:  # 높이가 모자라면 아래를 0으로(손실에서 빼도록 '실제 자리' 채널도 0)
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


def focal(logit, y, pos_thr=0.9):
    """희소한 점 지도(선 끝·관절): 정답 점 개수로 나눈 focal 손실(CenterNet 방식) — 전체 픽셀 평균에 묻히지 않게(GPT 검토 8)."""
    p = torch.sigmoid(logit).clamp(1e-4, 1 - 1e-4)
    pos = (y >= pos_thr).float()
    lp = -(torch.log(p) * (1 - p) ** 2 * pos).sum()
    ln = -(torch.log(1 - p) * p ** 2 * (1 - y) ** 4 * (1 - pos)).sum()
    return (lp + ln) / pos.sum().clamp(min=1)


def loss_fn(p, y):
    """정답 채널: 0 가운데, 1 선 끝, 2–3 방향, 4 면, 5–20 속성, 21 관절, 22 종류, 23–25 배경, 26 실제 자리."""
    valid = y[:, 26:27]
    c = (F.max_pool2d(y[:, 0:1], 3, 1, 1) > 0).float()       # 가운데 정답을 3px로
    lc = F.binary_cross_entropy_with_logits(p[:, 0:1], c, pos_weight=torch.tensor(5.0, device=p.device))
    s = torch.sigmoid(p[:, 0:1])
    dice = 1 - (2 * (s * c).sum() + 1) / (s.sum() + c.sum() + 1)
    lp = focal(p[:, 1:2], y[:, 1:2])
    on_line = (y[:, 0:1] > 0).float()  # 방향·선 속성·종류는 정확한 가운데선 픽셀에서만(GPT 검토 1: 넓힌 띠에는 방향 정답이 없다)
    lo = ((torch.tanh(p[:, 2:4]) - y[:, 2:4]).abs() * on_line).sum() / (on_line.sum() * 2 + 1)
    lf = F.binary_cross_entropy_with_logits(p[:, 4:5], y[:, 4:5])
    # 속성(사용자 10-29: 페인트·글로우·투명도·선 굵기·색·레이어)
    a, ya = torch.sigmoid(p[:, 5:21]), y[:, 5:21]
    on_fill = (y[:, 4:5] > 0).float()
    on_any = (ya[:, 15:16] > 0).float()
    on_glow = on_line * (ya[:, 7:8] > 0).float()  # 글로우 값·색은 글로우가 있는 선에서만(GPT 검토 10)
    l1 = lambda sl, m: ((a[:, sl] - ya[:, sl]).abs() * m).sum() / (m.sum() * (sl.stop - sl.start) + 1)
    ll = l1(slice(0, 5), on_line)      # 굵기 + 선 RGBA
    lga = l1(slice(7, 8), on_line)     # 글로우 세기(없으면 0 = 글로우 없음)
    lg = l1(slice(5, 7), on_glow) + l1(slice(8, 11), on_glow)  # 글로우 반경·두께·색
    lfa = l1(slice(11, 15), on_fill)   # 면 RGBA
    lo2 = l1(slice(15, 16), on_any)    # 그리는 순서(레이어·앞뒤)
    lj = focal(p[:, 21:22], y[:, 21:22])                                   # 관절
    kt = y[:, 22].long()
    km = kt > 0
    lk = F.cross_entropy(p[:, 22:25].permute(0, 2, 3, 1)[km], kt[km] - 1) if km.any() else p.sum() * 0  # 종류(가운데선 픽셀)
    bgm = valid * (1 - on_any) * (1 - c)  # 배경색은 실제로 배경이 보이는 픽셀에서만(GPT 검토 11)
    lb = ((torch.sigmoid(p[:, 25:28]) - y[:, 23:26]).abs() * bgm).sum() / (bgm.sum() * 3 + 1)
    tot = lc + dice + lp + lo + lf + 2 * ll + lga + lg + lfa + lo2 + lj + 0.5 * lk + lb
    return tot, dict(c=lc.item(), dice=dice.item(), p=lp.item(), o=lo.item(), f=lf.item(), line=ll.item(), glow_a=lga.item(), glow=lg.item(),
                     fill_rgba=lfa.item(), order=lo2.item(), joint=lj.item(), kind=lk.item(), bg=lb.item())


def save(obj, path):
    """다 쓴 뒤 한 번에 바꿔치기 — Drive로 올리는 도중에 반쯤 쓴 파일이 올라가지 않게. 모든 상태는 ckpt.pt 한 파일(GPT 검토 16)."""
    tmp = path + '.tmp'
    torch.save(obj, tmp)
    os.replace(tmp, path)


def files_of(data, res):
    return sorted(glob.glob(os.path.join(data, res, '*.npz')))


def src_key(f):
    return os.path.basename(f).split('__w')[0]


def is_val(name, val_frac=0.05):
    """원본 SFA 이름의 해시로 정한다 — 해상도·반복·생성 실패와 상관없이 늘 같은 쪽(GPT 검토 2: 해상도마다 따로 뽑으면 누수)."""
    return int(hashlib.md5(name.encode('utf-8')).hexdigest(), 16) % 1000 < val_frac * 1000


def split(fs):
    return [f for f in fs if not is_val(src_key(f))], [f for f in fs if is_val(src_key(f))]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--hours', type=float, default=4.0, help='이번 실행 시간')
    ap.add_argument('--plan-hours', type=float, default=0, help='커리큘럼 전체 계획 시간(0이면 --hours). 이어서 할 때는 저장된 계획을 쓴다')
    ap.add_argument('--batch', type=int, default=2, help='DataLoader 묶음(묶음마다 파일 하나에서 8조각 → 실제 배치 = ×8)')
    ap.add_argument('--lr', type=float, default=1e-3)
    ap.add_argument('--workers', type=int, default=4)
    ap.add_argument('--smoke', action='store_true', help='단계마다 몇 걸음만(문법·메모리 확인)')
    ap.add_argument('--resume', default='', help='ckpt.pt(모델·최적화기·AMP·진행·최고 점수) — 이어서')
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    dev = 'cuda' if torch.cuda.is_available() else 'cpu'
    net = Net(pretrained=not a.smoke or dev == 'cuda').to(dev)
    amp = Amp(net, dev == 'cuda')
    model = nn.DataParallel(amp) if torch.cuda.device_count() > 1 else amp
    opt = torch.optim.AdamW(net.parameters(), lr=a.lr, weight_decay=1e-4)
    scaler = torch.amp.GradScaler('cuda', enabled=dev == 'cuda')
    st = dict(progress=0.0, step=0, best=1e9, plan=(a.plan_hours or a.hours) * 3600, max_n=10 ** 9)
    if a.resume and os.path.exists(a.resume):  # 완전한 이어하기(GPT 검토 15): 가중치만이 아니라 최적화기·AMP·진행·최고 점수까지
        ck = torch.load(a.resume, map_location=dev, weights_only=False)
        net.load_state_dict(ck['model'])
        opt.load_state_dict(ck['opt'])
        scaler.load_state_dict(ck['scaler'])
        st.update(ck['state'])
        print(f"이어서: 진행 {st['progress'] * 100:.1f}%, {st['step']}걸음, 최고 검증 {st['best']:.4f}", flush=True)
    log = open(os.path.join(a.out, 'log.jsonl'), 'a')
    t_sess = time.time()
    prog0 = st['progress']
    progress = lambda: prog0 + (time.time() - t_sess) / st['plan']
    out_of_time = lambda: time.time() - t_sess >= a.hours * 3600
    allv, seen = [], []
    last = (float('nan'), {})  # 마지막으로 성공한 걸음의 손실

    def checkpoint(rec):
        save(dict(model=net.state_dict(), opt=opt.state_dict(), scaler=scaler.state_dict(), state=dict(st, progress=progress()), rec=rec),
             os.path.join(a.out, 'ckpt.pt'))
        save(net.state_dict(), os.path.join(a.out, 'last.pt'))

    for si, (res, frac) in enumerate(STAGES):
        tr, va = split(files_of(a.data, res))
        assert not ({src_key(f) for f in tr} & {src_key(f) for f in allv + va}), '학습·검증 원본이 겹침'
        allv += va
        prev = seen[:]
        seen += tr
        if not tr:
            print('자료 없음', res, flush=True)
            continue
        if progress() >= BOUNDS[si] and not a.smoke:
            continue  # 이미 지난 단계(이어서 할 때)
        print(f"단계 {si + 1} 해상도 {res}: 학습 파일 {len(tr)} (앞 단계 {len(prev)}), 검증 {len(va)}, 진행 {progress() * 100:.1f}% → {BOUNDS[si] * 100:.0f}%", flush=True)
        dl_new = torch.utils.data.DataLoader(DS(tr), batch_size=a.batch, num_workers=a.workers, persistent_workers=a.workers > 0)
        dl_old = torch.utils.data.DataLoader(DS(prev), batch_size=a.batch, num_workers=max(1, a.workers // 2)) if prev else None
        it_new, it_old = iter(dl_new), iter(dl_old) if dl_old else None
        ep = 0
        while (progress() < BOUNDS[si] or a.smoke) and not out_of_time():
            model.train()
            for _ in range(5 if a.smoke else 200):
                if progress() >= BOUNDS[si] and not a.smoke or out_of_time():
                    break
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
                for g in opt.param_groups:  # 학습률: 계획 전체 진행에 걸쳐 코사인(이어서 해도 이어짐)
                    g['lr'] = a.lr * (0.05 + 0.95 * 0.5 * (1 + np.cos(np.pi * min(progress(), 1.0))))
                try:
                    xb = x.flatten(0, 1)[:st['max_n']].to(dev, non_blocking=True)
                    yb = y.flatten(0, 1)[:st['max_n']].to(dev, non_blocking=True)
                    p = model(xb)
                    l, parts = loss_fn(p.float(), yb)
                    opt.zero_grad(set_to_none=True)
                    scaler.scale(l).backward()
                    scaler.step(opt)
                    scaler.update()
                    last = (l.item(), parts)
                    st['step'] += 1
                except torch.cuda.OutOfMemoryError:  # 8GB 5060 대비: 멈추지 않고 한 번에 보는 조각을 절반으로
                    opt.zero_grad(set_to_none=True)
                    p = l = xb = yb = None
                    torch.cuda.empty_cache()
                    if st['max_n'] <= 1 or x.flatten(0, 1).shape[0] <= 1 and st['max_n'] < 10 ** 9:
                        raise SystemExit('조각 1개도 GPU 메모리에 안 들어감 — 중단')
                    st['max_n'] = max(1, min(st['max_n'], x.flatten(0, 1).shape[0]) // 2)
                    print('GPU 메모리 부족 → 조각 수', st['max_n'], flush=True)
            # 검증: 늘 같은 문제(파일·장·자리 고정, 모든 지나온 해상도)
            model.eval()
            vl, n = 0.0, 0
            with torch.no_grad():
                rs = random.getstate()
                random.seed(1234)
                vds = DS(allv, k=4, length=8 if a.smoke else 40)
                for i in range(len(vds)):
                    x, y = vds[i]
                    try:
                        p = model(x[:st['max_n']].to(dev))
                        vl += loss_fn(p.float(), y[:st['max_n']].to(dev))[0].item()
                        n += 1
                    except torch.cuda.OutOfMemoryError:
                        torch.cuda.empty_cache()
                random.setstate(rs)
            vl /= max(n, 1)
            ep += 1
            rec = dict(stage=si + 1, res=res, ep=ep, step=st['step'], train=round(last[0], 4), val=round(vl, 4),
                       parts={k: round(v, 4) for k, v in last[1].items()}, lr=opt.param_groups[0]['lr'],
                       progress=round(progress() * 100, 1), min=round((time.time() - t_sess) / 60, 1))
            print(json.dumps(rec, ensure_ascii=False), flush=True)
            log.write(json.dumps(rec, ensure_ascii=False) + '\n')
            log.flush()
            if si == len(STAGES) - 1 and vl < st['best']:  # 최종 단계(모든 해상도 검증)에서 가장 좋은 것
                st['best'] = vl
                save(net.state_dict(), os.path.join(a.out, 'best.pt'))
            checkpoint(rec)
            if a.smoke:
                break
        save(net.state_dict(), os.path.join(a.out, f'stage{si + 1}_{res}.pt'))
        del it_new, it_old, dl_new, dl_old  # 단계마다 자료 읽기 프로세스가 쌓이지 않게
        if out_of_time():
            break
    print(f"끝 {(time.time() - t_sess) / 60:.1f}분, 진행 {progress() * 100:.1f}%", flush=True)


if __name__ == '__main__':
    main()
