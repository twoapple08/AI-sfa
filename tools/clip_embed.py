"""CLIP 이미지 임베딩(학습 없음, 추론만): 요소 트리의 태그 없는 요소·작은 소품을 글 문장으로 찾기 위한 준비.

사용: python tools/clip_embed.py <목록 csv(post_id, animator)> <영상 루트(animator/post_id.mp4)> <출력 폴더> [모델] [가중치]
기본 모델: ViT-B-16 / laion2b_s34b_b88k (CPU 4코어 기준).
출력: <출력>/<post_id>.npz
- t: 프레임 시각(초), 1초 간격
- e: (프레임, 5, 차원) float16, L2 정규화. 보기 0 = 전체 화면(정사각형으로 여백 채움), 1–4 = 2×2 확대 조각(왼위·오위·왼아래·오아래)
임베딩을 저장해 두면 글 문장(clip_score.py)을 바꿔도 다시 계산하지 않는다.
- 이미 있는 npz는 건너뛴다(이어하기).
"""
import csv
import os
import sys
import time

import cv2
import numpy as np
import torch
from PIL import Image

STEP = 1.0


def frames(path, step):
    """앞에서부터 차례로 읽어 step초마다 한 장(cap.set 탐색은 키프레임이 드문 영상에서 매우 느렸다)."""
    cap = cv2.VideoCapture(path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 24
    i, nxt = 0, 0.0
    while cap.grab():
        t = i / fps
        if t + 1e-6 >= nxt:
            ok, f = cap.retrieve()
            if ok:
                yield round(nxt, 3), cv2.cvtColor(f, cv2.COLOR_BGR2RGB)
            nxt += step
        i += 1
    cap.release()


def square(im):
    w, h = im.size
    s = max(w, h)
    out = Image.new('RGB', (s, s), (0, 0, 0))
    out.paste(im, ((s - w) // 2, (s - h) // 2))
    return out


def views(rgb):
    im = Image.fromarray(rgb)
    w, h = im.size
    crops = [im.crop((x, y, x + w // 2, y + h // 2)) for y in (0, h // 2) for x in (0, w // 2)]
    return [square(v) for v in [im] + crops]


def main():
    import open_clip
    lst, root, out = sys.argv[1:4]
    arch = sys.argv[4] if len(sys.argv) > 4 else 'ViT-B-16'
    wts = sys.argv[5] if len(sys.argv) > 5 else 'laion2b_s34b_b88k'
    os.makedirs(out, exist_ok=True)
    torch.set_num_threads(os.cpu_count() or 4)
    dev = 'cuda' if torch.cuda.is_available() else 'cpu'
    model, _, prep = open_clip.create_model_and_transforms(arch, pretrained=wts, device=dev)
    model.eval()
    jobs = [(r['post_id'], r['animator']) for r in csv.DictReader(open(lst, encoding='utf-8-sig'))]
    t0 = time.time()
    for k, (pid, an) in enumerate(jobs):
        dst = os.path.join(out, pid + '.npz')
        src = os.path.join(root, an, pid + '.mp4')
        if os.path.exists(dst) or not os.path.exists(src):
            continue
        ts, embs = [], []
        batch = []
        for t, f in frames(src, STEP):
            ts.append(t)
            batch += [prep(v) for v in views(f)]
        with torch.no_grad():
            for i in range(0, len(batch), 80):
                x = torch.stack(batch[i:i + 80]).to(dev)
                e = model.encode_image(x)
                embs.append((e / e.norm(dim=-1, keepdim=True)).float().cpu().numpy())
        e = np.concatenate(embs).reshape(len(ts), 5, -1).astype(np.float16) if embs else np.zeros((0, 5, 1), np.float16)
        np.savez_compressed(dst, t=np.array(ts, np.float32), e=e)
        print(k + 1, len(jobs), pid, len(ts), f'{time.time() - t0:.0f}s', flush=True)


if __name__ == '__main__':
    main()
