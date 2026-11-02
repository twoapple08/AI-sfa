# AI-sfa 현행 인수인계 — 2026-11-01 밤

이전 판(10-31 낮의 상세 기록): docs/history/HANDOFF-2026-10-31-day.md
전체 역사(10-14 → 10-31): docs/PROJECT-HISTORY-2026-10-31.md
새 대화 시작 문구: docs/HANDOFF-PROMPT.md

## 현재 우선순위
**영상 → SFA 변환 AI(재설계판) 1판 — GPU 첫 회차 직전.** GPT 재확인(2e255ee) 새 반례 R-01–R-06을 재현·수정했다(554880c, 답변 docs/GPT-RESPONSE-RECHECK-CODE-REVIEW-2026-11-01.md). 앱 시험 `glow_link_test6`(14장, 레이어·면·원/곡선·글로우 전용 이음)이 렌더러 예상과 모두 같았다(11-02).
- 모델이 영상 한 장을 보고 SFA 오브젝트 문장(토큰열)을 직접 쓰고, 원본 파일과 오브젝트 단위로 채점한다. 주 목적은 스틱맨 동작(사용자 10-28).
- 설계: docs/VIDEO-TO-SFA-REDESIGN-2026-10-30.md, 해설: docs/EXPLAINER-VIDEO-TO-SFA-2026-10-31.md, 판정 기준(확정): docs/JUDGE-CRITERIA-FINAL-2026-10-31.md
- 학습 방식: 조합 문제 + 쉬운 것부터 + 해상도 단계 1080→720→480→360(docs/COMPOSE-CURRICULUM-2026-11-01.md)
- 11-01 낮까지의 상세 경과: docs/history/HANDOFF-2026-11-01-day.md

## 꼭 지킬 사용자 결정
- **사용자 지시 없이 Kaggle GPU 실행 금지**(코드도 막음: GPU push는 `--gpu-ok` 필요). 예산은 주간 30시간 '풀로'(사용자 11-01).
- 채점 원칙: AI 파일 대 원본 파일, 만점이면 영상도 육안상 같다. 영상이 안 바뀌는 차이는 정답(ID·면 칠 순서·파란점·점 방향·점 연결·겹치지 않는 것끼리 순서). **예외: 글로우가 겹치는 쌍의 점 연결 무리 차이는 영상을 바꾸므로 만점 아님(`glow_group`, 앱 확인 11-01).** 기본 점수 없음.
- 시험 작품 중 `47112(2_2)-1`의 7·8장만 새 작품 시험에서 뺀다(학습 `바람1-1`과 같은 그림, `data/holdout_exclude.json`).
- 토론은 논증거리가 없어질 때까지(사용자 10-31). GPT는 GitHub·Drive 직접 접근.

## 바로 할 일
1. **Kaggle 자료 판 10 완료**(f731e51, CPU 148분, 판정 자료 5.5분 포함): `data-check` — sd·sd1920·sd1280·sd854·sc 모두 100화소 넘는 어긋남 0(최대 85).
2. **GPU 속도 측정 실행 중**(사용자 지시 11-02, 커널 판 5, 00:35 UTC 시작, 실행표 명령 그대로): 끝나면 pull → 실측표·계획 계산 → 사용자 보고.
3. GPU: ① 속도 측정 회차(진행 중, 실행표 docs/GPU-SPEEDTEST-RUNBOOK-2026-11-01.md) → ② 실측한 학습 외 시간으로 계획(학습 진행 분)을 정함 → ③ 본 학습. 회차마다 `python tools/seq_trend.py log.jsonl`로 추세를 보여 드린다. 계획 정책: docs/GPT-RESPONSE-VERIFY-ROUND2-FLOWTEST-2026-11-01.md §5.
3. GPT에 응답 문서 재검토 요청(docs/GPT-RESPONSE-CODE-REVIEW-2026-11-01.md).
4. 측정(GPU 뒤): 길이별 생성 시간·마지막 평가 예상 대 실제, 메모리(rss_gb), 실제 장 노출, 묶음 검출 오탐(M-01–M-04).

**사용자 결정 대기**
1. GPU 첫 회차 지시와 본 학습 예산
2. P-03·P-01: 사용자가 C안(새 작품 별도 최종 시험)을 택해 첫 자료를 줬다 → `data/final_test_c/`(막고라 11컷 243장, 앱 영상 짝, 봉인). 다른 작가 작품 추가 수집은 진행 중. 38파일 판단용·최종용 분리(B안)를 함께 할지는 미정
3. P1 관절점(Flags 0x21)을 정답 문장에 넣을지(Claude 권장: 넣음 — 스틱맨 포즈 편집에 필요)
4. 예전 도구를 `tools/legacy/`로 옮길지

