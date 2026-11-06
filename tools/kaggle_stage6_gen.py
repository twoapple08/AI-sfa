"""첫 완성판 생성(Kaggle T4, 학습 없음): 단계 5 LoRA로 '글 → 원하는 길이의 동작'.
(11-06 사용자 '그래'(선택 A): 단계 5는 요청 32·24장에 15·13장쯤으로 끝냄 — 학습 쌍 목표 장 중앙 15장. 이어 만들기를 원하는 길이까지 반복한다.)

- 글은 동작 문장 목록. 조각 k에는 k번째 동작 문장을 준다(학습 쌍도 목표 구간에 겹친 동작만 글로 받았다). 문장이 다 떨어지면 마지막 문장을 계속.
- 첫 조각 '길이: 32장', 다음부터 '길이: 24장' + 앞 조각 마지막 키 3개. 합이 TARGET장 이상이 되거나 MAX_CHUNKS에 닿으면 끝.
- 표본: 평가 글(stage5_split 평가 '처음' 쌍, 문장을 ' → '로 나눔) N_EVAL개 + 손으로 쓴 글(CUSTOM, 기준 프롬프트의 걷기·달리기·펀치 등). 참고 층 글은 <ref> 없이(생성은 항상 스타일 층).
입력: /kaggle/input/**/motion5.jsonl·motion_tokens.py·stage5_split, /kaggle/input/**/lora/adapter_model.safetensors(단계 5 커널 출력)
출력: /kaggle/working/stage6_gen.jsonl(표본마다 chunks), stage6_result.json
"""
import glob, json, os, random, sys, time
DRY = os.environ.get('DRYRUN') == '1'
if not DRY:
    os.system('pip -q install -U "transformers>=4.49" "peft>=0.15" bitsandbytes accelerate > /dev/null 2>&1')
import torch

DATA = os.environ.get('DATA_DIR') or sorted(glob.glob('/kaggle/input/**/motion5.jsonl', recursive=True))[0].rsplit('/', 1)[0]
sys.path.insert(0, DATA)
import motion_tokens as MT  # noqa: E402

OUT = os.environ.get('OUT_DIR', '/kaggle/working')
MODEL = 'trl-internal-testing/tiny-Qwen2_5_VLForConditionalGeneration' if DRY else 'Qwen/Qwen2.5-VL-3B-Instruct'
DEV = 'cpu' if DRY else 'cuda'
TARGET, FIRST, NEXT, CTX, K = 72, 32, 24, 3, 23
MAX_CHUNKS = 3 if DRY else 10
N_EVAL = 2 if DRY else 6
MODES = [m for m in os.environ.get('MODES', 'full').split(',') if m]   # 2차 결과(11-06): 기본 = 글 전체. 옛 비교는 MODES=full,act,full_ref
_OLD_MODES = ['full', 'act', 'full_ref']   # 11-06 비교: 매 조각 글 전체 / 조각마다 문장 하나(1차, 이어 만들기 50% 정지) / 글 전체 + <ref>(단계 5 평가 조건)
RETRY, MIN_MOTION = 3, 0.05           # 정지(이웃 키 자세 변화 평균 < 0.05 몸통 — 학습 정답 중앙 0.6, 정지 판정 0.02)·되돌림 실패 조각은 다시 뽑기
GB = 4 if DRY else 16
CUSTOM = [
    ['걷기: 몸을 세우고 발을 번갈아 내딛는다.', '달리기: 몸을 앞으로 기울이고 팔다리를 번갈아 움직인다.', '펀치: 상체를 기울이며 한 팔을 앞으로 곧게 뻗는다.'],
    ['착지: 다리를 내리고 무릎을 굽혀 받친다.', '서기: 팔과 다리를 내리고 몸을 세운다.', '달리기: 몸을 앞으로 기울이고 팔다리를 번갈아 움직인다.'],
    ['자세 잡기: 예비 동작: 몸과 무릎을 깊이 낮춘다.', '점프: 몸을 펴 팔과 무릎을 들어 띄운다.', '착지: 다리를 내리고 무릎을 굽혀 받친다.'],
    ['킥: 몸을 기울여 한 다리를 높게 뻗는다.', '펀치: 상체를 기울이며 한 팔을 앞으로 곧게 뻗는다.', '회피: 상체와 머리를 뒤로 젖힌다.'],
]
res = dict(model=MODEL, target=TARGET, first=FIRST, next=NEXT, max_chunks=MAX_CHUNKS)
t0 = time.time()

