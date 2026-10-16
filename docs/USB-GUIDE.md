# USB에 담아 여러 PC에서 쓰기

저장소(`aisfa`)와 수집·분석 결과를 USB에 넣고 PC를 옮겨 다니며 작업하는 방법이다. 기본 설치와 명령은 [PC-SETUP-GUIDE](PC-SETUP-GUIDE.md)를 따른다.

## 무엇이 옮겨지고 무엇이 PC마다 따로인가

| 항목 | USB로 옮김 | 비고 |
|---|---|---|
| 코드·문서·git 기록(`.git`) | 예 | |
| 수집 영상·메타데이터(`data_sakuga`) | 예 | 개인 자료. 저장소에 올리지 않는다 |
| 분석 결과(`*.shots.json`, `*.pose.npz`, `*.motion.json`) | 예 | 끝난 클립은 다른 PC에서도 건너뛴다 |
| 모델 가중치(`models`) | 예 | |
| 파이썬 환경(`.venv`, PyTorch 포함 약 4.5GB) | **아니오** | 그 PC의 파이썬 경로·GPU 세대에 묶여 있다. PC마다 `%LOCALAPPDATA%\aisfa\venv`에 따로 만든다 |
| Python·Git·FFmpeg 설치, GitHub 로그인 | **아니오** | PC마다 한 번 |
| 사양 판정(`hardware_profile.json`) | 자동 | 실행할 때마다 그 PC로 다시 감지 |

## USB 준비

- USB 3.0 이상, **64GB 이상**(지금 자료 기준 약 10GB, 수집이 늘면 더). 외장 SSD면 더 좋다.
- 파일 시스템은 **exFAT 또는 NTFS**. FAT32는 파일 하나가 4GB로 제한되므로 쓰지 않는다.
- 드라이브 문자(E:, F: …)는 PC마다 달라도 된다. 모든 스크립트가 상대 경로를 쓴다.

## 처음 옮기기 (지금 PC → USB)

1. 돌고 있는 작업이 없게 한다(끝났거나 PC를 다시 켠 직후).
2. PowerShell에서(USB가 `E:`라면):

```powershell
robocopy D:\aisfa E:\aisfa /E /XD .venv __pycache__
```

`.venv`는 빼고 복사한다. 이 PC에서는 계속 `D:\aisfa\.venv`를 쓰면 된다.

## 다른 PC에서 처음 쓸 때 (한 번만)

1. 설치(관리자 권한 불필요):

```powershell
winget install -e --id Python.Python.3.12
winget install -e --id Git.Git
winget install -e --id Gyan.FFmpeg
```

2. 터미널을 새로 열고 USB의 저장소로 이동한다: `cd E:\aisfa`
3. git이 "dubious ownership"으로 거부하면 한 번만: `git config --global --add safe.directory E:/aisfa`
4. 이어하기를 실행한다. 이 PC용 환경이 없으면 GPU에 맞는 PyTorch를 먼저 설치한다(약 2.6GB, 10–20분).

```powershell
powershell -ExecutionPolicy Bypass -File tools\stage2_resume.ps1
```

## 매번 쓸 때

```powershell
cd E:\aisfa
git pull
powershell -ExecutionPolicy Bypass -File tools\stage2_resume.ps1
```

- 끝난 클립은 건너뛰고 남은 것만 처리한다. 도중에 꺼도 다음에 같은 명령으로 이어진다.
- 처리 속도와 모델 크기는 그 PC의 GPU에 맞춰 자동으로 정해진다(예: 1050 Ti는 small, RTX 4080은 large).
- 코드를 고쳐 커밋했다면 `git push`(PC마다 처음 한 번 브라우저로 GitHub 로그인).

## USB를 뺄 때

- 작업이 끝났거나 멈춘 뒤, 작업 표시줄의 **하드웨어 안전하게 제거**를 누르고 뺀다.
- 결과 파일은 다 쓴 뒤 이름을 바꾸므로 작업 중 뽑혀도 반쯤 쓴 결과는 남지 않는다. 다만 쓰기 캐시 때문에 다른 파일이 손상될 수 있으니 안전 제거를 지킨다.

## 원본은 한 곳만

- USB를 원본으로 정했으면 그 뒤로는 USB에서만 작업한다. D:와 USB 양쪽에서 따로 작업하면 결과가 갈라진다.
- D:로 다시 합치려면(USB가 최신일 때):

```powershell
robocopy E:\aisfa D:\aisfa /E /XO /XD .venv __pycache__
```

`/XO`는 D:에 더 새 파일이 있으면 덮어쓰지 않는다.

## 문제가 생기면

- `python`이 없다고 나오면: 설치 후 터미널을 새로 열었는지 확인한다.
- 환경 설치 끝에 "GPU 검증 실패"가 나오면: NVIDIA 드라이버를 최신으로 올리고 `python -m pipeline.setup_env`를 다시 실행한다. RTX 50 계열은 드라이버의 CUDA 12.8 이상이 필요하다.
- 이 PC의 환경 위치 확인: `python -m pipeline.setup_env --where`
