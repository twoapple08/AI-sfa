"""P1 포즈 모델 비교 Colab 노트북을 만든다.

입력: data/p1/pose_compare_clips.json (애니메이터 5명 × 영상 4개 × 연속 32프레임 구간)
출력: tools/colab_p1_pose_compare.ipynb

노트북은 같은 구간을 YOLO11x-pose, RTMW-x(rtmlib), ViTPose+-H, Sapiens2(1B, A100이면 5B도)로
추론하고 결과를 Drive `AI-sfa/02_분석자료/P1_포즈비교/<모델>/` 에 저장한다.
비교·평가는 서버(tools/p1_pose_eval.py)에서 Drive 결과를 읽어 한다.
"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def md(s):
    return {"cell_type": "markdown", "metadata": {}, "source": s.strip("\n").splitlines(True)}


def code(s):
    return {"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [],
            "source": s.strip("\n").splitlines(True)}


def build():
    clips = json.load(open(os.path.join(ROOT, "data/p1/pose_compare_clips.json"), encoding="utf-8"))
    cells = [
        md("""
# P1 포즈 모델 비교 — Colab GPU

순서대로 실행하거나 **런타임 → 모두 실행**을 누른다.

- 시작 전: **런타임 → 런타임 유형 변경 → GPU**(A100 > L4 > T4 순으로 좋음)
- 2번 칸에서 Google Drive 연결을 허용한다.
- 끊겨도 다시 '모두 실행'하면 끝난 구간은 건너뛴다.
- 결과: 내 드라이브 `AI-sfa/02_분석자료/P1_포즈비교/` — Claude가 Drive에서 직접 읽는다(첨부 필요 없음).
- 표본: 애니메이터 5명 × 영상 4개 × 연속 32프레임 2구간 = 1280프레임
"""),
        code("""
# 1. 준비(3~5분)
!pip -q install -U "transformers>=5.20" accelerate ultralytics rtmlib onnxruntime-gpu
import torch; print('GPU:', torch.cuda.is_available() and torch.cuda.get_device_name(0))
"""),
        code("""
# 2. 내 드라이브 연결
from google.colab import drive
drive.mount('/content/drive')
"""),
        code("""
# 3. 설정
import os, json, shutil, time, traceback
import cv2, numpy as np, torch
from PIL import Image
ROOT = '/content/drive/MyDrive/AI-sfa'
OUT = ROOT + '/02_분석자료/P1_포즈비교'
os.makedirs(OUT, exist_ok=True)
CLIPS = json.loads(r'''%s''')
GPU = torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'cpu'
BIG = torch.cuda.is_available() and torch.cuda.get_device_properties(0).total_memory > 30e9
DT = torch.bfloat16 if torch.cuda.is_available() and torch.cuda.is_bf16_supported() else torch.float32
print(len(CLIPS), '구간', GPU, '큰 모델(5B):', BIG, DT)

def key(c): return f"{c['animator']}_{c['id']}_{c['start']}"

_cache = {}
def frames(c):
    k = key(c)
    if k in _cache: return _cache[k]
    src = ROOT + '/' + c['path']; loc = '/content/v_' + os.path.basename(src)
    if not os.path.exists(loc): shutil.copy(src, loc)
    cap = cv2.VideoCapture(loc); fs = []; i = 0
    while len(fs) < c['count']:
        ok, im = cap.read()
        if not ok: break
        if i >= c['start']: fs.append(im)
        i += 1
    cap.release(); _cache.clear(); _cache[k] = fs
    return fs

def save(model, c, rows, labels=None):
    d = f'{OUT}/{model}'; os.makedirs(d, exist_ok=True)
    if labels is not None and not os.path.exists(d + '/_labels.json'):
        json.dump(labels, open(d + '/_labels.json', 'w'))
    json.dump({'clip': c, 'frames': rows}, open(f'{d}/{key(c)}.json', 'w'))

def done(model, c): return os.path.exists(f'{OUT}/{model}/{key(c)}.json')

def r1(a): return np.round(np.asarray(a, dtype=float), 1).tolist()
def kp3(a):  # x, y는 소수 1자리, 점수는 소수 3자리
    a = np.asarray(a, dtype=float); return np.concatenate([a[:, :2].round(1), a[:, 2:3].round(3)], 1).tolist()
""" % json.dumps(clips, ensure_ascii=False)),
        code("""
# 4. 사람 상자: rtmlib의 HumanArt 검출기(그림·애니 포함 학습, 기준값 0.3).
#    모든 top-down 모델(RTMW·ViTPose·Sapiens2)이 같은 상자를 쓴다. 상자가 없으면 화면 전체.
from rtmlib import Wholebody
WB = Wholebody(mode='performance', backend='onnxruntime', device='cuda')
WB.det_model.score_thr = 0.3
BOXES = {}
for c in CLIPS:
    p = f'{OUT}/_boxes/{key(c)}.json'
    if os.path.exists(p): BOXES[key(c)] = json.load(open(p)); continue
    fs = frames(c); h, w = fs[0].shape[:2]; bl = []
    for im in fs:
        b = [[x1, y1, x2 - x1, y2 - y1] for x1, y1, x2, y2 in np.asarray(WB.det_model(im)).reshape(-1, 4).tolist()]
        bl.append(r1(b) if b else [[0, 0, w, h]])
    os.makedirs(f'{OUT}/_boxes', exist_ok=True); json.dump(bl, open(p, 'w')); BOXES[key(c)] = bl
