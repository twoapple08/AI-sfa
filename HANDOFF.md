# AI-sfa 현행 인수인계 — 2026-10-27 밤

이전(10-27 낮까지: 오전 '벡터 자료집' 방향, ProPainter 배치, 기준작 A, 환경 상세): docs/history/HANDOFF-2026-10-27-day.md. 새 대화 시작 문구: docs/HANDOFF-PROMPT.md.

## 현재 우선순위
**1단계 = 나카무라 이펙트 '영상(픽셀)' 스타일 AI** (사용자 10-27 저녁 결정: "꼭 SFA로 하려고 하지 말고 먼저 나카무라 스타일을 따라 만드는 AI, SFA는 그다음"). SFA 변환은 2단계.
**공통 지시(10-27 밤)**: 사용자의 심판이 필요한 경우(GPT↔Claude 합의 실패, 측정으로 못 가르는 눈 판정·취향·방향)는 쟁점·양쪽 근거·볼 장을 정리해 사용자에게 부탁한다. 현재 후보: s0177 6, s0194 6–9, s0149 17·27, s0299 41(GPT 답 뒤에도 갈리면).
합의: 방법을 바꾸기 전에 성공 기준·확인 날짜를 먼저 정한다. 제안 기준: 같은 프롬프트 LoRA 없음/있음 비교에서 사용자가 '나카무라 같다'고 보는 쪽이 LoRA에 확실히 많으면 계속.
GPT와 Claude는 각자 잘하는 일을 한다(AGENTS '다 GPT에 맡기지 말 것'). GPT = 시트 눈 판정·태깅, Claude = 측정·처리·검증·학습 준비·1차 평가.

## 바로 할 일 (다음 세션)
1. **GPT↔Claude 태그 토론 5차까지 진행**: 1–4차 docs/DEBATE-ROUND1~4-TO-GPT → **5차 docs/DEBATE-ROUND5-TO-GPT-2026-10-28.md**. 컷 합의·사용자 판정 끝. 저장소 태그 = GPT 5차본.
   조각 캡션: GPT가 경우 B 443조각 작성·수정(6차) → 저장소 `data/style_kb/ai_results/gpt_WINDOW_CAPTIONS_2026-10-28.jsonl`, 태그도 GPT 6차본. check 필수 오류 0. 경우 A 조건 보강(빠진 장 리듬)으로 경우 B 444조각 — s0031 0–28은 GPT가 채팅으로 준 한 줄을 합본 끝에 더함(Drive 파일엔 없음). **캡션 완료: check 444 필수 오류 0, 사실표와 1:1.**
   **학습 자료 재생성 완료(10-28 01:01 UTC)**: 275컷 → 482조각 11,410장(GPT 조각 캡션 444 + 컷 캡션 38), 검사: 태그 조각 길이 일치·캡션 조각 밖 번호 0·mp4 장 수/txt 일치·시트 위치 보정 off 0:267/1:8/2:2. wanlora.zip(97.7MB) 같은 Drive ID 덮어씀, **로그인 없는 공개 다운로드가 새 파일과 SHA 일치 → 공유 설정 문제 해결 확인**.
   **바로 할 일**: (a) 사용자 PC에서 `tools/pc_wan_lora.bat` 실행 → wan_out.zip 받으면 LoRA 없음/있음 1차 평가. (b) 사용자 지시 시 학습 자료 재생성 `tools/wan_lora_dataset.py <nk_src> data/style_kb/nk_shots_rough_2026-10-27.csv <OUT> --gpt <ALL+30 합본> --window-captions data/style_kb/ai_results/gpt_WINDOW_CAPTIONS_2026-10-28.jsonl`(원본 99편 scratch `nk_src`) → 검사 → wanlora.zip 같은 Drive ID. 사용자는 캡션 먼저 끝내길 원함(10-28). PC는 10-28 새벽 기준 약 4시간 뒤 가능하다고 함. (c) 남은 Claude 몫: `cutcheck` 영역 분리·내점 분포·재투영 오차.
2. **PC 영상 LoRA 시험**: `tools/pc_wan_lora.bat` 하나(설치 → 모델 14.5GB → Drive wanlora.zip → 캐시 → Wan2.1 T2V 1.3B LoRA → 비교 영상 → C:\aisfa\wan_out.zip). 토론 결과를 기다릴 필요는 없다(바뀌어도 몇 컷). 결과 오면 Claude가 LoRA 없음/있음 1차 평가 → GPT 2차 → 사용자 최종.
3. 앱 측정 대기(SFA 로딩 원인 가르기): `ink_12fps_slim10_alt.sfa` 로딩 시간 — 16초 근처면 '서로 다른 ID 수', 1:50 근처면 '앞 장과 ID 연속성'이 원인(docs/REF-SFA-FILE-BUILDER-2026-10-27.md 끝).

## 막힌 것
- 서버엔 GPU 없음, musubi-tuner 실행 시험은 자동 검토 거절(설정 해석기 파싱만 확인). PC 사용 가능 시간은 사용자에게 확인.

## 상태 (10-27 밤, 검증 범위 표시)
- **태그**: 277컷(시험 30 + b01–b17) 전부 v2. Claude 독립 검토(docs/REVIEW-GPT-SHOT-TAGS-2026-10-27.md)와 GPT 독립 검토(docs/GPT-REVIEW-SHOT-TAGS-2026-10-27.md, 71컷 보완)를 대조해 **GPT 검토본 채택**. 독립 일치: s0208 과분할 수정, 시험 30 재작성. 저장소 `data/style_kb/ai_results/gpt_SHOT_MOTION_ALL·_30_2026-10-27.jsonl`(GPT 원본 그대로), 검토 기록 `…_review_log_…`.
  GPT 검토본 결함: 고친 캡션 39개 숫자 앞 띄어쓰기 누락 → `caption_window.normalize`로 학습 자료에서만 정규화.
