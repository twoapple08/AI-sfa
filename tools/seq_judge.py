#!/usr/bin/env python3
"""판정 장치(2026-11-01, docs/JUDGE-CRITERIA-FINAL-2026-10-31.md §2): 입력 교환 생성 대조 + 생성 건전성 + A·B·외움 기준선.

평가 목록(manifest)은 학습 전에 고정해 저장소에 둔다(data/judge_manifest.json — 파일 이름·장 번호만, 원본 그림 없음).
- 위치 시험 파일(학습 파일 10개 중 1개 = seq_data --every 10과 같은 목록)마다, 공식 두 방향 모두 잘림 없고·비어 있지 않고·길이 한도 안인
  장에서 1장을 사전 고정 난수로 고른다(진단 4방향 모두 잘림 없는 장을 먼저, 없으면 공식 두 방향만 맞는 장).
- 두 정답(옮긴 정답 Gd, 원래 자리 G0)은 (파일, Frame.Position)으로 연결한다.
- 작품 묶음: 정확 사본(파일 바이트·전체 토큰·고른 장 토큰 해시)만 자동으로 묶는다. 나머지는 '미확정'으로 기록(§5).
사용:
  python seq_judge.py manifest [--out data/judge_manifest.json]      평가 목록 만들기(모델 출력을 보기 전에)
  python seq_judge.py build 출력폴더 [--W 640] [--stage-w 1920,1280,854]   목록대로 4방향 영상·정답 자료(judge.npz)
  python seq_judge.py baseline 출력폴더                               외움 기준선(원래 자리 정답을 그대로 냈을 때)
"""
import argparse
import hashlib
import json
import math
import os
import random
import statistics
import sys
import time
import zipfile
import xml.etree.ElementTree as ET

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sfa_objscore as OS  # noqa: E402
import sfa_tokens as K  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
MANIFEST = os.path.join(HERE, '..', 'data', 'judge_manifest.json')
JUDGE_VERSION = 1
# 이동 4방향(배율 모두 1.05, GPT 2차 §B). 0·1 = 공식 반대 방향 쌍, 2·3 = 축별 진단용(별도 합격 기회 아님)
DIRS = ((6.0, 4.0, 1.05), (-6.0, -4.0, 1.05), (6.0, -4.0, 1.05), (-6.0, 4.0, 1.05))
OFFICIAL = (0, 1)
SEED = 20261101          # 장 고르기 고정 난수(모델 출력을 보기 전에 정함)
TIE = 0.5                # 동점 범위: |Δ| ≤ 0.5점(0–100 부분 점수). 사용자 확정(11-01, 첫 판정 전) — 결과를 본 뒤 바꾸지 않는다
ALPHA = 0.025            # 공식 시점(최초 끝·연장 끝)마다 단측
EVERY = 5            # 위치 시험 후보 = 학습 파일 목록[::5](11-01: [::10]은 독립 단위 22개뿐이라 검정력 부족 → 파일 수를 늘림, 모델 출력을 보기 전 결정)
MAXLEN = 2048
BAD_FRAC = 0.10          # 건전성: 비어 있지 않은 정답 장 중 '빈 출력 ∪ 길이 한도 미완료' ≤ 10%(정수 판정)
TYPE_TOKS = {K.TOK[v] for v in K.TYPES.values()}


# ---------- 평가 목록 ----------

def transform(root, d):
    dx, dy, sc = d
    for p in root.iter('AP'):
        p.set('X', repr((float(p.get('X')) - 50) * sc + 50 + dx))
        p.set('Y', repr((float(p.get('Y')) - 50) * sc + 50 + dy))
    return root


def n_objs(toks):
    return sum(t in TYPE_TOKS for t in toks)


def _inside(xy, typ, hwr):
    """오브젝트가 화면(0–100%) 안에 다 있는가. 원은 두 점(지름 끝)으로 만든 원의 경계 상자를 화면 화소 비율로 본다."""
    if typ == '2' and len(xy) >= 2:
        (x0, y0), (x1, y1) = xy[:2]
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2 * hwr
        r = math.hypot(x1 - x0, (y1 - y0) * hwr) / 2
        return cx - r >= 0 and cx + r <= 100 and cy - r >= 0 and cy + r <= 100 * hwr
    return all(0 <= x <= 100 and 0 <= y <= 100 for x, y in xy)


