"""AMASS(+SMPL-X 몸 모델) 받기 Colab 노트북을 만든다.

출력: tools/colab_amass_download.ipynb
계정 정보는 Colab 비밀값(AMASS_USER, AMASS_PASS)에서만 읽는다. 출력·저장하지 않는다.
받은 파일은 Drive `AI-sfa/02_분석자료/모캡_AMASS/`에 둔다. 관절 좌표 변환은 서버에서 한다.

MPI 다운로드 서버는 로그인 아이디·비밀번호를 POST로 받는다(download.is.tue.mpg.de/download.php).
파일 경로 이름은 공개 목록이 없어 후보 여러 개를 시도하고, bz2/zip 머리 바이트로 진짜 파일인지 확인한다.
"""
import json
import os

from colab_p1_build import ROOT, code, md

# 격투·넘어짐·과장 동작이 많은 순서. 이름 철자는 AMASS 다운로드 페이지 표기 후보.
DATASETS = ["ACCAD", "HDM05", "KIT", "BMLmovi", "BMLrub", "EyesJapanDataset", "Transitions", "SFU",
            "DanceDB", "HumanEva", "TotalCapture", "MoSh", "EKUT", "CNRS", "SOMA", "WEIZMANN", "HUMAN4D",
            "PosePrior", "SSM", "DFaust", "TCDHands", "GRAB", "CMU"]


def build():
    cells = [
        md("""
# AMASS 모캡 받기 — Colab (GPU 필요 없음)

**처음 한 번만:**
1. 왼쪽 열쇠 아이콘(**보안 비밀**)에서 `AMASS_USER`(AMASS 가입 이메일), `AMASS_PASS`(비밀번호)를 추가하고 '노트북 액세스'를 켠다. 대화에는 붙이지 않는다.
2. https://smpl-x.is.tue.mpg.de 에도 **같은 이메일로 가입**하고 라이선스에 동의한다(몸 모델 파일. AMASS 자료를 관절 좌표로 바꾸는 데 필요).

그다음 **런타임 → 모두 실행.** 런타임 유형은 CPU여도 된다. 끊기면 다시 실행하면 이어서 받는다.
결과: 내 드라이브 `AI-sfa/02_분석자료/모캡_AMASS/` (전부 받으면 수십 GB일 수 있다. 3번 칸 출력에 크기가 찍힌다)
"""),
        code("""
# 1. 드라이브 연결과 계정 읽기(값은 출력하지 않는다)
from google.colab import drive, userdata
drive.mount('/content/drive')
U, P = userdata.get('AMASS_USER'), userdata.get('AMASS_PASS')
print('계정 읽음:', bool(U), bool(P))
"""),
        code("""
# 2. 받기 함수
import os, requests, shutil, time
OUT = '/content/drive/MyDrive/AI-sfa/02_분석자료/모캡_AMASS'
os.makedirs(OUT, exist_ok=True)
URL = 'https://download.is.tue.mpg.de/download.php'
MAGIC = (b'BZh', b'PK', b'\\x1f\\x8b', b'\\xfd7zXZ')

def get(domain, sfile, dst):
    if os.path.exists(dst) and os.path.getsize(dst) > 1000: return 'have'
    r = requests.post(URL, params={'domain': domain, 'resume': 1, 'sfile': sfile},
                      data={'username': U, 'password': P}, stream=True, timeout=120)
    it = r.iter_content(1 << 20); first = next(it, b'')
    if r.status_code != 200 or not first.startswith(MAGIC):
        return f'없음({r.status_code}, {first[:60]!r})'
    tmp = '/content/dl.part'
    with open(tmp, 'wb') as f:
        f.write(first)
        for ch in it: f.write(ch)
    shutil.move(tmp, dst)
    return f'{os.path.getsize(dst) / 1e6:.0f}MB'
"""),
        code("""
# 3. SMPL-X 몸 모델과 AMASS 자료(SMPL-X 중성 → 실패하면 성별별 → SMPL-H 순으로 시도)
print('SMPL-X 모델:', get('smplx', 'models_smplx_v1_1.zip', OUT + '/models_smplx_v1_1.zip'))
DATASETS = %s
for ds in DATASETS:
    res = None
    for sub in ['smplx/neutral/mosh_results', 'smplx/gender_specific/mosh_results', 'smplh/gender_specific/mosh_results']:
        dst = f"{OUT}/{sub.split('/')[0]}_{sub.split('/')[1]}_{ds}.tar.bz2"
        res = get('amass', f'amass_per_dataset/{sub}/{ds}.tar.bz2', dst)
        if not res.startswith('없음'): break
    print(ds, sub if not res.startswith('없음') else '', res)
total = sum(os.path.getsize(f'{OUT}/{f}') for f in os.listdir(OUT)) / 1e9
print('합계', round(total, 1), 'GB')
""" % json.dumps(DATASETS)),
    ]
    nb = {"cells": cells, "metadata": {"colab": {"provenance": []},
                                       "kernelspec": {"name": "python3", "display_name": "Python 3"}},
          "nbformat": 4, "nbformat_minor": 0}
    p = os.path.join(ROOT, "tools/colab_amass_download.ipynb")
    json.dump(nb, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return p


if __name__ == "__main__":
    print(build())
