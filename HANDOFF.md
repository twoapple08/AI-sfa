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
| 5차 | 애니 95(문장-자세 불일치 16 제외) + 착지·무릎 모캡 24창 + 모캡 2,881 | PC 3,000단계(`ft_v5_gpu`): 걷기·펀치 유지, 일어서기(서 있기만)·착지(넘어져 누움) 여전히 실패 |
| 6차·7차(대조) | 6차 = 애니 0배(모캡 2,905), 7차 = 애니 1배 | PC방 5060: **애니를 줄일수록 나음**(6차가 낙하·착지 가장 좋음, 걷기 유지). 일어서기는 모든 판 실패(기본이 최선) |
| 8차 | 애니 없음, 모캡 11,464 + 착지 24, 6,000단계 | PC방 5060: 6차와 비슷. 달리기 가속 가장 큼(8.2–8.5m), 착지 뒤 눕는 경향, 일어서기 실패(기본이 최선) |
- 자료 도구: `tools/motion_dataset.py`(애니 3D = `tools/lift_apply.py` 출력, 위 방향 정렬·평활·디딤발 엉덩이 이동), 학습: `tools/momask_finetune.py`(VQ 고정, 마스크·잔차 트랜스포머만).
- 동작 문장: `data/style_kb/ai_results/codex_action_captions_2026-10-23.csv`(699행, 확신 낮음 269는 학습 제외, 판정수정 39 — 태그 색인 반영 전).
- 태그 색인·추출: `tools/tag_index.py`, `data/tag_index.csv`, 안내 [TAG-GUIDE](docs/TAG-GUIDE-2026-10-22.md).

## 다음 행동(2026-10-23 저녁, 사용자: "이펙트 없이 모션만 잘 나와도 괜찮은 장면인데 다 별로")
진단: 지금까지는 '동작이 맞는지'(착지·걷기)만 고쳤고 '보기 좋은지'는 안 다뤘다. 원인 ① 모캡식 고른 움직임 — 애니의 키 자세 멈춤·빠른 넘김 타이밍 없음(애니 3D 자료로 가르치기는 실패) ② 장면마다 2초 동작을 따로 뽑아 이어 붙여 이음새가 튐 ③ 구도 규칙 없음(걷기·달리기에서 인물이 점) ④ 얇은 선 막대 그림.
순서(효과 큰 순, 모두 서버에서 학습 없이 가능):
1. **애니 타이밍 입히기**: 생성 동작에서 키 자세(관절 속도 최저점)를 찾아 몇 프레임 멈추고 사이를 빠르게 넘김(착지 멈춤, 펀치 당김→내지름, 임팩트 정지). 나카무라 타이밍 자료(`tools/strike_timing.py`·`fx_timing` 결과)로 멈춤 길이 정하기.
2. **구도 규칙**: 인물이 화면 높이 40–60%가 되게 카메라 거리 자동(장면 4–6).
3. **장면 이음새**: 앞 장면 끝 자세 → 다음 장면 처음 몇 프레임 섞기.
4. **선 굵기·몸 비율**: 스틱파이터 기본 캐릭터처럼 굵게.
이어서(뒤로 미룸): 애니 자료는 동작 모양에서 빼고 타이밍으로만(사용자 동의 대기), 이펙트 학습 모델 방식, 1단계 언어 모델.
현재 최선 조립 명령: `storyboard_compose.py docs/storyboards/bench01_city_landing.json <출력> --momask <momask> --name t2m_…_ft_v8_gpu --res-name tres_…_ft_v8_gpu --scene-model 3=t2m_nlayer8_nhead6_ld384_ff1024_cdp0.1_rvq6ns,tres_nlayer8_ld384_ff1024_rvq6ns_cdp0.2_sw --seed 1`. mp4 만들기: `sfa_render.iter_frames`·`render_frame`로 모든 프레임 → cv2.VideoWriter(F fps).

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
