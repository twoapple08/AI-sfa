# AI-sfa 학교 PC(Windows, GTX 1050 Ti) 설정과 3D 올리기 학습. 관리자 권한·설치 없이 사용자 폴더에만 받는다.
# 재부팅하면 초기화되는 PC 기준. 작업이 끝나면 꼭 재부팅해서 Drive 인증값을 지운다.
# 실행: PowerShell 창에 아래 한 줄
#   irm https://raw.githubusercontent.com/twoapple08/AI-sfa/ccr-bccf15a6-d6ee46/tools/pc_setup.ps1 | iex
# 인증값 넣는 방법(둘 중 하나):
#   가) 메모장에 값만 붙여 넣어 %USERPROFILE%\aisfa\key.txt 로 저장(스크립트가 읽고 바로 지운다)
#   나) 4/6 단계 입력란에 붙여 넣기
$ProgressPreference = "SilentlyContinue"
$BR = "https://raw.githubusercontent.com/twoapple08/AI-sfa/ccr-bccf15a6-d6ee46"
$W = "$env:USERPROFILE\aisfa"
New-Item -ItemType Directory -Force $W | Out-Null
Set-Location $W
Start-Transcript -Path "$W\setup.log" -Append | Out-Null

function Step([string]$msg, [scriptblock]$body) {
  Write-Host ""
  Write-Host "== $msg" -ForegroundColor Cyan
  try { & $body } catch {
    Write-Host "오류: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "이 화면(빨간 줄)을 Claude에게 보내 주세요. 기록: $W\setup.log"
    Stop-Transcript | Out-Null
    Read-Host "Enter를 누르면 닫힙니다"
    throw
  }
}

Step "1/6 uv(파이썬 관리 도구)" {
  if (-not (Test-Path "$W\uv\uv.exe")) {
    Invoke-WebRequest https://github.com/astral-sh/uv/releases/latest/download/uv-x86_64-pc-windows-msvc.zip -OutFile uv.zip
    Expand-Archive uv.zip -DestinationPath uv -Force
  } else { Write-Host "있음, 건너뜀" }
}
$uv = "$W\uv\uv.exe"
$py = "$W\venv\Scripts\python.exe"

Step "2/6 파이썬 3.11 + PyTorch(CUDA 11.8)" {
  if (-not (Test-Path $py)) { & $uv venv --python 3.11 venv }
  & $py -c "import torch" 2>$null
  if ($LASTEXITCODE -ne 0) {
    & $uv pip install --python $py torch==2.4.1 --index-url https://download.pytorch.org/whl/cu118
    & $uv pip install --python $py numpy
  } else { Write-Host "있음, 건너뜀" }
  & $py -c "import torch; print('GPU:', torch.cuda.is_available() and torch.cuda.get_device_name(0))"
}

Step "3/6 rclone" {
  if (-not (Test-Path "$W\rc")) {
    Invoke-WebRequest https://downloads.rclone.org/rclone-current-windows-amd64.zip -OutFile rc.zip
    Expand-Archive rc.zip -DestinationPath rc -Force
  } else { Write-Host "있음, 건너뜀" }
}
$rcdir = Split-Path (Get-ChildItem "$W\rc" -Recurse -Filter rclone.exe | Select-Object -First 1).FullName
$env:PATH = "$rcdir;$env:PATH"

Step "4/6 Drive 인증" {
  $conf = "$env:APPDATA\rclone\rclone.conf"
  if (Test-Path $conf) { Write-Host "이미 설정됨, 건너뜀" } else {
    $keyFile = "$W\key.txt"
    if (Test-Path $keyFile) {
      $b64 = (Get-Content $keyFile -Raw).Trim()
      Remove-Item $keyFile -Force
      Write-Host "key.txt에서 읽고 지움"
    } else {
      Write-Host "인증값을 붙여 넣고 Enter (마우스 오른쪽 클릭 = 붙여 넣기). 입력 후 화면을 지운다."
      Stop-Transcript | Out-Null  # 입력값이 기록 파일에 남지 않도록 입력 동안 기록을 멈춘다
      $b64 = (Read-Host "값").Trim()
      Clear-Host
      Start-Transcript -Path "$W\setup.log" -Append | Out-Null
    }
    Write-Host "읽은 길이: $($b64.Length) (정상은 약 720)"
    if ($b64.Length -lt 200) { throw "값이 너무 짧다. 전체를 복사했는지 확인" }
    # 파이썬 도우미를 파일로 써서 실행(인용부호·줄바꿈 문제 피함). 값은 환경 변수로만 넘기고 바로 지운다.
    @'
import base64, json, os, pathlib
raw = os.environ["AISFA_B64"].strip()
d = json.loads(base64.b64decode(raw + "=" * (-len(raw) % 4)))
p = pathlib.Path(os.environ["APPDATA"]) / "rclone"
p.mkdir(parents=True, exist_ok=True)
lines = ["[gdrive]", "type = drive", "scope = drive.readonly,drive.file"]
for k in ("client_id", "client_secret"):
    if d.get(k):
        lines.append(f"{k} = {d[k]}")
lines.append("token = " + d["token"])
(p / "rclone.conf").write_text("\n".join(lines) + "\n")
print("rclone 설정 완료")
'@ | Set-Content -Encoding UTF8 "$W\mkconf.py"
    $env:AISFA_B64 = $b64
    & $py "$W\mkconf.py"
    Remove-Item Env:AISFA_B64; Remove-Item "$W\mkconf.py"; $b64 = $null
    if ($LASTEXITCODE -ne 0) { throw "인증값 해석 실패(값이 잘렸거나 다른 값)" }
  }
  rclone lsd gdrive:AI-sfa | Select-Object -First 3
  if ($LASTEXITCODE -ne 0) { throw "Drive 연결 실패" }
}

Step "5/6 학습 자료(통합 모캡 약 630MB)·코드·이전 중간 저장본" {
  New-Item -ItemType Directory -Force mocap, out | Out-Null
  rclone copy "gdrive:AI-sfa/02_분석자료/모캡_통합" mocap -P
  rclone copy "gdrive:AI-sfa/02_분석자료/모델_3D올리기" out
  Invoke-WebRequest "$BR/tools/lift_train.py" -OutFile lift_train.py
}

Step "6/6 학습(창을 닫지 말 것. 5000단계마다 Drive에 저장, 다시 실행하면 이어서)" {
  $idx = (Get-ChildItem mocap -Filter *.csv | Select-Object -First 1).FullName
  & $py lift_train.py mocap out --index $idx --batch 128 --sync "gdrive:AI-sfa/02_분석자료/모델_3D올리기"
  rclone copy out\lifter.pt "gdrive:AI-sfa/02_분석자료/모델_3D올리기"
}
Write-Host "끝. 재부팅해서 인증값을 지울 것."
Stop-Transcript | Out-Null
Read-Host "Enter를 누르면 닫힙니다"
