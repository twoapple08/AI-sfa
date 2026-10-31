"""CLIP 글 문장 점수: clip_embed.py 임베딩에 요소 트리의 영어 이름을 맞대어 프레임별 점수를 낸다(학습 없음).

사용: python tools/clip_score.py <임베딩 폴더> <출력 npz> [모델] [가중치]
- 요소 문장: 트리의 'CLIP' 칸(없으면 '태그' 칸)의 영어 이름 → "an anime screenshot with {이름}".
  여러 이름은 문장을 각각 만들어 임베딩을 평균한다.
- 프레임 점수 = 보기 5개(전체 + 2×2 확대) 중 최대 코사인 유사도에서 기준 문장(BASE) 최대 유사도를 뺀 값.
  요소마다 전체 프레임으로 z 점수를 낸다(요소 문장마다 유사도 수준이 달라서 원값끼리는 비교하지 않는다).
  처음 시험한 softmax(요소 문장 대 기준 문장)는 거의 모든 요소가 0.95 이상이 되어 버렸다(2026-10-21).
- 출력 npz: post_ids, t_index(영상별 프레임 범위), elements(번호), score(z 점수, 전체 프레임 × 요소, float16), raw(차이 원값)
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
        se = (e @ el.T).amax(1)                    # (프레임, 요소)
        sb = (e @ base.T).amax(-1).amax(1, keepdim=True)  # (프레임, 1)
        p = se - sb
        pids.append(os.path.basename(f)[:-4])
        idx.append((k, k + len(p)))
        k += len(p)
        scores.append(p.numpy().astype(np.float16))
    raw = np.concatenate(scores).astype(np.float32) if scores else np.zeros((0, len(tree)), np.float32)
    z = (raw - raw.mean(0)) / (raw.std(0) + 1e-6)
    np.savez_compressed(out, post_ids=np.array(pids), t_index=np.array(idx), elements=np.array([r['번호'] for r in tree]),
                        score=z.astype(np.float16), raw=raw.astype(np.float16))
    print('영상', len(pids), '프레임', k, '요소', len(tree))


if __name__ == '__main__':
    main()
