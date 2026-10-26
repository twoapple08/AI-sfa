@echo off
setlocal
rem 선화가 있는 그림(인물 등) -> 선 객체(곡선+굵기)만의 SFA. 학습된 선화 추출기 -> 가운데 줄기 -> 긴 곡선, 굵기 0.8배.
rem 결과: 같은 폴더에 <이름>_line.sfa, 선화 지도 <이름>_linemap.png, 비교 그림 <이름>_line_check.jpg
call "%~dp0school_env.bat"
if "%~1"=="" (echo 그림 파일을 이 bat 위로 끌어다 놓아 주세요. & pause & exit /b 1)
set PY=D:\sfa\env\Scripts\python.exe
set T=D:\sfa\aisfa\tools
:next
if "%~1"=="" goto done
echo %~nx1 선화 추출 중...
"%PY%" "%T%\lineart_map.py" "%~1" "%~dpn1_linemap.png" D:\sfa\models\sk_model.pth || goto fail
echo SFA로 바꾸는 중...
"%PY%" "%T%\effect_clip_sfa.py" "%~1" 0 0 "%~dpn1_line.sfa" --fit pad --height 0 --lines-only --line-join --line-map "%~dpn1_linemap.png" --bg 255,255,255 --line-scale 0.8 --check "%~dpn1_line_check.jpg" || goto fail
shift
goto next
:fail
echo [오류] 변환 실패 - 위 화면을 찍어 보내 주세요.
:done
pause
