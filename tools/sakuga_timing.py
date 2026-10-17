#!/usr/bin/env python3
"""작화 영상의 '새 그림' 타이밍 측정과 고유 그림 contact sheet 생성.

사용 예:
  python tools/sakuga_timing.py clip.mp4 --sheet out.jpg --json out.json
  python tools/sakuga_timing.py clip.mp4 --run 120:168 --sheet run.jpg   # 연속 프레임 시트

방법: ffmpeg로 프레임을 축소 회색조로 읽고 이전 프레임과의 평균 절대차를 잰다.
차이가 임계값 이하이면 같은 그림의 유지(hold)로 보고, 새 그림 사이 간격으로
1s/2s/3s(한 장을 몇 프레임 보여 주는지) 분포를 낸다. 화면 전체 차이를 쓰므로
카메라 이동·배경 스크롤이 있으면 hold가 새 그림으로 잡힐 수 있다(측정 한계).
"""
import argparse
import collections
import json
import subprocess

import numpy as np

W, H = 160, 90


def probe(path):
    out = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0',
                          '-show_entries', 'stream=r_frame_rate', '-of', 'csv=p=0', path],
                         capture_output=True, text=True, check=True).stdout.strip()
    num, den = out.split('/')
    return float(num) / float(den)


def frames(path, w=W, h=H, gray=True):
    fmt, ch = ('gray', 1) if gray else ('rgb24', 3)
    p = subprocess.Popen(['ffmpeg', '-v', 'error', '-i', path, '-vf', f'scale={w}:{h}',
                          '-f', 'rawvideo', '-pix_fmt', fmt, '-'], stdout=subprocess.PIPE)
    size = w * h * ch
    try:
        while True:
            buf = p.stdout.read(size)
            if len(buf) < size:
                break
            yield np.frombuffer(buf, np.uint8).reshape(h, w, ch) if not gray else \
                np.frombuffer(buf, np.uint8).reshape(h, w)
    finally:  # 중간에 멈추면(run 시트) ffmpeg를 끝내 broken pipe 출력을 막는다
        p.kill()
        p.wait()


def analyze(path, thresh):
    fps = probe(path)
    diffs, prev = [], None
    for f in frames(path):
        f = f.astype(np.int16)
        diffs.append(0.0 if prev is None else float(np.abs(f - prev).mean()))
        prev = f
    new = [0] + [i for i, d in enumerate(diffs) if i and d > thresh]
    holds = [b - a for a, b in zip(new, new[1:])] + [len(diffs) - new[-1]]
    dist = collections.Counter(min(h, 6) for h in holds)
    return {'fps': round(fps, 3), 'frames': len(diffs), 'drawings': len(new),
            'hold_hist': {('6+' if k == 6 else f'{k}s'): v for k, v in sorted(dist.items())},
            'mean_hold': round(len(diffs) / len(new), 2), 'new_frame_index': new,
            'threshold': thresh}


def sheet(path, idx, out, cols=8, w=213, h=120, limit=64):
    if len(idx) > limit:  # 앞부분만 보지 않도록 클립 전체에서 고르게 뽑는다
        idx = [idx[round(k * (len(idx) - 1) / (limit - 1))] for k in range(limit)]
    pick = set(idx)
    tiles = [f for i, f in enumerate(frames(path, w, h, gray=False)) if i in pick]
    rows = (len(tiles) + cols - 1) // cols
    canvas = np.zeros((rows * h, cols * w, 3), np.uint8)
    for k, t in enumerate(tiles):
        r, c = divmod(k, cols)
        canvas[r * h:(r + 1) * h, c * w:(c + 1) * w] = t
    from PIL import Image
    Image.fromarray(canvas).save(out, quality=85)


def run_sheet(path, start, end, out, step=1, cols=6, w=320, h=180):
    """연속 프레임 [start, end)를 step 간격으로 깐다. 몸 동작 간격(spacing)을 보기 위한 시트."""
    from PIL import Image, ImageDraw
    pick = list(range(start, end, step))[:48]
    tiles = []
    for i, f in enumerate(frames(path, w, h, gray=False)):
        if i in pick:
            im = Image.fromarray(f.copy())
            ImageDraw.Draw(im).text((4, 2), str(i), fill=(255, 255, 0))
            tiles.append(im)
        if i >= pick[-1]:
            break
    rows = (len(tiles) + cols - 1) // cols
    canvas = Image.new('RGB', (cols * w, rows * h))
    for k, t in enumerate(tiles):
        r, c = divmod(k, cols)
        canvas.paste(t, (c * w, r * h))
    canvas.save(out, quality=85)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('video')
    ap.add_argument('--thresh', type=float, default=0.5)
    ap.add_argument('--sheet')
    ap.add_argument('--start', type=int, default=0, help='sheet에 넣을 첫 고유 그림 순번')
    ap.add_argument('--json')
    ap.add_argument('--run', help='START:END[:STEP] 연속 프레임 시트만 만든다(--sheet에 저장, 프레임 번호 표시)')
    a = ap.parse_args()
    if a.run:
        start, end, *step = map(int, a.run.split(':'))
        run_sheet(a.video, start, end, a.sheet, step[0] if step else 1)
        return
    r = analyze(a.video, a.thresh)
    print({k: v for k, v in r.items() if k != 'new_frame_index'})
    if a.sheet:
        sheet(a.video, r['new_frame_index'][a.start:], a.sheet)
    if a.json:
        with open(a.json, 'w', encoding='utf-8') as f:
            json.dump(r, f)


if __name__ == '__main__':
    main()
