# 인수인계 (2026-10-21 밤, 전체 학습 준비 P0 완료·P1 노트북 대기)

https://github.com/twoapple08/AI-sfa 작업을 이어서 한다. 작업 브랜치는 `ccr-bccf15a6-d6ee46`이다(같은 내용이 `claude/eager-clarke-lz1z9m`에도 있다). fetch 후 이 브랜치에서 계속한다. 시스템이 다른 브랜치를 배정해도 사용자 지정이 우선이다.

**읽기 순서:** AGENTS.md(특히 끝의 '이펙트 그리기 원칙'·'전체 학습 결정') → 이 문서 §0 → **docs/PREP-PLAN-2026-10-21.md(현재 계획)** → docs/SFA-CREATOR-2026-10-21.md(앱 v0.1) → 필요할 때만 docs/SUPPLEMENT-PLAN-2026-10-21.md → docs/ELEMENT-RANK-DRAFT-2026-10-21.md(현재 결과) → docs/ELEMENT-RANKING-PLAN-2026-10-20.md → 필요할 때만 docs/GEMINI-TASK-ACTION-TYPES-2026-10-20.md(동작 세기 경과)와 docs/SOURCE-FORMAT-2026-10-20.md(셀 폐기). 직전 긴 인수인계(임팩트 분류·뷰어·셀 판정 경과)는 docs/history/HANDOFF-PROMPT-2026-10-20-archive.md에 있다.

## 최종 목표 (사용자 2026-10-21)

**사용자 기기(폰·PC) 안에서만 도는 앱(APK·EXE)에 창작 AI를 넣는다.** 사용자가 프롬프트를 넣으면 그 AI가 애니메이션을 만들어 .sfa 파일로 내보낸다. Claude 같은 서버 모델이 아니라 기기 안에서 돌아야 한다.

- 입력 방식: NAI식 태그, 자연어 설명, 스토리보드 업로드 등 여러 가지
- 지금까지의 분석(SFA 형식·렌더링, 요소 트리·순위, 번역 규칙, 임팩트, 동작)은 그 AI의 지식(작곡 규칙·파라미터)이 된다.
- Claude 제안 구조(미확정)
  - ① 입력 이해: 태그는 규칙 변환, 자연어는 기기용 소형 언어 모델, 스토리보드는 소형 비전 모델
  - ② 작곡기: 동작·이펙트·연출 문법. 처음에는 규칙과 파라미터, 나중에는 소형 동작 생성 모델
  - ③ SFA 작성기
  - ④ 미리보기: 기존 SfaViewer 재활용
- 단계안
  1. 태그 → 1대1 육탄전 .sfa (규칙 기반, 모델 훈련 없음)
  2. 이펙트·연출 추가
  3. 자연어(소형 모델 탑재)
  4. 동작 생성 모델 훈련
  5. 스토리보드 입력
- **허가(2026-10-21 사용자):** AI 연결과 모델 학습을 모두 허용한다. 첫 플랫폼은 APK이고, 개인용이다(공개 배포 아님).
- 공개 배포를 하면 학습 원본 프레임을 앱에 넣지 않는다(추상화한 규칙·수치만 넣는다). 탑재 모델의 라이선스를 확인한다.

