@echo off
chcp 65001 >nul
rem Day 2 (2026-10-28): ProPainter person removal for the remaining Nakamura effect clips. One file does everything.
rem - If the PC was reset, installs Python 3.11 + torch cu128 + ProPainter again (same as pc_propainter.bat, about 10-15 min).
rem - Uses pc_propainter_batch2.py (models loaded once; same results as day 1, checked byte-identical on the server).
rem - Runs only clips in ppb_order_day2.txt (remaining after day 1). No accounts/tokens. Everything under C:\aisfa.
set ROOT=C:\aisfa
set PY=%ROOT%\py\python.exe
set RAW=https://raw.githubusercontent.com/twoapple08/AI-sfa/ccr-bccf15a6-d6ee46/tools
set LIMIT=200
if not "%1"=="" set LIMIT=%1
if not exist %ROOT% mkdir %ROOT%
cd /d %ROOT%

if not exist %PY% (
  echo [setup] Python 3.11
  curl -L -o py311.exe https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe
  py311.exe /quiet InstallAllUsers=0 TargetDir=%ROOT%\py PrependPath=0 Include_test=0 Include_launcher=0 Shortcuts=0 AssociateFiles=0
)
%PY% -c "import torch;assert torch.cuda.is_available()" 2>nul || (
  echo [setup] PyTorch cu128
  %PY% -m pip install -q --upgrade pip
  %PY% -m pip install -q torch torchvision --index-url https://download.pytorch.org/whl/cu128
)
%PY% -c "import torch;print('torch',torch.__version__,'cuda',torch.cuda.is_available(),torch.cuda.get_device_name(0))" || (echo torch failed & pause & exit /b 1)
if not exist %ROOT%\ProPainter-main (
  echo [setup] ProPainter code
  curl -L -o pp.zip https://github.com/sczhou/ProPainter/archive/refs/heads/main.zip
  tar -xf pp.zip
)
%PY% -c "import einops,timm,scipy,cv2,imageio" 2>nul || %PY% -m pip install -q "numpy==1.26.4" av addict einops future scipy opencv-python matplotlib scikit-image imageio-ffmpeg pyyaml requests timm yapf

if not exist %ROOT%\ppb\clips (
  echo [input] 127MB
  curl -L -o ppb.zip "https://drive.usercontent.google.com/download?id=17vhp6kuo6e8ezdC9S8Nl1PVRe9ES19mg&export=download&confirm=t"
  tar -xf ppb.zip
)
curl -L -o %ROOT%\ppb\pc_propainter_batch2.py %RAW%/pc_propainter_batch2.py
curl -L -o %ROOT%\ppb\order_day2.txt %RAW%/ppb_order_day2.txt
if not exist %ROOT%\ppb2 mkdir %ROOT%\ppb2
copy /y %ROOT%\ppb\order_day2.txt %ROOT%\ppb2\order.txt >nul
if not exist %ROOT%\ppb2\clips mklink /j %ROOT%\ppb2\clips %ROOT%\ppb\clips >nul
if not exist %ROOT%\ppb2\masks mklink /j %ROOT%\ppb2\masks %ROOT%\ppb\masks >nul

echo Running up to %LIMIT% minutes (run this bat again to continue).
%PY% %ROOT%\ppb\pc_propainter_batch2.py %ROOT%\ppb2 %ROOT%\ProPainter-main --limit %LIMIT%
echo Zipping results...
cd /d %ROOT%\ppb2
tar -a -cf %ROOT%\ppb_out2.zip out log.csv
echo DONE. Upload C:\aisfa\ppb_out2.zip to Drive (PC_ProPainter folder) and send the first lines of this window.
pause
