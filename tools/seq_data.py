#!/usr/bin/env python3
"""재설계 학습 자료(2026-10-30, docs/VIDEO-TO-SFA-REDESIGN-2026-10-30.md): SFA 장 → (압축 영상 장, 정답 토큰열).
그림은 앱처럼 파일 비율 그대로 렌더(굵기는 1920 기준 비율 그대로 — 정답 파일과 같은 굵기)한 뒤 H.264로 압축·복원하고,
모델 입력 크기로 늘이거나 줄인다(비율은 meta.hwr로 모델에 따로 준다).
정답 = sfa_tokens.encode 토큰열 + 토큰마다 칸 번호(fields). 파일마다 npz 하나: img (n,H,W,3), tok/fld (이어 붙임), off (n+1).
--video(10-31 해상도 단계 1080→720→480→360): img 대신 vid(H.264 mp4 바이트, 파일 비율 렌더 크기 W×render_h)를 저장한다.
사용: python seq_data.py 출력폴더 [--maxlen 2048] [--max-frames 200] [--every 1] [--holdout] [--aug 1] [--check]
"""
import argparse
import json
import os
import sys
import zipfile
import xml.etree.ElementTree as ET
from multiprocessing import Pool

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sfa_paint_synth as SY  # noqa: E402
import sfa_render as R  # noqa: E402
import sfa_tokens as K  # noqa: E402
import vec_data as V  # noqa: E402

ROOT = V.ROOT
SEQ_DATA_VERSION = 3   # 정답 문장·렌더 방식이 바뀌면 올린다(다 만듦 표시가 옛 자료를 건너뛰지 않게). 2: GPT 검토 10-30 정답 변환 수정·늘리기. 3: 늘리기에 굵기 배율(10-31)
THICK_RANGE = (0.5, 2.0)   # 늘린 사본의 파일 전체 굵기 배율(로그 고르게). 사용자 10-31: "굵기 조절도 다양한 기능을 고루 쓸 줄 알아야" — 이전 방식 0.75–1.5보다 넓게


def augment(root, rng):
    """늘리기(GPT 검토 10-30 권고): 파일 전체 좌표를 같은 변환으로 — 좌우 반전(반반), 가운데 기준 0.8–1.2배, ±8% 이동.
    SFA를 먼저 바꾸고 렌더하므로 그림과 정답이 정확히 같이 변한다. % 좌표에 같은 배율이라 화면 화소로도 가로세로 같은 배율(원은 원).
    굵기(10-31): 모든 오브젝트 ThicknessScale에 같은 배율(THICK_RANGE) — 정답의 굵기 칸도 같이 바뀐다. 글로우 폭은 앱에서 굵기를 따르므로 함께 변한다.
    화면 밖으로 나간 것은 정답 변환이 화면 밖 판정으로 뺀다."""
    flip = rng.random() < 0.5
    sc = float(rng.uniform(0.8, 1.2))
    tx, ty = (float(v) for v in rng.uniform(-8, 8, 2))
    for p in root.iter('AP'):
        x, y = float(p.get('X')), float(p.get('Y'))
        if flip:
            x = 100 - x
        p.set('X', repr((x - 50) * sc + 50 + tx))
        p.set('Y', repr((y - 50) * sc + 50 + ty))
    th = float(np.exp(rng.uniform(*np.log(THICK_RANGE))))
    for o in root.iter('AO'):
        o.set('ThicknessScale', repr(float(o.get('ThicknessScale') or 1) * th))
    return dict(flip=flip, scale=sc, tx=tx, ty=ty, thick=th)


