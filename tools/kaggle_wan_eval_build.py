"""Kaggle 노트북(나카무라 Wan LoRA 평가 영상 16개)을 만든다 (2026-10-28).

출력: tools/kaggle_wan_eval.ipynb — tools/kaggle_wan_eval_worker.py 본문을 넣어 둔다.
Drive 업로드는 Kaggle 비밀값 RCLONE_GDRIVE_AUTH_B64가 있을 때만(kaggle_build.py와 같은 방식). 없으면 Output 탭에 결과 zip이 남는다.
"""
import json
import os

from colab_p1_build import ROOT, code, md


DRIVE_CELL = """
# 1. (선택) Drive 연결 — 비밀값이 없으면 건너뛴다. 인증값은 출력하지 않는다
import os, json, base64, pathlib, subprocess
try:
    from kaggle_secrets import UserSecretsClient
    raw = UserSecretsClient().get_secret('RCLONE_GDRIVE_AUTH_B64').strip()
    d = json.loads(base64.b64decode(raw + '=' * (-len(raw) % 4)))
    p = pathlib.Path.home() / '.config/rclone'; p.mkdir(parents=True, exist_ok=True)
    lines = ['[gdrive]', 'type = drive', 'scope = drive.readonly,drive.file']
    if d.get('client_id'): lines.append('client_id = ' + d['client_id'])
    if d.get('client_secret'): lines.append('client_secret = ' + d['client_secret'])
    lines.append('token = ' + d['token'])
    (p / 'rclone.conf').write_text('\\n'.join(lines) + '\\n'); os.chmod(p / 'rclone.conf', 0o600)
    del raw, d, lines
    subprocess.run('cd /tmp && curl -sSLo rc.zip https://downloads.rclone.org/rclone-current-linux-amd64.zip && unzip -qo rc.zip && cp rclone-*/rclone /usr/local/bin/', shell=True, check=True)
    print('Drive 연결됨')
except Exception as e:
    print('Drive 연결 없이 진행(결과는 Output 탭):', type(e).__name__)
"""


