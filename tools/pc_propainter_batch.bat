@echo off
chcp 65001 >nul
rem Batch: remove characters from Nakamura effect clips with ProPainter (needs pc_propainter.bat setup done). 2026-10-27
set ROOT=C:\aisfa
set PY=%ROOT%\py\python.exe
cd /d %ROOT%
if not exist %ROOT%\ProPainter-main (echo Run pc_propainter.bat first & pause & exit /b 1)
if not exist %ROOT%\ppb\order.txt (
  echo Downloading input 127MB...
  curl -L -o ppb.zip "https://drive.usercontent.google.com/download?id=17vhp6kuo6e8ezdC9S8Nl1PVRe9ES19mg&export=download&confirm=t"
  tar -xf ppb.zip
)
curl -L -o %ROOT%\ppb\pc_propainter_batch.py "https://drive.usercontent.google.com/download?id=1vNU-r12p9cfNR_0dFD7WakiMaD-f_1Hk&export=download&confirm=t"
echo Running. It stops by itself after 160 minutes; run again later to continue.
%PY% %ROOT%\ppb\pc_propainter_batch.py %ROOT%\ppb %ROOT%\ProPainter-main --limit 160
echo Zipping results...
cd /d %ROOT%\ppb
tar -a -cf %ROOT%\ppb_out.zip out log.csv
echo DONE. Upload C:\aisfa\ppb_out.zip to Drive and send the link.
pause
