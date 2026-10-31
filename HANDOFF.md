# AI-sfa 현행 인수인계 — 2026-11-01

이전 판(10-31 낮의 상세 기록): docs/history/HANDOFF-2026-10-31-day.md
전체 역사(10-14 → 10-31): docs/PROJECT-HISTORY-2026-10-31.md
새 대화 시작 문구: docs/HANDOFF-PROMPT.md

## 현재 우선순위
**영상 → SFA 변환 AI(재설계판) 1판.** 판정 장치 구현을 마쳤다(11-01). 다음은 PC 시험 학습이다.
- 모델이 영상 한 장을 보고 SFA 오브젝트 문장(토큰열)을 빈 상태에서 직접 쓴다. 그 파일을 원본 파일과 오브젝트 단위로 채점한다.
- 주 목적은 스틱맨 동작(사용자 10-28).
- 설계: docs/VIDEO-TO-SFA-REDESIGN-2026-10-30.md(§6.2 해상도 단계). 일반인용 해설: docs/EXPLAINER-VIDEO-TO-SFA-2026-10-31.md
- **판정 기준(확정): docs/JUDGE-CRITERIA-FINAL-2026-10-31.md** — GPT와 4라운드 토론 끝에 '논증거리 없음'. 경과: docs/JUDGE-CRITERIA-DEBATE-2026-10-31.md

## 꼭 지킬 사용자 결정
- **사용자 지시 없이 Kaggle GPU 실행 금지.** GPU 시간은 남은 확인 뒤에 풀로 쓴다(주간 30시간 중 약 0.5시간 사용, 10-31 09:02 KST 초기화). Kaggle CPU 자료 만들기·CPU 흐름 시험은 승인 범위.
- 채점 원칙
  - AI 파일 대 원본 파일, 만점이면 영상도 육안상 같다.
  - 영상이 안 바뀌는 차이는 정답: ID·면 칠 순서·파란점·점 방향·**관절 연결(10-31)**·겹치지 않는 것끼리 순서.
  - 기본 점수 없음.
- 토론은 논증거리가 없어질 때까지 한다(사용자 10-31). GPT는 GitHub·Drive에 직접 접근 가능하다.

## 바로 할 일
0. **판정 장치 구현 완료(11-01)** — docs/JUDGE-IMPLEMENTATION-2026-11-01.md
   - 평가 목록 `data/judge_manifest.json`: 학습 파일 5개 중 1개 → 46장, 독립 단위 N=46, 필요 31승. 외움 기준선 공식 2방향 12.07점.
   - `tools/seq_judge.py`(목록·자료·계산), `seq_train.py --judge`(중간 2방향·마지막 4방향, 그림 시트, 단계별 업데이트 수).
   - PC 본 학습은 `--judge … --gen-minutes 20`, Kaggle은 학습 커널에서 판정 자료를 만든다(미리 만든 자료 판 3 그대로).
   - **채점기 원 수정(§4)도 완료**: 원 면 T 구간 = (시작 위상 mod 1, 부호 있는 길이)·δ 대응, 독립 WHOLE만 방향 무시, 반례 시험 10개(옛 채점기 9개 실패), 렌더 화소와 판정 일치.
   - 미구현: 첫 점·이어지는 점 구분, 묶음 변형 판정(§5), 앱 열기 확인. 동점 범위 0.5점은 Claude 제안값(첫 판정 전 확인 요청).
1. **사용자 PC 시험 학습**
   - 빠른 시험 bat부터 돌린다. 첫 4분이 1080 단계라 가장 무거운 단계의 속도·GPU 메모리를 잰다.
   - 그다음 2시간 학습: `pc_seq_4060.bat 2 0` 또는 `pc_seq_5060.bat 2`. 계획 0이면 2시간 안에 네 해상도 단계를 다 거친다.
   - 판정 시간 `judge_sec`(GPU 긴 출력 생성 속도 미측정)이 너무 길면 `--gen-minutes`를 조정한다(AISFA_SEQ_TRAIN_ARGS로 덧붙이기).
   - 판정은 판정 기준 §2대로 한다. 진행 / 1회 연장 / 원인 조사, '실패'와 '판정 자료 부족'은 구분한다.
