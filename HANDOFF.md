# AI-sfa 현행 인수인계 — 2026-11-03 새벽(KST 00:40)

- 작업 브랜치: `claude/new-session-gknz4t`. 이 세션의 배정 브랜치는 `ccr-10538cf4-93fhfq`이고, 같은 HEAD를 두 브랜치에 푸시한다. main에는 올리지 않는다.

- 이전 판(11-01 밤): docs/history/HANDOFF-2026-11-01-night.md
- 11-01–11-02 경과: docs/history/PROJECT-HISTORY-2026-11-01-02.md
- 10-14 → 10-31 전체 역사: docs/PROJECT-HISTORY-2026-10-31.md
- 새 대화 시작 문구: docs/HANDOFF-PROMPT.md

## 현재 우선순위(두 갈래가 동시에 진행 중)
1. **1단계 — 영상 → SFA 변환 AI(1판):** 1회차가 끝났다. **2회차(Kaggle 판 7)를 11-02 15:47 UTC에 시작했다**(사용자 허락, 이어하기, `--fresh` 없음). 예상 종료는 01:00–01:45 UTC(KST 11-03 10:00–10:45).
2. **2단계 — 실제 애니 → SFA → 생성기.** 첫 부품은 '인물 → 스틱맨' 변환이다.
   - **11-02 밤 사용자 지시:** 진짜 처음부터 다시 한다. 하던 변환(v1–v5)은 중단했다.
   - 주제: "어떻게 하면 애니 사람 캐릭터의 움직임을 스틱맨으로 전환할 수 있을까?"
   - 진행: Claude와 GPT의 토론·의논 형식으로 한다. 3D 배제는 뺐다. 외부 프로그램·도구·스킬 사용에 제약이 없다(Claude·GPT 모두).
   - 새 프롬프트: docs/GPT-PROMPT-ANIME-TO-STICKMAN-FRESH-2026-11-02.md
   - 토론 기록: docs/ANIME-TO-STICKMAN-DEBATE-2026-11-02.md(Claude 1차 의견 작성 완료, GPT는 1차 답 전에 이 파일을 열지 않음)

## 바로 할 일
1. **1단계 본 학습 — 1회차 완료, 2회차 실행 중(판 7, 15:47 UTC 시작)**
   - 2회차가 끝나면 pull → save-ckpt → seq_trend로 1회차와 같은 조건의 판정끼리 비교해 보고한다.
   - 1회차 모델 임의 그림 시험(CPU, 한 장에 8초): 직접 그린 스틱맨 그림에서 머리·몸 선·바닥선은 나왔지만 각도·위치가 틀렸다. 앱 기본 스틱맨 렌더에서는 짧은 선 하나만 나왔다. 애니 장면은 엉뚱한 결과였다(학습 범위 밖).
   - 결과: rc 0, 544.7분, 마감보다 52분 일찍 끝났다. plan 900분에는 닿지 못했다(plan_reached false).
   - pull·save-ckpt를 마쳤다(Kaggle 비공개 자료 `aisfa-seq-ckpt`). 판정 시트·로그는 Drive `02_분석자료/seq/run1_2026-11-02/`에 있다.
   - 추세(`seq_trend`): 판정 4회(139·285·414·543분).
     - A 점수 1.0 → 4.9 → 2.4 → 8.2(외움 기준 12.9, A−외움 −4.7).
     - 위치 읽기 8 → 26 → 20 → 28/45(필요 30).
     - 새 작품 F1 0.0 → 1.4. 건전성은 4회 모두 미통과.
     - 마지막 기록은 판정 조건이 바뀌어 같은 조건의 비교가 2회 미만이다. **추세를 말할 수 없다.**
   - 마지막 판정 시트(입력 | AI SFA | 정답 SFA): 물체 위치·종류는 대체로 맞추기 시작했지만, 스틱맨 팔다리 엉킴·십자 → 선처럼 모양은 아직 틀리다(Claude 눈).
   - **2회차 제안:** `python tools/kaggle_seq_remote.py push --prebuilt --gpu-ok --minutes 600 --plan-minutes 900 --extra "--gen-minutes 120"`. `--fresh`는 붙이지 않는다. GPU 실행은 사용자 허락 뒤에 한다.
