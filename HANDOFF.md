# AI-sfa 현행 인수인계 — 2026-10-23

> 2026-10-16 배경(AOT 분석·환경 복구)은 [docs/history/HANDOFF-2026-10-16-archive.md](docs/history/HANDOFF-2026-10-16-archive.md). 상세 프롬프트는 [docs/HANDOFF-PROMPT.md](docs/HANDOFF-PROMPT.md).

## 현재 우선순위
**프롬프트(배경·장면 글) → 고퀄 스틱파이터 .sfa를 만드는 AI.** 기본 테스트는 기준 프롬프트 1(`docs/storyboards/bench01_city_landing.json` 원문 — 도시, 붉은 섬광, 낙하·착지, 균열·부유 파편, 뒤로 빠지는 카메라, 붉은 가시, 걷기→달리기, 순간이동 펀치, 암전). 새 모델·도구마다 이것으로 끝까지 뽑아 이전 결과와 비교한다(AGENTS).

## 구조(2026-10-22 사용자 합의: "기초 모델 + 우리 자료" = 체크포인트 + LoRA 방식)
1. 프롬프트 → 스토리보드(언어 모델) — **미구현**. 지금은 손으로 쓴 정답 예시. 형식: [STORYBOARD-SCHEMA](docs/STORYBOARD-SCHEMA-2026-10-22.md)(T/F, 전체·장면 초·최소초 — 모두 비울 수 있음, 배경 채색/비채색, 나누기 5초).
2. 동작 → 3D 관절: 공개 MoMask(HumanML3D) + 추가 학습(트리거 "in anime style"). [MOTION-BASE-TEST](docs/MOTION-BASE-TEST-2026-10-22.md).
3. 연출 요소(임팩트·이펙트·배경) — 임팩트 프레임 규칙은 [P3 8–9차](docs/P3-EFFECT-LAYERS-2026-10-21.md), 이펙트 형태 사전(GPT 판정 반영)은 Drive. 균열·부유 파편·붉은 가시·연필 임팩트 그림 **미구현**(학습 모델 없음 — 규칙 코드로 그린 임팩트는 품질 미달로 판정됨).
4. 조립 → .sfa: `tools/storyboard_compose.py`(길이·동작 생성·3D 카메라·땅 격자·색 섬광·순간이동·암전·5초 분할). 관절→스틱 `tools/motion_to_sfa.py`.

## 동작 모델 학습 상태
| 판 | 자료 | 결과 |
|---|---|---|
| 기본(학습 전) | — | 걷기·일어서기 자연스러움. 히어로 착지·카메라 쪽 펀치 약함, 애니식 끊어짐 없음 |
| 1차(서버 3,000단계) | 애니 471(짧은 라벨) + 모캡 4,000 | **나빠짐**: 착지→바닥 기기, 펀치 안 함. 원인 = 빈약한 문장·나쁜 3D 창·4배 반복 |
| 3차 | 애니 117(Codex 동작 문장, 판정 구간 중심 2.2초 창, 창별 품질 필터) + 모캡 3,000 | 서버 CPU 1,500단계·PC 1050 Ti 6,000단계(`ft_v3_gpu`) 진행 중(2026-10-23) |
- 자료 도구: `tools/motion_dataset.py`(애니 3D = `tools/lift_apply.py` 출력, 위 방향 정렬·평활·디딤발 엉덩이 이동), 학습: `tools/momask_finetune.py`(VQ 고정, 마스크·잔차 트랜스포머만).
- 동작 문장: `data/style_kb/ai_results/codex_action_captions_2026-10-23.csv`(699행, 확신 낮음 269는 학습 제외, 판정수정 39 — 태그 색인 반영 전).
- 태그 색인·추출: `tools/tag_index.py`, `data/tag_index.csv`, 안내 [TAG-GUIDE](docs/TAG-GUIDE-2026-10-22.md).

## 다음 행동
1. 3차 학습 결과(서버 `ft_v3`, PC `ft_v3_gpu` — 사용자가 Drive `07_도구/동작학습_1050ti/결과/`에 올림)로 기준 프롬프트를 조립기로 뽑아 기본·1차·3차 비교.
2. 결과가 기본보다 나으면 자료 늘리기(3D 추적이 없는 Codex 문장 구간 회수, 확신 '보통' 비중), 아니면 원인(자료 양 117개) 대응.
3. 미구현 연출(균열·부유 파편·붉은 가시) 방법 결정 — 이펙트 형태 사전 + 학습 모델.
4. 1단계(프롬프트 → 스토리보드) 언어 모델 연결.

## 환경
- 서버(GPU 없음): scratchpad `/tmp/claude-0/…/scratchpad`(대화마다 다를 수 있음) — `motion/momask-codes`(numpy 2 호환으로 고친 판 + 공개 가중치, `checkpoints/t2m/*_ft_anime`·`*_ft_v3`), `anim3d`(애니 3D), `mds3`(3차 자료), `data/mocap_unified`. 2026-10-23 01시경 컨테이너 재시작으로 돌던 학습이 끊긴 적 있음 — 긴 작업은 결과 저장 위치를 먼저 확인.
- 디스크가 자주 찬다(여유 1GB 안팎). Drive에 같은 사본이 있는 큰 파일만 서버에서 지운다(크기 대조 후).
- 사용자 PC: GTX 1050 Ti(4GB), Python `D:\ph`, 작업 `D:\mm`, 안내 [PC-1050TI-TRAINING](docs/PC-1050TI-TRAINING-2026-10-22.md). 단계당 약 0.53초(배치 16).
- 외부 AI: GPT Codex 새 세션(저장소·rclone 연결됨)으로 문장 작업. 커밋은 같은 브랜치로 들어온다 — 푸시 전 fetch·merge.
- 브랜치: `ccr-bccf15a6-d6ee46`(주 작업) + `ccr-9131e8a7-0gjed0`(세션 지정) 둘 다 푸시.

## 보호
원본 영상·다른 작가 그림에서 뗀 형태·학습 자료·가중치는 저장소에 넣지 않는다(Drive). 토큰·키 출력 금지. Drive 삭제는 사용자 승인 후.
