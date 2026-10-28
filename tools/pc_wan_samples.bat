@echo off
chcp 65001 >nul
rem 학습 없이, C:\aisfa\wan\out 의 마지막 LoRA로 'LoRA 있음' 비교 영상 4개만 다시 만든다(약 10–15분). 2026-10-28
rem 첫 실행에서 LoRA 키 이름이 모델과 안 맞아 LoRA 있음/없음 영상이 같았던 것을 고친 판. 결과: C:\aisfa\wan_out_samples.zip
set ROOT=C:\aisfa
set W=%ROOT%\wan
set PY=%ROOT%\py\python.exe
set RAW=https://raw.githubusercontent.com/twoapple08/AI-sfa/ccr-bccf15a6-d6ee46/tools
if not exist %W%\out (echo C:\aisfa\wan\out 이 없습니다. 학습 결과가 있는 PC에서 실행하세요 & pause & exit /b 1)
curl -L -o %W%\pc_wan_lora_run.py %RAW%/pc_wan_lora_run.py
%PY% %W%\pc_wan_lora_run.py %W% --samples-only
echo.
echo DONE. C:\aisfa\wan_out_samples.zip 을 Drive에 올리고 링크를 보내 주세요.
pause
