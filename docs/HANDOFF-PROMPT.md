# 인수인계 (2026-10-19 밤 후반, 앞뒤 문맥 판정 추가·재검사 291 육안 재분류 뒤)

https://github.com/twoapple08/AI-sfa 작업을 이어서 한다. 작업 브랜치는 `ccr-bccf15a6-d6ee46`이다. fetch 후 이 브랜치에서 계속한다(시스템이 다른 브랜치를 배정해도 사용자 지정이 우선).

**2026-10-20 최신:** 임팩트 전수 분류를 끝내고 Drive `05_임팩트 프레임 분류/`에 올렸다. 결과·한계는 **docs/IMPACT-CLASSIFY-RESULT-2026-10-20.md**에 있다.
- 끝난 일:
  - 사용자가 애매 138건을 전수검사했다. 맞음 27, 아님 111이다.
  - 사용자가 "맞음은 전부 학습 자료"로 정했다.
- 다음 할 일 1: 중요도 순위를 정한다(사용자와 함께).
- 다음 할 일 2: 범위 밖 채점 표본 100개를 판정한다.
- 아래 1·2절은 10-19 기록이다.
- 옛 `05_임팩트 프레임 재검사` 폴더는 권한 403으로 못 지웠다. 사용자가 직접 지워야 한다.

**읽기 순서:** AGENTS.md → 이 문서 → **docs/IMPACT-CLASSIFY-RESULT-2026-10-20.md** → docs/IMPACT-CONTEXT-2026-10-19.md(문맥 판정·재분류 결과) → docs/GPU-1050TI-FILTERING-2026-10-19.md → 필요하면 docs/IMPACT-V2-CRITERIA-2026-10-18.md 4차·3차. 직전 인수인계: docs/history/HANDOFF-PROMPT-2026-10-19c-archive.md(문맥 문제 원문, 그 전 19b·19a).

## 0. 현재 우선순위

- **우선순위:** 임팩트 프레임 거르기의 정확도. 사용자가 전부 직접 검사하기는 힘들다고 했다. 모델 훈련은 허가되지 않았다(추론만 가능).
- 문맥 문제(32488 f120–122 눈 클로즈업이 임팩트로 올라옴): 사용자 지적은 원본 그대로 19c 보관본 0절에 있다.

## 1. 이번에 한 일 (2026-10-19)

| 항목 | 상태 |
|---|---|
| 문맥 판정 도구 | `tools/impact_context.py`. 후보의 면·선 색이 앞뒤(3–12프레임) '주된 그림 방식' 색표에 있는지 잰다. `same_style=1`이면 같은 컷 클로즈업·줌·동화 쪽(아님). 흑백 두 색 실루엣은 제외 |
| 검증 [실측] | 확정 임팩트 63 중 0, 육안 임팩트 89 중 0을 잘못 거름. 아님 47 중 8, 32488 f121–122는 '아님'. 보수적 규칙이라 같은 장면 유형 61 중 14만 잡는다 |
| A 31 회귀 [실측] | 사용자 아님·옆에실제 25 중 12가 자동 '아님'(문맥 7 + 아님유력 5). **13은 여전히 재검사**: 먼지·물·섬광 등 다른 색 이펙트라 색 비교로 안 걸림. 사용자 임팩트 4는 아님으로 안 감 |
| 재검사 291 재분류 [추론] | Claude 육안(앞 6·후보·뒤 6 띠): 임팩트 89, 아님 88, 단색섬광 64, 옆에실제 15, 애매 35. `data/style_kb/impact_recheck_claude_2026-10-19.csv`(메모·needs_user 열) |
| 시험 후 뺀 것 | X-CLIP 문맥 창+반대 문구(AUC 0.54), 면적 기반 지표, SIFT, 컷 경계 자르기 |
| 1050 Ti 거르기(**사용자 취소**) | 문서 `docs/GPU-1050TI-FILTERING-2026-10-19.md`, 한 명령 도구 `tools/impact_pipeline.py`(scan2→문맥→GPU X-CLIP→3분류, 단색섬광 분리, 이어서 실행). `impact_xclip.py`에 `IMPACT_DEVICE=cuda` 추가. 서버 CPU로 3영상 끝까지 시험 |
| 지표 파일 | `data/style_kb/impact_context_2026-10-19.csv`(515구간: 재분류 대상+확정 라벨) |
| tag_overrides | **아직 안 넣음**(사용자 확인 전) |

