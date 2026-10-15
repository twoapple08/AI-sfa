#!/usr/bin/env python3
"""Render a whole SFA with the static timeline/interpolation reading to MP4 or PNG frames.

Usage: python tools/render_video.py PROJECT.sfa TWEEN_FPS PLAYBACK_FPS OUT.mp4 [--size 1920x1080]
       python tools/render_video.py PROJECT.sfa 30 12 OUT_DIR --png
Needs numpy and Pillow; MP4 output also needs ffmpeg. Approximation, not the app renderer.
"""
import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import sfa  # noqa: E402
import sfa_render  # noqa: E402
import sfa_tween  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('sfa_path')
    ap.add_argument('tween_fps', type=int)
    ap.add_argument('playback_fps', type=int)
    ap.add_argument('out')
    ap.add_argument('--size', default='1920x1080')
    ap.add_argument('--png', action='store_true')
    a = ap.parse_args()
    w, h = (int(v) for v in a.size.split('x'))
    root = sfa.read_sfa(a.sfa_path)
    plan = sfa_tween.timeline(len(root.findall('Frame')), a.tween_fps, a.playback_fps)
    proc = None
    if a.png:
        Path(a.out).mkdir(parents=True, exist_ok=True)
    else:
        proc = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24',
                                 '-s', f'{w}x{h}', '-r', str(plan['output_fps']), '-i', '-',
                                 '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-colorspace', 'bt709',
                                 '-color_primaries', 'bt709', '-color_trc', 'bt709', a.out], stdin=subprocess.PIPE)
    for j, frame, _ in sfa_tween.export_frames(root, a.tween_fps, a.playback_fps):
        img = sfa_render.render_frame(frame, w, h)
        if proc:
            proc.stdin.write(img.tobytes())
        else:
            from PIL import Image
            Image.fromarray(img).save(Path(a.out) / f'frame_{j + 1:05d}.png')
    if proc:
        proc.stdin.close()
        proc.wait()
    print(f"{len(plan['frames'])} frames at {plan['output_fps']} fps")


if __name__ == '__main__':
    main()