2. **스틱맨 토론(처음부터):** GPT 6차(docs/GPT-ANIME-TO-STICKMAN-ROUND6-2026-11-02.md)와 Claude 7차 답까지 썼다(docs/ANIME-TO-STICKMAN-DEBATE-2026-11-02.md).
   - B325–333은 세 그림이다(325–327 / 328–330 / 331–333). 확인 경계는 `data/stickman_motion/verified_boundaries_1913_2026-11-02.json`에 있다.
   - `drawing_segments.py` 2판: 후보(candidate)와 확인(verified, `pose_copy_ok`)을 나눈다. 복사 가능한 것은 루트 기준 상대 포즈뿐이다.
   - 라벨 명세 v1.2(요약 순서, 부분 검증 대 전체 통과, 본문 정리).
   - 다음
     - CPU 피팅 진단 6조건(2D / 3D 평면 / 3D 깊이 × 원 RTMW / 검수 필터, 7차 §2 규칙)을 구현한다.
     - 좌표 라벨 JSON 형식 초안을 만든다.
     - '몸 돌리기' 구간을 찾는다.
     - 좌표 입력 방식(웹 도구 / 표)은 사용자 답 대기다.
   - GPU는 Colab(사용자 실행)으로 한다. 3D 모델은 사용자 등록(SMPL·SMPL-X, HF 접근 신청) 뒤에 한다.
   - nian41 원본 5개, RTMW 1913 결과, run1 출력은 scratchpad(`vid/`, `rtmw/`, `run1/`)에 있고, 세션이 끝나면 사라진다.
   - v5 앱 확인은 중단으로 필요 없어졌다. 점 ID 규칙(장마다 새로)은 앱 사실로 그대로 유효하다.
   - 옛 토론 자료(비교 영상, 앱 녹화, v1–v3 SFA, 포즈 좌표)는 Drive `gdrive:AI-sfa/02_분석자료/stickman_test_2026-11-02/`에 14개 파일로 있다. 둘지 지울지는 아직 사용자에게 묻지 못했다.
4. GPT 2단계 설계 검토: `docs/GPT-PROMPT-STAGE2-DESIGN-2026-11-02.md`. 사용자가 붙여 넣으면 진행한다.

## 사용자 결정 대기
- 기본 스틱맨 비율 유지 불필요는 사용자 확정. 인물 고유 비율 추정 방식·장별 원근 단축은 별도 검토한다(토론 기록 맨 끝 사용자 지시, GPT 2차).
- 2단계: ① 캐릭터 디자인 입력 방식 ② 첫 범위로 나카무라와 nian41을 쓸지 ③ 애니용 포즈 모델 조사. 이 셋은 GPT 토론 결과를 보고 정한다.
- Drive `stickman_test_2026-11-02` 자료를 유지할지.
- P1: 관절점(Flags 33)을 정답 문장에 넣을지(Claude 권장: 넣음). 예전 도구를 `tools/legacy/`로 옮길지.

## 2단계 '인물 → 스틱맨' — 중단된 옛 시도(기록용, 11-02 밤 중단. 상세: docs/GPT-PROMPT-ANIME-TO-STICKMAN-2026-11-02.md §3)
- 도구: `tools/pose_to_stickman.py`, 시험: `tests/test_pose_to_stickman.py`.
  - 포즈는 YOLO11m-pose(COCO 17점, 추론만)로 뽑았다. 서버 scratchpad `pose/pose_1913.json`에 있고, Drive에도 사본이 있다.
- 시험 장면: nian41 `1913231262086463573.mp4`(854×534, 24fps, 화면 위 50px부터 480줄), 298–390장. 창고에서 등을 보이며 걸어가며 팔을 휘두르는 장면이다.
  - 이 장면을 고른 이유: nian41 영상 8개를 훑었을 때 검출률이 0–39%였고, 연속으로 검출된 구간이 여기뿐이었다.