## 2. 다음 할 일

1. **사용자 확인 받기:** 재검사 291의 애매 35·옆에실제 15(구간 번호 고침 메모), 그리고 '임팩트 89'를 tag_overrides에 넣어도 되는지.
   - **Drive `05_임팩트 프레임 재검사/`로 재검사 폴더 289개를 옮겼다(사용자 지정 구조, 2026-10-19).** `재검사 결과:맞음`(88)·`재검사 결과:아님`(102, 옆에실제 15 포함)·`재검사 결과:애매`(99, 단색섬광 64 포함). 폴더 이름은 `<애니메이터>_<게시물>_<옛 분류>_f<구간>_<옛 번호>[(단색섬광)|(옆에실제)]`. 같은 곳에 읽어보기.txt·재검사_판정표.csv(drive_folder 열).
   - 통합 영상은 02 쪽 게시물 폴더에 그대로다. 02의 재검사목록.csv·판정표_전체.csv의 folder 열은 옛 위치라 맞지 않는다.
   - 승인되면 tag_overrides에 status=candidate, by=Claude(문맥 육안)로 넣는다.
2. **다른 색 이펙트(먼지·물·섬광) 구별:** A 13건이 남은 원인이다. 색 비교로는 안 된다. 후보:
   - 이펙트 종류 문구로 X-CLIP 재채점(후보만): 문맥 창 방식은 AUC 0.54였으니 반복하지 않는다.
   - '흑백 두 색 정도'(bilevel)를 점수 한 항으로 쓰기. 점검 결과 AUC는 육안 표본 0.82, 독립 표본(확정 63·47) 0.70이다. 연필 해칭 임팩트는 두 색이 아니라 단독 판정은 안 된다(IMPACT-CONTEXT 6절).
3. ~~1050 Ti 실행~~ — **사용자가 취소함(2026-10-19).** 사용자는 모바일 환경으로 돌아왔다. 다시 요청하기 전에는 GPU·PC 실행을 제안하지 않는다. 문서·`impact_pipeline.py`는 CPU에서도 돌아가서 남겨 둔다.
4. 재검사 분담안(Gemini 영상 판정 + Claude 띠 판정, 엇갈린 것만 사용자): 사용자 승인 대기. Claude 몫은 이번에 끝났다.
5. A 32–50번 19건 확인. 239055 f213은 재분류 띠에서 f212–215가 같은 흑연 해칭 실루엣으로 보였다.
6. 학습 형태 결정은 거르기가 안정된 뒤 다시 묻는다.

## 3. 학습 범위와 임팩트 규칙

(나) 분석형 스타일 학습. Stick Fighter용 스타일 지식베이스를 만든다.
- 모델 훈련·AI 연결은 하지 않는다.
- 포즈 추론(YOLO11-pose)만 허가됐고, PC방 실행은 연기됐다.
- 조정 권한은 Claude에게 있다.

| 대상 | 학습 | 제외 |
|---|---|---|
| yutaka_nakamura | 이펙트·배경·연출, 머리카락·복장(옷자락·천)의 움직임 표현, 몸 움직임 | 얼굴·표정(나중에 다시 검토), 캐릭터 그림체, 에반게리온 |
| nian41 | 몸 움직임(메인) | 머리카락·얼굴·복장·옷자락·이펙트·연출 |
| yukina_kosaka | 이펙트·연출·연필 임팩트 | 인체 |
| riooo | 큰 전투씬의 이펙트·연출 | 인체, 불(화염 자체). 마력 오라·폭발 섬광은 포함 |
| optical-core | 이펙트·연출 | 인체 |
| 기법 itano_circus | 투사체 무리 회피·추적 연출 | 에반게리온, 반려 작가 공동 태그 |
| 기법 kutsuna_lightning | 지그재그 번개 | 반려 작가 공동 태그 21건은 이 기법 학습용으로만 쓴다 |

- 반려(원본 삭제): katsumi_ishizuka·sota_shigetsugu·isuta_meister.
- 캐릭터 그림체는 어느 작가에서도 학습하지 않는다.