def notebook(intro, worker_rel, run_args, out_rel, step_note):
    worker = open(os.path.join(ROOT, worker_rel), encoding="utf-8").read()
    name = os.path.basename(worker_rel)
    cells = [md(intro), code(DRIVE_CELL), code("""
# 2. 작업자 파일 쓰기 → 실행(%s)
open('/tmp/%s', 'w', encoding='utf-8').write(%s)
!python -u /tmp/%s %s
""" % (step_note, name, json.dumps(worker, ensure_ascii=False), name, run_args))]
    nb = {"cells": cells, "metadata": {"kernelspec": {"name": "python3", "display_name": "Python 3"},
                                       "language_info": {"name": "python"}},
          "nbformat": 4, "nbformat_minor": 4}
    p = os.path.join(ROOT, out_rel)
    json.dump(nb, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("→", p)


SETUP_MD = """
**설정:**
1. **Settings → Accelerator → GPU T4 x2**
2. **Settings → Internet → On**
3. (선택) **Add-ons → Secrets**에 `RCLONE_GDRIVE_AUTH_B64`를 붙이면 결과가 Drive `AI-sfa/02_분석자료/WanLoRA_평가/`로 올라간다. 없으면 Output 탭에서 받는다.
"""


def build():
    notebook("""
# AI-sfa 나카무라 Wan LoRA 평가 2판 — Kaggle GPU

PC방 학습 결과(LoRA 3000스텝)로 비교 영상 16개를 만든다: 프롬프트 4개 × (LoRA 세기 0.6 · 0.8 · 1.0 · 1.0+인물 빼기).
**2판(10-28 저녁):** 1판은 프롬프트 해석기(T5)를 fp16으로 돌려 PC 결과와 구도부터 달랐다 → T5를 PC와 같은 bf16으로.
먼저 p1·p2를 PC와 같은 조건으로 다시 만들어 PC 영상과 비교(재현 확인)한 뒤 16개를 만든다.
모델은 HuggingFace, LoRA·PC 영상은 Drive 공유 링크에서 노트북이 직접 받는다.

""" + SETUP_MD + """
**실행:** 오른쪽 위 **Save Version → Save & Run All (Commit)** — 브라우저를 닫아도 돈다. 예상 40–80분(추정, bf16 쪽이 느림).
결과 `wan_out_eval2.zip`: `repro/`(PC·DiT fp16·DiT bf16 재현 비교), `samples/` 영상, `compare/p{번호}_sheet.jpg`·`p{번호}_side.mp4`, `logs/`.
""", "tools/kaggle_wan_eval_worker.py", "--out /kaggle/working", "tools/kaggle_wan_eval.ipynb",
             "받기·설치 → PC 재현 확인 → 16개 GPU 나눠서 → 비교 시트 → zip")


def build_train_test():
    notebook("""
# AI-sfa Wan LoRA 학습 시험 — Kaggle T4에서 학습이 되는지

사용자 GPU가 당분간 1050 Ti뿐이라 학습을 Kaggle로 옮길 수 있는지 잰다. 학습 자료 48조각, 100스텝만(결과 LoRA는 안 씀).
GPU 0 = fp16 학습, GPU 1 = bf16 학습(PC와 같은 방식, T4에선 에뮬레이션)을 동시에 돌려 속도·손실·메모리를 PC(2.85초/스텝, 손실 0.16)와 비교한다.
""" + SETUP_MD + """
**실행:** **Save Version → Save & Run All (Commit)**. 예상 40–70분(추정). 결과 `wan_train_test.zip` 안 `train_test/summary.json`을 Claude에게.
""", "tools/kaggle_wan_train_test_worker.py", "--out /kaggle/working --steps 100", "tools/kaggle_wan_train_test.ipynb",
             "받기·설치 → 48조각 캐시 → fp16·bf16 학습 100스텝 → 요약")


def build_eval3():
    notebook("""
# AI-sfa 나카무라 Wan LoRA 평가 3판 — 여러 씨앗 + CPU 노이즈 기준선

2판에서 같은 씨앗이라도 PC와 Kaggle 결과가 구도부터 달랐다(GPU 난수 차이가 유력) → 씨앗 하나로는 판정할 수 없다.
3판: 초기 노이즈를 CPU에서 만들어 장비와 상관없이 재현, 프롬프트 7개(기존 4 + 학습 캡션 낱말판 번개·임팩트 고리 + 로봇) × 씨앗 3개 × (학습 전·세기 0.6·0.8) = 영상 63개.
재학습한 LoRA와 같은 씨앗으로 비교할 기준선이 된다.
""" + SETUP_MD + """
**실행:** **Save Version → Save & Run All (Commit)**. 예상 60–90분(추정). 결과 `wan_out_eval3.zip`: `compare3/p{이름}_sheet.jpg`(줄 = 조건×씨앗), `p{이름}_grid.mp4`(3×3 나란히 재생), `samples3/`, `logs3/`.
""", "tools/kaggle_wan_eval3_worker.py", "--out /kaggle/working", "tools/kaggle_wan_eval3.ipynb",
             "받기·설치 → 63개 GPU 나눠서 → 시트 → zip")


def build_train(data_url):
    notebook("""
# AI-sfa 나카무라 Wan LoRA 본 학습 2차 — Kaggle T4 (fp16)

학습 자료 2판(효과 없음 23조각 제외 + 인물·로봇 캡션 문장)으로 3000스텝 학습한다(학습 시험: 4.41초/스텝 → 약 3.7시간).
GPU 0이 학습하는 동안 GPU 1이 1000·2000·3000스텝 저장본으로 평가 영상(프롬프트 7 × 씨앗 3, 세기 0.8, CPU 노이즈)을 만든다 — 평가 3판 기준선과 같은 씨앗.
""" + SETUP_MD.replace("02_분석자료/WanLoRA_평가/", "07_도구/PC_WanLoRA/") + """
**실행:** **Save Version → Save & Run All (Commit)**. 예상 5–6시간(추정). 결과 `nkmr_wan13_v2_out.zip`(LoRA 저장본 500스텝마다, 저장본 평가 시트 `ckpt_compare/`, 기록 `train/`).
""", "tools/kaggle_wan_train_worker.py", f"--out /kaggle/working --data-url '{data_url}'", "tools/kaggle_wan_train.ipynb",
             "받기·설치 → 캐시(GPU 2장) → GPU0 학습 + GPU1 저장본 평가 → zip")


if __name__ == "__main__":
    build()
    build_train_test()
    build_eval3()
    if os.environ.get("WANLORA_V2_URL"):  # 학습 자료 2판을 Drive에 올린 뒤 그 공유 주소로 만든다
        build_train(os.environ["WANLORA_V2_URL"])
