#!/usr/bin/env python3
"""YOLO 포즈(jsonl.gz)에서 리그 A용 동작 조각과 타이밍 통계를 만든다.

- nian41: 몸 뼈대 동작(관절 각도 조각)
- 나카무라: 타격 타이밍(빠름·멈춤 길이, 타격 간격)만

출력 JSON은 생성 앱(creator-android)의 assets로 들어간다. 원본 영상·포즈 파일은 저장소에 넣지 않는다.
사용: python tools/motion_lib.py --nian <dir> --nak <dir> --out motion_lib.json
"""
import argparse
import glob
import gzip
import json
import math
import os
import statistics

# COCO 17 키포인트
NOSE, LEAR, REAR = 0, 3, 4
LS, RS, LE, RE, LW, RW = 5, 6, 7, 8, 9, 10
LH, RH, LK, RK, LA, RA = 11, 12, 13, 14, 15, 16
BODY = [LS, RS, LE, RE, LW, RW, LH, RH, LK, RK, LA, RA]
SPINE = 1.6          # 리그 A 몸통 길이(머리=1)
FPS = 24.0


def frames(path):
    with gzip.open(path, 'rt', encoding='utf-8') as fh:
        for line in fh:
            yield json.loads(line)


def iou(a, b):
    x0, y0 = max(a[0], b[0]), max(a[1], b[1])
    x1, y1 = min(a[2], b[2]), min(a[3], b[3])
    inter = max(0, x1 - x0) * max(0, y1 - y0)
    ua = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / ua if ua > 0 else 0


def runs(path, th, min_len):
    """온몸이 잡힌 같은 사람의 연속 구간(박스 IoU로 추적)."""
    cur, prev = [], None
    for x in frames(path):
        ok = [p for p in x['p'] if min(p['kpts'][k][2] for k in BODY) >= th and p['box'][3] - p['box'][1] > 80]
        pick = None
        if ok:
            if prev is None:
                pick = max(ok, key=lambda p: p['conf'])
                pick['f'] = x['f']
            else:
                best = max(ok, key=lambda p: iou(p['box'], prev['box']))
                if iou(best['box'], prev['box']) > 0.2:
                    pick = best
        if pick is None:
            if len(cur) >= min_len:
                yield cur
            cur, prev = [], None
            if ok:
                prev = max(ok, key=lambda p: p['conf'])
                prev['f'] = x['f']
                cur = [prev]
            continue
        pick['f'] = x['f']
        cur.append(pick)
        prev = pick
    if len(cur) >= min_len:
        yield cur


def mid(a, b):
    return ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)


def ang(a, b):
    return math.degrees(math.atan2(b[1] - a[1], b[0] - a[0]))


def unwrap(seq):
    out = [seq[0]]
    for v in seq[1:]:
        d = (v - out[-1] + 180) % 360 - 180
        out.append(out[-1] + d)
    return out


def median3(seq):
    if len(seq) < 3:
        return seq
    return [seq[0]] + [sorted(seq[i - 1:i + 2])[1] for i in range(1, len(seq) - 1)] + [seq[-1]]


