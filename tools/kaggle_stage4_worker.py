"""단계 4 학습 1단계(Kaggle T4): '글 → 정지 포즈 한 장'(동작 토큰 키프레임 1개). Qwen2.5-VL-3B-Instruct 4비트 + LoRA.
평가 자료(stage4_split의 출처)는 학습에서 빼고, 그 글로 생성한 포즈 토큰을 저장한다(채점은 서버 stage4_pack.score).

입력: /kaggle/input/**/poses.jsonl, motion_tokens.py
출력: /kaggle/working/stage4_result.json, stage4_gen.jsonl, lora/
"""
import glob, json, os, random, sys, time
os.system('pip -q install -U "transformers>=4.49" "peft>=0.15" bitsandbytes accelerate > /dev/null 2>&1')
import torch

DATA = sorted(glob.glob('/kaggle/input/**/poses.jsonl', recursive=True))[0].rsplit('/', 1)[0]
sys.path.insert(0, DATA)
import motion_tokens as MT  # noqa: E402

OUT = '/kaggle/working'
MODEL = 'Qwen/Qwen2.5-VL-3B-Instruct'
STEPS, ACC, LR, MAXLEN = int(os.environ.get('STEPS', 800)), 8, 2e-4, 160
res = dict(model=MODEL, steps=STEPS, accum=ACC)
t0 = time.time()

from transformers import AutoTokenizer, BitsAndBytesConfig, Qwen2_5_VLForConditionalGeneration
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training

tok = AutoTokenizer.from_pretrained(MODEL)
new = MT.VOCAB + ['<ref>']
tok.add_special_tokens({'additional_special_tokens': new})
q = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type='nf4', bnb_4bit_compute_dtype=torch.float16, bnb_4bit_use_double_quant=True)
model = Qwen2_5_VLForConditionalGeneration.from_pretrained(MODEL, quantization_config=q, device_map={'': 0}, torch_dtype=torch.float16)
model.resize_token_embeddings(len(tok))
new_ids = tok.convert_tokens_to_ids(new)
model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=True)
lc = dict(r=16, lora_alpha=32, lora_dropout=0.05, task_type='CAUSAL_LM',
          target_modules=['q_proj', 'k_proj', 'v_proj', 'o_proj', 'gate_proj', 'up_proj', 'down_proj'])
try:
    model = get_peft_model(model, LoraConfig(**lc, trainable_token_indices={'embed_tokens': new_ids}))
    res['new_token_training'] = 'trainable_token_indices'
except Exception as e:   # 오래된 peft
    model = get_peft_model(model, LoraConfig(**lc, modules_to_save=['embed_tokens', 'lm_head']))
    res['new_token_training'] = f'modules_to_save ({type(e).__name__})'
res['load_s'] = round(time.time() - t0, 1)
res['trainable_params'] = sum(p.numel() for p in model.parameters() if p.requires_grad)

allrows = [json.loads(l) for l in open(f'{DATA}/poses.jsonl', encoding='utf-8')]
held = set(json.load(open(f'{DATA}/stage4_split_2026-11-05.json', encoding='utf-8'))['held_out'])
rows = [r for r in allrows if r['src'] not in held]; evals = [r for r in allrows if r['src'] in held]
res.update(train_pairs=len(rows), eval_pairs=len(evals))
def text(r): return f"글: {r['prompt']}\n동작: ", ''.join(r['tokens'])
def batch(r):
    a, b = text(r)
    ia = tok(a, add_special_tokens=False)['input_ids']; ib = tok(b, add_special_tokens=False)['input_ids'] + [tok.eos_token_id]
    ids = (ia + ib)[:MAXLEN]; lab = ([-100] * len(ia) + ib)[:MAXLEN]
    return torch.tensor([ids], device='cuda'), torch.tensor([lab], device='cuda')
res['tokens_per_pair_median'] = sorted(len(tok(''.join(r['tokens']), add_special_tokens=False)['input_ids']) for r in rows)[len(rows) // 2]

opt = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=LR)
scaler = torch.amp.GradScaler('cuda')
model.train(); random.seed(0); losses = []; torch.cuda.reset_peak_memory_stats()
style = [r for r in rows if r['layer'] == 'style']
t1 = time.time()
for step in range(STEPS):
    for _ in range(ACC):
        r = random.choice(style) if random.random() < 0.3 else random.choice(rows)   # 스타일 층을 더 자주
        ids, lab = batch(r)
        with torch.autocast('cuda', dtype=torch.float16):
            loss = model(input_ids=ids, labels=lab).loss / ACC
        scaler.scale(loss).backward(); losses.append(loss.item() * ACC)
    scaler.step(opt); scaler.update(); opt.zero_grad(set_to_none=True)
    if step % 10 == 0: print('step', step, 'loss', round(sum(losses[-ACC * 10:]) / len(losses[-ACC * 10:]), 3), round(time.time() - t1), 's', flush=True)
res['train_s'] = round(time.time() - t1, 1); res['s_per_step'] = round(res['train_s'] / STEPS, 2)
res['train_peak_gb'] = round(torch.cuda.max_memory_allocated() / 2 ** 30, 2)
res['loss_first10'] = round(sum(losses[:ACC * 10]) / (ACC * 10), 3); res['loss_last10'] = round(sum(losses[-ACC * 10:]) / (ACC * 10), 3)
model.save_pretrained(f'{OUT}/lora')

model.eval(); random.seed(1)
ev = random.sample(evals, min(200, len(evals)))
tg = time.time(); f = open(f'{OUT}/stage4_gen.jsonl', 'w', encoding='utf-8')
for i in range(0, len(ev), 16):
    chunk = ev[i:i + 16]
    tok.padding_side = 'left'
    enc = tok([f"글: {r['prompt']}\n동작: " for r in chunk], return_tensors='pt', padding=True, add_special_tokens=False).to('cuda')
    with torch.no_grad(), torch.autocast('cuda', dtype=torch.float16):
        out = model.generate(**enc, max_new_tokens=30, do_sample=True, temperature=0.8, top_p=0.95, eos_token_id=tok.eos_token_id, pad_token_id=tok.eos_token_id)
    for r, o in zip(chunk, out):
        toks = [t for t in tok.convert_ids_to_tokens(o[enc['input_ids'].shape[1]:].tolist()) if t in set(MT.VOCAB)]
        f.write(json.dumps(dict(src=r['src'], frame=r['frame'], prompt=r['prompt'], layer=r['layer'], gen=toks, ref=r['tokens']), ensure_ascii=False) + '\n')
f.close(); gens = dict(n=len(ev), seconds=round(time.time() - tg, 1))
res['generation'] = gens
res['gen_peak_gb'] = round(torch.cuda.max_memory_allocated() / 2 ** 30, 2)
res['total_s'] = round(time.time() - t0, 1)
json.dump(res, open(f'{OUT}/stage4_result.json', 'w'), ensure_ascii=False, indent=1)
print(json.dumps(res, ensure_ascii=False), flush=True)
