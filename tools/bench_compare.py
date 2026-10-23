#!/usr/bin/env python3
"""기준 프롬프트 비교: 같은 스토리보드를 여러 동작 모델로 조립해 장면별 대표 프레임을 한 장에 나란히 놓는다.

사용: python tools/bench_compare.py <스토리보드 json> <출력 폴더> --momask <momask-codes 폴더>
        --model 이름표=마스크이름,잔차이름[,트리거] [--model …]
  예) --model 기본=t2m_nlayer8_nhead6_ld384_ff1024_cdp0.1_rvq6ns,tres_nlayer8_ld384_ff1024_rvq6ns_cdp0.2_sw
      --model 3차=t2m_…_ft_v3,tres_…_ft_v3,in anime style
- 모델마다 tools/storyboard_compose.py로 SFA를 만들고(출력 폴더/<이름표>/), 장면마다 가운데·끝 프레임을 서버 렌더로 그려
  행 = 모델, 열 = 장면으로 붙인 비교.jpg를 만든다. 같은 --seed를 쓴다. 이름표는 영문(그림 글자가 ASCII만 됨, 예: base·v1·v3).
"""
import argparse
import glob
import json
import os
import subprocess
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sfa_render import iter_frames, render_frame  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("storyboard")
    ap.add_argument("out")
    ap.add_argument("--momask", required=True)
    ap.add_argument("--model", action="append", required=True)
    ap.add_argument("--seed", type=int, default=1)
    a = ap.parse_args()
    here = os.path.dirname(os.path.abspath(__file__))
    rows, labels = [], []
    for spec in a.model:
        label, rest = spec.split("=", 1)
        parts = rest.split(",", 2)
        od = os.path.join(a.out, label)
        cmd = [sys.executable, os.path.join(here, "storyboard_compose.py"), a.storyboard, od, "--momask", a.momask,
               "--name", parts[0], "--res-name", parts[1], "--seed", str(a.seed)]
        if len(parts) > 2 and parts[2]:
            cmd += ["--style", parts[2]]
        subprocess.run(cmd, check=True)
        info = json.load(open(os.path.join(od, "조립정보.json"), encoding="utf-8"))
        lens, per = info["장면_프레임"], int(5 * info["F"])
        want = []
        s0 = 0
        for n in lens:
            want += [s0 + n // 2, s0 + n - 1]
            s0 += n
        tiles = {}
        for k, fn in enumerate(sorted(glob.glob(os.path.join(od, "*.sfa")))):
            local = {w - k * per for w in want if k * per <= w < (k + 1) * per}
            for seq, fr in iter_frames(fn, local):
                tiles[k * per + int(fr.get("Position"))] = render_frame(seq, fr, 320, 180)[..., ::-1].copy()
        row = []
        for i, w in enumerate(want):
            t = tiles.get(w, np.full((180, 320, 3), 200, np.uint8))
            cv2.putText(t, f"S{i // 2 + 1}{'mid' if i % 2 == 0 else 'end'}", (4, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
            row.append(t)
        head = np.full((180, 120, 3), 255, np.uint8)
        cv2.putText(head, label, (6, 95), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2)
        rows.append(np.hstack([head] + row))
        labels.append(label)
    cv2.imwrite(os.path.join(a.out, "비교.jpg"), np.vstack(rows), [cv2.IMWRITE_JPEG_QUALITY, 85])
    print("비교", labels, "→", os.path.join(a.out, "비교.jpg"))


if __name__ == "__main__":
    main()
