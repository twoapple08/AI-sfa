"""비교 실험용 목적함수: 종료/계속, 첫 객체, 색·굵기·글로우·면을 별도로 학습한다."""
from functools import lru_cache

import torch
import torch.nn.functional as F

import sfa_tokens as K
import seq_coord2 as C2

WEIGHTS = {'token-v1': (0., 0., 0.), 'balanced-v1': (.2, .2, .1)}
APPEARANCE = [('color', 'bg'), ('thick',), ('glow',), ('obj', 'ptidx', 't')]


@lru_cache(maxsize=1024)
def metadata(tokens, coord2=False):
    """CPU 원정답을 엄격 문법으로 읽는다. 로그잇 위치는 BOS 다음부터0이다.
    coord2: 두 단계 좌표 토큰열(seq_coord2)을 그 문법(grammar2)으로 읽는다. 종료 비교의 계속 후보도 C 토큰 범위가 된다."""
    if not tokens or tokens[0] != K.TOK['BOS'] or tokens[-1] != K.TOK['EOS'] or tokens.count(K.TOK['EOS']) != 1:
        raise ValueError('완전한 BOS…EOS 정답 하나가 필요하다')
    grammar = C2.grammar2(strict=True) if coord2 else K.grammar(strict=True)
    allowed = next(grammar)
    stop, fields = [], []
    for i, token in enumerate(tokens):
        specs, lo, hi, field = allowed
        fields.append(K.FID[field] if token >= K.OFF else K.FID['spec'])
        if i and K.TOK['EOS'] in specs:
            stop.append((i-1, tuple(sorted(specs)), lo, hi, token == K.TOK['EOS']))
        try:
            allowed = grammar.send(token)
        except StopIteration:
            if i != len(tokens)-1:
                raise ValueError('종료 뒤에 정답 토큰이 있다')
    types = {K.TOK[n] for n in K.TYPES.values()}
    starts = [i for i, token in enumerate(tokens) if token in types]
    first = None
    if starts:
        begin = starts[0]
        ends = types | {K.TOK[n] for n in ('LAYER', 'FILL', 'EOS')}
        end = next(i for i in range(begin+1, len(tokens)) if tokens[i] in ends)
        first = begin-1, end-1
    if not stop or sum(s[-1] for s in stop) != 1:
        raise ValueError('문법상 종료할 수 있는 정답 끝이 정확히 하나여야 한다')
    return tuple(stop), first, tuple(fields)


def balanced_stop(logits, records):
    """합법한 종료 자리에서 EOS 대 실제 합법한 나머지 후보. 양성/음성을 장별 균형 평균한다."""
    batch, length, vocab = logits.shape
    groups = {}
    for b, record in enumerate(records):
        for pos, specs, lo, hi, positive in record[0]:
            groups.setdefault((specs, lo, hi), []).append((b, pos, positive))
    losses, rows, labels = [], [], []
    flat = logits.float().reshape(-1, vocab)
    for (specs, lo, hi), entries in groups.items():
        ids = list(specs) + list(range(K.OFF+lo, K.OFF+hi+1)) if lo <= hi else list(specs)
        eos = ids.index(K.TOK['EOS'])
        if len(ids) < 2:
            raise ValueError('종료 비교에 계속 후보가 없다')
        ix = torch.tensor([b*length+p for b, p, _ in entries], device=logits.device)
        legal = flat.index_select(0, ix).index_select(1, torch.tensor(ids, device=logits.device))
        end = legal[:, eos]
        continuation = torch.logsumexp(torch.cat([legal[:, :eos], legal[:, eos+1:]], 1), 1)
        target = torch.tensor([p for _, _, p in entries], device=logits.device)
        losses.append(torch.where(target, F.softplus(continuation-end), F.softplus(end-continuation)))
        rows.extend(b for b, _, _ in entries)
        labels.extend(p for _, _, p in entries)
    values = torch.cat(losses)
    rows = torch.tensor(rows, device=logits.device)
    labels = torch.tensor(labels, device=logits.device)
    means, present = [], []
    for flag in (True, False):
        select = labels == flag
        counts = torch.bincount(rows[select], minlength=batch).to(values.dtype)
        sums = values.new_zeros(batch).scatter_add(0, rows[select], values[select])
        means.append(sums/counts.clamp_min(1))
        present.append((counts > 0).to(values.dtype))
    return ((means[0]+means[1])/(present[0]+present[1]).clamp_min(1)).mean()


def objective(logits, tgt, fld, full_tokens, mode='balanced-v1', diagnostics=False):
    """순전파/기울기만 계산한다. 생성 상한·문법·공식 합격선·모델 구조는 바꾸지 않는다."""
    from seq_train import token_loss
    if mode not in WEIGHTS:
        raise ValueError('알 수 없는 목적함수')
    per, mask = token_loss(logits, tgt, fld)
    base = (per*mask.float()).sum()/mask.sum()
    zero = base*0
    if mode == 'token-v1' and not diagnostics:
        return base, dict(token=base, stop=zero, first_object=zero, appearance=zero)
    coord2 = logits.shape[-1] > K.VOCAB   # 두 단계 좌표 모델(어휘 C2.VOCAB2)
    records = [metadata(tuple(int(t) for t in tokens), coord2) for tokens in full_tokens]
    if len(records) != len(tgt):
        raise ValueError('목적함수의 장 수가 다르다')
    first, appearance = [], []
    for b, (record, tokens) in enumerate(zip(records, full_tokens)):
        size = len(tokens)-1
        if size > tgt.shape[1] or not torch.equal(tgt[b, :size], torch.as_tensor(tokens[1:], device=tgt.device)):
            raise ValueError('원정답과 BOS를 뺀 학습 표적이 다르다')
        expected_fields = torch.tensor(record[2][1:], device=fld.device)
        if not torch.equal(fld[b, :size], expected_fields):
            raise ValueError('정답 문법과 학습 칸 번호가 다르다')
        if not (tgt[b, size:] == K.TOK['PAD']).all():
            raise ValueError('정답 뒤의 패딩이 잘못됐다')
        if record[1] is not None:
            lo, hi = record[1]
            first.append(per[b, lo:hi].mean())
        parts = []
        for fields in APPEARANCE:
            selected = torch.zeros(size, dtype=torch.bool, device=fld.device)
            for field in fields:
                selected |= fld[b, :size] == K.FID[field]
            if selected.any():
                parts.append(per[b, :size][selected].mean())
        if parts:
            appearance.append(torch.stack(parts).mean())
    stop = balanced_stop(logits, records)
    first = torch.stack(first).mean() if first else zero
    appearance = torch.stack(appearance).mean() if appearance else zero
    ws, wf, wa = WEIGHTS[mode]
    return base+ws*stop+wf*first+wa*appearance, dict(token=base, stop=stop, first_object=first, appearance=appearance)