2. **진행이면 Kaggle 본 학습**(사용자 지시 뒤): `python tools/kaggle_seq_remote.py push --prebuilt`. PC 학습 상태는 `from-drive` → `save-ckpt`로 이어받는다.
   - 회차당 새 파일 엄격 F1 상승이 2%p 미만이면 원인 조사 신호로 본다. 최대 예산에 도달하면 종료한다.
3. **서버에서 이어서 할 수 있는 일**(학습을 막지 않음): 첫 점·이어지는 점 구분, 묶음 변형 판정(§5).

**사용자 결정 대기**
1. 본 학습 최대 예산
2. 숫자 허용 범위 눈 판정 시트(한 속성만 바꾼 렌더)를 볼지
3. '연기 1'·'연기 4'가 같은 작품인지(정확 사본은 아님, 둘 다 이번 평가 목록에서는 '이동으로 잘림'으로 빠짐)
4. 판정 동점 범위 |Δ| ≤ 0.5점(Claude 제안값)으로 확정할지 — 첫 판정 전에

## 1판에 들어간 것(10-31)
- **해상도 단계 1080 → 720 → 480 → 360**(사용자 10-29 지시, 재설계 때 빠졌다 복원)
  - 시간 20/25/25/30%, 앞 단계 30% 섞기, 되돌아가지 않음.
  - 그림 특징은 45×80칸으로 모으고, 한 묶음 그림 수는 화소 예산(`--px-budget` 8M)으로 정한다.
  - 고해상도 자료는 mp4로 저장한다(`seq_data --video`).
  - 목적: 화질 나쁜 애니 자료(360까지)도 깔끔하게 옮기는 실력.
- **페인트 합성**(사용자 10-29: 흰 바탕이 너무 많아서): 학습 파일 30%에서 흰 바탕만 합성판을 추가한다(`--synth 0.3`). 합성한 면도 정답에 들어간다.
- **굵기 배율**(사용자 10-31): 늘린 사본마다 ThicknessScale × 0.5–2, 정답도 같이 바뀐다. 자료 판 3.
- **인코더 이어 쓰기**: 이전 픽셀 지도 2차 모델 `vec/pc2/best.pt`를 변환했다(같은 그림 출력 차 0.12%) → `--init-encoder`. Kaggle 비공개 자료 `aisfa-vec-encoder`, Drive `seq/vec_encoder.pt`. 새로 시작할 때만 쓴다.
- **채점기**
  - 관절 연결을 만점에서 뺐다.
  - 위치·형상 부분 점수(`*_partial`)를 추가했다.
  - 분야별 연습 점수(구조·좌표·색·굵기·글로우·연결·면, 좌표는 '몇 개마다 지적')를 추가했다. 진단용이고 교사 강제 값이다.
- 끄기: `--no-stages`, `--no-init-encoder`. 계획만 있는 것: 색·배경색 늘리기.

## 확인된 것(검증 범위)
- **판 3 전체 자료**[Kaggle CPU, 커밋 91f39d4, 64분, GPU 0]: 학습 4해상도 각 35,115장·738파일(360 1,720MB / 480 93MB / 720 139MB / 1080 212MB), 시험 sv 965장, 위치 시험 ss 134장. 커널 `aisfa-seq-data` 출력.
- **전체 기능 CPU 흐름 시험**[Kaggle CPU, rc 0, 17분]: 미리 만든 자료 `--check` 6개 → 인코더 174항목 → 네 단계 전환(진행 21·45·71%) → 검증·생성 채점·저장.
  - CPU 시험은 `--tok-budget 1024 --max-batch 2`로 한다. CPU 강제 종료의 원인은 해상도가 아니라 CPU 교차 어텐션 메모리다(1장·922단어에 3.7GB). GPU T4는 최대 4.8GB였다.
