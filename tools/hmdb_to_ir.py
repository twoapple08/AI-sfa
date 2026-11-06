"""공개 2D 관절 자료 HMDB51(MMAction2 hmdb51_2d.pkl, HRNet COCO 17점, 320×240, 30fps) → 기본기 층(참고) 동작 자료(motion-ir/1).
(11-06 사용자: SFA를 더 모으기 어렵다 → "걷기 조각이 필요하면 다른 클립에서 끌어다 쓸 수는 없어?" → "그냥 바로 가자".
 nian41·나카무라 영상은 싸움 작화 모음이라 실제 걷기·달리기 8구간뿐. 스타일 규칙(몸동작 = nian41·나카무라)은 그대로 두고 참고 층에만 넣는다.)

- 내려받은 pkl은 신뢰할 수 없는 자료라 숫자·배열 말고는 거부하는 제한 로더로만 연다(safe_load).
- 동작 종류(CLASSES)만: 걷기·달리기·점프·킥·펀치·넘어짐·서기·몸 돌리기·공중제비·옆돌기·때리기·던지기·앉기.
- 사람: 평균 점수가 가장 높은 사람 하나. 장마다 몸통(어깨·골반 4점) 점수 ≥ MIN_TORSO, 다리 동작(걷기·달리기 등)은 발목 점수 ≥ MIN_LEG도.
  조건을 만족하는 연속 구간이 MIN_RUN장(24fps 기준) 이상인 것만, 가장 긴 구간 하나.
- 관절: 목 = 두 어깨 가운데, 골반 = 두 엉덩이 가운데, 팔꿈치·손목·무릎·발목 그대로(COCO 오른쪽 = _r).
  머리: 방향 = (두 귀 또는 두 눈 가운데) − 목, 길이는 몸통 배율(수집 SFA·추출 통계: 머리 위 0.69·머리 아래 0.13 몸통).
- 30fps → 24fps 직선 보간, 3장 이동 평균으로 검출 떨림만 줄임. 좌표 = 16:9 화면 %(stage2_extract.to_pct와 같은 방식).
출력: jsonl.gz(한 줄 = 한 클립 ir, source.dataset='hmdb51', reference=True, verb, label). 원본 관절 좌표는 공개 저장소에 넣지 않는다(비공개 작업 폴더·Drive).
사용: python -I tools/hmdb_to_ir.py <hmdb51_2d.pkl> <출력.jsonl.gz>  (-I: 내려받은 폴더의 파일을 불러오지 않게)
"""
import gzip, json, math, os, pickle, sys
import numpy as np

HMDB = ['brush_hair', 'cartwheel', 'catch', 'chew', 'clap', 'climb', 'climb_stairs', 'dive', 'draw_sword', 'dribble', 'drink', 'eat',
        'fall_floor', 'fencing', 'flic_flac', 'golf', 'handstand', 'hit', 'hug', 'jump', 'kick', 'kick_ball', 'kiss', 'laugh', 'pick',
        'pour', 'pullup', 'punch', 'push', 'pushup', 'ride_bike', 'ride_horse', 'run', 'shake_hands', 'shoot_ball', 'shoot_bow',
        'shoot_gun', 'sit', 'situp', 'smile', 'smoke', 'somersault', 'stand', 'swing_baseball', 'sword', 'sword_exercise', 'talk',
        'throw', 'turn', 'walk', 'wave']
# 영어 이름 → (동사, 설명, 다리가 보여야 하는가)
CLASSES = {
    'walk': ('걷기', '몸을 세우고 발을 번갈아 내딛으며 걷는다.', 'gait'),
    'run': ('달리기', '몸을 앞으로 기울이고 팔다리를 번갈아 크게 움직이며 달린다.', 'gait'),
    'jump': ('점프', '무릎을 굽혔다 펴며 몸을 띄운다.', True),
    'kick': ('킥', '한 다리를 들어 앞으로 뻗어 찬다.', True),
    'punch': ('펀치', '한 팔을 앞으로 곧게 뻗어 친다.', False),
    'fall_floor': ('넘어짐', '몸이 기울며 바닥으로 넘어진다.', False),
    'stand': ('일어남', '앉거나 낮춘 몸을 펴며 일어선다.', True),
    'turn': ('몸 돌리기', '선 채로 몸을 돌려 방향을 바꾼다.', True),
    'somersault': ('구르기', '몸을 말아 앞으로 돈다.', False),
    'cartwheel': ('몸 돌리기', '두 손을 짚고 다리를 넘기며 옆으로 돈다.', False),
    'hit': ('때리기', '팔을 휘둘러 상대를 친다.', False),
    'throw': ('던지기', '팔을 뒤로 뺐다가 앞으로 휘둘러 던진다.', False),
    'sit': ('앉기', '무릎을 굽혀 몸을 낮추며 앉는다.', True),
}
MIN_TORSO, MIN_LEG, MIN_RUN = 0.35, 0.3, 16
# 11-06 눈 확인 뒤 강화: 다리 안 보이는 펀치에서 지어낸 다리가 접힘 → 모든 동작에 다리 요구 · 다리 길이 ≥ 0.5 몸통,
# 사람 크기(몸통 ≥ 화면 높이 MIN_SIZE), 걷기·달리기는 두 발이 번갈아 앞서는 걸음 MIN_STEPS 이상(정면으로 걸어오는 클립은 다리 움직임이 안 보임)
MIN_SIZE, MIN_LEGLEN, MIN_STEPS, STEP_AMP = 0.12, 0.5, 2, 0.25
ALLOW = {('numpy.core.multiarray', '_reconstruct'), ('numpy._core.multiarray', '_reconstruct'), ('numpy', 'ndarray'), ('numpy', 'dtype'),
         ('numpy.core.multiarray', 'scalar'), ('numpy._core.multiarray', 'scalar'), ('collections', 'OrderedDict'), ('_codecs', 'encode')}


