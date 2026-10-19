#!/usr/bin/env python3
"""좁힌 임팩트 정의로 후보 재판정: X-CLIP(비디오 트랜스포머) 제로샷 + 사용자 예시 유사도 + 대비·반전·실루엣·연속성 지표.

사용: python tools/impact_xclip.py <rows.csv> <원본 폴더> <예시 이미지 폴더> <out.csv>
rows.csv 열: key,post_id,frames (그 밖의 열은 그대로 출력에 붙는다).
모델 훈련 없음(추론만). 모델: microsoft/xclip-base-patch32(8프레임, CPU 가능).

좁힌 정의(2026-10-19 사용자): 실루엣(또는 빛에 의한 그림자) 표현, 고대비 또는 색상 반전 프레임.
지표(후보 구간 프레임 기준, 문맥=구간 앞뒤 12프레임):
- xclip_pos: 긍정 문구 묶음의 소프트맥스 확률 합
- ref_sim: 사용자 예시 5장(+반전)과의 비디오 임베딩 코사인 최대값
- ctx_sim: 후보 임베딩과 문맥 임베딩의 코사인(높으면 앞뒤와 같은 장면)
- mono: 1-평균 채도(무채색일수록 1), contrast: 밝기 양 끝 15% 화소 비율
- invert: 후보 프레임과 직전/직후 문맥 프레임 반전본의 밝기 상관 최대값
- silhouette: Otsu 이진화 뒤 가장 큰 연결 덩어리 면적 비율(배경 제외, 3–70%일 때만)
- cont: 경계 프레임↔바로 앞/뒤 프레임 에지 상관 최대값(judge_context.py와 같음)
"""
import csv, glob, os, subprocess, sys
import numpy as np
import cv2
import torch
from PIL import Image
from transformers import AutoProcessor, XCLIPModel

POS = ['a black and white pencil drawing of an explosion with a dark silhouette of a character',
       'a high contrast inverted color frame showing a character silhouette',
       'a monochrome sketch with radial hatching lines bursting from a bright center',
       'a stark black and white flash frame with a silhouette and shadows']
NEG = ['a colorful anime scene with characters', 'a cloud of dust and smoke', 'a plain white flash of light',
       'speed lines in the background', 'a character moving in a colorful scene', 'water splashing',
       'a dark night scene', 'an electric lightning attack in color']
MID = 224


def frames(path, s, e, w=MID, h=MID):
    p = subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-i', path, '-vf',
                        f'select=between(n\\,{s}\\,{e}),scale={w}:{h}', '-vsync', '0',
                        '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], capture_output=True, stdin=subprocess.DEVNULL)
    a = np.frombuffer(p.stdout, np.uint8)
    n = a.size // (w * h * 3)
    return a[:n * w * h * 3].reshape(n, h, w, 3)


def pick8(F):
    idx = np.linspace(0, len(F) - 1, 8).round().astype(int)
    return [F[i] for i in idx]


def ecorr(x, y):
    gx = lambda f: np.abs(np.diff(f, axis=1))[:-1, :] + np.abs(np.diff(f, axis=0))[:, :-1]
    x, y = gx(x), gx(y)
    x, y = x - x.mean(), y - y.mean()
    d = np.sqrt((x * x).sum() * (y * y).sum())
    return float((x * y).sum() / d) if d > 1e-6 else 0.0


def corr(x, y):
    x, y = x - x.mean(), y - y.mean()
    d = np.sqrt((x * x).sum() * (y * y).sum())
    return float((x * y).sum() / d) if d > 1e-6 else 0.0


