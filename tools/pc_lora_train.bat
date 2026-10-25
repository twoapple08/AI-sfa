@echo off
setlocal
rem 이펙트 화풍 LoRA 학습 한 번에 실행(PC방, RTX 4060 8GB). 모두 H 드라이브에 설치. CP949로 저장(한국어 cmd 기본).
rem 기본 모델 Illustrious-XL v1.0 / 방식 LyCORIS LoCon(사용자 그림체 LoRA와 같은 계열, 따로 얹어 쓰기) / 문서 docs/PC-LORA-TRAIN-GUIDE-2026-10-25.md
set ROOT=H:\fx\train
set TMP=H:\fx\tmp
set TEMP=H:\fx\tmp
set HF_HOME=H:\fx\hf
set UV_CACHE_DIR=H:\fx\uvcache
set UV_PYTHON_INSTALL_DIR=H:\fx\py
set PIP_NO_CACHE_DIR=1
set USERPROFILE=H:\fx\home
set HOME=H:\fx\home
set APPDATA=H:\fx\home\AppData\Roaming
set LOCALAPPDATA=H:\fx\home\AppData\Local
set CUDA_CACHE_PATH=H:\fx\cudacache
set TORCH_HOME=H:\fx\torch
set XDG_CACHE_HOME=H:\fx\home\.cache
set PYTHONUSERBASE=H:\fx\home\pyuser
set MPLCONFIGDIR=H:\fx\home\mpl
set HF_HUB_DISABLE_XET=1
for %%D in (H:\fx\tmp H:\fx\hf H:\fx\uvcache H:\fx\py H:\fx\tools H:\fx\home\AppData\Roaming H:\fx\home\AppData\Local H:\fx\cudacache H:\fx\torch %ROOT%\models %ROOT%\out) do if not exist %%D mkdir %%D
for /f "tokens=3" %%S in ('dir /-c C:\ ^| find "bytes free"') do echo C 드라이브 남은 공간: %%S 바이트
cd /d %ROOT% || (echo [오류] %ROOT% 폴더가 없습니다. & pause & exit /b 1)
for %%F in (dataset.toml lora_train_data.zip) do if not exist %ROOT%\%%F (echo [오류] %ROOT%\%%F 가 없습니다. Drive 학습실행 폴더에서 받아 넣어 주세요. & pause & exit /b 1)

rem 1) 설치 도구 uv
if not exist H:\fx\tools\uv.exe (
  echo [1/6] 설치 도구 uv 받는 중...
  powershell -NoProfile -ExecutionPolicy Bypass -Command "Invoke-WebRequest https://github.com/astral-sh/uv/releases/download/0.5.31/uv-x86_64-pc-windows-msvc.zip -OutFile H:\fx\tmp\uv.zip; Expand-Archive -Force H:\fx\tmp\uv.zip H:\fx\tools"
)
if not exist H:\fx\tools\uv.exe (echo [오류] uv를 받지 못했습니다. & pause & exit /b 1)
set UV=H:\fx\tools\uv.exe

rem 2) 학습 프로그램 kohya sd-scripts v0.9.1
if not exist %ROOT%\sd-scripts\sdxl_train_network.py (
  echo [2/6] 학습 프로그램 받는 중...
  powershell -NoProfile -ExecutionPolicy Bypass -Command "Invoke-WebRequest https://github.com/kohya-ss/sd-scripts/archive/refs/tags/v0.9.1.zip -OutFile H:\fx\tmp\sdscripts.zip; Expand-Archive -Force H:\fx\tmp\sdscripts.zip H:\fx\tmp\sdscripts; Move-Item H:\fx\tmp\sdscripts\sd-scripts-0.9.1 %ROOT%\sd-scripts"
)
if not exist %ROOT%\sd-scripts\sdxl_train_network.py (echo [오류] 학습 프로그램을 받지 못했습니다. & pause & exit /b 1)

