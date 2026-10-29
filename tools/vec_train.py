#!/usr/bin/env python3
"""영상 → SFA 딥러닝 학습(Kaggle GPU용, 2026-10-29).

입력: 앞·지금·뒤 3장(9채널) → 출력 28채널: 선 가운데, 선 끝, 방향(cos2θ, sin2θ), 칠한 면, 속성 16(선 굵기·선 RGBA·글로우·면 RGBA·그리는 순서),
관절, 종류(직선·원·곡선), 배경색. 정답은 27채널(마지막 = 실제 그림이 있는 자리).
자료: tools/vec_data.py가 만든 npz(해상도별 폴더). 커리큘럼(사용자 10-29): 1920 → 1280 → 854 → 640 순(계획 진행 20·45·70·100%), 단계마다 새 해상도 70% + 앞 단계 30%.
모델: U-Net(torchvision ResNet34 인코더, ImageNet 가중치, 첫 층 9채널로 늘림 + 원래 크기 갈래). bf16 자동 혼합 정밀도(지원 안 되면 fp16 + GradScaler), GPU 여러 장이면 DataParallel.
손실: loss_fn 참고(가운데 BCE+Dice, 선 끝·관절 focal, 방향·속성은 1px 가운데선, 면 BCE·RGBA, 순서, 종류 CE, 배경색). GPT 검토 1·2차 반영(docs/VIDEO-TO-SFA-2026-10-29.md).
검증: 원본 이름 해시로 5%. 200걸음마다 고정 문제로 검증, ckpt.pt(이어하기용 전체 상태)·last.pt·best.pt·log.jsonl.
사용: python vec_train.py --data /kaggle/tmp/vd --out /kaggle/working/vec_out --hours 4 [--smoke]
"""
import argparse
import glob
import hashlib
import json
import os
import random
import subprocess
import time

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
import torchvision

STAGES = [('1920', 0.20), ('1280', 0.25), ('854', 0.25), ('640', 0.30)]  # (해상도 폴더, 시간 몫)
CROP_W, CROP_H = 512, 256
BOUNDS = np.cumsum([f for _, f in STAGES])  # 단계 끝 = 전체 진행의 20·45·70·100%
BOUNDS[-1] = 1.0  # 소수점 오차로 마지막 단계가 일찍 끝나지 않게
PAINT_TAGS = ('묶음5_페인트', '면변환')
N_ATTR = 16  # vec_data.ATTR: 선 굵기, 선 RGBA, 글로우(반경·두께·세기·RGB), 면 RGBA, 그리는 순서
# 출력 채널: 0 가운데, 1 선 끝, 2–3 방향, 4 면, 5–20 속성, 21 관절(이어진 선 끝), 22–24 종류(직선·원·곡선), 25–27 배경색(사용자 10-29)
# 정답 채널: 0–20 같음, 21 관절, 22 종류 번호(0 없음·1 직선·2 원·3 곡선), 23–25 배경색
OUT_CH = 28


def arr(d, key, n, shape, dtype=np.uint8):
    return d[key] if key in d.files else np.zeros((n,) + shape, dtype)


class DS(torch.utils.data.Dataset):
    """파일 하나에서 무작위 장 k개(앞·뒤 장 포함) 자르기. 압축 파일은 한 번만 풀어 k조각을 뽑는다(GPT 검토 13)."""

    def __init__(self, files, k=8, length=2000, paint_w=4.0):
        self.files, self.k, self.length = files, k, length
        # 페인트 자료(채우기·반투명 면·색 배경이 많은 묶음5·면변환본)는 자주 뽑는다(2026-10-29 자료 충당 현황: 면 있는 장 5%뿐)
        self.w = [paint_w if any(t in os.path.basename(f) for t in PAINT_TAGS) else 1.0 for f in files]

    def __len__(self):
        return self.length

    def __getitem__(self, i):
        f = random.choices(self.files, weights=self.w)[0]
        self.last = f  # 검증에서 종류별 점수를 따로 세려고(작업자 없이 직접 부를 때만 의미 있음)
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
        with torch.no_grad():  # 드문 점 지도(선 끝·관절)는 처음 확률을 1%로 — 빈 조각에서 focal 손실이 폭발하지 않게(GPT 2차: logit 0이면 약 2만)
            self.head.bias[1] = -4.6
            self.head.bias[21] = -4.6

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

    def __init__(self, net, on, dtype=torch.float16):
        super().__init__()
        self.net, self.on, self.dtype = net, on, dtype

    def forward(self, x):
        with torch.autocast(device_type='cuda', dtype=self.dtype, enabled=self.on):
            return self.net(x)