def one(job):
    rel, out_dir, seed, a, *rest = job
    aug_k = rest[0] if rest else 0
    syn = len(rest) > 1 and rest[1]
    rng = np.random.default_rng(seed)
    try:
        z = zipfile.ZipFile(os.path.join(ROOT, rel))
        root = ET.fromstring(z.read(z.namelist()[0]))
    except Exception as e:
        return rel, 'err:' + type(e).__name__
    if syn:   # 페인트 합성(사용자 10-29: 흰 바탕이 너무 많아 학습에 합성을 넣기로) — 흰 바탕 파일만, 원본과 따로 '추가'되는 판
        if not SY.is_white(root):
            return rel, 'skip'
        import random
        SY.synth(root, random.Random(seed))   # 배경·띠·땅·그림자·머리 채우기·빛을 SFA에 더함 → 그림과 정답 문장이 같이 바뀐다
    aug = augment(root, rng) if aug_k else None
    if a.get('fixed'):   # 위치 시험용 고정 변환(GPT 3차: 학습 파일의 학습에 없던 이동 쌍)
        dx, dy, sc = a['fixed']
        for p in root.iter('AP'):
            p.set('X', repr((float(p.get('X')) - 50) * sc + 50 + dx))
            p.set('Y', repr((float(p.get('Y')) - 50) * sc + 50 + dy))
        aug = dict(fixed=[dx, dy, sc])
    frs = root.findall('Frame')
    if len(frs) > a['max_frames']:
        s = int(rng.integers(0, len(frs) - a['max_frames'] + 1))
        frs = frs[s:s + a['max_frames']]
    # 비율(사용자 10-30): 앱은 파일 비율 그대로 영상을 내보낸다(오버드라이브 0.45 → 1920×864 확인). 그래서 파일 비율로 렌더·압축한 뒤
    # 모델 입력 크기(W×W·9/16)로 늘이거나 줄여 저장한다. SFA 좌표는 가로·세로 각각 0–100이라 이렇게 하면 그림 위치 ↔ 좌표가 비율과 무관하게 맞는다.
    hwr = float(root.get('HeightWidthRatio') or 0.5625) or 0.5625
    W, H = a['W'], a['W'] * 9 // 16
    Hr = max(2, int(round(W * hwr / 2)) * 2)
    R.PARAMS['pad'] = 0.0
    R.PARAMS['thick_mul'] = W / 1920
    keep, toks, flds, pos = [], [], [], []
    for fr in frs:
        t, _ = K.encode(root, fr)
        if len(t) > a['maxlen']:
            continue
        try:
            f = K.fields(t)
        except ValueError:
            continue
        keep.append(fr)
        toks.append(t)
        flds.append(f)
        pos.append(int(fr.get('Position')))
    if not keep:
        return rel, 'none'
    crf = int(rng.integers(23, 36))   # 그림 렌더는 난수를 쓰지 않으므로 이전(렌더 뒤에 뽑던 때)과 같은 값
    if a.get('video'):   # 고해상도 단계 자료(10-31): 렌더한 장을 바로 압축기로 흘리고(1080 수백 장을 메모리에 모으지 않게) mp4 바이트 그대로 저장. 학습이 읽을 때 풀어 입력 크기로 맞춘다
        vid = V.encode_video((R.render_frame(root, fr, W, Hr) for fr in keep), crf, size=(W, Hr))
        nf = V.count_frames(vid)
        if nf != len(keep):
            return rel, f'err:frames {nf}/{len(keep)}'
        dec = None
    else:
        imgs = [R.render_frame(root, fr, W, Hr) for fr in keep]
        vid = None
        dec = V.encode_decode(imgs, crf)
        if len(dec) != len(imgs):
            return rel, f'err:frames {len(dec)}/{len(imgs)}'
        if Hr != H:
            dec = np.stack([cv2.resize(f, (W, H), interpolation=cv2.INTER_AREA if Hr > H else cv2.INTER_LINEAR) for f in dec])
    off = np.cumsum([0] + [len(t) for t in toks])
    name = rel.replace('/', '__').replace(' ', '_')[:-4] + f'__c{crf}' + (f'_a{aug_k}' if aug_k else '') + ('_syn' if syn else '') + '.npz'
    tmp = os.path.join(out_dir, name + '.tmp')
    with open(tmp, 'wb') as fh:
        pix = dict(vid=np.frombuffer(vid, np.uint8)) if dec is None else dict(img=dec)
        np.savez_compressed(fh, **pix, tok=np.concatenate(toks).astype(np.int16), fld=np.concatenate(flds).astype(np.int8),
                            off=off.astype(np.int64), pos=np.array(pos),
                            meta=json.dumps(dict(file=rel, crf=crf, W=W, H=H, vocab=K.VOCAB, xstep=K.XSTEP,
                                                 hwr=hwr, render_h=Hr, aug=aug, synth=bool(syn))))
    os.replace(tmp, os.path.join(out_dir, name))
    return rel, f'ok {len(keep)}'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('out_dir')
    ap.add_argument('--maxlen', type=int, default=2048)
    ap.add_argument('--max-frames', type=int, default=200)
    ap.add_argument('--W', type=int, default=640)
    ap.add_argument('--every', type=int, default=1, help='파일 몇 개마다 하나(시험용)')
    ap.add_argument('--holdout', action='store_true', help='시험용 파일만')
    ap.add_argument('--workers', type=int, default=max(1, (os.cpu_count() or 2) - 1))
    ap.add_argument('--low-priority', action='store_true', help='양보 모드: 낮은 CPU 우선순위')
    ap.add_argument('--aug', type=int, default=0, help='파일마다 늘린 사본 수(좌우 반전·확대·이동, 학습 자료만)')
    ap.add_argument('--fixed', default='', help='위치 시험 자료: 고정 변환 "dx,dy,배율"(학습 파일에, 늘리기 없이)')
    ap.add_argument('--synth', type=float, default=0.0, help='학습 파일 중 이 비율을 골라 흰 바탕인 것만 페인트 합성판을 원본과 별도로 더 만든다(사용자 10-29: 0.3, 원본은 그대로 모두)')
    ap.add_argument('--video', action='store_true', help='그림을 풀지 않고 H.264 mp4로 저장(고해상도 단계 자료, --W 1920·1280·854)')
    ap.add_argument('--check', action='store_true', help='만들지 않고 같은 설정으로 다 만들었는지만 확인(읽기 전용 폴더 가능, 맞으면 0·아니면 3으로 끝남)')
    a = ap.parse_args()
    if a.check:
        want = dict(config(a), files=len(V.file_list(only='holdout') if a.holdout else V.file_list()[::a.every]))
        ok = os.path.isdir(a.out_dir) and done_ok(a.out_dir, want)
        print('미리 만든 자료 맞음' if ok else '미리 만든 자료 아님(판·설정·파일 수 다름 또는 미완)', a.out_dir, flush=True)
        raise SystemExit(0 if ok else 3)
    os.makedirs(a.out_dir, exist_ok=True)
    if a.low_priority:
        try:
            if os.name == 'nt':
                import ctypes
                ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)
            else:
                os.nice(10)
        except Exception as e:
            print('우선순위 낮추기 실패(무시):', e, flush=True)
    want = dict(config(a), files=len(V.file_list(only='holdout') if a.holdout else V.file_list()[::a.every]))
    if done_ok(a.out_dir, want):
        print('이미 같은 설정으로 다 만듦 — 건너뜀', a.out_dir, flush=True)
        return
    # 다시 만들 때는 옛 결과를 지운다(설정이 바뀌어 옛 npz가 섞이지 않게, GPT 검토 10-30)
    for f in os.listdir(a.out_dir):
        if f.endswith(('.npz', '.tmp')) or f == 'done.json':
            os.remove(os.path.join(a.out_dir, f))
    files = V.file_list(only='holdout') if a.holdout else V.file_list()
    files = files[::a.every]
    cfg = dict(maxlen=a.maxlen, max_frames=a.max_frames, W=a.W, video=a.video, fixed=[float(v) for v in a.fixed.split(',')] if a.fixed else None)
    jobs = [(rel, a.out_dir, 1000 + i, cfg) for i, rel in enumerate(files)]
    if not a.holdout and not a.fixed:
        jobs += [(rel, a.out_dir, 500000 + 1000 * k + i, cfg, k) for k in range(1, a.aug + 1) for i, rel in enumerate(files)]
        if a.synth > 0:   # 고르기는 고정 난수 → 해상도 단계 자료끼리 같은 파일·같은 합성
            import random
            pick = random.Random(77)
            jobs += [(rel, a.out_dir, 900000 + i, cfg, 0, True) for i, rel in enumerate(files) if pick.random() < a.synth]
    n = n_files = 0
    fails = []
    with Pool(a.workers) as p:
        for res in p.imap_unordered(one, jobs):
            rel, st = res[0], res[1]
            if st.startswith('ok'):
                n += int(st.split()[1])
                n_files += 1
            elif st not in ('none', 'skip'):   # skip = 합성 대상 아님(흰 바탕 아님)
                fails.append(f'{rel} {st}')
                print(rel, st, flush=True)
    print('작업', len(jobs), '파일', n_files, '장', n, '실패', len(fails), flush=True)
    if n == 0:
        raise SystemExit('만든 장이 0 — 완료 표시를 쓰지 않음')
    with open(os.path.join(a.out_dir, 'done.json'), 'w', encoding='utf-8') as fh:
        json.dump(dict(want, frames=int(n), npz=n_files, fails=fails), fh, ensure_ascii=False)


def config(a):
    c = dict(version=SEQ_DATA_VERSION, maxlen=a.maxlen, max_frames=a.max_frames, W=a.W, every=a.every, holdout=a.holdout, vocab=K.VOCAB,
             aug=0 if a.holdout or a.fixed else a.aug, fixed=a.fixed)
    if getattr(a, 'video', False):   # 켰을 때만 넣는다(기존 그림 자료의 '다 만듦' 표시가 그대로 맞게)
        c['video'] = True
    if getattr(a, 'synth', 0) > 0 and not (a.holdout or a.fixed):
        c['synth'] = a.synth
    return c


def done_ok(out_dir, want):
    """같은 설정 + 장이 1개 이상 + npz 수가 기록과 같고 + 실패 작업이 없을 때만 '다 만듦'(GPT 검토 10-30·2차)."""
    try:
        d = json.load(open(os.path.join(out_dir, 'done.json'), encoding='utf-8'))
    except Exception:
        return False
    npz = sum(f.endswith('.npz') for f in os.listdir(out_dir))
    return all(d.get(k) == v for k, v in want.items()) and d.get('frames', 0) > 0 and d.get('npz') == npz and not d.get('fails')   # 실패가 있으면 다시(GPT 2차)


if __name__ == '__main__':
    main()
