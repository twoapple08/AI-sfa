#!/usr/bin/env python3
"""Kaggle T4 x2: Wan2.1 1.3B LoRA 학습이 T4에서 되는지 시험 (2026-10-28 밤).

사용자 GPU가 당분간 1050 Ti(4GB)뿐이라 학습을 Kaggle로 옮길 수 있는지 먼저 잰다. T4는 bf16 연산이 에뮬레이션(느림)이라 두 방식을 동시에 비교한다.
  GPU 0: DiT fp16 파일 + --mixed_precision fp16 (musubi가 fp16 DiT면 fp16/no만 허용)
  GPU 1: DiT bf16 파일 + --mixed_precision bf16 (PC와 같은 방식, 느릴 수 있음)
나머지 설정은 PC 학습(pc_wan_lora_run.py)과 같다: LoRA 32/16, AdamW 2e-4, shift 3.0, gradient checkpointing, 시드 42. fp8_base는 뺐다(T4 16GB면 필요 없음).
자료: Drive wanlora.zip(482조각) 중 48조각만(10개마다 1개) — 캐시 시간·스텝 속도·손실·메모리만 본다. 결과 LoRA는 쓰지 않는다.
PC 기준(10-28, 5060, 482조각): 2.85 s/it, avr_loss 10스텝 0.182 / 20 0.169 / 40 0.164 / 60 0.159 / 100 0.161.
도우미(fetch·MODELS·set_t5_dtype)는 kaggle_wan_eval_worker.py를 같은 브랜치에서 받아 쓴다.
사용(노트북): python kaggle_wan_train_test_worker.py [--out /kaggle/working] [--steps 100]
"""
import argparse
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import zipfile

W = os.environ.get("WAN_DIR", "/tmp/wan")
RAW = "https://raw.githubusercontent.com/twoapple08/AI-sfa/ccr-bccf15a6-d6ee46/tools"
WANLORA_ZIP = "https://drive.usercontent.google.com/download?export=download&confirm=t&id=1YdosWijIlDx0vaTvIxos8rhlkY3CRH8m"
PC_REF = {10: 0.182, 20: 0.169, 40: 0.164, 60: 0.159, 100: 0.161}
T0 = time.time()


def say(*a):
    print(f"[{(time.time() - T0) / 60:5.1f}분]", *a, flush=True)