from transformers import AutoTokenizer, BitsAndBytesConfig, Qwen2_5_VLForConditionalGeneration
from peft import LoraConfig, get_peft_model, set_peft_model_state_dict

tok = AutoTokenizer.from_pretrained(MODEL)
new = MT.VOCAB + ['<ref>']
tok.add_special_tokens({'additional_special_tokens': new})
q = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type='nf4', bnb_4bit_compute_dtype=torch.float16, bnb_4bit_use_double_quant=True)
model = (Qwen2_5_VLForConditionalGeneration.from_pretrained(MODEL) if DRY else
         Qwen2_5_VLForConditionalGeneration.from_pretrained(MODEL, quantization_config=q, device_map={'': 0}, torch_dtype=torch.float16))
model.resize_token_embeddings(len(tok))
new_ids = tok.convert_tokens_to_ids(new)
lc = dict(r=16, lora_alpha=32, lora_dropout=0.0, task_type='CAUSAL_LM',
          target_modules=['q_proj', 'k_proj', 'v_proj', 'o_proj', 'gate_proj', 'up_proj', 'down_proj'])
model = get_peft_model(model, LoraConfig(**lc, trainable_token_indices={'embed_tokens': new_ids}))
# 학습 결과: 입력 안의 모든 adapter_model.safetensors(단계 5 2차의 30분 중간 저장본 lora_XXm/ + 마지막 lora/)를 차례로 불러 같은 글로 생성
# (11-06: 오래 학습하면 외울 수 있어 시점별 비교). 이름 = 들어 있는 폴더 이름(맨 위면 데이터셋 이름).
from safetensors.torch import load_file
CKPTS = sorted(glob.glob(os.environ.get('INPUT_ROOT', '/kaggle/input') + '/**/adapter_model.safetensors', recursive=True))
if os.environ.get('CKPT_ONLY'): CKPTS = [c for c in CKPTS if os.path.basename(os.path.dirname(c)) in os.environ['CKPT_ONLY'].split(',')]
if not CKPTS and not DRY: raise SystemExit('학습 결과(LoRA)가 입력에 없다')
res['ckpts'] = [os.path.basename(os.path.dirname(c)) for c in CKPTS]
model.eval()
res['load_s'] = round(time.time() - t0, 1)

rows = [json.loads(l) for l in open(f'{DATA}/motion5.jsonl', encoding='utf-8')]
held = set(json.load(open(f'{DATA}/stage5_split_2026-11-05.json', encoding='utf-8'))['held_out'])
starts = [r for r in rows if r['src'] in held and r['kind'] == 'start']
random.seed(2); ev = random.sample(starts, min(N_EVAL, len(starts)))
base = [dict(src=r['src'], layer=r['layer'], acts=r['prompt'].replace('<ref> ', '').split(' → ')) for r in ev]
base += [dict(src=f'custom{i}', layer='custom', acts=a) for i, a in enumerate(CUSTOM)]
import math
def motion(toks):
    body = [t for t in toks if t not in ('<motion>', '</motion>')]; P = []
    for i in range(0, len(body) - K + 1, K):
        ir = MT.decode(['<motion>'] + body[i:i + K] + ['</motion>'])
        if ir is None: continue
        J = ir['actors'][0]['joints']; p0 = J['pelvis'][0]
        T = math.hypot(J['neck'][0][0] - p0[0], (J['neck'][0][1] - p0[1]) * 0.5625) or 1
        P.append([((J[n][0][0] - p0[0]) / T, (J[n][0][1] - p0[1]) * 0.5625 / T) for n in MT.NAMES if n not in ('pelvis', 'head_b')])
    if len(P) < 2: return 0.0
    d = [sum(math.hypot(a[0] - b[0], a[1] - b[1]) for a, b in zip(x, y)) / len(x) for x, y in zip(P, P[1:])]
    return sum(d) / len(d)
def prompt_of(s, k):
    if s['mode'] == 'act': return s['acts'][min(k, len(s['acts']) - 1)]
    return ('<ref> ' if s['mode'] == 'full_ref' else '') + ' → '.join(s['acts'])