def focal(logit, y, valid, pos_thr=0.99):
    """희소한 점 지도(선 끝·관절): 정답 점 개수로 나눈 focal 손실(CenterNet 방식) — 전체 픽셀 평균에 묻히지 않게(GPT 검토 8)."""
    p = torch.sigmoid(logit).clamp(1e-4, 1 - 1e-4)
    pos = (y >= pos_thr).float() * valid
    lp = -(torch.log(p) * (1 - p) ** 2 * pos).sum()
    ln = -(torch.log(1 - p) * p ** 2 * (1 - y) ** 4 * (1 - pos) * valid).sum()
    return (lp + ln) / pos.sum().clamp(min=1)


def loss_fn(p, y):
    """정답 채널: 0 가운데, 1 선 끝, 2–3 방향, 4 면, 5–20 속성, 21 관절, 22 종류, 23–25 배경, 26 실제 자리."""
    valid = y[:, 26:27]  # 실제 그림이 있는 자리(아래 채운 빈칸 0) — 모든 공간 손실에 적용(GPT 2차 11)
    vs = valid.sum() + 1
    c = (F.max_pool2d(y[:, 0:1], 3, 1, 1) > 0).float() * valid       # 가운데 정답을 3px로
    lc = (F.binary_cross_entropy_with_logits(p[:, 0:1], c, pos_weight=torch.tensor(5.0, device=p.device), reduction='none') * valid).sum() / vs
    s = torch.sigmoid(p[:, 0:1]) * valid
    dice = 1 - (2 * (s * c).sum() + 1) / (s.sum() + c.sum() + 1)
    lp = focal(p[:, 1:2], y[:, 1:2], valid)
    on_line = (y[:, 0:1] > 0).float()  # 방향·선 속성·종류는 정확한 가운데선 픽셀에서만(GPT 검토 1: 넓힌 띠에는 방향 정답이 없다)
    lo = ((torch.tanh(p[:, 2:4]) - y[:, 2:4]).abs() * on_line).sum() / (on_line.sum() * 2 + 1)
    lf = (F.binary_cross_entropy_with_logits(p[:, 4:5], y[:, 4:5], reduction='none') * valid).sum() / vs
    # 속성(사용자 10-29: 페인트·글로우·투명도·선 굵기·색·레이어)
    a, ya = torch.sigmoid(p[:, 5:21]), y[:, 5:21]
    on_fill = (y[:, 4:5] > 0).float()
    # 무언가 있는 픽셀: 순서 값 > 0 또는 가운데선·면(순서가 uint8로 0이 된 작은 번호도 포함, GPT 2차 11)
    on_any = ((ya[:, 15:16] > 0) | (on_line > 0) | (on_fill > 0)).float()
    on_glow = on_line * (ya[:, 7:8] > 0).float()  # 글로우 값·색은 글로우가 있는 선에서만(GPT 검토 10)
    l1 = lambda sl, m: ((a[:, sl] - ya[:, sl]).abs() * m).sum() / (m.sum() * (sl.stop - sl.start) + 1)
    ll = l1(slice(0, 5), on_line)      # 굵기 + 선 RGBA
    lga = l1(slice(7, 8), on_line)     # 글로우 세기(없으면 0 = 글로우 없음)
    lg = l1(slice(5, 7), on_glow) + l1(slice(8, 11), on_glow)  # 글로우 반경·두께·색
    lfa = l1(slice(11, 15), on_fill)   # 면 RGBA
    lo2 = l1(slice(15, 16), (ya[:, 15:16] > 0).float())  # 그리는 순서(레이어·앞뒤)
    lj = focal(p[:, 21:22], y[:, 21:22], valid)                            # 관절
    kt = y[:, 22].long()
    km = kt > 0
    lk = F.cross_entropy(p[:, 22:25].permute(0, 2, 3, 1)[km], kt[km] - 1) if km.any() else p.sum() * 0  # 종류(가운데선 픽셀)
    # 배경색: 실제 자리 중 아무것도 없는 픽셀. 반투명·글로우 전용 선은 번호판에 폭이 없으니 가운데선 5px 안도 뺀다(GPT 2차 11)
    near = (F.max_pool2d(y[:, 0:1], 11, 1, 5) > 0).float()
    bgm = valid * (1 - on_any) * (1 - near)
    lb = ((torch.sigmoid(p[:, 25:28]) - y[:, 23:26]).abs() * bgm).sum() / (bgm.sum() * 3 + 1)
    # 선 색(2026-10-29 1차 학습: 파란 선을 검게 예측) — 가운데선 1px만이 아니라 3px 띠에서도, 가중치 3. 띠의 정답은 가까운 가운데선 색(최댓값 풀링)
    # GPT 5차 1: 채널마다 최댓값을 따로 뽑으면 빨강+파랑 → 자홍처럼 섞인다. 띠 픽셀은 3×3 안 '가운데선 픽셀 하나'의 RGB를 통째로 가져오고,
    # 가운데선 픽셀은 자기 색 그대로.
    band = F.max_pool2d(on_line, 3, 1, 1) * valid
    _, idx = F.max_pool2d(on_line, 3, 1, 1, return_indices=True)
    rgb = ya[:, 1:4]
    got = rgb.flatten(2).gather(2, idx.flatten(2).expand(-1, 3, -1)).view_as(rgb)
    ycol = torch.where(on_line > 0, rgb, got)
    lcol = ((a[:, 1:4] - ycol).abs() * band).sum() / (band.sum() * 3 + 1)
    tot = lc + dice + lp + lo + lf + 2 * ll + 3 * lcol + lga + lg + lfa + lo2 + lj + 0.5 * lk + lb
    return tot, dict(c=lc.item(), dice=dice.item(), p=lp.item(), o=lo.item(), f=lf.item(), line=ll.item(), color=lcol.item(), glow_a=lga.item(), glow=lg.item(),
                     fill_rgba=lfa.item(), order=lo2.item(), joint=lj.item(), kind=lk.item(), bg=lb.item())


