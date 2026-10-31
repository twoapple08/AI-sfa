#!/usr/bin/env python3
"""Kaggle T4 x2: 나카무라 Wan2.1 1.3B LoRA 본 학습 + 중간 저장본 평가 (2026-10-28 밤).

학습 시험(10-28, data/style_kb/kaggle_wan_train_test_2026-10-28.json): T4 fp16 4.41 s/it, NaN 없음, 손실이 bf16과 같음 → 3000스텝 약 3.7시간.
순서:
  1) 받기·설치(평가 노트북과 같은 musubi 커밋·모델), 학습 자료 zip(--data-url)
  2) 잠재 캐시를 GPU 2장에 반씩(VAE fp16 — 시험에서 bf16 에뮬레이션은 15.7초/조각), 글 캐시(T5 fp8 저장 + bf16)
  3) GPU 0: fp16 학습(설정은 PC와 같음: LoRA 32/16, AdamW 2e-4, shift 3.0, checkpointing, 시드 42), --save-every마다 저장본을 모두 남김
  4) GPU 1: 저장본이 나올 때마다(기본 1000·2000·3000) 평가 3판 프롬프트 7개 × 씨앗 3개를 세기 0.8·CPU 노이즈로 생성 → 같은 씨앗의 기준선과 비교
  5) LoRA 저장본·평가 시트·기록 → zip → Drive(비밀값 있을 때)
도우미는 kaggle_wan_eval_worker.py·kaggle_wan_eval3_worker.py(같은 브랜치)를 받아 쓴다. 서버에서는 GPU 실행을 못 했다(문법·명령 구성만 확인).
사용(노트북): python kaggle_wan_train_worker.py --data-url URL [--name nkmr_wan13_v2] [--steps 3000] [--save-every 500] [--eval-steps 1000,2000,3000]
"""
import argparse
import glob
import json
import os
import shutil
import subprocess
import sys
import threading
import time
import zipfile

