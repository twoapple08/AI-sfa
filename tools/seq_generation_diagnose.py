#!/usr/bin/env python3
"""고정 판정 표본의 CPU 자유 생성·종료 선택·접두 그림을 진단한다. 공식 판정을 대체하지 않는다.

출력에는 원자료 그림·전체 생성 토큰이 포함되므로 저장소 밖 비공개 경로를 사용한다.
"""
import argparse
import hashlib
import json
import time
from pathlib import Path

import numpy as np
import torch

import seq_train as T
import sfa_tokens as K
import seq_judge as J
import sfa_render as R
import sfa_objscore as OS


@torch.inference_mode()
def trace(net, image, hwr):
    """기존 greedy 생성과 같은 선택을 하며 EOS 허용 자리의 확률을 남긴다."""
    mem = net.memory(image[None], torch.tensor([hwr], dtype=torch.float32))
    cache = T.Cache(net, mem)
    grammar = K.grammar()
    allowed = next(grammar)
    tokens, fields, decisions = [], [], []
    forced = False
    while len(tokens) < net.maxlen:
        logits = cache.step(tokens[-1], fields[-1]) if tokens else torch.zeros(K.VOCAB)
        logits = logits + T.allowed_mask(allowed, image.device)
        chosen = int(logits.argmax())
        if K.TOK['EOS'] in allowed[0]:
            decisions.append(dict(position=len(tokens), chosen=K.SPECIAL[chosen] if chosen < K.OFF else chosen,
                                  eos_probability=float(logits.softmax(-1)[K.TOK['EOS']]),
                                  eos_rank=1 + int((logits > logits[K.TOK['EOS']]).sum()),
                                  chosen_probability=float(logits.softmax(-1)[chosen])))
            if len(tokens) >= net.maxlen - 64:
                forced = chosen != K.TOK['EOS']
                chosen = K.TOK['EOS']
        tokens.append(chosen)
        fields.append(K.FID[allowed[3]] if chosen >= K.OFF else K.FID['spec'])
        try:
            allowed = grammar.send(chosen)
        except StopIteration:
            return tokens, 'forced' if forced else 'eos', decisions, mem
    return tokens, 'limit', decisions, mem


@torch.inference_mode()
def teacher_end(net, mem, target):
    """정답 접두열을 주었을 때 마지막 EOS 선택. 자유 생성 종료와 구별한다."""
    fields = K.fields(target)
    inp = torch.tensor(target[:-1], dtype=torch.long)[None]
    fld = torch.tensor(fields[:-1], dtype=torch.long)[None]
    logits = net.step(mem, inp, fld)[0, -1]
    g = K.grammar()
    al = next(g)
    for token in target[:-1]:
        al = g.send(token)
    logits += T.allowed_mask(al, logits.device)
    choice = int(logits.argmax())
    return dict(eos_probability=float(logits.softmax(-1)[K.TOK['EOS']]),
                eos_rank=1 + int((logits > logits[K.TOK['EOS']]).sum()),
                chosen=K.SPECIAL[choice] if choice < K.OFF else choice)


def score_prefix(tokens, position, target, hwr):
    pred = K.decode(tokens[:position] + [K.TOK['EOS']])
    sc = OS.score(pred, K.decode(target), hwr=hwr)
    return pred, dict(position=position, objects=sc['pred'], target_objects=sc['ans'],
                      match=sc['match'], partial=100 * sc['partial'])


