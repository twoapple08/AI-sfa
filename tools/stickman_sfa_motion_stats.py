"""수집 SFA 스틱맨 뼈대(10-28 추출본 jsonl)에서 마디 길이 안정성·정지·장당 이동을 잰다.

좌표는 x = X(가로 %), y = hwr * Y 로 가로 % 단위로 맞춘다(화면비 보정).
2026-11-02 2판: GPT 2차 지적 반영
- 트랙 = (파일, 몸통 ID) 행이 10개 이상(연속 여부와 무관). 연속 구간(장 번호 +1)은 따로 센다.
- 파일 수는 조건을 통과한 트랙 기준으로 센다.
- 정지는 화면 기준(이동 포함)과 골반 기준(이동 제거) 두 가지를 모두 낸다.
- 팔·다리 대응 순서(오브젝트 ID 목록)가 연속 장 사이에 같은지 센다.
- 길이 편차는 '장×마디 관측값' 분포이며, 부호(짧아짐/늘어남)와 큰 편차 표본을 함께 낸다.

사용: python tools/stickman_sfa_motion_stats.py 뼈대.jsonl tf.json [--samples N]
"""
import json, sys, collections, statistics as st, math

HOLD = 0.01  # 관절 최대 이동 < 몸통 길이 1% 이면 정지

def P(p, h):
    return (p[0], p[1] * h)

def dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])

def std_ok(r):
    return len(r['arms']) == 2 and len(r['legs']) == 2 and all(len(c[1]) == 3 for c in r['arms'] + r['legs'])

SEG_NAMES = ['몸통', '팔1위', '팔1아래', '팔2위', '팔2아래', '다리1위', '다리1아래', '다리2위', '다리2아래']

def segs(r, h):
    out = [dist(P(r['neck'], h), P(r['hip'], h))]
    for _, c in r['arms'] + r['legs']:
        out += [dist(P(c[0], h), P(c[1], h)), dist(P(c[1], h), P(c[2], h))]
    return out

def joints(r):
    h = r['hwr']
    pts = [P(r['neck'], h), P(r['hip'], h)]
    for _, c in r['arms'] + r['legs']:
        pts += [P(c[1], h), P(c[2], h)]
    pts.append(P(r['head'][1], h))
    return pts

def q(xs, ps=(0.5, 0.9, 0.99)):
    xs = sorted(xs)
    return [round(xs[min(len(xs) - 1, int(p * len(xs)))], 4) for p in ps] if xs else None

def main(path, tf_path, nsamp=12):
    rows = [json.loads(l) for l in open(path, encoding='utf-8')]
    tracks = collections.defaultdict(list)
    for r in rows:
        if std_ok(r):
            tracks[(r['file'], r['torso_id'])].append(r)
    tracks = {k: sorted(v, key=lambda r: r['frame']) for k, v in tracks.items() if len(v) >= 10}

    dev, sdev, dev_noasp, big = [], [], [], []
    move, relmove = [], []
    hold_scr = hold_rel = n_pairs = 0
    order_same_arm = order_same_leg = 0
    seg_lens = []
    per_file = collections.defaultdict(lambda: [0, 0, 0])  # 화면정지, 골반정지, 쌍
    for key, tr in tracks.items():
        S = [segs(r, r['hwr']) for r in tr]
        med = [st.median(s[i] for s in S) for i in range(len(S[0]))]
        S1 = [segs(r, 1.0) for r in tr]
        med1 = [st.median(s[i] for s in S1) for i in range(len(S1[0]))]
        for r, s, s1 in zip(tr, S, S1):
            for i, v in enumerate(s):
                if med[i] > 1e-6:
                    x = v / med[i] - 1
                    dev.append(abs(x)); sdev.append(x)
                    big.append((abs(x), x, key[0], r['frame'], SEG_NAMES[i]))
                if med1[i] > 1e-6:
                    dev_noasp.append(abs(s1[i] / med1[i] - 1))
        torso = med[0] if med[0] > 1e-6 else 1.0
        run = 1
        for a, b in zip(tr, tr[1:]):
            if b['frame'] != a['frame'] + 1:
                seg_lens.append(run); run = 1
                continue
            run += 1
            n_pairs += 1
            order_same_arm += [c[0] for c in a['arms']] == [c[0] for c in b['arms']]
            order_same_leg += [c[0] for c in a['legs']] == [c[0] for c in b['legs']]
            ja, jb = joints(a), joints(b)
            m = max(dist(x, y) for x, y in zip(ja, jb)) / torso
            ra = [(x[0] - ja[1][0], x[1] - ja[1][1]) for x in ja]
            rb = [(x[0] - jb[1][0], x[1] - jb[1][1]) for x in jb]
            rm = max(dist(x, y) for x, y in zip(ra, rb)) / torso
            move.append(m); relmove.append(rm)
            pf = per_file[key[0]]
            pf[2] += 1
            if m < HOLD: hold_scr += 1; pf[0] += 1
            if rm < HOLD: hold_rel += 1; pf[1] += 1
        seg_lens.append(run)

    files = {k[0] for k in tracks}
    print('트랙(행 10개 이상, 표준 뼈대):', len(tracks), ' 그 트랙의 파일:', len(files))
    sl = collections.Counter(min(x, 24) for x in seg_lens)
    print('연속 구간 수:', len(seg_lens), ' 길이 1/2–9/10–23/24+:',
          sl[1], sum(sl[k] for k in range(2, 10)), sum(sl[k] for k in range(10, 24)), sl[24])
    print('연속 장 쌍:', n_pairs, ' 팔 ID 순서 같음:', round(order_same_arm / n_pairs, 4),
          ' 다리 ID 순서 같음:', round(order_same_leg / n_pairs, 4))
    print('길이 편차 |L/트랙중앙-1| (장×마디 관측값) 50/90/99%: 보정', q(dev), ' 보정없음', q(dev_noasp))
    print('  부호: 짧아짐(<-0.11)', round(sum(1 for x in sdev if x < -0.11) / len(sdev), 4),
          ' 늘어남(>+0.11)', round(sum(1 for x in sdev if x > 0.11) / len(sdev), 4))
    print('정지 비율(쌍): 화면 기준', round(hold_scr / n_pairs, 4), ' 골반 기준', round(hold_rel / n_pairs, 4))
    fs = [(a / t, b / t) for a, b, t in per_file.values() if t >= 20]
    for name, idx in (('화면', 0), ('골반', 1)):
        xs = sorted(x[idx] for x in fs)
        print(f'  파일별 {name} 정지 비율(20쌍 이상 파일 {len(xs)}개) 0/25/50/75/100%:',
              [round(xs[int(p * (len(xs) - 1))], 3) for p in (0, .25, .5, .75, 1)])
    print('장당 최대 관절 이동/몸통 50/90/99%: 화면', q(move), ' 골반 기준', q(relmove))
    big.sort(reverse=True)
    seen = set(); out = []
    for a, x, f, fr, sname in big:
        if (f, sname) in seen:
            continue
        seen.add((f, sname)); out.append((round(x, 2), f[-40:], fr, sname))
        if len(out) >= nsamp:
            break
    print('큰 편차 표본(파일·마디별 최대 1개):')
    for o in out:
        print('  ', o)

if __name__ == '__main__':
    n = 12
    if '--samples' in sys.argv:
        n = int(sys.argv[sys.argv.index('--samples') + 1])
    main(sys.argv[1], sys.argv[2], n)
