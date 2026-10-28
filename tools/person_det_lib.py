"""애니 인물 검출(deepghs/anime_person_detection person_detect_v1.3_s ONNX, YOLOv8 출력 1클래스) — 학습 조각의 인물 비중 재기용 (2026-10-28)."""
import cv2, numpy as np, onnxruntime as ort
class Det:
    def __init__(self, path, size=640):
        self.s = ort.InferenceSession(path, providers=['CPUExecutionProvider']); self.size = size
    def __call__(self, bgr, conf=0.35):
        h, w = bgr.shape[:2]; r = self.size / max(h, w)
        nh, nw = round(h * r), round(w * r)
        canvas = np.full((self.size, self.size, 3), 114, np.uint8)
        canvas[:nh, :nw] = cv2.resize(bgr, (nw, nh))
        x = canvas[..., ::-1].transpose(2, 0, 1)[None].astype(np.float32) / 255
        out = self.s.run(None, {'images': x})[0][0]
        if out.shape[0] < out.shape[1]:
            out = out.T  # (anchors, 4+nc)
        sc = out[:, 4:].max(1); keep = sc > conf
        b = out[keep, :4]; sc = sc[keep]
        if not len(b): return []
        xyxy = np.c_[b[:, 0] - b[:, 2] / 2, b[:, 1] - b[:, 3] / 2, b[:, 0] + b[:, 2] / 2, b[:, 1] + b[:, 3] / 2] / r
        idx = cv2.dnn.NMSBoxes(xyxy[:, :2].tolist() and [[*p[:2], p[2]-p[0], p[3]-p[1]] for p in xyxy.tolist()], sc.tolist(), conf, 0.5)
        idx = np.array(idx).reshape(-1)
        return [(np.clip(xyxy[i], 0, [w, h, w, h]), float(sc[i])) for i in idx]
