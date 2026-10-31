#!/usr/bin/env python3
"""임팩트 프레임 후보 구간을 찾고 연필/디지털 지표를 잰다.

사용 예:
  python tools/impact_scan.py clip.mp4 --json out.json --sheets outdir/

후보 프레임: 채도가 낮은(흑백·단색에 가까운) 프레임이 짧게(최대 16프레임) 나타나고,
앞뒤 장면보다 채도가 뚜렷이 낮거나 화면 대부분이 흰색·검정인 경우.
흑백 장면이 길게 이어지면 연출(무채색 장면)로 보고 후보에서 뺀다.

지표(후보 프레임별, 320x180 회색조):
  flat  = 순수 검정(<40)·순수 흰색(>215) 화소 비율. 디지털 단색은 높다.
  mid   = 중간 회색(40–215) 비율. 연필 해칭은 회색 농도를 선 밀도로 만들어 높다.
  tex   = 중간 회색 영역의 고주파 에너지(3x3 라플라시안 절댓값 평균). 연필 결은 높다.
사전 분류는 digital_like(흑·백 평면 85% 이상)와 check(육안 확인 필요) 두 가지뿐이다.
연필 판정은 지표로 하지 않는다: 사용자 예시로 보정한 결과 회색 3D 화면과 연필 해칭의 지표가 겹쳤다.
"""
import argparse
import json
import os
import subprocess

import numpy as np

W, H = 320, 180


def frames(path, w=W, h=H):
    p = subprocess.Popen(['ffmpeg', '-v', 'error', '-i', path, '-vf', f'scale={w}:{h}',
                          '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], stdout=subprocess.PIPE)
    size = w * h * 3
    try:
        while True:
            buf = p.stdout.read(size)
            if len(buf) < size:
                break
            yield np.frombuffer(buf, np.uint8).reshape(h, w, 3)
    finally:
        p.kill()
        p.wait()


def metrics(f):
    f = f.astype(np.int16)
    sat = (f.max(-1) - f.min(-1)).mean()
    g = f.mean(-1)
    black, white = (g < 40).mean(), (g > 215).mean()
    midmask = (g >= 40) & (g <= 215)
    lap = np.abs(4 * g[1:-1, 1:-1] - g[:-2, 1:-1] - g[2:, 1:-1] - g[1:-1, :-2] - g[1:-1, 2:])
    m = midmask[1:-1, 1:-1]
    tex = float(lap[m].mean()) if m.any() else 0.0
    return {'sat': float(sat), 'black': float(black), 'white': float(white),
            'flat': float(black + white), 'mid': float(midmask.mean()), 'tex': tex}


def classify(m):
    if m['flat'] >= 0.85 and m['mid'] < 0.12:
        return 'digital_like'
    return 'check'  # 연필/디지털 육안 확인 필요. 회색 3D 화면과 연필 해칭은 지표로 갈리지 않았다(2026-10-17 보정)


def scan(path, sat_max=28.0, ctx=8, max_run=16, drop=18.0):
    M = [metrics(f) for f in frames(path)]
    sat = np.array([m['sat'] for m in M])
    gray = sat < sat_max
    runs, i = [], 0
    while i < len(M):
        if not gray[i]:
            i += 1
            continue
        j = i
        while j + 1 < len(M) and gray[j + 1]:
            j += 1
        if j - i + 1 <= max_run:
            around = np.r_[sat[max(0, i - ctx):i], sat[j + 1:j + 1 + ctx]]
            flash = any(M[k]['white'] > 0.9 or M[k]['black'] > 0.9 for k in range(i, j + 1))
            if flash or (len(around) and np.median(around) - sat[i:j + 1].mean() >= drop):
                cls = [classify(M[k]) for k in range(i, j + 1)]
                runs.append({'start': i, 'end': j, 'frames': [
                    {'f': k, **{x: round(M[k][x], 3) for x in ('sat', 'flat', 'mid', 'tex')}, 'pre': c}
                    for k, c in zip(range(i, j + 1), cls)],
                    'pre_class': max(set(cls), key=cls.count)})
        i = j + 1
    return {'frames': len(M), 'runs': runs}


def run_sheet(path, start, end, out, cols=6):
    from PIL import Image, ImageDraw
    pick = set(range(start, end + 1))
    tiles = []
    for i, f in enumerate(frames(path)):
        if i in pick:
            im = Image.fromarray(f.copy())
            ImageDraw.Draw(im).text((4, 2), str(i), fill=(255, 255, 0))
            tiles.append(im)
        if i >= end:
            break
    rows = (len(tiles) + cols - 1) // cols
    canvas = Image.new('RGB', (cols * W, rows * H))
    for k, t in enumerate(tiles):
        r, c = divmod(k, cols)
        canvas.paste(t, (c * W, r * H))
    canvas.save(out, quality=85)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('video')
    ap.add_argument('--json')
    ap.add_argument('--sheets', help='후보 구간마다 앞뒤 6프레임을 붙인 연속 프레임 시트를 저장할 폴더')
    a = ap.parse_args()
    r = scan(a.video)
    if a.sheets:
        os.makedirs(a.sheets, exist_ok=True)
        merged = []
        for run in r['runs']:  # 가까운 구간은 시트 하나로 묶는다
            s, e = max(0, run['start'] - 6), min(r['frames'] - 1, run['end'] + 6)
            if merged and s <= merged[-1][1] + 1 and e - merged[-1][0] < 48:
                merged[-1][1] = e
            else:
                merged.append([s, e])
        for s, e in merged:
            run_sheet(a.video, s, e, os.path.join(a.sheets, f'f{s:05d}-{e:05d}.jpg'))
        r['sheets'] = [f'f{s:05d}-{e:05d}.jpg' for s, e in merged]
    if a.json:
        with open(a.json, 'w', encoding='utf-8') as f:
            json.dump(r, f, ensure_ascii=False)
    print(json.dumps({'frames': r['frames'], 'runs': len(r['runs']),
                      'pre': [x['pre_class'] for x in r['runs']]}, ensure_ascii=False))


if __name__ == '__main__':
    main()
