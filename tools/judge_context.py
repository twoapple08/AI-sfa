#!/usr/bin/env python3
"""사용자 판정 묶음 보강: 폴더마다 번호 붙은 문맥 시트(1/4속 영상과 같은 범위) + 판정표에 연속성 경고·인접 후보 열.

사용: python tools/judge_context.py <판정표.csv> <원본 폴더> <출력 폴더>
- 판정표.csv: make_judge_bundle.py가 만든 것(Drive에서 받은 것). 열 post_id,frames,folder 필요.
- 원본 폴더: <post_id>.<ext> 원본 영상(md5 대조는 받을 때 한다).
- 출력: <출력>/<animator>/<folder>/문맥시트.jpg, <출력>/판정표.csv(열 추가, 애니메이터 순 정렬).

문맥 시트: 후보 구간(노란 테두리), tag_overrides의 다른 임팩트 행(하늘색 테두리), 프레임 번호.
연속성(cont): 후보 첫 프레임↔바로 앞, 끝 프레임↔바로 뒤의 에지 상관 최대값. 0.6 이상이면
'앞뒤와 이어짐(동화 의심)'으로 표시한다. 2026-10-19 사용자 A 판정 31건 보정: 아님 22 중 5, 임팩트 4 중 0,
기존 확정 37 중 1이 걸렸다. 경고일 뿐 판정이 아니다.
"""
import csv, glob, os, subprocess, sys
import numpy as np

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGETS = ['yutaka_nakamura', 'nian41', 'yukina_kosaka', 'riooo', 'optical-core']
W, H, THR = 96, 54, 0.6


def animators():
    art = {}
    for f in ['data/catalog.csv', 'data/sakuga/candidates/candidates_catalog.csv']:
        for r in csv.DictReader(open(f'{R}/{f}', encoding='utf-8-sig')):
            if r['post_id'] in art:
                continue
            hit = [t for t in TARGETS if t in r['artists'].split()]
            art[r['post_id']] = hit[0] if hit else '기타_' + r['artists'].split()[0] + '(반려)'
    return art


def rng(fr):
    try:
        a, b = (fr.split('-') + [fr])[:2]
        return int(a), int(b)
    except ValueError:
        return None


def grab(path, s, e):
    p = subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-i', path, '-vf',
                        f'select=between(n\\,{s}\\,{e}),scale={W}:{H}', '-vsync', '0',
                        '-f', 'rawvideo', '-pix_fmt', 'gray', '-'], capture_output=True, stdin=subprocess.DEVNULL)
    a = np.frombuffer(p.stdout, np.uint8).astype(np.float32)
    n = a.size // (W * H)
    return a[:n * W * H].reshape(n, H, W)


def ecorr(x, y):
    x = np.abs(np.diff(x, axis=1))[:-1, :] + np.abs(np.diff(x, axis=0))[:, :-1]
    y = np.abs(np.diff(y, axis=1))[:-1, :] + np.abs(np.diff(y, axis=0))[:, :-1]
    x, y = x - x.mean(), y - y.mean()
    d = np.sqrt((x * x).sum() * (y * y).sum())
    return float((x * y).sum() / d) if d > 1e-6 else 0.0


def cont(path, a, b):
    F = grab(path, max(0, a - 1), b + 1)
    off = a - max(0, a - 1)
    vals = []
    if off and len(F) > off:
        vals.append(ecorr(F[off], F[0]))
    if len(F) > off + (b - a + 1):
        vals.append(ecorr(F[off + b - a], F[-1]))
    return round(max(vals), 3) if vals else ''


def sheet(path, s, e, a, b, others, out):
    between = lambda x, y: f'between(n+{s}\\,{x}\\,{y})'
    vf = [f'select=between(n\\,{s}\\,{e})', 'scale=240:-2']
    for x, y in others:
        vf.append(f"drawbox=c=cyan:t=8:enable='{between(x, y)}'")
    vf.append(f"drawbox=c=yellow:t=8:enable='{between(a, b)}'")
    vf.append(f"drawtext=text='f%{{eif\\:n+{s}\\:d}}':x=6:y=6:fontsize=22:fontcolor=red:box=1:boxcolor=white")
    rows = (e - s + 1 + 7) // 8
    vf.append(f'tile=8x{rows}')
    subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-i', path, '-vf', ','.join(vf), '-vsync', '0',
                    '-frames:v', '1', '-q:v', '4', out], stdin=subprocess.DEVNULL)


def main():
    table, src, outdir = sys.argv[1:4]
    art = animators()
    files = {os.path.basename(f).split('.')[0]: f for f in glob.glob(src + '/*')}
    ov = [r for r in csv.DictReader(open(f'{R}/data/style_kb/tag_overrides.csv', encoding='utf-8'))
          if r['tag'].startswith('impact_frames') and r['status'] in ('candidate', 'confirmed', 'borderline') and rng(r['frames'])]
    rows = list(csv.DictReader(open(table, encoding='utf-8-sig')))
    for r in rows:
        pid, fr = r['post_id'], r['frames']
        r['animator'] = art.get(pid, '?')
        r['cont'], r['continuity_warning'], r['nearby_impact_rows'] = '', '', ''
        ab = rng(fr)
        if not ab or pid not in files or r['folder'].startswith('('):
            continue
        a, b = ab
        lo, hi = max(0, a - 2 - 12), b + 2 + 12  # slow_quarter.mp4와 같은 범위
        near = [(rng(o['frames']), o) for o in ov if o['post_id'] == pid and rng(o['frames']) != (a, b)]
        near = [(x, o) for x, o in near if x[1] >= lo and x[0] <= hi]
        r['nearby_impact_rows'] = '; '.join(f"f{o['frames']}({o['status']})" for _, o in near)
        c = cont(files[pid], a, b)
        r['cont'] = c
        if c != '' and c >= THR:
            r['continuity_warning'] = '앞뒤와 이어짐(동화 의심)'
        base = r['folder'].split('/')[-1]
        d = f"{outdir}/{r['animator']}/{base}"
        os.makedirs(d, exist_ok=True)
        sheet(files[pid], lo, hi, a, b, [x for x, _ in near], f'{d}/문맥시트_f{lo}-{hi}.jpg')
        r['folder'] = f"{r['animator']}/{base}"
    rows.sort(key=lambda r: (r['animator'], r['no']))
    with open(f'{outdir}/판정표.csv', 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print('rows', len(rows), 'warn', sum(bool(r['continuity_warning']) for r in rows))


if __name__ == '__main__':
    main()