- 판별 경과
  - v1: 점 구조를 짐작해서 만들었다 → 앱에서 연결 안 됨, 머리 흔들림.
  - v2: 앱 기본 스틱맨 틀 사용(`data/app_templates/stickman_default.sfa`, 사용자 제공, 10조각, 관절점 없음) → 어색함.
  - v3: 원근 단축과 떨림 줄이기 추가 → 여전히 어색함. 팔이 가려지면 과하게 휘두른다(사용자).
  - v4: 길이 고정 → 편집하면 바로 깨짐.
  - v5: 점 ID를 장마다 새로 씀 → 확인 대기.
- 측정
  - 팔은 장의 20–31%에서 틀 길이의 0.6 미만으로 보인다(가려짐·원근).
  - 팔 방향이 한 장에 27–29° 이상 튀는 장이 10%다(떨림 줄이기 후 20–22°).
  - 실제 앱 스틱맨 파일 4개는 조각 길이가 장마다 거의 일정하다(중앙값 변화 0%).
- Claude 진단: 장마다 2D 투영을 베끼는 방식 자체가 문제다(가림, 원근, 몸 돌리기). 스틱맨 애니메이터는 키포즈 + 타이밍 + 관절 회전으로 그린다. 선택지 A–E(2D 개선, 키포즈 재연출, 3D 경유, 학습 변환기, 사람 검수)를 GPT와 토론 중이다.

## SFA·앱 규칙(파일 만들 때) — 11-02 정정 포함
- **ID 규칙(11-02 전수 조사 + 사용자 앱 시험으로 확정):**
  - 오브젝트(AO) ID는 장끼리 이어진다.
  - **점(AP) ID는 장마다 새로 쓴다**(여러 장 파일 304개 모두 이웃 장끼리 공유 0).
  - 점 ID를 모든 장에서 같게 쓰면 앱 편집에서 조각이 떨어진다(1장짜리만 정상).
  - 예전 기록의 "점 ID는 파일 전체에서 같은 대상"은 틀렸다. AGENTS.md는 정정했다.
- **앱 기본 스틱맨 구조**(`data/app_templates/stickman_default.sfa`)
  - 조각: 머리 원(TypeId 2, 지름 양끝 점), 몸통(Index0 목 Flags 4, Index1 골반 Flags 3 = 파란점·뿌리), 위팔(팔꿈치 5, 목 쪽 4), 아래팔(손목 5, 팔꿈치 쪽 4), 허벅지(골반 쪽 2, 무릎 5), 정강이(무릎 쪽 4, 발목 5).
  - 이어진 점끼리는 좌표가 같다.
  - 관절점(주황, Flags 33)은 사용자가 따로 지정한다. 기본 스틱맨에는 없다.
- 점 연결(AC) 묶음
  - 같은 레이어 안에서 점으로 이은 오브젝트는 한 무리다.
  - 무리 글로우를 먼저 그리고, 그다음 오브젝트마다 면과 선을 그린다.
  - 레이어를 넘어 묶이지는 않는다.
  - 앱 시험 test3–6으로 확인했다(docs/GPT-RESPONSE-RECHECK-CODE-REVIEW-2026-11-01.md §6-1).
- 레이어 순서는 모든 장 공통이다.
- 레이어 투명도: LayerDef `Opacity`. 막고라 1–11에만 있다. 렌더러, 정답 문장(`[LAYER] [LOPAC] 값`), 채점기에 반영했다.
- 파란점: 이어진 무리마다 꼭 하나. 위치는 상관없다.
- 앱 화면의 옅은 회색은 어니언 스킨이다.
- 앱은 DrawOrder를 읽지 않는다. 좌표는 화면 %다. 사용자는 24,24로 만든다.
- 상세: docs/FORMAT.md

## 1단계 상태 요약
- 자료 판 10(f731e51, LOPAC 단어 포함, 단어장 8212), 판정 자료 v5. Kaggle CPU 경로 점검과 GPU 속도 측정을 마쳤다(docs/GPU-SPEEDTEST-RUNBOOK-2026-11-01.md).
- GPT 재확인 R-01–R-06 수정(docs/GPT-RESPONSE-RECHECK-CODE-REVIEW-2026-11-01.md). I-10 글로우 묶음 채점 확정.
- **최종 시험 C안**: `data/final_test_c/`(index.csv 밖, 학습 미사용, 봉인). 작가 11명, 1,066장(막고라 001–011, chute, batch3 16개).
  - 작가 묶음: A = 스테인드 2·엔젤·묘·걷기달리기, B = 플립 3·노레그, 나머지는 각각 따로. 결과는 작가별로 보고한다.
  - 영상은 Drive `AI-sfa/02_분석자료/final_test_c/`에 있다.
