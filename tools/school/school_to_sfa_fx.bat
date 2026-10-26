@echo off
setlocal
rem 이펙트 그림 -> SFA(층층이 쌓기: 배경색 / 배경 묘사 / 밝은 선 / 폭발 어두운 층 -> 중심부). 그림 파일을 이 bat에 끌어다 놓는다.
rem 결과: 같은 폴더에 <이름>_fx.sfa 와 비교 그림 <이름>_fx_check.jpg
call "%~dp0school_env.bat"
if "%~1"=="" (echo 그림 파일을 이 bat 위로 끌어다 놓아 주세요. & pause & exit /b 1)
:next
if "%~1"=="" goto done
echo %~nx1 변환 중...
D:\sfa\env\Scripts\python.exe D:\sfa\aisfa\tools\stack_layers_sfa.py "%~1" "%~dpn1_fx.sfa" --check "%~dpn1_fx_check.jpg"
shift
goto next
:done
pause
