# 2단계 이어하기: PC를 껐다 켠 뒤 저장소 폴더에서 실행한다.
#   powershell -ExecutionPolicy Bypass -File tools\stage2_resume.ps1
# 모든 단계가 이미 끝난 클립은 건너뛰므로 몇 번 다시 실행해도 된다.
# 받는 중이던 영상(.part)은 처음부터 다시 받고, 분석 중이던 클립 1개는 다시 분석한다.
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
$env:Path = [Environment]::GetEnvironmentVariable('Path','Machine') + ';' + [Environment]::GetEnvironmentVariable('Path','User')
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONUNBUFFERED = '1'
$py = '.venv\Scripts\python.exe'
# 학습 대상 기준(사용자 결정 2026-10-16): 액션씬, 점수 상위 30%, 서양 카툰·옛날 애니 자동 제외
$match = '~fighting ~impact_frames -cgi -mecha -creatures rating:s'
$minScore = 158
& $py -m pipeline.collect_sakuga media data_sakuga --max 800 --min-score $minScore --match $match
& $py -m pipeline.collect_sakuga curate data_sakuga --min-score $minScore --match $match
& $py -m pipeline.shots data_sakuga
& $py -m pipeline.pose data_sakuga
& $py -m pipeline.motion data_sakuga
Write-Output '2단계 이어하기 완료'
