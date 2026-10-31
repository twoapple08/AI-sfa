@echo off
setlocal
rem (한국어 윈도 cmd 기본 코드페이지 949에 맞춰 CP949로 저장. UTF-8+chcp 65001은 줄을 잘못 읽었다, 2026-10-25)
rem AI-sfa 인물 자르기 한 번에 실행 (PC방용, 모두 H 드라이브에 설치) - docs/PC-PERSON-MASK-GUIDE-2026-10-25.md
set ROOT=H:\fx\lora
set TMP=H:\fx\tmp
set TEMP=H:\fx\tmp
set HF_HOME=H:\fx\hf
set UV_CACHE_DIR=H:\fx\uvcache
set UV_PYTHON_INSTALL_DIR=H:\fx\py
set PIP_NO_CACHE_DIR=1
set SAM2_BUILD_CUDA=0
rem C 드라이브에 아무것도 남기지 않게(PC방 C 여유 1GB, 2026-10-25): 실행 중 사용자 폴더,AppData,각종 캐시를 H로
set USERPROFILE=H:\fx\home
set HOME=H:\fx\home
set APPDATA=H:\fx\home\AppData\Roaming
set LOCALAPPDATA=H:\fx\home\AppData\Local
set CUDA_CACHE_PATH=H:\fx\cudacache
set TORCH_HOME=H:\fx\torch
set XDG_CACHE_HOME=H:\fx\home\.cache
set TRITON_CACHE_DIR=H:\fx\home\.triton
set PYTHONUSERBASE=H:\fx\home\pyuser
set MPLCONFIGDIR=H:\fx\home\mpl
set PIP_CACHE_DIR=H:\fx\uvcache\pip
set HF_HUB_DISABLE_XET=1
for %%D in (H:\fx\tmp H:\fx\hf H:\fx\uvcache H:\fx\py H:\fx\tools H:\fx\home\AppData\Roaming H:\fx\home\AppData\Local H:\fx\cudacache H:\fx\torch) do if not exist %%D mkdir %%D
for /f "tokens=3" %%S in ('dir /-c C:\ ^| find "bytes free"') do echo C 드라이브 남은 공간: %%S 바이트
cd /d %ROOT% || (echo [오류] %ROOT% 폴더가 없습니다. 안내서 1번대로 파일을 넣어 주세요. & pause & exit /b 1)

for %%F in (lora_person_mask.py isnetis.onnx) do if not exist %ROOT%\%%F (echo [오류] %ROOT%\%%F 가 없습니다. Drive PC실행 폴더에서 받아 넣어 주세요. & pause & exit /b 1)

rem 1) 설치 도구 uv (파일 하나)
if not exist H:\fx\tools\uv.exe (
  echo [1/4] 설치 도구 uv 받는 중...
  powershell -NoProfile -ExecutionPolicy Bypass -Command "Invoke-WebRequest https://github.com/astral-sh/uv/releases/download/0.5.31/uv-x86_64-pc-windows-msvc.zip -OutFile H:\fx\tmp\uv.zip; Expand-Archive -Force H:\fx\tmp\uv.zip H:\fx\tools"
)
if not exist H:\fx\tools\uv.exe (echo [오류] uv를 받지 못했습니다. 인터넷 연결을 확인해 주세요. & pause & exit /b 1)
set UV=H:\fx\tools\uv.exe

rem 2) 파이썬 3.11 + 패키지 (이미 되면 건너뜀)
set PY=%ROOT%\env\Scripts\python.exe
"%PY%" -c "import torch, sam2, cv2, transformers, onnxruntime; assert torch.cuda.is_available()" >nul 2>&1
if errorlevel 1 (
  echo [2/4] 파이썬과 패키지 설치 중... 처음 한 번은 약 3GB를 받습니다.
  if not exist "%PY%" "%UV%" venv %ROOT%\env --python 3.11 || (echo [오류] 파이썬 설치 실패 & pause & exit /b 1)
  "%UV%" pip install --python "%PY%" torch==2.5.1 torchvision==0.20.1 --index-url https://download.pytorch.org/whl/cu124 || (echo [오류] torch 설치 실패 & pause & exit /b 1)
  "%UV%" pip install --python "%PY%" sam2 huggingface_hub opencv-python "transformers==4.49.0" onnxruntime || (echo [오류] 패키지 설치 실패 & pause & exit /b 1)
) else (
  echo [2/4] 설치돼 있음 - 건너뜀
)
"%PY%" -c "import psutil" >nul 2>&1 || "%UV%" pip install --python "%PY%" psutil
"%PY%" -c "import torch; print('GPU:', torch.cuda.is_available(), torch.cuda.get_device_name(0) if torch.cuda.is_available() else '')"

rem 3) 클립 풀기
if not exist %ROOT%\clips\c0001.mp4 (
  if not exist %ROOT%\lora_clips_781.zip (echo [오류] lora_clips_781.zip 이 없습니다. & pause & exit /b 1)
  echo [3/4] 클립 압축 푸는 중...
  tar -xf %ROOT%\lora_clips_781.zip -C %ROOT% || (echo [오류] 압축 풀기 실패 & pause & exit /b 1)
) else (
  echo [3/4] 클립 있음 - 건너뜀
)

rem 4) 인물 자르기 - 두 단계로 나눠 메모리를 적게 씀(한 번에 다 켜니 C의 pagefile이 8GB 넘게 늘었다). 다시 실행하면 끝난 클립은 건너뜀
echo 다른 프로그램(크롬 등)을 닫아 두면 C 드라이브 가상 메모리가 덜 늘어납니다.
echo [4/4] 1단계: GPU로 인물 찾기 - 클립마다 한 줄씩 나옵니다
"%PY%" %ROOT%\lora_person_mask.py %ROOT%\clips %ROOT%\person_raw --model mix --stage gdino --conf 0.3 --clean --resume
if errorlevel 1 (
  echo 반정밀도에서 문제가 생겨 보통 정밀도로 다시 합니다.
  "%PY%" %ROOT%\lora_person_mask.py %ROOT%\clips %ROOT%\person_raw --model mix --stage gdino --conf 0.3 --clean --resume --half 0
  if errorlevel 1 (echo [오류] 1단계 실행 중 문제가 생겼습니다. 이 창을 찍어 보내 주세요. & pause & exit /b 1)
)
echo [4/4] 2단계: 인물 안 구멍 메우기
"%PY%" %ROOT%\lora_person_mask.py %ROOT%\clips %ROOT%\person --model mix --stage anime --raw %ROOT%\person_raw --anime %ROOT%\isnetis.onnx --grow 2 --sheet %ROOT%\person_check.jpg
if errorlevel 1 (echo [오류] 2단계 실행 중 문제가 생겼습니다. 이 창을 찍어 보내 주세요. & pause & exit /b 1)

echo.
for /f "tokens=3" %%S in ('dir /-c C:\ ^| find "bytes free"') do echo C 드라이브 남은 공간: %%S 바이트
echo 끝났습니다. %ROOT%\person 폴더를 Drive AI-sfa/02_분석자료/LoRA_클립/인물마스크/ 에 올려 주세요.
pause
