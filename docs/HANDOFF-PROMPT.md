https://github.com/twoapple08/AI-sfa 작업을 이어서 진행해 줘. 작업 브랜치는 `ccr-bccf15a6-d6ee46`이다. fetch 후 이 브랜치에서 계속한다(시스템이 다른 브랜치를 배정해도 사용자 지정이 우선).

읽기 순서: AGENTS.md → 이 문서 → docs/COORDINATION-PHASE2-2026-10-17.md(작업표가 현재 기준) → docs/STYLE-KB-ROOTS-2026-10-16.md. 주제 문서는 필요할 때만 연다. HANDOFF.md는 이전 AOT 분석 단계의 기록이다. 이전 인수인계 상세: docs/history/HANDOFF-PROMPT-2026-10-17-archive.md.

## 현재 우선순위

(나) 분석형 스타일 학습. Stick Fighter용 스타일 지식베이스를 만든다.
- **yutaka_nakamura:** 이펙트·배경·연출 + **머리카락·복장(옷자락·천) 표현·몸 움직임**(2026-10-18 추가: nian41만으로는 자료가 부족함). 얼굴·표정은 언급이 없어 제외로 둔다. 에반게리온 제외. 구작·최신작 공통 기법 가중.
- **impact_frames는 4B 연필 느낌만 학습하고 디지털은 제외한다(최중요).**
  - 임팩트 프레임의 정의: 흑백(반전)이 짧게 번갈아 바뀌며 번쩍이는 것. 흑백 처리가 이어지기만 하면 연출(`bw_direction`)이다.
  - 섞인 프레임은 비중이 큰 쪽으로 분류하고 '섞임(연필 우세)'처럼 표기한다.
  - 셀 시대(era 1999 이하)의 단색 섬광은 실제 빛을 비추는 방식이라 제외한다(`impact_frames_cel_light`).
  - 정지 일러스트·원화의 흑연 질감은 `pencil_texture_reference`(참고 전용)다.
  - 상세: docs/TAG-RULES-2026-10-17.md.
- **nian41:** 사람 몸 움직임이 메인이다. 머리카락·얼굴·복장 표현·이펙트·연출은 제외한다. 옷자락도 제외로 확정했다(2026-10-18). 머리카락·복장은 yutaka 자료로 보충한다. 규칙: docs/NIAN41-BODY-MOTION-2026-10-17.md.
- **승낙 작가(2026-10-18):**
  - yukina_kosaka: 이펙트·연출·연필 임팩트, 인체 제외.
  - riooo: 규모가 큰 전투씬의 이펙트·연출만. 인체와 불 이펙트 전부 제외.
  - optical-core: 이펙트·연출, 인체 제외.
  - 반려(원본 삭제됨): katsumi_ishizuka·sota_shigetsugu·isuta_meister.
  - 범위와 절차: docs/INTAKE-PROCEDURE-2026-10-18.md.
- 학습(모델 훈련)·AI 연결은 하지 않는다. 포즈 추론(YOLO11-pose, tools/pose_extract.py)만 허가됐고, PC방 실행은 연기됐다.
- 조정 권한은 Claude에게 있다(GPT·Gemini 역할 배정과 기록).

## 현재 상태 (2026-10-18, 작업 15·16 완료) [실측 수치]

- 작업표 1–16을 완료했다(docs/COORDINATION-PHASE2-2026-10-17.md).
- `data/style_kb/observations.jsonl` 378건(작업 15 편입 89건 포함). 편입분 관찰 문장은 Claude 단독 판독이다.
- 편입 3명 원본은 `01_원본영상/<작가>/`(presumed는 하위 `presumed/`)에 있다. 회차·연도 표: `data/sakuga/candidates/intake_step4_era_2026-10-18.csv`.
- `data/style_kb/tag_overrides.csv` 356행.
  - **impact_frames_pencil confirmed 52**: 기존 28 + 작업 15 사용자 판정 24.
  - `impact_frames_partial` confirmed 2(새 태그, 화면 일부만 임팩트).
  - 디지털 candidate 165, 연필 candidate 3(기존).
  - 판정 기록: `data/style_kb/impact_intake15_claude_2026-10-18.csv`, docs/IMPACT-PENCIL-CROSSCHECK-2026-10-17.md 끝 절.