def handcrafted(F, pre, post):
    out = {'mono': [], 'contrast': [], 'silhouette': [], 'invert': []}
    g = lambda f: cv2.cvtColor(f, cv2.COLOR_RGB2GRAY).astype(np.float32)
    for f in F:
        hsv = cv2.cvtColor(f, cv2.COLOR_RGB2HSV)
        out['mono'].append(1 - hsv[..., 1].mean() / 255)
        y = g(f)
        out['contrast'].append(float(((y < 38) | (y > 217)).mean()))
        y8 = y.astype(np.uint8)
        _, b = cv2.threshold(y8, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        best = 0.0
        for m in (b, 255 - b):
            n, lab, st, _ = cv2.connectedComponentsWithStats(m, 8)
            if n > 1:
                a = st[1:, cv2.CC_STAT_AREA].max() / m.size
                if 0.03 <= a <= 0.7:
                    best = max(best, float(a))
        out['silhouette'].append(best)
        inv = [corr(y, 255 - g(c)) for c in (pre, post) if c is not None]
        out['invert'].append(max(inv) if inv else 0.0)
    r = {k: round(float(np.max(v)), 3) for k, v in out.items()}
    r['mono'] = round(float(np.max(out['mono'])), 3)
    return r


def main():
    rows_csv, src, refdir, out_csv = sys.argv[1:5]
    files = {os.path.basename(f).split('.')[0]: f for f in glob.glob(src + '/*')}
    torch.set_num_threads(os.cpu_count())
    name = 'microsoft/xclip-base-patch32'
    proc = AutoProcessor.from_pretrained(name)
    model = XCLIPModel.from_pretrained(name).eval()
    texts = POS + NEG

    def video_emb(fr8):
        with torch.no_grad():
            inp = proc(videos=[list(fr8)], return_tensors='pt')
            return torch.nn.functional.normalize(model.get_video_features(**inp).pooler_output, dim=-1)[0]

    with torch.no_grad():
        tin = proc(text=texts, return_tensors='pt', padding=True)
    refs = []
    for f in sorted(glob.glob(refdir + '/ref*.png')):
        im = np.array(Image.open(f).convert('RGB').resize((MID, MID)))
        refs.append(video_emb([im] * 8))
    R = torch.stack(refs)
    rows = list(csv.DictReader(open(rows_csv, encoding='utf-8')))
    done = set()
    if os.path.exists(out_csv):
        done = {r['key'] for r in csv.DictReader(open(out_csv, encoding='utf-8'))}
    fo = open(out_csv, 'a', newline='', encoding='utf-8')
    w = None
    for n, r in enumerate(rows):
        if r['key'] in done:
            continue
        fr = r['frames']
        if r['post_id'] not in files or not fr[:1].isdigit():
            continue
        a, b = [int(v) for v in (fr.split('-') + [fr])[:2]]
        s = max(0, a - 12)
        F = frames(files[r['post_id']], s, b + 12)
        if len(F) < (a - s) + 1:
            continue
        cand = F[a - s:a - s + (b - a + 1)]
        ctx = list(F[:a - s]) + list(F[a - s + (b - a + 1):])
        pre = F[a - s - 1] if a - s >= 1 else None
        post = F[a - s + (b - a + 1)] if len(F) > a - s + (b - a + 1) else None
        ve = video_emb(pick8(cand))
        with torch.no_grad():
            inp = proc(text=texts, videos=[pick8(cand)], return_tensors='pt', padding=True)
            pr = model(**inp).logits_per_video.softmax(-1)[0]
        res = dict(r)
        res['xclip_pos'] = round(float(pr[:len(POS)].sum()), 3)
        res['ref_sim'] = round(float((R @ ve).max()), 3)
        res['ctx_sim'] = round(float(video_emb(pick8(ctx)) @ ve), 3) if len(ctx) else ''
        gy = lambda f: cv2.cvtColor(cv2.resize(f, (96, 54)), cv2.COLOR_RGB2GRAY).astype(np.float32)
        c = []
        if pre is not None:
            c.append(ecorr(gy(cand[0]), gy(pre)))
        if post is not None:
            c.append(ecorr(gy(cand[-1]), gy(post)))
        res['cont'] = round(max(c), 3) if c else ''
        res.update(handcrafted(cand, pre, post))
        if w is None:
            w = csv.DictWriter(fo, fieldnames=list(res))
            if not done:
                w.writeheader()
        w.writerow(res)
        fo.flush()
        if n % 25 == 0:
            print('progress', n, len(rows), flush=True)
    print('DONE', flush=True)


if __name__ == '__main__':
    main()