HEAVY = ('cod.exe', 'modernwarfare.exe', 'blackops6.exe', 'cod_hq.exe', 'cod24-cod.exe')   # 무거운 게임: 켜져 있으면 학습 멈춤
LIGHT = ('league of legends.exe', 'clipstudiopaint.exe',                                 # 가벼운 것: 천천히
         'hd-player.exe', 'dnplayer.exe', 'nox.exe', 'mumuplayer.exe')                    # 안드로이드 에뮬레이터(블루스택·LD·녹스·MuMu, 사용자 10-29)


class Yielder:
    """양보 모드(사용자 10-29, 4060 PC: 시간 제한 없음 대신 콜 오브 듀티·롤·클립 스튜디오가 같이 돌아도 문제없어야).
    30초마다 실행 중 프로그램 목록을 보고: 무거운 게임 → 끝날 때까지 학습 멈춤(GPU 캐시 비움), 가벼운 것 → 걸음마다 쉼.
    쉰 시간은 paused에 모아 학습 계획(진행률)·시간 계산에서 뺀다."""

    def __init__(self, on, extra_heavy='', extra_light=''):
        self.on, self.paused, self.t_check, self.mode = on, 0.0, 0.0, ''
        self.heavy = HEAVY + tuple(x.strip().lower() for x in extra_heavy.split(',') if x.strip())
        self.light = LIGHT + tuple(x.strip().lower() for x in extra_light.split(',') if x.strip())

    def _running(self):
        try:
            if os.name == 'nt':
                out = subprocess.run('tasklist /fo csv /nh', shell=True, capture_output=True, text=True, errors='ignore').stdout.lower()
                names = {l.split('","')[0].strip('"') for l in out.splitlines() if l}
            else:
                names = set(subprocess.run(['ps', '-eo', 'comm='], capture_output=True, text=True).stdout.lower().split())
        except Exception:
            return ''
        if any(n in names for n in self.heavy):
            return 'heavy'
        return 'light' if any(n in names for n in self.light) else ''

    def tick(self):
        """학습 걸음마다 부른다."""
        if not self.on:
            return
        now = time.time()
        if now - self.t_check > 30:
            self.t_check = now
            m = self._running()
            if m != self.mode:
                print(time.strftime('%H:%M'), {'heavy': '무거운 게임 실행 중 → 학습 멈춤', 'light': '가벼운 프로그램 실행 중 → 천천히', '': '양보 끝 → 정상 속도'}[m], flush=True)
                self.mode = m
        if self.mode == 'heavy':
            t0 = time.time()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            while self._running() == 'heavy':
                time.sleep(30)
            self.mode = ''
            self.paused += time.time() - t0
            print(time.strftime('%H:%M'), f'게임 끝 → 학습 다시({(time.time() - t0) / 60:.0f}분 쉼)', flush=True)
        elif self.mode == 'light':
            time.sleep(0.4)
            self.paused += 0.4