- **MVP 결정(사용자 2026-10-21, 아직 시작하지 않음):**
  1. 대상 기기: 갤럭시 Z 폴드4(안드로이드 16)
  2. 막대 인간: 앱 기본 비율이 마음에 들지 않아 따로 만든다(전용 리그 설계).
  3. 앱 설정: 총 길이, T(tween_fps), F(playback_fps)를 사용자가 정한다. 출력은 5초마다 끊어 여러 .sfa 파일로 준다.
  4. 첫 범위: 태그 `1v1`만 쓴다.
     - 맨손 캐릭터 둘, 도구·배경 없음
     - 격투 방법은 자유(발차기·구르기 등)이고, 학습한 것을 토대로 만든다.
     - 육탄전에 꼭 필요한 이펙트를 포함한다. 나머지는 나중에 추가한다.
  5. 환경: 사용자는 모바일만 쓴다. PC가 없으므로 학습·가공은 Claude 서버에서 한다.
  6. 첫 시험: 배경 없이 스틱맨 둘이 1v1 육탄전 하는 결과를 만들어 품질을 확인한다.
  7. 리그는 시안 A(머리 1 : 키 6.5, 균형형)로 정했다. 시안 그림은 scratch의 `rig/rig2.py`로 다시 만들 수 있다.
  8. 뼈대 재료
     - 나카무라 186개: **완료(2026-10-21, Colab T4, yolo11m-pose, 모든 프레임).** 결과는 Drive `AI-sfa/02_분석자료/포즈_claude/nakamura_pose_yolo11m.zip`(Claude가 볼 수 있는 백업, 8.9MB)이다.
       - 186파일, 118,176프레임. 사람이 검출된 프레임은 44.9%다(영상별 중앙값 0.43, 0.2 미만 영상 36개, 0.6 이상 46개). 한 프레임에 1명 41k, 2명 9.3k이고, conf 중앙값은 0.69다.
     - nian41 48개: **완료(2026-10-21, Colab, yolo11m-pose).** Drive `AI-sfa/02_분석자료/포즈_claude/nian41_pose_yolo11m.zip`(4.4MB). 48파일이 목록과 일치한다.
       - 55,828프레임, 사람 검출 46.5%(영상별 중앙값 0.46, 0.2 미만 10개, 0.6 이상 12개). 한 프레임에 1명 20.4k, 2명 5.2k, 3명 이상 356.
  9. 이펙트 세기는 타격 세기에 따라 단계를 둔다(가벼움: 스미어·속도선 / 중간: + 타격 섬광·먼지 / 결정타: + 임팩트 프레임·충격파).
  10. **SFA 크리에이터 v0.1(2026-10-21, 사용자 요청으로 시작):** `creator-android/`, 설명 `docs/SFA-CREATOR-2026-10-21.md`. 태그 1v1 → 기기 안에서 안무·이펙트 생성 → 5초 단위 SFA 저장. 학습 자료는 `tools/motion_lib.py`(nian41 펀치 자세 53개 + 나카무라 타이밍)이고 모델 학습은 아직 아니다. APK·샘플 영상은 Drive `07_도구/SFA크리에이터/`. 휴대폰 설치·Stick Fighter에서 열기는 사용자 확인 대기.
  11. **이펙트 원칙(사용자 재지시):** 이펙트는 학습한 형태를 '수학 함수로 그린 아이젠' 방식(구간 제한 포물선 조각 = SFA 2차 베지어)으로 그린다. 원·직선 기본 도형으로 대신하지 않는다. 투명도(알파)로 그라데이션·색 겹침을 적극 쓴다. AGENTS.md '이펙트 그리기 원칙'. 사용자 지적: v0.1의 고정 구도·평면·어색한 포즈도 고칠 대상(카메라 통계 → 3D 올리기 → 연속 동작·발 고정 → 모델 학습).
  12. **중간 상태(2026-10-21, 사용자 지적 후):** `tools/effect_vectorize.py`(윤곽 → 포물선 조각, IoU 0.95–0.996)·`effect_library.py`·`effect_palette.py`로 나카무라 임팩트 장면 사전을 만들어 앱에 연결했다(assets/effects.txt는 gitignore, 저장소 금지). 사용자 판정: 덩어리를 찍어 붙이는 방식도 틀렸다. **다음 방향(사용자 확인 대기):** 사람이 그리듯 선 레이어(곡선 테두리) + 색 레이어 여러 장(바탕·그림자·밝은 면, 반투명 그라데이션) + 검은 배경 레이어로 그린다. 나카무라 컬러 이펙트를 색 영역별 테두리·칠로 따서 레이어 그림 사전을 만든다. 조각 수 제한(600·80)은 임의값이라 없앤다(깎인 장면 44/154프레임, 버린 덩어리 190/2741). 사용자 제공 돌 파편 영상(stone_cube_burst_4.mp4, 업로드 폴더)은 아직 미분석.
  13. **전체 학습 준비 계획(사용자 승인 대기 → 시작):** `docs/PREP-PLAN-2026-10-21.md`. 결정: 라이선스 무관·최고 품질, 나카무라 관절도 몸 학습, 보충 애니메이터 이펙트 전부, 생성 시간 무제한, Colab GPU 사용, 사용자 요청 목록(Drive 권한 전체/읽기 재인증, Colab Pro 여부, HF 토큰은 Colab 비밀 값에만, 휴대폰 확인). VideoPose3D 가중치는 서버 scratch `vp3d/`에 받아 둠.

## 0. 현재 우선순위 (2026-10-21 저녁)

**전체 학습 준비 단계(P0–P6) — `docs/PREP-PLAN-2026-10-21.md`.** 사용자: "모든 걸 다 학습, 기존 학습 방식도 바꿔, 제한 두지 말고 최대한, Colab GPU 포함 모든 수단, 부탁할 건 전부 말해."

**P0 결과(2026-10-21 밤, 이 세션):**
- Drive 재인증 반영 확인: `RCLONE_GDRIVE_AUTH_B64`를 풀면 `{client_id, client_secret, token(문자열 JSON)}` 구조다(client_id·secret은 빈 값 → rclone 공용 client_id). `~/.config/rclone/rclone.conf`에 `[gdrive] type=drive, scope=drive.readonly,drive.file, token=…`으로 썼다. 옛 TOKEN 환경 변수는 이미 없다. tokeninfo 범위 = `drive.file drive.readonly`. 사용자 파일(Classroom·Takeout·Colab Notebooks·`02_분석자료/포즈/` 사용자 Colab 결과)이 보인다.
- 주의: rclone이 "공용 client_id가 2026년 중 중단된다"는 안내를 낸다. 중단되면 사용자 자신의 client_id(Google Cloud 콘솔 OAuth 클라이언트)로 다시 인증해야 한다.
- 복구(서버 scratch `data/`): 백업 tgz(autodet 265·CLIP 377·clip_score·fx·motion_lib), 포즈 zip 4개, 돌 파편 영상, 저용량 영상 377개(1.3GB), **원본 영상 354개**(nian41 48·optical-core 24·riooo 49·yukina 61·나카무라 디지털 172; 원본도 480p급).
- 사용자 Colab 나카무라 포즈(68개)는 Claude YOLO11m 결과(186개)의 부분집합이고 검출 프레임 수가 같다 → Claude 세트를 기준으로 쓴다.
- 자동 태그 남은 112개는 사용자 중지 결정을 유지했다(잠깐 재실행했다가 새 파일 없이 멈춤). 다시 돌릴지는 사용자 결정.
- CMU 모캡 전체(ASF/AMC 2514개, 4.2GB) 서버에 받음. 색인 `cmu/index.json`(설명·fps 2379개, 격투·점프·구르기 등 273개). `tools/cmu_amc.py`로 31관절 3D 좌표(미터, Y 위, 30fps) 변환(걷기 02_01 검증: 뼈 길이 변화 0, 발 높이 0.005m).
- P1 포즈 모델 비교 노트북: `tools/colab_p1_build.py` → `tools/colab_p1_pose_compare.ipynb`, Drive `Colab Notebooks/P1_포즈모델비교_colab.ipynb`에 올림. 표본 `data/p1/pose_compare_clips.json`(5명×영상4×연속32프레임×2 = 1280프레임). 모델: YOLO11x-pose, RTMW-x(133점), ViTPose+-H, Sapiens2-1B(308점), A100이면 Sapiens2-5B. 상자는 rtmlib HumanArt 검출기(그림·애니 포함 학습)로 통일. 서버 CPU에서 작은 변형으로 전 단계 실행 확인. 평가 `tools/p1_pose_eval.py`(검출률·떨림·좌우 뒤바뀜·합의도, 정답 없음).

