# AI-sfa 현행 인수인계 — 2026-11-05

한국어로 답한다. 브랜치 `claude/new-session-gknz4t`만(main 읽기/쓰기 금지). 저장 전 지정 브랜치 fetch·다른 변경 보존. 커밋 전 루트 `python -m unittest discover -s tests` 전체 OK/exit0을 따로 확인. GPU/새 학습/Kaggle 실행은 사용자 명시 승인 뒤에만.

- **읽기:** AGENTS.md 전체 → 이 문서 → docs/NEW-COLLABORATOR-ONBOARDING-2026-11-04.md → .claude/skills/stickman-extraction/START-HERE.md. 11-04 이전 상세 상태: docs/history/HANDOFF-BEFORE-2026-11-05.md.
- **비공개 자료 복원:** 새 환경이면 manifest의 Drive 링크 공유 파일을 `https://drive.usercontent.google.com/download?id=<ID>&export=download&confirm=t`로 받아 `restore_data.py --import-path`(11-04 Claude 확인: 13종 verified). rclone 설정은 drive.file 범위라 GPT가 올린 폴더 목록은 안 보이고, rclone 자신이 만든 파일·링크 공유 파일만 접근된다. 값/토큰 출력 금지.


> **현재(2026-11-06, 정본 기록 docs/REPLAN-PLAN-DRAFT-2026-11-05.md 끝):** 글 → 동작 언어 모델(3B + LoRA) 1–3차는 걷기 주기를 못 만듦(3차는 평가 손실만 낮아지고 더 멈춤). 생성 경로는 **조각 잇기 `tools/compose.py`** — 걷기·달리기는 `tools/gait_cycle.py`(애니메이션 원리 계산 주기, 학습 아님), 다른 동작은 스타일 층 실제 조각 + 앞 6·뒤 9장 여유(다른 동작 앞에서 멈춤), 따라가는 카메라, nian41 리듬 보정(커밋 0f8293b). 사용자 눈가림 판정(A·B·C "셋 다 끔찍", 나카무라 실제 달리기만 봐줄 만) 뒤 고친 새판 비교 영상(scratch compose5) **사용자 판정 대기**. 걷기·달리기·펀치는 스타일 층 실제 조각 우선(loco48 거꾸로·nkm_16·n41_07), 몸 방향 넘기기. 붉은 날은 나중에, 가면 흔들림 없음(사용자 확정). 다음 후보(GPT 합의): 2D 확산 좁은 과제(사이 채우기) vs 계산 기준선, 작은 동작 토큰 표현. Kaggle: 새 계정 Titanium08 약 5시간 10분 사용(30시간 중), 옛 계정 약 1시간 남음 추정. GPU는 매번 허락.
>
> **2026-11-05 단계 2 진행(움직임 자료, 사용자 "nian41로 30구간", "부족하면 나카무라쪽도"):** 자동 추출 `tools/stage2_extract.py`(작업 폴더 = scratch `stage2/`, 원본·좌표·결과 비공개).
> 시트 검토로 바꾼 거르기: 흔들림 상한 0.15→2.0(빠른 동작까지 잘림), 트랙 늦게 시작 → 구간을 주 인물 관측 범위로 자름(팔다리 전체 NaN 5구간), 화면 밖 발목·골반–발목 0.6몸통 미만 제외, 무릎·발목 점수 중앙값 3.0 미만 제외(근접 상반신 컷 다리 지어냄), 액션 0.05 미만 제외, **같은 그림의 다른 판(X↔사쿠가, 사쿠가끼리) = 정규화 포즈 열 차이 <0.2로 제거**(썸네일 비교는 놓침). nian41 46영상(세로 2·개발 사례 제외) → 쓸 만함 약 22 → 나카무라(가로, 302394 제외)로 채우는 중(36 고른 뒤 눈 검토로 30).
> **발견:** 키포즈 PCHIP 보간이 유지 리듬(2s·3s)을 지움 → `drawings`(원본 그림 구간) 저장, `motion_ir.hold_drawings`(끊어 보여 주기 판), `tools/motion_style.py`(유지 리듬·빠른 전환 뒤 멈춤·예비 동작·획 최고 속도 위치, 카메라 흔들림 미측정). 태깅 시트 `tools/stage2_tag_sheets.py`, GPT 프롬프트 초안 docs/GPT-PROMPT-STAGE2-TAGGING-2026-11-05.md(30구간 ◆판정·Drive 업로드 뒤 새 GPT 세션에 보냄).
> **완성 기준 = 승인 10초판**(사용자 11-05: "60초판은 3분의 1 실패, 10초를 완성 기준"). 단계 2 변환은 확정 경로 `stickman_clip.person_in_shot`(50분위·투영 길이·머리 유지, 그림 키만 끔) — 비율 중앙값이 10초판과 맞음(data/stage2/selection_2026-11-05.json proportion_fix).
> **11-05 장별 수정:** 30구간(nian41만) 전부 Claude 원본 대조 → `data/stage2/edits/<영상>_<시작>.json`(원인 기록, 추출기가 자동 적용, 좌표 직접 지정 없음), 제외 135/1354장. 근접 컷 다리 숨김 규칙(NEAR_TORSO 30%). 사용자 제안 대기: 캐릭터 시트 8면(정면·우반·우측·좌반·좌측·후면·위·아래) + Claude 추천 후반측면 2면 = 10면.
> **11-05 사용자 정정:** 스미어는 팔다리를 지우지 않고 표시만(smear_mark, 나중에 덧대기). 안 보이는 다리는 숨기지 않고 예상 위치(보인 장 각도 보간, 길이 ≥10초판 비율, 화면 밖 허용, 발목만 보이면 무릎을 두 뼈 길이로) — actor['inferred']. 280830:156은 러프 원화라 제외.
> **11-05 검출기 비교 진행(사용자 '자세를 제대로 못 잡는 게 너무 많다' → 추천 A+B 승인):** A = Kaggle 비공개 커널 aisfa-posecmp(ViTPose++ Huge·Sapiens 1B, 자료 aisfa-posecmp-frames = 30구간 1,320장·상자 2,164) — `tools/kaggle_pose_cmp.py`(pack/push-data/push/status/pull/apply), 결과 비교 `tools/pose_cmp_report.py`(같은 구간 STAGE2_SEGMENTS·수정 미적용으로 튐·접힘·예상 다리 수 + 나란히 영상). B = `stage2_extract.py --easy`(몸통 < 25%·예상 다리 ≤ 30%·팔 숨김 ≤ 10%). 캐릭터 시트 v3 10면(사용자 '좋네, 보충해서 추가로 줄게'; 우측면 = 얼굴이 화면 왼쪽인지 확인 대기).
> **검출기 비교 결과(11-05):** RTMW 유지(ViTPose·Sapiens 개선 없음). Kaggle 사용 약 1시간 10분(v3 약 56분 + ViTPose 재실행) → 잔여 약 3시간 20분 추정.
> **Kaggle GPU 잔여(사용자 11-05 UTC 약 14:50 보고): 4시간 30분** — 실행 중인 aisfa-posecmp v3(13:58 무렵 시작)도 이 시간을 쓰고 있다. 새 GPU 실행 전 남은 시간과 예상 소요를 먼저 비교한다.
> **다음(옛):** 나카무라 채우기 실행 끝 → drawings 포함 재실행 → 30구간 1차 눈 판정 → 몸 방향 원본 대조 → 사용자 ◆표본 판정(부드러운 판/끊어 보여 주기 판 나란히) → 스타일 실측·태깅.
>
> **2026-11-05 진행:** 계획 승인 → **단계 1 완료**(사용자 v5 "좋은 것 같아"): `tools/motion_ir.py`(중간 표현 v1·컴파일러, 60초판 왕복 불일치 0), `tools/char_sheet.py`(캐릭터 시트 읽기·연속 방향·PBD 망토·흰 채우기·레이어 순서), `tools/facing_from_pose.py`, 시험 `tests/test_motion_ir.py`. 기록 docs/REPLAN-PLAN-DRAFT-2026-11-05.md '진행 기록'. 함께: SFA 뷰어 Windows 1.2(docs/SFA-VIEWER-WIN-1.2-2026-11-05.md). **다음 = 단계 2(움직임 자료 만들기)** — 시작 전 사용자에게 범위 확인. **상시 요청(사용자 11-05): 계획표 체크 목록(docs/REPLAN-PLAN-DRAFT-2026-11-05.md '체크 목록')을 작업이 끝날 때마다 갱신하고, 달라고 하면 최신본(PDF 포함)을 준다.**
>
> **2026-11-05 재계획(정본):** 사용자 "산발식이었다 — 지금까지 것은 남기고 처음부터 계획". 확정 조건 **docs/REPLAN-CONDITIONS-2026-11-05.md**, 계획 초안 **docs/REPLAN-PLAN-DRAFT-2026-11-05.md**(사용자 미승인 — 승인 전 실행 금지), 대화 기록 docs/REPLAN-REQUIREMENTS-2026-11-05.md, 조사 docs/RESEARCH-ANIME-GEN-ARCHITECTURES-2026-11-05.md. 아래 기존 내용은 재계획 이전 상태 기록.

