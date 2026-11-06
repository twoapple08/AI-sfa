"""단계 5 학습 2단계(Kaggle T4): '길이·글(·앞 키프레임) → 움직임'. 처음부터 만들기 + 이어 만들기. Qwen2.5-VL-3B-Instruct 4비트 + LoRA.
평가: stage4_split 출처를 학습에서 빼고, 그 글로 처음 32장 + 이어 만들기 2번(앞 조각 마지막 키 3개) = 약 3초를 생성해 저장(채점은 서버 stage5_score·stage4_pack).
단계 4 LoRA가 입력에 있으면(/kaggle/input/**/lora) 이어서 학습한다.

입력: /kaggle/input/**/motion5.jsonl, motion_tokens.py
출력: /kaggle/working/stage5_result.json, stage5_gen.jsonl, lora/
"""
import glob, json, os, random, sys, time
DRY = os.environ.get('DRYRUN') == '1'   # 서버 CPU 흐름 시험(작은 모델·양자화 없음·2단계) — Kaggle 버그로 GPU 시간 낭비 방지
if not DRY:
    os.system('pip -q install -U "transformers>=4.49" "peft>=0.15" bitsandbytes accelerate > /dev/null 2>&1')
import torch

DATA = os.environ.get('DATA_DIR') or sorted(glob.glob('/kaggle/input/**/motion5.jsonl', recursive=True))[0].rsplit('/', 1)[0]
sys.path.insert(0, DATA)
import motion_tokens as MT  # noqa: E402

OUT = os.environ.get('OUT_DIR', '/kaggle/working')
MODEL = 'trl-internal-testing/tiny-Qwen2_5_VLForConditionalGeneration' if DRY else 'Qwen/Qwen2.5-VL-3B-Instruct'
DEV = 'cpu' if DRY else 'cuda'
STEPS, ACC, LR, MAXLEN = (2 if DRY else int(os.environ.get('STEPS', 3000))), (2 if DRY else 8), 2e-4, 1000
# 2차 학습(11-06, 새 계정 30시간): 1차(70분·517단계)에서 이어 학습, 스타일 층 비중 0.3 → 0.5, 거의 정지한 목표 쌍 제외(생성 정지 15% 대책)
# 3차(11-06): 기본기 자료(HMDB51·뒤집기)로 4,214쌍 — 스타일 67쌍을 0.5로 뽑으면 외우기만 → 0.25. 학습 중 평가 손실로 가장 좋은 시점 저장·조기 종료
STYLE_P = float(os.environ.get('STYLE_P', 0.25)); STATIC_MIN = 0.02
EVAL_EVERY, EVAL_N, PATIENCE = (1 if DRY else 50), (3 if DRY else 80), 4
res = dict(model=MODEL, steps=STEPS, accum=ACC)
t0 = time.time()

from transformers import AutoTokenizer, BitsAndBytesConfig, Qwen2_5_VLForConditionalGeneration
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training

tok = AutoTokenizer.from_pretrained(MODEL)
new = MT.VOCAB + ['<ref>']
tok.add_special_tokens({'additional_special_tokens': new})
q = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type='nf4', bnb_4bit_compute_dtype=torch.float16, bnb_4bit_use_double_quant=True)
model = (Qwen2_5_VLForConditionalGeneration.from_pretrained(MODEL) if DRY else
         Qwen2_5_VLForConditionalGeneration.from_pretrained(MODEL, quantization_config=q, device_map={'': 0}, torch_dtype=torch.float16))
model.resize_token_embeddings(len(tok))
new_ids = tok.convert_tokens_to_ids(new)
if not DRY: model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=True)
lc = dict(r=16, lora_alpha=32, lora_dropout=0.05, task_type='CAUSAL_LM',
          target_modules=['q_proj', 'k_proj', 'v_proj', 'o_proj', 'gate_proj', 'up_proj', 'down_proj'])
try:
    model = get_peft_model(model, LoraConfig(**lc, trainable_token_indices={'embed_tokens': new_ids}))
    res['new_token_training'] = 'trainable_token_indices'
except Exception as e:   # 오래된 peft
    model = get_peft_model(model, LoraConfig(**lc, modules_to_save=['embed_tokens', 'lm_head']))
    res['new_token_training'] = f'modules_to_save ({type(e).__name__})'
prev = sorted(glob.glob('/kaggle/input/**/adapter_model.safetensors', recursive=True)) if not DRY else []   # 데이터셋 맨 위·lora/ 어디든(11-06 새 계정 LoRA 데이터셋은 맨 위)
REQUIRE_RESUME = True   # 2차: 이어 학습이 실패하면 GPU를 쓰기 전에 멈춘다
if prev:   # 단계 4 LoRA에서 이어 학습
    from safetensors.torch import load_file
    from peft import set_peft_model_state_dict
    try:
        r_ = set_peft_model_state_dict(model, load_file(prev[0]))
        res['resumed_from'] = prev[0]; res['resume_unexpected'] = len(getattr(r_, 'unexpected_keys', []) or [])
    except Exception as e:
        res['resume_error'] = f'{type(e).__name__}: {e}'[:300]
        if REQUIRE_RESUME: raise
