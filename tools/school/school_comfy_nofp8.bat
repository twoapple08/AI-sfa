@echo off
setlocal
rem fp8 보관으로 그림이 깨질 때 쓰는 판(저용량 모드만). 램을 더 쓰고 느리다.
call "%~dp0school_env.bat"
cd /d D:\sfa\ComfyUI || (echo [오류] 먼저 school_setup.bat 을 실행해 주세요. & pause & exit /b 1)
start "" http://127.0.0.1:8188
D:\sfa\env\Scripts\python.exe main.py --lowvram --preview-method auto
pause