## 큰 그림(사용자 11-04 계획)

변환기(그림→SFA)와 스틱맨화로 클립을 "SFA화"(배경·이펙트·연출을 라벨 붙은 요소로 + 인물은 스틱맨) → 많이 쌓아 태그/문장/스토리보드로 .sfa를 만드는 AI. 최종 AI는 **중간 표현**(docs/SFA-INTERMEDIATE-REPRESENTATION-DRAFT-2026-11-04.md)을 생성하고 컴파일러가 .sfa를 만든다(초안, 사용자 미승인 부분 있음).

## 현재 진행 3갈래

1. **변환기(그림→SFA 토큰)** — docs/SEQ-CONVERTER-DIAGNOSIS-2026-11-04.md, docs/SEQ-COORD-TWO-LEVEL-DESIGN-2026-11-04.md
   - 원인 확정: 8192 초미세 좌표칸에 확률이 흩어져 생성이 무너짐 → **두 단계 좌표(`seq_train --coord2`, C128→F64)** 구현. Kaggle 60분 비교(aisfa-seq-coord2-ab-base/two): 교사 강제 좌표 오차 17.2%→4.8%, 입력의존 판정 two만 통과. 그러나 생성은 둘 다 실패.
   - two의 남은 문제(CPU 진단 확인): **앞 좌표 베끼기**(끝점이 시작점으로 몰려 길이 4px 조각). 멈추지 못함은 끝냄 결정 불균형(적은 객체 부족 아님).
   - 준비됨: `--objective balanced-v1`(종료 보조 손실)이 coord2와 함께 동작(시험·CPU 흐름 확인), 생성 보정 `generate(big_mass, coord_window)` 선택 기능, 별도 Kaggle 커널 이름 `--kernel-name`.
   - **진행 중:** `tools/coord_repr_probe.py`로 베끼기 대책 CPU 비교(two / two_w 손실 가중 / ptr 격자 포인터, seed0·1). 단, 이 작은 과제에선 two의 붕괴가 1% 수준이라 실제 문제를 잘 재현하지 못할 수 있음.
   - 다음: 비교 결과로 대책 선택 → 실제 seq_train 반영 → 사용자 승인 뒤 Kaggle 장기(약3h) "두 단계+대책+종료 손실". GPU 잔여: 11-05 02:4x 사용자 확인 10h11m에서 비교 2개(각 약2h 세션) 사용, 초기화 11-07 09:00 KST.