elif REQUIRE_RESUME and not DRY:
    raise SystemExit('이어 학습할 LoRA가 입력에 없다')
res['load_s'] = round(time.time() - t0, 1)
res['trainable_params'] = sum(p.numel() for p in model.parameters() if p.requires_grad)

allrows = [json.loads(l) for l in open(f'{DATA}/motion5.jsonl', encoding='utf-8')]
# 11-05 사용자 '파일 단위 새 분리 + 처음부터': stage5_split(파일·영상 단위)이 있으면 그것, 없으면 옛 stage4_split
sp = next(p_ for p_ in (f'{DATA}/stage5_split_v3_2026-11-06.json', f'{DATA}/stage5_split_2026-11-05.json', f'{DATA}/stage4_split_2026-11-05.json') if os.path.exists(p_))
held = set(json.load(open(sp, encoding='utf-8'))['held_out']); res['split'] = os.path.basename(sp)
rows = [r for r in allrows if r['src'] not in held]; evals = [r for r in allrows if r['src'] in held]
import math
def _motion(toks):   # 이웃 키 자세 변화 평균(몸통 단위) — 서버 stage5_report.keys와 같은 정의
    body = [t for t in toks if t not in ('<motion>', '</motion>')]; P = []
    for i in range(0, len(body) - 22, 23):
        ir = MT.decode(['<motion>'] + body[i:i + 23] + ['</motion>'])
        if ir is None: continue
        J = ir['actors'][0]['joints']; p0 = J['pelvis'][0]
        T = math.hypot(J['neck'][0][0] - p0[0], (J['neck'][0][1] - p0[1]) * 0.5625) or 1
        P.append([((J[n][0][0] - p0[0]) / T, (J[n][0][1] - p0[1]) * 0.5625 / T) for n in MT.NAMES if n not in ('pelvis', 'head_b')])
    if len(P) < 2: return 1.0
    return sum(sum(math.hypot(a[0] - b[0], a[1] - b[1]) for a, b in zip(x, y)) / len(x) for x, y in zip(P, P[1:])) / (len(P) - 1)
n0 = len(rows); rows = [r for r in rows if _motion(r['tokens']) >= STATIC_MIN]; res['dropped_static'] = n0 - len(rows); res['style_p'] = STYLE_P
res.update(train_pairs=len(rows), eval_pairs=len(evals))
def head(prompt, frames, ctx=()): return f'길이: {frames}장\n글: {prompt}\n' + (f"앞 동작: {''.join(ctx)}\n" if ctx else '') + '동작: '
def text(r): return head(r['prompt'], r['frames'], r.get('context') or ()), ''.join(r['tokens'])
def batch(r):
    a, b = text(r)
    ia = tok(a, add_special_tokens=False)['input_ids']; ib = tok(b, add_special_tokens=False)['input_ids'] + [tok.eos_token_id]
    ids = (ia + ib)[:MAXLEN]; lab = ([-100] * len(ia) + ib)[:MAXLEN]
    return torch.tensor([ids], device=DEV), torch.tensor([lab], device=DEV)
res['tokens_per_pair_median'] = sorted(len(tok(''.join(r['tokens']), add_special_tokens=False)['input_ids']) for r in rows)[len(rows) // 2]

opt = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=LR)
scaler = torch.amp.GradScaler('cuda', enabled=not DRY)
model.train(); random.seed(0); losses = []
if not DRY: torch.cuda.reset_peak_memory_stats()
style = [r for r in rows if r['layer'] == 'style']
t1 = time.time()
TRAIN_MIN = float(os.environ.get('TRAIN_MIN', 150))   # 학습 시간 상한(분). 11-05: 긴 쌍(~400–700토큰)이라 800단계면 약 1시간 40분. 사용자 GPU 잔여 3시간 5분 확인 뒤 '추천대로' 70분(처음부터 학습)
done = 0; ckpts = []; CKPT_MIN = 30
random.seed(5); evsub = random.sample(evals, min(EVAL_N, len(evals))); random.seed(0)
def eval_loss():
    model.eval(); tot = n_ = 0.0
    with torch.no_grad():
        for r in evsub:
            ids, lab = batch(r)
            with torch.autocast('cuda', dtype=torch.float16, enabled=not DRY):
                l = model(input_ids=ids, labels=lab).loss
            k = int((lab != -100).sum()); tot += float(l) * k; n_ += k
    model.train(); return tot / max(n_, 1)
