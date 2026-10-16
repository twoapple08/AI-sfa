# PC 준비와 첫 수집 — Windows 안내

[AI-PIPELINE-PLAN](AI-PIPELINE-PLAN-2026-10-16.md)의 0–1단계다. PC 사양은 매번 달라도 된다. 도구가 실행할 때마다 자동으로 감지한다. 수집한 영상·메타데이터는 개인용이며 저장소에 올리지 않는다(`.gitignore`로 막아 두었다).

## 1. 설치 (한 번만)

PowerShell 또는 명령 프롬프트에서:

```powershell
winget install --id Git.Git -e
winget install --id Python.Python.3.11 -e
winget install --id Gyan.FFmpeg -e
```

설치 후 **터미널을 새로 연다.** `python --version`, `git --version`, `ffmpeg -version`이 모두 나오면 성공이다. winget이 없으면 각 공식 사이트 설치 파일을 써도 된다. Python 설치 시 "Add to PATH"에 체크한다.

NVIDIA 그래픽카드가 있으면 드라이버를 최신으로 업데이트한다. GeForce Experience 또는 NVIDIA 사이트를 쓴다.

## 2. 저장소 받기

```powershell
cd D:\          # 여유 공간이 큰 드라이브(SSD 권장, 200GB 이상)
git clone https://github.com/twoapple08/AI-sfa.git
cd AI-sfa
git checkout claude/stick-fighter-ai-analysis-2knx37
```

이미 받았다면 `git pull`로 최신화한다.

## 3. 사양 확인

```powershell
python -m pipeline.hwprofile
```

GPU·VRAM·RAM·디스크와 처리 등급(cpu/low/mid/high)이 출력되고 `hardware_profile.json`이 만들어진다. 출력 내용을 대화창에 붙여 주면 된다.

## 4. 첫 수집 — 메타데이터만 (영상 없이, 수 분)

```powershell
python -m pipeline.collect_sakuga tags  data_sakuga
python -m pipeline.collect_sakuga posts data_sakuga "fighting" --max 500
python -m pipeline.collect_sakuga stats data_sakuga
```

- `tags`: 전체 태그와 종류(애니메이터/작품/일반/메타)를 받는다. 한 번만 하면 된다.
- `posts`: 검색어에 맞는 클립의 정보(태그·점수·파일 주소)를 받는다. 다시 실행하면 이어서 받는다. 검색어는 사쿠가부루 검색과 같다(예: `"punch smears"`, `"yutaka_nakamura"`).
- `stats`: 많이 나온 애니메이터·태그 순위를 보여 주고 `data_sakuga\stats.json`을 만든다. 이 출력을 붙여 주면 수집 대상과 스타일 대상 애니메이터를 함께 정한다.

## 5. 영상 받기 (대상이 정해진 뒤)

```powershell
python -m pipeline.collect_sakuga media data_sakuga --max 200
```

`data_sakuga\media\`에 `번호.mp4`와 `번호.json`(태그 종류별, 학습용 태그에서 작품명 제외)이 생긴다. `index.csv`에 목록이 쌓인다. 중간에 꺼도 다시 실행하면 받은 파일은 md5를 확인한 뒤 건너뛴다. 요청은 1.5초 간격이다(`--delay`로 조정).

받을 클립은 `--match`로 고른다. 문법은 사쿠가부루 검색과 같다(`태그`=필수, `-태그`=제외, `rating:s`=등급). 이미 받아 둔 post 목록 안에서만 거른다.

```powershell
python -m pipeline.collect_sakuga media data_sakuga --max 200 --match "fighting -cgi -mecha -creatures rating:s"
```

## 6. 2단계 환경 (한 번만, PC가 바뀌면 다시)

```powershell
python -m pipeline.setup_env            # --dry-run 이면 고를 PyTorch 빌드만 보여 준다
```

`.venv`를 만들고, 이 PC의 GPU 세대와 드라이버가 지원하는 PyTorch CUDA 빌드를 골라 설치한다. 예: GTX 1050 Ti(Pascal)는 cu126, RTX 50 계열은 드라이버 CUDA 12.8 이상이 필요하다. 끝에 GPU 검증 결과가 나오고 `.venv\aisfa_env.json`에 남는다.

## 7. 샷 분할·홀드 판별

```powershell
.venv\Scripts\python -m pipeline.shots data_sakuga
```

`western` 태그(서양 카툰)는 사용자 결정으로 받지 않는다.

받은 클립마다 `번호.shots.json`이 생긴다. 컷 경계, 같은 그림 반복(1s/2s/3s 작화), 한 장 그림에 카메라만 움직이는 샷(`camera_only`), 정지샷(`still`), 원화처럼 보이는 선화(`lineart_like`)를 기록한다. 이어서 실행하면 분석한 클립은 건너뛴다.

## 8. 관절 추출(층①)

```powershell
.venv\Scripts\python -m pipeline.pose data_sakuga
```

`animated` 샷마다 사람별 트랙(ID 유지, 컷마다 초기화)과 COCO 관절 17개를 `번호.pose.npz`에 저장한다. 모델 크기·fp16은 사양 등급을 따르고, GPU 메모리가 부족하면 입력 크기를 낮춰 다시 한다. 1050 Ti 기준 클립당 약 25초. 그림 타이밍(on 1s/2s/3s)은 관절이 움직였는지로 다시 잰다(카메라·이펙트 영향 없음). 가중치는 `models\`에 받으며 커밋하지 않는다.

## Claude Code를 PC에서 쓰는 경우

PC에 Claude Code를 설치하면, 이 저장소 폴더에서 대화하며 PC의 GPU로 명령을 직접 실행할 수 있다. 설치 방법은 공식 안내(https://code.claude.com/docs)를 따른다. 설치하지 않아도 위 명령을 직접 실행하고 결과를 붙여 주는 방식으로 진행할 수 있다.