def _vis_objs(seq, fr):
    """정답 변환이 남기는(보이거나 면에 쓰이는) 오브젝트의 (TypeId, 점들)."""
    fill = {s.get('ObjId') for r in fr.findall('FR') if K._alpha(r.get('Color')) > 0 for s in r.findall('FS')}
    out = []
    for _, a in K.order_objects(seq, fr):
        if K._alpha(a.get('Color')) > 0 or K.style_of(a)[2] is not None or a.get('ID') in fill:
            out.append((a.get('TypeId'), [(float(p.get('X')), float(p.get('Y'))) for p in a.findall('AP')]))
    return out


def clipped(orig, moved, hwr):
    """이동 때문에 잘린 오브젝트 수: 원래 화면 안에 다 있던 것이 이동 뒤 화면 밖으로 걸침(원래부터 화면 밖에 걸친 것은 이동 탓이 아님)."""
    return sum(_inside(xy0, t, hwr) and not _inside(xy1, t, hwr) for (t, xy0), (_, xy1) in zip(orig, moved))


def frame_rows(rel, root_bytes, maxlen=MAXLEN):
    """파일 한 개의 장마다 방향별 상태."""
    base = ET.fromstring(root_bytes)
    hwr = float(base.get('HeightWidthRatio') or 0.5625) or 0.5625
    moved = [transform(ET.fromstring(root_bytes), d) for d in DIRS]
    frs0, frsd = base.findall('Frame'), [m.findall('Frame') for m in moved]
    rows = []
    for k, fr in enumerate(frs0):
        t0, _ = K.encode(base, fr)
        vis0 = _vis_objs(base, fr)
        row = dict(index=k, pos=int(fr.get('Position')), len0=len(t0), n0=n_objs(t0), h0=hashlib.sha1(np.array(t0, np.int32).tobytes()).hexdigest()[:16],
                   dirs=[])
        for j, m in enumerate(moved):
            frd = frsd[j][k]
            t, _ = K.encode(m, frd)
            try:
                K.fields(t)
                ok_f = True
            except ValueError:
                ok_f = False
            row['dirs'].append(dict(len=len(t), n=n_objs(t), clip=clipped(vis0, _vis_objs(m, frd), hwr), fields_ok=ok_f))
        rows.append(row)
    return rows, hwr


def eligible(row, dirs, maxlen=MAXLEN):
    """잘림 없음(이동 탓 잘림 0, 남는 오브젝트 수 같음) · 비어 있지 않음 · 길이 한도 안 — 주어진 방향 모두."""
    for j in dirs:
        d = row['dirs'][j]
        if d['clip'] or d['n'] != row['n0'] or d['n'] == 0 or d['len'] > maxlen or not d['fields_ok']:
            return False
    return row['len0'] <= maxlen


def reason(row, maxlen=MAXLEN):
    ds = [row['dirs'][j] for j in OFFICIAL]
    if row['n0'] == 0 or any(d['n'] == 0 for d in ds):
        return '빈 장'
    if row['len0'] > maxlen or any(d['len'] > maxlen for d in ds):
        return '길이 한도 초과'
    if any(not d['fields_ok'] for d in ds):
        return '문법 칸 오류'
    return '이동으로 잘림'