- **외움 기준선**[서버, GPT 재현]: 원본을 원래 자리에 그대로 그린 '완벽하게 외운 AI'의 위치 시험 부분 점수는 전체 134장에서 17.65점, 학습기 기본 20장에서 15.88점이다(엄격 2.4%·1.1%). 그래서 절대 점수 합격선은 폐기했다.
- **페인트 저장 방식**[사용자 앱 녹화 11-01]: 면은 오브젝트별 T 구간 + 자동 연결선으로 저장된다. 관절 연결은 칠하기 조건이 아니다(docs/FORMAT.md 끝).
- **이전 확인**: 정답지 왕복 100%(22,371장), 렌더러 ≈ 앱 0.3%, Kaggle T4 30분 시험(2,403걸음, 54장 흐름용 — 실력 판단 불가), Drive ↔ Kaggle ↔ PC 이어하기.
- **단위 시험 98개 통과**(11-01, `python -m unittest discover -s tests`, 판정 장치 10개 + 원 면 반례 10개 추가).

## 도구 요약
- `tools/kaggle_seq_remote.py`
  - `push [--prebuilt] [--smoke] [--cpu] [--minutes] [--tok-budget] [--extra] [--no-stages] [--no-init-encoder]`
  - `push-data [--smoke] [--no-stages]`, `push-encoder 파일`
  - `status|wait|pull [--data] [--smoke]`, `save-ckpt`, `to-drive`, `from-drive`
- `tools/seq_train.py`
  - `train … [--stages 1920,1280,854 자료] [--init-encoder] [--px-budget] [--gen-minutes]`
  - `draw`, `vec-encoder`, `train … --judge 폴더 [--judge-dirs 2] [--judge-dirs-final 4] [--sheet-n 6]`
- `tools/seq_judge.py manifest|build 폴더|baseline 폴더`(판정 장치, 11-01)
- `tools/seq_data.py … [--W] [--video] [--synth] [--fixed dx,dy,배율] [--check]`
- PC: `pc_seq_1050ti_quick.bat`, `pc_seq_5060.bat [시간] [계획]`, `pc_seq_4060.bat [시간] [계획] [noyield]`. Drive `AI-sfa/02_분석자료/seq/`.
- 측정: `tools/measure_toklen.py`·`analyze_toklen.py`(docs/TOKEN-LENGTH-2026-10-31.md).

## SFA·앱 규칙(파일 만들 때)
- 앱은 DrawOrder를 읽지 않는다. AO ID 하나 = 파일 전체 공통 오브젝트, 레이어도 ID마다 하나.
- 면을 아래·위에 깔려면 레이어로 분리한다. 파란점 규칙은 docs/FORMAT.md를 따른다.
- 렌더러 ≈ 앱. 앱은 파일 비율로 영상을 내보낸다. 좌표는 화면 %. 사용자는 24,24로 만든다.

## 막힌 것 / 환경
- 서버 GPU 없음(CPU 4개, RAM 15GB). 사용자 GPU: 1050 Ti 상시, 5060 가끔, 4060 PC(RAM 32GB).
- 저장소 `/home/user/AI-sfa`, 주 브랜치 `ccr-bccf15a6-d6ee46`(11-01 세션은 `claude/new-session-gknz4t`에서 작업하고 같은 HEAD를 주 브랜치에도 푸시).
- 새 컨테이너 준비
  - `pip install opencv-python-headless numpy skia-python scipy scikit-image kaggle` + CPU torch(`--index-url https://download.pytorch.org/whl/cpu`)
  - `apt-get install libegl1 libgl1`
  - rclone v1.75.2 zip → /usr/local/bin(`RCLONE_CONFIG_GDRIVE_*`로 바로 연결)
  - Kaggle 비밀값 등록됨(출력 금지).

## 보호
- 원본 영상·추출 프레임·나카무라 자료·가중치·앱 녹화는 저장소에 넣지 않는다.
- GPT 측정 파일 중 정답 장 XML이 든 것(judge-pairs.json)도 비공개다.
- 사용자 수집 `.sfa`는 `data/user_sfa/`(공개).
- 토큰·키 출력 금지. 3D 금지. 사용자에게는 한국어로만.
