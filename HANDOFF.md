# AI-sfa 현행 인수인계 — 2026-10-31

전체 역사(10-14 → 10-31, 방향 전환·재설계 때 빠진 항목): docs/PROJECT-HISTORY-2026-10-31.md. 이전: docs/history/HANDOFF-2026-10-29-night.md(픽셀 지도 방식 1·2차 학습 시기). 새 대화 시작 문구: docs/HANDOFF-PROMPT.md.

## 현재 우선순위
**영상 → SFA 변환 AI(재설계판) — GPU 본 학습 직전.**
- 모델이 영상 한 장을 보고 SFA 오브젝트 문장(토큰열)을 직접 써서 .sfa를 만든다.
- 주 목적은 스틱맨 동작(사용자 10-28).
- 전체 해설(일반인용): docs/EXPLAINER-VIDEO-TO-SFA-2026-10-31.md
- 설계: docs/VIDEO-TO-SFA-REDESIGN-2026-10-30.md
- GPT 검토 전후: docs/GPT-REVIEW-IMPACT-2026-10-30.md

## 사용자 결정(10-31) — 꼭 지킬 것
- **Kaggle GPU 시간은 아껴 둔다.** 남은 확인이 다 끝난 뒤에 풀로 돌린다. 주간 30시간 중 약 0.5시간 사용(10-31 09:02 KST 초기화). **사용자 지시 없이 Kaggle GPU 실행 금지.**
- 10-31 Kaggle은 CPU 커널만 사용(GPU 0). Kaggle 자료 만들기·CPU 흐름 시험은 사용자 승인 범위.

## 10-31 추가(사용자 지시) — 1판 학습 자료·모델에 들어간 것
- **해상도 단계 1080 → 720 → 480 → 360**(사용자 10-29 지시, 재설계 때 빠졌다가 복원): 시간 20/25/25/30%, 앞 단계 30% 섞기, 단계는 되돌아가지 않음. 그림 특징은 45×80칸으로 모음, 한 묶음 그림 수 = 화소 예산(`--px-budget` 8M). 고해상도 자료는 mp4 저장(`seq_data --video`). 상세: 설계 문서 §6.2
  - 목적(사용자): 나중에 모은 애니 자료(화질이 360까지 떨어짐)도 깔끔하게 옮기는 실력
  - 측정: 그림 처리 메모리 1장 fp32 360=173MB, 1080=1,681MB. **CPU 학습 강제 종료(Kaggle CPU rc137 두 번)의 원인은 해상도가 아니라 CPU의 글자 쪽 어텐션**: 서버 측정에서 그림 1장·922단어가 디코더에서 3.7GB, 2장이면 7.8GB(단어마다 그림 칸 3,600개를 보는 교차 어텐션을 CPU는 통째로 들고 있음). GPU(T4 fp16)는 같은 설정에서 최대 4.8GB였다. → CPU 흐름 시험은 `--tok-budget 1024 --max-batch 2`. GPU는 메모리 부족 자동 복구(체크포인팅 → 화소 예산 → 토큰 한도)
- **페인트 합성**(사용자 10-29: 흰 바탕이 너무 많아 학습에 넣기로, 재설계 때 빠졌던 것): 학습 파일 30%에서 흰 바탕만 합성판 추가(`--synth 0.3`), 합성한 면도 정답에
- **굵기 배율**(사용자 10-31: 굵기도 고루 쓰게): 늘린 사본마다 ThicknessScale × 0.5–2, 정답도 같이. 자료 판 3
- **인코더 이어 쓰기**(재설계 문서 '그대로 쓰는 것'이 빠졌던 것): 이전 픽셀 지도 2차 모델 `vec/pc2/best.pt` 인코더 변환(같은 그림 출력 차 0.12%) → `--init-encoder`. Kaggle 비공개 자료 `aisfa-vec-encoder`, Drive `seq/vec_encoder.pt`. 새로 시작할 때만
- 모두 Kaggle(`push-data`/`push`)·PC(`pc_seq_*.bat`)에서 기본으로 켬. 끄기: `--no-stages`, `--no-init-encoder`
- 역사·빠진 항목 대조: docs/PROJECT-HISTORY-2026-10-31.md. 남은 계획만 있는 것: 색 바꾸기·배경색 늘리기

## 바로 할 일(순서대로, 각각 사용자 승인 뒤)
1. ~~Kaggle CPU로 전체 자료 미리 만들기~~ 완료. **판 3(단계·합성·굵기) 전체 자료를 10-31 다시 만드는 중** — 끝나면 data_info.json(장 수·크기·시간) 확인
   - 판 2 기록: 360 자료 8.8분, sd 31,578장·1,482MB, 실패 0. 고해상도 추가 추정 약 22분·약 0.5GB
   - 흐름 시험(판 2·3): 미리 만든 자료 6개 `--check` 맞음, 인코더 이어 쓰기 적용, 1080 → 720 → 480 단계 전환 확인(두 번 다 480 구간에서 큰 묶음이 걸려 CPU 메모리로 종료 — 위 원인). 작은 묶음 CPU 시험 10-31 진행 중
   - GPU 본 학습 시작(사용자 지시 뒤): `python tools/kaggle_seq_remote.py push --prebuilt`
