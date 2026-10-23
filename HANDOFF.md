# AI-sfa 현행 인수인계 — 2026-10-23 (오후)

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
| 3차 | 애니 117(Codex 동작 문장, 판정 구간 중심 2.2초 창, 창별 품질 필터) + 모캡 3,000 | PC 6,000단계(`ft_v3_gpu`): **섞임** — 낙하·펀치 나음, 일어서기·걷기 나빠짐, 착지 둘 다 실패(3씨앗). 원인: 애니 자료 엉덩이 높이 고정 버그. [결과](docs/MOTION-BASE-TEST-2026-10-22.md) |
| 4차 | 고친 애니 111(높이 복원) + 3차 모캡 2,881 | 자료 Drive `motion_data_mds4.zip` 준비됨, PC 학습 대기(안내 10번) |
- 자료 도구: `tools/motion_dataset.py`(애니 3D = `tools/lift_apply.py` 출력, 위 방향 정렬·평활·디딤발 엉덩이 이동), 학습: `tools/momask_finetune.py`(VQ 고정, 마스크·잔차 트랜스포머만).
- 동작 문장: `data/style_kb/ai_results/codex_action_captions_2026-10-23.csv`(699행, 확신 낮음 269는 학습 제외, 판정수정 39 — 태그 색인 반영 전).
- 태그 색인·추출: `tools/tag_index.py`, `data/tag_index.csv`, 안내 [TAG-GUIDE](docs/TAG-GUIDE-2026-10-22.md).

## 다음 행동
1. 사용자 PC에서 4차 학습(`ft_v4_gpu`, 3,000단계 약 27분, [안내 10번](docs/PC-1050TI-TRAINING-2026-10-22.md)) → 결과를 받아 기본·3차·4차를 `tools/bench_compare.py` + 관절 막대 비교(씨앗 1–3)로 본다. 판단 기준: 일어서기·걷기가 기본 수준으로 돌아오고 낙하·펀치 개선이 남는가.
2. 4차로도 일어서기·착지가 안 되면: 애니 2D→3D 자세 품질이 병목(문장과 자세가 어긋나는 창 많음) — 창별 자세-문장 일치 판정으로 거르기, 또는 애니 자료는 타이밍(빠름·멈춤)에만 쓰고 동작 모양은 모캡에 맡기기를 결정. 애니 자료에 착지·낙하 0, 펀치 1이라 기준 프롬프트 동작 학습엔 모캡 보강(히어로 착지·펀치 모캡 찾기)이 필요.
3. 조립기 이펙트(`--shapes`, 커밋 8f975ac)는 미검증 — 첫 시험에서 SFA 88MB·둘째 파일 빈 채 멈춤. 층 2–3겹·작은 파편 빼고 장면 하나로 먼저 시험.
4. 미구현 연출(균열·부유 파편·붉은 가시) 방법 결정 — 이펙트 형태 사전 + 학습 모델.
5. 1단계(프롬프트 → 스토리보드) 언어 모델 연결.

## 환경
- 새 컨테이너 복구(2026-10-23 확인): rclone은 `tools/codex_setup.sh` 1–2단계(환경 변수 `RCLONE_GDRIVE_AUTH_B64`), torch는 Python 3.13이라 `torch==2.6.0 torchvision==0.21.0`(cpu 저장소), CLIP은 `pip install --no-build-isolation git+https://github.com/openai/CLIP.git`, 렌더(skia)는 `apt-get install libegl1 libgl1`. momask는 Drive `07_도구/동작학습_1050ti/`의 code·checkpoints zip, CLIP은 `ViT-B-32.pt` → `~/.cache/clip/`. `motion_dataset.py`의 ref 관절은 `example_data/000612.npy`를 `recover_from_ric`로 바꿔 씀(HumanML3D는 모든 자료가 같은 뼈 길이). 2D 추적 = Drive `02_분석자료/포즈_정리/{nian41,yutaka_nakamura}`, 올리기 모델 = `02_분석자료/모델_3D올리기/lifter.pt`.
- PC 학습 결과는 사용자가 Drive의 별도 폴더에 올린다: `rclone lsf -R --drive-root-folder-id 1VDQR5yDVGkxykQaNduMZ5FNtDivOOmVy gdrive:`(같은 옵션으로 copy). 서버 1차(`_ft_anime`)·서버 3차(`_ft_v3`) 가중치는 컨테이너 재시작으로 사라졌고 백업 없음.
- 서버(GPU 없음): scratchpad `/tmp/claude-0/…/scratchpad`(대화마다 다를 수 있음) — `motion/momask-codes`(numpy 2 호환으로 고친 판 + 공개 가중치, `checkpoints/t2m/*_ft_anime`·`*_ft_v3`), `anim3d`(애니 3D), `mds3`(3차 자료), `data/mocap_unified`. 2026-10-23 01시경 컨테이너 재시작으로 돌던 학습이 끊긴 적 있음 — 긴 작업은 결과 저장 위치를 먼저 확인.
- 디스크가 자주 찬다(여유 1GB 안팎). Drive에 같은 사본이 있는 큰 파일만 서버에서 지운다(크기 대조 후).
- 사용자 PC: GTX 1050 Ti(4GB), Python `D:\ph`, 작업 `D:\mm`, 안내 [PC-1050TI-TRAINING](docs/PC-1050TI-TRAINING-2026-10-22.md). 단계당 약 0.53초(배치 16).
- 외부 AI: GPT Codex 새 세션(저장소·rclone 연결됨)으로 문장 작업. 커밋은 같은 브랜치로 들어온다 — 푸시 전 fetch·merge.
- 브랜치: `ccr-bccf15a6-d6ee46`(주 작업). 세션이 다른 브랜치를 배정하면 같은 HEAD를 거기에도 푸시.

## 보호
원본 영상·다른 작가 그림에서 뗀 형태·학습 자료·가중치는 저장소에 넣지 않는다(Drive). 토큰·키 출력 금지. Drive 삭제는 사용자 승인 후.