## 11-01 검토·확인 요약
- 검토 문서: Claude docs/CODE-REVIEW-CLAUDE-2026-11-01.md, GPT docs/GPT-CODE-REVIEW-2026-11-01.md(fef6ffb), 응답·대조 docs/GPT-RESPONSE-CODE-REVIEW-2026-11-01.md
- 고친 것: 공식 통과 = 부호 검정 ∧ 건전성, GPU push 잠금, PC 절대 마감, 판정 자료 미리 만들기, 메모리 기록, 비유한 기울기 = 실패, 채점 순서 예외 좁힘·글로우 번짐 범위, 판정 목록 검사(judge_list_ok), 추세 표 '통과'는 공식만, 저장 실패 처리, 묶음 레이어 순서, 공식 반복 차단, 글로우 묶음 채점(I-10).
- 시계: `train_min`(성공 업데이트만)이 학습률·단계·쉬운 것부터·공식 계획 끝을 정한다. 실패 시간은 `fail_min`, 벽시계는 `done_min`. `--deadline`은 절대 마감.
- 작은 CPU 통합 시험 `tools/seq_flow_small.py`(f731e51 단어장·검증 간격 수정 뒤 다시 모두 통과). 단위 시험 168개 통과.
- **앱 규칙 확인(11-01, 사용자 화면, 시험 SFA 4개)**: 점 연결(AC)로 이은 오브젝트는 한 무리로, 무리 글로우를 먼저 모두 그린 뒤 선을 그린다. 점 값(8/9·관절 33/5)·이음 방향·한쪽만 적은 AC와 무관. 점 ID는 파일 전체에서 같은 오브젝트를 가리킨다(실제 파일 위반 0) — 시험 SFA도 이를 지켜야 한다.
- 레이어 순서는 모든 장 공통(사용자 11-01). 여러 장 출력 조립 때 장별 레이어 목록을 하나의 공통 순서로 맞춰야 한다(조립 도구 만들 때 반영).

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
  - 점 연결을 만점에서 뺐다(단 글로우 겹침 무리 차이는 `glow_group`).
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
- 단위 시험: `python -m unittest discover -s tests`(11-02 168개 통과).

## 도구 요약
- `tools/kaggle_seq_remote.py`
  - `push [--prebuilt] [--smoke] [--cpu] [--gpu-ok] [--minutes] [--tok-budget] [--extra] [--no-stages] [--no-init-encoder]`
  - `push-data [--smoke] [--no-stages]`, `push-encoder 파일`
  - `status|wait|pull [--data] [--smoke]`, `data-check 폴더`(자료 커널은 pull 대신 이것), `save-ckpt`, `to-drive`, `from-drive`
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
- **레이어 투명도**(LayerDef `Opacity` 0–100, 새 앱 기능, 11-02 막고라 파일에서 처음 봄): 렌더러 반영(앱 영상과 평균 차 ≤ 2), 정답 문장 `[LAYER] [LOPAC] 값`(100은 안 적음), 채점기도 비교. 수집 453파일에는 없음.
- **파란점 규칙(사용자 11-02)**: 점 연결로 이어진 무리(무리 통째로 한 오브젝트)마다 파란점(Flags 3)이 꼭 하나 — 사람이 앱에서 편집할 수 있게. 디코더가 무리마다 첫 점을 3으로 붙인다(실제 5,157장 왕복: 빠진 무리 0, 회귀 시험 `test_lopac_bluept`).
- 앱 편집 화면 캡처의 옅은 회색 그림은 어니언 스킨(앞 장 겹쳐 보기)이다 — 대조할 때 빼고 본다(사용자 11-02). 점 표시·점선도 편집용.
- 렌더러 ≈ 앱. 앱은 파일 비율로 영상을 내보낸다. 좌표는 화면 %. 사용자는 24,24로 만든다.

## 막힌 것 / 환경
- 서버 GPU 없음(CPU 4개, RAM 15GB). 사용자 GPU: 1050 Ti 상시, 5060 가끔, 4060 PC(RAM 32GB).
- 저장소 `/home/user/AI-sfa`, 작업 브랜치 `claude/new-session-gknz4t`(Kaggle 원격 도구 기본값도 이 브랜치).
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
