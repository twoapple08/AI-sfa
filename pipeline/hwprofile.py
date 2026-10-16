#!/usr/bin/env python3
"""Detect the current machine and pick a processing tier.

The user's PC changes (GTX 1050 Ti 4 GB ... RTX 4070/4080/5060, varying RAM), so every
pipeline step calls detect() instead of assuming a spec. Standard library only; uses
torch or nvidia-smi when available.

Usage: python -m pipeline.hwprofile            # prints and writes hardware_profile.json
"""
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path


def _ram_bytes():
    try:
        if sys.platform == 'win32':
            import ctypes

            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [('dwLength', ctypes.c_ulong), ('dwMemoryLoad', ctypes.c_ulong),
                            ('ullTotalPhys', ctypes.c_ulonglong), ('ullAvailPhys', ctypes.c_ulonglong),
                            ('ullTotalPageFile', ctypes.c_ulonglong), ('ullAvailPageFile', ctypes.c_ulonglong),
                            ('ullTotalVirtual', ctypes.c_ulonglong), ('ullAvailVirtual', ctypes.c_ulonglong),
                            ('ullAvailExtendedVirtual', ctypes.c_ulonglong)]
            stat = MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
            return int(stat.ullTotalPhys), int(stat.ullAvailPhys)
        pages, size = os.sysconf('SC_PHYS_PAGES'), os.sysconf('SC_PAGE_SIZE')
        avail = os.sysconf('SC_AVPHYS_PAGES') * size
        return pages * size, avail
    except (OSError, ValueError, AttributeError):
        return None, None


def _gpus():
    gpus = []
    try:
        import torch  # noqa: F401
        if torch.cuda.is_available():
            for i in range(torch.cuda.device_count()):
                p = torch.cuda.get_device_properties(i)
                gpus.append({'name': p.name, 'vram_bytes': int(p.total_memory), 'source': 'torch'})
            return gpus
    except Exception:
        pass
    exe = shutil.which('nvidia-smi')
    if exe:
        try:
            out = subprocess.run([exe, '--query-gpu=name,memory.total', '--format=csv,noheader,nounits'],
                                 capture_output=True, text=True, timeout=20).stdout
            for line in out.strip().splitlines():
                name, mem = [v.strip() for v in line.split(',')[:2]]
                gpus.append({'name': name, 'vram_bytes': int(float(mem)) * 1024 * 1024, 'source': 'nvidia-smi'})
        except (OSError, subprocess.SubprocessError, ValueError):
            pass
    return gpus


def tier_for(vram_gb, ram_gb):
    """Processing tier from the largest GPU's VRAM (GPU names are not trusted: same name, different VRAM)."""
    if vram_gb is None or vram_gb < 3:
        return 'cpu'
    if vram_gb <= 6:
        return 'low'
    if vram_gb < 14:
        return 'mid'
    return 'high'


TIER_DEFAULTS = {
    'cpu':  {'pose_model': 'small', 'batch': 1, 'max_side': 720, 'fp16': False, 'workers': 2},
    'low':  {'pose_model': 'small', 'batch': 2, 'max_side': 960, 'fp16': True, 'workers': 2},
    'mid':  {'pose_model': 'medium', 'batch': 8, 'max_side': 1280, 'fp16': True, 'workers': 4},
    'high': {'pose_model': 'large', 'batch': 16, 'max_side': 1920, 'fp16': True, 'workers': 6},
}


def detect(work_dir='.'):
    total, avail = _ram_bytes()
    gpus = _gpus()
    vram = max((g['vram_bytes'] for g in gpus), default=None)
    vram_gb = round(vram / 2**30, 1) if vram else None
    ram_gb = round(total / 2**30, 1) if total else None
    disk = shutil.disk_usage(work_dir)
    tier = tier_for(vram_gb, ram_gb)
    settings = dict(TIER_DEFAULTS[tier])
    if ram_gb is not None and ram_gb < 12:
        settings['workers'] = min(settings['workers'], 2)
    return {
        'os': f'{platform.system()} {platform.release()}', 'python': platform.python_version(),
        'cpu': platform.processor() or platform.machine(), 'cpu_cores': os.cpu_count(),
        'ram_gb': ram_gb, 'ram_available_gb': round(avail / 2**30, 1) if avail else None,
        'gpus': [{'name': g['name'], 'vram_gb': round(g['vram_bytes'] / 2**30, 1), 'source': g['source']} for g in gpus],
        'disk_free_gb': round(disk.free / 2**30, 1),
        'tools': {name: bool(shutil.which(name)) for name in ('ffmpeg', 'ffprobe', 'git', 'nvidia-smi')},
        'tier': tier, 'settings': settings,
    }


def main():
    profile = detect()
    Path('hardware_profile.json').write_text(json.dumps(profile, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps(profile, ensure_ascii=False, indent=1))
    warn = []
    if profile['disk_free_gb'] < 200:
        warn.append(f"디스크 여유 {profile['disk_free_gb']}GB: 클립 대량 수집에는 200GB 이상 권장")
    for tool, ok in profile['tools'].items():
        if not ok and tool != 'nvidia-smi':
            warn.append(f'{tool} 없음: 설치 필요')
    if not profile['gpus']:
        warn.append('GPU 감지 안 됨: NVIDIA 드라이버 확인(없으면 CPU 등급으로 진행)')
    for w in warn:
        print('주의:', w)


if __name__ == '__main__':
    main()