rem 3) 파이썬 3.10 + 패키지(학습 전용 환경, 인물 자르기 환경과 따로)
set PY=%ROOT%\env\Scripts\python.exe
"%PY%" -c "import numpy, cv2, torch, library, lycoris, bitsandbytes; assert numpy.__version__.startswith('1.'); assert torch.cuda.is_available()" >nul 2>&1
if errorlevel 1 (
  echo [3/6] 파이썬과 패키지 설치 중... 처음 한 번은 약 4GB를 받습니다.
  if not exist "%PY%" "%UV%" venv %ROOT%\env --python 3.10 || (echo [오류] 파이썬 설치 실패 & pause & exit /b 1)
  "%UV%" pip install --python "%PY%" torch==2.4.1 torchvision==0.19.1 --index-url https://download.pytorch.org/whl/cu124 || (echo [오류] torch 설치 실패 & pause & exit /b 1)
  pushd %ROOT%\sd-scripts
  "%UV%" pip install --python "%PY%" -r requirements.txt || (popd & echo [오류] 학습 프로그램 부품 설치 실패 & pause & exit /b 1)
  popd
  "%UV%" pip install --python "%PY%" lycoris-lora==3.1.1 || (echo [오류] LyCORIS 설치 실패 & pause & exit /b 1)
  rem sd-scripts v0.9.1의 opencv 4.8은 numpy 1.x용 - torch가 numpy 2를 끌어오면 cv2 불러오기가 깨진다(2026-10-25 PC방: _ARRAY_API not found)
  "%UV%" pip install --python "%PY%" "numpy==1.26.4" || (echo [오류] numpy 설치 실패 & pause & exit /b 1)
) else (
  echo [3/6] 설치돼 있음 - 건너뜀
)
"%PY%" -c "import torch; print('GPU:', torch.cuda.is_available(), torch.cuda.get_device_name(0) if torch.cuda.is_available() else '')"

rem 4) 기본 모델 Illustrious-XL v1.0 (6.9GB, 끊기면 이어 받음)
set MODEL=%ROOT%\models\Illustrious-XL-v1.0.safetensors
for %%A in ("%MODEL%") do set MSIZE=%%~zA
if not "%MSIZE%"=="6938040736" (
  echo [4/6] 기본 모델 받는 중... 6.9GB
  curl -L -C - -o "%MODEL%" https://huggingface.co/OnomaAIResearch/Illustrious-XL-v1.0/resolve/main/Illustrious-XL-v1.0.safetensors
)
for %%A in ("%MODEL%") do set MSIZE=%%~zA
if not "%MSIZE%"=="6938040736" (echo [오류] 기본 모델을 다 받지 못했습니다. 다시 실행하면 이어 받습니다. & pause & exit /b 1)

rem 5) 학습 자료 풀기
if not exist %ROOT%\data\c0001.txt (
  echo [5/6] 학습 자료 푸는 중...
  if not exist %ROOT%\data mkdir %ROOT%\data
  tar -xf %ROOT%\lora_train_data.zip -C %ROOT%\data || (echo [오류] 압축 풀기 실패 & pause & exit /b 1)
) else (
  echo [5/6] 학습 자료 있음 - 건너뜀
)

if /i "%~1"=="prep" (echo. & echo 준비 끝: 설치, 기본 모델, 학습 자료가 모두 H에 있습니다. 학습은 pc_lora_train.bat를 더블클릭하면 시작합니다. & pause & exit /b 0)

rem 6) 학습 - 2바퀴마다 저장(out 폴더), 중간에 멈추면 마지막 저장본부터 다시 할 수 있음
echo [6/6] 학습 시작 - 몇 시간 걸립니다. 진행 막대의 it/s 숫자와 남은 시간을 보면 됩니다.
pushd %ROOT%\sd-scripts
"%PY%" sdxl_train_network.py ^
  --pretrained_model_name_or_path "%MODEL%" ^
  --dataset_config %ROOT%\dataset.toml ^
  --output_dir %ROOT%\out --output_name nkmr_fx_ilxl ^
  --network_module lycoris.kohya --network_dim 32 --network_alpha 8 ^
  --network_args "algo=locon" "preset=full" "conv_dim=16" "conv_alpha=4" ^
  --network_train_unet_only --unet_lr 4e-4 ^
  --optimizer_type AdamW8bit --lr_scheduler cosine --lr_warmup_steps 100 ^
  --max_train_epochs 10 --save_every_n_epochs 2 --save_model_as safetensors ^
  --mixed_precision bf16 --save_precision bf16 --sdpa --gradient_checkpointing ^
  --cache_latents --cache_latents_to_disk --cache_text_encoder_outputs --cache_text_encoder_outputs_to_disk ^
  --min_snr_gamma 5 --max_data_loader_n_workers 0 --seed 42 --save_state
set RC=%errorlevel%
popd
if not "%RC%"=="0" (echo [오류] 학습 중 문제가 생겼습니다. 이 창을 찍어 보내 주세요. & pause & exit /b 1)

echo.
for /f "tokens=3" %%S in ('dir /-c C:\ ^| find "bytes free"') do echo C 드라이브 남은 공간: %%S 바이트
echo 끝났습니다. %ROOT%\out 폴더의 nkmr_fx_ilxl*.safetensors 파일들을 Drive AI-sfa/05_모델/이펙트LoRA/ 에 올려 주세요.
pause