def low_priority():
    """이 프로세스(와 자식: 자료 읽기 작업자)를 '보통 이하' 우선순위로 — 게임·그림 프로그램이 CPU를 먼저 쓰게."""
    try:
        if os.name == 'nt':
            import ctypes
            ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)  # BELOW_NORMAL_PRIORITY_CLASS
        else:
            os.nice(10)
    except Exception as e:
        print('우선순위 낮추기 실패(무시):', e, flush=True)


def save(obj, path, tries=60):
    """다 쓴 뒤 한 번에 바꿔치기 — Drive로 올리는 도중에 반쯤 쓴 파일이 올라가지 않게. 모든 상태는 ckpt.pt 한 파일(GPT 검토 16).
    Windows는 다른 프로그램(rclone 올리기)이 읽고 있는 파일을 바꿔치기하지 못한다 → 2초 간격으로 다시 시도, 끝내 안 되면 이번 저장만 건너뜀(학습은 계속)."""
    tmp = path + '.tmp'
    torch.save(obj, tmp)
    for i in range(tries):
        try:
            os.replace(tmp, path)
            return True
        except PermissionError:
            time.sleep(2)
    print('저장 건너뜀(파일 사용 중):', os.path.basename(path), flush=True)
    return False


def files_of(data, res):
    """완료 표시(_done.json)에 기록된 성공 파일만 — 옛 자료가 섞이지 않게(GPT 3차 7). 표시가 없으면(직접 만든 시험 자료) 폴더 전체."""
    d = os.path.join(data, res)
    try:
        names = json.load(open(os.path.join(d, '_done.json'), encoding='utf-8'))['files']
        return sorted(os.path.join(d, n) for n in names if os.path.exists(os.path.join(d, n)))
    except Exception:
        return sorted(glob.glob(os.path.join(d, '*.npz')))


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
    ap.add_argument('--yield', dest='yield_', action='store_true', help='양보 모드: 낮은 우선순위, GPU 메모리 절반 남짓, 무거운 게임이면 멈춤·가벼운 것이면 천천히(4060 PC)')
    ap.add_argument('--yield-heavy', default='', help='멈출 프로그램 이름 추가(쉼표, 예: game.exe)')
    ap.add_argument('--yield-light', default='', help='천천히 돌릴 프로그램 이름 추가')
    ap.add_argument('--init', default='', help='가중치만 불러와 새 계획으로 시작(2차 학습: 1차 best.pt에서 출발). --resume이 있으면 무시')
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    dev = 'cuda' if torch.cuda.is_available() else 'cpu'
    yl = Yielder(a.yield_, a.yield_heavy, a.yield_light)
    if a.yield_:
        low_priority()
        if dev == 'cuda':
            torch.cuda.set_per_process_memory_fraction(0.55)  # 8GB 중 약 4.4GB만 — 나머지는 게임·그림 프로그램 몫. 모자라면 OOM 장치가 조각 수를 줄인다
        print('양보 모드: 무거운 게임', ', '.join(yl.heavy), '/ 천천히', ', '.join(yl.light), flush=True)
    net = Net(pretrained=not a.smoke or dev == 'cuda').to(dev)
    # bf16(5060 등 지원 GPU): 수 범위가 fp32와 같아 넘침이 없다. 1차 학습은 fp16에서 디코더 값이 65,504를 넘어 검증 NaN·마지막 단계 출렁임(2026-10-29)
    # 진짜 bf16 하드웨어(계산 능력 8.0 이상, RTX 30xx 이후)만. 최근 PyTorch의 is_bf16_supported()는 흉내 내기까지 True라 1050 Ti(6.1)에서 느린 bf16이 될 수 있다
    bf16 = dev == 'cuda' and torch.cuda.get_device_capability(0)[0] >= 8
    amp = Amp(net, dev == 'cuda', torch.bfloat16 if bf16 else torch.float16)
    print('혼합 정밀도', 'bf16' if bf16 else ('fp16' if dev == 'cuda' else '없음(CPU)'), flush=True)
    model = nn.DataParallel(amp) if torch.cuda.device_count() > 1 else amp
    opt = torch.optim.AdamW(net.parameters(), lr=a.lr, weight_decay=1e-4)
    scaler = torch.amp.GradScaler('cuda', enabled=dev == 'cuda' and not bf16)  # bf16은 배율 조정이 필요 없다
    # 마지막 검증·저장 시간을 미리 떼어 둔다(서버 실행 시험: 학습이 시간을 다 쓰면 마지막 검증이 바로 멈춰 마지막 모델이 최고 선택에서 빠졌다)
    reserve = min(300.0, 0.05 * a.hours * 3600)
    st = dict(progress=0.0, step=0, skipped=0, best=1e9, plan=(a.plan_hours or a.hours) * 3600 - reserve, max_n=10 ** 9, lr=a.lr)
    if a.init and not (a.resume and os.path.exists(a.resume)):
        if not os.path.exists(a.init):  # GPT 5차 2: 지정한 시작 가중치가 없으면 조용히 처음부터 하지 않는다
            raise SystemExit(f'시작 가중치 없음: {a.init}')
        sd = torch.load(a.init, map_location=dev, weights_only=False)
        sd = sd.get('model', sd) if isinstance(sd, dict) and 'model' in sd else sd
        net.load_state_dict(sd)
        st['lr'] = a.lr * 0.5  # 이미 배운 가중치 — 처음부터보다 작은 학습률로(1e-3이면 초반에 배운 것이 크게 흔들린다)
        print('가중치 불러옴(새 계획으로 시작, 학습률', st['lr'], '):', os.path.basename(a.init), flush=True)
    if a.resume and os.path.exists(a.resume):  # 완전한 이어하기(GPT 검토 15): 가중치만이 아니라 최적화기·AMP·진행·최고 점수까지
        ck = torch.load(a.resume, map_location=dev, weights_only=False)
        net.load_state_dict(ck['model'])
        opt.load_state_dict(ck['opt'])
        if scaler.is_enabled() and ck.get('scaler'):
            scaler.load_state_dict(ck['scaler'])
        st.update(ck['state'])
        print(f"이어서: 진행 {st['progress'] * 100:.1f}%, {st['step']}걸음, 최고 검증 {st['best']:.4f}", flush=True)
    log_path = os.path.join(a.out, 'log.jsonl')  # 쓸 때마다 열고 닫는다 — Windows는 열린 파일의 크기·시각을 늦게 갱신해 15분 올리기가 기록을 건너뛰었다(1차 학습)
    t_sess = time.time()
    prog0 = st['progress']
    active = lambda: time.time() - t_sess - yl.paused  # 양보로 쉰 시간은 뺀 실제 학습 시간
    progress = lambda: prog0 + active() / st['plan']
    out_of_time = lambda: active() >= a.hours * 3600 - reserve  # 학습은 여기까지
    hard_stop = lambda: active() >= a.hours * 3600             # 검증은 여기까지
    allv, seen = [], []
    last = (float('nan'), {})  # 마지막으로 성공한 걸음의 손실

    def checkpoint(rec):
        ok = save(dict(model=net.state_dict(), opt=opt.state_dict(), scaler=scaler.state_dict(), state=dict(st, progress=progress()), rec=rec),
                  os.path.join(a.out, 'ckpt.pt'))
        save(net.state_dict(), os.path.join(a.out, 'last.pt'))
        return ok

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
        steps0 = st['step']
        while (progress() < BOUNDS[si] or a.smoke) and not out_of_time():
            model.train()
            for _ in range(5 if a.smoke else 200):
                yl.tick()
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
                    g['lr'] = st['lr'] * (0.05 + 0.95 * 0.5 * (1 + np.cos(np.pi * min(progress(), 1.0))))
                try:
                    xb = x.flatten(0, 1)[:st['max_n']].to(dev, non_blocking=True)
                    yb = y.flatten(0, 1)[:st['max_n']].to(dev, non_blocking=True)
                    p = model(xb)
                    l, parts = loss_fn(p.float(), yb)
                    opt.zero_grad(set_to_none=True)
                    if not torch.isfinite(l):  # 넘침·깨진 자료 — 이 걸음은 건너뛰고 센다(1차 학습에서 보이지 않던 헛걸음을 기록)
                        st['skipped'] = st.get('skipped', 0) + 1
                        continue
                    scaler.scale(l).backward()
                    s0 = scaler.get_scale() if scaler.is_enabled() else None
                    scaler.step(opt)
                    scaler.update()
                    if s0 is not None and scaler.get_scale() < s0:  # fp16 배율이 줄었다 = 기울기 넘침으로 이 걸음을 건너뜀
                        st['skipped'] = st.get('skipped', 0) + 1
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
            # 검증: 늘 같은 문제(파일·장·자리 고정, 모든 지나온 해상도). 빈 목록이면 건너뜀, 하나라도 실패하면 이번 점수는 최고 선택에 쓰지 않음(GPT 2차 18)
            model.eval()
            vl, n, nv, nbad = 0.0, 0, 0, 0
            cat = {}  # 종류별 검증(GPT 5차 6): 원본·페인트·합성 — 총점은 자료 구성에 따라 바뀌므로 종류별로 1·2차를 비교
            vds = []
            if allv:
                with torch.no_grad():
                    rs = random.getstate()
                    vds = DS(allv, k=4, length=8 if a.smoke else 40)
                    for i in range(len(vds)):
                        if hard_stop():  # 시간이 다 되면 검증을 멈춤(미완료 → 최고 선택에 안 씀, GPT 3차 14)
                            break
                        random.seed(1234 + i)  # 문제마다 고정 번호 — 미리 다 만들어 두면 RAM 약 3GB(조각 160 × 36채널 × 512×256 × 4바이트)
                        x, y = vds[i]
                        nv += 1
                        try:
                            tot_i = 0.0
                            for j in range(0, x.shape[0], 2):  # 작은 묶음으로 끝까지
                                p = model(x[j:j + 2].to(dev))
                                tot_i += loss_fn(p.float(), y[j:j + 2].to(dev))[0].item() * min(2, x.shape[0] - j)
                            if not np.isfinite(tot_i):  # NaN·무한대 문제는 평균에 넣지 않고, 이번 검증은 미완료(최고 선택 제외)
                                nbad += 1
                                continue
                            vl += tot_i / x.shape[0]
                            n += 1
                            nm = os.path.basename(vds.last)
                            c = '합성' if '_syn' in nm else '페인트' if any(t in nm for t in PAINT_TAGS) else '원본'
                            cs = cat.setdefault(c, [0.0, 0])
                            cs[0] += tot_i / x.shape[0]
                            cs[1] += 1
                        except torch.cuda.OutOfMemoryError:
                            torch.cuda.empty_cache()
                    random.setstate(rs)
            complete = bool(allv) and n == nv == len(vds) and nbad == 0
            vl = vl / n if n else float('nan')
            ep += 1
            rec = dict(stage=si + 1, res=res, ep=ep, step=st['step'], train=round(last[0], 4), val=round(vl, 4) if n else None, val_complete=bool(complete), val_bad=nbad, val_cat={k: [round(v / m, 4), m] for k, (v, m) in cat.items()}, skipped=st.get('skipped', 0),
                       parts={k: round(v, 4) for k, v in last[1].items()}, lr=opt.param_groups[0]['lr'],
                       progress=round(progress() * 100, 1), min=round((time.time() - t_sess) / 60, 1), paused_min=round(yl.paused / 60, 1))
            print(json.dumps(rec, ensure_ascii=False), flush=True)
            with open(log_path, 'a', encoding='utf-8') as lf:
                lf.write(json.dumps(rec, ensure_ascii=False) + '\n')
            if si == len(STAGES) - 1 and complete and vl < st['best']:  # 최종 단계, 검증을 끝까지 한 경우만(GPT 2차 18)
                if save(net.state_dict(), os.path.join(a.out, 'best.pt')):  # 저장에 성공했을 때만 최고 점수 갱신(GPT 3차 12)
                    st['best'] = vl
            if not checkpoint(rec):
                print('ckpt.pt 저장 실패 — 다음 저장 때 다시', flush=True)
            if a.smoke:
                break
        print(f'단계 {si + 1} 학습 걸음 {st["step"] - steps0}', flush=True)  # 단계를 실제로 학습했는지(GPT 2차: 진행률 기준이라 0일 수도)
        save(net.state_dict(), os.path.join(a.out, f'stage{si + 1}_{res}.pt'))
        del it_new, it_old, dl_new, dl_old  # 단계마다 자료 읽기 프로세스가 쌓이지 않게
        if out_of_time():
            break
    if not os.path.exists(os.path.join(a.out, 'best.pt')):  # 마지막 단계 검증을 끝까지 못 한 경우 — 마지막 모델을 대신(이름으로 구분)
        save(net.state_dict(), os.path.join(a.out, 'best_fallback_last.pt'))
        print('best.pt 없음 → 마지막 모델을 best_fallback_last.pt로 저장(마지막 단계 검증 미완료)', flush=True)
    print(f"끝 {(time.time() - t_sess) / 60:.1f}분, 진행 {progress() * 100:.1f}%", flush=True)


if __name__ == '__main__':
    main()
