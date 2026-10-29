#!/usr/bin/env python3
"""Kaggle 작업자: 영상 → SFA 딥러닝(자료 만들기 → 짧은 시험 → 본 학습 → 결과 zip·Drive) (2026-10-29).
저장소(공개)에서 SFA 파일과 도구를 받는다. 4711_2 합작 28개는 학습에서 빠진다(vec_data.HOLDOUT, 최종 시험용).
"""
import argparse
import os
import shutil
import subprocess
import sys
import time


def sh(cmd):
    print('$', cmd, flush=True)
    subprocess.run(cmd, shell=True, check=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--branch', default='ccr-bccf15a6-d6ee46')
    ap.add_argument('--hours', type=float, default=4.0)
    ap.add_argument('--repeat', type=int, default=2)
    ap.add_argument('--max-frames', type=int, default=24)
    ap.add_argument('--out', default='/kaggle/working')
    a = ap.parse_args()
    t0 = time.time()
    sh('pip install -q skia-python')
    if not os.path.isdir('/kaggle/tmp/AI-sfa'):
        sh(f'git clone -q --depth 1 -b {a.branch} https://github.com/twoapple08/AI-sfa /kaggle/tmp/AI-sfa')
    tools = '/kaggle/tmp/AI-sfa/tools'
    data = '/kaggle/tmp/vd'
    cpus = os.cpu_count() or 4
    def gen(res):
        d = os.path.join(data, res)
        if os.path.exists(os.path.join(d, '_done.json')):  # 다 만든 표시(GPT 검토 17)
            return
        rep = 1 if res in ('1920', '1280') else a.repeat
        sh(f'cd {tools} && python -u vec_data.py {d} --res {res} --repeat {rep} --max-frames {a.max_frames} --workers {cpus} --seed {res}')
    out = os.path.join(a.out, 'vec_out')
    # 1080 자료만 먼저 → 짧은 시험(문법·GPU 메모리; 서버에 torch가 없어 여기서 처음 돈다) → 나머지 자료 → 본 학습
    gen('1920')
    sh(f'cd {tools} && python -u vec_train.py --data {data} --out /kaggle/tmp/smoke --smoke --workers 2')
    for res in ('1280', '854', '640'):  # 커리큘럼 단계별 자료(사용자 10-29)
        gen(res)
    sh(f'du -sh {data}/*')
    print(f'자료 만들기·시험 {(time.time() - t0) / 60:.1f}분', flush=True)
    import torch
    if not torch.cuda.is_available():  # GPU 시간이 없을 때: 자료·짧은 시험까지만 확인하고 멈춤(사용자 10-29, Kaggle GPU 0시간)
        print('GPU 없음 → 자료 만들기와 짧은 시험까지만 확인하고 멈춥니다. 오류 없이 여기까지 왔으면 GPU 시간이 돌아왔을 때 그대로 다시 실행하면 됩니다.', flush=True)
        return
    sh(f'cd {tools} && python -u vec_train.py --data {data} --out {out} --hours {a.hours} --workers {max(2, cpus - 1)}')
    shutil.copy(os.path.join(tools, 'vec_train.py'), out)
    sh(f'cd {a.out} && zip -qr vec_out.zip vec_out')
    if shutil.which('rclone'):
        try:
            sh(f'rclone copy {a.out}/vec_out.zip "gdrive:AI-sfa/02_분석자료/vec/" -P')
        except Exception as e:
            print('Drive 올리기 실패(Output 탭에서 받기):', e)
    print(f'전체 {(time.time() - t0) / 60:.1f}분', flush=True)


if __name__ == '__main__':
    main()