class _Safe(pickle.Unpickler):
    def find_class(self, mod, name):
        if (mod, name) in ALLOW: return super().find_class(mod, name)
        raise pickle.UnpicklingError(f'허용하지 않는 객체 {mod}.{name}')


def safe_load(p):
    with open(p, 'rb') as f: return _Safe(f).load()


def to_pct(x, y, W=320, H=240):
    vis_h = W * 0.5625
    return [float(x) / W * 100, float(y - (H - vis_h) / 2) / vis_h * 100]


def convert(ann, legs):
    K, S = ann['keypoint'], ann['keypoint_score']
    if K.shape[0] == 0: return None
    p = int(np.argmax(S.mean(axis=(1, 2)))); K, S = K[p].astype(float), S[p].astype(float)
    H, W = ann.get('img_shape', (240, 320))
    T = K.shape[0]
    # 30fps → 24fps
    t24 = np.arange(0, (T - 1) / 30 + 1e-9, 1 / 24) * 30
    i0 = np.floor(t24).astype(int); i1 = np.minimum(i0 + 1, T - 1); w = (t24 - i0)[:, None, None]
    K = K[i0] * (1 - w) + K[i1] * w; S = np.minimum(S[i0], S[i1])
    ok = S[:, [5, 6, 11, 12]].min(1) >= MIN_TORSO
    ok &= S[:, [13, 14, 15, 16]].min(1) >= MIN_LEG
    tor0 = np.linalg.norm((K[:, 5] + K[:, 6]) / 2 - (K[:, 11] + K[:, 12]) / 2, axis=1) + 1e-6
    ok &= tor0 >= MIN_SIZE * H
    for h_, k_, a_ in ((12, 14, 16), (11, 13, 15)):
        ok &= (np.linalg.norm(K[:, k_] - K[:, h_], axis=1) + np.linalg.norm(K[:, a_] - K[:, k_], axis=1)) >= MIN_LEGLEN * 2 * tor0
    best, i = (0, 0), 0
    while i < len(ok):
        if not ok[i]: i += 1; continue
        j = i
        while j < len(ok) and ok[j]: j += 1
        if j - i > best[1] - best[0]: best = (i, j)
        i = j
    a, b = best
    if b - a < MIN_RUN: return None
    K = K[a:b]
    if legs == 'gait':   # 걸음 번갈이: (왼발목 x − 오른발목 x)/몸통 부호가 진폭 STEP_AMP 이상으로 바뀐 횟수
        tg = np.linalg.norm((K[:, 5] + K[:, 6]) / 2 - (K[:, 11] + K[:, 12]) / 2, axis=1) + 1e-6
        d = (K[:, 15, 0] - K[:, 16, 0]) / tg; steps = sign = 0
        for x in d:
            if abs(x) < STEP_AMP: continue
            sg = 1 if x > 0 else -1
            if sign and sg != sign: steps += 1
            sign = sg
        if steps < MIN_STEPS: return None
    Kp = np.concatenate([K[:1], K, K[-1:]]); K = (Kp[:-2] + Kp[1:-1] + Kp[2:]) / 3   # 3장 이동 평균
    N = len(K)
    neck = (K[:, 5] + K[:, 6]) / 2; pel = (K[:, 11] + K[:, 12]) / 2
    tor = np.linalg.norm(neck - pel, axis=1) + 1e-6
    headc = np.where((S[a:b, [3, 4]].min(1) >= 0.3)[:, None], (K[:, 3] + K[:, 4]) / 2, (K[:, 1] + K[:, 2]) / 2)
    u = headc - neck; u = u / (np.linalg.norm(u, axis=1, keepdims=True) + 1e-6)
    J = {'neck': neck, 'pelvis': pel, 'head_t': neck + 0.69 * tor[:, None] * u, 'head_b': neck + 0.13 * tor[:, None] * u,
         'elb_r': K[:, 8], 'wri_r': K[:, 10], 'elb_l': K[:, 7], 'wri_l': K[:, 9],
         'kne_r': K[:, 14], 'ank_r': K[:, 16], 'kne_l': K[:, 13], 'ank_l': K[:, 15]}
    joints = {k: [to_pct(x, y, W, H) for x, y in v] for k, v in J.items()}
    return dict(schema='motion-ir/1', fps=[24, 24], aspect=0.5625, frames=N,
                actors=[dict(slot=0, color='blue', joints=joints, thickness=[{} for _ in range(N)], hidden=[[] for _ in range(N)],
                             smear=[[] for _ in range(N)], head_fill=[True] * N, facing=[None] * N, train_mask=[True] * N)],
                source=dict(dataset='hmdb51', clip=ann['frame_dir'], reference=True, auto=True))


def main(pkl, outp):
    d = safe_load(pkl); n = 0; per = {}
    with gzip.open(outp, 'wt', encoding='utf-8') as f:
        for ann in d['annotations']:
            name = HMDB[int(ann['label'])]
            if name not in CLASSES: continue
            verb, detail, legs = CLASSES[name]
            ir = convert(ann, legs)
            if ir is None: continue
            ir['source'].update(label=name, verb=verb, detail=detail)
            f.write(json.dumps(ir, ensure_ascii=False) + '\n'); n += 1; per[name] = per.get(name, 0) + 1
    print('클립', n, per)


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
