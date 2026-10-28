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
   **바로 할 일(10-28 저녁 갱신)**: PC방 사용 불가 → **Kaggle 평가** `tools/kaggle_wan_eval.ipynb`(생성 `tools/kaggle_wan_eval_build.py`, 본문 `tools/kaggle_wan_eval_worker.py`): T4 x2, 모델은 HF·LoRA는 Drive `wan_out.zip`(공유 링크) 직접 받기, DiT·T5 fp16(T4 bf16 미지원) — 세기 1.0 묶음 먼저 생성해 검은 화면(NaN)이면 bf16으로 재시도, 나머지 3묶음(0.6·0.8·1.0+인물 빼기 부정)은 GPU별, T5 단계만 잠금(RAM). 결과 `wan_out_eval.zip`(영상 16 + 장 0·8·16·24·32 시트 + 나란히 재생) → Drive `02_분석자료/WanLoRA_평가/`(비밀값 있을 때) 또는 Output 탭. 서버 검증: 셀 문법·프롬프트 줄 파싱·비교 시트(기존 영상)만, GPU 실행은 미검증. **Kaggle 결과(10-28 저녁, 사용자 업로드 wan_out_eval.zip, scratch evalres)**: fp16 정상(검은 화면 없음), 3.0 s/it·영상당 약 75초, LoRA 병합 기록 확인. Claude 1차: ① 모든 세기에서 2D 셀 이펙트(검은 바탕·평면 주황/노랑 층·각진 파편·렌즈 섬광) ② p2(프롬프트 'mostly twos')에서 0.8·1.0이 장 변화가 한 장 걸러 크게 나는 2장 리듬(변화열 #-#-) — 학습 전은 없음, 타이밍 학습 첫 신호(측정: 연속 장 평균 화소차, 압축 때문에 완전 정지는 아님) ③ 인물: p2에서 모든 세기·인물 빼기 부정 프롬프트에도 남음(작아지기만) → 자료에서 인물 컷 제외가 필요 ④ 인물 빼기 부정은 p0·p3에서 형태를 흐리게 함 → 쓰지 않음 쪽 ⑤ p1 번개는 세기 무관 일반 청록 섬광으로 수렴(갈래 번개 사라짐), p0은 연기·회색 먼지 단계 없이 섬광만 커짐 → 프롬프트 순서 충실도 낮음 ⑥ p3 1.0은 가운데 점박이 공 잔상, 0.6·0.8은 흑백 임팩트 → 주황 방사로 프롬프트에 더 가까움. 잠정 기본 세기 0.8. **정정: 1판은 T5 fp16 탓으로 PC와 구도부터 달라(p1 화소차 87, p2 43) 판정 보류 → 2판 노트북(T5 bf16, PC 재현 확인 후 16개, 결과 wan_out_eval2.zip) 실행 대기. 토론 docs/DEBATE-WAN-EVAL-2026-10-28.md.** 다음 학습 준비 — **인물 조각 조사(10-28)**: `tools/person_scan.py`(애니 인물 검출 ONNX, 조각당 5장) → `data/style_kb/person_scan_wanlora8_2026-10-28.json`. 482조각 중 1군(인물 면적 10%↑·5장 중 3장↑) 109, 2군(크지만 1–2장) 89, 3군(작음) 16, 4군(확신 낮음) 89, 인물 없음 179. Claude 시트 대조: 1군 대부분 실제 인물(어두운 방·보라 연기 등 일부 오검출), 2군·화면 전체 상자는 이펙트 오검출이 절반가량. **캡션에 인물 낱말이 거의 없음(1군 109 중 4)** → `nkmr_fx`가 인물을 흡수해 기본으로 나오는 것이 유력. "no visible effects" 캡션 조각 45(1군 23). 안: ① 효과 없음 45 제거 ② +1군 제거(합 131) ③ 효과 없음 제거 + 인물 조각 캡션에 인물 낱말 추가(효과-몸 맞물림 보존). 사용자 판정 대기(시트 scratch `pdet/sheets`). 이전 기록: (a) 사용자 PC에서 `tools/pc_wan_lora.bat` 실행(Drive 사본 ID `1e6Mo7J_g5Ya0c9gR3OqxuHUOkrBnfUog`, 공개 직접 다운로드 `drive.usercontent…&confirm=t` 원본과 일치 확인) → wan_out.zip 받으면 LoRA 없음/있음 1차 평가. 첫 실행은 기존 설정 그대로(10-28 사용자 결정, 시간 자동 계산안은 사용자 취소·되돌림). **첫 실행 결과(10-28 16:28)**: 학습 3,000스텝 완료·LoRA 저장(wan_out.zip, Drive 사용자 링크 `1NnqoIsJ94lH-_2u4ofeHCduhhWgXC0lv`, scratch에 받음). 그러나 비교 영상 LoRA 있음/없음이 바이트까지 같음 → 원인: ComfyUI 재포장 DiT 키 접두사 `model.diffusion_model.` 때문에 생성 때 LoRA 키 900개 전부 미사용(musubi lora_utils 생성 병합은 원 키 기준). 수정: `merge_ready()` 키 이름 변환(서버 모의 300/300 일치, 데이터 동일) + `--samples-only`·`tools/pc_wan_samples.bat`(Drive ID `1c1S-i6Gg1aRkENuDzmwDGm9kAwRcJe0d`). **LoRA 적용 비교 영상(10-28 16:47, wan_out_samples.zip Drive `1GkoFDUODE2Jfwz8f-touKkbv9pis_PyR`)**: 키 변환으로 미사용 경고 0, p1·p2만 생성(p0·p3은 허깅페이스 연결 끊김 → 재시도·건너뛰기 추가 dc73c88). **Claude 1차 평가**: 실사·3D풍(LoRA 없음) → 2D 애니메 셀 채색 이펙트로 확실히 이동(p2 먼지: 평면 갈색 + 짙은 갈색 덩어리 명암, 하늘·땅 애니 배경 / p1 번개: 청록·흰 번짐과 장마다 깜빡임). 문제: ① 학습 자료에 인물 컷이 섞여 p2에 녹색 인물이 생김(프롬프트에 없음) ② 형태가 흐릿·뭉개짐(나카무라의 각지고 또렷한 윤곽 부족) ③ 프롬프트 충실도 낮음(p2 상자 굴러감 사라짐). **사용자 판정(10-28): "느낌 있어 엄청" → 1단계 방향 성공, 계속 진행.** 후보: LoRA 세기 0.6–0.8, 중간 저장본 비교, 부정 프롬프트(character, person), 인물 컷 제외·가림 후 재학습. **첫 실행(10-28 오후, 사용자 PC방 5060)**: 설치·다운로드 정상(허깅페이스 연결당 약 3.5MB/s → `tools/t5_fast.bat` 4갈래로 T5 약 15분), 잠재 캐시 약 2.5초/조각. 학습 1차는 cp949 콘솔에서 일본어 로그 UnicodeEncodeError로 즉시 실패 → `pc_wan_lora_run.py`에 PYTHONUTF8·캐시 건너뛰기·OOM일 때만 블록 교체 재시도(커밋 6950e67) → 재실행 학습 진행 중, **약 2.9 s/it**(512×288·33장·fp8·블록 교체 0, 손실 약 0.19), 170분 제한이면 약 3,000스텝(약 6에폭). 첫 결과의 s/it를 보고 다음 조정 후보: 조각 17장(스텝 약 2배) > 해상도↓ > checkpointing 끄기(OOM 위험). 서버에서 bat의 다운로드 주소 확인: python·PyTorch·모델 3개·학습 스크립트 응답 정상, musubi GitHub zip은 이 서버 프록시가 막음(PC는 무관). (b) 사용자 지시 시 학습 자료 재생성 `tools/wan_lora_dataset.py <nk_src> data/style_kb/nk_shots_rough_2026-10-27.csv <OUT> --gpt <ALL+30 합본> --window-captions data/style_kb/ai_results/gpt_WINDOW_CAPTIONS_2026-10-28.jsonl`(원본 99편 scratch `nk_src`) → 검사 → wanlora.zip 같은 Drive ID. 사용자는 캡션 먼저 끝내길 원함(10-28). PC는 10-28 새벽 기준 약 4시간 뒤 가능하다고 함. (c) 남은 Claude 몫: `cutcheck` 영역 분리·내점 분포·재투영 오차.
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
