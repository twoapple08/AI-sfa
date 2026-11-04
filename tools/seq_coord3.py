"""격자 포인터 좌표(coord3) 변환층 — 2026-11-05 (docs/SEQ-COORD-TWO-LEVEL-DESIGN-2026-11-04.md 끝점 붕괴 대책).

꺾은선 CPU 비교에서 '그림 특징 격자 칸을 가리키는' 표현(ptr)이 앞 좌표 베끼기·끝점 붕괴를 가장 줄였다.
화면 안 점(x, y 둘 다 일반 수이고 화면 0–100% 안)은 X 자리 하나에서
  CELL(격자 칸, 모델이 그림 특징과의 내적으로 점수) → FX(칸 안 x) → FY(칸 안 y)
세 토큰으로 적는다. Y 자리는 따로 적지 않는다. 화면 밖·BIG·나머지 좌표는 coord2(C→F)를 그대로 쓴다.

칸 경계는 좌표 토큰 단위에 맞춘다(왕복이 정확하도록): 좌표 수 v ↔ X% = XMIN + v·XSTEP, 화면 0–100% = v 2000–5999.
  x칸 i: v ∈ [2000 + 50i, 2000 + 50(i+1)),  i = 0..79 (FX 0..49)
  y칸 j: v ∈ [2000 + ⌊4000j/45⌋, 2000 + ⌊4000(j+1)/45⌋),  j = 0..44 (FY 0..88/89)
격자 80×45는 seq_train 기본(in_w 640, stride 8)의 특징 격자와 같다(칸 = 메모리 위치 j*80+i).
"""
import numpy as np

import sfa_tokens as K
import seq_coord2 as C2