def build_manifest(files, root_dir, maxlen=MAXLEN):
    ents, excl, fhash = [], [], {}
    for rel in files:
        try:
            with open(os.path.join(root_dir, rel), 'rb') as fh:
                raw = fh.read()
            with zipfile.ZipFile(os.path.join(root_dir, rel)) as z:
                xml = z.read(z.namelist()[0])
        except Exception as e:
            excl.append(dict(file=rel, reason='열기 실패:' + type(e).__name__))
            continue
        rows, hwr = frame_rows(rel, xml, maxlen)
        full = hashlib.sha1(''.join(r['h0'] for r in rows).encode()).hexdigest()[:16]
        fhash[rel] = (hashlib.sha1(raw).hexdigest()[:16], full)
        all4 = [r for r in rows if eligible(r, range(len(DIRS)), maxlen)]
        off2 = [r for r in rows if eligible(r, OFFICIAL, maxlen)]
        pool = all4 or off2
        if not pool:
            why = {}
            for r in rows:
                why[reason(r, maxlen)] = why.get(reason(r, maxlen), 0) + 1
            excl.append(dict(file=rel, reason='고를 장 없음', frames=len(rows), why=why))
            continue
        r = random.Random(f'{SEED}:{rel}').choice(pool)
        ents.append(dict(file=rel, pos=r['pos'], index=r['index'], hwr=hwr, frames=len(rows), pool=len(pool), pool_kind='4방향' if all4 else '공식 2방향',
                         all4=bool(all4), len0=r['len0'], n0=r['n0'], frame_hash=r['h0'], file_sha=fhash[rel][0], tok_hash=fhash[rel][1],
                         dirs=r['dirs']))
    # 작품 묶음: 정확 사본만 자동(파일 바이트·전체 토큰·고른 장 토큰이 같은 것끼리 합침). 나머지는 미확정
    par = list(range(len(ents)))

    def find(i):
        while par[i] != i:
            par[i] = par[par[i]]
            i = par[i]
        return i
    for key in ('file_sha', 'tok_hash', 'frame_hash'):
        seen = {}
        for i, e in enumerate(ents):
            if e[key] in seen:
                par[find(i)] = find(seen[e[key]])
            else:
                seen[e[key]] = i
    roots = {}
    for i, e in enumerate(ents):
        e['group'] = roots.setdefault(find(i), len(roots))
    groups = [dict(id=g, files=[e['file'] for e in ents if e['group'] == g],
                   status='정확 사본' if sum(e['group'] == g for e in ents) > 1 else '단독(변형 여부 미확정)') for g in range(len(roots))]
    return dict(version=JUDGE_VERSION, dirs=DIRS, official=OFFICIAL, seed=SEED, tie=TIE, alpha=ALPHA, every=EVERY, maxlen=maxlen,
                files=len(files), n_entries=len(ents), n_units=len(groups), entries=ents, excluded=excl, groups=groups,
                note='묶음 판정은 정확 사본만 자동. 변형(같은 작품의 다른 판) 판정은 미구현 — §5')


# ---------- 통계 ----------

def binom_tail(k, n):
    """P(X ≥ k), X ~ Bin(n, 1/2)."""
    return sum(math.comb(n, i) for i in range(k, n + 1)) / 2 ** n if n else 1.0


def need_wins(n, alpha=ALPHA):
    """고정 N, 동점은 비승리: P(X ≥ k) ≤ α인 가장 작은 k(없으면 n+1)."""
    for k in range(n + 1):
        if binom_tail(k, n) <= alpha:
            return k
    return n + 1


def vote(delta, tie=TIE):
    if delta is None:
        return 'fail'   # 평가 실패(OOM 등): 승리로 세지 않고, 조용히 빼지도 않는다(N에 남김)
    return 'win' if delta > tie else ('loss' if delta < -tie else 'tie')


def sign_test(deltas_by_unit, tie=TIE, alpha=ALPHA):
    votes = [vote(d, tie) for d in deltas_by_unit]
    n = len(votes)
    w = votes.count('win')
    ds = [d for d in deltas_by_unit if d is not None]
    return dict(N=n, win=w, tie=votes.count('tie'), loss=votes.count('loss'), fail=votes.count('fail'),
                need=need_wins(n, alpha), p=binom_tail(w, n), passed=n > 0 and w >= need_wins(n, alpha),
                delta_median=statistics.median(ds) if ds else None, delta_mean=statistics.fmean(ds) if ds else None)


def health(rows, frac=BAD_FRAC):
    """생성 건전성(§2-1). rows: 생성마다 dict(ans_n, pred_n, done, oom). 정답이 빈 장은 manifest에서 이미 뺐다."""
    tgt = [r for r in rows if r['ans_n'] > 0]
    bad = sum(1 for r in tgt if not r['oom'] and (r['pred_n'] == 0 or not r['done']))
    oom = sum(1 for r in tgt if r['oom'])
    limit = int(math.floor(frac * len(tgt) + 1e-9))
    ratios = [r['pred_n'] / r['ans_n'] for r in tgt if not r['oom']]
    return dict(n=len(tgt), empty=sum(1 for r in tgt if not r['oom'] and r['pred_n'] == 0), unfinished=sum(1 for r in tgt if not r['oom'] and not r['done']),
                bad=bad, oom=oom, limit=limit, passed=bool(tgt) and bad + oom <= limit,   # OOM은 재시도 못 했으면 실패로 센다
                obj_ratio_median=statistics.median(ratios) if ratios else None, obj_ratio_out=sum(1 for x in ratios if not 0.5 <= x <= 2))


