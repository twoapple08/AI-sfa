@echo off
chcp 65001 >nul
rem Nakamura-style video LoRA (Wan2.1 T2V 1.3B) on PC-bang RTX 5060 8GB. One file does everything. 2026-10-27
rem Install (Python 3.11, torch cu128, musubi-tuner) -> models 14.5GB (HuggingFace, no login) -> data (Drive)
rem -> cache -> train with time limit -> before/after sample videos -> C:\aisfa\wan_out.zip
rem No accounts/tokens. Everything under C:\aisfa. Delete C:\aisfa when done.
rem Total time limit for cache+train+samples (minutes). Default 170 leaves about 40-60 min for install/download in a 4 hour slot.
set MINUTES=170
if not "%1"=="" set MINUTES=%1
set ROOT=C:\aisfa
set W=%ROOT%\wan
set PY=%ROOT%\py\python.exe
set RAW=https://raw.githubusercontent.com/twoapple08/AI-sfa/ccr-bccf15a6-d6ee46/tools
set MT=f8a1b03794a49239a3539015075f5123d6c07d66
set HF=https://huggingface.co
if not exist %W%\models mkdir %W%\models
cd /d %ROOT%

echo [setup 1/4] Python 3.11
if not exist %PY% (
  curl -L -o py311.exe https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe
  py311.exe /quiet InstallAllUsers=0 TargetDir=%ROOT%\py PrependPath=0 Include_test=0 Include_launcher=0 Shortcuts=0 AssociateFiles=0
)
%PY% --version || (echo Python install failed & pause & exit /b 1)

echo [setup 2/4] PyTorch cu128 for RTX 5060
%PY% -c "import torch;assert torch.cuda.is_available()" 2>nul || (
  %PY% -m pip install -q --upgrade pip
  %PY% -m pip install -q torch torchvision --index-url https://download.pytorch.org/whl/cu128
)
%PY% -c "import torch;print('torch',torch.__version__,'cuda',torch.cuda.is_available(),torch.cuda.get_device_name(0))" || (echo torch failed & pause & exit /b 1)

echo [setup 3/4] musubi-tuner (fixed version)
if not exist %W%\musubi\src (
  curl -L -o %W%\musubi.zip https://github.com/kohya-ss/musubi-tuner/archive/%MT%.zip
  tar -xf %W%\musubi.zip -C %W%
  move %W%\musubi-tuner-%MT% %W%\musubi >nul
)
%PY% -m pip install -q -e %W%\musubi || (echo musubi install failed & pause & exit /b 1)

echo [setup 4/4] models (14.5GB, resumable) and data
curl -L -C - -o %W%\models\wan2.1_t2v_1.3B_bf16.safetensors %HF%/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/diffusion_models/wan2.1_t2v_1.3B_bf16.safetensors
curl -L -C - -o %W%\models\wan_2.1_vae.safetensors %HF%/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/vae/wan_2.1_vae.safetensors
curl -L -C - -o %W%\models\models_t5_umt5-xxl-enc-bf16.pth %HF%/Wan-AI/Wan2.1-T2V-1.3B/resolve/main/models_t5_umt5-xxl-enc-bf16.pth
if not exist %W%\data\video (
  if not exist %ROOT%\wanlora.zip curl -L -o %ROOT%\wanlora.zip "https://drive.usercontent.google.com/download?id=1YdosWijIlDx0vaTvIxos8rhlkY3CRH8m&export=download&confirm=t"
  if not exist %W%\data mkdir %W%\data
  tar -xf %ROOT%\wanlora.zip -C %W%\data || (echo wanlora.zip missing or not shared. Download it from Drive to C:\aisfa\wanlora.zip & pause & exit /b 1)
)
curl -L -o %W%\pc_wan_lora_run.py %RAW%/pc_wan_lora_run.py

echo Running cache + train + samples, up to %MINUTES% minutes.
%PY% %W%\pc_wan_lora_run.py %W% --minutes %MINUTES%
echo.
echo DONE. Upload C:\aisfa\wan_out.zip to Drive and send the link. Also send the lines with "s/it" or "it/s" above.
pause
