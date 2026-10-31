#!/usr/bin/env python3
"""두 이펙트 마스크(Claude 지시판·GPT 지시판)의 장점을 섞는다 (2026-10-24, 사용자: "너랑 GPT 장점만 섞어봐").

최종 = (A ∪ B) − (A의 '빼기' 물체 ∪ B의 '빼기' 물체)
- 한쪽이라도 이펙트로 잡은 곳은 넣고, 한쪽이라도 인물·물체로 뺀 곳은 뺀다.
- '빼기' 물체 = fx_auto_fix.py 출력의 obj_mask 중 labels가 remove로 시작하는 것(SAM 2가 구간 전체로 따라간 마스크).
- 색으로 뺀 것(color remove)은 물체 마스크로 남지 않아 다시 빼지 못한다 — 한쪽판이 다른 판을 바탕으로 만든 경우 그 판에 이미 반영돼 있다.
출력은 v3와 같은 키라 effect_clip_sfa.py --mask로 바로 쓴다.
사용: python tools/fx_mask_mix.py <A.npz> <B.npz> <출력.npz>
"""
import json
import sys

import numpy as np


def load(p):
    z = np.load(p)
    shp = tuple(int(v) for v in z["shape"])
    m = np.unpackbits(z["mask"], axis=-1)[..., :shp[2]].astype(bool)
    rem = np.zeros_like(m)
    labels = [str(x) for x in z["labels"]] if "labels" in z else []
    if "obj_mask" in z and z["obj_mask"].shape[0] == len(labels):
        objs = np.unpackbits(z["obj_mask"], axis=-1)[..., :shp[2]].astype(bool)
        for lab, om in zip(labels, objs):
            if lab.startswith("remove"):
                rem |= om
    return z, m, rem


def main():
    a, b, out = sys.argv[1:4]
    za, ma, ra = load(a)
    zb, mb, rb = load(b)
    assert ma.shape == mb.shape and list(za["frames"]) == list(zb["frames"]), "두 마스크의 장·크기가 다르다"
    m = (ma | mb) & ~(ra | rb)
    n = m.shape[0]
    np.savez_compressed(out, mask=np.packbits(m, axis=-1), shape=np.array(m.shape), frames=za["frames"],
                        obj_mask=np.packbits(np.stack([ra | rb]), axis=-1), labels=np.array(["remove_mix"]),
                        area=m.reshape(n, -1).mean(1).astype(np.float32),
                        det=np.array(json.dumps({"mix": [a, b]}, ensure_ascii=False)))
    print(f"{out}: 평균 면적 A {ma.mean() * 100:.1f}% · B {mb.mean() * 100:.1f}% → 섞음 {m.mean() * 100:.1f}%")


if __name__ == "__main__":
    main()
