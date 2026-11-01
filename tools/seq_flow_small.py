"""작은 CPU 통합 시험(GPT 2라운드 4-2, 11-01): 네 해상도 단계·쉬운 것부터·끊고 재개·계획 연장·섞기 기록·판정 폭을
작은 자료 + 작은 모델로 수십 분 안에 실제 학습기(seq_train.train)로 확인한다. 시간 함수의 단위 시험과는 확인 범위가 다르다.

사용: python tools/seq_flow_small.py 작업폴더 [--plan 6]
  1) 자료: 단계마다 조합 문제 소수 장(1920·1280·854 영상, 640), 시험·위치 시험·종류별 검증 소수, 판정 자료(평가 목록 앞 2장으로 줄여 씀)
  2) 회차 1: 새로 시작, 계획 --plan 학습 진행 분, 벽시계 마감으로 도중에 끊김
  3) 회차 2: 이어서 계획 끝까지
  4) 회차 3: 계획 연장(--plan-minutes 늘림) — 360 단계·도달한 길이 분위 유지 확인
  5) 기록(log.jsonl·콘솔)으로 확인 항목을 판정해 결과 json을 남긴다.
작은 모델(resnet18, d 64, 1층)이라 성적은 보지 않는다. 경로·기록만 본다.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time

TOOLS = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable


def sh(cmd, log=None):
    print('$', cmd, flush=True)
    t = time.time()
    r = subprocess.run(cmd, shell=True, cwd=TOOLS, capture_output=True, text=True)
    out = r.stdout + r.stderr
    if log:
        with open(log, 'a', encoding='utf-8') as fh:
            fh.write(out)
    if r.returncode:
        print(out[-3000:])
        raise SystemExit(f'실패 rc {r.returncode}: {cmd}')
    print(f'  ({time.time() - t:.0f}초)', flush=True)
    return out


def build(root, n):
    d = {}
    for w in (1920, 1280, 854):
        d[f'sd{w}'] = f'{root}/sd{w}'
        if not os.path.exists(f'{d[f"sd{w}"]}/done.json'):
            sh(f'{PY} -u seq_data.py {d[f"sd{w}"]} --maxlen 2048 --compose {n} --W {w} --video --seed {w} --workers 4')
    jobs = dict(sd=f'--maxlen 2048 --compose {n} --seed 640 --workers 4',
                sv='--maxlen 2048 --max-frames 3 --every 8 --holdout --workers 4',
                ss='--maxlen 2048 --max-frames 2 --every 40 --fixed 6,4,1.05 --workers 4',
                sc='--maxlen 2048 --compose 30 --seed 7777 --workers 4')
    for k, args in jobs.items():
        d[k] = f'{root}/{k}'
        if not os.path.exists(f'{d[k]}/done.json'):
            sh(f'{PY} -u seq_data.py {d[k]} {args}')
    d['sj'] = f'{root}/sj'
    if not os.path.exists(f'{d["sj"]}/judge.npz'):
        sh(f'{PY} -u seq_judge.py build {d["sj"]}')
    return d


def session(d, out, minutes, plan, log):
    small = ('--d 64 --layers 1 --heads 2 --backbone resnet18 --max-batch 2 --tok-budget 2048 --val-n 8 --gen-n 1 --judge-n 2 '
             '--sheet-n 1 --val-minutes 1.5 --gen-minutes 3 --log-every 10 --final-reserve-min 0.5 --save-minutes 1')
    stages = ','.join(d[f'sd{w}'] for w in (1920, 1280, 854))
    sh(f'{PY} -u seq_train.py train {d["sd"]} {d["sv"]} {out} --minutes {minutes} --plan-minutes {plan} --shift-val {d["ss"]} '
       f'--judge {d["sj"]} --val-kind {d["sc"]} --stages {stages} {small}', log)


def check(out, console, plan, plan2):
    L = [json.loads(x) for x in open(f'{out}/log.jsonl', encoding='utf-8')]
    txt = open(console, encoding='utf-8').read()
    fin = [r for r in L if r.get('final')]
    c = {}
    trans = re.findall(r'해상도 단계 (\d+) → (\d+)폭', txt)
    c['단계 순서 1920→1280→854→640'] = trans[:3] == [('1920', '1280'), ('1280', '854'), ('854', '640')]
    ss = fin[-1]['stage_steps']
    c['네 단계 모두 업데이트'] = all(ss.get(str(w), 0) > 0 for w in (1920, 1280, 854, 640))
    starts = {}
    for w, q in re.findall(r'쉬운 것부터: (\d+)폭 정답 길이 하위 (\d+)%', txt):
        starts.setdefault(w, int(q))
    # 분위는 5% 칸 올림(cur_quantile) — 단계 진행이 0보다 조금이라도 크면 25%로 시작한다
    c['단계마다 하위 20–25%에서 시작'] = all(starts.get(str(w)) in (20, 25) for w in (1920, 1280, 854, 640))
    sel = fin[-1].get('sel', {})
    c['섞기 선택·성공 기록'] = any(k.endswith('|mix') and v[0] > 0 for k, v in sel.items())
    c['회차 1은 마감으로 끊김'] = fin[0].get('stop') == 'deadline' and fin[0]['train_min'] < plan
    c['회차 2는 계획 끝'] = len(fin) >= 2 and fin[1].get('stop') == 'plan' and fin[1].get('plan_reached') is True
    c['재개 때 학습 진행 이어받음'] = '이어하기' in txt and fin[1]['train_min'] > fin[0]['train_min']
    c['판정 폭이 단계 폭을 따라감'] = all(r.get('judge_w') in (1920, 1280, 854, 640) for r in L if 'judge_w' in r) and \
        any(r.get('judge_w', 640) != 640 for r in L)
    c['축소 목록이라 공식 아님'] = all(not r.get('judge_official') and not r.get('judge360_official') for r in L)
    if len(fin) >= 3:
        part3 = txt.split('이어하기')[-1]
        c['연장: 360 유지'] = '해상도 단계' not in part3 and fin[2]['stage_steps'].get('640', 0) > fin[1]['stage_steps'].get('640', 0)
        c['연장: 360 길이 분위 유지(100%)'] = fin[2].get('cur_max', {}).get('3') == 1.0 and '640폭 정답 길이 하위' not in part3
        c['연장: 계획'] = fin[2].get('plan_min') == plan2
    c['마지막 평가 예상 ≥ 실제(보수적)'] = all((r.get('final_est_sec') or 0) >= (r.get('final_sec') or 0) for r in fin)
    c['마감 안에 끝남'] = all((r.get('deadline_over_sec') or 0) <= 0 for r in fin)
    lost = [round(r['time_sec']['load'] + r['time_sec']['val'] + r['time_sec']['gen']) for r in fin]
    return c, dict(stage_steps=ss, sel=sel, cur_max=fin[-1].get('cur_max'), stops=[r.get('stop') for r in fin],
                   train_min=[round(r['train_min'], 2) for r in fin], wall_min=[round(r['minutes'], 2) for r in fin],
                   overhead_sec=lost, final_est_sec=[r.get('final_est_sec') for r in fin], final_sec=[r.get('final_sec') for r in fin],
                   deadline_over_sec=[r.get('deadline_over_sec') for r in fin])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('root')
    ap.add_argument('--n', type=int, default=40, help='단계마다 조합 문제 장 수')
    ap.add_argument('--plan', type=float, default=6, help='학습 진행 계획(분)')
    ap.add_argument('--first', type=float, default=6, help='회차 1 벽시계(분) — 계획보다 짧게 끊기게')
    a = ap.parse_args()
    os.makedirs(a.root, exist_ok=True)
    d = build(a.root, a.n)
    out, con = f'{a.root}/out', f'{a.root}/console.txt'
    for p in (out, con):
        if os.path.exists(p):
            subprocess.run(['rm', '-rf', p])
    session(d, out, a.first, a.plan, con)
    session(d, out, 60, a.plan, con)
    plan2 = a.plan * 1.5
    session(d, out, 60, plan2, con)
    c, info = check(out, con, a.plan, plan2)
    res = dict(checks=c, passed=all(c.values()), info=info)
    json.dump(res, open(f'{a.root}/result.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    for k, v in c.items():
        print(('통과 ' if v else '실패 ') + k)
    print(json.dumps(info, ensure_ascii=False))
    raise SystemExit(0 if res['passed'] else 1)


if __name__ == '__main__':
    main()
