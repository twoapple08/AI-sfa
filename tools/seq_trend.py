#!/usr/bin/env python3
"""학습 추세 보기(2026-11-01): log.jsonl(회차를 이어도 한 파일에 쌓인다) → '외우는가, 보고 판단하며 크는가' 표.
사용: python seq_trend.py log.jsonl [--md 결과.md]

보는 것(미리 정함, 판정 기준 §2와 같은 이름):
- 위치 읽기: 입력 교환 승수(공식 46개 중 31승이면 통과)와 Δ 중앙값이 오르는가.
- 외움보다 나은가: A(옮긴 정답 점수) − 외움 기준선이 0보다 크고 오르는가. B(원래 자리)만 오르면 외우는 쪽.
- 새 작품: 시험 파일(학습에 없던 작품) 생성 부분 점수가 오르는가 — 외워서는 오를 수 없는 점수.
- 건전성: 빈 출력·미완료가 한도 안인가.
연습 점수(구조·좌표·첫 점·이어지는 점)는 교사 강제 값이라 참고.
"""
import argparse
import json


def f(v, n=1, pct=False):
    if v is None:
        return '-'
    return f'{v * 100:.{n}f}' if pct else f'{v:.{n}f}'


def rows_of(path):
    out = []
    for line in open(path, encoding='utf-8'):
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if 'judge_N' in r or 'gen_partial' in r:
            out.append(r)
    return out


def table(rows):
    head = ['분', '걸음', '단계폭', '위치 읽기(승/N, 필요)', 'Δ중앙', 'A', 'B', '외움', 'A−외움', '새 작품 부분', '새 작품 F1', '건전성', '첫 점', '이어지는 점']
    lines = ['| ' + ' | '.join(head) + ' |', '|' + '---|' * len(head)]
    for r in rows:
        rc, pr = r.get('gen_recall'), r.get('gen_precision')
        gf1 = 2 * rc * pr / (rc + pr) if rc is not None and pr and rc + pr else (0.0 if rc is not None else None)
        win = (f"{r.get('judge_win')}/{r.get('judge_N')}({r.get('judge_need')})" + (' 통과' if r.get('judge_passed_all', r.get('judge_passed') and r.get('judge_health_passed')) else '')
               + (f" @{r['judge_w']}" if r.get('judge_w') else '')) if r.get('judge_N') else '-'
        if r.get('judge360_N'):
            win += f" · 360폭 {r.get('judge360_win')}/{r.get('judge360_N')}" + (' 통과' if r.get('judge360_passed_all', r.get('judge360_passed') and r.get('judge360_health_passed')) else '')
        hp = r.get('judge_health_passed')
        lines.append('| ' + ' | '.join([
            f(r.get('minutes'), 0), str(r.get('step', '-')), str(r.get('stage_w', '마지막' if r.get('final') else '-')), win,
            f(r.get('judge_delta_median'), 2), f(r.get('judge_A')), f(r.get('judge_B')), f(r.get('judge_memo')), f(r.get('judge_A_minus_memo')),
            f(r.get('gen_partial'), 1, True), f(gf1, 1, True), '-' if hp is None else ('통과' if hp else '미통과'),
            f(r.get('val_coord_first')), f(r.get('val_coord_rest'))]) + ' |')
    return '\n'.join(lines)


def verdict(rows):
    j = [r for r in rows if r.get('judge_N')]
    if len(j) < 2:
        return '판정 기록이 2번 미만 — 추세를 말할 수 없음'
    a, b = j[0], j[-1]
    out = []

    def d(k):
        return None if a.get(k) is None or b.get(k) is None else b[k] - a[k]
    out.append(f"위치 읽기 승수 {a.get('judge_win')} → {b.get('judge_win')} (필요 {b.get('judge_need')}), Δ중앙 {f(a.get('judge_delta_median'), 2)} → {f(b.get('judge_delta_median'), 2)}")
    out.append(f"A−외움 {f(a.get('judge_A_minus_memo'))} → {f(b.get('judge_A_minus_memo'))}, B {f(a.get('judge_B'))} → {f(b.get('judge_B'))}")
    g = [r for r in rows if r.get('gen_partial') is not None]
    if len(g) >= 2:
        out.append(f"새 작품 부분 점수 {f(g[0]['gen_partial'], 1, True)} → {f(g[-1]['gen_partial'], 1, True)}")
    sig = []
    if (d('judge_win') or 0) > 0 and (d('judge_delta_median') or 0) > 0:
        sig.append('위치를 더 읽음')
    if b.get('judge_A_minus_memo') is not None and b['judge_A_minus_memo'] > 0 and (d('judge_A_minus_memo') or 0) > 0:
        sig.append('외움보다 낫고 벌어짐')
    if len(g) >= 2 and g[-1]['gen_partial'] > g[0]['gen_partial']:
        sig.append('새 작품 점수 오름')
    if (d('judge_B') or 0) > 0 and (d('judge_A') or 0) <= 0:
        sig.append('주의: 원래 자리 점수만 오름(외우는 쪽)')
    out.append('신호(참고, 공식 판정은 판정 기준 §2): ' + (', '.join(sig) if sig else '뚜렷한 성장 신호 없음'))
    return '\n'.join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('log')
    ap.add_argument('--md', default='')
    a = ap.parse_args()
    rows = rows_of(a.log)
    txt = table(rows) + '\n\n' + verdict(rows)
    print(txt)
    if a.md:
        with open(a.md, 'w', encoding='utf-8') as fh:
            fh.write(txt + '\n')


if __name__ == '__main__':
    main()