**임팩트 프레임 규칙(최중요)**
- 정의: 대개 흑백으로, 날카로운 선·실루엣·그림자 등 강조할 부분을 집중 묘사한 짧은 삽입이다.
  - 흑백 교대가 없어도 되고, 2프레임이어도 해당한다.
  - 밝은 상태로 실루엣이 이어지기만 하는 것, 앞뒤와 차이 없는 장면은 아니다.
  - Sakugabooru 위키: ショックコマ(쇼크 코마). 컬러 쇼크 프레임은 학습 범위 밖이다.
- **연필/디지털:** 비질란테(302394)만 디지털이고, 나머지 임팩트 프레임은 전부 연필이다. 흑백 2색으로 처리된 거친 손그림 결도 연필이다.
- **학습 사용(2026-10-20 사용자):** 판정이 '맞음'이면 연필·디지털 구분 없이 전부 학습 자료로 쓴다.
  - 중요도 순위는 나중에 정한다.
  - 302394의 임팩트는 기본 중요도 '낮음'이다.
  - 판정표 training·priority 열에 적었다.
- **색 포인트 임팩트도 맞음(2026-10-20 사용자):** 흰색·검은색 대신 한 색으로 포인트를 준 것.
- **판정은 한 장이 아니라 앞뒤 ±12프레임 연속으로 한다(2026-10-19).** 앞뒤와 이어지는 동화, 먼지·연기·충격파, 섬광, 집중선·고속 이동 배경, 옷이 화면을 가림, 물·전기 이펙트, 실루엣 연출만 빌린 장면은 흑백이어도 아니다(IMPACT-V2-CRITERIA 3차).
- 학습 비중: 실루엣·강조 없는 단색 번쩍임·수준 낮음·추구미 아님 = low, 추구미 전혀 아님 = exclude, 사용자 "반은 맞음" = borderline.
- 부분 임팩트(화면 일부만)는 `impact_frames_partial`로 따로 센다.
- 셀 시대(≤1999) 단색 섬광은 `impact_frames_cel_light`로 학습에서 제외한다.
- TV판에서 명도가 낮아진 임팩트(218857 등)는 학습할 때 밝은 흰색·검정 조합으로 변환한다.

## 향후 계획 (사용자 2026-10-18, 미착수)

현재 단계가 끝난 뒤에 한다. 상세: docs/FUTURE-PLAN-2026-10-18.md.
1. 캐릭터 디자인(파일·사진)을 주면 그 캐릭터를 등장인물로 만든다.
2. BGM 파일과 분량·타이밍을 주면 음악에 맞춰 애니메이션을 만든다.

## 환경·자료 위치

- **Drive:** rclone `gdrive:` remote를 환경 변수 RCLONE_CONFIG_GDRIVE_{TYPE,SCOPE,TOKEN}로 쓴다.
  - 범위가 drive.file이라 GPT가 올린 파일은 안 보인다.
  - 공용 client_id 폐지 예정 경고가 있다.
- **Drive 구조 `AI-sfa/`:**
  - 00_목록: catalog·manifest·연도표·색인
  - 01_원본영상: yutaka GPT ZIP, nian41, yukina_kosaka·riooo·optical-core(presumed는 하위 폴더), 기법_itano_circus·기법_kutsuna_lightning, `_후보검토`(반려 기록만)
  - 02_분석자료: `<post>/`(contact_sheet·timing), `impact/`(v1), `impact_v2/`, `기법/`, **`임팩트_재분류_2026-10-19/`(옛 사용자판정 A·B·C 통합, 아래 1절)**, 연필판정_작업15_28구간, 연필보류_12구간
  - 03_스타일지식베이스/참고_임팩트예시/: 사용자 예시 연필 임팩트 5장(공개 금지)
  - 03_스타일지식베이스: 문서·observations·tag_overrides
  - 05_임팩트 프레임 분류(2026-10-20): 전수 분류 3,247구간
    - 맞음/단색섬광·맞음/실루엣이미지·애매·아님 아래 애니메이터 폴더로 나눴다.
    - 판정표·연필 목록이 함께 있다.
    - 옛 05_임팩트 프레임 재검사는 남아 있다(drive.file 권한 밖 항목 때문에 403, 사용자 삭제 필요).
