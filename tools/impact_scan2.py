#!/usr/bin/env python3
"""임팩트 프레임 후보 검출 v2 (2026-10-18 사용자 정의 반영).

정의(사용자): 임팩트 프레임은 대개 흑백으로, 날카로운 선·실루엣·그림자 등 강조할 부분을
집중 묘사한 짧은 삽입이다. 흑백 반전이 번갈아 일어나지 않아도 흑백 강조가 있으면 해당한다
(예: 2프레임). 밝은 상태로 실루엣이 이어지기만 하는 것, 앞뒤와 차이 없는 장면은 아니다.
TV판은 명도를 낮춘 경우가 있어(점멸 대책) 대비를 프레임별로 정규화해서 본다.

사용 예:
  python tools/impact_scan2.py clip.mp4 --json out.json --sheets outdir/

프레임 지표(320x180):
  mono  = RGB 공분산의 둘째/첫째 고유값 비의 제곱근. 무채색·단일 색조(보라·적색 연필 등)면 작다.
  chroma= 채널 최대-최소 평균. 색조가 남은 밝은 화면(노랑 섬광 등) 구분용.
  ext   = 2–98 백분위로 늘린 명도에서 검정·흰 극단 화소 비율.
  edge  = 늘린 명도의 기울기 크기 40 초과 비율(선·해칭 밀도).
  flat  = 명도 범위(2–98 백분위)가 8 미만인 단색 전면.
후보 구간: 단색조 프레임이 연속 max_run 이하로 이어지고, 앞뒤 문맥보다 뚜렷이 단색조이거나
극단·선 밀도가 크게 달라진 경우. 전면 단색만으로 된 구간(흰 섬광만)은 뺀다.
판정은 지표로 하지 않는다. 연속 프레임 시트를 사람이 보고 정한다.
"""
import argparse
import json
import os
import subprocess

import numpy as np

W, H = 320, 180


def frames(path, w=W, h=H):
    p = subprocess.Popen(['ffmpeg', '-nostdin', '-v', 'error', '-i', path, '-vf', f'scale={w}:{h}',
                          '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'],
                         stdout=subprocess.PIPE, stdin=subprocess.DEVNULL)
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
    f = f.astype(np.float32)
    px = f.reshape(-1, 3)
    ev = np.sort(np.linalg.eigvalsh(np.cov(px.T) + np.eye(3) * 1e-3))[::-1]
    mono = float(np.sqrt(ev[1] / max(ev[0], 1e-3)))
    g = f.mean(-1)
    lo, hi = np.percentile(g, 2), np.percentile(g, 98)
    rng = float(hi - lo)
    gn = np.clip((g - lo) / max(rng, 1.0) * 255, 0, 255)
    gy, gx = np.gradient(gn)
    return {'mono': mono, 'chroma': float((f.max(-1) - f.min(-1)).mean()),
            'ext': float(((gn < 50) | (gn > 205)).mean()), 'edge': float((np.hypot(gx, gy) > 40).mean()),
            'rng': rng, 'mean': float(g.mean())}


def is_mono(m, mono_max=0.12, chroma_max=25.0):
    return m['rng'] < 8 or (m['mono'] < mono_max and m['chroma'] < chroma_max)


def salient(M, i, j, max_run):
    """긴 단색조 구간(무채색·어두운 장면) 안에서 극단·선 밀도가 갑자기 튀는 짧은 부분."""
    ext_med = np.median([m['ext'] for m in M[i:j + 1]])
    edge_med = np.median([m['edge'] for m in M[i:j + 1]])
    hit = [k for k in range(i, j + 1) if M[k]['rng'] >= 8 and
           (M[k]['ext'] - ext_med >= 0.2 or M[k]['edge'] - edge_med >= 0.08)]
    out, s = [], None
    for n, k in enumerate(hit):
        if s is None:
            s = k
        if n + 1 == len(hit) or hit[n + 1] > k + 2:
            if k - s + 1 <= max_run:
                out.append({'start': s, 'end': k, 'n': k - s + 1, 'in_long': [i, j],
                            'frames': [{'f': x, **{y: round(M[x][y], 3) for y in ('mono', 'chroma', 'ext', 'edge', 'rng')}}
                                       for x in range(s, k + 1)]})
            s = None
    return out


