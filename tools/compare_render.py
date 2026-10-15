#!/usr/bin/env python3
"""Compare sfa_render output with frames decoded from an app-exported video.

Usage: python tools/compare_render.py PROJECT.sfa VIDEO.mp4 7 19 31 ... [--json out.json]
Frame numbers are 1-based. Needs numpy, Pillow and ffmpeg. The video is read locally and
never copied; only aggregate metrics are written.
"""
import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import sfa  # noqa: E402
import sfa_render  # noqa: E402

# BT.709 full-range RGB <-> YCbCr
M = np.array([[0.2126, 0.7152, 0.0722], [-0.1146, -0.3854, 0.5], [0.5, -0.4542, -0.0458]])
MI = np.linalg.inv(M)


def chroma_420(img):
    """Apply 2x2 chroma averaging like yuv420p so codec-limited edges compare fairly."""
    ycc = img.astype(float) @ M.T
    h, w = ycc.shape[:2]
    c = ycc[:h - h % 2, :w - w % 2, 1:]
    c = c.reshape(h // 2, 2, w // 2, 2, 2).mean((1, 3)).repeat(2, 0).repeat(2, 1)
    ycc[:h - h % 2, :w - w % 2, 1:] = c
    return np.clip(ycc @ MI.T, 0, 255)


def extract(video, frames, out_dir):
    expr = '+'.join(f'eq(n\\,{f - 1})' for f in frames)
    subprocess.run(['ffmpeg', '-v', 'error', '-i', str(video), '-vf',
                    f"select='{expr}',scale=in_range=tv:in_color_matrix=bt709:out_range=pc,format=rgb24",
                    '-vsync', '0', str(Path(out_dir) / 'f_%04d.png')], check=True)
    return sorted(Path(out_dir).glob('f_*.png'))


def metrics(out, ref):
    d = np.abs(out - ref)
    m = d.max(2)
    return {'mae': round(float(d.mean()), 3), 'pct_gt16': round(float((m > 16).mean() * 100), 3),
            'p99': round(float(np.percentile(m, 99)), 1), 'max': int(m.max())}


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('sfa_path')
    ap.add_argument('video')
    ap.add_argument('frames', type=int, nargs='+')
    ap.add_argument('--json')
    a = ap.parse_args()
    frames = sfa.read_sfa(a.sfa_path).findall('Frame')
    report = {}
    with tempfile.TemporaryDirectory() as tmp:
        refs = extract(a.video, a.frames, tmp)
        for n, path in zip(a.frames, refs):
            ref = np.asarray(Image.open(path)).astype(float)
            out = sfa_render.render_frame(frames[n - 1], ref.shape[1], ref.shape[0]).astype(float)
            report[n] = {'raw': metrics(out, ref), 'chroma420': metrics(chroma_420(out), ref)}
            print(n, report[n])
    if a.json:
        Path(a.json).write_text(json.dumps(report, indent=1) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