def run(cmd, cwd, log, env=None, timeout=None, show=("Error", "error", "Traceback", "steps:")):
    t0 = time.time()
    last = 0
    with open(log, "a", encoding="utf-8") as fh:
        p = subprocess.Popen(cmd, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace")
        for line in p.stdout:
            fh.write(line)
            if any(s in line for s in show) and time.time() - last > 30:  # 진행 표시는 30초에 한 줄만
                say(os.path.basename(log), line.rstrip()[-140:])
                last = time.time()
            if timeout and time.time() - t0 > timeout:
                p.kill()
                break
        p.wait()
    return p.returncode, time.time() - t0


class MemWatch(threading.Thread):
    """nvidia-smi로 GPU별 최대 메모리(MiB)를 잰다."""
    def __init__(self):
        super().__init__(daemon=True)
        self.peak, self.stop = {}, False

    def run(self):
        while not self.stop:
            r = subprocess.run(["nvidia-smi", "--query-gpu=index,memory.used", "--format=csv,noheader,nounits"], capture_output=True, text=True)
            for line in r.stdout.strip().splitlines():
                i, m = (int(x) for x in line.split(","))
                self.peak[i] = max(self.peak.get(i, 0), m)
            time.sleep(5)


def parse_steps(log):
    t = open(log, encoding="utf-8", errors="replace").read()
    d = {}
    for m in re.finditer(r"steps: +\d+%\|[^|]*\| (\d+)/(\d+) \[[^,]*, +([\d.]+)(s/it|it/s), avr_loss=([\d.na]+)", t):
        sit = float(m.group(3)) if m.group(4) == "s/it" else 1 / float(m.group(3))
        d[int(m.group(1))] = (round(sit, 2), m.group(5))
    return d, "avr_loss=nan" in t.lower()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="/kaggle/working")
    ap.add_argument("--steps", type=int, default=100)
    ap.add_argument("--clips", type=int, default=48)
    a = ap.parse_args()
    os.makedirs(W, exist_ok=True)
    logdir = os.path.join(a.out, "train_test")
    os.makedirs(logdir, exist_ok=True)
    subprocess.run(["curl", "-sSL", "-o", f"{W}/kaggle_wan_eval_worker.py", f"{RAW}/kaggle_wan_eval_worker.py"], check=True)
    sys.path.insert(0, W)
    import torch
    import kaggle_wan_eval_worker as ev
    ng = torch.cuda.device_count()
    say("GPU", ng, "장", torch.cuda.get_device_name(0), torch.cuda.get_device_capability(0))
    x, y = torch.randn(256, 1024, device="cuda"), torch.randn(1024, 256, device="cuda")
    say(f"bf16 곱셈 상대 오차 {float(((x.bfloat16() @ y.bfloat16()).float() - x @ y).abs().mean() / (x @ y).abs().mean()):.4f}")

    # 설치·받기(평가 노트북과 같은 musubi 커밋)
    mt = os.path.join(W, "musubi")
    if not os.path.exists(mt):
        subprocess.run(["curl", "-sSL", "-o", f"{W}/mt.zip", f"https://github.com/kohya-ss/musubi-tuner/archive/{ev.MT}.zip"], check=True)
        with zipfile.ZipFile(f"{W}/mt.zip") as z:
            z.extractall(W)
        os.rename(os.path.join(W, f"musubi-tuner-{ev.MT}"), mt)
    say("musubi-tuner 설치")
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-e", mt], check=True, stdout=subprocess.DEVNULL)
    ev.set_t5_dtype(mt, "bfloat16")
    m = os.path.join(W, "models")
    os.makedirs(m, exist_ok=True)
    ths = [threading.Thread(target=ev.fetch, args=(f"{ev.HF}/{ev.MODELS[k][0]}", os.path.join(m, os.path.basename(ev.MODELS[k][0])), ev.MODELS[k][1]))
           for k in ("dit_fp16", "dit_bf16", "vae", "t5")]
    zp = os.path.join(W, "wanlora.zip")
    ths.append(threading.Thread(target=lambda: os.path.exists(zp) or subprocess.run(["curl", "-sSL", "--retry", "5", "-o", zp, WANLORA_ZIP], check=True)))
    say("모델 4개 + 학습 자료(wanlora.zip 98MB) 받는 중")
    for t in ths:
        t.start()
    for t in ths:
        t.join()

    # 자료 일부(10개마다 1개)
    data = os.path.join(W, "data")
    vid = os.path.join(data, "video")
    if not os.path.exists(vid):
        os.makedirs(vid)
        with zipfile.ZipFile(zp) as z:
            mp4 = sorted(n for n in z.namelist() if n.startswith("video/") and n.endswith(".mp4"))
            step = max(1, len(mp4) // a.clips)
            for n in mp4[::step][:a.clips]:
                for nn in (n, n[:-4] + ".txt"):
                    open(os.path.join(data, nn), "wb").write(z.read(nn))
            toml = z.read("dataset.toml").decode("utf-8")
        open(os.path.join(data, "dataset.toml"), "w", encoding="utf-8").write(toml.replace("DATA_ROOT", data))
    toml = os.path.join(data, "dataset.toml")
    nclip = len(glob.glob(os.path.join(vid, "*.mp4")))
    say(f"자료 {nclip}조각")
    src = os.path.join(mt, "src", "musubi_tuner")
    env0 = dict(os.environ, CUDA_VISIBLE_DEVICES="0", PYTHONUNBUFFERED="1")
    res = {"clips": nclip, "gpu": torch.cuda.get_device_name(0)}
    rc, sec = run([sys.executable, os.path.join(src, "wan_cache_latents.py"), "--dataset_config", toml, "--vae", os.path.join(m, "wan_2.1_vae.safetensors"),
                   "--vae_cache_cpu"], mt, os.path.join(logdir, "cache_latents.log"), env0)
    res["cache_latents"] = dict(rc=rc, sec=round(sec), sec_per_clip=round(sec / max(1, nclip), 1), est_482_min=round(sec / max(1, nclip) * 482 / 60))
    say("잠재 캐시", res["cache_latents"])
    rc, sec = run([sys.executable, os.path.join(src, "wan_cache_text_encoder_outputs.py"), "--dataset_config", toml,
                   "--t5", os.path.join(m, "models_t5_umt5-xxl-enc-bf16.pth"), "--batch_size", "8", "--fp8_t5"], mt, os.path.join(logdir, "cache_text.log"), env0)
    if rc:  # T4에서 fp8 저장이 안 되면 bf16 저장으로
        rc, sec = run([sys.executable, os.path.join(src, "wan_cache_text_encoder_outputs.py"), "--dataset_config", toml,
                       "--t5", os.path.join(m, "models_t5_umt5-xxl-enc-bf16.pth"), "--batch_size", "8"], mt, os.path.join(logdir, "cache_text.log"), env0)
    res["cache_text"] = dict(rc=rc, sec=round(sec))
    say("글 캐시", res["cache_text"])

    # 두 방식 동시 학습
    mw = MemWatch()
    mw.start()
    variants = {"fp16": ("dit_fp16", "fp16", 0), "bf16": ("dit_bf16", "bf16", 1 if ng > 1 else 0)}
    out = {}

    def train(name):
        dk, mp, gpu = variants[name]
        o = os.path.join(W, "out_" + name)
        log = os.path.join(logdir, f"train_{name}.log")
        cmd = [sys.executable, "-m", "accelerate.commands.launch", "--num_cpu_threads_per_process", "1", "--num_processes", "1", "--mixed_precision", mp,
               os.path.join(src, "wan_train_network.py"), "--task", "t2v-1.3B", "--dit", os.path.join(m, os.path.basename(ev.MODELS[dk][0])),
               "--dataset_config", toml, "--sdpa", "--mixed_precision", mp, "--optimizer_type", "AdamW", "--learning_rate", "2e-4",
               "--gradient_checkpointing", "--max_data_loader_n_workers", "2", "--persistent_data_loader_workers",
               "--network_module", "networks.lora_wan", "--network_dim", "32", "--network_alpha", "16",
               "--timestep_sampling", "shift", "--discrete_flow_shift", "3.0", "--max_train_steps", str(a.steps),
               "--seed", "42", "--output_dir", o, "--output_name", "test_" + name]
        rc, sec = run(cmd, mt, log, dict(os.environ, CUDA_VISIBLE_DEVICES=str(gpu), PYTHONUNBUFFERED="1"), timeout=50 * 60)
        steps, nan = parse_steps(log)
        last = max(steps) if steps else 0
        out[name] = dict(rc=rc, min=round(sec / 60, 1), gpu=gpu, last_step=last, nan=nan,
                         s_per_it=steps[last][0] if last else None,
                         loss={k: steps[k][1] for k in sorted(steps) if k in PC_REF or k == last},
                         est_3000_steps_h=round(steps[last][0] * 3000 / 3600, 1) if last else None)
        say(f"학습 {name}:", out[name])

    names = ["fp16", "bf16"]
    if ng > 1:
        ths = [threading.Thread(target=train, args=(n,)) for n in names]
        for t in ths:
            t.start()
        for t in ths:
            t.join()
    else:
        for n in names:
            train(n)
    mw.stop = True
    res["train"] = out
    res["peak_mem_mib"] = mw.peak
    res["pc_ref"] = dict(s_per_it=2.85, loss=PC_REF)
    json.dump(res, open(os.path.join(logdir, "summary.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    say("요약:", json.dumps(res, ensure_ascii=False))
    zp = os.path.join(a.out, "wan_train_test.zip")
    with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED) as z:
        for f in glob.glob(os.path.join(logdir, "*")):
            z.write(f, os.path.relpath(f, a.out))
    if shutil.which("rclone") and os.path.exists(os.path.expanduser("~/.config/rclone/rclone.conf")):
        r = subprocess.run(["rclone", "copy", zp, "gdrive:AI-sfa/02_분석자료/WanLoRA_평가/"], capture_output=True, text=True)
        say("Drive 업로드:", "성공" if r.returncode == 0 else "실패 — Output 탭에서 받아 주세요")
    say(f"완료 → {zp} (요약 summary.json을 Claude에게)")


if __name__ == "__main__":
    main()