GX, GY = 80, 45
NCELL = GX * GY
V0 = int(round((0 - K.XMIN) / K.XSTEP))          # 화면 0% = 2000
VSPAN = int(round(100 / K.XSTEP))                  # 4000
XB = [V0 + VSPAN * i // GX for i in range(GX + 1)]  # 칸 경계(정수)
YB = [V0 + VSPAN * j // GY for j in range(GY + 1)]
NFX = max(b - a for a, b in zip(XB, XB[1:]))       # 50
NFY = max(b - a for a, b in zip(YB, YB[1:]))       # 89
CELL0 = C2.VOCAB2
FX0 = CELL0 + NCELL
FY0 = FX0 + NFX
VOCAB3 = FY0 + NFY
COORD = K.FID['coord']


def _bin(bounds, v):
    import bisect
    i = bisect.bisect_right(bounds, v) - 1
    return i if 0 <= i < len(bounds) - 1 else None


def cell_of(vx, vy):
    """좌표 수 (vx, vy) → (칸, fx, fy) 또는 화면 밖이면 None."""
    i, j = _bin(XB, vx), _bin(YB, vy)
    if i is None or j is None:
        return None
    return j * GX + i, vx - XB[i], vy - YB[j]


def value_of(cell, fx, fy):
    j, i = divmod(cell, GX)
    return XB[i] + fx, YB[j] + fy


def _coord_starts(tok):
    """원 토큰열에서 좌표 자리를 문법으로 찾는다: [(위치, 축 0=x 1=y, 일반수 여부)]."""
    g = K.grammar()
    al = next(g)
    out, expect_y, i = [], False, 0
    while i < len(tok):
        t = int(tok[i])
        specs, lo, hi, field = al
        if field == 'coord' and (t >= K.OFF or t == K.TOK['BIG']):
            out.append((i, 1 if expect_y else 0, t >= K.OFF))
            expect_y = not expect_y
        try:
            al = g.send(t)
        except StopIteration:
            break
        i += 1
    return out


def to_three(tok, fld):
    """기존 (tok, fld) 한 장 → coord3 (tok, fld). 화면 안 (x,y) 쌍은 CELL·FX·FY, 나머지 좌표는 coord2."""
    tok = np.asarray(tok)
    fld = np.asarray(fld)
    starts = _coord_starts(tok)
    plan = {}                                       # 위치 → 대체 토큰들(빈 목록 = 지움)
    for (i, ax, plain), nxt in zip(starts, starts[1:] + [None]):
        if ax != 0 or nxt is None or nxt[1] != 1:
            continue
        j = nxt[0]
        if plain and nxt[2] and j == i + 1:
            c = cell_of(int(tok[i]) - K.OFF, int(tok[j]) - K.OFF)
            if c is not None:
                plan[i] = [CELL0 + c[0], FX0 + c[1], FY0 + c[2]]
                plan[j] = []
    out_t, out_f = [], []
    for k, (t, f) in enumerate(zip(tok.tolist(), fld.tolist())):
        if k in plan:
            out_t += plan[k]
            out_f += [COORD] * len(plan[k])
        elif f == COORD and K.OFF <= t < K.VOCAB:
            v = t - K.OFF
            out_t += [C2.C0 + v // C2.FINE, C2.F0 + v % C2.FINE]
            out_f += [COORD, COORD]
        else:
            out_t.append(t)
            out_f.append(f)
    return np.array(out_t, dtype=tok.dtype), np.array(out_f, dtype=fld.dtype)


def merge(toks):
    """coord3 토큰열 → 기존 토큰열. 짝이 깨진 끝부분은 버린다."""
    out, i, toks = [], 0, [int(t) for t in toks]
    while i < len(toks):
        t = toks[i]
        if CELL0 <= t < FX0:
            if i + 2 < len(toks) and FX0 <= toks[i + 1] < FY0 and FY0 <= toks[i + 2] < VOCAB3:
                vx, vy = value_of(t - CELL0, toks[i + 1] - FX0, toks[i + 2] - FY0)
                out += [K.OFF + vx, K.OFF + vy]
            i += 3
            continue
        if C2.C0 <= t < C2.F0:
            if i + 1 < len(toks) and C2.F0 <= toks[i + 1] < C2.VOCAB2:
                out.append(K.OFF + (t - C2.C0) * C2.FINE + toks[i + 1] - C2.F0)
            i += 2
            continue
        out.append(t)
        i += 1
    return out


def grammar3(strict=False):
    """sfa_tokens.grammar()를 감싼다. 물음은 (허용 특수 토큰, lo, hi, field[, (extra_lo, extra_hi)]), 수 범위는 OFF 기준.
    다섯째 항목은 같은 자리에서 함께 허용하는 둘째 범위(CELL)다 — seq_train.allowed_mask가 읽는다.
    x 자리: 특수 토큰 + C 범위 + (화면이 허용 범위 안이면) CELL 범위. CELL을 고르면 FX·FY를 묻고 x·y를 한 번에 보낸다.
    C를 고르면 F를 묻고 x를 보낸 뒤 y 자리는 C→F만. BIG은 원래 문법으로(세 자리 'big' 물음이 이어진다)."""
    g = K.grammar(strict=strict)
    al = next(g)
    expect_y = False
    NC, NF = C2._NC, C2._NF

    def two_level(specs, lo, hi):
        c = yield (specs, NC + lo // C2.FINE, NC + hi // C2.FINE, 'coord')
        if C2.C0 <= c < C2.F0:
            ci = c - C2.C0
            flo = lo % C2.FINE if ci == lo // C2.FINE else 0
            fhi = hi % C2.FINE if ci == hi // C2.FINE else C2.FINE - 1
            f = yield (frozenset(), NF + flo, NF + fhi, 'coord')
            return K.OFF + ci * C2.FINE + (f - C2.F0), True
        return c, False

    while True:
        specs, lo, hi, field = al[:4]
        if field == 'coord' and hi >= lo and not expect_y:
            cell_ok = lo <= V0 and hi >= V0 + VSPAN - 1
            c = yield (specs, NC + lo // C2.FINE, NC + hi // C2.FINE, 'coord',
                       (CELL0 - K.OFF, FX0 - 1 - K.OFF) if cell_ok else None)
            if CELL0 <= c < FX0:
                j, i = divmod(c - CELL0, GX)
                fx = yield (frozenset(), FX0 - K.OFF, FX0 - K.OFF + XB[i + 1] - XB[i] - 1, 'coord')
                fy = yield (frozenset(), FY0 - K.OFF, FY0 - K.OFF + YB[j + 1] - YB[j] - 1, 'coord')
                vx, vy = value_of(c - CELL0, fx - FX0, fy - FY0)
                try:
                    al = g.send(K.OFF + vx)
                    al = g.send(K.OFF + vy)
                except StopIteration:
                    return
                continue
            if C2.C0 <= c < C2.F0:
                ci = c - C2.C0
                flo = lo % C2.FINE if ci == lo // C2.FINE else 0
                fhi = hi % C2.FINE if ci == hi // C2.FINE else C2.FINE - 1
                f = yield (frozenset(), NF + flo, NF + fhi, 'coord')
                t = K.OFF + ci * C2.FINE + (f - C2.F0)
                expect_y = True
            else:
                t = c
                expect_y = c == K.TOK['BIG']          # BIG x 뒤에는 y가 온다. 다른 특수 토큰(GLOW·LINK·끝)은 좌표가 아니다
        elif field == 'coord' and hi >= lo:            # y 자리
            t, _ = yield from two_level(specs, lo, hi)
            expect_y = False
        else:
            t = yield al
        try:
            al = g.send(t)
        except StopIteration:
            return
