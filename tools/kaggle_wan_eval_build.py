"""Kaggle 노트북(나카무라 Wan LoRA 평가 영상 16개)을 만든다 (2026-10-28).

출력: tools/kaggle_wan_eval.ipynb — tools/kaggle_wan_eval_worker.py 본문을 넣어 둔다.
Drive 업로드는 Kaggle 비밀값 RCLONE_GDRIVE_AUTH_B64가 있을 때만(kaggle_build.py와 같은 방식). 없으면 Output 탭에 결과 zip이 남는다.
"""
import json
import os

from colab_p1_build import ROOT, code, md


def build():
    worker = open(os.path.join(ROOT, "tools/kaggle_wan_eval_worker.py"), encoding="utf-8").read()
    cells = [
        md("""
# AI-sfa 나카무라 Wan LoRA 평가 — Kaggle GPU

PC방 학습 결과(LoRA 3000스텝)로 비교 영상 16개를 만든다: 프롬프트 4개 × (LoRA 세기 0.6 · 0.8 · 1.0 · 1.0+인물 빼기).
모델은 HuggingFace, LoRA는 Drive의 `wan_out.zip`(공유 링크)에서 노트북이 직접 받는다.

**설정:**
1. **Settings → Accelerator → GPU T4 x2**
2. **Settings → Internet → On**
3. (선택) **Add-ons → Secrets**에 `RCLONE_GDRIVE_AUTH_B64`를 이 노트북에 붙이면 결과가 Drive `AI-sfa/02_분석자료/WanLoRA_평가/`로 올라간다. 없으면 Output 탭에서 받는다.

**실행:** 오른쪽 위 **Save Version → Save & Run All (Commit)** — 브라우저를 닫아도 돈다. 예상 40–70분(추정).
결과 `wan_out_eval.zip`: `samples/p{번호}_{세기}.mp4` 16개, `compare/p{번호}_sheet.jpg`(장 0·8·16·24·32 × 학습 전·세기별), `compare/p{번호}_side.mp4`(나란히 재생), `logs/`.
"""),
        code("""
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
"""),
        code("""
# 2. 작업자 파일 쓰기 → 실행(받기·설치 → 세기 1.0 먼저 확인 → 나머지 GPU 나눠서 → 비교 시트 → zip)
open('/tmp/kaggle_wan_eval_worker.py', 'w', encoding='utf-8').write(%s)
!python -u /tmp/kaggle_wan_eval_worker.py --out /kaggle/working
""" % json.dumps(worker, ensure_ascii=False)),
    ]
    nb = {"cells": cells, "metadata": {"kernelspec": {"name": "python3", "display_name": "Python 3"},
                                       "language_info": {"name": "python"}},
          "nbformat": 4, "nbformat_minor": 4}
    p = os.path.join(ROOT, "tools/kaggle_wan_eval.ipynb")
    json.dump(nb, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("→", p)


if __name__ == "__main__":
    build()