VS = set(MT.VOCAB)
def head(prompt, frames, ctx=()): return f'길이: {frames}장\n글: {prompt}\n' + (f"앞 동작: {''.join(ctx)}\n" if ctx else '') + '동작: '
def gen_many(items):
    outs = []; tok.padding_side = 'left'
    for i in range(0, len(items), GB):
        part = items[i:i + GB]
        enc = tok([head(p, n, c) for p, n, c in part], return_tensors='pt', padding=True, add_special_tokens=False).to(DEV)
        with torch.no_grad(), torch.autocast('cuda', dtype=torch.float16, enabled=not DRY):
            o = model.generate(**enc, max_new_tokens=(60 if DRY else 420), do_sample=True, temperature=0.8, top_p=0.95,
                               eos_token_id=tok.eos_token_id, pad_token_id=tok.eos_token_id)
        L = enc['input_ids'].shape[1]
        if DRY and os.environ.get('DRY_FAKE'):   # 흐름 시험: 작은 모델은 동작 토큰을 못 내므로 정답 토큰으로
            outs += [rows[0]['tokens'] for _ in part]; continue
        for row in o: outs.append([t for t in tok.convert_ids_to_tokens(row[L:].tolist()) if t in VS])
    return outs

tg = time.time()
OUT_F = open(f'{OUT}/stage6_gen.jsonl', 'w', encoding='utf-8')
for ci, ck_path in enumerate(CKPTS or [None]):
    ck = os.path.basename(os.path.dirname(ck_path)) if ck_path else 'none'
    if ck_path:
        r_ = set_peft_model_state_dict(model, load_file(ck_path)); res.setdefault('ckpt_unexpected', {})[ck] = len(getattr(r_, 'unexpected_keys', []) or [])
    samples = [dict(b, mode=m) for m in MODES for b in base]
    for s in samples: s.update(chunks=[], frames=0, done=False)
    for k in range(MAX_CHUNKS):
        todo = []
        for i, s in enumerate(samples):
            if s['done']: continue
            act = prompt_of(s, k)
            if k == 0: todo.append((i, (act, FIRST, ())))
            else:
                body = [t for t in s['chunks'][-1] if t not in ('<motion>', '</motion>')]
                ctx = body[-CTX * K:] if len(body) >= K else []
                if not ctx or len(ctx) % K: s['done'] = True; s['stop'] = '앞 조각 키 부족'; continue
                todo.append((i, (act, NEXT, ctx)))
        if not todo: break
        outs = gen_many([x for _, x in todo]); tries = [1] * len(todo)
        for _r in range(RETRY - 1):   # 정지·되돌림 실패 조각만 다시 뽑기
            bad = [j for j, g in enumerate(outs) if MT.decode(g) is None or (not (DRY and os.environ.get('DRY_FAKE')) and motion(g) < MIN_MOTION)]
            if not bad: break
            for j, g in zip(bad, gen_many([todo[j][1] for j in bad])): outs[j] = g; tries[j] += 1
        for (i, _), g, tr in zip(todo, outs, tries):
            s = samples[i]; ir = MT.decode(g); s.setdefault('tries', []).append(tr); s.setdefault('motion', []).append(round(motion(g), 3) if ir else None)
            if ir is None: s['done'] = True; s['stop'] = f'{k}번 조각 되돌림 실패'; continue
            s['chunks'].append(g); s['frames'] += ir['frames']
            if s['frames'] >= TARGET: s['done'] = True; s['stop'] = '목표 길이'
        print('조각', k, '남은 표본', sum(not s['done'] for s in samples), round(time.time() - tg), 's', flush=True)
    f = OUT_F
    if True:
        for s in samples:
            f.write(json.dumps(dict(ckpt=ck, src=s['src'], layer=s['layer'], mode=s['mode'], tries=s.get('tries'), motion=s.get('motion'),
                                    prompt=' → '.join(s['acts']), acts=s['acts'], chunks=s['chunks'],
                                    frames=s['frames'], stop=s.get('stop', '조각 상한')), ensure_ascii=False) + '\n')
    res.setdefault('generation', {})[ck] = dict(n=len(samples), seconds=round(time.time() - tg, 1),
                             frames=[s['frames'] for s in samples], chunks=[len(s['chunks']) for s in samples])

OUT_F.close()
res['total_s'] = round(time.time() - t0, 1)
json.dump(res, open(f'{OUT}/stage6_result.json', 'w'), ensure_ascii=False, indent=1)
print(json.dumps(res, ensure_ascii=False), flush=True)
