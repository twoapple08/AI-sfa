"""GPT 판정용 시트: 영상마다 12장 요약 시트, 1초 간격 시트(6×4=24초씩), 움직임 점수를 만든다.

사용: python tools/gpt_sheets.py <묶음목록_v3.csv> <영상 루트(animator/post_id.mp4)> <출력 폴더> [묶음 최솟값]
출력: <출력>/<묶음>/<post_id>_요약.jpg, <post_id>_1s_<n>.jpg, <출력>/<묶음>/index.csv
움직임점수: 4fps 64px 흑백 프레임 간 평균 절대차(0–255). 장면전환: 그 차이가 40을 넘은 횟수.
"""
import csv
import io
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

from PIL import Image, ImageChops, ImageDraw, ImageStat

TW = 256


def grab(path, fps, w):
    p = subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-i', path, '-vf', f'fps={fps},scale={w}:-2',
                        '-f', 'image2pipe', '-vcodec', 'mjpeg', '-q:v', '5', '-'], capture_output=True).stdout
    out, i = [], 0
    while True:
        a = p.find(b'\xff\xd8', i)
        b = p.find(b'\xff\xd9', a + 2) if a >= 0 else -1
        if a < 0 or b < 0:
            return out
        out.append(Image.open(io.BytesIO(p[a:b + 2])).convert('RGB'))
        i = b + 2


def grid(ims, times, cols, rows):
    th = ims[0].height
    g = Image.new('RGB', (TW * cols, th * rows), 'black')
    d = ImageDraw.Draw(g)
    for k, (im, t) in enumerate(zip(ims, times)):
        x, y = (k % cols) * TW, (k // cols) * th
        g.paste(im, (x, y))
        d.rectangle([x, y, x + 40, y + 13], fill='black')
        d.text((x + 2, y + 1), f'{int(t // 60)}:{t % 60:04.1f}', fill='yellow')
    return g


def one(job):
    batch, pid, src, od = job
    small = [im.convert('L').resize((64, 36)) for im in grab(src, 4, 64)]
    diffs = [ImageStat.Stat(ImageChops.difference(a, b)).mean[0] for a, b in zip(small, small[1:])]
    motion = sum(diffs) / len(diffs) if diffs else 0
    cuts = sum(x > 40 for x in diffs)
    ims = grab(src, 1, TW)
    if not ims:
        return batch, pid, 0, 0, 0, 0
    n = 0
    for s in range(0, len(ims), 24):
        n += 1
        grid(ims[s:s + 24], range(s, s + 24), 6, 4).save(os.path.join(od, f'{pid}_1s_{n}.jpg'), quality=80)
    idx = [round(i * (len(ims) - 1) / 11) for i in range(12)] if len(ims) >= 12 else list(range(len(ims)))
    grid([ims[i] for i in idx], idx, 4, 3).save(os.path.join(od, f'{pid}_요약.jpg'), quality=80)
    return batch, pid, len(ims), motion, cuts, n


def main():
    lst, root, out = sys.argv[1:4]
    lo = sys.argv[4] if len(sys.argv) > 4 else ''
    jobs = []
    for r in csv.DictReader(open(lst, encoding='utf-8-sig')):
        if r['묶음'] < lo:
            continue
        od = os.path.join(out, r['묶음'])
        os.makedirs(od, exist_ok=True)
        jobs.append((r['묶음'], r['post_id'], os.path.join(root, r['animator'], r['post_id'] + '.mp4'), od))
    with ThreadPoolExecutor(4) as ex:
        res = list(ex.map(one, jobs))
    idx = {}
    for b, *rest in res:
        idx.setdefault(b, []).append(rest)
    for b, rows in idx.items():
        with open(os.path.join(out, b, 'index.csv'), 'w', newline='', encoding='utf-8') as f:
            w = csv.writer(f)
            w.writerow(['post_id', '길이초(약)', '움직임점수', '장면전환수', '1초시트수'])
            for p, dur, m, c, n in rows:
                w.writerow([p, dur, f'{m:.2f}', c, n])
    print('videos', len(res), 'sheets', sum(r[5] for r in res), 'empty', sum(r[5] == 0 for r in res))


if __name__ == '__main__':
    main()
