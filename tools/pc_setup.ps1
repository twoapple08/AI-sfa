# AI-sfa 학교 PC(Windows, GTX 1050 Ti) 설정과 3D 올리기 학습. 관리자 권한·설치 없이 사용자 폴더에만 받는다.
# 재부팅하면 초기화되는 PC 기준. 작업이 끝나면 꼭 재부팅해서 Drive 인증값을 지운다.
# 실행: PowerShell 창에 아래 한 줄
#   irm https://raw.githubusercontent.com/twoapple08/AI-sfa/ccr-bccf15a6-d6ee46/tools/pc_setup.ps1 | iex
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
$BR = "https://raw.githubusercontent.com/twoapple08/AI-sfa/ccr-bccf15a6-d6ee46"
$W = "$env:USERPROFILE\aisfa"
New-Item -ItemType Directory -Force $W | Out-Null
Set-Location $W

Write-Host "1/6 uv(파이썬 관리 도구) 받기"
if (-not (Test-Path "$W\uv\uv.exe")) {
  Invoke-WebRequest https://github.com/astral-sh/uv/releases/latest/download/uv-x86_64-pc-windows-msvc.zip -OutFile uv.zip
  Expand-Archive uv.zip -DestinationPath uv -Force
}
$uv = "$W\uv\uv.exe"

Write-Host "2/6 파이썬 3.11 + PyTorch(CUDA 11.8, 1050 Ti 지원) 받기 — 몇 분 걸린다"
if (-not (Test-Path "$W\venv\Scripts\python.exe")) { & $uv venv --python 3.11 venv }
$py = "$W\venv\Scripts\python.exe"
& $uv pip install --python $py torch==2.4.1 --index-url https://download.pytorch.org/whl/cu118
& $uv pip install --python $py numpy
& $py -c "import torch; print('GPU:', torch.cuda.is_available() and torch.cuda.get_device_name(0))"

Write-Host "3/6 rclone 받기"
if (-not (Test-Path "$W\rc")) {
  Invoke-WebRequest https://downloads.rclone.org/rclone-current-windows-amd64.zip -OutFile rc.zip
  Expand-Archive rc.zip -DestinationPath rc -Force
}
$rcdir = Split-Path (Get-ChildItem "$W\rc" -Recurse -Filter rclone.exe | Select-Object -First 1).FullName
$env:PATH = "$rcdir;$env:PATH"

Write-Host "4/6 Drive 인증: RCLONE_GDRIVE_AUTH_B64 값을 붙여 넣고 Enter (화면에 보이지 않는다)"
$sec = Read-Host -AsSecureString "값"
$b64 = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($sec))
$env:AISFA_B64 = $b64
& $py -c @"
import base64, json, os, pathlib
raw = os.environ['AISFA_B64'].strip()
d = json.loads(base64.b64decode(raw + '=' * (-len(raw) % 4)))
p = pathlib.Path(os.environ['APPDATA']) / 'rclone'
p.mkdir(parents=True, exist_ok=True)
lines = ['[gdrive]', 'type = drive', 'scope = drive.readonly,drive.file']
for k in ('client_id', 'client_secret'):
    if d.get(k): lines.append(f'{k} = {d[k]}')
lines.append('token = ' + d['token'])
(p / 'rclone.conf').write_text('\n'.join(lines) + '\n')
print('rclone 설정 완료')
"@
Remove-Item Env:AISFA_B64
$b64 = $null
rclone lsd gdrive:AI-sfa | Select-Object -First 3

Write-Host "5/6 학습 자료(통합 모캡 약 630MB)·코드·이전 중간 저장본 받기"
New-Item -ItemType Directory -Force mocap, out | Out-Null
rclone copy "gdrive:AI-sfa/02_분석자료/모캡_통합" mocap -P
rclone copy "gdrive:AI-sfa/02_분석자료/모델_3D올리기" out
Invoke-WebRequest "$BR/tools/lift_train.py" -OutFile lift_train.py

Write-Host "6/6 학습 시작(창을 닫지 말 것). 5000단계마다 Drive '02_분석자료/모델_3D올리기'에 저장. 멈춰도 다시 실행하면 이어서 한다."
$idx = (Get-ChildItem mocap -Filter *.csv | Select-Object -First 1).FullName
& $py lift_train.py mocap out --index $idx --batch 128 --sync "gdrive:AI-sfa/02_분석자료/모델_3D올리기"
rclone copy out\lifter.pt "gdrive:AI-sfa/02_분석자료/모델_3D올리기"
Write-Host "끝. 재부팅해서 인증값을 지울 것."
