#!/usr/bin/env python3
"""PC방 5060(8GB): Wan2.1 T2V 1.3B 나카무라 스타일 LoRA — 캐시 → 학습(시간 제한) → 학습 전/후 비교 영상 → zip (2026-10-27).

사용자 결정(10-27 저녁): SFA보다 먼저 나카무라 스타일 영상 AI. 첫 시험은 '이 PC에서 영상 LoRA 학습이 되는지 + LoRA가 화풍·움직임을 바꾸는지'.
학습 도구: kohya-ss/musubi-tuner(고정 커밋, pc_wan_lora.bat가 받음). 자료: wanlora.zip(tools/wan_lora_dataset.py, 275컷 → 17–33장 조각 482개 11,410장 512×288 24fps, 캡션 = GPT 조각 캡션 444 + 컷 캡션 38·조각 기준 장 번호, full 추출, 10-28 갱신).
메모리: DiT fp8(--fp8_base) + gradient checkpointing, 처음 몇 분 안에 실패하면 블록 교체(--blocks_to_swap)를 늘려 다시.
시간: --minutes 안에 학습을 끊고(150스텝마다 저장) 남은 시간에 비교 영상을 만든다. 서버에서는 실행 시험을 못 했다(외부 코드 실행 거절) — 명령 형식은 소스 대조만.
사용: python pc_wan_lora_run.py <작업 폴더 C:\\aisfa\\wan> --minutes 170
"""
import argparse
import glob
import os
import subprocess
import sys
import time
import zipfile

PROMPTS = [  # GPT 움직임 캡션 문체(대상·장 번호·변화·리듬·카메라·컷 수, 2026-10-27). 33장 = 0–32
    "nkmr_fx, A white-yellow flash at 0-1 bursts into an orange fireball with angular dark smoke at 2-9, splits into sharp flame tongues at 10-17, and thins into gray dust through 32. Small dark debris chips scatter from 4. Mostly twos with singles at the burst; fixed camera, one cut.",
    "nkmr_fx, A cyan-white lightning bolt with a pink rim strikes down at 0-1, branches into jagged forks at 2-7, flickers on ones at 8-15, then fades into a thin glowing afterimage through 32. Fixed camera, one cut.",
    "nkmr_fx, Gray blocks tumble across 0-32 while a brown dust cloud with angular edges spreads from the ground at 3-12 and curls upward at 13-32. Mostly twos; slow lateral pan, one cut.",
    "nkmr_fx, A black-and-white radial impact frame alternates on ones at 0-3, then an orange shockwave ring with speed lines expands from the center at 4-15, holds its peak for three frames, and breaks into fading streaks through 32. Fixed camera, one cut.",
]