- **학습 자료**: `tools/wan_lora_dataset.py` → 274컷 → 17–33장(4N+1) 조각 479개 11,323장 512×288 24fps, 캡션 장 번호는 조각 기준(`tools/caption_window.py`), `frame_extraction="full"`·`max_frames=33`(musubi 설정 해석기로 확인). 검사: 조각 밖 번호 0, 붙은 숫자 0, 내용 빠진 조각 1, 첫 장–시트 일치 459/479(19 같은 그림, 1 애매) [서버 측정].
- **정정**: 'cv2 set(POS_FRAMES,a)는 a+1' 결론이 틀렸다(29컷 중 27컷 a 그대로). 시트 위치는 컷마다 측정(`sheet_offset`). 그 전 학습 자료는 266/274컷이 1장 밀려 있었다.
- **비교 프롬프트**: `tools/pc_wan_lora_run.py` PROMPTS 4개를 GPT 캡션 문체로.

## 확인된 사실 (SFA·앱)
- 앱은 소수점 글로우 값이면 글로우를 끈다 → 정수 [앱 확인]. 안 보이는 선은 색 알파 0.
- 서버 렌더러 `tools/sfa_render.py` ≈ 앱(평균 차 0.2–0.7) [앱 확인].
- **SFA 로딩**: 장마다 새 AO ID인 변환본 1:50 → 장 사이 ID 재사용 16초 [앱 확인], 앱 내보내기 영상도 원본과 같음 [앱 확인]. 사람 파일 ID 압축(47,677→26,693)은 1:34→1:31로 거의 효과 없음 [앱 확인] → '서로 다른 ID 수' 단독 원인설은 약해짐, '앞 장과 ID 연속성' 가설 시험 중(위 3). 변환기 출력은 장 사이 ID 재사용을 기본으로.
  도구: `sfa_slim.py`(겹쳐 칠하기 경계 단순화, 곡선 34%↓), `sfa_reuse_ids.py`(장마다 j번째 = 같은 ID, `--alternate` 시험), `sfa_pack_ids.py`(앱 제작 파일 ID 압축, 레이어별 순서 유지).
- 외부 스킬 sfa-file-builder 검토(받아갈 것 6·버릴 것): docs/REF-SFA-FILE-BUILDER-2026-10-27.md. 원문·결과물은 저장소에 안 넣음.

## 환경 (컨테이너 바뀌면 scratch 사라짐)
- 저장소 `/home/user/ai-sfa-pc`, 브랜치 `ccr-bccf15a6-d6ee46`(주) + 세션 배정 브랜치에 같은 HEAD 푸시. 시험: `python -m unittest discover -s tests` 23개 통과(10-27 밤).
- scratch(이번 세션): `/tmp/claude-0/-home-user/6f3d…/scratchpad`(nk_src 원본 99편, nk_shots/shots.csv, nk_sheets30·nk_sheets_all/b01–b17 시트, wanlora7 = 현재 학습 자료, gpt_merged.jsonl, fetch_any.py, musubi-tuner, venvpp = torch cpu) / `/tmp/claude-0/-home-user-ai-sfa/6f3d…/scratchpad`(slim·human SFA 시험, review/ 검사 스크립트·cut_metrics.csv, gpt_review/).
  없으면 Drive에서 복구: 원본 `01_원본영상/yutaka_nakamura_디지털/`, 시트 `02_분석자료/영상LoRA_컷/시트_전체/b01–b17`·`시트_시험30`, 학습 자료 `07_도구/PC_WanLoRA/wanlora.zip`, GPT 태그 폴더(공개) `1T2i1_QlI6D43pU4pS7TAJDtOg2uWw5us`(embeddedfolderview로 목록 → drive.usercontent 다운로드).
- (10-27 밤 2차 세션) `RCLONE_CONFIG_GDRIVE_TYPE·SCOPE·TOKEN` 있음, rclone은 기본 미설치 → downloads.rclone.org 바이너리 v1.75.2를 /usr/local/bin에 설치 → `rclone about/lsd gdrive:` 인증 성공(토큰 자동 갱신). 단 범위 drive.file이라 GPT 태그 폴더는 21개 중 4개(b01–b03·pilot30)만 보임 → GPT 파일은 계속 공개 링크(`tools/cutcheck_drive_ls.py`, drive.usercontent). rclone이 공유 client_id 폐기 예정 경고를 냄(2026 중 중단 가능).
- rclone `gdrive:`는 환경 변수 RCLONE_CONFIG_GDRIVE_*, 범위 drive.file(이 앱이 만든 파일만 보임). GPT가 올린 파일은 공개 링크로만.
- 렌더(skia)는 `apt-get install libegl1 libgl1`. 디스크 여유 작음.

## 보호
원본 영상·다른 작가 그림에서 뗀 형태·변환 결과 SFA/mp4·학습 자료·가중치·다른 사람 SFA/스킬 원문은 저장소에 넣지 않는다(Drive·scratch만). 토큰·키 출력 금지. Drive 삭제는 사용자 승인 후. 3D 금지, SFA 글로우 정수, 24fps 리듬 보존.