W = os.environ.get("WAN_DIR", "/tmp/wan")
RAW = "https://raw.githubusercontent.com/twoapple08/AI-sfa/ccr-bccf15a6-d6ee46/tools"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="/kaggle/working")
    ap.add_argument("--data-url", required=True)
    ap.add_argument("--name", default="nkmr_wan13_v2")
    ap.add_argument("--steps", type=int, default=3000)
    ap.add_argument("--save-every", type=int, default=500)
    ap.add_argument("--eval-steps", default="1000,2000,3000")
    ap.add_argument("--hours", type=float, default=11.0, help="Kaggle 세션 12시간 — 이 시간이 지나면 학습을 멈추고 결과를 묶는다")
    a = ap.parse_args()
    os.makedirs(W, exist_ok=True)
    for f in ("kaggle_wan_eval_worker.py", "kaggle_wan_eval3_worker.py"):
        subprocess.run(["curl", "-sSL", "-o", f"{W}/{f}", f"{RAW}/{f}"], check=True)
    sys.path.insert(0, W)
    import kaggle_wan_eval3_worker as e3
    import kaggle_wan_eval_worker as ev
    t_end = time.time() + a.hours * 3600
    cap, ng, mt = ev.setup()  # 모델·LoRA(기존)·musubi 설치. T4 bf16 곱셈 확인 포함
    import pc_wan_lora_run as pc
    ev.set_t5_dtype(mt, "bfloat16")
    m = os.path.join(W, "models")
    dit = os.path.join(m, os.path.basename(ev.MODELS["dit_fp16"][0]))
    src = os.path.join(mt, "src", "musubi_tuner")
    logdir = os.path.join(a.out, "train")
    os.makedirs(logdir, exist_ok=True)

    # 1) 자료: 조각을 반씩 두 폴더로(캐시를 GPU 2장에 나누기 위해), 학습 설정은 두 폴더를 함께
    data = os.path.join(W, "data_v2")
    if not os.path.exists(os.path.join(data, "a")):
        zp = os.path.join(W, "wanlora_v2.zip")
        if a.data_url.startswith("gdrive:"):  # 비공개 Drive 파일 — 노트북 1번 셀의 rclone 연결(비밀값 RCLONE_GDRIVE_AUTH_B64) 필요
            subprocess.run(["rclone", "copyto", a.data_url, zp], check=True)
        else:
            subprocess.run(["curl", "-sSL", "--retry", "5", "-o", zp, a.data_url], check=True)
        with zipfile.ZipFile(zp) as z:
            mp4 = sorted(n for n in z.namelist() if n.startswith("video/") and n.endswith(".mp4"))
            for k, n in enumerate(mp4):
                half = "a" if k % 2 == 0 else "b"
                os.makedirs(os.path.join(data, half, "video"), exist_ok=True)
                for nn in (n, n[:-4] + ".txt"):
                    open(os.path.join(data, half, "video", os.path.basename(nn)), "wb").write(z.read(nn))
            for nn in ("captions.csv",):
                if nn in z.namelist():
                    open(os.path.join(a.out, "train", "captions_used.csv"), "wb").write(z.read(nn))
    general = '[general]\nresolution = [512, 288]\ncaption_extension = ".txt"\nbatch_size = 1\nenable_bucket = false\n'
    ds = lambda h: f'\n[[datasets]]\nvideo_directory = "{data}/{h}/video"\ncache_directory = "{data}/{h}/cache"\nframe_extraction = "full"\nmax_frames = 33\n'  # noqa: E731
    tomls = {h: os.path.join(data, f"ds_{h}.toml") for h in ("a", "b", "all")}
    open(tomls["a"], "w").write(general + ds("a"))
    open(tomls["b"], "w").write(general + ds("b"))
    open(tomls["all"], "w").write(general + ds("a") + ds("b"))
    nclip = len(glob.glob(os.path.join(data, "*", "video", "*.mp4")))
    res = {"clips": nclip, "name": a.name, "steps": a.steps}
    ev.say(f"학습 자료 {nclip}조각")

    # 2) 캐시
    def cache_lat(h, gpu):
        log = os.path.join(logdir, f"cache_latents_{h}.log")
        t0 = time.time()
        with open(log, "w") as fh:
            rc = subprocess.run([sys.executable, os.path.join(src, "wan_cache_latents.py"), "--dataset_config", tomls[h], "--vae",
                                 os.path.join(m, "wan_2.1_vae.safetensors"), "--vae_dtype", "float16", "--vae_cache_cpu"],
                                cwd=mt, env=dict(os.environ, CUDA_VISIBLE_DEVICES=str(gpu)), stdout=fh, stderr=subprocess.STDOUT).returncode
        res[f"cache_latents_{h}"] = dict(rc=rc, min=round((time.time() - t0) / 60, 1))
        ev.say(f"잠재 캐시 {h}:", res[f"cache_latents_{h}"])
    ths = [threading.Thread(target=cache_lat, args=(h, g % max(1, ng))) for g, h in enumerate(("a", "b"))]
    for t in ths:
        t.start()
    for t in ths:
        t.join()
    t0 = time.time()
    with open(os.path.join(logdir, "cache_text.log"), "w") as fh:
        rc = subprocess.run([sys.executable, os.path.join(src, "wan_cache_text_encoder_outputs.py"), "--dataset_config", tomls["all"],
                             "--t5", os.path.join(m, "models_t5_umt5-xxl-enc-bf16.pth"), "--batch_size", "8", "--fp8_t5"],
                            cwd=mt, env=dict(os.environ, CUDA_VISIBLE_DEVICES="0"), stdout=fh, stderr=subprocess.STDOUT).returncode
    res["cache_text"] = dict(rc=rc, min=round((time.time() - t0) / 60, 1))
    ev.say("글 캐시:", res["cache_text"])
    if any(v.get("rc") for k, v in res.items() if k.startswith("cache")):
        raise SystemExit("캐시 실패 — train/ 기록을 Claude에게")

    # 3) 학습(GPU 0) + 4) 저장본 평가(GPU 1)
    out = os.path.join(W, "out_v2")
    os.makedirs(out, exist_ok=True)
    tlog = os.path.join(logdir, "train.log")
    cmd = [sys.executable, "-m", "accelerate.commands.launch", "--num_cpu_threads_per_process", "1", "--num_processes", "1", "--mixed_precision", "fp16",
           os.path.join(src, "wan_train_network.py"), "--task", "t2v-1.3B", "--dit", dit, "--dataset_config", tomls["all"],
           "--sdpa", "--mixed_precision", "fp16", "--optimizer_type", "AdamW", "--learning_rate", "2e-4",
           "--gradient_checkpointing", "--max_data_loader_n_workers", "2", "--persistent_data_loader_workers",
           "--network_module", "networks.lora_wan", "--network_dim", "32", "--network_alpha", "16",
           "--timestep_sampling", "shift", "--discrete_flow_shift", "3.0", "--max_train_steps", str(a.steps),
           "--save_every_n_steps", str(a.save_every), "--seed", "42", "--output_dir", out, "--output_name", a.name]
    done = threading.Event()
    eval_steps = [int(x) for x in a.eval_steps.split(",") if x]
    names = ["0", "1", "2", "3", "1v", "3v", "4r"]
    prompts = {str(i): p for i, p in enumerate(pc.PROMPTS)}
    prompts.update(e3.EXTRA)
    sd = os.path.join(W, "samples_ckpt")
    os.makedirs(sd, exist_ok=True)
    items = [(f"{n}_s{s}", prompts[n], 1000 * (k + 1) + s) for k, n in enumerate(names) for s in e3.SEEDS]  # 평가 3판과 같은 씨앗

    def evaluator():
        gpu = 1 if ng > 1 else 0
        lock = threading.Lock()
        pending = list(eval_steps)
        while pending:
            st = pending[0]
            cands = [os.path.join(out, f"{a.name}-step{st:08d}.safetensors")]
            if st >= a.steps and done.is_set():  # 마지막 스텝은 최종 파일 이름으로만 남을 수도 있다
                cands.append(os.path.join(out, f"{a.name}.safetensors"))
            f = next((c for c in cands if os.path.exists(c)), cands[0])
            if os.path.exists(f):
                s1 = os.path.getsize(f)
                time.sleep(15)
                if os.path.getsize(f) != s1:
                    continue
                lora = pc.merge_ready(f, dit)
                ev.say(f"저장본 {st}스텝 평가 시작(GPU {gpu})")
                try:
                    ev.run_group(dict(tag=f"st{st}", mult=0.8, neg=None, items=items, dit=dit, lora=lora, mt=mt, sd=sd, logdir=logdir, cpu_noise=True), gpu, lock)
                except Exception as e:  # 평가 실패가 학습을 멈추지 않게
                    ev.say("평가 실패:", e)
                pending.pop(0)
            elif done.is_set():
                ev.say(f"저장본 {st}스텝 없음 — 평가 건너뜀")
                pending.pop(0)
            else:
                time.sleep(60)

    eth = threading.Thread(target=evaluator)
    eth.start()
    t0 = time.time()
    left = t_end - time.time() - 45 * 60  # 마지막 평가·묶기에 45분
    ev.say(f"학습 시작 {a.steps}스텝(fp16, 예상 {a.steps * 4.41 / 3600:.1f}시간), 시간 한도 {left / 3600:.1f}시간")
    with open(tlog, "w", encoding="utf-8") as fh:
        p = subprocess.Popen(cmd, cwd=mt, env=dict(os.environ, CUDA_VISIBLE_DEVICES="0", PYTHONUNBUFFERED="1"),
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace")
        last = 0
        for line in p.stdout:
            fh.write(line)
            if ("steps:" in line and time.time() - last > 300) or "Error" in line or "Traceback" in line:
                ev.say(line.rstrip()[-140:])
                last = time.time()
            if time.time() - t0 > left:
                ev.say("시간 한도 — 학습을 멈춤(저장본까지만)")
                p.kill()
                break
        p.wait()
    done.set()
    res["train"] = dict(rc=p.returncode, min=round((time.time() - t0) / 60, 1))
    ev.say("학습 끝:", res["train"])
    eth.join()

    # 5) 시트·묶기
    base_dir = os.path.join(a.out, "ckpt_compare")
    conds = [f"st{s}" for s in eval_steps]
    e3.sheets(ev, sd, base_dir, names, conds)
    loras = sorted(glob.glob(os.path.join(out, f"{a.name}*.safetensors")))
    loras = [f for f in loras if not f.endswith("_merge.safetensors")]
    res["loras"] = [os.path.basename(f) for f in loras]
    json.dump(res, open(os.path.join(logdir, "summary.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    zp = os.path.join(a.out, f"{a.name}_out.zip")
    with zipfile.ZipFile(zp, "w", zipfile.ZIP_STORED) as z:
        for f in loras:
            z.write(f, "lora/" + os.path.basename(f))
        for f in sorted(glob.glob(os.path.join(sd, "*.mp4"))):
            z.write(f, "samples_ckpt/" + os.path.basename(f))
        for d in ("ckpt_compare", "train"):
            for f in sorted(glob.glob(os.path.join(a.out, d, "*"))):
                z.write(f, os.path.relpath(f, a.out))
    ev.say(f"완료 → {zp} ({os.path.getsize(zp) / 1e9:.2f}GB)", json.dumps(res, ensure_ascii=False))
    if shutil.which("rclone") and os.path.exists(os.path.expanduser("~/.config/rclone/rclone.conf")):
        r = subprocess.run(["rclone", "copy", zp, "gdrive:AI-sfa/07_도구/PC_WanLoRA/"], capture_output=True, text=True)
        ev.say("Drive 업로드:", "성공 → AI-sfa/07_도구/PC_WanLoRA/" if r.returncode == 0 else "실패 — Output 탭에서 받아 주세요")


if __name__ == "__main__":
    main()
