@echo off
setlocal
rem 그림 생성 화면(ComfyUI) 열기. 1050 Ti 4GB: 저용량 모드 + 그림 모델을 fp8로 보관(계산은 fp32, 이 세대는 fp16 계산이 매우 느림).
rem 브라우저에서 http://127.0.0.1:8188 이 열린다. 작업 흐름 school_workflow.json 을 화면에 끌어다 놓으면 LoRA까지 연결된 상태로 시작한다.
call "%~dp0school_env.bat"
cd /d D:\sfa\ComfyUI || (echo [오류] 먼저 school_setup.bat 을 실행해 주세요. & pause & exit /b 1)
start "" http://127.0.0.1:8188
D:\sfa\env\Scripts\python.exe main.py --lowvram --fp8_e4m3fn-unet --preview-method auto
pause