def to_clip(run):
    """프레임마다 관절 각도(도, 0=오른쪽 90=아래)와 루트 위치(몸통 단위)."""
    k = [[(q[0], q[1]) for q in p['kpts']] for p in run]
    torso = statistics.median(math.dist(mid(f[LS], f[RS]), mid(f[LH], f[RH])) for f in k)
    if torso < 20:
        return None
    unit = torso / SPINE
    # 얼굴 방향으로 좌우를 정한다. 오른쪽을 보도록 뒤집는다
    face = statistics.median(f[NOSE][0] - mid(f[LS], f[RS])[0] for f in k)
    flip = face < 0
    if flip:
        k = [[(-x, y) for x, y in f] for f in k]
    names = ['sp', 'nk', 'ua0', 'fa0', 'ua1', 'fa1', 'th0', 'sh0', 'th1', 'sh1']
    tracks = {n: [] for n in names}
    root, ground = [], []
    for f in k:
        sh, hp = mid(f[LS], f[RS]), mid(f[LH], f[RH])
        tracks['sp'].append(ang(hp, sh))
        tracks['nk'].append(ang(sh, mid(f[LEAR], f[REAR])))
        # 0번 팔다리 = 화면 앞(오른쪽, 상대 쪽)에 더 가까운 쪽이 아니라 해부학 왼쪽. 앱에서 앞뒤를 정한다
        for i, (s, e, w) in enumerate(((LS, LE, LW), (RS, RE, RW))):
            tracks[f'ua{i}'].append(ang(f[s], f[e]))
            tracks[f'fa{i}'].append(ang(f[e], f[w]))
        for i, (h, kn, a) in enumerate(((LH, LK, LA), (RH, RK, RA))):
            tracks[f'th{i}'].append(ang(f[h], f[kn]))
            tracks[f'sh{i}'].append(ang(f[kn], f[a]))
        root.append(hp)
        ground.append(max(f[LA][1], f[RA][1]))
    for n in names:
        tracks[n] = [round(v, 1) for v in median3(unwrap(tracks[n]))]
    x0 = root[0][0]
    g = statistics.median(ground)
    rx = [round((r[0] - x0) / unit, 3) for r in root]          # 카메라 이동이 섞여 있어 참고용
    ry = [round((g - r[1]) / unit, 3) for r in root]           # 바닥(발목 중앙값) 위 엉덩이 높이
    return {'n': len(run), 'flip': flip, 'unit_px': round(unit, 2), 'a': tracks, 'rx': rx, 'ry': ry}


def tip_speed(clip):
    """손·발 끝의 루트 기준 속도(몸통 단위/프레임)와 뻗은 거리."""
    a = clip['a']
    L = {'ua': 1.25, 'fa': 1.15, 'th': 1.55, 'sh': 1.5}
    out = []
    for i in range(clip['n']):
        tips = {}
        for limb, (u, f) in (('arm0', ('ua0', 'fa0')), ('arm1', ('ua1', 'fa1')), ('leg0', ('th0', 'sh0')), ('leg1', ('th1', 'sh1'))):
            lu, lf = L[u[:2]], L[f[:2]]
            base = (0.0, 0.0)
            if limb.startswith('arm'):
                s = math.radians(a['sp'][i])
                base = (SPINE * math.cos(s), SPINE * math.sin(s))
            p1 = (base[0] + lu * math.cos(math.radians(a[u][i])), base[1] + lu * math.sin(math.radians(a[u][i])))
            p2 = (p1[0] + lf * math.cos(math.radians(a[f][i])), p1[1] + lf * math.sin(math.radians(a[f][i])))
            tips[limb] = p2
        out.append(tips)
    return out


def strikes(clip):
    """손·발이 앞으로 크게 뻗는 순간(타격). 흔들림을 거르려고 뻗기 전후 차이·높이·간격을 본다."""
    tips = tip_speed(clip)
    n = clip['n']
    ev = []
    for limb in ('arm0', 'arm1', 'leg0', 'leg1'):
        rx = [t[limb][0] for t in tips]
        ry = [t[limb][1] for t in tips]
        for i in range(n):
            lo, hi = max(0, i - 3), min(n, i + 4)
            if rx[i] < max(rx[lo:hi]) or rx[i] < 2.0:
                continue
            before = min(rx[max(0, i - 6):i + 1])
            if rx[i] - before < 1.2:
                continue
            if limb[0] == 'l' and ry[i] > 1.0:      # 발이 무릎 높이보다 낮으면 발차기가 아니다
                continue
            if limb[0] == 'a' and not (-4.0 < ry[i] < 0.8):
                continue
            ev.append({'f': i, 'limb': limb, 'ext': round(rx[i] - before, 2), 'reach': round(rx[i], 2), 'h': round(ry[i], 2)})
    ev.sort(key=lambda e: -e['ext'])
    keep = []
    for e in ev:
        if all(abs(e['f'] - k['f']) >= 5 for k in keep):
            keep.append(e)
    return sorted(keep, key=lambda e: e['f'])


