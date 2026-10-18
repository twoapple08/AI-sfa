https://github.com/twoapple08/AI-sfa 작업을 이어서 진행해 줘. 작업 브랜치는 `ccr-bccf15a6-d6ee46`이다. fetch 후 이 브랜치에서 계속한다(시스템이 다른 브랜치를 배정해도 사용자 지정이 우선).

읽기 순서: AGENTS.md → 이 문서 → docs/COORDINATION-PHASE2-2026-10-17.md(작업표가 현재 기준) → docs/STYLE-KB-ROOTS-2026-10-16.md. 주제 문서는 필요할 때만 연다. HANDOFF.md는 이전 AOT 분석 단계의 기록이다. 이전 인수인계 상세: docs/history/HANDOFF-PROMPT-2026-10-17-archive.md.

## 현재 우선순위

(나) 분석형 스타일 학습. Stick Fighter용 스타일 지식베이스를 만든다.
- **yutaka_nakamura:** 이펙트·배경·연출. 에반게리온 제외. 구작·최신작 공통 기법 가중.
- **impact_frames는 4B 연필 느낌만 학습하고 디지털은 제외한다(최중요).**
  - 임팩트 프레임의 정의: 흑백(반전)이 짧게 번갈아 바뀌며 번쩍이는 것. 흑백 처리가 이어지기만 하면 연출(`bw_direction`)이다.
  - 섞인 프레임은 비중이 큰 쪽으로 분류하고 '섞임(연필 우세)'처럼 표기한다.
  - 셀 시대(era 1999 이하)의 단색 섬광은 실제 빛을 비추는 방식이라 제외한다(`impact_frames_cel_light`).
  - 정지 일러스트·원화의 흑연 질감은 `pencil_texture_reference`(참고 전용)다.
  - 상세: docs/TAG-RULES-2026-10-17.md.
- **nian41:** 사람 몸 움직임만. 표정·그림체·머리카락·이펙트·연출 제외. 옷자락은 사용자 확인 대기. 규칙: docs/NIAN41-BODY-MOTION-2026-10-17.md.
- **승낙 작가(2026-10-18):**
  - yukina_kosaka: 이펙트·연출·연필 임팩트, 인체 제외.
  - riooo: 규모가 큰 전투씬의 이펙트·연출만. 인체와 불 이펙트 전부 제외.
  - optical-core: 이펙트·연출, 인체 제외.
  - 반려(원본 삭제됨): katsumi_ishizuka·sota_shigetsugu·isuta_meister.
  - 범위와 절차: docs/INTAKE-PROCEDURE-2026-10-18.md.
- 학습(모델 훈련)·AI 연결은 하지 않는다. 포즈 추론(YOLO11-pose, tools/pose_extract.py)만 허가됐고, PC방 실행은 연기됐다.
- 조정 권한은 Claude에게 있다(GPT·Gemini 역할 배정과 기록).

## 현재 상태 (2026-10-18, 작업 15 반영) [실측 수치]

- 작업표 1–14는 완료했다. 15는 9단계(교차 확인)만 남았다. 작업표: docs/COORDINATION-PHASE2-2026-10-17.md.
- `data/style_kb/observations.jsonl` 378건. 기존 289건에 작업 15 편입분 89건을 더했다. 편입분은 Claude 단독 판독이다.
- 편입 3명 117건 처리 결과:
  - 회차·연도: `data/sakuga/candidates/intake_step4_era_2026-10-18.csv`. high 72 / medium 18 / 미확인 27.
  - riooo 큰 전투 판정: `riooo_big_battle_2026-10-18.csv`. 포함 22, 제외 24.
  - catalog 상태: `candidates_catalog.csv` analyzed_intake15 89, out_of_scope_intake15 28.
  - 상세: docs/INTAKE-PROCEDURE-2026-10-18.md 4–10단계 결과.
- `data/style_kb/tag_overrides.csv` 356행. 작업 15에서 +33, 5구간 재분할에서 +7을 더했고 기존 5행은 superseded로 바꿨다.
  - impact_frames_pencil confirmed는 **28 그대로**다.
  - 작업 15에서 연필 candidate 16, `impact_frames` 판단 보류 12, 디지털 candidate 5를 추가했다.
  - 임팩트 판정표: `data/style_kb/impact_intake15_claude_2026-10-18.csv`.
- 원 해상도 재확인으로 400px 시트의 '디지털' 4구간을 판단 보류로 정정했다. 거친 손그림 해칭을 2치로 처리한 화면이었다. 400px 판독만으로 디지털을 확정하지 않는다.
- impact_scan은 무채색 문맥, 16프레임을 넘는 흑백, 일부 연필 프레임(85724 13–15)을 놓친다. 임팩트 태그 클립은 시트를 직접 본다.
- 이전 관찰은 유지한다.
  - 302394(2026-03) 이후 작품에는 임팩트 프레임이 없다.
  - 나카무라 디지털 임팩트 경계 연도는 사용자 결정을 기다린다(재검토 목록 `digital_impact_before_302394_2026-10-18.csv`).
- yukina 연필 후보는 2015–2022에 걸친다(단독 판독).

## 다음 할 일 (순서대로)

1. **작업 16 — 작업 15 연필 후보 교차 판독.**
   - Drive `02_분석자료/연필판정_작업15_28구간/`에 묶음이 있다. 구간마다 PNG(앞뒤 2프레임)와 1/4속 영상, `판정표.csv`가 들어 있다.
   - GPT/Gemini 판독이나 사용자 판정을 받아 일치하는 구간을 tag_overrides에서 confirmed로 올린다. 섞인 프레임은 우세 쪽으로 분류한다.
   - 결과를 `impact_intake15_claude_2026-10-18.csv`와 대조해 반영한다.
2. **사용자 확인 대기(작업 15):**
   - 원본을 `_후보검토/<작가>/tagged`에서 `01_원본영상/<작가>/`로 옮길지.
   - riooo의 마력 오라·폭발 섬광을 '불'에서 뺀 판단이 맞는지.
3. **임팩트 정의 재적용(기존 3번).**
   - 1–8프레임 디지털 구간의 극성 전환을 측정한다.
   - 전환 1–2회 5구간은 재분할을 마쳤다(2026-10-18, TAG-RULES 끝 절, tag_overrides 356행). 남은 것은 1–8프레임 구간 전체의 극성 측정이다.
   - 400px에서 디지털로 본 기존 candidate 163건도 원 해상도로 일부 표본 감사를 하는 것이 좋다. 작업 15에서 오판 4/9가 나왔다.
4. **사용자 결정 대기:** 디지털 임팩트 경계 연도.
5. 우선순위 낮음:
   - 11b 확인 대기 구간(경계 20곳)
   - 프레임 번호가 없는 태그 보정 행
   - nian41 옷자락 범위 결정
   - PC방 포즈 추론
   - impact_scan 검출 조건 개선(무채색 문맥·긴 흑백)

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
