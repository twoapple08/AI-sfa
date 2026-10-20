"""액션 동작 세기용 시트: 영상마다 0.5초 간격 프레임을 6×4 격자(12초)로 나열하고 칸마다 시각을 적는다.

사용: python tools/action_sheets.py <묶음목록_v2.csv> <영상 루트(animator/post_id.mp4)> <출력 폴더>
출력: <출력>/<묶음>/<post_id>_<n>.jpg, <출력>/<묶음>/index.csv(post_id,길이초,시트수)
"""
import csv
import io
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

from PIL import Image, ImageDraw

FPS = 2
COLS, ROWS = 6, 4
TW = 256


def frames(path):
    p = subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-i', path, '-vf', f'fps={FPS},scale={TW}:-2',
                        '-f', 'image2pipe', '-vcodec', 'mjpeg', '-q:v', '5', '-'], capture_output=True).stdout
    out, i = [], 0
    while True:
        a = p.find(b'\xff\xd8', i)
        b = p.find(b'\xff\xd9', a + 2) if a >= 0 else -1
        if a < 0 or b < 0:
            return out
        out.append(Image.open(io.BytesIO(p[a:b + 2])).convert('RGB'))
        i = b + 2


def one(job):
    batch, pid, src, outdir = job
    ims = frames(src)
    if not ims:
        return batch, pid, 0, 0
    th = ims[0].height
    n = 0
    for s in range(0, len(ims), COLS * ROWS):
        g = Image.new('RGB', (TW * COLS, th * ROWS), 'black')
        d = ImageDraw.Draw(g)
        for k, im in enumerate(ims[s:s + COLS * ROWS]):
            x, y = (k % COLS) * TW, (k // COLS) * th
            g.paste(im, (x, y))
            t = (s + k) / FPS
            d.rectangle([x, y, x + 40, y + 13], fill='black')
            d.text((x + 2, y + 1), f'{int(t // 60)}:{t % 60:04.1f}', fill='yellow')
        n += 1
        g.save(os.path.join(outdir, f'{pid}_{n}.jpg'), quality=80)
    return batch, pid, len(ims) / FPS, n


def main():
    lst, root, out = sys.argv[1:4]
    jobs = []
    for r in csv.DictReader(open(lst, encoding='utf-8-sig')):
        od = os.path.join(out, r['묶음'])
        os.makedirs(od, exist_ok=True)
        jobs.append((r['묶음'], r['post_id'], os.path.join(root, r['animator'], r['post_id'] + '.mp4'), od))
    with ThreadPoolExecutor(4) as ex:
        res = list(ex.map(one, jobs))
    idx = {}
    for b, p, dur, n in res:
        idx.setdefault(b, []).append((p, dur, n))
    for b, rows in idx.items():
        with open(os.path.join(out, b, 'index.csv'), 'w', newline='', encoding='utf-8') as f:
            w = csv.writer(f)
            w.writerow(['post_id', '길이초', '시트수'])
            for p, dur, n in rows:
                w.writerow([p, f'{dur:.1f}', n])
    print('videos', len(res), 'sheets', sum(r[3] for r in res), 'empty', sum(r[3] == 0 for r in res))


if __name__ == '__main__':
    main()
