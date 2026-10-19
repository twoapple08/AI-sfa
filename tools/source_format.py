#!/usr/bin/env python3
"""원본 영상의 형식 지표: 셀/디지털, 원화(러프)/완성. 모델 훈련 없음(공개 모델 추론 + 영상 통계).

사용: python tools/source_format.py <targets.csv> <원본 폴더> <out.csv> [--sheets <폴더>]
targets.csv 열: post_id (그 밖의 열은 그대로 붙는다). 원본 파일 이름은 <post_id>.<확장자>.
이어서 돌리면 out.csv에 있는 post_id는 건너뛴다.

영상마다 앞뒤 5%를 뺀 구간에서 고르게 8프레임을 뽑아 잰다.
- width,height,aspect,fps,frames: ffprobe. aspect 1.25–1.4는 4:3(TV 셀 시대에 많음).
- sat: 평균 채도(0–1). 원화(연필·종이)는 낮다.
- paper: 밝고(L>80) 채도 낮은 화소 비율의 중앙값. 흰 종이 바탕.
- grain: 평평한 영역(5x5 표준편차 하위 30%)에서 라플라시안 절대값 평균. 필름 입자·종이 질감.
- wd_*: WD ViT Tagger v3(SmilingWolf/wd-vit-tagger-v3, ONNX, CPU) 태그 확률의 8프레임 평균.
  sketch·lineart·traditional_media·graphite_(medium)·monochrome·greyscale·paper → 원화 쪽,
  film_grain·retro_artstyle·1990s_(style)·1980s_(style) → 셀 시대 쪽.
--sheets: 8프레임 띠(200x112)를 <post_id>.jpg로 저장(육안 확인용, 공개 금지).
판정은 이 지표만으로 하지 않는다. 태그·연도표·육안과 합쳐서 정한다(docs/SOURCE-FORMAT-2026-10-20.md).
"""
import csv, glob, json, os, subprocess, sys
import numpy as np
import cv2

TAGS = ['sketch', 'lineart', 'traditional_media', 'graphite_(medium)', 'monochrome', 'greyscale', 'paper',
        'film_grain', 'retro_artstyle', '1990s_(style)', '1980s_(style)', '2000s_(style)', 'pillarboxed', 'letterboxed']
N = 8


def probe(path):
    p = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-count_packets', '-show_entries',
                        'stream=width,height,r_frame_rate,nb_read_packets', '-of', 'json', path],
                       capture_output=True, text=True, stdin=subprocess.DEVNULL)
    s = json.loads(p.stdout or '{}').get('streams', [{}])[0]
    a, b = (s.get('r_frame_rate', '0/1').split('/') + ['1'])[:2]
    return int(s.get('width', 0)), int(s.get('height', 0)), round(float(a) / max(float(b), 1), 3), int(s.get('nb_read_packets', 0) or 0)


def grab(path, idx, w):
    sel = '+'.join(f'eq(n\\,{i})' for i in idx)
    p = subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-i', path, '-vf', f"select='{sel}',scale={w}:-2",
                        '-vsync', '0', '-f', 'image2pipe', '-vcodec', 'png', '-'], capture_output=True, stdin=subprocess.DEVNULL)
    out, buf = [], p.stdout
    while buf:
        end = buf.find(b'IEND') + 8
        if end < 8:
            break
        im = cv2.imdecode(np.frombuffer(buf[:end], np.uint8), cv2.IMREAD_COLOR)
        if im is not None:
            out.append(cv2.cvtColor(im, cv2.COLOR_BGR2RGB))
        buf = buf[end:]
    return out