- **도구:**
  - tools/impact_scan2.py(개정 정의 검출), tools/run_impact_v2.py, tools/collect_technique.py(Drive 기준 재개, 둘 다 완료됨)
  - 판정 기준: docs/IMPACT-V2-CRITERIA-2026-10-18.md(하위 에이전트용 임팩트 판정 기준)
  - tools/make_judge_bundle.py(판정 묶음), tools/judge_context.py(문맥 시트·연속성 지표)
  - tools/impact_xclip.py(X-CLIP 추론, CPU 가능, IMPACT_DEVICE=cuda), tools/impact_narrow_classify.py(좁힌 정의 3분류)
  - **tools/impact_context.py(앞뒤 문맥 같은 그림 판정, IMPACT_CACHE로 프레임 캐시), tools/impact_pipeline.py(원본 폴더→final.csv 한 명령)**
  - X-CLIP 환경: 새 세션엔 없다. `python3 -m venv <dir> && <dir>/bin/pip install --index-url https://download.pytorch.org/whl/cpu torch torchvision && <dir>/bin/pip install transformers pillow numpy opencv-python-headless`(서버 복구 허용 범위). transformers 5.x는 get_video_features가 객체를 돌려주므로 `.pooler_output`을 쓴다(도구에 반영됨).
  - tools/sakuga_timing.py(`--run S:E` 연속 시트), tools/sakuga_index.py(태그 색인), tools/intake_step4_era.py, tools/pose_extract.py
  - tools/impact_scan.py(v1, 연필 누락이 있어 대체됨)
- **주의:**
  - 반복문 안 ffmpeg는 표준입력을 가로챈다(`-nostdin`, stdin=DEVNULL).
  - `pkill -f <이름>`은 그 이름이 든 자기 셸까지 죽인다. PID로 kill한다.
  - `until ! pgrep -f <이름>` 대기도 자기 셸 명령줄을 잡아 끝나지 않는다. `pgrep -f "python3 tools/<이름>"`처럼 좁히거나 PID로 기다린다.
  - rclone moveto를 병렬로 돌리면 같은 이름 폴더가 중복 생성된다. 끝난 뒤 `rclone dedupe --dedupe-mode rename <경로> --max-depth 1`로 병합한다(파일 삭제 없음).
  - `rclone lsf --include`로 셀 때는 `--files-only`를 붙인다.
  - Wikipedia API는 429로 막혀 WebFetch로 확인했다. YouTube는 oEmbed만 된다.
  - scratchpad는 새 세션에 없다.
  - **원본 복구:** 새 세션엔 원본이 없다. catalog·candidates_catalog의 md5로 `https://www.sakugabooru.com/data/<md5>.<ext>`에서 받아 md5를 대조한다(2026-10-19 162개 1.9GB 약 10분, 불일치 0). rclone은 공식 zip을 받아 설치한다. yutaka 원본은 drive.file 범위라 Drive에서 안 보인다.
  - 프레임 띠로 육안 판정할 때는 160x90 타일 3건씩 묶은 이미지가 한 장에 약 1,100토큰이다(291건 97장).
- **Sakugabooru 태그 위키(태그 옆 '?'):** `https://www.sakugabooru.com/wiki.json?query=<태그>`

## 검증 상태

- `python -m unittest discover -s tests -v` 통과(2026-10-19 밤 후반, 도구 추가 뒤 1회).
- 새 도구는 단위 테스트가 없다(cv2·torch가 서버 기본 파이썬에 없음). 515구간 실행·3영상 파이프라인 실행으로 확인했다.
- 시각 판독은 [추론], 지표·건수는 [실측]. X-CLIP 분류는 보정 표본 86구간 기준 수치이고 전수 검증이 아니다.

## 규칙

- 토큰·키를 출력하지 않는다.
- 영상 원본·contact sheet·남의 작화·사용자 예시 이미지는 GitHub(공개)에 올리지 않고 Drive에만 둔다.
- Drive 삭제는 사용자 승인 후에만 한다(이번 구간별 slow_quarter 삭제는 "중복 영상은 하나로 통합" 지시에 따른 것).
- 자동 승인 거부·로그인/위험 제어 차단은 우회하지 않는다.
- 사용자 대화와 문서는 한국어. 문서·aggregate 메타데이터 커밋은 상시 허가.
- 혼자 가능한 일은 자율 진행한다. 모델 훈련은 명시적 허가 전 금지(추론은 가능).