- **판정 기준 정정(사용자):** 흑백 2치로 처리된 거친 손그림 결도 연필이다. 회색 중간톤이 없다고 디지털이나 보류로 보지 않는다(TAG-RULES 끝 절).
  - 400px 시트로 매긴 기존 디지털 candidate(GPT·Claude 11a/11b)에도 같은 오판이 있을 가능성이 크다.
- impact_scan은 무채색 문맥, 16프레임을 넘는 흑백, 일부 연필 프레임을 놓친다. 임팩트 태그 클립은 시트를 직접 본다.
- 302394(2026-03) 이후 작품에는 임팩트 프레임이 없다. 디지털은 비질란테(302394)뿐이고 나머지는 연필이다(사용자 결정 2026-10-18).
- yukina 연필 confirmed는 2015–2022 작품에 걸친다.

## 다음 할 일 (순서대로)

1. **임팩트 프레임 전체 재검사(진행 중).**
   - 개정 정의(TAG-RULES 끝 두 절): 흑백 강조 삽입이면 교대가 없어도 되고, 2프레임이어도 된다. **비질란테 302394만 디지털이고 나머지는 전부 연필이다.**
   - 대상: yutaka 영상 294 + 편입 117. 도구는 `tools/impact_scan2.py`, 드라이버는 scratchpad `v2run.py`(재개 가능).
   - 검출이 끝나면 후보 시트로 임팩트 여부만 판정한다(연필/디지털은 규칙으로 정해짐).
   - 그다음 tag_overrides의 연필 candidate 163행을 confirmed나 not_impact로 정하고, 새로 찾은 구간을 추가한다.
2. **기법 자료 수집(진행 중):** 이타노 서커스·쿠츠나 번개. docs/TECHNIQUE-ITANO-KUTSUNA-2026-10-18.md, 드라이버 scratchpad `techrun.py`(재개 가능).
   - 반려 작가 공동 태그 kutsuna 21건은 쿠츠나 학습용으로 받는다. 첫 실행에서 skipped로 남은 것은 done 폴더를 지우고 다시 돌린다.
   - 수집이 끝나면 클립별로 기법 구간을 찾고 관찰을 작성한다. 쿠츠나는 작업 15의 번개 관찰과도 대조한다.
3. **yutaka 인체 범위 추가 관찰(새 작업, 2026-10-18 범위 변경).**
   - 기존 yutaka 관찰 250건은 이펙트·배경·연출만 적었다.
   - 분석 297건의 contact sheet(Drive `02_분석자료/<post>/`)로 다음 항목을 보충 관찰한다.
     - 머리카락: 덩어리 분할, 흩날림 타이밍, 끝 처리
     - 복장: 옷자락·천의 펄럭임, 뒤따름(follow-through)
     - 몸 움직임: 원화 포즈 간격, 1s/2s, 스미어, 무게 이동
   - nian41 규칙(docs/NIAN41-BODY-MOTION-2026-10-17.md)과 같은 항목명을 써서 비교할 수 있게 한다.
   - 포즈 추론(YOLO11-pose)을 하게 되면 yutaka도 대상에 넣는다.
   - 보류였던 옷자락 기록 216075·216079·216085는 nian41 클립이라 제외로 확정했다.
4. 우선순위 낮음:
   - 11b 확인 대기 구간(경계 20곳)
   - 프레임 번호가 없는 태그 보정 행
   - PC방 포즈 추론

## 향후 계획 (사용자 2026-10-18, 미착수)