class Tagger:
    def __init__(self):
        import onnxruntime as rt
        from huggingface_hub import hf_hub_download
        rid = 'SmilingWolf/wd-vit-tagger-v3'
        names = [r['name'] for r in csv.DictReader(open(hf_hub_download(rid, 'selected_tags.csv')))]
        self.idx = [names.index(t) for t in TAGS]
        self.sess = rt.InferenceSession(hf_hub_download(rid, 'model.onnx'), providers=['CPUExecutionProvider'])
        self.inp = self.sess.get_inputs()[0]
        self.size = self.inp.shape[1]

    def __call__(self, frames):
        batch = []
        for f in frames:
            h, w = f.shape[:2]
            m = max(h, w)
            sq = np.full((m, m, 3), 255, np.uint8)
            sq[(m - h) // 2:(m - h) // 2 + h, (m - w) // 2:(m - w) // 2 + w] = f
            sq = cv2.resize(sq, (self.size, self.size), interpolation=cv2.INTER_CUBIC)
            batch.append(sq[:, :, ::-1].astype(np.float32))  # 공식 예제와 같이 BGR, 0–255
        pr = self.sess.run(None, {self.inp.name: np.stack(batch)})[0]
        return {t: round(float(pr[:, i].mean()), 3) for t, i in zip(TAGS, self.idx)}


def stats(frames):
    sat, paper, grain = [], [], []
    for f in frames:
        hsv = cv2.cvtColor(f, cv2.COLOR_RGB2HSV)
        L = cv2.cvtColor(f, cv2.COLOR_RGB2LAB)[..., 0].astype(np.float32) * 100 / 255
        s = hsv[..., 1].astype(np.float32) / 255
        sat.append(float(s.mean()))
        paper.append(float(((L > 80) & (s < 0.12)).mean()))
        g = cv2.cvtColor(f, cv2.COLOR_RGB2GRAY).astype(np.float32)
        mu = cv2.blur(g, (5, 5))
        sd = np.sqrt(np.maximum(cv2.blur(g * g, (5, 5)) - mu * mu, 0))
        flat = sd <= np.percentile(sd, 30)
        grain.append(float(np.mean(np.abs(cv2.Laplacian(g, cv2.CV_32F))[flat])))
    return {'sat': round(float(np.median(sat)), 3), 'paper': round(float(np.median(paper)), 3),
            'grain': round(float(np.median(grain)), 3)}


def main():
    tcsv, src, out = sys.argv[1:4]
    sheets = sys.argv[sys.argv.index('--sheets') + 1] if '--sheets' in sys.argv else None
    files = {os.path.basename(f).split('.')[0]: f for f in glob.glob(src + '/*')}
    rows = list(csv.DictReader(open(tcsv, encoding='utf-8-sig')))
    done = {r['post_id'] for r in csv.DictReader(open(out, encoding='utf-8'))} if os.path.exists(out) else set()
    tag = Tagger()
    cols = ['width', 'height', 'aspect', 'fps', 'frames', 'sat', 'paper', 'grain'] + ['wd_' + t for t in TAGS]
    fo = open(out, 'a', newline='', encoding='utf-8')
    w = csv.DictWriter(fo, fieldnames=list(rows[0]) + [c for c in cols if c not in rows[0]])
    if not done:
        w.writeheader()
    for n, r in enumerate(rows):
        pid = r['post_id']
        if pid in done or pid not in files:
            continue
        wd, ht, fps, nf = probe(files[pid])
        if nf < 1:
            continue
        lo, hi = int(nf * 0.05), max(int(nf * 0.95) - 1, int(nf * 0.05))
        idx = sorted(set(np.linspace(lo, hi, N).round().astype(int).tolist()))
        fr = grab(files[pid], idx, 448)
        if not fr:
            continue
        res = dict(r, width=wd, height=ht, aspect=round(wd / max(ht, 1), 3), fps=fps, frames=nf)
        res.update(stats(fr))
        res.update({'wd_' + k: v for k, v in tag(fr).items()})
        w.writerow(res)
        fo.flush()
        if sheets:
            os.makedirs(sheets, exist_ok=True)
            tiles = [cv2.resize(f, (200, 112)) for f in fr]
            tiles += [np.zeros_like(tiles[0])] * (N - len(tiles))
            cv2.imwrite(os.path.join(sheets, f'{pid}.jpg'), cv2.cvtColor(np.hstack(tiles), cv2.COLOR_RGB2BGR),
                        [cv2.IMWRITE_JPEG_QUALITY, 80])
        if n % 25 == 0:
            print('progress', n, len(rows), flush=True)
    print('DONE', flush=True)


if __name__ == '__main__':
    main()