- 추가 모캡(가입 불필요, 비상업 라이선스): Ubisoft LaFAN1 BVH 77개(격투 3·격투+스포츠 2·넘어졌다 일어서기 6·밀려 넘어짐 등, media.githubusercontent.com로 받음), Bandai Namco Research Motiondataset 3077개(감정·스타일별 몸짓 위주, 펀치·킥·베기 소수, git clone). `tools/bvh_pos.py`로 같은 npz 형식 변환(LaFAN1 걷기 검증: 키 1.62m, 뼈 길이 변화 0.00004m; Bandai는 고정 joint_Root→Hips 연결만 변함). github.com 압축 다운로드(archive·raw)는 프록시 403, git clone과 raw/media 호스트는 됨.
- P2 카메라 노트북: `tools/colab_p2_build.py` → `tools/colab_p2_camera_flow.ipynb`, Drive `Colab Notebooks/P2_카메라광류_colab.ipynb`. torchvision RAFT-large 광류 + 캐릭터 상자 가림 + 닮음 변환 RANSAC → 프레임별 [tx, ty, log_scale, rot, inlier, 중앙 흐름] + 9×16 흐름 격자. 원본 354개 전부, 흘려 읽기(최장 5540프레임). 합성 이동·확대 영상으로 서버 CPU에서 복원 확인(이동 기대 −0.0070 → −0.0064~−0.0077, 확대 log 기대 0.0099 → 0.008~0.011).

- 사용자 답(2026-10-21 밤): P1 노트북 실행함. Colab 유료 GPU(A100·L4) 못 씀·구매 불가 → **무료 T4 기준**으로 설계. AMASS 가입함 → `tools/colab_amass_build.py` → Drive `Colab Notebooks/AMASS_받기_colab.ipynb`(Colab 비밀값 AMASS_USER/PASS, download.is.tue.mpg.de POST; 잘못된 계정이면 401 확인. 파일 경로는 후보를 시도). SMPL-X 사이트 별도 가입 필요(안내함). Adobe 계정 있음 → Mixamo는 PC 브라우저에서 받는 방식이 필요(대기). 자동 태그 남은 112개 재개(사용자에게 설명, 반대 시 중지). HF 토큰은 필요할 때 안내.
- CMU 변환본 Drive 백업 `02_분석자료/모캡_CMU/cmu_npz30.tgz`(387MB) 확인. LaFAN1(276분)·Bandai(234분) 변환본도 Drive 같은 폴더 `mocap_lafan1_bandai_npz30.tgz`(223MB)에 백업(사용자 확인).

- P1 결과(2026-10-21 밤): 3모델 40구간 평가 — RTMW-x 검출 0.99·합의 0.73, ViTPose+-H 0.66·0.73, YOLO11x 0.46·0.67. 표본 그림 확인 결과 RTMW는 사람 없는 장면(상자 대체=전체 화면)에서도 거짓 뼈대를 그림 → **RTMW-x 선택(133점, 손·발 포함), 재추출은 대체 상자 없이 검출 상자만 + 시간 보간.** Sapiens2-1B는 T4 fp32에서 구간당 약 6분이고 첫 4구간 합의 0.36이라 제외.
- AMASS: 사용자 Colab이 Drive `02_분석자료/모캡_AMASS/`에 SMPL-X 모델 + ACCAD·HDM05·KIT·BMLmovi·BMLrub·EyesJapanDataset·Transitions·SFU(약 13.6GB) 받음(나머지 계속 받는 중일 수 있음). `tools/amass_joints.py`(관절 회귀+순운동학, 22관절, Y 위, 30fps; ACCAD 252개 검증) 서버 변환 중 → scratch `amass/npz30`.
- P2: v1은 초당 약 1프레임(검출기 CPUExecutionProvider). v2(검출 6프레임마다, RAFT 반복 6, 묶음 16, 나카무라·nian41 우선)는 영상당 약 130초(3~5fps, 전체 약 20시간). v3(정지 프레임 광류 생략 약 20%, 시간 내역 출력)는 Drive `P2_카메라광류_colab_v3.ipynb` — 세션이 끊기면 v3로 재개 안내함.

