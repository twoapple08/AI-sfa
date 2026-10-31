@echo off
chcp 65001 >nul
rem T5 글 인코더(11.4GB)를 4갈래로 나눠 동시에 받는다(허깅페이스가 연결 하나당 속도를 제한해서). 2026-10-28
rem 먼저 pc_wan_lora.bat 창을 닫고 이 파일을 실행. 끝나면 pc_wan_lora.bat 를 다시 실행(받은 것은 건너뜀).
set D=C:\aisfa\wan\models
set F=%D%\models_t5_umt5-xxl-enc-bf16.pth
set U=https://huggingface.co/Wan-AI/Wan2.1-T2V-1.3B/resolve/main/models_t5_umt5-xxl-enc-bf16.pth
if not exist %D% (echo C:\aisfa\wan\models 폴더가 없습니다 & pause & exit /b 1)
cd /d %D%
del /q t5_p*.part t5_p*.ok 2>nul
echo T5 4갈래 동시 다운로드 시작(작은 창 4개가 따로 뜹니다. 닫지 마세요)
start "t5 1" /min cmd /c "curl -L -r 0-2840480104 -o t5_p1.part %U% && echo ok> t5_p1.ok"
start "t5 2" /min cmd /c "curl -L -r 2840480105-5680960209 -o t5_p2.part %U% && echo ok> t5_p2.ok"
start "t5 3" /min cmd /c "curl -L -r 5680960210-8521440314 -o t5_p3.part %U% && echo ok> t5_p3.ok"
start "t5 4" /min cmd /c "curl -L -r 8521440315-11361920417 -o t5_p4.part %U% && echo ok> t5_p4.ok"
:wait
timeout /t 20 /nobreak >nul
dir /-c t5_p*.part | find "t5_p"
echo ----
if not exist t5_p1.ok goto wait
if not exist t5_p2.ok goto wait
if not exist t5_p3.ok goto wait
if not exist t5_p4.ok goto wait
echo 합치는 중...
copy /b t5_p1.part+t5_p2.part+t5_p3.part+t5_p4.part %F% >nul
for %%A in (%F%) do set SZ=%%~zA
if not "%SZ%"=="11361920418" (echo 크기가 맞지 않습니다: %SZ% / 11361920418. 이 화면을 찍어 보내 주세요 & pause & exit /b 1)
del /q t5_p*.part t5_p*.ok
echo 완료. 이제 pc_wan_lora.bat 를 다시 실행하세요(설치와 받은 모델은 건너뜁니다).
pause
