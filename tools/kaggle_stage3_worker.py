"""단계 3 거대 모델 적합 시험(Kaggle T4): Qwen2.5-VL-3B-Instruct 4비트 + LoRA로 '글 → 동작 토큰' 짧게 학습하고
메모리·학습 속도·3초(72장) 생성 속도·생성 토큰의 디코딩 가능 비율을 잰다. 품질 판정용이 아니다(자료 539쌍, 짧은 학습).

입력: /kaggle/input/**/pairs.jsonl, motion_tokens.py
출력: /kaggle/working/stage3_result.json, gen_*.json(생성 토큰), lora/(어댑터)
"""
import glob, json, os, random, sys, time
os.system('pip -q install -U "transformers>=4.49" "peft>=0.15" bitsandbytes accelerate > /dev/null 2>&1')
import torch

DATA = sorted(glob.glob('/kaggle/input/**/pairs.jsonl', recursive=True))[0].rsplit('/', 1)[0]
sys.path.insert(0, DATA)
import motion_tokens as MT  # noqa: E402

OUT = '/kaggle/working'
MODEL = 'Qwen/Qwen2.5-VL-3B-Instruct'
STEPS, ACC, LR, MAXLEN = 150, 4, 2e-4, 1100
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

rows = [json.loads(l) for l in open(f'{DATA}/pairs.jsonl', encoding='utf-8')]
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

model.eval(); gens = []
allowed = set(new_ids) | {tok.eos_token_id}
prompts = ['0~1초 파랑이 몸을 낮췄다가 앞으로 달려가 오른쪽 상대에게 펀치를 뻗는다. 전신, 카메라 고정.',
           '서 있다가 뛰어올라 공중에서 몸을 돌리고 착지한다.',
           '상대의 공격을 팔로 막다가 뒤로 밀려 넘어지고 다시 일어난다.']
for i, p in enumerate(prompts):
    ids = tok(f'글: {p}\n동작: ', return_tensors='pt', add_special_tokens=False).input_ids.cuda()
    torch.cuda.synchronize(); tg = time.time()
    with torch.no_grad(), torch.autocast('cuda', dtype=torch.float16):
        out = model.generate(ids, max_new_tokens=950, do_sample=True, temperature=0.8, top_p=0.95,
                             bad_words_ids=None, eos_token_id=tok.eos_token_id)
    torch.cuda.synchronize(); dt = time.time() - tg
    gen = out[0, ids.shape[1]:].tolist()
    toks = tok.convert_ids_to_tokens(gen)
    mt = [t for t in toks if t in set(MT.VOCAB)]
    ir = MT.decode(mt)
    g = dict(prompt=p, seconds=round(dt, 1), new_tokens=len(gen), tok_per_s=round(len(gen) / dt, 1),
             motion_token_share=round(len(mt) / max(len(gen), 1), 3), decoded_frames=ir['frames'] if ir else 0)
    gens.append(g); json.dump(dict(g, tokens=mt), open(f'{OUT}/gen_{i}.json', 'w'), ensure_ascii=False)
    print(g, flush=True)
res['generation'] = gens
res['gen_peak_gb'] = round(torch.cuda.max_memory_allocated() / 2 ** 30, 2)
res['total_s'] = round(time.time() - t0, 1)
json.dump(res, open(f'{OUT}/stage3_result.json', 'w'), ensure_ascii=False, indent=1)
print(json.dumps(res, ensure_ascii=False), flush=True)