- Kaggle(주 30시간 무료 T4×2): `tools/kaggle_worker.py`+`kaggle_build.py` → Drive `07_도구/Kaggle/AI-sfa_P1P2_kaggle_v3.ipynb`. GPU0=P2, GPU1=P1 동시, Drive 직접 입출력(rclone, Kaggle 비밀값 RCLONE_GDRIVE_AUTH_B64), 끝난 영상 건너뜀. v1 문제: 두 작업자 rtmlib 모델 동시 다운로드 충돌(P2 실패), ONNX가 CPU(617프레임 426초). v3: 모델 미리 받기 + onnx2torch로 RTMW·YOLOX를 PyTorch GPU 실행(서버 대조 관절 차이 0). 사용자 v3 실행 중(2026-10-21 17:2x UTC~). P2 첫 결과 111284 정상(2218프레임, 정지 47%).
- Colab 무료 GPU는 사용량 한도 도달(2026-10-21 16:2x UTC). 풀리면 Colab에서도 P2 v4 병행 가능.
- 모캡 통합: `tools/mocap_unify.py` → scratch `mocap_unified/{cmu,lafan1,bandai,amass}.npz`(공통 18관절, 30fps), 목록 `data/mocap/mocap_index_2026-10-21.csv`(키워드 태그, 대략값). 합계 약 25.5시간(AMASS 변환 진행 중이면 다시 실행). Bandai 어깨 폭이 좁음 → 재타깃에서 표준 뼈대로 맞출 것.
- 포즈 정리: `tools/pose_tracks.py`(컷 나누기: HSV 상관 <0.55 또는 회색조 정규화 상관 <0.2·색 상관 <0.9 / 컷 안 헝가리안 추적 / 신뢰도·테두리·얼굴 클로즈업(얼굴 폭 >25% 화면) 점 제거 / 좌우 뒤바뀜·튀는 점·3프레임 이하 빈칸 / 멈춤 보존 / 추적별 사람다움 지표). 나카무라 6개로 시험: 놓친 어두운 컷(110822 f756) 수정, 클로즈업 거짓 몸 제거. 사람 추적(몸점수 3.23·비율 이탈 0.13) vs 괴물 오검출(1.84·0.50)로 구분됨 — **선별 기준(GPT T01 눈 검사 111추적, 2026-10-21 밤): 몸점수_중앙 ≥ 2.8(정밀 92%·재현 81%), 양이 필요하면 ≥ 2.4(84%·95%). 팔다리비 지표는 쓸모없음(AUC 0.48). 나카무라만 검사함.** GPT 판정 A45·B14·C17·D14·E21, 결과 `data/style_kb/ai_results/gpt_T01_2026-10-21.csv`(Codex 실행; Codex 환경은 비밀값이 도메인 제한 자리표시라 일반 환경 변수로 넣어야 했음).
- 동작 분류: 2D 규칙(`tools/pose_actions.py`)은 GPT T02(89구간, `data/style_kb/ai_results/gpt_T02_2026-10-21.csv`) 대비 일치 18% → 폐기 방향. GPT 분포: 대기 23·판단 불가 22·기타 10·이동 9·공격 8·점프 6·막기 4·쓰러짐 4·피격 3. 3D 분류기 1차(`tools/action_classifier.py`, 모캡 키워드 태그 약지도·관절거리 특징·로지스틱): 모캡 안 72.5%, **T02 37개 중 7개(19%)** — 5000단계 3D 모델의 흔들림(뼈 길이 CV 12%)을 '점프'로 읽음. 움직임 총량은 대기(0.007)·이동(0.046)·점프(0.128)를 가른다. 2026-10-22 재평가(10000단계, `data/p1/action_classifier_t02_eval_10k_2026-10-22.json`): 뼈 길이 고정(`lift_apply.py` 기본) 11/37, +5프레임 다듬기 10/37, 모캡 2·3프레임 유지 증강은 오판을 '점프'→'공격'으로 옮길 뿐(공격 재현 6/8, 대기→공격 16) — **모캡 약지도는 약 30%에서 막힘**. 다음: GPT T03(355장, 나카무라·nian41, `docs/GPT-PROMPT-T03-ACTIONS-2026-10-22.md`, Drive `00_목록/_GPT용_시트/T03_동작`) 정답으로 애니 3D 특징에 직접 학습(모캡 특징은 사전학습/보조), T02로 평가. Kaggle P1·P2 354/354 완료, 포즈_정리 354/354. 20000·35000단계 3D 모델(모캡 검증 MPJPE 38000단계 42mm)도 애니 떨림(0.035)·T02(9~10/37) 개선 없음 → 모캡 영역 밖(애니 2D 입력) 차이가 원인, 애니 정답(T03) 직접 학습으로 간다.
- 동작 분류 애니 직접 학습(`tools/action_anime_train.py`, GPT T03 355장): 8동작 T02 34/67(51%, 다수결 34%), T03 CV 51%. 공격 2/8·점프 0/6 약함 → GPT T04 401장(`docs/GPT-PROMPT-T04-ACTIONS-2026-10-22.md`, 능동 뽑기 `tools/action_active_pick.py`) 대기.
- **현재 우선(사용자 2026-10-22): 1v1을 잠시 미루고 이펙트·연출 먼저.** 순서 임팩트 섬광·폭발·연기·충격파·파편, **결과물은 캐릭터 없이 이펙트만.** 경과·수치는 `docs/P3-EFFECT-LAYERS-2026-10-21.md` 4차.
  - 재현: `tools/effect_clip_sfa.py`(층 분해 → SFA, `--mask`로 이펙트만). Drive `04_SFA시험작/이펙트_재현/`.
  - 분리: Kaggle `AI-sfa_P3_이펙트분리_kaggle_v3.ipynb`(Grounding DINO 2묶음 + SAM 2.1, 큰 상자·큰 물체 제외, 물체별 마스크 저장) → Drive `02_분석자료/이펙트_분리/*_v3.npz`. 구간 `data/p3/fx_segments_2026-10-22.csv`(157구간, 제작 자료 11구간 exclude). v1·v2 결과는 버림(파편 못 찾음 / 배경 통째).
  - 다음: 전체 v3 완료 → `tools/fx_timing.py`로 종류별 시간 변화 → `tools/fx_gen.py`(이펙트 생성기 시제품, Drive `04_SFA시험작/이펙트_생성/`) 가정값 교체, 대표 장면 이펙트만 SFA.
