#!/usr/bin/env python3
"""Create .venv for stage 2+ and install the PyTorch build this PC's GPU and driver can run.

The PC changes (GTX 1050 Ti ... RTX 5060), so the CUDA channel is chosen at run time:
the newest channel that the driver supports and that still ships kernels for the GPU's
compute capability (cu128+ dropped Pascal sm_6x, cu130 dropped Volta sm_70).

Usage (repository root):  python -m pipeline.setup_env [--dry-run]
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VENV = ROOT / '.venv'
REQUIREMENTS = Path(__file__).resolve().parent / 'requirements-stage2.txt'
# (channel, minimum driver CUDA version, minimum compute capability, maximum compute capability)
CHANNELS = [('cu130', 13.0, 7.5, 99.0), ('cu128', 12.8, 7.0, 99.0),
            ('cu126', 12.6, 5.0, 9.0), ('cu118', 11.8, 5.0, 9.0)]


def nvidia_info():
    """(compute capability, driver CUDA version) of the first NVIDIA GPU, or (None, None)."""
    exe = shutil.which('nvidia-smi')
    if not exe:
        return None, None
    try:
        cap = subprocess.run([exe, '--query-gpu=compute_cap', '--format=csv,noheader'],
                             capture_output=True, text=True, timeout=20).stdout.split()
        head = subprocess.run([exe], capture_output=True, text=True, timeout=20).stdout
        cuda = re.search(r'CUDA Version:\s*([\d.]+)', head)
        return (float(cap[0]) if cap else None), (float(cuda.group(1)) if cuda else None)
    except (OSError, subprocess.SubprocessError, ValueError):
        return None, None


def torch_channel(compute_cap, driver_cuda):
    """Newest PyTorch wheel channel usable here; 'cpu' when no usable CUDA channel exists."""
    if compute_cap is None or driver_cuda is None:
        return 'cpu'
    for name, min_driver, min_cap, max_cap in CHANNELS:
        if driver_cuda >= min_driver and min_cap <= compute_cap <= max_cap:
            return name
    return 'cpu'


VERIFY = r'''
import json, torch
r = {"torch": torch.__version__, "cuda": torch.version.cuda, "available": torch.cuda.is_available()}
if r["available"]:
    major, minor = torch.cuda.get_device_capability(0)
    r["device"] = torch.cuda.get_device_name(0)
    r["arch_supported"] = f"sm_{major}{minor}" in torch.cuda.get_arch_list()
    x = torch.randn(512, 512, device="cuda")
    r["matmul_ok"] = bool(torch.isfinite(x @ x).all().item())
print(json.dumps(r))
'''


def venv_python():
    return VENV / ('Scripts/python.exe' if sys.platform == 'win32' else 'bin/python')


def run(cmd):
    print('>', ' '.join(str(c) for c in cmd), flush=True)
    subprocess.run([str(c) for c in cmd], check=True)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--dry-run', action='store_true')
    a = ap.parse_args(argv)
    cap, cuda = nvidia_info()
    channel = torch_channel(cap, cuda)
    print(f'GPU compute capability {cap}, driver CUDA {cuda} -> PyTorch channel {channel}')
    if cap is not None and channel == 'cpu':
        print('주의: 이 GPU용 CUDA 빌드를 고르지 못했다. NVIDIA 드라이버를 최신으로 올린 뒤 다시 실행한다.')
    if a.dry_run:
        return
    if not venv_python().exists():
        run([sys.executable, '-m', 'venv', VENV])
    py = venv_python()
    run([py, '-m', 'pip', 'install', '--upgrade', 'pip'])
    run([py, '-m', 'pip', 'install', 'torch', 'torchvision',
         '--index-url', f'https://download.pytorch.org/whl/{channel}'])
    run([py, '-m', 'pip', 'install', '-r', REQUIREMENTS])
    result = json.loads(subprocess.run([str(py), '-c', VERIFY], capture_output=True, text=True,
                                       check=True).stdout.strip().splitlines()[-1])
    result.update(channel=channel, compute_cap=cap, driver_cuda=cuda)
    (VENV / 'aisfa_env.json').write_text(json.dumps(result, indent=1), encoding='utf-8')
    print(json.dumps(result, indent=1))
    if channel != 'cpu' and not (result.get('available') and result.get('arch_supported') and result.get('matmul_ok')):
        print('주의: GPU 검증 실패. CPU로는 동작하지만 느리다. 위 결과를 대화창에 붙여 준다.')


if __name__ == '__main__':
    main()
