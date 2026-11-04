"""두 단계 좌표 표현(coord2) 변환층 — 2026-11-04 설계(docs/SEQ-COORD-TWO-LEVEL-DESIGN-2026-11-04.md).

기존 토큰 체계(sfa_tokens)는 그대로 둔다. 좌표 칸(field 'coord')의 범위 안 수 토큰 하나를
거친 칸 C(v // FINE)와 세부 칸 F(v % FINE) 두 토큰으로 바꾼다. 새 토큰은 기존 어휘 뒤에 붙인다:
  C c → K.VOCAB + c            (c = 0..COARSE-1)
  F f → K.VOCAB + COARSE + f   (f = 0..FINE-1)
BIG과 BIG 뒤 세 자리(field 'big'), 다른 분야(색·굵기·T·번호)는 바꾸지 않는다.
학습 자료는 불러올 때 to_two로 바꾸고, 생성은 grammar2로 두 단계로 고른 뒤 merge로 기존 토큰열로 합친다.
그래서 판정·채점·디코딩(기존 토큰 공간)은 바뀌지 않는다.
"""
import numpy as np

import sfa_tokens as K

FINE = 64
COARSE = K.NUM // FINE          # 128
VOCAB2 = K.VOCAB + COARSE + FINE
C0 = K.VOCAB                    # 첫 C 토큰
F0 = K.VOCAB + COARSE           # 첫 F 토큰
_NC = K.NUM                     # allowed_mask의 lo/hi(OFF 기준)로 쓰는 C 시작 = C0 - K.OFF
_NF = K.NUM + COARSE            # 같은 기준의 F 시작
COORD = K.FID['coord']

assert COARSE * FINE == K.NUM


def to_two(tok, fld):
    """기존 (tok, fld) 한 장 → 두 단계 (tok, fld). 좌표 범위 안 수만 둘로 나눈다(C·F 모두 field 'coord')."""
    tok = np.asarray(tok)
    fld = np.asarray(fld)
    hit = (fld == COORD) & (tok >= K.OFF) & (tok < K.VOCAB)
    rep = np.where(hit, 2, 1)
    out_t = np.repeat(tok, rep).astype(tok.dtype)
    out_f = np.repeat(fld, rep).astype(fld.dtype)
    pos = np.cumsum(rep) - rep          # 각 원래 토큰이 새 배열에서 시작하는 자리
    v = tok[hit] - K.OFF
    out_t[pos[hit]] = C0 + v // FINE
    out_t[pos[hit] + 1] = F0 + v % FINE
    return out_t, out_f


def merge(toks):
    """두 단계 토큰열 → 기존 토큰열(C 다음 F를 하나의 수로). 짝이 깨진 C는 버린다(생성이 한도에서 끊긴 경우)."""
    out = []
    i = 0
    while i < len(toks):
        t = int(toks[i])
        if C0 <= t < F0:
            if i + 1 < len(toks) and F0 <= int(toks[i + 1]) < VOCAB2:
                out.append(K.OFF + (t - C0) * FINE + int(toks[i + 1]) - F0)
            i += 2
            continue
        out.append(t)
        i += 1
    return out


def grammar2(strict=False):
    """sfa_tokens.grammar()를 감싼다. 좌표 자리 하나를 C 자리 → F 자리 두 번의 물음으로 바꾼다.
    물음 형식은 원래와 같다: (허용 특수 토큰, lo, hi, field), 수 범위는 OFF 기준(allowed_mask와 같은 방식)."""
    g = K.grammar(strict=strict)
    al = next(g)
    while True:
        specs, lo, hi, field = al
        if field == 'coord' and hi >= lo:
            c = yield (specs, _NC + lo // FINE, _NC + hi // FINE, 'coord')
            if C0 <= c < F0:
                ci = c - C0
                flo = lo % FINE if ci == lo // FINE else 0
                fhi = hi % FINE if ci == hi // FINE else FINE - 1
                f = yield (frozenset(), _NF + flo, _NF + fhi, 'coord')
                t = K.OFF + ci * FINE + (f - F0)
            else:
                t = c                                   # BIG 등 특수 토큰은 원래 문법으로
        else:
            t = yield al
        try:
            al = g.send(t)
        except StopIteration:
            return
