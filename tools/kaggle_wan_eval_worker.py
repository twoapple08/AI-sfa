#!/usr/bin/env python3
"""Kaggle T4 x2: 나카무라 Wan LoRA 평가 영상 16개 — 세기 0.6·0.8·1.0 + '인물 빼기' 부정 프롬프트(1.0) (2026-10-28, 2판).

PC방을 못 쓰게 되어 pc_wan_lora_run.py --eval과 같은 비교를 Kaggle에서 만든다. 프롬프트·부정 프롬프트·LoRA 키 이름 바꾸기는
pc_wan_lora_run.py를 GitHub 작업 브랜치에서 받아 그대로 쓴다(한 곳에서만 고친다).
1판 정정(10-28 저녁): T5를 fp16으로 돌렸더니 같은 LoRA·시드·세기 1.0인데 PC(bf16) 결과와 구도부터 달랐다(p1 갈래 번개 → 일반 십자 섬광,
p2 명암 흙먼지 → 평평한 황토 덩어리; 평균 화소차 87·43). 프롬프트 해석(T5)이 fp16에서 망가진 것이 유력 → 2판은 T5를 원래대로 bf16.
0단계(재현 확인): p1·p2를 세기 1.0으로 GPU 0 = DiT fp16, GPU 1 = DiT bf16로 만들어 PC 결과와 비교 → PC에 더 가까운 DiT로 16개.
모델은 /tmp에 둬서 Kaggle 출력(20GB 제한)에 넣지 않는다. 서버에서는 GPU 실행을 못 했다 — 비교 시트·이름 바꾸기만 기존 영상으로 시험.
사용(노트북): python kaggle_wan_eval_worker.py [--out /kaggle/working]
"""
import argparse
import glob
import os
import queue
import shutil
import subprocess
import sys
import threading
import time
import zipfile

W = os.environ.get("WAN_DIR", "/tmp/wan")
MT = "f8a1b03794a49239a3539015075f5123d6c07d66"
RAW = "https://raw.githubusercontent.com/twoapple08/AI-sfa/ccr-bccf15a6-d6ee46/tools"
HF = "https://huggingface.co"
DL = "https://drive.usercontent.google.com/download?export=download&confirm=t&id="
WAN_OUT_ZIP = DL + "1NnqoIsJ94lH-_2u4ofeHCduhhWgXC0lv"  # 10-28 PC방 학습 결과(LoRA + 학습 전 영상, 사용자 공유)
PC_SAMPLES_ZIP = DL + "1GkoFDUODE2Jfwz8f-touKkbv9pis_PyR"  # 10-28 PC방 LoRA 적용 영상 p1·p2(세기 1.0, bf16) — 재현 기준
MODELS = {
    "dit_fp16": ("Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/diffusion_models/wan2.1_t2v_1.3B_fp16.safetensors", 2838303560),
    "dit_bf16": ("Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/diffusion_models/wan2.1_t2v_1.3B_bf16.safetensors", 2838104528),
    "vae": ("Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/vae/wan_2.1_vae.safetensors", 253815318),
    "t5": ("Wan-AI/Wan2.1-T2V-1.3B/resolve/main/models_t5_umt5-xxl-enc-bf16.pth", 11361920418),
}
T0 = time.time()
T5_FP8 = [True]  # PC와 같은 T5(fp8 저장 + bf16 계산). T4에서 fp8 저장이 실패하면 bf16 저장으로 한 번 바꾼다


def say(*a):
    print(f"[{(time.time() - T0) / 60:5.1f}분]", *a, flush=True)


def sh(cmd, **kw):
    subprocess.run(cmd, check=True, **kw)


