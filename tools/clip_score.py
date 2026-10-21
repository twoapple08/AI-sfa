"""CLIP 글 문장 점수: clip_embed.py 임베딩에 요소 트리의 영어 이름을 맞대어 프레임별 점수를 낸다(학습 없음).

사용: python tools/clip_score.py <임베딩 폴더> <출력 npz> [모델] [가중치]
- 요소 문장: 트리의 'CLIP' 칸(없으면 '태그' 칸)의 영어 이름 → "an anime screenshot with {이름}".
  여러 이름은 문장을 각각 만들어 임베딩을 평균한다.
- 기준 문장(BASE)과 함께 softmax(×100)를 해서 '그 요소일 확률'을 낸다. 보기 5개(전체 + 2×2 확대) 중 최대값을 프레임 점수로 쓴다.
- 출력 npz: post_ids, t_index(영상별 프레임 범위), elements(번호), score(전체 프레임 × 요소, float16)
  임계값은 GPT 판정(G15–G17·H01–H04)과 육안 확인으로 정한다(clip 점수만으로 '나옴'을 확정하지 않는다).
"""
import csv
import glob
import os
import sys

import numpy as np
import torch

KB = os.path.join(os.path.dirname(__file__), '..', 'data', 'style_kb')
BASE = ['an anime screenshot', 'an anime character', 'an anime background', 'a blank frame', 'a pencil sketch']


def names(r):
    src = r['CLIP'] or r['태그']
    return [w.replace('_', ' ') for w in src.split()][:4]


def main():
    import open_clip
    emb, out = sys.argv[1:3]
    arch = sys.argv[3] if len(sys.argv) > 3 else 'ViT-B-16'
    wts = sys.argv[4] if len(sys.argv) > 4 else 'laion2b_s34b_b88k'
    model, _, _ = open_clip.create_model_and_transforms(arch, pretrained=wts)
    tok = open_clip.get_tokenizer(arch)
    tree = [r for r in csv.DictReader(open(os.path.join(KB, 'element_tree_2026-10-20.csv'), encoding='utf-8-sig')) if r['단계'] != '0']
    tree = [r for r in tree if names(r)]
    with torch.no_grad():
        def enc(texts):
            e = model.encode_text(tok(texts))
            return e / e.norm(dim=-1, keepdim=True)
        base = enc(BASE)
        el = []
        for r in tree:
            e = enc([f'an anime screenshot with {n}' for n in names(r)]).mean(0)
            el.append(e / e.norm())
        el = torch.stack(el)
    files = sorted(glob.glob(os.path.join(emb, '*.npz')))
    pids, idx, scores = [], [], []
    k = 0
    for f in files:
        d = np.load(f)
        e = torch.from_numpy(d['e'].astype(np.float32))  # (프레임, 5, 차원)
        if not len(e):
            continue
        se = e @ el.T                       # (프레임, 5, 요소)
        sb = e @ base.T                     # (프레임, 5, 기준)
        logit = torch.cat([se.unsqueeze(-1), sb.unsqueeze(-2).expand(-1, -1, se.shape[-1], -1)], -1) * 100
        p = logit.softmax(-1)[..., 0].amax(1)  # (프레임, 요소)
        pids.append(os.path.basename(f)[:-4])
        idx.append((k, k + len(p)))
        k += len(p)
        scores.append(p.numpy().astype(np.float16))
    np.savez_compressed(out, post_ids=np.array(pids), t_index=np.array(idx), elements=np.array([r['번호'] for r in tree]),
                        score=np.concatenate(scores) if scores else np.zeros((0, len(tree)), np.float16))
    print('영상', len(pids), '프레임', k, '요소', len(tree))


if __name__ == '__main__':
    main()
