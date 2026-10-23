# 인수인계 프롬프트 (2026-10-23 저녁, 동작을 '보기 좋게' 만드는 단계)

https://github.com/twoapple08/AI-sfa 작업을 이어서 한다. 작업 브랜치는 `ccr-bccf15a6-d6ee46`이다. 시작할 때 fetch·merge하고, 시스템이 다른 브랜치를 배정하면 같은 HEAD를 그 브랜치에도 푸시한다. 한국어로 답한다(영어로 답하지 말 것 — 사용자가 여러 번 지적).

**읽기 순서:** AGENTS.md(특히 '최종 목표'·'기본 테스트 영상'·'이펙트 그리기 원칙') → **HANDOFF.md(현재 상태·다음 행동)** → 필요할 때만 docs/MOTION-BASE-TEST-2026-10-22.md(동작 학습 1–8차·문장 시험 경과), docs/STORYBOARD-SCHEMA-2026-10-22.md, docs/PCBANG-RTX5060-TRAINING-2026-10-23.md(PC방 학습 방법).

## 목표 한 줄
배경·장면 글(기준 프롬프트 1 = `docs/storyboards/bench01_city_landing.json` 원문)을 넣으면 고퀄 스틱파이터 .sfa를 뽑는 AI. 지금은 이펙트 없이 **동작·카메라만으로도 보기 좋은 장면**을 만드는 단계.

## 지금 상태(2026-10-23 저녁)
- 동작 모델: 공개 MoMask + 미세조정 8차(`_ft_v8_gpu`, 애니 없음·모캡 11,464)가 현재 최선. 일어서기 장면만 기본 모델(`--scene-model 3=…`). 착지는 문장을 "drops from above and lands crouching on one knee"로 바꿔 해결("superhero landing"은 모델이 모름).
- 조립기: 장면별 모델, 낙하 추적 카메라(하늘 올려다봄 → 붉은 섬광 → 카메라 쪽으로 낙하 → 카메라가 따라 내려와 착지까지 끊김 없이 — 사용자 구도).
- 사용자 평가: "이펙트 없이 모션만 잘 나와도 괜찮은 장면인데 다 별로". 진단과 순서는 HANDOFF '다음 행동'.
- 가중치(기본·v3–v8)는 서버 scratch에만 있다. 새 컨테이너면: rclone 설정(`tools/codex_setup.sh` 1–2단계), momask 코드·기본 가중치 = Drive `07_도구/동작학습_1050ti/`의 zip, 미세조정 가중치 = 결과 폴더(`rclone … --drive-root-folder-id 1VDQR5yDVGkxykQaNduMZ5FNtDivOOmVy gdrive:`; v6·v7·v8은 `results_v6_v7.zip`·`results_v8.zip` — Windows zip이라 경로가 역슬래시, unzip은 경고 후 정상), torch 2.6 cpu·CLIP(`--no-build-isolation`)·skia(`apt-get install libegl1 libgl1`)는 HANDOFF '환경'.

## 바로 할 일
1. HANDOFF '다음 행동' 1(애니 타이밍 입히기)부터. 결과는 mp4로 만들어 보여 주고 이전 판(Drive `04_SFA시험작/bench01_2026-10-23_v8_낙하추적카메라/`)과 비교한다.

## 사용자와 일하는 방식
- 결과는 그림·영상·SFA로 바로 보여 주고, 문제를 정직하게 적는다. 규칙 코드로 그림을 '지어내는' 방식은 품질 미달로 판정됐다.
- 오래 걸리는 작업은 시작 전에 시간을 말하고 중간에 짧게 알린다.
- 사용자 PC 안내는 복사해 쓰는 명령 줄이나 더블클릭 bat으로. 작업 위치는 D(`D:\mm`). PC방 RTX 5060은 cu128 torch 필요.
- 외부 AI(GPT Codex)에는 저장소·rclone이 연결돼 있다. 프롬프트 끝에 커밋 해시·파일 경로를 보고하게 한다.
