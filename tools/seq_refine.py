"""동일 가중치에서 기존/균형 목적함수를 비교한다. 기본은 계획 저장, --run-gpu 때만 학습한다."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import random
import time

import numpy as np
import torch

import seq_train as T
import sfa_tokens as K
from seq_objective import objective, WEIGHTS


def file_sha(path):
    with open(path, 'rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest()


def load_plan(path):
    plan = json.loads(Path(path).read_text(encoding='utf-8'))
    if plan.get('schema') != 1 or plan.get('modes') != list(WEIGHTS):
        raise ValueError('비교 계획의 버전/두 목적함수가 다르다')
    if plan['objective_weights'] != {k: list(v) for k, v in WEIGHTS.items()}:
        raise ValueError('계획과 구현의 목적함수 비중이 다르다')
    for key in ('steps_per_arm', 'max_batch', 'tok_budget', 'val_n'):
        if not isinstance(plan[key], int) or plan[key] < 1:
            raise ValueError(f'계획의 {key}는 양의 정수여야 한다')
    for key in ('max_train_minutes_per_arm', 'lr'):
        if not np.isfinite(plan[key]) or plan[key] <= 0:
            raise ValueError(f'계획의 {key}는 유한한 양수여야 한다')
    return plan


def dataset_sha(ds):
    h = hashlib.sha256()
    for image, tok, fld, meta, ratio in zip(ds.img, ds.tok, ds.fld, ds.meta, ds.hwr):
        h.update(json.dumps([meta, ratio], sort_keys=True, ensure_ascii=False).encode())
        for array in (image, tok, fld):
            array = np.ascontiguousarray(array)
            h.update(str((array.shape, array.dtype.str)).encode())
            h.update(memoryview(array))
    return h.hexdigest()


def probe_indices(train, validation):
    """모델 출력을 보기 전 고정: 앞6검증장 + 출제 기능별 첫 표본. 학습 표본은 일반화 판정과 구분한다."""
    from seq_target_audit import features
    probes = [dict(split='validation', index=i, reason='목록 앞 고정 표본') for i in range(min(6, len(validation)))]
    selected = {}
    for feature in ('glow', 'fill', 'nonwhite_background', 'layer_opacity'):
        i = next((i for i, tokens in enumerate(train.tok) if feature in features(list(map(int, tokens)))), None)
        if i is not None:
            selected.setdefault(i, []).append(feature)
    probes.extend(dict(split='training_feature_diagnostic', index=i, reason=','.join(kinds)) for i, kinds in selected.items())
    return probes


def probe_font():
    """진단 글꼴 부재가 학습 비교를 중단시키지 않도록 기본 글꼴로 대체한다."""
    from PIL import ImageFont
    try:
        return ImageFont.truetype('DejaVuSans.ttf', 16)
    except OSError:
        return ImageFont.load_default()


@torch.inference_mode()
def generate_probes(net, train, validation, probes, out, mode, device):
    import xml.etree.ElementTree as ET
    import zipfile
    from PIL import Image, ImageDraw, ImageFont
    import sfa_render as R
    import sfa_objscore as OS
    net.eval()
    output = Path(out)/mode
    output.mkdir(exist_ok=True)
    records, sheets = [], []
    font = probe_font()
    saved = dict(R.PARAMS)
    R.PARAMS.update(pad=0., thick_mul=640/1920)
    try:
        for number, probe in enumerate(probes):
            ds = validation if probe['split'] == 'validation' else train
            i = probe['index']
            image, _, _, ratio = ds.batch([i])
            tokens, done, reason = T.generate(net, image[0].to(device), float(ratio[0]), reason=True)
            frame = K.decode(tokens)
            target = K.decode([int(t) for t in ds.tok[i]])
            score = OS.score(frame, target, hwr=float(ratio[0]))
            seq = T.seq_xml(float(ratio[0]))
            height = max(2, round(640*float(ratio[0])))
            images = [np.asarray(Image.fromarray(ds.image(i)).resize((640, height))), R.render_frame(seq, frame, 640, height), R.render_frame(seq, target, 640, height)]
            sheet = Image.new('RGB', (1920, height+32), 'white')
            draw = ImageDraw.Draw(sheet)
            for col, (im, title) in enumerate(zip(images, ['Input', mode, 'Target'])):
                draw.text((col*640+4, 3), title, font=font, fill='black')
                sheet.paste(Image.fromarray(im), (col*640, 32))
            sheet.save(output/f'probe_{number:02d}.png')
            sheets.append(sheet)
            seq.append(frame)
            with zipfile.ZipFile(output/f'probe_{number:02d}.sfa', 'w', zipfile.ZIP_DEFLATED) as archive:
                archive.writestr('probe.xml', ET.tostring(seq, encoding='utf-8', xml_declaration=True))
            records.append(dict(probe, file=ds.meta[i].get('file'), position=ds.meta[i].get('pos'), done=done, reason=reason,
                                tokens=len(tokens), target_tokens=len(ds.tok[i]), partial=100*score['partial'],
                                objects=score['pred'], target_objects=score['ans'], official=False))
        combined = Image.new('RGB', (1920, sum(s.height for s in sheets)), 'white')
        y = 0
        for sheet in sheets:
            combined.paste(sheet, (0, y))
            y += sheet.height
        combined.save(output/'probes_native.png')
        (output/'probes.json').write_text(json.dumps(records, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    finally:
        R.PARAMS.clear()
        R.PARAMS.update(saved)
        net.train()
    return records


def prepare(checkpoint, data, val, out, profile):
    plan = load_plan(profile)
    output = Path(out).resolve()
    if output == Path(checkpoint).resolve().parent:
        raise ValueError('원본 가중치 폴더를 비교 출력으로 쓸 수 없다')
    if output.exists() and any(output.iterdir()):
        raise ValueError('비교 출력은 새 빈 폴더여야 한다')
    state = torch.load(checkpoint, map_location='cpu', weights_only=False)
    record = dict(schema=1, experiment=True, official=False, plan=plan, parent_step=state.get('step'),
                  parent_sha256=file_sha(checkpoint), parent_cfg=state['cfg'],
                  data_reference=str(data), val_reference=str(val),
                  note='계획 준비이며 모델 개선/학습 실행의 증거가 아니다. 두 분기는 같은 새 옵티마이저에서 출발한다.')
    output.mkdir(parents=True, exist_ok=True)
    (output/'plan.json').write_text(json.dumps(record, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    return record


@torch.inference_mode()
def evaluate(net, ds, batches, device):
    net.eval()
    total = correct = count = 0.
    for batch in batches:
        image, tokens, fields, ratio = (x.to(device) for x in ds.batch(batch))
        logits = net(image, tokens[:, :-1], fields[:, :-1], ratio)
        loss, acc, n = T.loss_fn(logits, tokens[:, 1:], fields[:, 1:])
        total += float(loss)*float(n)
        correct += float(acc)*float(n)
        count += float(n)
    net.train()
    return dict(token_loss=total/count, token_accuracy=correct/count, tokens=int(count))


MAX_SCALE_RETRIES = 24


def scaled_update(net, optimizer, scaler, run_batch, max_retries=MAX_SCALE_RETRIES):
    """한 묶음을 한 번의 실제 업데이트로 반영한다.

    fp16 GradScaler의 배율 넘침(초기 65536 배율 등)은 공식 학습처럼 업데이트로 세지 않고 배율만 줄인다.
    두 분기의 묶음 순서/업데이트 수를 같게 두기 위해 묶음을 버리지 않고 같은 묶음을 줄어든 배율로 다시 계산한다.
    배율이 없는 경로(bf16/CPU)나 배율이 줄지 않는 비유한 기울기는 실제 수치 문제이므로 중단한다.
    반환: (loss, parts, 넘침으로 다시 계산한 횟수)
    """
    overflows = 0
    while True:
        optimizer.zero_grad(set_to_none=True)
        loss, parts = run_batch()
        if not torch.isfinite(loss):
            raise RuntimeError('비교 중 비유한 손실: 자동 건너뛰기로 분기 업데이트 수를 달리하지 않는다')
        scaler.scale(loss).backward()
        scaler.unscale_(optimizer)
        norm = torch.nn.utils.clip_grad_norm_(net.parameters(), 1.)
        if torch.isfinite(norm):
            scaler.step(optimizer)
            scaler.update()
            return loss, parts, overflows
        if not scaler.is_enabled():
            raise RuntimeError('비교 중 비유한 기울기(배율 없는 경로): 양쪽을 같은 조건으로 다시 준비해야 한다')
        before = scaler.get_scale()
        scaler.update()   # unscale_가 기록한 넘침으로 배율만 줄인다. step(optimizer)는 부르지 않는다
        optimizer.zero_grad(set_to_none=True)
        if not scaler.get_scale() < before:
            raise RuntimeError('비교 중 비유한 기울기: 배율 넘침이 아닌데 노름이 비유한이다')
        overflows += 1
        if overflows > max_retries:
            raise RuntimeError(f'비교 중 배율 넘침이 {max_retries}회를 넘었다: 같은 묶음이 계속 넘친다')


def train_pair(checkpoint, data, val, out, record):
    if not torch.cuda.is_available():
        raise RuntimeError('--run-gpu에는 사용 가능한 CUDA GPU가 필요하다')
    plan, cfg = record['plan'], record['parent_cfg']
    device = 'cuda'
    train = T.Data(data, cfg['maxlen'], cfg['in_w'])
    validation = T.Data(val, cfg['maxlen'], cfg['in_w'], exclude=T.holdout_exclude())
    if not len(train) or not len(validation):
        raise ValueError('비교 학습/검증 자료가 비어 있다')
    random.seed(plan['seed'])
    batches = []
    while len(batches) < plan['steps_per_arm']:
        epoch = T.make_batches(train, plan['max_batch'], plan['tok_budget'])
        if not epoch:
            raise ValueError('토큰 예산에 맞는 학습 묶음이 없다')
        random.shuffle(epoch)
        batches.extend(epoch)
    batches = batches[:plan['steps_per_arm']]
    val_ids = sorted(set(np.linspace(0, len(validation)-1, min(plan['val_n'], len(validation))).astype(int).tolist()))
    val_batches = T.make_batches_fixed(validation, plan['max_batch'], plan['tok_budget'], val_ids)
    record.update(train_sha256=dataset_sha(train), val_sha256=dataset_sha(validation),
                  batch_order_sha256=hashlib.sha256(json.dumps(batches).encode()).hexdigest(),
                  train_n=len(train), val_n=len(val_ids))
    probes = probe_indices(train, validation)
    record['probes'] = probes
    Path(out, 'run.json').write_text(json.dumps(record, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    results = []
    for mode in plan['modes']:
        torch.manual_seed(plan['seed'])
        random.seed(plan['seed'])
        np.random.seed(plan['seed'])
        net, cfg = T.load(checkpoint, 'cpu')
        net.to(device).train()
        net.grad_ckpt = True
        optimizer = torch.optim.AdamW(net.parameters(), lr=plan['lr'])
        dtype = torch.bfloat16 if torch.cuda.get_device_capability()[0] >= 8 else torch.float16
        scaler = torch.amp.GradScaler('cuda', enabled=dtype == torch.float16)
        initial = evaluate(net, validation, val_batches, device)
        if not results:
            generate_probes(net, train, validation, probes, out, 'parent', device)
        steps, train_seconds, overflows = 0, 0., 0
        for step, batch in enumerate(batches):
            if train_seconds >= plan['max_train_minutes_per_arm']*60:
                break
            begin = time.monotonic()
            image, tokens, fields, ratio = (x.to(device) for x in train.batch(batch))

            def run_batch():
                with torch.autocast('cuda', dtype=dtype):
                    logits = net(image, tokens[:, :-1], fields[:, :-1], ratio)
                    return objective(logits, tokens[:, 1:], fields[:, 1:], [train.tok[i] for i in batch], mode)
            loss, parts, retried = scaled_update(net, optimizer, scaler, run_batch)
            overflows += retried
            torch.cuda.synchronize()
            train_seconds += time.monotonic()-begin
            steps += 1
            if steps % 50 == 0 or steps == len(batches):
                row = dict(mode=mode, step=steps, train_seconds=train_seconds, objective=float(loss),
                           scale_overflows=overflows, scale=float(scaler.get_scale()) if scaler.is_enabled() else None,
                           **{k: float(v) for k, v in parts.items()})
                with Path(out, 'train.jsonl').open('a', encoding='utf-8') as fh:
                    fh.write(json.dumps(row, ensure_ascii=False)+'\n')
                print(f'{mode}: {steps}/{len(batches)}업데이트', flush=True)
        final = evaluate(net, validation, val_batches, device)
        child_cfg = copy.deepcopy(cfg)
        child_cfg.pop('stages', None)
        child_cfg['refinement'] = dict(mode=mode, plan=plan, parent_sha256=record['parent_sha256'], parent_step=record['parent_step'], official=False)
        torch.save(dict(model=net.state_dict(), cfg=child_cfg, step=steps, parent_step=record['parent_step']), Path(out, mode+'.pt'))
        generate_probes(net, train, validation, probes, out, mode, device)
        results.append(dict(mode=mode, updates=steps, train_seconds=train_seconds, scale_overflows=overflows,
                            initial=initial, final=final, complete=steps == len(batches)))
        Path(out, 'results.json').write_text(json.dumps(dict(official=False, arms=results,
            comparable=len(results) == 2 and all(r['complete'] for r in results)), ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
        del net, optimizer, loss, parts
        torch.cuda.empty_cache()
    if not all(r['complete'] for r in results):
        raise RuntimeError('예산 안에서 같은 업데이트 수를 완료하지 못했으므로 비교 미완료다')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('checkpoint')
    parser.add_argument('data')
    parser.add_argument('val')
    parser.add_argument('out')
    parser.add_argument('--profile', default=str(Path(__file__).resolve().parents[1]/'profiles/seq_refinement_balanced_v1.json'))
    parser.add_argument('--run-gpu', action='store_true', help='명시적으로 승인한 GPU 비교 학습 실행. 생략하면 CPU 계획 저장만')
    args = parser.parse_args()
    record = prepare(args.checkpoint, args.data, args.val, args.out, args.profile)
    print('비교 계획 저장 완료. 공식 학습 결과/합격 판정과 구분한다.', flush=True)
    if args.run_gpu:
        train_pair(args.checkpoint, args.data, args.val, args.out, record)


if __name__ == '__main__':
    main()
