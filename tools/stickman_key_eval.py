"""스틱맨 자동 추출 정확도: 장면의 원본 판독 관절 좌표(visible_views·partials의 keys)를 정답으로 쓰고,
SFA의 같은 관절이 얼마나 떨어졌는지 머리 지름 단위로 잰다('딸깍' 추출 진척 지표, 11-10 사용자).

정답은 사람이 원본에서 읽은 좌표라 판독 오차가 있다. 키를 넣은 장은 대부분 자동이 틀렸던 어려운 장이라
구간 전체 정확도가 아니라 '어려운 장 정확도'다. 자동 추출을 잴 때는 키를 뺀 장면 설정으로 만든 SFA를 넣는다.

예: python tools/stickman_key_eval.py 자동.sfa --scene scenes/nian41_3072-3311.json --start 3072 --crop-y 63
"""
import argparse
import json
import os
import sys
import zipfile
import xml.etree.ElementTree as E

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pose_to_stickman import BODY  # noqa: E402
from stickman_clip import AO0  # noqa: E402

NAMES = {pid: name for _, _, pts in BODY for pid, name, _, _ in pts}


def sfa_joints(path, start, crop_y, W=1152, H=648):
    """{(장, 슬롯): {관절: (x, y)}} (원본 픽셀, y는 잘라낸 위 여백 포함)."""
    root = E.fromstring(zipfile.ZipFile(path).read(zipfile.ZipFile(path).namelist()[0]))
    out = {}
    for n, f in enumerate(root.findall('Frame')):
        for a in f.findall('AO'):
            oid = int(a.get('ID'))
            if not AO0 < oid < AO0 + 1000 or a.get('Color') == '0' and (oid - AO0) % 100 != 1:
                continue
            slot = (oid - AO0) // 100
            for p in a.findall('AP'):
                pid = int(p.get('ID')) % 100
                if pid in NAMES:
                    out.setdefault((start + n, slot), {})[NAMES[pid]] = (float(p.get('X')) * W / 100, float(p.get('Y')) * H / 100 + crop_y)
    return out


def evaluate(sfa, scene, start, crop_y, slots):
    J = sfa_joints(sfa, start, crop_y)
    rows = []
    for v in scene.get('visible_views', []) + scene.get('partials', []):
        hd = v.get('head_d') or {}
        for fr, keys in v.get('keys', {}).items():
            fr = int(fr)
            d = None
            if hd:
                ks = sorted(int(k) for k in hd)
                d = float(np.interp(fr, ks, [hd[str(k)] for k in ks]))
            if d is None and 'head_t' in keys and 'head_b' in keys:
                d = float(np.linalg.norm(np.subtract(keys['head_t'], keys['head_b'])))
            got = J.get((fr, slots[v['actor']]))
            for name, xy in keys.items():
                if name.startswith('head'):
                    continue  # 머리는 지름 규칙(구간 흐름)으로 따로 정하므로 위치 오차는 목·몸통·팔다리로 잰다
                err = None if got is None or name not in got else float(np.linalg.norm(np.subtract(got[name], xy)))
                rows.append(dict(frame=fr, actor=v['actor'], joint=name, err_px=err, head_d=d))
    return rows


def summary(rows):
    have = [r for r in rows if r['err_px'] is not None and r['head_d']]
    rel = np.array([r['err_px'] / r['head_d'] for r in have]) if have else np.array([])
    return dict(keys=len(rows), missing=len(rows) - len(have),
                median_head=float(np.median(rel)) if len(rel) else None,
                within_half_head=float((rel <= 0.5).mean()) if len(rel) else None,
                within_one_head=float((rel <= 1.0).mean()) if len(rel) else None)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('sfa', nargs='+')
    ap.add_argument('--scene', required=True)
    ap.add_argument('--start', type=int, required=True)
    ap.add_argument('--crop-y', type=float, default=63)
    ap.add_argument('--rows', help='관절별 결과 JSON 저장 경로(첫 SFA)')
    a = ap.parse_args()
    scene = json.load(open(a.scene))
    slots = {'blue': 0, 'red': 1}
    for i, s in enumerate(a.sfa):
        rows = evaluate(s, scene, a.start, a.crop_y, slots)
        print(os.path.basename(s), json.dumps(summary(rows), ensure_ascii=False))
        if a.rows and i == 0:
            json.dump(rows, open(a.rows, 'w'), ensure_ascii=False)


if __name__ == '__main__':
    main()
