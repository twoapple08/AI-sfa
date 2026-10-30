@echo off
chcp 65001 >nul
rem REDESIGN (2026-10-30): video -> SFA written directly as SFA objects. GTX 1050 Ti FEW-MINUTE TEST:
rem small data + the real model size, 4 min training + 1 min resume. Measures speed and GPU memory for the main run.
rem Double-click. About 10-15 min after install (install only the first time on this PC).
set ROOT=C:\aisfa
set V=%ROOT%\seq
set PY=%ROOT%\py\python.exe
set BR=ccr-bccf15a6-d6ee46
if not exist %V% mkdir %V%
cd /d %ROOT%

echo [1/6] Python 3.11
if not exist %PY% (
  curl -L -o py311.exe https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe
  py311.exe /quiet InstallAllUsers=0 TargetDir=%ROOT%\py PrependPath=0 Include_test=0 Include_launcher=0 Shortcuts=0 AssociateFiles=0
)
%PY% --version || (echo Python install failed & pause & exit /b 1)

echo [2/6] PyTorch + libraries (RTX 50xx: cu128 / GTX 10xx: cu126 - cu128 builds dropped Pascal)
set CU=cu126
for /f "delims=" %%G in ('nvidia-smi --query-gpu^=name --format^=csv^,noheader') do set GPU=%%G
echo GPU: %GPU%
%PY% -c "import torch;(torch.zeros(1).cuda()+1).item()" 2>nul || (
  %PY% -m pip install -q --upgrade pip
  %PY% -m pip install -q --force-reinstall torch torchvision --index-url https://download.pytorch.org/whl/%CU%
)
%PY% -m pip install -q skia-python opencv-python-headless numpy
%PY% -c "import torch,skia,cv2;print('torch',torch.__version__,'cuda',torch.cuda.is_available(),torch.cuda.get_device_name(0))" || (echo torch/skia failed & pause & exit /b 1)

echo [3/6] ffmpeg
if not exist %ROOT%\ffmpeg\bin\ffmpeg.exe (
  curl -L -o ffmpeg.zip https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip
  tar -xf ffmpeg.zip -C %ROOT%
  for /d %%D in (%ROOT%\ffmpeg-master-latest-win64-gpl) do move %%D %ROOT%\ffmpeg >nul
)
set PATH=%ROOT%\ffmpeg\bin;%PATH%
ffmpeg -version >nul || (echo ffmpeg failed & pause & exit /b 1)

echo [4/6] repo (SFA files + tools, about 120MB)
if exist %V%\repo rmdir /s /q %V%\repo
curl -L -o %V%\repo.zip https://codeload.github.com/twoapple08/AI-sfa/zip/refs/heads/%BR%
tar -xf %V%\repo.zip -C %V%
move %V%\AI-sfa-%BR% %V%\repo >nul

echo [5/6] rclone + Drive login (browser opens once; allow access)
if not exist %ROOT%\rclone.exe (
  curl -L -o rclone.zip https://downloads.rclone.org/rclone-current-windows-amd64.zip
  tar -xf rclone.zip -C %ROOT%
  for /d %%D in (%ROOT%\rclone-*-windows-amd64) do copy %%D\rclone.exe %ROOT%\rclone.exe >nul
)
set RC=%ROOT%\rclone.exe
%ROOT%\rclone.exe listremotes | findstr /c:"gdrive:" >nul || %ROOT%\rclone.exe config create gdrive drive scope=drive.file >nul

echo [6/6] quick test (data -> 4 min training -> 1 min resume)
%PY% -u %V%\repo\tools\pc_seq_run.py --root %V% --rclone "%RC%" --run s1 --quick --tok-budget 4096 || (echo. & echo FAILED - send a photo of this window & pause & exit /b 1)
echo.
echo DONE. Send a photo of the lines above (steps, GPU memory).
pause
