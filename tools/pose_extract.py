#!/usr/bin/env python3
"""nian41 영상에서 프레임마다 사람 관절 좌표(17점)를 뽑는다. GPU PC용.

준비(Windows, H: 드라이브):
  pip install torch --index-url https://download.pytorch.org/whl/cu126
  pip install ultralytics opencv-python
실행:
  python pose_extract.py            # 전부(Sakugabooru 36 + 본인 X 12)
  python pose_extract.py --test     # 1개만 시험

- 이미 만들어진 YOLO11 포즈 모델로 추론만 한다(학습 없음, 2026-10-17 사용자 허가).
- 영상은 공개 주소에서 받아 md5를 대조하고, 끝나면 지운다.
- 결과: out/<id>.jsonl.gz (프레임별 사람 목록: box, conf, kpts 17×[x,y,score]),
        out/<id>_preview.jpg (관절을 그린 확인용 프레임 6장), out/summary.json
- 애니 그림은 실사 학습 모델과 차이가 커서 검출이 빠지거나 틀릴 수 있다. preview로 확인한다.
"""
import argparse
import gzip
import hashlib
import json
import os
import time
import urllib.request

RAW = 'https://raw.githubusercontent.com/twoapple08/AI-sfa/ccr-bccf15a6-d6ee46'
X_VIDEOS = {  # 본인 X 게시 영상(A등급). 공개 주소, md5는 Claude가 받은 파일 기준
    '1534075160545878017': 'https://video.twimg.com/ext_tw_video/1534075102643597314/pu/vid/1280x520/uRGXkj6FWa7Jg27-.mp4',
    '1534078885696000000': 'https://video.twimg.com/ext_tw_video/1534078818415259648/pu/vid/1280x520/VqdwKsOLFbQR6qZ7.mp4',
    '1567691748968906752': 'https://video.twimg.com/ext_tw_video/1567691674331287552/pu/vid/444x248/r44oSAbZwFOI4Itr.mp4',
    '1569962812805644289': 'https://video.twimg.com/ext_tw_video/1569962730874093570/pu/vid/444x722/9G0zx1Vqiiqb3mBF.mp4',
    '1613887197383622656': 'https://video.twimg.com/ext_tw_video/1613886859045896192/pu/vid/1280x720/vCi4hDosMqM8gILO.mp4',
    '1613887377965211649': 'https://video.twimg.com/ext_tw_video/1613887069633540099/pu/vid/1280x720/KnnUsMF5dViFRhPL.mp4',
    '1913231262086463573': 'https://video.twimg.com/amplify_video/1913230817725382656/vid/avc1/1152x720/NNSRXlDNZ-Tyqx-H.mp4',
    '1913481070839742689': 'https://video.twimg.com/amplify_video/1913480806426980352/vid/avc1/872x480/_TvwueNlbClzDGkp.mp4',
    '1913589758644908348': 'https://video.twimg.com/amplify_video/1913589621298270208/vid/avc1/1280x718/oyUiv5h9iOyXhCyO.mp4',
    '1937399147772137658': 'https://video.twimg.com/amplify_video/1937398858709106688/vid/avc1/666x1082/JB_gtpJy6f-UBipj.mp4',
    '1943223713455051062': 'https://video.twimg.com/amplify_video/1943223503043399681/vid/avc1/1280x720/PIcrvOcWgAX6WPKE.mp4',
    '2029588466376511962': 'https://video.twimg.com/amplify_video/2029588131645992960/vid/avc1/1280x720/0S54oiZ2EPjIcy2I.mp4',
}
# A등급(본인 작화 확인)을 먼저 처리한다
PRIORITY = [301142, 280544, 280597, 280830, 280831, 280833, 280834, 280835, 287139, 287140, 216085]
UA = {'User-Agent': 'AI-sfa-pose/1.0'}