def moves(clips, before=8, after=8):
    """타격 하나를 중심으로 자른 동작 조각. peak는 조각 안에서 타격 프레임 위치."""
    out = []
    for c in clips:
        for e in c['strikes']:
            a, b = max(0, e['f'] - before), min(c['n'], e['f'] + after + 1)
            if e['f'] - a < 3 or b - e['f'] < 4:
                continue
            out.append({'src': c['src'], 'limb': e['limb'], 'peak': e['f'] - a, 'reach': e['reach'], 'h': e['h'],
                        'a': {k: v[a:b] for k, v in c['a'].items()}, 'ry': c['ry'][a:b]})
    return out


NAMES = ['sp', 'nk', 'ua0', 'fa0', 'ua1', 'fa1', 'th0', 'sh0', 'th1', 'sh1']


def wrap(d):
    return (d + 180) % 360 - 180


def upright(a, i):
    """몸통이 서 있고 두 다리가 아래를 향하는 자세인가(넘어짐·구르기 제외)."""
    if not -125 <= wrap(a['sp'][i]) <= -55 or not -150 <= wrap(a['nk'][i]) <= -30:
        return False
    return all(35 <= wrap(a[k][i]) <= 145 for k in ('th0', 'th1', 'sh0', 'sh1'))


def keyposes(lib):
    """펀치 핵심 자세 3장(준비·타격·뒤따름). 흔들린 프레임을 피하려고 자세 조건으로 거른다."""
    out = []
    for m in lib['moves']:
        if m['limb'][0] != 'a':
            continue
        a, pk = m['a'], m['peak']
        k = m['limb'][-1]
        ua, fa = f'ua{k}', f'fa{k}'
        if not upright(a, pk) or abs(wrap(a[ua][pk] - a[fa][pk])) > 30 or not -70 <= wrap(a[ua][pk]) <= 40:
            continue
        tip = tip_speed({'n': len(m['ry']), 'a': a})
        limb = 'arm' + k
        if tip[pk]['arm' + str(1 - int(k))][0] > 1.5:   # 반대팔도 앞으로 뻗은 T자 자세 제외
            continue
        cand = [i for i in range(max(0, pk - 8), pk - 1) if upright(a, i) and tip[i][limb][0] < tip[pk][limb][0] - 1.0]
        if not cand:
            continue
        w = min(cand, key=lambda i: tip[i][limb][0])
        f = min(len(m['ry']) - 1, pk + 3)
        if not upright(a, f):
            f = pk
        out.append({'arm': int(k), 'reach': m['reach'], 'h': m['h'], 'src': m['src'],
                    'pose': [[round(wrap(a[n][i]), 1) for n in NAMES] for i in (w, pk, f)], 'wind': pk - w})
    return out


def write_asset(lib, path):
    """앱용 간단한 글자 형식(외부 라이브러리 없이 읽기).
    T 줄: 나카무라 타이밍(p50,p75: 타격 전 멈춤·타격·타격 뒤 멈춤·간격, 정지 비율)
    P 줄: 펀치 하나(팔 번호, 뻗은 거리, 높이, 준비→타격 프레임) 다음 3줄이 준비·타격·뒤따름 자세 각도 10개"""
    with open(path, 'w', encoding='utf-8') as fh:
        t = lib['timing']
        fh.write('T ' + ' '.join(str(t[k]['p50'] if t[k] else 0) + ',' + str(t[k]['p75'] if t[k] else 0)
                                 for k in ('pre_hold', 'strike', 'post_hold', 'gap')) + f" {t['still_ratio']}\n")
        for k in lib['punches']:
            fh.write(f"P {k['arm']} {k['reach']} {k['h']} {k['wind']}\n")
            for row in k['pose']:
                fh.write(' '.join(str(v) for v in row) + '\n')


