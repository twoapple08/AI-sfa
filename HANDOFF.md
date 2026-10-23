# AI-sfa 현행 인수인계 — 2026-10-23 (오후 늦게)

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
| 4차 | 고친 애니 111(높이 복원) + 3차 모캡 2,881 | PC 3,000단계(`ft_v4_gpu`): **걷기 회복**, 일어서기·히어로 착지 여전히 실패(착지는 눕거나 뒤엉킴). 원인 추가: "stands upright"인데 엉덩이 낮은 창, 실제 일어서기 창 0 |
| 5차 | 애니 95(문장-자세 불일치 16 제외) + 착지·무릎 모캡 24창 + 모캡 2,881 | 자료 Drive `motion_data_mds5.zip`, PC 학습 대기(안내 11번) |
| 6차(대조) | 5차에서 애니만 뺌(모캡 2,905) | 자료 Drive `motion_data_mds6.zip`, 5차 뒤 PC 학습(안내 12번). 5차와 비교해 애니 자료의 득실 판단 |
- 자료 도구: `tools/motion_dataset.py`(애니 3D = `tools/lift_apply.py` 출력, 위 방향 정렬·평활·디딤발 엉덩이 이동), 학습: `tools/momask_finetune.py`(VQ 고정, 마스크·잔차 트랜스포머만).
- 동작 문장: `data/style_kb/ai_results/codex_action_captions_2026-10-23.csv`(699행, 확신 낮음 269는 학습 제외, 판정수정 39 — 태그 색인 반영 전).
- 태그 색인·추출: `tools/tag_index.py`, `data/tag_index.csv`, 안내 [TAG-GUIDE](docs/TAG-GUIDE-2026-10-22.md).

## 다음 행동
1. 사용자 PC 5차(`ft_v5_gpu`, [안내 11번](docs/PC-1050TI-TRAINING-2026-10-22.md)) 결과로 기본·4차·5차(+6차 대조) 비교(`tools/bench_compare.py` + 관절 막대, 씨앗 1–3). 보는 것: 일어서기가 서는지, 착지가 낮게 웅크렸다 서는지, 걷기·펀치 유지.
2. 5차로도 착지·일어서기가 안 되면 애니 2D→3D 품질 문제로 보고, 애니는 타이밍(빠름·멈춤)에만 쓰고 동작 모양은 모캡에 맡기는 쪽을 검토(기본 모델 + 모캡 보강만 한 판과 비교).
3. 이펙트: 규칙 배치(`--shapes`) 시험 결과 품질 미달(아래) — 학습 모델 방식으로 결정 필요. 형태 사전 `fx_shapes.txt`는 Drive `02_분석자료/이펙트_형태사전/`에 복구됨(1,591개, GPT 판정 번호와 시트 픽셀 일치 확인).
4. 1단계(프롬프트 → 스토리보드) 언어 모델 연결.

## 이펙트 규칙 배치 시험(2026-10-23, 커밋 8f975ac 코드)
- 기준 프롬프트 전체 230프레임, 약 4분, SFA 88MB + 164MB(둘째 파일도 정상 기록 — 이전 '빈 파일'은 중단 때문으로 보임). 그림: Drive `04_SFA시험작/bench01_2026-10-23_fx_shapes/frames.jpg`.
- 부유 파편(돌 형태)은 그럴듯, 균열은 검은 긴 줄 몇 개, **붉은 가시는 지평선을 덮는 빨간 벽**. 장면 3의 "부유하던 부스러기가 떨어짐"을 새 부유로 읽어 돌 36개가 한 번 더 생기는 버그(고침). 규칙으로 계속 다듬지 않음(규칙 그림 품질 미달 판정과 같은 결론).

## 환경
- 새 컨테이너 복구(2026-10-23 확인): rclone은 `tools/codex_setup.sh` 1–2단계(환경 변수 `RCLONE_GDRIVE_AUTH_B64`), torch는 Python 3.13이라 `torch==2.6.0 torchvision==0.21.0`(cpu 저장소), CLIP은 `pip install --no-build-isolation git+https://github.com/openai/CLIP.git`, 렌더(skia)는 `apt-get install libegl1 libgl1`. momask는 Drive `07_도구/동작학습_1050ti/`의 code·checkpoints zip, CLIP은 `ViT-B-32.pt` → `~/.cache/clip/`. `motion_dataset.py`의 ref 관절은 `example_data/000612.npy`를 `recover_from_ric`로 바꿔 씀(HumanML3D는 모든 자료가 같은 뼈 길이). 2D 추적 = Drive `02_분석자료/포즈_정리/{nian41,yutaka_nakamura}`, 올리기 모델 = `02_분석자료/모델_3D올리기/lifter.pt`.
- PC 학습 결과는 사용자가 Drive의 별도 폴더에 올린다: `rclone lsf -R --drive-root-folder-id 1VDQR5yDVGkxykQaNduMZ5FNtDivOOmVy gdrive:`(같은 옵션으로 copy). 서버 1차(`_ft_anime`)·서버 3차(`_ft_v3`) 가중치는 컨테이너 재시작으로 사라졌고 백업 없음.
- 서버 scratch에 지금 있는 것(컨테이너가 바뀌면 사라짐): momask + 기본·`_ft_v3_gpu`·`_ft_v4_gpu` 가중치, `anim3d`(nian41·나카무라 다시 올림), `mds3`·`mds4`·`mds5`, `fx_shapes.txt`, `mocap/mixamo.npz`.
- 서버(GPU 없음): scratchpad `/tmp/claude-0/…/scratchpad`(대화마다 다를 수 있음) — `motion/momask-codes`(numpy 2 호환으로 고친 판 + 공개 가중치, `checkpoints/t2m/*_ft_anime`·`*_ft_v3`), `anim3d`(애니 3D), `mds3`(3차 자료), `data/mocap_unified`. 2026-10-23 01시경 컨테이너 재시작으로 돌던 학습이 끊긴 적 있음 — 긴 작업은 결과 저장 위치를 먼저 확인.
- 디스크가 자주 찬다(여유 1GB 안팎). Drive에 같은 사본이 있는 큰 파일만 서버에서 지운다(크기 대조 후).
- 사용자 PC: GTX 1050 Ti(4GB), Python `D:\ph`, 작업 `D:\mm`, 안내 [PC-1050TI-TRAINING](docs/PC-1050TI-TRAINING-2026-10-22.md). 단계당 약 0.53초(배치 16).
- 외부 AI: GPT Codex 새 세션(저장소·rclone 연결됨)으로 문장 작업. 커밋은 같은 브랜치로 들어온다 — 푸시 전 fetch·merge.
- 브랜치: `ccr-bccf15a6-d6ee46`(주 작업). 세션이 다른 브랜치를 배정하면 같은 HEAD를 거기에도 푸시.

## 보호
원본 영상·다른 작가 그림에서 뗀 형태·학습 자료·가중치는 저장소에 넣지 않는다(Drive). 토큰·키 출력 금지. Drive 삭제는 사용자 승인 후.