2. **사용자 PC(4060 또는 5060)로 4~6시간 학습**
   - 먼저 `pc_seq_1050ti_quick.bat`류 빠른 시험: 첫 4분이 1080 단계라 가장 무거운 단계의 속도·GPU 메모리를 잰다
   - 확인할 것: 단계별 메모리(특히 1080·480), **위치를 배우는지**(위치 시험 `shift_coord_err` 감소, `shift_recall` > 0)
   - 실행: `pc_seq_4060.bat 6 0 [noyield]` 또는 `pc_seq_5060.bat 6` — 계획 0 = 이번 실행 시간이라 6시간 안에 네 단계를 다 거친다
   - PC 자료 만들기 시간 늘어남(고해상도 3벌 + 합성): PC CPU로 추가 수십 분 추정(미측정)
   - 끝나면 Claude: `kaggle_seq_remote.py from-drive s1_4060 폴더` → `seq_train.py draw` 그림 + log의 gen_/shift_ 곡선 보고
3. **판단**
   - 위치를 따라가면: Kaggle 풀(11.5시간 × 2~3회, PC 학습 상태를 `save-ckpt`로 이어받기). 단계는 되돌아가지 않으므로 PC에서 360 단계까지 끝났으면 Kaggle은 360(+480 30%)으로 계속
   - 정체하면: sin 비교(`--sine`, **새 출력 폴더에서 처음부터**)를 PC에서
4. 나중에: 세로 영상 90° 돌리기, 장 사이 추적(KEEP, 2단계), 정답 없는 영상 오브젝트 대입 채점(3단계), 긴 장(>2,048) 지원(측정: docs/TOKEN-LENGTH-2026-10-31.md — 4,096이면 학습 97.4%·시험 87.9%, 반복 좌표 15.7%; 2,048로 학습한 뒤 위치 칸을 늘려 긴 장으로 추가 학습하는 방식 가능 — 1판 결과 뒤 결정), 색·배경색 늘리기, 레이어 전체 투명도(파일 받으면).

## 지금까지 확인된 것(검증 범위 표시)
- **정답지**(`sfa_tokens.py`)[서버]
  - 학습 22,371장 왕복: 연결·면 100% 복원, 렌더 차 최대 0.70%(파일 비율로 잼)
  - 문법 위반 0. 점 삭제로 점이 모자란 오브젝트도 보존(tlqkf 154–156 곡선 1점 — 앱 표시 미확인)
- **채점기**(`sfa_objscore.py`)[단위 시험]
  - 맞는 짝 수 우선 헝가리안, 실제 그리는 순서, 원은 화면 화소 기준
  - 면은 조각·T·윤곽까지 비교, WHOLE은 점 방향 무관
  - 가림 순서는 겹치고 겉모습(선 색·글로우·딸린 면 색)이 다른 쌍만 셈
  - perfect = 모든 점 같은 칸, near_perfect는 별도. **관절 연결은 만점에서 뺌**(사용자 10-31, 24,24라 영상에 안 보임) — 연결 F1은 참고 점수
- **학습기**(`seq_train.py`)[서버 CPU·Kaggle T4]
  - 구조: ResNet34 1/8 특징 80×45, 디코더 8층 폭 512, 5,160만 변수
  - 장치: 문법 강제, KV 캐시, 토큰 한도 묶음, 메모리 부족 3단계 복구(GradScaler 단계별)
  - 이어하기: 시간 기준 학습률, 다른 GPU 사이 이어하기
  - 검증: 토큰 가중 검증, 1시간마다 생성 채점 2종(gen_ 시험 파일, shift_ 위치 시험 +6,+4,×1.05)
- **Kaggle**[실측]
  - CPU 흐름(자료 → 학습 → 결과 → 자료 올리기 → 이어하기 491→716걸음) 통과
  - **GPU 짧은 시험**(10-31, T4, 실제 크기 모델 30분): 2,403걸음, 최대 4.8GB(짧은 장 위주), 오류·메모리 부족 0, 생성 채점·저장 정상
  - **620MB 학습 상태 올리기** 106초, 바이트 일치
- **Drive 다리**[서버]: Kaggle ↔ PC 학습 상태 왕복·이어하기 확인. rclone 공용 client_id 2026 중 종료 예정 경고(지금은 작동).
- **진단 실험**[서버 CPU, 결론 정정 포함]
  - 늘리기 없이 44장 외운 모델: 원래 위치 31% ↔ 6% 옮기면 0% → 외운 자세(GPT 반론이 맞음)
  - 늘리기 8벌 모델(25분): 학습에 없던 이동에서 좌표 오차 영상 13.2% / 다른 영상 19.7% / 흰 화면 17.5%(영상 약하게 사용), 생성 맞힘 0
  - sin 비교는 무효(걸음 수 절반) → 판단 보류