# ---------- 자료 ----------

def load_manifest(path=MANIFEST):
    m = json.load(open(path, encoding='utf-8'))
    if m.get('version') != JUDGE_VERSION or [list(d) for d in m['dirs']] != [list(d) for d in DIRS]:
        raise SystemExit(f'평가 목록 판·방향이 코드와 다름: {path}')
    return m


def build_data(m, root_dir, out_dir, W=640, stage_ws=(), n_stage=6):
    """목록의 장마다 4방향 그림(파일 비율 렌더 → H.264 한 장 압축·복원 → 입력 크기) + 방향별 정답 토큰 + 원래 자리 정답 토큰.
    압축 세기는 장마다 고정 난수, 네 방향 같은 값(입력 교환이 화질 차이에 좌우되지 않게).
    stage_ws: 해상도 단계 폭마다 공식 방향 0 그림을 앞 n_stage장만 따로(현재 단계 해상도 대 기본 입력 비교용)."""
    import cv2
    import sfa_render as R
    import vec_data as V
    os.makedirs(out_dir, exist_ok=True)
    H = W * 9 // 16
    imgs, toks, toks0, stage = [], [], [], {w: [] for w in stage_ws}
    for ei, e in enumerate(m['entries']):
        with zipfile.ZipFile(os.path.join(root_dir, e['file'])) as z:
            xml = z.read(z.namelist()[0])
        base = ET.fromstring(xml)
        fr0 = base.findall('Frame')[e['index']]
        if int(fr0.get('Position')) != e['pos']:
            raise SystemExit(f"평가 목록과 파일이 다름: {e['file']} 장 {e['index']}")
        t0, _ = K.encode(base, fr0)
        if hashlib.sha1(np.array(t0, np.int32).tobytes()).hexdigest()[:16] != e['frame_hash']:
            raise SystemExit(f"정답 토큰이 평가 목록과 다름(파일 또는 토큰 변환이 바뀜): {e['file']}")
        toks0.append(np.array(t0, np.int16))
        crf = random.Random(f"{SEED}:crf:{e['file']}").randint(23, 35)
        hwr = e['hwr']
        for j, d in enumerate(DIRS):
            root = transform(ET.fromstring(xml), d)
            fr = root.findall('Frame')[e['index']]
            t, _ = K.encode(root, fr)
            toks.append(np.array(t, np.int16))

            def shot(w):
                hr = max(2, int(round(w * hwr / 2)) * 2)
                R.PARAMS['pad'] = 0.0
                R.PARAMS['thick_mul'] = w / 1920
                im = V.encode_decode([R.render_frame(root, fr, w, hr)], crf)[0]
                h = w * 9 // 16
                return im if hr == h else cv2.resize(im, (w, h), interpolation=cv2.INTER_AREA if hr > h else cv2.INTER_LINEAR)
            imgs.append(shot(W))
            if j == 0 and ei < n_stage:
                for w in stage_ws:
                    stage[w].append(shot(w))
        print(f"{ei + 1}/{len(m['entries'])} {e['file']} 장 {e['pos']} crf {crf}", flush=True)
    cat = lambda xs: (np.concatenate(xs) if xs else np.zeros(0, np.int16), np.cumsum([0] + [len(x) for x in xs]))  # noqa: E731
    tk, off = cat(toks)
    tk0, off0 = cat(toks0)
    meta = dict(version=JUDGE_VERSION, W=W, H=H, vocab=K.VOCAB, dirs=DIRS, manifest_sha=manifest_sha(m), stage_ws=list(stage_ws), n_stage=n_stage,
                entries=[dict(file=e['file'], pos=e['pos'], hwr=e['hwr'], group=e['group'], all4=e['all4']) for e in m['entries']])
    extra = {f'stage{w}': np.stack(v) for w, v in stage.items() if v}
    tmp = os.path.join(out_dir, 'judge.npz.tmp')
    with open(tmp, 'wb') as fh:
        np.savez_compressed(fh, img=np.stack(imgs), tok=tk, off=off, tok0=tk0, off0=off0, meta=json.dumps(meta, ensure_ascii=False), **extra)
    os.replace(tmp, os.path.join(out_dir, 'judge.npz'))


