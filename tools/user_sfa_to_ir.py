"""수집 SFA 뼈대(data/stickman_motion/user_sfa_skeletons_2026-10-28.jsonl) → 스틱맨 중간 표현(motion-ir/1) 구간들.
(2026-11-05 사용자 'ㄱㄱ': 학습 기본기 층 = 사람이 앱에서 만든 스틱맨 동작, 포즈 검출 오류 없음. 스타일 층은 nian41 자료.)

- 묶기: (파일, 몸통 객체 ID)별로 장 순서대로 잇고, 장 번호가 끊기거나 팔 2·다리 2(각 3점)가 아니면 구간을 나눈다. MIN_LEN장 미만 구간은 버린다.
- 유사 중복(similar_groups_2026-10-28.json): 묶음마다 표준 뼈대 장이 가장 많은 파일 하나만.
- 팔·다리 좌우: 원본은 좌우 구분이 없어 객체 ID 순서로 정한다(장 사이에는 같은 객체라 일정). 좌우 의미는 없다.
- 표시: source.reference=True(조건 29 ②, 참고용 — 생성은 항상 '우리 스타일'), source.animator='user_sfa'. 캐릭터 그림은 쓰지 않는다(조건 8, 뼈대만).
- 속도: tf_from_videos에 확정된 파일만 fps를 적고, 나머지는 null(장 순서로만 쓴다 — STICKMAN-MOTION 10-28).
사용: python tools/user_sfa_to_ir.py <출력 jsonl.gz>
"""
import gzip, json, os, sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SK = f'{ROOT}/data/stickman_motion/user_sfa_skeletons_2026-10-28.jsonl'
GROUPS = f'{ROOT}/data/stickman_motion/similar_groups_2026-10-28.json'
TF = f'{ROOT}/data/stickman_motion/tf_from_videos_2026-10-28.json'
MIN_LEN = 8   # 동작 구간 최소 장 수(12면 7,816장, 8이면 9,347장 — 중복 뺀 표준 뼈대 12,847장 중). 정지 포즈 학습은 짧은 구간 장도 쓸 수 있다
LINK = 2.0   # 객체 ID가 바뀐 장: 목 이동 < 몸통 2배면 같은 인물(같은 ID 이웃 장 목 이동 90분위 1.33 — 저장 장 수가 적어 크게 움직인다)
NAMES = ['head_t', 'head_b', 'neck', 'pelvis', 'elb_r', 'wri_r', 'elb_l', 'wri_l', 'kne_r', 'ank_r', 'kne_l', 'ank_l']


def joints_of(r):
    if len(r['arms']) != 2 or len(r['legs']) != 2: return None
    arms = sorted(r['arms'], key=lambda a: int(a[0])); legs = sorted(r['legs'], key=lambda a: int(a[0]))
    if any(len(a[1]) != 3 for a in arms + legs): return None
    return dict(head_t=r['head'][1], head_b=r['head'][0], neck=r['neck'], pelvis=r['hip'],
                elb_r=arms[0][1][1], wri_r=arms[0][1][2], elb_l=arms[1][1][1], wri_l=arms[1][1][2],
                kne_r=legs[0][1][1], ank_r=legs[0][1][2], kne_l=legs[1][1][1], ank_l=legs[1][1][2])


def build():
    rows = [json.loads(l) for l in open(SK, encoding='utf-8')]
    per_file = defaultdict(int)
    for r in rows:
        if joints_of(r): per_file[r['file']] += 1
    drop = set()
    for g in json.load(open(GROUPS, encoding='utf-8')):
        keep = max(g, key=lambda f: per_file.get(f, 0))
        drop |= set(g) - {keep}
    fps = {}
    for t in json.load(open(TF, encoding='utf-8')):
        if t.get('state') == '확정': fps.setdefault(t['file'], [t['T'], t['F']])
    # 추적: 같은 파일 안에서 장마다 인물(뼈대)을 앞 장 인물과 목 거리로 잇는다(몸통 객체 ID는 그림을 다시 그리면 바뀐다 —
    # ID로만 이으면 표준 뼈대 20,311장 중 7,176장만 12장 이상 구간에 남았다, 11-05)
    byfile = defaultdict(lambda: defaultdict(list))
    for r in rows:
        if r['file'] in drop: continue
        j = joints_of(r)
        if j: byfile[r['file']][r['frame']].append((r, j))
    out = []
    def dist(a, b, hwr):
        return ((a[0] - b[0]) ** 2 + ((a[1] - b[1]) * hwr) ** 2) ** 0.5
    for f, frs in byfile.items():
        tracks = []   # [(마지막 장, [(r, j)...])]
        for n in sorted(frs):
            used, todo = set(), []
            for r, j in frs[n]:            # 1) 같은 몸통 객체 ID면 잇는다
                ti = next((i for i, (last, run) in enumerate(tracks) if i not in used and last == n - 1 and run[-1][0]['fig'] == r['fig']), None)
                if ti is None: todo.append((r, j)); continue
                tracks[ti][0] = n; tracks[ti][1].append((r, j)); used.add(ti)
            for r, j in todo:              # 2) ID가 바뀌었으면 끊긴 트랙 중 목이 가장 가까운 것(몸통 LINK배 이내)
                hwr = float(r['hwr']); tor = dist(j['neck'], j['pelvis'], hwr) or 1.0
                cand = [(dist(run[-1][1]['neck'], j['neck'], hwr), i) for i, (last, run) in enumerate(tracks) if i not in used and last == n - 1]
                cand = [c for c in cand if c[0] < LINK * tor]
                if cand:
                    ti = min(cand)[1]; tracks[ti][0] = n; tracks[ti][1].append((r, j)); used.add(ti)
                else:
                    tracks.append([n, [(r, j)]]); used.add(len(tracks) - 1)
        for _, run in tracks:
            if len(run) < MIN_LEN: continue
            N = len(run)
            J = {k: [list(map(float, j[k])) for _, j in run] for k in NAMES}
            out.append(dict(schema='motion-ir/1', fps=fps.get(f), aspect=float(run[0][0]['hwr']), frames=N,
                            actors=[dict(slot=0, color='blue', joints=J, thickness=[{} for _ in range(N)],
                                         hidden=[[] for _ in range(N)], smear=[[] for _ in range(N)],
                                         head_fill=[True] * N, facing=[None] * N)],
                            camera=[[0.0, 0.0, 1.0] for _ in range(N)], timeline=[],
                            source=dict(animator='user_sfa', reference=True, file=f, figs=sorted({r['fig'] for r, _ in run}),
                                        start=run[0][0]['frame'], end=run[-1][0]['frame'],
                                        note='참고용(조건 29 ②) — 뼈대만, 좌우는 객체 ID 순서(객체가 바뀐 장에서 뒤바뀔 수 있음)')))
    return out, len(drop)


if __name__ == '__main__':
    segs, ndrop = build()
    with gzip.open(sys.argv[1], 'wt', encoding='utf-8') as g:
        for s in segs: g.write(json.dumps(s, ensure_ascii=False) + '\n')
    files = {s['source']['file'] for s in segs}
    print('구간', len(segs), '장', sum(s['frames'] for s in segs), '파일', len(files), '중복으로 뺀 파일', ndrop,
          'fps 확정 구간', sum(1 for s in segs if s['fps']))
