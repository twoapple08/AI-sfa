"""Kaggle 노트북(2D→3D 올리기 모델 학습)을 만든다.

출력: tools/kaggle_lift.ipynb — tools/lift_train.py 본문을 넣어 둔다.
입력은 Drive `02_분석자료/모캡_통합/`(mocap_unified/*.npz, mocap_index csv), 중간 저장본은 `02_분석자료/모델_3D올리기/lifter.pt`.
10분마다 중간 저장본을 Drive에 올리고, 다시 실행하면 이어서 학습한다(12시간 제한 대응).
"""
import json
import os

from colab_p1_build import ROOT, code, md



def build():
    trainer = open(os.path.join(ROOT, "tools/lift_train.py"), encoding="utf-8").read()
    setup = json.load(open(os.path.join(ROOT, "tools/kaggle_p1p2.ipynb"), encoding="utf-8"))["cells"][1]["source"]
    setup = "".join(setup).replace("\n!pip -q install rtmlib onnxruntime-gpu onnx onnx2torch", "")
    cells = [
        md("""
# AI-sfa 3D 올리기 모델 학습 — Kaggle GPU

설정은 P1·P2 노트북과 같다: **GPU T4 x2(또는 P100)**, **Internet On**, Secrets `RCLONE_GDRIVE_AUTH_B64` 연결.
**Save Version → Save & Run All (Commit)**. 12시간에 멈추면 다시 실행하면 이어서 학습한다.
"""),
        code(setup),
        code("""
# 2. 자료·학습 코드 준비
import os, subprocess, time
os.makedirs('/kaggle/working/mocap', exist_ok=True); os.makedirs('/kaggle/working/out', exist_ok=True)
subprocess.run(['rclone', 'copy', 'gdrive:AI-sfa/02_분석자료/모캡_통합', '/kaggle/working/mocap'], check=True)
subprocess.run(['rclone', 'copy', 'gdrive:AI-sfa/02_분석자료/모델_3D올리기', '/kaggle/working/out'])
print(os.listdir('/kaggle/working/mocap'), os.listdir('/kaggle/working/out'))
open('/kaggle/working/lift_train.py', 'w', encoding='utf-8').write(%s)
"""
             % json.dumps(trainer, ensure_ascii=False)),
        code("""
# 3. 학습(중간 저장본을 10분마다 Drive에 올림)
idx = [f for f in os.listdir('/kaggle/working/mocap') if f.endswith('.csv')][0]
pr = subprocess.Popen(['python', '/kaggle/working/lift_train.py', '/kaggle/working/mocap', '/kaggle/working/out',
                       '--index', '/kaggle/working/mocap/' + idx], stdout=open('/kaggle/working/lift.log', 'w'),
                      stderr=subprocess.STDOUT)
t0 = time.time()
while pr.poll() is None and time.time() - t0 < 11.5 * 3600:
    time.sleep(600)
    subprocess.run(['rclone', 'copy', '/kaggle/working/out/lifter.pt', 'gdrive:AI-sfa/02_분석자료/모델_3D올리기'])
    subprocess.run(['rclone', 'copy', '/kaggle/working/lift.log', 'gdrive:AI-sfa/02_분석자료/모델_3D올리기'])
    print(round((time.time() - t0) / 60), '분 |', open('/kaggle/working/lift.log').read().splitlines()[-1:], flush=True)
pr.terminate()
subprocess.run(['rclone', 'copy', '/kaggle/working/out/lifter.pt', 'gdrive:AI-sfa/02_분석자료/모델_3D올리기'])
subprocess.run(['rclone', 'copy', '/kaggle/working/lift.log', 'gdrive:AI-sfa/02_분석자료/모델_3D올리기'])
print('종료')
"""),
    ]
    nb = {"cells": cells, "metadata": {"kernelspec": {"name": "python3", "display_name": "Python 3"},
                                       "kaggle": {"accelerator": "nvidiaTeslaT4", "isInternetEnabled": True}},
          "nbformat": 4, "nbformat_minor": 4}
    p = os.path.join(ROOT, "tools/kaggle_lift.ipynb")
    json.dump(nb, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return p


if __name__ == "__main__":
    print(build())
