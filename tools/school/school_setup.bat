@echo off
setlocal
rem 학교 PC(GTX 1050 Ti 4GB, 램 16GB) 설치 한 번에. 모두 D:\sfa 에 설치한다 - C는 재부팅하면 초기화된다(2026-10-26 사용자).
rem 설치: 파이썬 환경, ComfyUI(그림 생성), AI-sfa 변환 도구, 기본 모델 Illustrious-XL v1.0, 이펙트 LoRA 1차, 선화 추출기. 문서: docs/SCHOOL-PC-GUIDE-2026-10-26.md
rem CP949로 저장(한국어 cmd 기본). 다시 실행하면 이미 된 단계는 건너뛴다.
set ROOT=D:\sfa
call "%~dp0school_env.bat"
for %%D in (%ROOT%\tmp %ROOT%\tools %ROOT%\models %ROOT%\dl) do if not exist %%D mkdir %%D
cd /d %ROOT% || (echo [오류] D:\sfa 를 만들 수 없습니다. & pause & exit /b 1)

rem 1) 설치 도구 uv
if not exist %ROOT%\tools\uv.exe (
  echo [1/7] 설치 도구 uv 받는 중...
  curl -L -o %ROOT%\tmp\uv.zip https://github.com/astral-sh/uv/releases/download/0.5.31/uv-x86_64-pc-windows-msvc.zip
  tar -xf %ROOT%\tmp\uv.zip -C %ROOT%\tools
)
if not exist %ROOT%\tools\uv.exe (echo [오류] uv를 받지 못했습니다. 인터넷 연결을 확인해 주세요. & pause & exit /b 1)
set UV=%ROOT%\tools\uv.exe

rem 2) ComfyUI v0.3.10 (그림 생성 화면)
if not exist %ROOT%\ComfyUI\main.py (
  echo [2/7] ComfyUI 받는 중...
  curl -L -o %ROOT%\tmp\comfy.zip https://github.com/comfyanonymous/ComfyUI/archive/refs/tags/v0.3.10.zip
  tar -xf %ROOT%\tmp\comfy.zip -C %ROOT%\tmp
  move %ROOT%\tmp\ComfyUI-0.3.10 %ROOT%\ComfyUI >nul
)
if not exist %ROOT%\ComfyUI\main.py (echo [오류] ComfyUI를 받지 못했습니다. & pause & exit /b 1)

rem 3) AI-sfa 변환 도구(저장소 tools 폴더) - 매번 새로 받아 최신으로
echo [3/7] AI-sfa 변환 도구 받는 중...
curl -L -o %ROOT%\tmp\aisfa.zip https://github.com/twoapple08/AI-sfa/archive/refs/heads/ccr-bccf15a6-d6ee46.zip
if exist %ROOT%\tmp\aisfa rmdir /s /q %ROOT%\tmp\aisfa
mkdir %ROOT%\tmp\aisfa
tar -xf %ROOT%\tmp\aisfa.zip -C %ROOT%\tmp\aisfa
if exist %ROOT%\aisfa rmdir /s /q %ROOT%\aisfa
for /d %%P in (%ROOT%\tmp\aisfa\*) do move "%%P" %ROOT%\aisfa >nul
if not exist %ROOT%\aisfa\tools\effect_clip_sfa.py (echo [오류] 변환 도구를 받지 못했습니다. & pause & exit /b 1)
rem 실행 중인 school_setup.bat 자신은 덮어쓰지 않는다(cmd는 bat을 읽어 가며 실행)
for %%F in (school_env school_comfy school_comfy_nofp8 school_to_sfa_fx school_to_sfa_line) do copy /y %ROOT%\aisfa\tools\school\%%F.bat %ROOT%\ >nul
copy /y %ROOT%\aisfa\tools\school\*.json %ROOT%\ >nul