- **GPT 토론 3라운드 완료**
  - 지적 25개 반영. GPT 추가 검사 42개는 당시 코드에서 재현 61/61, 지금 코드에서 결함 37개 고쳐짐 확인. 회귀 시험 9개 이식.
  - 3차 판정: 본 학습 전 필수 없음(평가 필수 3개는 반영함)
- **단위 시험 75개 통과**(10-31, `python -m unittest discover -s tests`)

## Kaggle·실행 도구 요약
- `tools/kaggle_seq_remote.py`
  - `push [--smoke] [--cpu] [--minutes 690] [--ckpt 이름] [--extra "seq_train 옵션"]`
  - `push-data [--smoke]`: 자료만 만드는 CPU 커널 `aisfa-seq-data(-smoke)`(GPU 시간 0). 출력 sd·sv·ss + `data_info.json`(커밋·자료 코드 해시·장 수·분)
  - `push --prebuilt`: 그 출력을 입력으로 붙여 자료 만들기 없이 학습. 작업자가 `seq_data --check`로 판·설정·파일 수를, 해시로 자료 코드(seq_data·sfa_render·sfa_tokens·vec_data)를 확인하고 다르면 GPU 학습 전에 멈춘다(`--prebuilt-any-code`로만 무시). `--prebuilt` 없이 GPU push하면 경고
  - `status` / `wait` / `pull 폴더` / `save-ckpt 폴더 [--ckpt 이름]` / `to-drive 폴더 학습이름` / `from-drive 학습이름 폴더` (자료 커널은 status·wait·pull에 `--data`)
  - 비공개 커널 `aisfa-seq-train`(본), `aisfa-seq-train-smoke`(시험)
  - 이어하기 자료 `aisfa-seq-ckpt`(본, 아직 없음), `aisfa-seq-ckpt-smoke`(시험)
- 인증: 환경 비밀값 `KAGGLE_USERNAME`·`KAGGLE_API_TOKEN`(등록됨, 출력 금지). kaggle CLI 2.2.5는 필요하면 `pip install kaggle`로 설치.
- PC: `tools/pc_seq_1050ti_quick.bat`, `pc_seq_5060.bat [시간] [계획]`, `pc_seq_4060.bat [시간] [계획] [noyield]`(W 드라이브)
  - Drive `AI-sfa/02_분석자료/seq/<s1|s1_4060>`
  - 끝나면 사용자가 rclone 접근 해제

## 확인된 사실(SFA·앱) — 파일 만들 때 규칙
- 앱은 불러올 때 DrawOrder를 읽지 않음. AO ID 하나 = 파일 전체 공통 오브젝트, 레이어도 ID마다 하나. 장마다 '최대+1' ID 금지(docs/FORMAT.md 끝).
- 면을 아래·위에 깔려면 레이어로 분리.
- 파란점: 이어진 묶음마다 Flags 3 하나, 꼭짓점마다 표시 하나, 파란점 자리 다른 끝점은 8.
- 렌더러 ≈ 앱(0.3%). 앱은 파일 비율로 영상을 내보냄(0.45 → 1920×864). 좌표는 화면 %.
- 사용자는 24,24로 만든다(트위닝 없음) → 장 사이 ID 이어짐은 채점에서 무시.

## 막힌 것
- 서버 GPU 없음(CPU 4개, RAM 15GB). 사용자 GPU: 1050 Ti 상시, 5060 가끔, 4060 PC(i5 14세대, RAM 32GB).
- Kaggle GPU는 사용자 결정으로 보류 중(위).

## 환경
- 저장소 `/home/user/AI-sfa`, 주 브랜치 `ccr-bccf15a6-d6ee46`(10-31 세션은 이 브랜치에만 푸시).
- 10-31 GPU 30분 시험 모델은 Kaggle 자료 `aisfa-seq-ckpt-smoke`에 남아 있다(54장 흐름 시험용 — 실력 판단 불가). 서버 scratch는 새 컨테이너면 없다.
- 새 컨테이너 준비(10-31 실측): `pip install opencv-python-headless numpy skia-python scipy scikit-image kaggle` + CPU torch(`--index-url https://download.pytorch.org/whl/cpu`), `apt-get install libegl1 libgl1`(skia), rclone은 downloads.rclone.org v1.75.2 zip → /usr/local/bin(환경 변수 `RCLONE_CONFIG_GDRIVE_*`로 바로 연결).
- 학습 자료는 Kaggle `push-data`로 만든다(CPU, 판 2는 8.8분). 서버에서 직접: `python tools/seq_data.py 폴더 --maxlen 2048 --max-frames 300 --aug 1 --synth 0.3`(+ 고해상도는 `--W 1920|1280|854 --video`).

## 보호
- 원본 영상·추출 프레임·나카무라 자료·가중치는 저장소에 넣지 않는다(Drive·Kaggle 비공개·scratch만).
- 사용자 수집 `.sfa`는 `data/user_sfa/`(공개, 10-28 결정).
- 토큰·키 출력 금지. 3D 금지. 사용자에게는 한국어로만. 트레이싱 장면은 참고용(학습 자료 아님).