print('상자 완료', len(BOXES), '구간')
"""),
        code("""
# 5. 모델 A: YOLO11x-pose (상자도 스스로 찾음)
def run_yolo():
    from ultralytics import YOLO
    m = YOLO('yolo11x-pose.pt')
    for c in CLIPS:
        if done('yolo11x', c): continue
        rows = []
        for im in frames(c):
            r = m.predict(im, conf=0.10, imgsz=960, verbose=False)[0]
            ppl = []
            if r.keypoints is not None and len(r.boxes):
                for b, k in zip(r.boxes.xyxy.cpu().numpy(), r.keypoints.data.cpu().numpy()):
                    ppl.append({'box': r1([b[0], b[1], b[2] - b[0], b[3] - b[1]]), 'kp': kp3(k)})
            rows.append(ppl)
        save('yolo11x', c, rows, 'coco17')
    print('yolo11x 완료')
try: run_yolo()
except Exception: traceback.print_exc()
"""),
        code("""
# 6. 모델 B: RTMW-x 전신 133점(rtmlib, 4번 상자)
def run_rtmw():
    for c in CLIPS:
        if done('rtmw_x', c): continue
        rows = []
        for im, bx in zip(frames(c), BOXES[key(c)]):
            xyxy = np.array([[x, y, x + w, y + h] for x, y, w, h in bx])
            kps, sc = WB.pose_model(im, bboxes=xyxy)
            rows.append([{'box': b, 'kp': kp3(np.concatenate([k, s[:, None]], 1))} for b, k, s in zip(bx, kps, sc)])
        save('rtmw_x', c, rows, 'coco_wholebody133')
    print('rtmw_x 완료')
try: run_rtmw()
except Exception: traceback.print_exc()
"""),
        code("""
# 7. 모델 C·D: ViTPose+-H, Sapiens2 (4번 상자 사용, top-down)
from transformers import AutoProcessor, VitPoseForPoseEstimation, Sapiens2ForPoseEstimation

def run_topdown(name, repo, cls, vit=False):
    proc = AutoProcessor.from_pretrained(repo)
    m = cls.from_pretrained(repo, dtype=DT).cuda().eval()
    labels = [m.config.id2label[i] for i in range(len(m.config.id2label))] if m.config.id2label else None
    for c in CLIPS:
        if done(name, c): continue
        rows = []
        for im, bx in zip(frames(c), BOXES[key(c)]):
            pil = Image.fromarray(cv2.cvtColor(im, cv2.COLOR_BGR2RGB))
            inp = proc(images=[pil], boxes=[bx], return_tensors='pt').to('cuda')
            inp['pixel_values'] = inp['pixel_values'].to(DT)
            with torch.no_grad():
                if vit:
                    out = m(**inp, dataset_index=torch.zeros(len(bx), dtype=torch.long, device='cuda'))
                else:
                    out = m(pixel_values=inp['pixel_values'])
            out.heatmaps = out.heatmaps.float()
            res = proc.post_process_pose_estimation(out, boxes=[bx])[0]
            rows.append([{'box': b, 'kp': kp3(torch.cat([p['keypoints'].cpu(), p['scores'].cpu()[:, None]], 1))}
                         for b, p in zip(bx, res)])
        save(name, c, rows, labels)
    del m; torch.cuda.empty_cache(); print(name, '완료')

for name, repo, cls, vit, need_big in [
    ('vitpose_plus_h', 'usyd-community/vitpose-plus-huge', VitPoseForPoseEstimation, True, False),
    ('sapiens2_1b', 'facebook/sapiens2-pose-1b', Sapiens2ForPoseEstimation, False, False),
    ('sapiens2_5b', 'facebook/sapiens2-pose-5b', Sapiens2ForPoseEstimation, False, True),
]:
    if need_big and not BIG: print(name, '건너뜀(GPU 메모리 30GB 미만)'); continue
    t = time.time()
    try: run_topdown(name, repo, cls, vit)
    except Exception: traceback.print_exc()
    print(name, round(time.time() - t), '초')
"""),
        code("""
# 8. 확인: 모델별 저장 구간 수
for d in sorted(os.listdir(OUT)):
    if os.path.isdir(f'{OUT}/{d}'): print(d, len([x for x in os.listdir(f'{OUT}/{d}') if not x.startswith('_')]))
open(OUT + '/_gpu.txt', 'w').write(GPU)
"""),
    ]
    nb = {"cells": cells, "metadata": {"accelerator": "GPU", "colab": {"provenance": []},
                                       "kernelspec": {"name": "python3", "display_name": "Python 3"}},
          "nbformat": 4, "nbformat_minor": 0}
    p = os.path.join(ROOT, "tools/colab_p1_pose_compare.ipynb")
    json.dump(nb, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return p


if __name__ == "__main__":
    print(build())
