"""자동 탐지(auto_detect.py) 결과를 기존 사람·AI 판정과 대조해 개념별 신뢰도를 잰다.

사용: python tools/auto_calibrate.py <탐지 폴더> <출력 csv> [all|gpt|claude]
정답: data/style_kb/action_counts/*.csv(Claude), ai_results/gpt_G0*.csv(GPT). 영상 단위로 '나옴/안 나옴'을 만든다.
  gpt: GPT만 정답으로 쓴다. G07·G08은 이펙트·연출만 판정했으므로 동작 개념에서는 뺀다.
  claude: Claude 124개만. 이펙트 칸이 비어 있는 경우가 많아 이펙트 개념의 음성이 부풀려진다.
점수(2026-10-21 수정): 나온 시간 비율 = 0.5초 프레임별 태그 확률(개념 내 최대)의 평균(기대 시간 비율).
  고정 임계(0.05–0.35) 이상 프레임 비율도 비교했으나 드문 태그는 대부분 0이 되어 AUC가 떨어졌다.
  비교용으로 예전 점수(상위 5% 확률)의 AUC도 함께 적는다.
  흑백 임팩트는 태그 대신 cv 지표(0.125초 간 밝기 급변 최대값과 주변 대비 채도 최저비의 순위 평균)로 잰다.
출력: 개념, 정답원, 정답 양성 수, 음성 수, AUC(예전), AUC(시간 비율), 최적 영상 임계(비율), 정밀도, 재현율
"""
import csv
import glob
import json
import os
import re
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
from auto_detect import TAGS  # noqa: E402

KB = os.path.join(os.path.dirname(__file__), '..', 'data', 'style_kb')
ACTION = {'검', '총', '주먹', '발차기', '점프·공중', '질주·대시', '비행', '메카·로봇'}
EFFECT_ONLY = {'G07', 'G08'}

# 개념: (정답 키워드 정규식, 태그 목록)
CONCEPTS = {
    '폭발': (r'폭발', ['explosion']),
    '화염': (r'화염|불길|불꽃(?! 튐)|불바다|불타|화재', ['fire', 'burning', 'blue_fire']),
    '연기': (r'연기|흑연', ['smoke']),
    '번개·전격': (r'번개|전격|전기', ['lightning', 'electricity']),
    '광선': (r'광선|빔|레이저', ['energy_beam', 'laser']),
    '오라': (r'오라', ['aura']),
    '마법진·문양': (r'마법진|문양', ['magic_circle']),
    '파편': (r'파편|잔해', ['debris', 'rubble']),
    '분진': (r'분진|먼지|흙먼지', ['dust', 'dust_cloud']),
    '출혈': (r'출혈|피 |피$|혈흔|피가|핏', ['blood', 'blood_splatter']),
    '비·눈': (r'비·눈|눈가루|빗|눈발|강설|강우', ['rain', 'snow']),
    '물보라': (r'물보라|물기둥|물결|파도|수면', ['water', 'splashing']),
    '스미어': (r'스미어', ['motion_blur']),
    '속도선': (r'속도선', ['speed_lines', 'motion_lines']),
    '잔상': (r'잔상|분신', ['afterimage']),
    '불꽃 튐': (r'불꽃 튐|불티|스파크', ['sparks']),
    '검': (r'(^|[^가-힣])검($|[^광격은을])|칼|참격|검격', ['sword', 'katana', 'holding_sword', 'slashing']),
    '총': (r'총|사격|포탑|포구', ['gun', 'handgun', 'rifle', 'firing', 'muzzle_flash']),
    '주먹': (r'주먹', ['punching']),
    '발차기': (r'발차기', ['kicking']),
    '점프·공중': (r'점프|공중동작|도약', ['jumping', 'midair']),
    '질주·대시': (r'질주|대시|돌진', ['running']),
    '비행': (r'비행', ['flying', 'wings']),
    '메카·로봇': (r'기체|메카|로봇', ['mecha', 'robot']),
    '흑백 임팩트': (r'흑백|명암 반전|임팩트프레임', ['monochrome', 'greyscale']),
}