def run(cmd, cwd, log, timeout=None):
    print(">", " ".join(cmd[:4]), "...", flush=True)
    with open(log, "a", encoding="utf-8") as fh:
        p = subprocess.Popen(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
        t0 = time.time()
        killed = False
        for line in p.stdout:
            fh.write(line)
            if "it/s" in line or "s/it" in line or "steps:" in line or "Error" in line or "error" in line:
                print(line.rstrip()[-160:], flush=True)
            if timeout and time.time() - t0 > timeout:
                subprocess.run(["taskkill", "/T", "/F", "/PID", str(p.pid)], capture_output=True)
                killed = True
                break
        p.wait()
        return p.returncode, killed, time.time() - t0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("work")
    ap.add_argument("--minutes", type=float, default=170, help="이 스크립트 전체 시간(캐시·학습·비교 영상 포함)")
    ap.add_argument("--swap", type=int, default=0)
    ap.add_argument("--steps", type=int, default=3000)
    a = ap.parse_args()
    t_start = time.time()
    W = os.path.abspath(a.work)
    mt = os.path.join(W, "musubi")
    src = os.path.join(mt, "src", "musubi_tuner")
    py = sys.executable
    m = os.path.join(W, "models")
    dit, vae, t5 = (os.path.join(m, f) for f in ("wan2.1_t2v_1.3B_bf16.safetensors", "wan_2.1_vae.safetensors", "models_t5_umt5-xxl-enc-bf16.pth"))
    data = os.path.join(W, "data")
    toml = os.path.join(data, "dataset_pc.toml")
    open(toml, "w", encoding="utf-8").write(open(os.path.join(data, "dataset.toml"), encoding="utf-8").read().replace("DATA_ROOT", data.replace("\\", "/")))
    log = os.path.join(W, "run_log.txt")
    out = os.path.join(W, "out")
    os.makedirs(out, exist_ok=True)

    print("[1/4] 잠재 캐시(VAE)", flush=True)
    rc, _, sec = run([py, os.path.join(src, "wan_cache_latents.py"), "--dataset_config", toml, "--vae", vae, "--vae_cache_cpu"], mt, log)
    print(f"  끝 rc={rc} {sec / 60:.1f}분", flush=True)
    print("[2/4] 글 캐시(T5 fp8)", flush=True)
    rc2, _, sec = run([py, os.path.join(src, "wan_cache_text_encoder_outputs.py"), "--dataset_config", toml, "--t5", t5, "--batch_size", "8", "--fp8_t5"], mt, log)
    print(f"  끝 rc={rc2} {sec / 60:.1f}분", flush=True)
    if rc or rc2:
        print("캐시 실패 — run_log.txt 끝부분을 Claude에게 보내 주세요", flush=True)

    sample_min = 22  # 비교 영상 8개 + zip
    swap = a.swap
    for attempt in range(3):
        left = a.minutes * 60 - (time.time() - t_start) - sample_min * 60
        if left < 300:
            break
        print(f"[3/4] 학습 시도 {attempt + 1} (블록 교체 {swap}, 남은 학습 시간 {left / 60:.0f}분)", flush=True)
        cmd = [py, "-m", "accelerate.commands.launch", "--num_cpu_threads_per_process", "1", "--mixed_precision", "bf16",
               os.path.join(src, "wan_train_network.py"), "--task", "t2v-1.3B", "--dit", dit, "--dataset_config", toml,
               "--sdpa", "--mixed_precision", "bf16", "--fp8_base", "--optimizer_type", "AdamW", "--learning_rate", "2e-4",
               "--gradient_checkpointing", "--max_data_loader_n_workers", "2", "--persistent_data_loader_workers",
               "--network_module", "networks.lora_wan", "--network_dim", "32", "--network_alpha", "16",
               "--timestep_sampling", "shift", "--discrete_flow_shift", "3.0", "--max_train_steps", str(a.steps),
               "--save_every_n_steps", "150", "--seed", "42", "--output_dir", out, "--output_name", "nkmr_wan13"]
        if swap:
            cmd += ["--blocks_to_swap", str(swap)]
        rc, killed, sec = run(cmd, mt, log, timeout=left)
        print(f"  학습 끝 rc={rc} 시간 제한으로 멈춤={killed} {sec / 60:.1f}분", flush=True)
        if killed or rc == 0:
            break
        if sec < 900:  # 일찍 실패 = 메모리 부족일 가능성 → 블록 교체 늘려 다시
            swap = 15 if swap == 0 else 29
            continue
        break
    loras = sorted(glob.glob(os.path.join(out, "nkmr_wan13*.safetensors")), key=os.path.getmtime)
    print("저장된 LoRA:", [os.path.basename(x) for x in loras], flush=True)

    print("[4/4] 비교 영상(LoRA 없음/있음, 33장 24fps)", flush=True)
    sd = os.path.join(W, "samples")
    os.makedirs(sd, exist_ok=True)
    for i, p in enumerate(PROMPTS):
        for tag, lw in (("base", None), ("lora", loras[-1] if loras else None)):
            if tag == "lora" and not lw:
                continue
            cmd = [py, os.path.join(src, "wan_generate_video.py"), "--task", "t2v-1.3B", "--dit", dit, "--vae", vae, "--t5", t5, "--fp8_t5",
                   "--video_size", "288", "512", "--video_length", "33", "--fps", "24", "--infer_steps", "25", "--seed", str(100 + i),
                   "--prompt", p, "--save_path", os.path.join(sd, f"p{i}_{tag}")]
            if lw:
                cmd += ["--lora_weight", lw, "--lora_multiplier", "1.0"]
            if swap:
                cmd += ["--blocks_to_swap", str(swap)]
            rc, _, sec = run(cmd, mt, log, timeout=300)
            print(f"  p{i} {tag} rc={rc} {sec:.0f}초", flush=True)
    zp = os.path.join(os.path.dirname(W), "wan_out.zip")
    with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED) as z:
        for f in loras[-3:]:
            z.write(f, "lora/" + os.path.basename(f))
        for f in glob.glob(os.path.join(sd, "**", "*"), recursive=True):
            if os.path.isfile(f):
                z.write(f, "samples/" + os.path.relpath(f, sd))
        z.write(log, "run_log.txt")
    print(f"완료 {(time.time() - t_start) / 60:.0f}분 → {zp} 를 Drive에 올리고 Claude에게 알려 주세요", flush=True)


if __name__ == "__main__":
    main()
