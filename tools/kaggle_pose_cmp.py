#!/usr/bin/env python3
"""단계 2 포즈 검출기 비교(2026-11-05 사용자 '추천대로'): 30구간 장면을 비공개 Kaggle 자료로 올리고 GPU에서 ViTPose++ Huge·Sapiens 1B를 돌린다.

  pack <작업 폴더>   : out/summary.json 구간의 장면(저화질 영상) + RTMW 사람 상자 → <작업 폴더>/posecmp/(frames/, meta.json)
  push-data <작업 폴더>: 위 폴더를 비공개 자료 aisfa-posecmp-frames로(있으면 새 판)
  push               : 작업자(kaggle_pose_cmp_worker.py)를 비공개 GPU 커널 aisfa-posecmp로
  status | pull <폴더>
  apply <작업 폴더> <모델> : 받은 pose_<모델>.jsonl로 RTMW 파일의 해당 장 키포인트를 바꾼 사본 → <작업 폴더>_<모델>/rtmw/
      (상자는 RTMW 것을 그대로 써서 추적·구간은 같고 관절만 바뀐다. 점수는 RTMW 점수 분포에 분위 맞춤 — 거르기 문턱을 그대로 쓰려고)
원본 장면·좌표는 비공개 자료/작업 폴더에만. 인증값은 출력하지 않는다(kaggle_seq_remote.kg 재사용).
"""
import gzip, json, os, shutil, subprocess, sys, tempfile
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kaggle_seq_remote import kg, user  # noqa: E402

DATASET, KERNEL = 'aisfa-posecmp-frames', 'aisfa-posecmp'
HERE = os.path.dirname(os.path.abspath(__file__))


def pack(work):
    import cv2, stage2_extract as X
    S = json.load(open(f'{work}/out/summary.json'))['segments']
    d = f'{work}/posecmp'; shutil.rmtree(d, ignore_errors=True); os.makedirs(f'{d}/frames')
    RES = dict(X.VIDEOS); meta = []
    for s in S:
        vid = s['video']; R = X.load_rtmw(f'{work}/rtmw/{vid}.jsonl.gz')
        cap = cv2.VideoCapture(f'{work}/video/{vid}.mp4'); lw = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
        sc = RES[vid][0] / lw
        for f in range(s['start'], s['end'] + 1):
            name = f'{vid}_{f}.jpg'
            if not os.path.exists(f'{d}/frames/{name}'):
                cap.set(cv2.CAP_PROP_POS_FRAMES, f); ok, im = cap.read()
                if not ok: continue
                cv2.imwrite(f'{d}/frames/{name}', im, [cv2.IMWRITE_JPEG_QUALITY, 95])
                meta.append(dict(img=name, video=vid, frame=f, scale=sc, boxes=[b.tolist() for b, _ in R.get(f, [])]))
    json.dump(meta, open(f'{d}/meta.json', 'w'))
    print('장', len(meta), '상자', sum(len(m['boxes']) for m in meta))


def push_data(work):
    u = user(); d = f'{work}/posecmp'
    json.dump(dict(title=DATASET, id=f'{u}/{DATASET}', licenses=[dict(name='CC0-1.0')]), open(f'{d}/dataset-metadata.json', 'w'))
    exists = any(l.split(',')[0] == f'{u}/{DATASET}' for l in kg('datasets', 'list', '--mine', '-s', DATASET, '--csv', check=False).splitlines())
    out = kg('datasets', 'version', '-p', d, '-m', 'update', '-r', 'zip') if exists else kg('datasets', 'create', '-p', d, '-r', 'zip')
    print(out[-400:])


def push():
    u = user(); d = tempfile.mkdtemp(prefix='kpose_')
    shutil.copy(f'{HERE}/kaggle_pose_cmp_worker.py', f'{d}/kernel.py')
    json.dump(dict(id=f'{u}/{KERNEL}', title=KERNEL, code_file='kernel.py', language='python', kernel_type='script', is_private=True,
                   enable_gpu=True, enable_internet=True, dataset_sources=[f'{u}/{DATASET}'], competition_sources=[], kernel_sources=[]),
              open(f'{d}/kernel-metadata.json', 'w'))
    out = kg('kernels', 'push', '-p', d); shutil.rmtree(d); print(out[-400:])


def status():
    print(kg('kernels', 'status', f'{user()}/{KERNEL}', check=False)[-300:])


def pull(dst):
    os.makedirs(dst, exist_ok=True)
    print(kg('kernels', 'output', f'{user()}/{KERNEL}', '-p', dst, check=False)[-400:])


def quantile_map(new, ref):
    """새 점수 → RTMW 점수 분포(같은 순위)."""
    qs = np.linspace(0, 100, 201)
    return lambda x: np.interp(x, np.percentile(new, qs), np.percentile(ref, qs))


def apply(work, model, pulled):
    import stage2_extract as X
    rows = [json.loads(l) for l in open(f'{pulled}/pose_{model}.jsonl')]
    dst = f'{work}_{model}'
    os.makedirs(f'{dst}/rtmw', exist_ok=True)
    for sub in ('video', 'cuts'):
        if not os.path.lexists(f'{dst}/{sub}'): os.symlink(f'{work}/{sub}', f'{dst}/{sub}')
    for fn in os.listdir(work):
        if fn.startswith('rtmw_') and not os.path.exists(f'{dst}/{fn}'): shutil.copy(f'{work}/{fn}', dst)
    by = {}
    for r in rows: by.setdefault(r['video'], {})[r['frame']] = r['people']
    new_s = np.concatenate([np.array(p)[:17, 2] for r in rows for p in r['people']]) if rows else np.zeros(1)
    ref_s = []
    for vid in by:
        R = X.load_rtmw(f'{work}/rtmw/{vid}.jsonl.gz')
        ref_s += [k[:17, 2] for f in by[vid] for _, k in R.get(f, [])]
    qmap = quantile_map(new_s, np.concatenate(ref_s))
    for fn in os.listdir(f'{work}/rtmw'):
        vid = fn.replace('.jsonl.gz', '')
        if vid not in by:
            if not os.path.lexists(f'{dst}/rtmw/{fn}'): os.symlink(f'{work}/rtmw/{fn}', f'{dst}/rtmw/{fn}')
            continue
        lines = []
        for line in gzip.open(f'{work}/rtmw/{fn}', 'rt'):
            d = json.loads(line); f = int(d['f'])
            if f in by[vid] and len(by[vid][f]) == len(d['p']):
                for p, k in zip(d['p'], by[vid][f]):
                    k = np.array(k); k[:, 2] = qmap(k[:, 2]); k[17:, 2] = np.where(np.array(k)[17:, :2].any(1), k[17:, 2], 0)
                    p['k'] = k.round(3).tolist() + p['k'][23:]
            lines.append(json.dumps(d))
        if os.path.lexists(f'{dst}/rtmw/{fn}'): os.remove(f'{dst}/rtmw/{fn}')
        with gzip.open(f'{dst}/rtmw/{fn}', 'wt') as g: g.write('\n'.join(lines) + '\n')
    print('바꾼 영상', len(by), '→', dst)


if __name__ == '__main__':
    c = sys.argv[1]
    {'pack': lambda: pack(sys.argv[2]), 'push-data': lambda: push_data(sys.argv[2]), 'push': push, 'status': status,
     'pull': lambda: pull(sys.argv[2]), 'apply': lambda: apply(sys.argv[2], sys.argv[3], sys.argv[4])}[c]()