def manifest_sha(m):
    return hashlib.sha256(json.dumps(m['entries'], sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]


class JudgeSet:
    """judge.npz 읽기. 그림 i*4+d = 장 i의 방향 d."""

    def __init__(self, folder, in_w=None):
        import cv2
        z = np.load(os.path.join(folder, 'judge.npz'))
        self.meta = json.loads(str(z['meta']))
        if self.meta.get('version') != JUDGE_VERSION or self.meta['vocab'] != K.VOCAB:
            raise SystemExit(f'판정 자료 판·어휘가 코드와 다름: {folder}')
        img = z['img']
        if in_w and img.shape[2] != in_w:
            img = np.stack([cv2.resize(x, (in_w, in_w * 9 // 16), interpolation=cv2.INTER_AREA) for x in img])
        self.img = img
        self.ents = self.meta['entries']
        nd = len(self.meta['dirs'])
        tok, off = z['tok'], z['off']
        self.tok = [[tok[off[i * nd + d]:off[i * nd + d + 1]].astype(np.int64) for d in range(nd)] for i in range(len(self.ents))]
        tok0, off0 = z['tok0'], z['off0']
        self.tok0 = [tok0[off0[i]:off0[i + 1]].astype(np.int64) for i in range(len(self.ents))]
        self.stage = {int(k[5:]): z[k] for k in z.files if k.startswith('stage')}

    def __len__(self):
        return len(self.ents)

    def image(self, i, d):
        return self.img[i * len(self.meta['dirs']) + d]


# ---------- 평가 ----------

def S(pred_toks, ans_toks, hwr):
    """위치·형상 부분 점수(0–100)와 엄격 합산용 수."""
    sc = OS.score(K.decode([int(t) for t in pred_toks]), K.decode([int(t) for t in ans_toks]), hwr=hwr)
    return 100.0 * sc['partial'], sc


def memo_baseline(js, dirs=None):
    """완벽하게 외운 AI(원래 자리 정답을 그대로 냄) vs 옮긴 정답 — 이 평가 목록·방향·집계로 다시 계산(GPT 2차: 예전 15.88을 재사용하지 않음)."""
    dirs = list(dirs if dirs is not None else range(len(js.meta['dirs'])))
    v = [S(js.tok0[i], js.tok[i][d], js.ents[i]['hwr'])[0] for i in range(len(js)) for d in dirs]
    return statistics.fmean(v) if v else None


def evaluate(js, gen, dirs=None, tie=TIE, alpha=ALPHA, memo=None):
    """gen(i, d) → (토큰, 끝냄, 초) 또는 None(메모리 부족 = 평가 실패).
    같은 체크포인트·생성 옵션으로 입력마다 한 번만 생성하고 16칸 표에 재사용한다."""
    nd = len(js.meta['dirs'])
    dirs = list(dirs if dirs is not None else range(nd))
    rows, out = [], {}
    gens = {}
    for i in range(len(js)):
        for d in dirs:
            r = gen(i, d)
            ans_n = n_objs(js.tok[i][d])
            if r is None:
                gens[i, d] = None
                rows.append(dict(ans_n=ans_n, pred_n=0, done=False, oom=True, sec=None, len=None))
            else:
                t, done, sec = r
                gens[i, d] = [int(x) for x in t]
                rows.append(dict(ans_n=ans_n, pred_n=n_objs(t), done=bool(done), oom=False, sec=sec, len=len(t)))
    # 16칸 표: tab[i][g][p] = S(P_p, G_g)
    strict = dict(match=0, pred=0, ans=0)
    f1s = []
    tab = {}
    a_v, b_v = [], []
    for i in range(len(js)):
        hwr = js.ents[i]['hwr']
        for g in dirs:
            for p in dirs:
                if gens[i, p] is None:
                    tab[i, g, p] = None
                    continue
                s, sc = S(gens[i, p], js.tok[i][g], hwr)
                tab[i, g, p] = s
                if g == p:
                    a_v.append(s)
                    for k in strict:
                        strict[k] += sc[k]
                    f1s.append(OS.f1(sc['match'], sc['pred'], sc['ans']))
        for p in dirs:
            if gens[i, p] is not None:
                b_v.append(S(gens[i, p], js.tok0[i], hwr)[0])

    def bid(i, x, y):   # 양방향 Δ(입력 x·y 교환, 정답 Gx·Gy 고정)
        v = (tab.get((i, x, x)), tab.get((i, x, y)), tab.get((i, y, y)), tab.get((i, y, x)))
        return None if None in v else ((v[0] - v[1]) + (v[2] - v[3])) / 2
    # 공식: 파일(묶음)당 한 표 — 묶음 안 파일 Δ 평균, 한 파일이라도 평가 실패면 그 묶음은 실패
    units = {}
    for i, e in enumerate(js.ents):
        units.setdefault(e['group'], []).append(bid(i, *OFFICIAL))
    ud = [None if None in v else statistics.fmean(v) for v in units.values()]
    out['judge'] = sign_test(ud, tie, alpha) if all(d in dirs for d in OFFICIAL) else None
    # 합산 차이(효과 크기): 맞는 입력 점수 평균 − 바꾼 입력 점수 평균(공식 쌍)
    cor = [tab[i, g, g] for i in range(len(js)) for g in OFFICIAL if tab.get((i, g, g)) is not None]
    wro = [tab[i, g, p] for i in range(len(js)) for g, p in (OFFICIAL, OFFICIAL[::-1]) if tab.get((i, g, p)) is not None]
    if out['judge']:
        out['judge']['pooled_diff'] = statistics.fmean(cor) - statistics.fmean(wro) if cor and wro else None
        out['judge']['per_unit'] = [None if d is None else round(d, 3) for d in ud]
    # 축별 진단(4방향일 때만, 4방향 모두 잘림 없는 장만): x만 다른 쌍 (0,3)(2,1), y만 다른 쌍 (0,2)(3,1)
    if len(dirs) == nd == 4:
        keep = [i for i, e in enumerate(js.ents) if e['all4']]
        axis = {}
        for name, pairs in (('x', ((0, 3), (2, 1))), ('y', ((0, 2), (3, 1)))):
            per = []
            for i in keep:
                v = [bid(i, x, y) for x, y in pairs]
                per.append(None if None in v else statistics.fmean(v))
            ok = [v for v in per if v is not None]
            axis[name] = dict(n=len(per), win=sum(vote(v, tie) == 'win' for v in per), tie=sum(vote(v, tie) == 'tie' for v in per),
                              loss=sum(vote(v, tie) == 'loss' for v in per), median=statistics.median(ok) if ok else None)
        out['axis'] = axis
        out['table16'] = [[_mean([tab.get((i, g, p)) for i in keep]) for p in range(4)] for g in range(4)]   # 행 = 정답 방향, 열 = 입력 방향
    out['A'] = _mean(a_v)
    out['B'] = _mean(b_v)
    out['A_minus_B'] = out['A'] - out['B'] if out['A'] is not None and out['B'] is not None else None
    out['memo'] = memo
    out['A_minus_memo'] = out['A'] - memo if out['A'] is not None and memo is not None else None
    out['recall'] = strict['match'] / max(strict['ans'], 1)
    out['precision'] = strict['match'] / max(strict['pred'], 1)
    out['f1'] = 2 * strict['match'] / max(strict['pred'] + strict['ans'], 1)   # 합산(주 점수)
    out['f1_file_mean'] = _mean(f1s)
    out['health'] = health(rows)
    out['gen_time'] = gen_times(rows)
    out['n_entries'] = len(js)
    out['dirs'] = dirs
    return out, gens


def gen_times(rows):
    """실제 생성 시간: 출력 길이 순 셋으로 나눈 중앙값(짧은·중간·긴)."""
    r = sorted((x for x in rows if x['sec'] is not None), key=lambda x: x['len'])
    if not r:
        return None
    k = len(r)
    parts = [r[:k // 3], r[k // 3:2 * k // 3], r[2 * k // 3:]]
    return dict(total_sec=round(sum(x['sec'] for x in r), 1),
                **{n: dict(len_median=statistics.median([x['len'] for x in p]), sec_median=round(statistics.median([x['sec'] for x in p]), 2))
                   for n, p in zip(('short', 'mid', 'long'), parts) if p})


def _mean(v):
    v = [x for x in v if x is not None]
    return statistics.fmean(v) if v else None


def flat(out, pre='judge_'):
    """학습 기록(log.jsonl)에 넣을 평평한 값."""
    j = out.get('judge') or {}
    h = out['health']
    r = {f'{pre}{k}': out[k] for k in ('A', 'B', 'A_minus_B', 'memo', 'A_minus_memo', 'recall', 'precision', 'f1', 'f1_file_mean', 'n_entries')}
    r.update({f'{pre}{k}': j.get(k) for k in ('N', 'win', 'tie', 'loss', 'fail', 'need', 'p', 'passed', 'delta_median', 'delta_mean', 'pooled_diff', 'per_unit')})
    r.update({f'{pre}health_{k}': v for k, v in h.items()})
    r[f'{pre}gen_time'] = out['gen_time']
    if 'axis' in out:
        r[f'{pre}axis'] = out['axis']
        r[f'{pre}table16'] = out['table16']
    return r


def summary_line(out):
    j, h = out.get('judge') or {}, out['health']
    f = lambda v, n=1: '-' if v is None else f'{v:.{n}f}'  # noqa: E731
    return (f"판정: N {j.get('N')} 승 {j.get('win')}/동 {j.get('tie')}/패 {j.get('loss')}/실패 {j.get('fail')} (필요 {j.get('need')}승, p {f(j.get('p'), 4)}, "
            f"{'통과' if j.get('passed') else '미통과'}) Δ중앙 {f(j.get('delta_median'), 2)} 합산차 {f(j.get('pooled_diff'), 2)} | "
            f"A {f(out['A'])} B {f(out['B'])} 외움 {f(out['memo'])} | F1 {f(out['f1'] * 100)}% | "
            f"건전성 {'통과' if h['passed'] else '미통과'}(빈·미완 {h['bad']}+OOM {h['oom']}/{h['n']}, 한도 {h['limit']}, 수 비율 중앙 {f(h['obj_ratio_median'], 2)}·범위 밖 {h['obj_ratio_out']})")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='cmd', required=True)
    m = sub.add_parser('manifest')
    m.add_argument('--out', default=MANIFEST)
    b = sub.add_parser('build')
    b.add_argument('out_dir')
    b.add_argument('--manifest', default=MANIFEST)
    b.add_argument('--W', type=int, default=640)
    b.add_argument('--stage-w', default='1920,1280,854')
    b.add_argument('--n-stage', type=int, default=6)
    c = sub.add_parser('baseline')
    c.add_argument('out_dir')
    a = ap.parse_args()
    import vec_data as V
    if a.cmd == 'manifest':
        files = V.file_list()[::EVERY]
        t0 = time.time()
        res = build_manifest(files, V.ROOT)
        with open(a.out, 'w', encoding='utf-8') as fh:
            json.dump(res, fh, ensure_ascii=False, indent=1)
        print(f"평가 목록: 파일 {res['files']} → 장 {res['n_entries']}, 독립 단위 N {res['n_units']}, 제외 {len(res['excluded'])} "
              f"(4방향 {sum(e['all4'] for e in res['entries'])}) {time.time() - t0:.0f}초 → {a.out}", flush=True)
        for x in res['excluded']:
            print(' 제외', x['file'], x['reason'], x.get('why', ''), flush=True)
    elif a.cmd == 'build':
        mf = load_manifest(a.manifest)
        sw = [int(v) for v in a.stage_w.split(',') if v]
        done = os.path.join(a.out_dir, 'judge.npz')
        if os.path.exists(done):
            try:
                if JudgeSet(a.out_dir).meta['manifest_sha'] == manifest_sha(mf):
                    print('이미 같은 평가 목록으로 만듦 — 건너뜀', a.out_dir, flush=True)
                    return
            except SystemExit:
                pass
        build_data(mf, V.ROOT, a.out_dir, a.W, sw, a.n_stage)
    else:
        js = JudgeSet(a.out_dir)
        print(f'외움 기준선(4방향 평균): {memo_baseline(js):.2f}점, 공식 2방향: {memo_baseline(js, OFFICIAL):.2f}점 ({len(js)}장)', flush=True)


if __name__ == '__main__':
    main()