best, bad, curve = eval_loss(), 0, []
curve.append((0, round(best, 4))); print('평가 손실 0', round(best, 4), flush=True)
model.save_pretrained(f'{OUT}/lora_best')
for step in range(STEPS):
    if not DRY and time.time() - t1 > TRAIN_MIN * 60: break
    for _ in range(ACC):
        r = random.choice(style) if random.random() < STYLE_P else random.choice(rows)   # 스타일 층을 더 자주
        ids, lab = batch(r)
        with torch.autocast('cuda', dtype=torch.float16, enabled=not DRY):
            loss = model(input_ids=ids, labels=lab).loss / ACC
        scaler.scale(loss).backward(); losses.append(loss.item() * ACC)
    scaler.step(opt); scaler.update(); opt.zero_grad(set_to_none=True)
    done = step + 1
    if not DRY and time.time() - t1 > CKPT_MIN * 60 * (len(ckpts) + 1):   # 30분마다 중간 저장(오래 학습하면 외울 수 있어 앞 시점으로 되돌릴 수 있게)
        model.save_pretrained(f'{OUT}/lora_{int((time.time() - t1) // 60)}m'); ckpts.append(done)
    if step % 10 == 0: print('step', step, 'loss', round(sum(losses[-ACC * 10:]) / len(losses[-ACC * 10:]), 3), round(time.time() - t1), 's', flush=True)
    if done % EVAL_EVERY == 0:
        el = eval_loss(); curve.append((done, round(el, 4))); print('평가 손실', done, round(el, 4), '최고', round(best, 4), flush=True)
        if el < best: best, bad = el, 0; model.save_pretrained(f'{OUT}/lora_best')
        else:
            bad += 1
            if bad >= PATIENCE: print('조기 종료', done, flush=True); break
res['eval_curve'] = curve; res['best_eval_loss'] = round(best, 4)
res['train_s'] = round(time.time() - t1, 1); res['steps_done'] = done; res['checkpoints_at_step'] = ckpts; res['s_per_step'] = round(res['train_s'] / max(done, 1), 2)
res['train_peak_gb'] = 0 if DRY else round(torch.cuda.max_memory_allocated() / 2 ** 30, 2)
res['loss_first10'] = round(sum(losses[:ACC * 10]) / (ACC * 10), 3); res['loss_last10'] = round(sum(losses[-ACC * 10:]) / (ACC * 10), 3)
model.save_pretrained(f'{OUT}/lora')

model.eval(); random.seed(1)
starts = [r for r in evals if r.get('kind') == 'start']
ev = random.sample(starts, min(4 if DRY else 30, len(starts)))
VS = set(MT.VOCAB)
GB = 4 if DRY else 15   # 한 번에 여러 개 생성(11-05: 하나씩이면 30개 × 3조각 × 약 65초 ≈ 1시간 40분 → 묶음이면 몇 분)
def gen_many(items):
    """items = [(prompt, frames, ctx)] → 동작 토큰 목록들. 왼쪽 채움 묶음 생성."""
    outs = []
    tok.padding_side = 'left'
    for i in range(0, len(items), GB):
        part = items[i:i + GB]
        enc = tok([head(p, n, c) for p, n, c in part], return_tensors='pt', padding=True, add_special_tokens=False).to(DEV)
        with torch.no_grad(), torch.autocast('cuda', dtype=torch.float16, enabled=not DRY):
            o = model.generate(**enc, max_new_tokens=(60 if DRY else 420), do_sample=True, temperature=0.8, top_p=0.95, eos_token_id=tok.eos_token_id, pad_token_id=tok.eos_token_id)
        L = enc['input_ids'].shape[1]
        if DRY and os.environ.get('DRY_FAKE'):   # 흐름 시험: 작은 모델은 동작 토큰을 못 내므로 정답 토큰으로 이어 만들기 경로까지 돌린다
            outs += [ev[0]['tokens'] for _ in part]; continue
        for row in o:
            outs.append([t for t in tok.convert_ids_to_tokens(row[L:].tolist()) if t in VS])
        print('생성', i + len(part), '/', len(items), round(time.time() - tg), 's', flush=True)
    return outs
tg = time.time()
chunks = [[c] for c in gen_many([(r['prompt'], 32, ()) for r in ev])]
for _ in range(2):   # 이어 만들기: 앞 조각 마지막 키 3개(23토큰 × 3)
    todo = []
    for k, cs in enumerate(chunks):
        if len(cs) != _ + 1: continue
        body = [t for t in cs[-1] if t not in ('<motion>', '</motion>')]
        ctx = body[-3 * 23:] if len(body) >= 23 else []
        if ctx and not len(ctx) % 23: todo.append((k, ctx))
    for (k, ctx), g in zip(todo, gen_many([(ev[k]['prompt'], 24, ctx) for k, ctx in todo])):
        chunks[k].append(g)
f = open(f'{OUT}/stage5_gen.jsonl', 'w', encoding='utf-8')
for r, cs in zip(ev, chunks):
    f.write(json.dumps(dict(src=r['src'], prompt=r['prompt'], layer=r['layer'], chunks=cs, ref=r['tokens']), ensure_ascii=False) + '\n')
f.close(); gens = dict(n=len(ev), seconds=round(time.time() - tg, 1))
res['generation'] = gens
res['gen_peak_gb'] = 0 if DRY else round(torch.cuda.max_memory_allocated() / 2 ** 30, 2)
res['total_s'] = round(time.time() - t0, 1)
json.dump(res, open(f'{OUT}/stage5_result.json', 'w'), ensure_ascii=False, indent=1)
print(json.dumps(res, ensure_ascii=False), flush=True)