현재 단계가 끝난 뒤에 한다. 상세: docs/FUTURE-PLAN-2026-10-18.md.
1. 캐릭터 디자인(파일·사진)을 주면 그 캐릭터를 등장인물로 만든다.
2. BGM 파일과 분량·타이밍을 주면 음악에 맞춰 애니메이션을 만든다.

## 환경·자료 위치

- **Drive:** rclone `gdrive:` remote를 환경 변수 RCLONE_CONFIG_GDRIVE_{TYPE,SCOPE,TOKEN}로 쓴다.
  - 범위가 drive.file이라 GPT가 올린 파일은 rclone으로 안 보인다.
  - 공개 폴더 https://drive.google.com/drive/folders/1M8Fk05crDvs42R9Eqt7FdJv2fPSiX8Xy 를 `embeddedfolderview?id=`로 나열하고, `drive.usercontent.google.com/download?id=..&export=download&confirm=t`로 받는다.
  - 공용 client_id 폐지 예정 경고가 있다.
- **rclone 설치:** 새 컨테이너에는 rclone이 없을 수 있다. 공식 릴리스를 받아 SHA256을 대조한 뒤 설치한다(서버 분석 도구 복구 허용 범위).
- **Drive 구조 `AI-sfa/`:**
  - 00_목록: catalog, manifest, 연도표, 분할표.
  - 01_원본영상: yutaka GPT ZIP(`yutaka_tagged_reference_NNN.zip`, 목록 00_목록/GPT-YUTAKA-ZIP-CONTENTS-2026-10-17.csv), nian41 48개, `_후보검토/{yukina_kosaka,riooo,optical-core}/{tagged,presumed}`.
  - 02_분석자료/연필보류_12구간: 사용자 판정용 원 해상도 묶음(판정 완료).
  - 02_분석자료: `<post>/contact_sheet.jpg,timing.json`, `impact/<post>/f시작-끝.jpg`, `impact_candidates_*.csv`.
  - 03_스타일지식베이스: 문서, observations, tag_overrides, impact_reference.
- **원본 확인:** Sakugabooru 공개 URL `https://www.sakugabooru.com/data/<md5>.<ext>`에서 임시로 받고 확인 뒤 지운다. md5는 catalog.csv 또는 후보 manifest에 있다.
- **도구:** tools/sakuga_timing.py(`--run S:E` 연속 시트), tools/impact_scan.py, tools/sakuga_collect.py, tools/pose_extract.py, tools/intake_step4_era.py(편입 회차·연도).
- **ffmpeg 반복 실행 주의:** `while read` 반복문 안에서 ffmpeg/ffprobe를 쓰면 표준입력을 가로챈다. `-nostdin`이나 `</dev/null`을 붙이거나 Python subprocess(stdin=DEVNULL)를 쓴다.
- **Wikipedia API:** 서버 IP가 429로 막혀 WebFetch로 원문을 확인했다.
- **서버 임시 폴더(scratchpad)는 새 세션에 없다.** 필요한 시트는 Drive 02에서 다시 받는다.

## 검증 상태

- `python -m unittest discover -s tests -v` 통과(마지막 실행 2026-10-18, 작업 15 반영 후).
- 모든 시각 판독은 [추론]이고 timing.json 수치는 [실측]이다. 하위 에이전트 단독 판독은 `cross_check`에 표시돼 있다.

## 규칙

- 토큰·키를 출력하지 않는다.
- 영상 원본·contact sheet·남의 작화는 GitHub(공개)에 올리지 않고 Drive에만 둔다.
- Drive 삭제는 사용자 승인 후에만 한다.
- 자동 승인 거부·로그인/위험 제어 차단은 우회하지 않는다.
- 사용자 대화와 문서는 한국어로 쓰고, 중간 진행 안내도 한국어로 쓴다.
- 문서·aggregate 메타데이터 커밋은 상시 허가돼 있다.
- 혼자 가능한 일은 자율 진행한다. 표를 갱신할 때 완료 행은 선행 조건·상태 칸 모두 **완료**, 진행 중 행은 선행 조건 칸에 **진행 중**으로 적는다.