- 비전문가용 해설 아티팩트: https://claude.ai/artifact/XFJUGxgnAt1BdNYnQLcRg5
- 단위 시험: `python -m unittest discover -s tests`(11-02, 전부 통과).

## 도구 요약
- 1단계
  - `tools/kaggle_seq_remote.py`
    - `push|status|wait|pull|data-check|save-ckpt|to-drive|from-drive`
    - GPU push에는 `--gpu-ok`가 필요하다.
  - `tools/seq_train.py`, `tools/seq_judge.py`, `tools/seq_data.py`, `tools/seq_trend.py`, `tools/ckpt_files.py`(예비 저장본 promote)
  - `tools/sfa_tokens.py`(정답 문장), `tools/sfa_render.py`(렌더러, `파일 출력폴더 --size 854x480`), `tools/sfa_objscore.py`(채점기), `tools/sfa_compose.py`(조합 문제)
- 2단계
  - `tools/pose_to_stickman.py pose.json 출력.sfa --start --end [--crop-y --h --name --thick --fore --var-scale]`
  - `tools/pose_extract.py`(YOLO 포즈 추론)

## 막힌 것 / 환경
- 서버: GPU 없음(CPU 4개).
- 사용자 GPU: 1050 Ti(상시), 5060(가끔 2시간 미만). Kaggle T4 주간 30시간.
- 저장소 `/home/user/AI-sfa`, 브랜치 `claude/new-session-gknz4t`(Kaggle 원격 도구 기본값도 이 브랜치).
- 새 컨테이너 준비
  - `pip install opencv-python-headless numpy skia-python scipy scikit-image kaggle ultralytics` + CPU torch(`--index-url https://download.pytorch.org/whl/cpu`)
  - `apt-get install libegl1 libgl1`
  - rclone(`RCLONE_CONFIG_GDRIVE_*`로 연결)
  - Kaggle 비밀값 등록됨(출력 금지)
  - 서버 scratchpad(포즈·영상 사본)는 세션마다 사라진다. 포즈 좌표와 nian41 영상은 Drive에서 다시 받는다: `gdrive:AI-sfa/01_원본영상/_Gemini용_저용량/nian41/`, `.../stickman_test_2026-11-02/pose_1913_yolo11m.json`

## 이번 세션에서 생긴 실수(반복 금지)
- 사용자 앱 녹화를 확인하지 않고 "모두 멀쩡하다"고 단정했다(실제로는 T3가 깨져 있었다). 녹화에서 구분이 안 되면 단정하지 말고 묻는다.
- 이미 답이 나온 것(T2 정상, T3 깨짐)을 두고 시험 파일을 또 만들어 사용자를 번거롭게 했다. 사용자에게 시험을 부탁하기 전에 실제 파일 전수 조사로 가를 수 있는지 먼저 본다(이번 원인도 그렇게 찾았다).
- 점 ID 규칙을 "같은 점 ID의 연결은 모든 장에서 같다(위반 0)"라는 뜻 없는 사실로 잘못 일반화했다. 규칙을 세울 때는 반대쪽 경우(장마다 새 ID인가)도 같이 센다.

## 보호
- 원본 영상·추출 프레임·나카무라 자료·가중치·앱 녹화는 저장소에 넣지 않는다(Drive만).
- judge-pairs.json도 비공개다.
- 사용자 수집 `.sfa`는 `data/user_sfa/`(공개). 앱 기본 스틱맨은 `data/app_templates/`.
- 토큰·키 출력 금지. 사용자에게는 한국어로만.
- 3D: 원래 금지다. 11-02 토론에서만 배제를 빼고 평가하며, 채택은 사용자가 결정한다.
