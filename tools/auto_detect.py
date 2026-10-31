"""동작·이펙트 자동 탐지(학습 없음, 추론만): WD ViT Tagger v3 태그 + 영상 처리 지표.

사용: python tools/auto_detect.py <목록 csv(post_id, animator)> <영상 루트(animator/post_id.mp4)> <출력 폴더>
출력: <출력>/<post_id>.json
- tags: 0.5초 간격 프레임의 태그 확률(TAGS 순서, 소수 3자리)
- all: 0.5초 간격 프레임마다 일반 태그(8106개) 중 확률 0.05 이상인 것 {태그: 확률}. 요소 목록(산·바다·대포 등)을 넓게 세는 데 쓴다
- cv: 0.125초 간격 지표 [밝기, 채도, 회전도, 배율, 이동량]
  - 회전도·배율·이동량은 앞 프레임과의 전역 유사변환(ORB+RANSAC) 추정값
- 이미 있는 json은 건너뛴다(이어하기).
"""
import csv
import glob
import json
import os
import subprocess
import sys
import time

import cv2
import numpy as np

TAGS = ('explosion fire burning blue_fire smoke lightning electricity energy_beam laser aura glowing magic_circle magic '
        'debris dust dust_cloud rubble destruction broken_glass blood blood_splatter rain snow water splashing wind ice '
        'crystal floating_rock motion_blur motion_lines speed_lines afterimage sparks light_rays lens_flare energy_ball '
        'energy energy_sword muzzle_flash bullet shell_casing punching kicking fighting fighting_stance sword katana '
        'holding_sword swinging slashing gun handgun rifle aiming firing jumping running flying midair falling grabbing '
        'spear polearm weapon battle explosive wings mecha robot giant monster car motorcycle train airplane spacecraft '
        'monochrome greyscale silhouette fisheye dutch_angle from_below from_above perspective chromatic_aberration '
        'scenery cityscape ruins').split()


class Tagger:
    def __init__(self):
        import onnxruntime as rt
        d = glob.glob(os.path.expanduser('~/.cache/huggingface/hub/models--SmilingWolf--wd-vit-tagger-v3/snapshots/*'))[0]
        names = [r['name'] for r in csv.DictReader(open(os.path.join(d, 'selected_tags.csv')))]
        cats = [r['category'] for r in csv.DictReader(open(os.path.join(d, 'selected_tags.csv')))]
        self.names = names
        self.gen = [i for i, c in enumerate(cats) if c == '0']
        self.idx = [names.index(t) for t in TAGS]
        self.sess = rt.InferenceSession(os.path.join(d, 'model.onnx'), providers=['CPUExecutionProvider'])
        self.inp = self.sess.get_inputs()[0]
        self.size = self.inp.shape[1]

    def __call__(self, frames):
        out, full = [], []
        for s in range(0, len(frames), 16):
            batch = []
            for f in frames[s:s + 16]:
                h, w = f.shape[:2]
                m = max(h, w)
                sq = np.full((m, m, 3), 255, np.uint8)
                sq[(m - h) // 2:(m - h) // 2 + h, (m - w) // 2:(m - w) // 2 + w] = f
                sq = cv2.resize(sq, (self.size, self.size), interpolation=cv2.INTER_CUBIC)
                batch.append(sq[:, :, ::-1].astype(np.float32))
            pr = self.sess.run(None, {self.inp.name: np.stack(batch)})[0]
            out += [[round(float(p[i]), 3) for i in self.idx] for p in pr]
            full += [{self.names[i]: round(float(p[i]), 3) for i in self.gen if p[i] >= 0.05} for p in pr]
        return out, full


def frames(path, fps, w):
    p = subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-i', path, '-vf', f'fps={fps},scale={w}:-2',
                        '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], capture_output=True).stdout
    probe = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=width,height',
                            '-of', 'csv=p=0', path], capture_output=True, text=True).stdout.split(',')
    W, H = int(probe[0]), int(probe[1])
    h = int(round(H * w / W / 2) * 2)
    return np.frombuffer(p, np.uint8).reshape(-1, h, w, 3)


def cvstats(fr):
    orb = cv2.ORB_create(400)
    rows, prev = [], None
    for f in fr:
        hsv = cv2.cvtColor(f, cv2.COLOR_RGB2HSV)
        g = cv2.cvtColor(f, cv2.COLOR_RGB2GRAY)
        rot, sc, mv = 0.0, 1.0, 0.0
        kp, de = orb.detectAndCompute(g, None)
        if prev is not None and de is not None and prev[1] is not None and len(kp) > 20:
            m = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True).match(prev[1], de)
            if len(m) > 15:
                a = np.float32([prev[0][x.queryIdx].pt for x in m])
                b = np.float32([kp[x.trainIdx].pt for x in m])
                M, inl = cv2.estimateAffinePartial2D(a, b, method=cv2.RANSAC)
                if M is not None and inl.sum() > 12:
                    sc = float(np.hypot(M[0, 0], M[1, 0]))
                    rot = float(np.degrees(np.arctan2(M[1, 0], M[0, 0])))
                    mv = float(np.hypot(M[0, 2], M[1, 2]))
        prev = (kp, de)
        rows.append([round(float(g.mean()), 1), round(float(hsv[:, :, 1].mean()), 1), round(rot, 2), round(sc, 3), round(mv, 1)])
    return rows


def main():
    lst, root, out = sys.argv[1:4]
    os.makedirs(out, exist_ok=True)
    tg = Tagger()
    jobs = [(r['post_id'], r['animator']) for r in csv.DictReader(open(lst, encoding='utf-8-sig'))]
    t0 = time.time()
    for k, (pid, an) in enumerate(jobs):
        dst = os.path.join(out, pid + '.json')
        src = os.path.join(root, an, pid + '.mp4')
        if os.path.exists(dst) or not os.path.exists(src):
            continue
        tags, full = tg(list(frames(src, 2, 448)))
        cvr = cvstats(frames(src, 8, 320))
        json.dump({'post_id': pid, 'animator': an, 'tags': tags, 'all': full, 'cv': cvr}, open(dst, 'w'))
        print(k + 1, len(jobs), pid, len(tags), f'{time.time() - t0:.0f}s', flush=True)


if __name__ == '__main__':
    main()
