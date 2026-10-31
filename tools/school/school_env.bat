@echo off
rem 모든 캐시·사용자 폴더를 D:\sfa 로(C는 재부팅 때 초기화, 2026-10-26 사용자). 다른 bat이 call로 부른다.
set ROOT=D:\sfa
set TMP=%ROOT%\tmp
set TEMP=%ROOT%\tmp
set HF_HOME=%ROOT%\hf
set UV_CACHE_DIR=%ROOT%\uvcache
set UV_PYTHON_INSTALL_DIR=%ROOT%\py
set PIP_NO_CACHE_DIR=1
set USERPROFILE=%ROOT%\home
set HOME=%ROOT%\home
set APPDATA=%ROOT%\home\AppData\Roaming
set LOCALAPPDATA=%ROOT%\home\AppData\Local
set CUDA_CACHE_PATH=%ROOT%\cudacache
set TORCH_HOME=%ROOT%\torch
set XDG_CACHE_HOME=%ROOT%\home\.cache
set PYTHONUSERBASE=%ROOT%\home\pyuser
set MPLCONFIGDIR=%ROOT%\home\mpl
set HF_HUB_DISABLE_XET=1
set PYTHONUTF8=1
for %%D in (%ROOT%\tmp %ROOT%\hf %ROOT%\uvcache %ROOT%\py %ROOT%\home\AppData\Roaming %ROOT%\home\AppData\Local %ROOT%\cudacache %ROOT%\torch) do if not exist %%D mkdir %%D