2. **SFA화 시험판**(원본1032–1271, 사용자 "추천대로") — docs/SFA-SLICE-V0-2026-11-05.md, 코드 tools/slice/
   - 원화(현행 추출 원본)는 이펙트·채색이 부족 → 사용자 제공 **완성본**(Drive 1B9it03a32XyEvd_KK3ZoOxWVurs582bl, 854×480, 4212장). 이 구간 **완성본=원화+7장**(눈 대조, 영상 전체 고정 오프셋 아님). 인물·파편 영역은 원화에서 빌림.
   - 사용자 방향: 면 채우기 금지에 가깝게 "**윤곽 먼저, 채색은 나중**", "**직선이면 직선 객체**". 현재 = 학습된 선화 추출기(ControlNet lineart sk_model) → 곡선 획, 휘지 않은 조각은 직선(TypeId1)으로, 장당 약250–560획(60–70% 직선). 사용자 반응 "아쉬운데" 뒤 개선 중. 긴 구조선 끊김·선 라벨 미부여 남음.
   - **배경 판(고정 각도 와이드샷, 사용자 제안)**: 1032–1135 순수 평행 이동 → 판 한 장에서 투시도 선을 한 번 따고 장마다 옮겨 배치(배경 객체 ID 고정). **v2(fbeced6, 사용자 정정):** 판 기준 = **부서지기 전**(1077 이전 장만), 바닥 띠 = 그림자라 구조선 제외, 인물 그림자는 밝기 75백분위로 제거. 다음: 1080~ 파손·파편 요소 트랙, 1251~ 와이드샷. 앱 확인 전(Drive 1GsLVJKYJTFzwUZ3bgZU0pDuHxEoTTjJ8).
   - 레이어 이름 라벨: **앱 저장 후 보존 확인**(사용자 저장본), 레이어 순서는 모든 프레임 공유(사용자 설명).
