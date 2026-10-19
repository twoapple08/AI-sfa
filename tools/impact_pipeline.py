#!/usr/bin/env python3
"""원본 폴더 → 임팩트 후보 3분류까지 한 번에(추론만, 모델 훈련 없음). GTX 1050 Ti 같은 PC에서 돌리는 용도.

사용:
  python tools/impact_pipeline.py <원본 폴더> <출력 폴더> [--workers 3] [--refs <예시 이미지 폴더>]
  (GPU: IMPACT_DEVICE=cuda 환경 변수. --refs가 없으면 X-CLIP 단계를 건너뛴다.)

단계(각 단계 결과 파일이 있으면 이어서 한다):
1. impact_scan2.scan(): 영상마다 한 번 순차 디코딩해 후보 구간을 찾는다(CPU, --workers 병렬) → cands.csv
2. impact_context: 앞뒤 문맥과 같은 그림 방식인지(same_style) → context.csv
3. impact_xclip(--refs 있을 때): same_style=0인 후보만 X-CLIP·예시 유사도 → xclip.csv
4. impact_narrow_classify 점수와 합쳐 final.csv: class = 단색섬광(옆 확인) / 아님(같은그림) / 유력 / 재검사 / 아님유력 / 미판정
   단색섬광: 후보 프레임 전부에 그림이 없음(흰·검정 단색). 규칙상 low·cel_light이고, 실제 임팩트가 바로 옆에 있는 경우가 많다
   (재검사 291 대조: 그림 없음 56 = 육안 단색 44·옆에실제 9·아님 3, 임팩트 0).
원본 파일 이름은 <post_id>.<확장자>여야 한다. 출력 CSV에는 프레임 번호·지표만 들어간다(이미지 없음).
"""
import argparse
import csv
import glob
import os
import subprocess
import sys
from concurrent.futures import ProcessPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def scan_one(path):
    import impact_scan2
    post = os.path.basename(path).split('.')[0]
    try:
        r = impact_scan2.scan(path)
    except Exception as e:  # 깨진 원본은 건너뛰고 기록만 남긴다
        return post, None, str(e)
    return post, [(x['start'], x['end']) for x in r['runs']], ''


def read(p):
    return list(csv.DictReader(open(p, encoding='utf-8'))) if os.path.exists(p) else []


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('src')
    ap.add_argument('out')
    ap.add_argument('--workers', type=int, default=max(1, (os.cpu_count() or 2) - 1))
    ap.add_argument('--refs')
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    cands, ctx, xc, fin = (os.path.join(a.out, n) for n in ('cands.csv', 'context.csv', 'xclip.csv', 'final.csv'))

    vids = sorted(f for f in glob.glob(os.path.join(a.src, '*')) if f.rsplit('.', 1)[-1].lower() in ('mp4', 'webm', 'gif', 'mkv', 'mov'))
    done = {r['post_id'] for r in read(cands)} | {l.split('\t')[0] for l in open(os.path.join(a.out, 'scanned.txt'))} \
        if os.path.exists(os.path.join(a.out, 'scanned.txt')) else set()
    todo = [v for v in vids if os.path.basename(v).split('.')[0] not in done]
    print('영상', len(vids), '남음', len(todo), flush=True)
    new = not os.path.exists(cands)
    with open(cands, 'a', newline='', encoding='utf-8') as fc, open(os.path.join(a.out, 'scanned.txt'), 'a') as fs, \
            ProcessPoolExecutor(a.workers) as ex:
        w = csv.writer(fc)
        if new:
            w.writerow(['key', 'post_id', 'frames', 'label'])
        for n, (post, runs, err) in enumerate(ex.map(scan_one, todo)):
            for s, e in runs or []:
                w.writerow([f'{post}:{s}-{e}', post, f'{s}-{e}', ''])
            fs.write(f'{post}\t{err}\n')
            fc.flush()
            fs.flush()
            if n % 10 == 0:
                print('scan', n, len(todo), flush=True)

    env = {**os.environ}
    subprocess.run([sys.executable, os.path.join(HERE, 'impact_context.py'), cands, a.src, ctx], check=True, env=env)
    C = read(ctx)
    X = {}
    if a.refs:
        rest = os.path.join(a.out, 'xclip_rows.csv')
        rows = [r for r in C if r['same_style'] != '1']
        with open(rest, 'w', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=['key', 'post_id', 'frames', 'label'], extrasaction='ignore')
            w.writeheader()
            w.writerows(rows)
        subprocess.run([sys.executable, os.path.join(HERE, 'impact_xclip.py'), rest, a.src, a.refs, xc], check=True, env=env)
        cls = os.path.join(a.out, 'xclip_class.csv')
        subprocess.run([sys.executable, os.path.join(HERE, 'impact_narrow_classify.py'), xc, cls], check=True, env=env)
        X = {r['key']: r for r in read(cls)}
    out = []
    for r in C:
        x = X.get(r['key'], {})
        r['xclip_pos'], r['ref_sim'], r['cont'] = x.get('xclip_pos', ''), x.get('ref_sim', ''), x.get('cont', '')
        r['narrow_score'] = x.get('narrow_score', '')
        if r['drawn'].split('/')[0] == '0':
            r['class'] = '단색섬광(옆 확인)'
        elif r['same_style'] == '1':
            r['class'] = '아님(같은그림)'
        else:
            r['class'] = x.get('narrow_class', '미판정')
        out.append(r)
    if out:
        with open(fin, 'w', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=list(out[0]))
            w.writeheader()
            w.writerows(out)
    from collections import Counter
    print('final', len(out), dict(Counter(r['class'] for r in out)), flush=True)


if __name__ == '__main__':
    main()
