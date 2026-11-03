"""실제 출제 표본에서 기존 모델·새 목적함수를 CPU로 대조한다. 가중치는 업데이트하지 않는다."""
import argparse
import json
from pathlib import Path

import numpy as np
import torch
from PIL import Image, ImageDraw, ImageFont

import seq_train as T
import sfa_tokens as K
import sfa_render as R
from seq_objective import objective, metadata
from seq_target_audit import features
from seq_refine import file_sha


@torch.inference_mode()
def first_object(net, image, ratio, limit=192):
    memory = net.memory(image, ratio)
    cache = T.Cache(net, memory)
    grammar = K.grammar()
    allowed = next(grammar)
    tokens, fields = [], []
    kind, points, boundary = None, 0, None
    for _ in range(limit):
        if tokens and K.TOK['EOS'] in allowed[0]:
            boundary = list(tokens)
            if kind is not None and points >= K.NPTS[kind]:
                return K.decode(tokens+[K.TOK['EOS']]), '첫 객체를 자른 진단·전체 생성 결과 아님'
        logits = cache.step(tokens[-1], fields[-1]) if tokens else torch.zeros(K.VOCAB)
        token = int((logits+T.allowed_mask(allowed, 'cpu')).argmax())
        tokens.append(token)
        fields.append(K.FID[allowed[3]] if token >= K.OFF else K.FID['spec'])
        if token in {K.TOK[v] for v in K.TYPES.values()}:
            kind = K.SPECIAL[token]
        if token == K.TOK['PT']:
            points += 1
        try:
            allowed = grammar.send(token)
        except StopIteration:
            return K.decode(tokens), '기존 모델이 직접 종료'
    return K.decode((boundary or [K.TOK['BOS'], K.TOK['BG'], *[K.n(255)]*4])+[K.TOK['EOS']]), '첫 객체 진단 한도·전체 생성 정책 변경 아님'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('checkpoint')
    parser.add_argument('problems')
    parser.add_argument('out')
    args = parser.parse_args()
    torch.set_num_threads(2)
    torch.set_num_interop_threads(1)
    net, cfg = T.load(args.checkpoint, 'cpu')
    ds = T.Data(args.problems, cfg['maxlen'], cfg['in_w'], workers=1)
    selected = {}
    for kind in ('glow', 'fill', 'nonwhite_background', 'layer_opacity', 'curve'):
        found = next((i for i, tokens in enumerate(ds.tok) if kind in features(list(map(int, tokens)))), None)
        if found is not None:
            selected.setdefault(found, []).append(kind)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    rows, pictures = [], []
    font = ImageFont.truetype('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc', 18)
    R.PARAMS.update(pad=0., thick_mul=640/1920)
    for i, kinds in selected.items():
        print('실제 출제 표본 점검', i, ','.join(kinds), flush=True)
        image, tokens, fields, ratio = ds.batch([i])
        target = [int(t) for t in ds.tok[i]]
        with torch.no_grad():
            logits = net(image, tokens[:, :-1], fields[:, :-1], ratio).detach().requires_grad_(True)
        old, _ = objective(logits, tokens[:, 1:], fields[:, 1:], [target], 'token-v1')
        new, parts = objective(logits, tokens[:, 1:], fields[:, 1:], [target])
        old_grad = torch.autograd.grad(old, logits, retain_graph=True)[0]
        new_grad = torch.autograd.grad(new, logits)[0]
        end = logits.shape[1]-1
        spec = next(s for s in metadata(tuple(target))[0] if s[-1])
        ids = list(spec[1])+list(range(K.OFF+spec[2], K.OFF+spec[3]+1)) if spec[2] <= spec[3] else list(spec[1])
        legal = logits[0, end, ids].detach()
        choice = ids[int(legal.argmax())]
        row = dict(problem_index=i, features=kinds, tokens=len(target), original_loss=float(old.detach()),
                   candidate_objective=float(new.detach()), components={k: float(v.detach()) for k, v in parts.items()},
                   teacher_end_choice=K.SPECIAL[choice] if choice < K.OFF else choice,
                   teacher_end_eos_probability=float(legal.softmax(0)[ids.index(K.TOK['EOS'])]),
                   eos_logit_gradient_old=float(old_grad[0, end, K.TOK['EOS']]),
                   eos_logit_gradient_candidate=float(new_grad[0, end, K.TOK['EOS']]))
        pred, why = first_object(net, image, ratio)
        height = max(2, round(640*float(ratio[0])))
        seq = T.seq_xml(float(ratio[0]))
        refs = [np.asarray(Image.fromarray(ds.image(i)).resize((640, height))),
                R.render_frame(seq, K.decode(target), 640, height), R.render_frame(seq, pred, 640, height)]
        sheet = Image.new('RGB', (1920, height+70), 'white')
        draw = ImageDraw.Draw(sheet)
        for col, (im, title) in enumerate(zip(refs, ['실제 출제 입력', '출제 SFA 정답', '기존 모델 첫 객체 · 진단'])):
            draw.text((col*640+5, 3), title, font=font, fill='black')
            sheet.paste(Image.fromarray(im), (col*640, 70))
        draw.text((5, 30), f"표본{i} · {','.join(kinds)} · 정답끝 선택 {row['teacher_end_choice']} · 새 가중치 결과 아님", font=font, fill='black')
        sheet.save(out/f'problem_{i:03d}.png')
        pictures.append(sheet)
        rows.append(dict(row, prefix_scope=why))
        (out/'audit.json').write_text(json.dumps(dict(scope='실제 학습 출제 파일 일부의 CPU 진단. 옵티마이저/가중치 업데이트 없음. 공식 품질 판정 아님.',
            parent_sha256=file_sha(args.checkpoint), samples=rows), ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
        del logits, old_grad, new_grad, old, new, parts
    combined = Image.new('RGB', (1920, sum(s.height for s in pictures)), 'white')
    y = 0
    for sheet in pictures:
        combined.paste(sheet, (0, y))
        y += sheet.height
    combined.save(out/'problems_native.png')


if __name__ == '__main__':
    main()