def fetch(url, path, size, parts=8):
    """나눠 받기(HF 한 연결 속도 제한 대비). 크기가 맞으면 건너뛴다."""
    if os.path.exists(path) and os.path.getsize(path) == size:
        return
    step = -(-size // parts)
    procs = [subprocess.Popen(["curl", "-sSL", "--retry", "5", "-r", f"{i * step}-{min(size, (i + 1) * step) - 1}", "-o", f"{path}.{i}", url])
             for i in range(parts)]
    if any(p.wait() for p in procs):
        raise RuntimeError(f"받기 실패 {url}")
    with open(path, "wb") as out:
        for i in range(parts):
            with open(f"{path}.{i}", "rb") as f:
                shutil.copyfileobj(f, out, 1 << 24)
            os.remove(f"{path}.{i}")
    if os.path.getsize(path) != size:
        raise RuntimeError(f"크기 다름 {path} {os.path.getsize(path)} != {size}")


def setup():
    import torch
    cap = torch.cuda.get_device_capability(0)
    ng = torch.cuda.device_count()
    say("GPU", ng, "장", torch.cuda.get_device_name(0), "계산 능력", cap)
    # T5를 bf16으로 돌리므로 이 GPU에서 bf16 곱셈이 맞게 나오는지 먼저 본다(T4는 에뮬레이션)
    x = torch.randn(256, 1024, device="cuda")
    y = torch.randn(1024, 256, device="cuda")
    err = ((x.bfloat16() @ y.bfloat16()).float() - x @ y).abs().mean() / (x @ y).abs().mean()
    say(f"bf16 곱셈 상대 오차 {float(err):.4f}")
    if not err < 0.02:
        raise RuntimeError("이 GPU에서 bf16 계산이 맞지 않음 — Claude에게 이 줄을 보내 주세요")
    os.makedirs(os.path.join(W, "models"), exist_ok=True)
    mt = os.path.join(W, "musubi")
    if not os.path.exists(mt):
        sh(["curl", "-sSL", "-o", f"{W}/mt.zip", f"https://github.com/kohya-ss/musubi-tuner/archive/{MT}.zip"])
        with zipfile.ZipFile(f"{W}/mt.zip") as z:
            z.extractall(W)
        os.rename(os.path.join(W, f"musubi-tuner-{MT}"), mt)
    say("musubi-tuner 설치(torch는 Kaggle 것을 그대로)")
    sh([sys.executable, "-m", "pip", "install", "-q", "-e", mt], stdout=subprocess.DEVNULL)
    sh(["curl", "-sSL", "-o", f"{W}/pc_wan_lora_run.py", f"{RAW}/pc_wan_lora_run.py"])
    ths = []
    for k in ("dit_fp16", "dit_bf16", "vae", "t5"):
        rel, size = MODELS[k]
        ths.append(threading.Thread(target=fetch, args=(f"{HF}/{rel}", os.path.join(W, "models", os.path.basename(rel)), size)))
    for url, name in ((WAN_OUT_ZIP, "wan_out.zip"), (PC_SAMPLES_ZIP, "pc_samples.zip")):
        zp = os.path.join(W, name)
        ths.append(threading.Thread(target=lambda u=url, z=zp: os.path.exists(z) or sh(["curl", "-sSL", "--retry", "5", "-o", z, u])))
    say("모델 4개(DiT fp16·bf16, VAE, T5) + LoRA·PC 영상(Drive) 받는 중")
    for t in ths:
        t.start()
    for t in ths:
        t.join()
    os.makedirs(os.path.join(W, "base"), exist_ok=True)
    os.makedirs(os.path.join(W, "pc"), exist_ok=True)
    with zipfile.ZipFile(os.path.join(W, "wan_out.zip")) as z:
        z.extract("lora/nkmr_wan13.safetensors", W)
        for n in z.namelist():  # 학습 전(LoRA 없음) 영상을 비교 시트 기준으로
            if n.startswith("samples/p") and "_base/" in n and n.endswith(".mp4"):
                open(os.path.join(W, "base", n.split("/")[1].split("_")[0] + "_base.mp4"), "wb").write(z.read(n))
    with zipfile.ZipFile(os.path.join(W, "pc_samples.zip")) as z:
        for n in z.namelist():
            if n.startswith("samples/p") and "_lora/" in n and n.endswith(".mp4"):
                open(os.path.join(W, "pc", n.split("/")[1].split("_")[0] + "_pc.mp4"), "wb").write(z.read(n))
    say("받기 끝, PC 기준 영상:", sorted(os.listdir(os.path.join(W, "pc"))))
    return cap, ng, mt


def set_t5_dtype(mt, dt):
    p = os.path.join(mt, "src", "musubi_tuner", "wan", "configs", "shared_config.py")
    s = open(p, encoding="utf-8").read()
    s2 = s.replace("wan_shared_cfg.t5_dtype = torch.bfloat16", f"wan_shared_cfg.t5_dtype = torch.{dt}").replace(
        "wan_shared_cfg.t5_dtype = torch.float16", f"wan_shared_cfg.t5_dtype = torch.{dt}")
    if f"t5_dtype = torch.{dt}" not in s2:
        raise RuntimeError("shared_config.py의 t5_dtype 줄을 못 찾음(musubi 커밋 확인)")
    open(p, "w", encoding="utf-8").write(s2)


def run_group(job, gpu, t5_lock):
    """한 묶음(같은 DiT·세기·부정 프롬프트)을 한 번의 실행으로 — T5·DiT를 한 번만 읽는다. 결과 = sd/p{i}_{tag}.mp4"""
    tag, mult, neg, items, dit, lora, mt, sd, logdir = (job[k] for k in ("tag", "mult", "neg", "items", "dit", "lora", "mt", "sd", "logdir"))
    d = os.path.join(sd, "_" + tag)
    os.makedirs(d, exist_ok=True)
    todo = [(i, p) for i, p in items if not os.path.exists(os.path.join(sd, f"p{i}_{tag}.mp4"))]
    if not todo:
        return
    pf = os.path.join(d, "prompts.txt")
    open(pf, "w", encoding="utf-8").write("".join(f"{p} --d {100 + i}\n" for i, p in todo))  # 씨앗 = PC 실행과 같은 100+i
    m = os.path.join(W, "models")
    cmd = [sys.executable, os.path.join(mt, "src", "musubi_tuner", "wan_generate_video.py"), "--task", "t2v-1.3B", "--dit", dit,
           "--vae", os.path.join(m, "wan_2.1_vae.safetensors"), "--t5", os.path.join(m, "models_t5_umt5-xxl-enc-bf16.pth"),
           "--video_size", "288", "512", "--video_length", "33", "--fps", "24", "--infer_steps", "25",
           "--lora_weight", lora, "--lora_multiplier", str(mult), "--from_file", pf, "--save_path", d]
    if neg:
        cmd += ["--negative_prompt", neg]
    if T5_FP8[0]:
        cmd += ["--fp8_t5"]
    env = dict(os.environ, CUDA_VISIBLE_DEVICES=str(gpu), PYTHONUNBUFFERED="1")
    t5_lock.acquire()  # RAM(약 29GB)에 T5(11GB)를 둘이 동시에 올리지 않도록 T5 단계만 차례로
    held = True
    t0 = time.time()
    with open(os.path.join(logdir, tag + ".log"), "w", encoding="utf-8") as log:
        p = subprocess.Popen(cmd, cwd=mt, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace")
        for line in p.stdout:
            log.write(line)
            if held and "Loading DiT model" in line:
                t5_lock.release()
                held = False
            if "Processing prompt" in line or "precision" in line or "Error" in line or "error" in line or "Traceback" in line:
                say(f"GPU{gpu} {tag}:", line.rstrip()[-150:])
        p.wait()
    if held:
        t5_lock.release()
    for i, _ in todo:
        f = glob.glob(os.path.join(d, f"*_{100 + i}_*.mp4")) or glob.glob(os.path.join(d, f"*_{100 + i}.mp4"))
        if f:
            shutil.move(sorted(f)[-1], os.path.join(sd, f"p{i}_{tag}.mp4"))
    say(f"GPU{gpu} {tag} rc={p.returncode} {(time.time() - t0) / 60:.1f}분")
    if p.returncode and T5_FP8[0] and "loading text encoder" in open(os.path.join(logdir, tag + ".log"), encoding="utf-8").read().lower() \
            and "Loading DiT model" not in open(os.path.join(logdir, tag + ".log"), encoding="utf-8").read():
        say(f"{tag}: T5 단계에서 실패 → T5 fp8 끄고 다시")
        T5_FP8[0] = False
        return run_group(job, gpu, t5_lock)
    if p.returncode:
        raise RuntimeError(f"{tag} 실패 — {logdir}/{tag}.log 끝부분 확인")


def run_parallel(jobs, ng, lock):
    q = queue.Queue()
    for j in jobs:
        q.put(j)
    errs = []

    def worker(gpu):
        while True:
            try:
                job = q.get_nowait()
            except queue.Empty:
                return
            try:
                run_group(job, gpu, lock)
            except Exception as e:  # 한 묶음이 실패해도 나머지는 만든다
                errs.append(str(e))
                say("실패:", e)

    ths = [threading.Thread(target=worker, args=(g,)) for g in range(max(1, ng))]
    for t in ths:
        t.start()
    for t in ths:
        t.join()
    return errs


def diff_to(a, b):
    """두 영상의 (화소 평균 차, 구도 차 = 64×36로 줄여 흐린 뒤 평균 차). 0–255."""
    import cv2
    import numpy as np
    fa, fb = frames(a), frames(b)
    n = min(len(fa), len(fb))
    px = np.mean([np.abs(fa[k].astype(np.float32) - fb[k].astype(np.float32)).mean() for k in range(n)])
    sm = lambda f: cv2.GaussianBlur(cv2.resize(f, (64, 36), interpolation=cv2.INTER_AREA), (5, 5), 0).astype(np.float32)  # noqa: E731
    lo = np.mean([np.abs(sm(fa[k]) - sm(fb[k])).mean() for k in range(n)])
    return float(px), float(lo)


def is_black(mp4):
    import cv2
    cap = cv2.VideoCapture(mp4)
    vals = []
    while True:
        ok, fr = cap.read()
        if not ok:
            break
        vals.append(float(fr.mean()))
    return not vals or max(vals) < 3.0, len(vals)


def frames(mp4):
    import cv2
    cap = cv2.VideoCapture(mp4)
    out = []
    while True:
        ok, fr = cap.read()
        if not ok:
            break
        out.append(fr)
    return out


def compare(sd, outdir, rows, nprompt):
    """프롬프트마다 (1) 장 0·8·16·24·32 × 줄(학습 전·세기별) 시트 JPG, (2) 나란히 재생 mp4(2열)."""
    import cv2
    import numpy as np
    os.makedirs(outdir, exist_ok=True)

    def label(img, s):
        img = img.copy()
        cv2.rectangle(img, (0, 0), (8 + 11 * len(s), 22), (0, 0, 0), -1)
        cv2.putText(img, s, (4, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)
        return img

    for i in range(nprompt):
        vids = [(r, frames(f)) for r, f in ((r, os.path.join(sd, f"p{i}_{r}.mp4") if r != "base" else os.path.join(W, "base", f"p{i}_base.mp4"))
                                           for r in rows) if os.path.exists(f)]
        vids = [(r, v) for r, v in vids if v]
        if not vids:
            continue
        h, w = vids[0][1][0].shape[:2]
        pick = [0, 8, 16, 24, 32]
        sheet = np.vstack([np.hstack([label(v[min(k, len(v) - 1)], f"{r} f{k}") if j == 0 else label(v[min(k, len(v) - 1)], f"f{k}")
                                      for j, k in enumerate(pick)]) for r, v in vids])
        cv2.imwrite(os.path.join(outdir, f"p{i}_sheet.jpg"), sheet, [cv2.IMWRITE_JPEG_QUALITY, 88])
        cols = 2
        rws = -(-len(vids) // cols)
        n = max(len(v) for _, v in vids)
        vw = cv2.VideoWriter(os.path.join(outdir, f"p{i}_side.mp4"), cv2.VideoWriter_fourcc(*"mp4v"), 24, (w * cols, h * rws))
        for k in range(n):
            tiles = [label(v[min(k, len(v) - 1)], r) for r, v in vids] + [np.zeros((h, w, 3), np.uint8)] * (rws * cols - len(vids))
            vw.write(np.vstack([np.hstack(tiles[r * cols:(r + 1) * cols]) for r in range(rws)]))
        vw.release()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="/kaggle/working")
    ap.add_argument("--compare-only", help="시험용: 이 폴더의 p{i}_{tag}.mp4로 비교 시트만")
    a = ap.parse_args()
    rows = ["base", "m0.6", "m0.8", "m1.0", "m1.0_noperson"]
    if a.compare_only:
        compare(a.compare_only, os.path.join(a.out, "compare"), rows, 4)
        compare(a.compare_only, os.path.join(a.out, "repro"), ["pc", "r_dit16", "r_ditbf16"], 4)
        return
    cap, ng, mt = setup()
    sys.path.insert(0, W)
    import pc_wan_lora_run as pc
    sd = os.path.join(W, "samples3")
    logdir = os.path.join(a.out, "logs")
    os.makedirs(sd, exist_ok=True)
    os.makedirs(logdir, exist_ok=True)
    set_t5_dtype(mt, "bfloat16")  # 1판의 fp16 패치를 쓰지 않는다(PC와 같은 T5: fp8 저장 + bf16 계산)
    dits = {k: os.path.join(W, "models", os.path.basename(MODELS[k][0])) for k in ("dit_fp16", "dit_bf16")}
    lora = pc.merge_ready(os.path.join(W, "lora", "nkmr_wan13.safetensors"), dits["dit_fp16"])
    lock = threading.Lock()
    job = lambda tag, mult, neg, items, dit: dict(tag=tag, mult=mult, neg=neg, items=items, dit=dit, lora=lora, mt=mt, sd=sd, logdir=logdir)  # noqa: E731
    ref = [i for i in (1, 2) if os.path.exists(os.path.join(W, "pc", f"p{i}_pc.mp4"))]
    say(f"0단계: PC 결과 재현 확인 p{ref} 세기 1.0 — GPU 0 DiT fp16 / GPU 1 DiT bf16")
    items = [(i, pc.PROMPTS[i]) for i in ref]
    run_parallel([job("r_dit16", 1.0, None, items, dits["dit_fp16"]), job("r_ditbf16", 1.0, None, items, dits["dit_bf16"])], ng, lock)
    for i in ref:  # 비교 시트용으로 PC 영상을 같은 폴더에
        shutil.copy(os.path.join(W, "pc", f"p{i}_pc.mp4"), os.path.join(sd, f"p{i}_pc.mp4"))
    score = {}
    for t in ("r_dit16", "r_ditbf16"):
        ds = [diff_to(os.path.join(sd, f"p{i}_{t}.mp4"), os.path.join(sd, f"p{i}_pc.mp4")) for i in ref
              if os.path.exists(os.path.join(sd, f"p{i}_{t}.mp4"))]
        score[t] = sum(d[1] for d in ds) / len(ds) if ds else 1e9
        say(f"  {t}: PC와 차(화소, 구도) =", [(round(x, 1), round(y, 1)) for x, y in ds], "| 1판(T5 fp16) 화소차는 p1 87, p2 43")
    compare(sd, os.path.join(a.out, "repro"), ["pc", "r_dit16", "r_ditbf16"], 4)
    tag = "r_dit16" if score["r_dit16"] <= score["r_ditbf16"] * 1.15 else "r_ditbf16"
    dit = dits["dit_fp16" if tag == "r_dit16" else "dit_bf16"]
    say("고른 DiT:", os.path.basename(dit), "(구도 차", {k: round(v, 1) for k, v in score.items()}, ")")
    if min(score.values()) > 25:
        say("주의: 두 DiT 모두 PC와 구도가 많이 다름 — T5 말고 다른 원인 가능. repro 시트를 Claude에게 보여 주세요")
    for i in ref:  # 고른 설정의 재현 영상 = 세기 1.0 결과(같은 명령)
        shutil.copy(os.path.join(sd, f"p{i}_{tag}.mp4"), os.path.join(sd, f"p{i}_m1.0.mp4"))
    say(f"1단계: 16개(세기 0.6·0.8·1.0·1.0+인물 빼기) — GPU {ng}장")
    allp = list(enumerate(pc.PROMPTS))
    errs = run_parallel([job("m1.0", 1.0, None, allp, dit), job("m0.8", 0.8, None, allp, dit), job("m0.6", 0.6, None, allp, dit),
                         job("m1.0_noperson", 1.0, pc.NEG_NOPERSON, allp, dit)], ng, lock)
    compare(sd, os.path.join(a.out, "compare"), rows, len(pc.PROMPTS))
    zp = os.path.join(a.out, "wan_out_eval2.zip")
    with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(glob.glob(os.path.join(sd, "*.mp4"))):
            z.write(f, "samples/" + os.path.basename(f))
        for d in ("compare", "repro", "logs"):
            for f in sorted(glob.glob(os.path.join(a.out, d, "*"))):
                z.write(f, os.path.relpath(f, a.out))
    n = len(glob.glob(os.path.join(sd, "p*_m*.mp4")))
    say(f"완료: 평가 영상 {n}/16개 → {zp}", "| 실패:" if errs else "", "; ".join(errs))
    if shutil.which("rclone") and os.path.exists(os.path.expanduser("~/.config/rclone/rclone.conf")):
        r = subprocess.run(["rclone", "copy", zp, "gdrive:AI-sfa/02_분석자료/WanLoRA_평가/"], capture_output=True, text=True)
        say("Drive 업로드:", "성공 → AI-sfa/02_분석자료/WanLoRA_평가/wan_out_eval2.zip" if r.returncode == 0 else "실패 — Output 탭에서 받아 주세요")
    else:
        say("Drive 연결 없음 — 노트북 Output 탭에서 wan_out_eval2.zip을 받아 주세요")


if __name__ == "__main__":
    main()