- **P6 본 학습 설계 초안** `docs/P6-TRAINING-DESIGN-2026-10-22.md`(사용자 확정 전): 동작(VQ-VAE+소형 GPT, 모캡 사전학습→애니 미세조정)과 타이밍 층(그림 유지)을 나누는 구조, 평가 표, 기기 변환. 3D 올리기 60000단계 완료(떨림 0.034, 3D 특징 RF T02 38/66).
- **PC판 1v1 생성기+뷰어 v1.1**(사용자 2026-10-22: 휴대폰 사용 어려움 → PC 사용): `viewer-windows/SfaCore/Gen`(안드로이드 생성기 C# 이식, Kotlin과 XML 일치 확인), Drive `07_도구/SFA뷰어/SfaViewer-win-1.1.zip`. docs/SFA-VIEWER-2026-10-20.md 끝. 실제 Windows 실행 확인 대기.
- P5 출력 시험 SFA(`docs/P5-SFA-OUTPUT-TEST-2026-10-22.md`, Drive `04_SFA시험작/P5_출력시험`): 곡선 경계 채우기·반투명 6겹·도형 600/2500 — 사용자 휴대폰 확인 대기.
- Mixamo 2157개 변환 완료(실패 0, 1.89시간, 태그 공격 342·걷기 292·달리기 184·점프 133·방어 44·피격 44) → 모캡 통합 20,385클립 약 68.7시간, Drive 모캡_통합 갱신. 학교 PC 3D 학습은 Mixamo 전 통합본으로 돌고 있다(다음 학습부터 포함).
- 몸동작 타이밍: `docs/P1-STRIKE-TIMING-2026-10-22.md`(tools/strike_timing.py, nian41 손 계수 22간격 일치) — 두 작가 2s 바탕, 나카무라 3s+ 19%, 타격 정점 앞뒤 2~3프레임 유지·정점 이동 약 2배, 임팩트 직전 손발 속도 0.57배(표본 작음).
- 3D 올리기 학습: 학교 PC 1050 Ti(`tools/pc_setup.ps1`, 1000단계 약 7.3분, 검증 MPJPE 1000→149mm, 4000→80mm), 5000단계마다 Drive `02_분석자료/모델_3D올리기/lifter.pt`. 적용 도구 `tools/lift_apply.py`.
- Mixamo: 콘솔 스크립트 `tools/mixamo_console.js`(CSP 때문에 링크 클릭 방식), 사용자 학교 PC에서 받는 중 → rclone으로 `02_분석자료/모캡_Mixamo/`. 변환 `tools/mixamo_fbx.py`(bpy 5.0.1, Python 3.11 scratch `bpyenv`; 시험 FBX로 단위·축·뼈 길이 검증).
- P3 시제품: `tools/effect_layers.py`, `docs/P3-EFFECT-LAYERS-2026-10-21.md`(표본 ΔE 평균 3.9–10.7, 남은 문제 5개).

**다음 할 일:** 사용자가 P1 노트북을 돌리면 Drive `02_분석자료/P1_포즈비교/`를 rclone으로 받아 `p1_pose_eval.py` → 표본 그림 소수 확인 → 모델 선택 → 전체 재추출 노트북. 그동안 서버에서 CMU 변환 완료·격투 동작 정리, P2 광류·P4 돌 파편 측정 준비.

**사용자 확인 대기:**
- Colab: 사용자 계정(Google AI 최고 요금제 가족 구성원)은 A100·L4를 못 고른다. 가족 요금제는 Colab 혜택이 관리자 계정에만 있는 것으로 보인다. 관리자 계정이 사용자 소유인지, 아니면 컴퓨트 단위 구매($9.99/100)인지 답을 기다린다. 관리자 계정을 쓰면 rclone도 그 계정으로 다시 인증해야 한다.
- 보충 애니메이터(riooo·optical-core·yukina)의 몸 동작 포함 여부는 Claude 판단으로 '부족하니 포함'을 제안했다(사용자: 부족하면 포함하라). AMASS 가입, Mixamo 사용 여부 대기.
- Hugging Face 토큰: 필요할 때 Colab 비밀 값에만 넣도록 자세히 안내(대화에 붙이지 않음).

**준비 단계 순서:** P0 보존·환경(서버 scratch 자료 Drive 백업: autodet 26MB, CLIP npz 52MB, 포즈) → P1 몸(포즈 모델 비교·재추출, 정리, 3D 올리기, 분류, 발 접지; 실사 모캡 CMU/AMASS) · P2 카메라(광류) · P3 이펙트 그림(SAM 2 분리, 선·밑색·반투명 명암 층, DiffVG/LIVE 벡터화, 상한 없음) · P4 파편(사용자 돌 파편 영상 측정값: 19–21프레임 섬광, 22–71 비행·정지, 조각 66–74, 면 3색) → P5 SFA 출력 시험(레이어·배경색 무제한, 사용자 휴대폰 확인) → P6 학습 설계.

**앱:** `creator-android/` v0.1(APK Drive `07_도구/SFA크리에이터/`). 사용자 판정: 구도 고정·평면·어색한 포즈·도형 이펙트는 모두 틀렸다. 이펙트 사전 실험(`tools/effect_vectorize.py`·`effect_library.py`·`effect_palette.py`, assets/effects.txt는 gitignore)은 중간 단계이고, 새 방식(그림 과정 그대로)으로 바꾼다.

**백업(2026-10-21 13:17):** Drive `AI-sfa/02_분석자료/백업_claude/scratch_analysis_2026-10-21.tgz`(자동 태그·CLIP npz·clip_score·이펙트 사전·팔레트·motion_lib.json, 73MB), 돌 파편 영상 `AI-sfa/01_원본영상/사용자참고/stone_cube_burst_4.mp4`. 포즈는 `02_분석자료/포즈_claude/`, 저용량 원본은 `01_원본영상/_Gemini용_저용량/`. 새 컨테이너에서는 여기서 받아 복구한다.

**이전 서버 scratch(새 세션에는 없음):** 원본 영상 `allvid/<animator>/`(377개), 포즈 `pose_nak`·`pose_nian`, 자동 태그 `autodet/autodet`, CLIP `clip/`, VideoPose3D `vp3d/`, 돌 파편 영상은 업로드 폴더 `c0406812-stone_cube_burst_4.mp4`. Android SDK `/opt/android-sdk`, skia·scikit-image·playwright 설치(새 컨테이너면 다시 설치).

## 1. 사용자 결정 (2026-10-20 밤)

- **셀 폐기:** 셀 70개, 믹스 10개, 그리고 셀처럼 보이는 초기 디지털 28개(라제폰 15, 울프스 레인 7 등)를 폐기했다. 소울 이터(2008) 1개만 유지했다.
  - 기록: `cel_decision`, `source_format`(era='셀느낌'), `impact_classify`(맞음 11행 training=제외)
  - Drive: `01_원본영상/_폐기예정(셀·믹스)/`로 옮겼다. 지우지 않았다.
  - 대상은 디지털 377개다(나카무라 186개).
- **구작/신작:** 연도로 나눈다. 구작 2004–2011년 84개, 신작 2014–2026년 96개, 경계 2012–13년과 미상 6개.
- **점수:** 나온 시간(초) × 화면 비중(주인공/배경). 나카무라 점수는 √(구작 비율 × 신작 비율)이다(등비중항). 한쪽이 0이면 영상 1개분의 작은 값을 넣고 '구작 전용' / '신작 전용'으로 표시한다.
- **트리 범위:** 일반적으로도 거의 안 나오거나 안 쓰는 요소까지 뻗지 않는다. 우리 자료 0회이고 일반 빈도도 낮으면 접는다.
- **신뢰도:** 결과에 요소별 자동 탐지 신뢰도를 함께 적는다. 약한 요소는 눈으로 확인한다. 이때 예상 토큰을 먼저 알린다.
- **동반 구조(나중 사용):** 부모 태그를 적으면 자식이 조연으로 따라오고, 자식 태그를 적으면 그 자식이 주인공이 된다.
  - 집계할 때 동반확률(부모 장면에서 자식이 나온 비율)을 함께 계산한다.
  - 동반조건과 '위로 필요' 칸은 순위가 나온 뒤 초안을 만든다.
- **메카 보류(사용자 2026-10-21):** 메카(로봇·메카와 그 하위 6개)는 일단 빼고 나중에 추가할 수 있다. `tools/element_rank.py`의 HOLD에 들어 있고, 순위에서 빠져 '보류'로 남는다.
- **방향(사용자 2026-10-21):** **올라운더**다. 무엇이든 만들 수 있게 넓게 채우되, 주로 만들 것은 현대판타지다.
  - 필요도 초안(`tools/element_rank.py` NEED_CAT·NEED_EL): 모든 분류 기본은 중간(2)이다. 원소 이펙트·충격·파괴·연출은 높음(3)이다.
  - 현대판타지 핵심 요소(맨손·검·총·단검, 괴물·유령·촉수·거대 생물, 도시·건물·실내·폐허)는 높음으로 올렸다. '낮음' 예외는 두지 않는다. **사용자 확정(2026-10-21).**
- **보충자는 준비만(사용자 2026-10-21):** 보충 출처(이웃 컷·고수·프리렌·3D)는 후보·목록·양식까지만 준비한다. 다운로드·시험·승낙 요청 같은 실행은 하지 않는다.
- **2차 움직임·장비·의상(사용자 2026-10-21):** 나중에 추가 학습한다. 지금은 준비만 한다. 순위에서는 HOLD로 '나중 학습(준비만)'이다.
- **2004–05년 셀 느낌 22개(사용자 2026-10-21):** 확인하지 않고 넘어간다. 디지털 대상에 그대로 둔다.
- **임팩트 프레임 중요도(사용자 2026-10-21):** 따로 정하지 않는다. 예전 답은 질문에 맞춰 한 말이었다. 완성도 기준의 학습 자료 순위(`docs/PRIORITY-TIERS-2026-10-20.md`)는 그대로 유지한다.
  - 302394를 낮음으로 둔 이유는 '나카무라 임팩트 프레임 가운데 디테일이 가장 떨어져서'다.
- **4:3 영상(사용자 2026-10-21):** 폐기하지 않고 그대로 둔다(검토 결과: 나카무라 구작 84개 중 38개가 4:3).
- **미정(사용자에게 다시 물을 것):**
  - 필요도 가중. 큰 분류 9개에 높음/중간/낮음을 매기는 것이다. 정하지 않으면 모두 같은 비중으로 계산한다.
  - 2차 움직임(망토·머리카락)과 장비·의상을 순위에 넣을지.
  - 2004–05년 디지털 22개가 셀처럼 보이는지 사용자가 확인할지.

## 2. 진행 상태

| 항목 | 상태 |
|---|---|
| 판정 | Claude 124개(`action_counts/`), GPT G01–G04·G07·G08, **G13(nian41 3)·G14(optical-core 8)**, **G15–G17(판정만 있던 나카무라 49·nian41 6의 배경·사물·연출, 이름:초:주/배)** (`ai_results/gpt_G*.csv`). GPT 프롬프트: `docs/GPT-PROMPT-G13-G14-2026-10-21.md`, `docs/GPT-PROMPT-G15-G17-2026-10-21.md` |
| 자동 탐지 | 377개 중 **265개**(사용자 지시로 중지, 남은 112개는 판정으로 대체). 결과 Drive `AI-sfa/02_분석자료/자동탐지/autodet_265.tgz` |
| 채점 | `tools/auto_calibrate.py` 수정 완료: 시간 비율(확률 평균), 흑백은 cv 지표(AUC 0.70), 정답원 all/gpt/claude 분리. 결과 `data/style_kb/auto_detect/calibration_*_2026-10-21.csv` |
| 요소 집계 | `tools/element_aggregate.py` → `element_aggregate_2026-10-21.csv`. 377개 전부(탐지·판정 합집합, 판정 어휘는 TERM으로 트리에 대응) |
| 순위 초안 | `tools/element_rank.py` → `element_rank_2026-10-21.csv`, 보고서 `docs/ELEMENT-RANK-DRAFT-2026-10-21.md`. 육안 보정 후 충분 67 / 보충 필요 78 / 공백 88 / CLIP 대기 91 / 접기 4. 신뢰도 약함 184 |

## 3. 다음 할 일 (순서)

보충 계획 `docs/SUPPLEMENT-PLAN-2026-10-21.md`(층 구조·단계·분업)를 따른다. 0단계(출처 대장 `data/style_kb/supplement_ledger_2026-10-21.csv`, 들이는 절차 §5 승낙 양식)는 끝났다.

1. **GPT 공백 확인 H01–H04 결과 받기:** 프롬프트는 `docs/GPT-PROMPT-H01-H04-2026-10-21.md`(A·B 두 창)이다. Codex가 rclone으로 Drive에서 받아 보는 방식으로 돌리고 있다. 2026-10-21 오전 기준으로 H03·H04는 94개 중 17개 완료, 11개 부분, 66개 미검토이고, GPT 사용 한도 때문에 12:39 이후 재개된다. 재개할 때는 '10개씩 끊어서' 지시를 쓴다.
   - 결과는 `ai_results/gpt_H0N_2026-10-21.csv`로 저장한다. 부분·미검토 행은 저장하지 않거나 특이사항에 '열람불가'로 둔다.
   - **완료(2026-10-21 밤):** 마지막 7세션 전부 반영, 저장 **186/186**(H01 46, H02 46, H03 47, H04 47). 겹침·중복 없음, 근거 `evidence/gap_last_s1–s7_*`. CLIP 재보정 결과: 보정 요소 101→126, AUC 중앙값 0.75→0.785, 0.75 이상 51→76(`clip_calibration_2026-10-21.csv` 갱신). 자동 태그 377개 완료(사용자에게 재개 설명, 반대 없음) → element_aggregate(들여쓰기 오류 수정) → element_rank 갱신: 충분 59→128, 보충 필요 75→49, 공백 87→42, 미측정 88→90. 결과 `docs/ELEMENT-RANK-DRAFT-2026-10-21.md` 8절. 공백 지도 새 판 `docs/GAP-MAP-2026-10-21.md`(이전 GAP-MAP·ACTION-GAP은 기록용 표시). 자동 탐지 377 json은 Drive `02_분석자료/자동탐지/autodet_377.tgz`.
   - (과거) **2026-10-21 16:30 KST 현황:** 저장 122/186(H01 45, H02 31, H03 24, H04 22). GPT는 사용량 한도로 **18:32 KST부터** 다시 쓸 수 있다.
     - Codex가 Drive에서 받다가 403 RATE_LIMIT_EXCEEDED가 났다(rclone 공용 client_id).
     - 그래서 남은 영상을 파트별 zip으로 사용자에게 주었다. Codex에는 "Drive에서 받지 말고 첨부 zip을 써"라는 지시와 함께 첨부한다.
     - 남은 것: H03·H04 48개(167784·174312는 판정 정리만 남음), H01·H02 16개. 프롬프트는 `docs/GPT-PROMPT-H03H04-REST-2026-10-21.md`, `docs/GPT-PROMPT-H01H02-REST-2026-10-21.md`, 진행 기록은 `docs/GPT-H03-H04-PROGRESS-2026-10-21.md`.
   - `element_aggregate.py`(분류 칸 안에서 이름을 찾고, 열람불가는 뺀다)와 `element_rank.py`(측정상태·GPT_확인영상·GPT_나옴영상 칸)가 그대로 읽는다. 확인 목록은 `judge_lists/gpt_gapcheck_checklist_2026-10-21.csv`(166개)다.
2. **CLIP:** 임베딩(`tools/clip_embed.py`, ViT-B-16, 1초 간격, 전체 화면 + 2×2 확대)이 scratch `clip/`에서 돌고 있다. G15–G17 55개를 먼저 처리하는 순서다. 컨테이너가 재시작되면 죽으므로 이어서 다시 실행한다.
   - 점수는 `tools/clip_score.py`가 낸다. 기준 문장과의 차이를 요소별 z 점수로 바꾼다.
   - 1차 보정이 끝났다(`tools/clip_calibrate.py` → `data/style_kb/auto_detect/clip_calibration_2026-10-21.csv`).
     - 정답은 GPT G15–G17·H01–H04의 초 단위 판정이고, 임베딩된 165개 영상 기준이다.
     - 보정된 요소는 63개다. AUC 중앙값은 0.75이고, 0.75 이상인 요소는 33개다.
     - 사물·배경은 강하다(하늘 0.95, 산 0.97, 도시 0.87, 괴물 0.90). 연출은 약하다(원근 강조 0.33, 단색 0.39, 선화만 0.31, 임팩트 프레임 0.58).
     - 양성이 3–5개뿐인 요소가 많아 불안정하다.
   - **377개 전체 보정 결과(2026-10-21):** 보정된 요소 101개, AUC 0.75 이상 51개다.
   - **주의:** 태그·판정이 없는 '미측정' 88개(탄도 궤적·낙뢰·차원문·크레이터·벽 등)는 GPT 확인 목록에도 없어 정답이 없다. 그래서 보정할 수 없다.
     - 공통 임계로 세어 보면 88개 중 79개가 '충분'이 된다(객차 36·블랙홀 30 등). 요소별 z 점수에서는 임계를 넘는 프레임 비율이 어느 요소든 비슷하기 때문이다.
     - 그래서 적용하지 않고 '미측정'으로 둔다(사용자 C안, 2026-10-21). 다시 꺼내는 방법은 `docs/UNMEASURED-ELEMENTS-2026-10-21.md`에 있다.
   - CLIP 임베딩·점수 백업: Drive `AI-sfa/02_분석자료/CLIP/`(clip_emb_377_vitb16.tgz, clip_score_377.npz). 새 세션에서는 다시 만들지 말고 받아서 푼다.
   - 임베딩과 H01–H04가 끝나면 다음 순서로 다시 돌린다: clip_score → clip_calibrate → element_rank(세 번째 인자로 점수 npz). 그다음 ACTION-GAP·GAP-MAP을 다시 쓴다.
3. 끝난 것:
   - 이웃 컷 재고와 후보 348개(`docs/NEIGHBOR-CUTS-2026-10-21.md`)
   - 번역 규칙 초안과 검증 표본 54행(`docs/TRANSLATION-RULES-DRAFT-2026-10-21.md`)
   - 블라인드 시험 설계(`docs/BLIND-TEST-DESIGN-2026-10-21.md`)
   - 3D 라이선스 조사(`docs/3D-SOURCES-2026-10-21.md`)

   고수 후보 통계(`tools/master_candidates.py` → `data/style_kb/master_candidates_2026-10-21.csv`)는 수집 중이다(scratch `sakuga_cache2`에 캐시가 있다). 번역 규칙을 Claude가 직접 검증하는 일(시트 9장, 약 2–3만 토큰)은 사용자 승낙을 기다리고 있다.
4. 사용자 결정 대기: 필요도 가중, 2차 움직임·장비·의상 포함, 2004–05 셀 느낌 22개, 프리렌 승낙 범위, 고수 시험 다운로드 범위, 3D 사용 여부.

## 4. 환경

- **2026-10-21 밤 사용자: '약 1시간 뒤 1050 Ti 사용 가능'.** 용도 제안: Mixamo 일괄 받기(PC 브라우저 필요), 3D 올리기 학습(묶음 축소). 본인 PC/공용 PC 여부 확인 중(공용이면 토큰 남기지 않음).
- **사용자 PC GPU(2026-10-21 10:22 KST 기준 약 5시간 사용 가능, 일시적):** NVIDIA GTX 1050 Ti(VRAM 4GB), RAM 16GB, Windows. 사용자가 "지금 있는 상태"로 알려 둔 정보이고, 사용 지시는 아직 없다. 쓸 때는 공용 PC 여부와 토큰을 남기지 않는 규칙을 먼저 확인한다.
- **Drive:** rclone `gdrive:`. 환경 변수 `RCLONE_CONFIG_GDRIVE_{TYPE,SCOPE,TOKEN}`가 설정 파일보다 우선한다.
  - 2026-10-21 확인: 범위는 아직 drive.file이다(토큰 갱신 후 tokeninfo). 사용자나 GPT가 올린 파일은 안 보인다. Claude가 올린 파일(저용량 영상·autodet)은 보인다.
  - 사용자에게 재인증을 안내했다: `rclone authorize "drive" "eyJzY29wZSI6ImRyaXZlLnJlYWRvbmx5LGRyaXZlLmZpbGUifQ"`. 그다음 환경 변수 SCOPE=`drive.readonly,drive.file`과 새 TOKEN을 넣는다. 새 세션에서 `oauth2.googleapis.com/tokeninfo`로 범위를 확인한다(토큰은 출력하지 않는다).
- **Drive 자료:**
  - 저용량 영상: `01_원본영상/_Gemini용_저용량/<animator>/<post>.mp4`. 폐기 28개는 `_폐기예정(셀·믹스)/_저용량/`에 있다.
  - GPT용 시트: `00_목록/제미나이_동작종류/_GPT용_시트/G03–G12/` (`tools/gpt_sheets.py`)
  - 목록: `묶음목록_v3.csv` (저장소 `data/style_kb/judge_lists/gemini_action_batches_v3_2026-10-20.csv`)
- **서버에서 다시 준비할 것:**
  - rclone이 기본 설치돼 있지 않을 수 있다: downloads.rclone.org의 linux-amd64 zip을 받아 /usr/local/bin에 둔다.
  - 저용량 영상(위 Drive에서 rclone copy)
  - `pip install opencv-python-headless onnxruntime huggingface_hub`
  - WD Tagger: `~/.cache/huggingface/hub/models--SmilingWolf--wd-vit-tagger-v3`. 없으면 hf_hub_download로 받는다.
  - 탐지 목록: `data/style_kb/judge_lists/auto_detect_list_2026-10-20.csv`(377행, 남은 128개가 앞).
  - CPU 4코어 기준 영상 1개에 약 30초가 걸린다.
- **주의:**
  - 대기는 PID로 한다(`pgrep -f` 자기 일치 주의).
  - 백그라운드 대기는 최대 2시간이다. 컨테이너가 재시작되면 탐지가 죽는다. 이어서 실행하면 된다.

## 5. 대기 중인 다른 일

- SFA 뷰어 1.0 실기기 확인(`docs/SFA-VIEWER-2026-10-20.md`)
- 옛 `05_임팩트 프레임 재검사` 폴더 삭제(사용자 직접)

## 검증 상태

- 2026-10-21 밤 단위 테스트 23개 통과(`test_p1_pose_eval` 추가).
- 새 도구는 단위 테스트가 없고, 실행 결과로 확인했다.
  - `auto_detect`: 263개 정상 json
  - `gpt_sheets`: 시트 649개 업로드, 표본 1장 육안 확인
  - `element_tree`: 337행 생성
  - `element_aggregate`·`element_rank`: 377개 집계 실행, G15–G17 형식 검사(55행) 통과

## 규칙

- 토큰·키를 출력하지 않는다. 영상 원본·시트 이미지는 GitHub에 올리지 않는다.
- Drive 삭제는 사용자 승인 뒤에만 한다(이동은 가능).
- 판정자(Agent)나 이미지를 대량으로 볼 때는 먼저 토큰을 추정해 사용자에게 알리고 승낙을 받는다. 서버 작업도 무엇을 할지 먼저 설명한다.
- 사용자 대화와 문서는 한국어로 쓴다. 문서·aggregate 메타데이터 커밋은 상시 허가다.
