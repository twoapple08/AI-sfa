"""Kaggle GPU 작업자: 단계 2 구간 장면에서 사람 상자마다 ViTPose++ Huge(COCO 17)와 Sapiens 1B(308점 → COCO 17 + 발)를 돌린다.
(2026-11-05 사용자 '자세를 제대로 못 잡는 게 너무 많다' → 추천: 더 강한 검출기를 RTMW와 같은 구간에서 비교.)

입력: /kaggle/input/<자료>/frames/<영상>_<장>.jpg, meta.json [{img, video, frame, scale, boxes: [[x0,y0,x1,y1] 원본 좌표]}]
출력: /kaggle/working/pose_<모델>.jsonl  {img, video, frame, people: [[[x, y, 점수] × 23] 원본 좌표]}  (23 = RTMW 몸 17 + 발 6 순서)
"""
import glob, json, os, sys, time
import numpy as np, cv2, torch

DATA = sorted(glob.glob('/kaggle/input/**/meta.json', recursive=True))[0].rsplit('/', 1)[0]   # 입력 경로가 /kaggle/input/datasets/<계정>/<자료>/일 수 있다
OUT = '/kaggle/working'
META = json.load(open(f'{DATA}/meta.json'))
dev = 'cuda'


def crop(img, box, aspect, pad=1.25):
    """상자 중심·크기(가로:세로 = aspect) 유지 아핀 자르기 → (자른 그림, 중심, 크기)."""
    x0, y0, x1, y1 = box
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    w, h = (x1 - x0) * pad, (y1 - y0) * pad
    if w / h > aspect: h = w / aspect
    else: w = h * aspect
    return (cx, cy), (w, h)


def warp(img, c, s, out_wh):
    W, H = out_wh
    src = np.float32([[c[0] - s[0] / 2, c[1] - s[1] / 2], [c[0] + s[0] / 2, c[1] - s[1] / 2], [c[0] - s[0] / 2, c[1] + s[1] / 2]])
    dst = np.float32([[0, 0], [W, 0], [0, H]])
    return cv2.warpAffine(img, cv2.getAffineTransform(src, dst), (W, H), flags=cv2.INTER_LINEAR)


