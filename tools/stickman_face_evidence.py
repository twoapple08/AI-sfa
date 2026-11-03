"""독립 얼굴 관측을 CPU로 저장한다. 가중치는 외부 파일이며 저장소에 넣지 않는다.

deepghs/anime_face_detection의 YOLO ONNX(cx,cy,w,h,score)용이다.
얼굴 검출은 신체/가시성 정답이 아니며, 변환기는 원영상 지문을 대조해 보조 관측으로만 쓴다.
"""
import argparse
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np


def digest(path):
    with open(path, 'rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def detect(net, frame, threshold=.278, size=640):
    h, w = frame.shape[:2]
    scale = size / max(w, h)
    nw, nh = round(w*scale), round(h*scale)
    left, top = (size-nw)//2, (size-nh)//2
    image = np.full((size, size, 3), 114, np.uint8)
    image[top:top+nh, left:left+nw] = cv2.resize(frame, (nw, nh))
    net.setInput(cv2.dnn.blobFromImage(image, 1/255., (size, size), swapRB=True))
    rows = net.forward()
    if rows.ndim != 3 or rows.shape[:2] != (1, 5):
        raise ValueError('지원하지 않는 얼굴 ONNX 출력: cx,cy,w,h,score의 [1,5,N] 필요')
    rows = rows[0].T
    rows = rows[np.isfinite(rows).all(1) & (rows[:, 4] >= threshold)]
    boxes = np.c_[rows[:, :2]-rows[:, 2:4]/2, rows[:, 2:4]]
    keep = cv2.dnn.NMSBoxes(boxes.tolist(), rows[:, 4].tolist(), threshold, .7)
    result = []
    for index in np.asarray(keep).reshape(-1):
        box = boxes[index].copy()
        box[:2] -= [left, top]
        box /= scale
        result.append(dict(box=box.tolist(), score=float(rows[index, 4])))
    return result


def load_evidence(path, video, frames, width, height):
    data = json.loads(Path(path).read_text())
    if data.get('schema') != 1 or data.get('source_sha256') != digest(video):
        raise ValueError('얼굴 관측의 형식 또는 원영상 지문이 다르다')
    if data.get('size') != [width, height] or any(str(f) not in data.get('frames', {}) for f in frames):
        raise ValueError('얼굴 관측의 해상도/장 범위가 처리 대상과 다르다')
    for rows in data['frames'].values():
        for row in rows:
            box = np.asarray(row['box'], float)
            if box.shape != (4,) or not np.isfinite(box).all() or (box[2:] <= 0).any():
                raise ValueError('얼굴 관측에 잘못된 상자가 있다')
            if not np.isfinite(row['score']) or not 0 <= row['score'] <= 1:
                raise ValueError('얼굴 관측에 잘못된 점수가 있다')
    return data


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('video')
    ap.add_argument('model')
    ap.add_argument('output')
    ap.add_argument('--start', type=int, required=True)
    ap.add_argument('--end', type=int, required=True)
    ap.add_argument('--threshold', type=float, default=.278)
    args = ap.parse_args()
    if args.start < 0 or args.end < args.start or not 0 < args.threshold < 1:
        ap.error('장 범위/검출 문턱이 잘못되었다')
    cv2.setNumThreads(2)
    net = cv2.dnn.readNetFromONNX(args.model)
    net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
    net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
    cap = cv2.VideoCapture(args.video)
    width, height = (int(cap.get(k)) for k in (cv2.CAP_PROP_FRAME_WIDTH, cv2.CAP_PROP_FRAME_HEIGHT))
    data = dict(schema=1, source_sha256=digest(args.video), model_sha256=digest(args.model),
                size=[width, height], start=args.start, end=args.end, threshold=args.threshold,
                backend='OpenCV DNN CPU', frames={})
    cap.set(cv2.CAP_PROP_POS_FRAMES, args.start)
    for frame in range(args.start, args.end+1):
        ok, image = cap.read()
        if not ok:
            raise ValueError(f'원영상 {frame}장을 읽을 수 없다')
        data['frames'][str(frame)] = detect(net, image, args.threshold)
        if (frame-args.start+1) % 240 == 0:
            print(f'얼굴 보조 관측 {frame-args.start+1}/{args.end-args.start+1}', flush=True)
    cap.release()
    Path(args.output).write_text(json.dumps(data, ensure_ascii=False)+'\n')


if __name__ == '__main__':
    main()
