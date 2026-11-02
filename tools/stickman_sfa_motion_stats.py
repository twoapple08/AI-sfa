"""수집 SFA 스틱맨 뼈대(10-28 추출본)에서 길이 안정성·정지 비율·장당 이동량을 잰다.
좌표: x = X(가로 %), y = hwr * Y (가로 % 단위로 환산).
"""
import json, sys, collections, statistics as st, math

path = sys.argv[1]
tf_path = sys.argv[2]
rows = [json.loads(l) for l in open(path, encoding='utf-8')]
tf = json.load(open(tf_path, encoding='utf-8'))
F_known = {}
for r in tf:
    if 'F' in r and r.get('state') == '확정':
        F_known.setdefault(r['file'].split('/')[-1], set()).add((r.get('T'), r['F']))

def P(p, hwr):
    return (p[0], p[1] * hwr)

def d(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])

def std_ok(r):
    return len(r['arms']) == 2 and len(r['legs']) == 2 and all(len(c[1]) == 3 for c in r['arms'] + r['legs'])

tracks = collections.defaultdict(list)
for r in rows:
    if std_ok(r):
        tracks[(r['file'], r['torso_id'])].append(r)

def joints(r):
    h = r['hwr']
    pts = [P(r['neck'], h), P(r['hip'], h)]
    for _, c in r['arms'] + r['legs']:
        pts += [P(c[1], h), P(c[2], h)]
    pts.append(P(r['head'][1], h))
    return pts

def segs(r):
    h = r['hwr']
    out = [d(P(r['neck'], h), P(r['hip'], h))]
    for _, c in r['arms'] + r['legs']:
        out += [d(P(c[0], h), P(c[1], h)), d(P(c[1], h), P(c[2], h))]
    return out

len_dev = []          # 마디 길이 / 트랙 중앙 길이 - 1 (절대값)
len_dev_noasp = []    # 화면비 보정 없이
relmove = []
move = []             # 연속 장 사이 관절 최대 이동 / 몸통 길이
runs_all = []         # 정지 연속 길이(장)
n_pairs = 0; n_hold = 0
per_file_hold = collections.defaultdict(lambda: [0, 0])
HOLD = 0.01           # 몸통 길이의 1% 미만 이동이면 정지로 본다
ntr = 0
for key, tr in tracks.items():
    tr.sort(key=lambda r: r['frame'])
    if len(tr) < 10:
        continue
    ntr += 1
    S = [segs(r) for r in tr]
    med = [st.median(s[i] for s in S) for i in range(len(S[0]))]
    for s in S:
        for i, v in enumerate(s):
            if med[i] > 1e-6:
                len_dev.append(abs(v / med[i] - 1))
    S2 = []
    for r in tr:
        q = dict(r); q['hwr'] = 1.0; S2.append(segs(q))
    med2 = [st.median(s[i] for s in S2) for i in range(len(S2[0]))]
    for s in S2:
        for i, v in enumerate(s):
            if med2[i] > 1e-6:
                len_dev_noasp.append(abs(v / med2[i] - 1))
    torso = med[0] if med[0] > 1e-6 else 1
    run = 0
    for a, b in zip(tr, tr[1:]):
        if b['frame'] != a['frame'] + 1:
            if run: runs_all.append(run)
            run = 0
            continue
        ja, jb = joints(a), joints(b)
        m = max(d(x, y) for x, y in zip(ja, jb)) / torso
        move.append(m)
        ra = [(x[0]-ja[1][0], x[1]-ja[1][1]) for x in ja]; rb = [(x[0]-jb[1][0], x[1]-jb[1][1]) for x in jb]
        relmove.append(max(d(x, y) for x, y in zip(ra, rb)) / torso)
        n_pairs += 1
        per_file_hold[key[0]][1] += 1
        if m < HOLD:
            n_hold += 1; run += 1
            per_file_hold[key[0]][0] += 1
        else:
            if run: runs_all.append(run)
            run = 0
    if run: runs_all.append(run)

def q(xs, ps=(0.5, 0.9, 0.99)):
    xs = sorted(xs)
    return [round(xs[min(len(xs) - 1, int(p * len(xs)))], 4) for p in ps]

print('트랙(10장 이상, 표준 뼈대):', ntr, ' 파일:', len({k[0] for k in tracks}))
print('마디 길이 편차 |L/중앙-1| 50/90/99%: 화면비 보정', q(len_dev), ' 보정 없음', q(len_dev_noasp))
print('연속 장 쌍:', n_pairs, ' 정지(최대 이동 < 몸통 1%) 비율:', round(n_hold / max(1, n_pairs), 4))
print('장당 최대 관절 이동/몸통 50/90/99%:', q(move), ' 골반 기준(이동 제외):', q(relmove))
rc = collections.Counter(min(r, 6) for r in runs_all)
print('정지 연속 길이 분포(장 쌍 수, 6=6 이상):', sorted(rc.items()))
fh = sorted((h / t, f) for f, (h, t) in per_file_hold.items() if t >= 20)
print('파일별 정지 비율 분포(20쌍 이상 파일', len(fh), '개) 0/25/50/75/100%:',
      [round(fh[int(p * (len(fh) - 1))][0], 3) for p in (0, .25, .5, .75, 1)])
# F 알려진 파일
print('T/F 확정 파일:', len(F_known), sorted({tuple(sorted(v)) for v in F_known.values()})[:12])
kn = [(f, v) for f, v in F_known.items() if any(k[0].endswith(f) for k in tracks)]
print('그중 뼈대 트랙 있는 파일:', len(kn))
for f, v in kn[:12]:
    h, t = next((per_file_hold[k] for k in per_file_hold if k.endswith(f)), (0, 0))
    print('  ', f[:30], sorted(v), '정지비율', round(h / max(1, t), 3), '쌍', t)