def truth(src='all', groups=False):
    """post_id -> 판정 글. groups=True면 (글, 묶음 집합)을 돌려준다."""
    lab, grp = {}, {}
    files = []
    if src in ('all', 'claude'):
        files += glob.glob(os.path.join(KB, 'action_counts', '[0-9]*.csv'))
    if src in ('all', 'gpt'):
        files += glob.glob(os.path.join(KB, 'ai_results', 'gpt_G0*.csv'))
    for f in files:
        for r in csv.DictReader(open(f, encoding='utf-8-sig')):
            txt = ' '.join(v for k, v in r.items() if k not in ('묶음', 'post_id', '시간구간', '길이초', '움직임점수') and v)
            lab.setdefault(r['post_id'], []).append(txt)
            grp.setdefault(r['post_id'], set()).add(r['묶음'][:3])
    lab = {p: ' '.join(t) for p, t in lab.items()}
    return (lab, grp) if groups else lab


def score_top(d, tags):
    ix = [TAGS.index(t) for t in tags]
    a = np.array(d['tags'])[:, ix].max(1)
    return float(np.quantile(a, 0.95)) if len(a) else 0.0


def score(d, tags):
    """기대 나온 시간 비율(프레임 확률 평균)."""
    ix = [TAGS.index(t) for t in tags]
    a = np.array(d['tags'])[:, ix].max(1)
    return float(a.mean()) if len(a) else 0.0


def mono_feats(cv):
    """흑백 임팩트 지표: (밝기 급변 최대, 주변 대비 채도 최저비의 음수)."""
    c = np.array(cv, float)
    if len(c) < 3:
        return 0.0, 0.0
    b, s = c[:, 0], c[:, 1]
    med = np.array([np.median(s[max(0, i - 8):i + 9]) for i in range(len(s))])
    return float(np.abs(np.diff(b)).max()), float(-(s / (med + 1)).min())


def rank(x):
    x = np.asarray(x, float)
    return np.argsort(np.argsort(x)) / max(len(x) - 1, 1)


def mono_scores(ds):
    f = np.array([mono_feats(d['cv']) for d in ds])
    return list((rank(f[:, 0]) + rank(f[:, 1])) / 2) if len(f) else []


def auc(pos, neg):
    if not pos or not neg:
        return float('nan')
    p, n = np.array(pos), np.array(neg)
    return float(((p[:, None] > n[None]).sum() + 0.5 * (p[:, None] == n[None]).sum()) / (len(p) * len(n)))


def main():
    det, out = sys.argv[1:3]
    src = sys.argv[3] if len(sys.argv) > 3 else 'all'
    lab, grp = truth(src, groups=True)
    D = {os.path.basename(f)[:-5]: json.load(open(f)) for f in glob.glob(os.path.join(det, '*.json'))}
    common = sorted(p for p in D if p in lab and D[p]['tags'])
    rows = []
    for c, (rx, tags) in CONCEPTS.items():
        use = [p for p in common if not (c in ACTION and grp[p] <= EFFECT_ONLY)]
        y = [bool(re.search(rx, lab[p])) for p in use]
        old = [score_top(D[p], tags) for p in use]
        s = mono_scores([D[p] for p in use]) if c == '흑백 임팩트' else [score(D[p], tags) for p in use]
        pos = [a for a, b in zip(s, y) if b]
        neg = [a for a, b in zip(s, y) if not b]
        a_old = auc([a for a, b in zip(old, y) if b], [a for a, b in zip(old, y) if not b])
        best = (0, 0, 0, 0)
        for th in sorted(set(s)):
            tp = sum(a >= th and b for a, b in zip(s, y))
            fp = sum(a >= th and not b for a, b in zip(s, y))
            fn = sum(a < th and b for a, b in zip(s, y))
            pr = tp / (tp + fp) if tp + fp else 0
            rc = tp / (tp + fn) if tp + fn else 0
            f1 = 2 * pr * rc / (pr + rc) if pr + rc else 0
            if f1 > best[0]:
                best = (f1, th, pr, rc)
        rows.append([c, src, len(pos), len(neg), f'{a_old:.2f}', f'{auc(pos, neg):.2f}', f'{best[1]:.3f}', f'{best[2]:.2f}', f'{best[3]:.2f}'])
    with open(out, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['개념', '정답원', '정답_있음', '정답_없음', 'AUC_예전', 'AUC_시간비율', '영상임계', '정밀도', '재현율'])
        w.writerows(rows)
    print('영상', len(common))
    for r in rows:
        print(*r)


if __name__ == '__main__':
    main()
