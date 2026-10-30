#!/usr/bin/env python3
"""원인 가르기 시험(2026-10-30, GPT 검토 5번): 모델이 영상을 실제로 보고 쓰는지.
같은 정답 문장에 (정상) 그 장의 영상 / (섞음) 다른 파일 장의 영상 / (빈 화면) 흰 화면을 넣고
① 교사 강제 손실·좌표 칸 맞힘 ② 실제 생성 오브젝트 채점을 비교한다. 정상만 좋으면 영상을 본다, 셋이 비슷하면 외운 모양을 쓴다.
사용: python seq_diag.py ckpt.pt 자료폴더 [--n 20] [--no-gen]
"""
import argparse
import os
import random
import sys

import numpy as np
import torch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import seq_train as Q  # noqa: E402
import sfa_objscore as OS  # noqa: E402
import sfa_tokens as K  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('ckpt')
    ap.add_argument('data')
    ap.add_argument('--n', type=int, default=20)
    ap.add_argument('--no-gen', action='store_true')
    a = ap.parse_args()
    net, c = Q.load(a.ckpt)
    ds = Q.Data(a.data, c['maxlen'], c['in_w'])
    rng = random.Random(0)
    idx = rng.sample(range(len(ds)), min(a.n, len(ds)))
    files = [m['file'] for m in ds.meta]
    coord = K.FID['coord']

    def other(i):   # 다른 파일의 장(같은 파일의 이웃 장은 거의 같은 그림이라 뺀다)
        cand = [j for j in range(len(ds)) if files[j] != files[i]]
        return rng.choice(cand) if cand else i

    conds = {'정상': lambda i: ds.image(i), '섞음': lambda i: ds.image(other(i)),
             '빈 화면': lambda i: np.full_like(ds.image(i), 255)}
    for name, img_of in conds.items():
        tl = tn = cc = cn = 0.0
        sums = dict(ans=0, pred=0, match=0, link_tp=0, link_pred=0, link_ans=0)
        for i in idx:
            img = torch.from_numpy(np.ascontiguousarray(img_of(i))).permute(2, 0, 1).float()[None] / 255
            tok = torch.from_numpy(ds.tok[i])[None]
            fld = torch.from_numpy(ds.fld[i])[None]
            hwr = torch.tensor([ds.hwr[i]])
            with torch.no_grad():
                lg = net(img, tok[:, :-1], fld[:, :-1], hwr)
            l_, _, n_ = Q.loss_fn(lg, tok[:, 1:], fld[:, 1:])
            tl += l_.item() * n_.item()
            tn += n_.item()
            m = fld[:, 1:] == coord
            cc += ((lg.argmax(-1) - tok[:, 1:]).abs()[m] <= 4).sum().item()   # 좌표 ±4칸(0.1%) 안
            cn += m.sum().item()
            if not a.no_gen:
                toks, _ = Q.generate(net, img[0], ds.hwr[i], c['maxlen'])
                sc = OS.score(K.decode(toks), K.decode(ds.tok[i].tolist()), hwr=ds.hwr[i])
                for k in sums:
                    sums[k] += sc[k]
        line = f'{name}: 손실 {tl / tn:.3f} · 좌표 칸 ±4 맞힘 {cc / max(cn, 1) * 100:.1f}%'
        if not a.no_gen:
            line += (f' · 생성: 원본 {sums["ans"]} 중 맞힘 {sums["match"]} ({sums["match"] / max(sums["ans"], 1) * 100:.1f}%), '
                     f'AI {sums["pred"]}개, 연결 F1 {OS.f1(sums["link_tp"], sums["link_pred"], sums["link_ans"]) * 100:.1f}%')
        print(line, flush=True)


if __name__ == '__main__':
    main()