def decode(hm, c, s, in_wh):
    """히트맵(K, h, w) → (K, 3) 원본 좌표 + 최댓값 점수. 이웃 차이로 1/4칸 보정."""
    K, h, w = hm.shape
    flat = hm.reshape(K, -1); idx = flat.argmax(1); sc = flat.max(1)
    y, x = (idx // w).astype(float), (idx % w).astype(float)
    for k in range(K):
        xi, yi = int(x[k]), int(y[k])
        if 0 < xi < w - 1: x[k] += 0.25 * np.sign(hm[k, yi, xi + 1] - hm[k, yi, xi - 1])
        if 0 < yi < h - 1: y[k] += 0.25 * np.sign(hm[k, yi + 1, xi] - hm[k, yi - 1, xi])
    px = c[0] - s[0] / 2 + (x + 0.5) / w * s[0]
    py = c[1] - s[1] / 2 + (y + 0.5) / h * s[1]
    return np.stack([px, py, sc], 1)


def run_vitpose():
    from transformers import AutoProcessor, VitPoseForPoseEstimation
    name = 'usyd-community/vitpose-plus-huge'
    proc = AutoProcessor.from_pretrained(name)
    model = VitPoseForPoseEstimation.from_pretrained(name, torch_dtype=torch.float16).to(dev).eval()
    f = open(f'{OUT}/pose_vitpose.jsonl', 'w'); t0 = time.time()
    for i, m in enumerate(META):
        img = cv2.imread(f"{DATA}/frames/{m['img']}")[:, :, ::-1]
        sc = m['scale']
        boxes = [[b[0] / sc, b[1] / sc, (b[2] - b[0]) / sc, (b[3] - b[1]) / sc] for b in m['boxes']]   # COCO xywh, 저화질 좌표
        people = []
        if boxes:
            inp = proc(img, boxes=[boxes], return_tensors='pt').to(dev)
            inp['pixel_values'] = inp['pixel_values'].half()
            with torch.no_grad():
                out = model(**inp, dataset_index=torch.zeros(len(boxes), dtype=torch.long, device=dev))   # 0 = COCO
            res = proc.post_process_pose_estimation(out, boxes=[boxes])[0]
            for r in res:
                kp = r['keypoints'].float().cpu().numpy() * sc; s_ = r['scores'].float().cpu().numpy()
                k23 = np.zeros((23, 3)); k23[:17, :2] = kp; k23[:17, 2] = s_
                people.append(k23.round(3).tolist())
        f.write(json.dumps(dict(img=m['img'], video=m['video'], frame=m['frame'], people=people)) + '\n')
        if i % 200 == 0: print('vitpose', i, len(META), round(time.time() - t0), flush=True)
    f.close()
    del model; torch.cuda.empty_cache()


# Sapiens Goliath 308점 → RTMW 23점(몸 17 COCO 순서 + 발 6: 왼 엄지·새끼·뒤꿈치, 오른 엄지·새끼·뒤꿈치)
# Goliath 0–14 = 코·눈·귀·어깨·팔꿈치·엉덩이·무릎·발목(COCO와 손목 자리만 다름), 손목 = 왼 62 · 오른 41, 발 15–20
G2R = [0, 1, 2, 3, 4, 5, 6, 7, 8, 62, 41, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20]


def run_sapiens():
    from huggingface_hub import hf_hub_download
    p = hf_hub_download('facebook/sapiens-pose-1b-torchscript', 'sapiens_1b_goliath_best_goliath_AP_639_torchscript.pt2')
    model = torch.jit.load(p).to(dev).eval().half()
    mean = torch.tensor([123.5, 116.5, 103.5], device=dev).view(1, 3, 1, 1)
    std = torch.tensor([58.5, 57.0, 57.5], device=dev).view(1, 3, 1, 1)
    f = open(f'{OUT}/pose_sapiens.jsonl', 'w'); t0 = time.time()
    for i, m in enumerate(META):
        img = cv2.imread(f"{DATA}/frames/{m['img']}")   # BGR
        sc = m['scale']
        crops, cs = [], []
        for b in m['boxes']:
            c, s = crop(img, [v / sc for v in b], 768 / 1024)
            crops.append(warp(img, c, s, (768, 1024))[:, :, ::-1].copy()); cs.append((c, s))   # RGB
        people = []
        if crops:
            x = torch.from_numpy(np.stack(crops)).to(dev).permute(0, 3, 1, 2).float()
            x = ((x - mean) / std).half()
            with torch.no_grad():
                hm = model(x).float()
                hm = (hm + torch.flip(model(torch.flip(x, [3])).float(), [3])[:, _flip_idx()] ) / 2   # 좌우 뒤집기 평균
            hm = hm.cpu().numpy()
            for j, (c, s) in enumerate(cs):
                k = decode(hm[j], c, s, (768, 1024))
                k[:, :2] *= sc
                people.append(k[G2R].round(3).tolist())
        f.write(json.dumps(dict(img=m['img'], video=m['video'], frame=m['frame'], people=people)) + '\n')
        if i % 200 == 0: print('sapiens', i, len(META), round(time.time() - t0), flush=True)
    f.close()


_FLIP = None


def _flip_idx():
    """좌우 뒤집기에서 Goliath 왼·오른 점 짝 바꾸기 — 이름 목록이 없으면 몸 17·발만 짝 바꾸고 나머지는 그대로."""
    global _FLIP
    if _FLIP is None:
        idx = list(range(308))
        for a, b in ((1, 2), (3, 4), (5, 6), (7, 8), (9, 10), (11, 12), (13, 14), (15, 18), (16, 19), (17, 20), (62, 41)):
            idx[a], idx[b] = b, a
        _FLIP = idx
    return _FLIP


if __name__ == '__main__':
    os.system('pip -q install -U "transformers>=4.49" huggingface_hub accelerate > /dev/null 2>&1')
    print('GPU', torch.cuda.get_device_name(0), '장', len(META), flush=True)
    which = sys.argv[1:] or ['vitpose', 'sapiens']
    if 'vitpose' in which: run_vitpose()
    if 'sapiens' in which: run_sapiens()
    print('끝', flush=True)
