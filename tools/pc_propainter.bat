@echo off
chcp 65001 >nul
rem ProPainter (video inpainting) on PC-bang RTX 5060 - setup + run. 2026-10-27
rem No accounts/tokens. Everything under C:\aisfa. Delete the folder when done.
set ROOT=C:\aisfa
set PY=%ROOT%\py\python.exe
if not exist %ROOT% mkdir %ROOT%
cd /d %ROOT%

echo [1/5] Python 3.11 (local, no admin)
if not exist %PY% (
  curl -L -o py311.exe https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe
  py311.exe /quiet InstallAllUsers=0 TargetDir=%ROOT%\py PrependPath=0 Include_test=0 Include_launcher=0 Shortcuts=0 AssociateFiles=0
)
%PY% --version || (echo Python install failed & pause & exit /b 1)

echo [2/5] PyTorch for RTX 5060 (CUDA 12.8)
%PY% -m pip install -q --upgrade pip
%PY% -m pip install -q torch torchvision --index-url https://download.pytorch.org/whl/cu128
%PY% -c "import torch;print('torch',torch.__version__,'cuda',torch.cuda.is_available(),torch.cuda.get_device_name(0))" || (echo torch failed & pause & exit /b 1)

echo [3/5] ProPainter code + packages
if not exist %ROOT%\ProPainter-main (
  curl -L -o pp.zip https://github.com/sczhou/ProPainter/archive/refs/heads/main.zip
  tar -xf pp.zip
)
%PY% -m pip install -q "numpy==1.26.4" av addict einops future scipy opencv-python matplotlib scikit-image imageio-ffmpeg pyyaml requests timm yapf

echo [4/5] Input (frames + masks) from Drive
if not exist %ROOT%\pp_input.zip curl -L -o pp_input.zip "https://drive.usercontent.google.com/download?id=1N8Tc-14BvcWDggr30up6dsG-qu4W5RIc&export=download&confirm=t"
tar -xf pp_input.zip

echo [5/5] Run (weights download automatically the first time)
cd /d %ROOT%\ProPainter-main
powershell -command "$t=Get-Date; & '%PY%' inference_propainter.py -i %ROOT%\firewall\frames -m %ROOT%\firewall\masks -o %ROOT%\results --height 480 --width 848 --fp16 --save_frames; Write-Host ('elapsed sec:',((Get-Date)-$t).TotalSeconds)"
cd /d %ROOT%
tar -a -cf pp_result.zip results
echo.
echo DONE. Upload C:\aisfa\pp_result.zip to Drive and send the link.
echo Also tell: the 'elapsed sec' line above, and any error text.
pause
