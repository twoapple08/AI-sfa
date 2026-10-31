@echo off
chcp 65001 >nul
rem REDESIGN (2026-10-30): video -> SFA written directly as SFA objects (docs/VIDEO-TO-SFA-REDESIGN-2026-10-30.md).
rem RTX 5060 MAIN TRAINING. One file does everything: install -> repo -> Drive login once -> data -> train -> Drive backup every 15 min.
rem Double-click. Default 3.2 hours (fits a 4.5 hour PC slot). Other length: pc_seq_5060.bat 2.5
rem Train in several sittings with one learning-rate plan: pc_seq_5060.bat 3.2 12   (12 = whole plan in hours, only at the first start)
rem Close the window any time; the next run continues from the last save (every 10 min). Drive folder seq/s1.
set HOURS=3.2
set PLAN=0
if not "%1"=="" set HOURS=%1
if not "%2"=="" set PLAN=%2
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

echo [6/6] data -> train %HOURS% hours (Drive backup every 15 min; safe to leave the seat)
%PY% -u %V%\repo\tools\pc_seq_run.py --root %V% --hours %HOURS% --plan-hours %PLAN% --rclone "%RC%" --run s1 || (echo. & echo FAILED - read the lines above and send a photo of this window & pause & exit /b 1)
echo.
echo DONE. Results: Drive folder seq/s1 and Desktop\seq_s1.zip
pause