def early_prefixes(tokens, decisions, target, hwr):
    """완료된 첫 객체들과 정답 토큰 길이 부근을 본다. 조기 종료 정책은 아니다."""
    starts = [i for i, t in enumerate(tokens) if t in (K.TOK['LINE'], K.TOK['CIRC'], K.TOK['CURVE'])]
    boundaries = [d['position'] for d in decisions]
    positions = [(f'첫 {n}객체', starts[n]) for n in (1, 2, 4, 8) if len(starts) > n]
    positions.append(('정답 길이 부근', min(boundaries, key=lambda b: abs(b - len(target)))))
    return [(label, *score_prefix(tokens, pos, target, hwr)) for label, pos in positions]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('checkpoint')
    p.add_argument('judge_folder')
    p.add_argument('out')
    p.add_argument('--n', type=int, default=6)
    p.add_argument('--threads', type=int, default=2)
    p.add_argument('--verify-first', action='store_true', help='첫 표본을 기존 생성 함수와 토큰 단위 대조')
    a = p.parse_args()
    if a.n < 1 or a.threads < 1:
        p.error('--n과 --threads는 양수여야 한다')
    torch.set_num_threads(a.threads)
    torch.set_num_interop_threads(1)
    net, cfg = T.load(a.checkpoint, 'cpu')
    with open(a.checkpoint, 'rb') as source:
        checkpoint_sha256 = hashlib.file_digest(source, 'sha256').hexdigest()
    ds = J.JudgeSet(a.judge_folder, cfg['in_w'])
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    R.PARAMS.update(pad=0.0, thick_mul=640 / 1920)
    from PIL import Image, ImageDraw, ImageFont
    font = ImageFont.truetype('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc', 19)
    rows, sheets = [], []
    for i in range(min(a.n, len(ds))):
        start = time.time()
        print(f'고정 표본 {i + 1}/{a.n} 시작', flush=True)
        image = torch.from_numpy(np.ascontiguousarray(ds.image(i, 0))).permute(2, 0, 1).float() / 255
        hwr = ds.ents[i]['hwr']
        target = [int(t) for t in ds.tok[i][0]]
        with torch.inference_mode():
            tokens, why, decisions, mem = trace(net, image, hwr)
            teacher = teacher_end(net, mem, target)
            if i == 0 and a.verify_first:
                reference, done, reason = T.generate(net, image, hwr, reason=True)
                assert tokens == reference and why == reason, '기존 생성과 진단 생성 불일치'
        # EOS가 허용되는 위치에서만 자르므로 미완성 오브젝트를 새로 만들지 않는다.
        boundaries = [d['position'] for d in decisions]
        positions = [min(boundaries, key=lambda b: abs(b - len(tokens) * q)) for q in (.25, .5, .75)]
        positions.append(len(tokens) - 1 if tokens[-1] == K.TOK['EOS'] else boundaries[-1])
        frames, metrics = zip(*(score_prefix(tokens, pos, target, hwr) for pos in positions))
        early = early_prefixes(tokens, decisions, target, hwr)
        try:
            K.fields(tokens)
            grammar_error = None
        except ValueError as exc:
            grammar_error = str(exc)
        record = dict(index=i, file=ds.ents[i]['file'], position=ds.ents[i]['pos'], direction=0,
                      reason=why, tokens=len(tokens), target_tokens=len(target), strict_grammar=grammar_error is None,
                      grammar_error=grammar_error,
                      reference_generation_verified=bool(i == 0 and a.verify_first),
                      teacher_target_end=teacher, prefixes=list(metrics), decisions=decisions,
                      early_prefixes=[dict(label=label, **metric) for label, _, metric in early],
                      seconds=round(time.time() - start, 2))
        rows.append(record)
        # 원좌표·토큰은 비공개 출력 경로에만 둔다.
        (out / f'tokens_{i:02d}.json').write_text(json.dumps(tokens), encoding='utf-8')
        H = max(2, round(640 * hwr))
        seq = T.seq_xml(hwr)
        images = [np.asarray(Image.fromarray(ds.image(i, 0)).resize((640, H)))]
        images.extend(R.render_frame(seq, f, 640, H)[..., :3] for f in frames)
        images.append(R.render_frame(seq, K.decode(target), 640, H)[..., :3])
        end_label = {'forced': '강제 종료', 'eos': '자연 종료', 'limit': '한도 잘림'}[why]
        labels = ['입력', '생성 25%', '생성 50%', '생성 75%', f'최종 · {end_label}', '정답']
        # 각 칸은 고유 화면 비율을 유지한다. 축소본은 전체 훑기용이다.
        sheet = Image.new('RGB', (640 * 6, H + 70), 'white')
        draw = ImageDraw.Draw(sheet)
        for col, (im, label) in enumerate(zip(images, labels)):
            draw.text((col * 640 + 6, 4), f'{i + 1}. {label}', font=font, fill='black')
            if 0 < col < 5:
                m = metrics[col - 1]
                draw.text((col * 640 + 6, 29), f'객체 {m["objects"]}/{m["target_objects"]} · 부분점수 {m["partial"]:.2f}', font=font, fill='black')
            sheet.paste(Image.fromarray(im), (col * 640, 70))
        sheet.save(out / f'prefix_{i:02d}.png')
        sheets.append(sheet)
        summary = dict(evidence='CPU float32, 폭640, 방향0, 고정 앞 표본. 공식 GPU 판정 재현·승격 아님.',
                       checkpoint_sha256=checkpoint_sha256, maxlen=cfg['maxlen'], samples=rows)
        (out / 'diagnosis.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f'고정 표본 {i + 1}: {why}, 토큰 {len(tokens)}/{len(target)}, {time.time() - start:.1f}초', flush=True)
    overview = Image.new('RGB', (3840, sum(s.height for s in sheets)), 'white')
    y = 0
    for sheet in sheets:
        overview.paste(sheet, (0, y))
        y += sheet.height
    overview.save(out / 'prefix_all_native.png')
    overview.resize((1920, round(overview.height / 2))).save(out / 'prefix_overview.png')


if __name__ == '__main__':
    main()
