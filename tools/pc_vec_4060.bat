@echo off
chcp 65001 >nul
rem PC RTX 4060: video -> SFA deep learning (2026-10-29). One file does everything.
rem Install (Python 3.11, torch cu128, skia, opencv, ffmpeg, rclone) -> repo (SFA files + tools) -> Drive login once (browser)
rem -> data (1080/720/480/360) -> short test -> train (default 1.2 hours) with Drive backup every 15 min -> resumes next time.
rem RTX 4060 (8GB, RAM 32GB) version of pc_vec_5060.bat - same settings, separate run name so both PCs can train at the same time.
rem Double-click. Default 8 hours of ACTIVE training (no PC time limit; time paused for games is not counted). Other length: pc_vec_4060.bat 12
rem YIELD MODE: Call of Duty running -> training pauses; League of Legends / Clip Studio running -> training slows. Low CPU priority, about half of GPU memory.
rem You can close this window any time; the next run continues from the last save (every 200 steps).
rem 2nd run, retry b (2026-10-30: first try pc2_4060 collapsed - val 9.6 -> 27-34 in 400 steps, lr warmup added): Drive folder vec/pc2b_4060, starts from 1st run best.pt (vec/pc). Paint synthesis in data. bf16 (Ada GPU).
set HOURS=8
set CHECK=
set INIT=--init-from pc
if not "%1"=="" set HOURS=%1
rem pc_vec_5060.bat 3.2 scratch  = start from zero (without the 1st run model)
if "%2"=="scratch" set INIT=--init-from ""
rem W drive (user 10-29: C has 3GB free, W 200GB). Everything incl. pip/temp/torch caches goes to W.
if "%AISFA_DRIVE%"=="" set AISFA_DRIVE=W:
set ROOT=%AISFA_DRIVE%\aisfa
if not exist %ROOT% mkdir %ROOT%
if not exist %ROOT%\tmp mkdir %ROOT%\tmp
set TEMP=%ROOT%\tmp
set TMP=%ROOT%\tmp
set PIP_CACHE_DIR=%ROOT%\pipcache
set TORCH_HOME=%ROOT%\torchhome
set AISFA_ZIP_DIR=%ROOT%
set V=%ROOT%\vec
set PY=%ROOT%\py\python.exe
set BR=ccr-bccf15a6-d6ee46
if not exist %V% mkdir %V%
cd /d %ROOT% || (echo Drive %AISFA_DRIVE% not found & pause & exit /b 1)

echo [1/6] Python 3.11
if not exist %PY% (
  curl -L -o py311.exe https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe
  py311.exe /quiet InstallAllUsers=0 TargetDir=%ROOT%\py PrependPath=0 Include_test=0 Include_launcher=0 Shortcuts=0 AssociateFiles=0
)
%PY% --version || (echo Python install failed & pause & exit /b 1)

echo [2/6] PyTorch + libraries (RTX 50xx: cu128 / GTX 10xx: cu126 - cu128 builds dropped Pascal)
set CU=cu128
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

echo [6/6] data -> short test -> train %HOURS% hours (Drive backup every 15 min; safe to leave the seat)
%PY% -u %V%\repo\tools\pc_vec_run.py --root %V% --hours %HOURS% --rclone "%RC%" --run pc2b_4060 --yield %INIT% %CHECK% || (echo. & echo FAILED - read the lines above and send a photo of this window & pause & exit /b 1)
echo.
echo DONE. Results: Drive folder vec/pc2b_4060 and %ROOT%\vec_out.zip
pause