rem 4) 파이썬 3.11 + 패키지(ComfyUI와 변환 도구가 같이 씀)
set PY=%ROOT%\env\Scripts\python.exe
"%PY%" -c "import torch, cv2, skimage, potrace, einops; assert torch.cuda.is_available()" >nul 2>&1
if errorlevel 1 (
  echo [4/7] 파이썬과 패키지 설치 중... 처음 한 번은 약 4GB를 받습니다.
  if not exist "%PY%" "%UV%" venv %ROOT%\env --python 3.11 || (echo [오류] 파이썬 설치 실패 & pause & exit /b 1)
  "%UV%" pip install --python "%PY%" torch==2.4.1 torchvision==0.19.1 torchaudio==2.4.1 --index-url https://download.pytorch.org/whl/cu124 || (echo [오류] torch 설치 실패 & pause & exit /b 1)
  "%UV%" pip install --python "%PY%" -r %ROOT%\ComfyUI\requirements.txt || (echo [오류] ComfyUI 부품 설치 실패 & pause & exit /b 1)
  "%UV%" pip install --python "%PY%" opencv-python-headless==4.10.0.84 scikit-image potracer einops timm huggingface_hub scipy pillow "numpy==1.26.4" || (echo [오류] 변환 도구 부품 설치 실패 & pause & exit /b 1)
  "%UV%" pip install --python "%PY%" --no-deps controlnet_aux==0.0.9 || (echo [오류] 선화 추출기 설치 실패 & pause & exit /b 1)
) else (
  echo [4/7] 설치돼 있음 - 건너뜀
)
"%PY%" -c "import torch; print('GPU:', torch.cuda.is_available(), torch.cuda.get_device_name(0) if torch.cuda.is_available() else '')"

rem 5) 기본 모델 Illustrious-XL v1.0 (6.9GB, 끊기면 이어 받음)
set MODEL=%ROOT%\ComfyUI\models\checkpoints\Illustrious-XL-v1.0.safetensors
for %%A in ("%MODEL%") do set MSIZE=%%~zA
if not "%MSIZE%"=="6938040736" (
  echo [5/7] 기본 모델 받는 중... 6.9GB, HDD라 시간이 걸립니다
  curl -L -C - -o "%MODEL%" https://huggingface.co/OnomaAIResearch/Illustrious-XL-v1.0/resolve/main/Illustrious-XL-v1.0.safetensors
)
for %%A in ("%MODEL%") do set MSIZE=%%~zA
if not "%MSIZE%"=="6938040736" (echo [오류] 기본 모델을 다 받지 못했습니다. 다시 실행하면 이어 받습니다. & pause & exit /b 1)

rem 6) 이펙트 LoRA 1차(2·4·6바퀴) - Kaggle 1차 결과 zip(공유 링크)에서 out 폴더만
if not exist %ROOT%\ComfyUI\models\loras\nkmr_fx_ilxl.safetensors (
  echo [6/7] 이펙트 LoRA 1차 받는 중... 약 520MB
  curl -L -C - -o %ROOT%\dl\lora_v1.zip "https://drive.usercontent.google.com/download?id=1mWFaG9QN8Bk0U1CDZRfg_0NSDDeoI290&export=download&confirm=t"
  tar -xf %ROOT%\dl\lora_v1.zip -C %ROOT%\dl out
  copy /y %ROOT%\dl\out\*.safetensors %ROOT%\ComfyUI\models\loras\ >nul
)
if not exist %ROOT%\ComfyUI\models\loras\nkmr_fx_ilxl.safetensors echo [주의] 이펙트 LoRA를 받지 못했습니다. 그림 생성은 기본 모델만으로 됩니다.

rem 7) 선화 추출기(ControlNet lineart sk_model.pth, 17MB)
if not exist %ROOT%\models\sk_model.pth (
  echo [7/7] 선화 추출기 받는 중...
  curl -L -o %ROOT%\models\sk_model.pth https://huggingface.co/lllyasviel/Annotators/resolve/main/sk_model.pth
)

echo.
echo 설치 끝. D:\sfa 의 school_comfy.bat 로 그림 생성 화면을 열고,
echo 그림 파일을 school_to_sfa_fx.bat(이펙트) 또는 school_to_sfa_line.bat(선화)에 끌어다 놓으면 옆에 .sfa 가 생깁니다.
pause
