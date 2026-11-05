# AI-sfa 현행 인수인계 — 2026-11-05

한국어로 답한다. 브랜치 `claude/new-session-gknz4t`만(main 읽기/쓰기 금지). 저장 전 지정 브랜치 fetch·다른 변경 보존. 커밋 전 루트 `python -m unittest discover -s tests` 전체 OK/exit0을 따로 확인. GPU/새 학습/Kaggle 실행은 사용자 명시 승인 뒤에만.

- **읽기:** AGENTS.md 전체 → 이 문서 → docs/NEW-COLLABORATOR-ONBOARDING-2026-11-04.md → .claude/skills/stickman-extraction/START-HERE.md. 11-04 이전 상세 상태: docs/history/HANDOFF-BEFORE-2026-11-05.md.
- **비공개 자료 복원:** 새 환경이면 manifest의 Drive 링크 공유 파일을 `https://drive.usercontent.google.com/download?id=<ID>&export=download&confirm=t`로 받아 `restore_data.py --import-path`(11-04 Claude 확인: 13종 verified). rclone 설정은 drive.file 범위라 GPT가 올린 폴더 목록은 안 보이고, rclone 자신이 만든 파일·링크 공유 파일만 접근된다. 값/토큰 출력 금지.

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