def timing(clips):
    """나카무라 타이밍: 타격 전 멈춤, 타격 프레임 수, 타격 뒤 멈춤, 타격 간격, 정지 프레임 비율."""
    pre, strike, post, gap, still = [], [], [], [], []
    for c in clips:
        tips = tip_speed(c)
        sp = [0.0] + [max(math.dist(tips[i][l], tips[i - 1][l]) for l in tips[i]) for i in range(1, len(tips))]
        still += [1 if v < 0.08 else 0 for v in sp[1:]]
        peaks = sorted(set(e['f'] for e in strikes(c)))
        for j, p in enumerate(peaks):
            a = p
            while a > 0 and sp[a - 1] >= 0.25:
                a -= 1
            h = a
            while h > 0 and sp[h - 1] < 0.08:
                h -= 1
            b = p
            while b + 1 < len(sp) and sp[b + 1] >= 0.25:
                b += 1
            z = b
            while z + 1 < len(sp) and sp[z + 1] < 0.08:
                z += 1
            strike.append(b - a + 1)
            pre.append(a - h)
            post.append(z - b)
            if j:
                gap.append(p - peaks[j - 1])

    def q(v):
        if not v:
            return None
        v = sorted(v)
        return {'n': len(v), 'p25': v[len(v) // 4], 'p50': v[len(v) // 2], 'p75': v[3 * len(v) // 4]}
    return {'fps': FPS, 'pre_hold': q(pre), 'strike': q(strike), 'post_hold': q(post), 'gap': q(gap),
            'still_ratio': round(sum(still) / max(1, len(still)), 3)}


def build(d, th, min_len):
    clips = []
    for path in sorted(glob.glob(os.path.join(d, '**', '*.jsonl.gz'), recursive=True)):
        vid = os.path.basename(path)[:-9]
        for r in runs(path, th, min_len):
            c = to_clip(r)
            if c:
                c['src'] = vid
                c['start'] = r[0]['f']
                c['strikes'] = strikes(c)
                clips.append(c)
    return clips


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--nian', required=True)
    ap.add_argument('--nak', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--th', type=float, default=0.3)
    ap.add_argument('--min', type=int, default=12)
    ap.add_argument('--asset', help='앱용 글자 형식 출력 경로')
    a = ap.parse_args()
    nian = build(a.nian, a.th, a.min)
    nak = build(a.nak, a.th, a.min)
    lib = {'rig': 'A', 'units': 'head=1, spine=1.6', 'angle': 'deg, 0=right 90=down, facing +x',
           'clips': [{k: c[k] for k in ('src', 'start', 'n', 'a', 'ry', 'strikes')} for c in nian],
           'moves': moves(nian),
           'timing': timing(nak), 'timing_nian41': timing(nian)}
    lib['punches'] = keyposes(lib)
    with open(a.out, 'w', encoding='utf-8') as fh:
        json.dump(lib, fh, ensure_ascii=False, separators=(',', ':'))
    print('깨끗한 펀치 핵심 자세', len(lib['punches']))
    if a.asset:
        write_asset(lib, a.asset)
    ev = sum(len(c['strikes']) for c in nian)
    from collections import Counter
    print('조각 종류', Counter(m['limb'][:3] for m in lib['moves']))
    print('nian41 조각', len(nian), '프레임', sum(c['n'] for c in nian), '타격 후보', ev)
    print('나카무라 타이밍', json.dumps(lib['timing'], ensure_ascii=False))
    print('nian41 타이밍', json.dumps(lib['timing_nian41'], ensure_ascii=False))


if __name__ == '__main__':
    main()