def targets():
    with urllib.request.urlopen(urllib.request.Request(RAW + '/data/sources/nian41_drive_manifest_2026-10-17.jsonl', headers=UA), timeout=60) as r:
        rows = [json.loads(l) for l in r.read().decode('utf-8').splitlines() if l.strip()]
    sb = [r for r in rows if r['source'] == 'sakugabooru']
    sb.sort(key=lambda r: (PRIORITY.index(r['post_id']) if r['post_id'] in PRIORITY else 99, r['post_id']))
    out = [(str(r['post_id']), f"https://www.sakugabooru.com/data/{r['md5']}.{r['drive_path'].rsplit('.', 1)[1]}", r['md5']) for r in sb]
    out += [('x' + k, v, None) for k, v in X_VIDEOS.items()]
    return out


def fetch(url, path, md5):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=300) as r, open(path, 'wb') as f:
        f.write(r.read())
    if md5:
        got = hashlib.md5(open(path, 'rb').read()).hexdigest()
        if got != md5:
            raise RuntimeError(f'md5 불일치 {got}')


def run(model, vid, video, outdir):
    import cv2
    res_iter = model.predict(video, stream=True, verbose=False, half=True, imgsz=640, conf=0.25)
    n = det = 0
    keep = {}
    with gzip.open(os.path.join(outdir, f'{vid}.jsonl.gz'), 'wt', encoding='utf-8') as f:
        for i, res in enumerate(res_iter):
            people = []
            if res.keypoints is not None and len(res.boxes):
                k = res.keypoints.data.cpu().numpy().round(1).tolist()
                b = res.boxes.xyxy.cpu().numpy().round(1).tolist()
                c = res.boxes.conf.cpu().numpy().round(3).tolist()
                people = [{'box': b[j], 'conf': c[j], 'kpts': k[j]} for j in range(len(b))]
            f.write(json.dumps({'f': i, 'p': people}) + '\n')
            n += 1
            det += bool(people)
            if people and len(keep) < 6 and i % 25 == 0:
                keep[i] = res.plot()
    if keep:
        tiles = [cv2.resize(v, (480, 270)) for v in keep.values()]
        while len(tiles) < 6:
            tiles.append(tiles[-1] * 0)
        grid = cv2.vconcat([cv2.hconcat(tiles[:3]), cv2.hconcat(tiles[3:6])])
        cv2.imwrite(os.path.join(outdir, f'{vid}_preview.jpg'), grid, [cv2.IMWRITE_JPEG_QUALITY, 80])
    return n, det


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--test', action='store_true')
    ap.add_argument('--model', default='yolo11m-pose.pt')
    a = ap.parse_args()
    from ultralytics import YOLO
    import torch
    print('GPU:', torch.cuda.is_available() and torch.cuda.get_device_name(0))
    os.makedirs('out', exist_ok=True)
    os.makedirs('tmp_video', exist_ok=True)
    model = YOLO(a.model)
    T = targets()[:1] if a.test else targets()
    summary = {}
    if os.path.exists('out/summary.json'):
        summary = json.load(open('out/summary.json', encoding='utf-8'))
    for i, (vid, url, md5) in enumerate(T, 1):
        if vid in summary:
            continue
        t0 = time.time()
        path = os.path.join('tmp_video', vid + '.mp4')
        try:
            fetch(url, path, md5)
            n, det = run(model, vid, path, 'out')
            summary[vid] = {'frames': n, 'frames_with_person': det, 'sec': round(time.time() - t0, 1)}
            print(f'[{i}/{len(T)}] {vid}: {n}프레임, 사람 검출 {det}프레임, {time.time() - t0:.0f}초', flush=True)
        except Exception as e:
            summary[vid] = {'error': str(e)}
            print(f'[{i}/{len(T)}] {vid}: 실패 {e}', flush=True)
        finally:
            if os.path.exists(path):
                os.remove(path)
        json.dump(summary, open('out/summary.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('끝. out 폴더를 압축해서 Claude에게 보내 주세요.')


if __name__ == '__main__':
    main()