3. **스틱맨(60초판)** — 최신 수정 SFA [1Ba4WVy8NzRHIfjqxh4BsMLDQN6boIAeJ](https://drive.google.com/file/d/1Ba4WVy8NzRHIfjqxh4BsMLDQN6boIAeJ/view)(869장 파랑 왼발목 수정, XML 7c6f311b…, 재현 1Kn2utrinBXfYGoHJpFCt2nw1RDKCE53O, 코드 지문 ea8424b). 5겹침/24가속 후보 원본 대조 완료(수정은 869만). **사용자 판정 대기:** 876–877 파랑 근경 다리/몸 출력 없음, 1572/1574 빨강 팔 모호, 최신판 앱 확인. 이전 재현 묶음(1xzyO…)은 tools 변경으로 현재 HEAD 지문이 달라 `8cad3d7` worktree에서 재현.

## 지켜야 할 것(요약)

스틱맨 규칙(2D·기본11편집망·장마다 새 점ID·객체ID 연속·Flags3 하나·(24,24)·틀밖 허용·손가락/발가락/발길이0·근경 연속면·실제 접촉만·50px fallback 금지)은 AGENTS.md와 스킬 SKILL.md. 원본 영상·추출 그림·SFA 결과물·가중치는 Git 금지(Drive/비공개). 24개발사례는 held_out=false/training_ready=false. 보호 판정 JSON·작가별 학습 범위 재해석 금지. 공식 Kaggle 커널(aisfa-seq-train)·가중치·합격선은 실험으로 바꾸지 않는다.

## 이번 세션(11-04~05 Claude) 커밋 흐름

ea8424b(A/B 배율 넘침 수정) → 67973ec/e159ae9(869 수정) → 90a1811(v3 실행) → fd50963·58d5c5a(변환기 진단·정정) → cda27c9…914d635(좌표 표현 CPU 비교) → 2e3a340(--coord2) → cc9ba61(Kaggle 비교 실행) → 7837e93·f563723(결과·끝점 붕괴) → c59f735…28cac23(시험판·완성본·선화) → f8ce57b(베끼기 대책 시험 도구) → 0dbd83a(--objective) → f4ac6a2(coord3) → 9747ab2·fbeced6(배경 판 v1·v2) → 배경 판 v3 방 틀만(PLATE_BOX) → v4 왼쪽 열린 공간(사용자, 선 5개) → **배경 3D 모형 room3d v2**(사용자: 배경 3D 허용·기둥 포함·사물 제외·선 끝까지·Z축은 굵기 면, Drive 1iBWjb6V3Z_SdilUu5EGzvPki-z3h9Kc9) · Kaggle coord3 회차 76/180분 조기 멈춤 원인(마지막 평가 20배 과대 예상) 수정 --final-gen-est.

- 11-05 단계 6 연결부 `tools/tokens_to_sfa.py` 망토 레이어 수정(사용자 지적): 시트를 `CS.rig(CS.read_all(...))`로 넘김. 근거·시험: docs/REPLAN-PLAN-DRAFT-2026-11-05.md 단계 6, tests/test_motion_style.py TokensToSfaCape.