def scan(path, max_run=24, ctx=6):
    M = [metrics(f) for f in frames(path)]
    mono = [is_mono(m) for m in M]
    runs, long_runs, i = [], [], 0
    while i < len(M):
        if not mono[i]:
            i += 1
            continue
        j = i
        while j + 1 < len(M) and mono[j + 1]:
            j += 1
        seg = M[i:j + 1]
        content = [m for m in seg if m['rng'] >= 8 and (m['edge'] >= 0.02 or m['ext'] >= 0.6)]
        around = M[max(0, i - ctx):i] + M[j + 1:j + 1 + ctx]
        if content:
            ctx_mono = np.mean([is_mono(m) for m in around]) if around else 0.0
            d_edge = max(m['edge'] for m in content) - (np.median([m['edge'] for m in around]) if around else 0)
            d_ext = max(m['ext'] for m in content) - (np.median([m['ext'] for m in around]) if around else 0)
            contrast = ctx_mono <= 0.5 or d_edge >= 0.08 or d_ext >= 0.25
            rec = {'start': i, 'end': j, 'n': j - i + 1, 'ctx_mono': round(float(ctx_mono), 2),
                   'd_edge': round(float(d_edge), 3), 'd_ext': round(float(d_ext), 3),
                   'frames': [{'f': i + k, **{x: round(m[x], 3) for x in ('mono', 'chroma', 'ext', 'edge', 'rng')}}
                              for k, m in enumerate(seg)]}
            if j - i + 1 > max_run:
                long_runs.append({k: rec[k] for k in ('start', 'end', 'n')})
                runs.extend(salient(M, i, j, max_run))
            elif contrast:
                runs.append(rec)
        i = j + 1
    return {'frames': len(M), 'runs': runs, 'long_runs': long_runs}


def run_sheet(path, start, end, out, cols=8, w=240, h=135):
    from PIL import Image, ImageDraw
    tiles = []
    for i, f in enumerate(frames(path, w, h)):
        if i > end:
            break
        if i >= start:
            im = Image.fromarray(f)
            ImageDraw.Draw(im).text((3, 2), str(i), fill=(255, 255, 0))
            tiles.append(im)
    if not tiles:
        return
    rows = (len(tiles) + cols - 1) // cols
    sheet = Image.new('RGB', (cols * w, rows * h))
    for k, t in enumerate(tiles):
        sheet.paste(t, ((k % cols) * w, (k // cols) * h))
    sheet.save(out, quality=85)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('video')
    ap.add_argument('--json')
    ap.add_argument('--sheets', help='후보 구간마다 앞뒤 3프레임을 붙인 연속 시트를 저장할 폴더')
    a = ap.parse_args()
    r = scan(a.video)
    if a.sheets and r['runs']:
        os.makedirs(a.sheets, exist_ok=True)
        merged = []
        for run in r['runs']:
            s, e = max(0, run['start'] - 3), min(r['frames'] - 1, run['end'] + 3)
            if merged and s <= merged[-1][1] + 1 and e - merged[-1][0] < 40:
                merged[-1][1] = e
            else:
                merged.append([s, e])
        for s, e in merged:
            run_sheet(a.video, s, e, os.path.join(a.sheets, f'v2_f{s:05d}-{e:05d}.jpg'))
        r['sheets'] = [f'v2_f{s:05d}-{e:05d}.jpg' for s, e in merged]
    if a.json:
        with open(a.json, 'w', encoding='utf-8') as f:
            json.dump(r, f, ensure_ascii=False)
    print(json.dumps({'frames': r['frames'], 'runs': [(x['start'], x['end']) for x in r['runs']],
                      'long': [(x['start'], x['end']) for x in r['long_runs']]}, ensure_ascii=False))


if __name__ == '__main__':
    main()
