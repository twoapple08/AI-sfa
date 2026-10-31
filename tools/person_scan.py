"""학습 조각 mp4마다 5장(처음·1/4·1/2·3/4·끝)에서 인물을 검출해 가장 큰 인물(확신 0.5 이상)의 면적 비율·장 수를 JSON으로 (2026-10-28).
사용: python -I tools/person_scan.py model.onnx <조각 폴더> scan.json   (모델: HF deepghs/anime_person_detection/person_detect_v1.3_s/model.onnx)
CPU 482조각 약 26분. 확인(Claude 시트 대조): 면적 10%이상·5장 중 3장 이상은 대부분 실제 인물, 1–2장·화면 전체 상자는 이펙트 오검출이 절반가량.
"""
import sys, glob, json, os, cv2, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from person_det_lib import Det
d = Det(sys.argv[1]); vids = sorted(glob.glob(os.path.join(sys.argv[2], '*.mp4'))); out = []
for p in vids:
    c = cv2.VideoCapture(p); n = int(c.get(7)); best = None; hits = 0; ks = sorted({0, n // 4, n // 2, 3 * n // 4, n - 1})
    for k in ks:
        c.set(1, k); ok, f = c.read()
        if not ok: continue
        r = [(b, s) for b, s in d(f, conf=0.3)]
        if any(s >= 0.5 for _, s in r): hits += 1
        for b, s in r:
            a = float((b[2] - b[0]) * (b[3] - b[1]) / f.shape[0] / f.shape[1])
            key = a * (s >= 0.5) + s * 1e-3
            if best is None or key > best['key']:
                best = dict(key=key, frame=k, box=[float(x) for x in b], conf=s, area=a)
    out.append(dict(clip=os.path.basename(p)[:-4], frames=n, sampled=len(ks), hits=hits, **({k: v for k, v in best.items() if k != 'key'} if best else {})))
json.dump(out, open(sys.argv[3], 'w'), ensure_ascii=False)
print(len(out), '조각')
