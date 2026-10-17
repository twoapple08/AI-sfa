https://github.com/twoapple08/AI-sfa 작업을 이어서 진행해 줘. 작업 브랜치는 `ccr-bccf15a6-d6ee46`이다. fetch 후 이 브랜치에서 계속한다(시스템이 다른 브랜치를 배정해도 사용자 지정이 우선).

읽기 순서: AGENTS.md → 이 문서 → docs/COORDINATION-PHASE2-2026-10-17.md(작업표가 현재 기준) → docs/STYLE-KB-ROOTS-2026-10-16.md. 주제 문서는 필요할 때만 연다. HANDOFF.md는 이전 AOT 분석 단계의 기록이다. 이전 인수인계 상세: docs/history/HANDOFF-PROMPT-2026-10-17-archive.md.

## 현재 우선순위

(나) 분석형 스타일 학습. Stick Fighter용 스타일 지식베이스를 만든다.
- **yutaka_nakamura:** 이펙트·배경·연출. 에반게리온 제외. 구작·최신작 공통 기법 가중.
- **impact_frames는 4B 연필 느낌만 학습하고 디지털 단색은 제외한다(최중요).** 섞인 프레임은 비중이 큰 쪽으로 분류하고 '섞임(연필 우세)'처럼 표기한다(사용자 판정 290900 157).
- **nian41:** 사람 몸 움직임만. 표정·그림체·머리카락·이펙트·연출 제외. 옷자락은 사용자 확인 대기. 규칙: docs/NIAN41-BODY-MOTION-2026-10-17.md.
- 추가 작가는 사용자 승낙 후에만 편입한다. 학습(모델 훈련)·AI 연결은 하지 않는다. 포즈 추론(YOLO11-pose, tools/pose_extract.py)만 허가됐고, PC방 실행은 다음으로 연기됐다.
- 조정 권한은 Claude에게 있다(GPT·Gemini 역할 배정과 기록).

## 현재 상태 (2026-10-17 끝) [실측 수치]

- `data/style_kb/observations.jsonl` 289건. yutaka 미분석 241건 분석을 마쳤다.
  - 11a: GPT 신규 51건 + 같은 장면 병합 18건.
  - 11b: Claude 하위 에이전트 144건. 표본 감사 3/3 일치.
- catalog analyzed 335 / indexed 69.
- `data/style_kb/tag_overrides.csv` 296행.
  - impact_frames_pencil: confirmed 16, candidate 22.
  - impact_frames_digital: confirmed 1, candidate 207.
  - 그 외 태그 보정 candidate.
- 연필 confirmed 16구간은 모두 두 AI 일치 또는 사용자 판정이다.
  - 구성: GPT30분 9 + 11a분 5 + 후보 작가 85724분 2.
  - 85724는 승낙 전 학습 제외.
  - 상세: docs/IMPACT-PENCIL-CROSSCHECK-2026-10-17.md.
- Gemini 작업 A(후보 6명 평가)는 대조를 마쳤다(docs/GEMINI-A-CHECK-2026-10-17.md).
  - 프레임 판정은 정확했다.
  - 회차·연도·클립 설명은 믿을 수 없다(19727 오기 확인).
- Claude 의견: yukina_kosaka 승낙 추천(이펙트·연필 임팩트 한정), katsumi_ishizuka 보류, sota_shigetsugu·isuta_meister 반려 추천, riooo·optical-core 보류.

## 다음 할 일 (순서대로)

1. **사용자 응답 반영**(답이 오면 바로 처리):
   - (a) 후보 승낙·반려: 2026-10-18 riooo 승낙(큰 전투씬의 이펙트·연출만, 인체·불 제외), optical-core 승낙(이펙트·연출만, 인체 제외), katsumi_ishizuka 반려. yukina_kosaka·sota·isuta 미정. 범위와 색인은 docs/INTAKE-PROCEDURE-2026-10-18.md §4. 다음: riooo tagged 전체 contact sheet로 규모 판정 → 절차 4–10단계.
   - (b) 셀 시대 단색 섬광(313715 등) 태그 처리. 제안은 `impact_frames_digital` 뜻을 '디지털·셀 단색 평면'으로 넓히는 것.
   - (c) 연필 질감 정지 자료(11b 일러스트 7·409·232580·24634, 11a 정지 연필 7행)를 '연필 질감 참고'로 표시할지.
   - (d) 귀속 의심: 1475(원화 크레딧 佐藤雅弘로 보임), 430(다른 작품 그림으로 보임).
2. **작업 13 남은 것:** 11a 연필 보류 12구간. 400px로는 흑연·잉크·디지털 브러시를 가르기 어렵다(Claude는 흐린 결을 블러로 오판한 전력이 있음).
   - 할 일: 원 해상도 프레임 묶음을 만들어 사용자에게 보내 판정받는다.
   - 대상 목록: 크로스체크 문서 2차 표.
3. **작업 14:** 구작·최신작 공통 기법표.
   - 재료: observations의 `old_new_common`(true 다수)과 `old_new_common_note/source_posts`.
   - 산출: 기법별 구작 표본·최신작 표본·빈도 표를 만들고 STYLE-KB-ROOTS에 '공통 기법' 절로 통합한다. 단일 표본은 표시한다.
4. Gemini 작업 C 대조 완료 → 편입 절차 v1(docs/INTAKE-PROCEDURE-2026-10-18.md). 승낙이 오면 이 절차대로 진행한다. 반려 추천 2명(sota_shigetsugu·isuta_meister)의 근거 임팩트 4개 중 2개는 Gemini 오판이었다. 연필 부재는 전수 검사 전이다.
5. 11b 확인 대기 구간(디지털/불확실 경계 20곳, 학습 제외 쪽)과 프레임 번호 없는 태그 보정 행 정리. 우선순위는 낮다.

## 환경·자료 위치

- **Drive:** rclone `gdrive:` remote를 환경 변수 RCLONE_CONFIG_GDRIVE_{TYPE,SCOPE,TOKEN}로 쓴다.
  - 범위가 drive.file이라 GPT가 올린 파일은 rclone으로 안 보인다.
  - 공개 폴더 https://drive.google.com/drive/folders/1M8Fk05crDvs42R9Eqt7FdJv2fPSiX8Xy 를 `embeddedfolderview?id=`로 나열하고, `drive.usercontent.google.com/download?id=..&export=download&confirm=t`로 받는다.
  - 공용 client_id 폐지 예정 경고가 있다.
- **rclone 설치:** 새 컨테이너에는 rclone이 없을 수 있다. 공식 릴리스를 받아 SHA256을 대조한 뒤 설치한다(서버 분석 도구 복구 허용 범위).
- **Drive 구조 `AI-sfa/`:**
  - 00_목록: catalog, manifest, 연도표, 분할표.
  - 01_원본영상: yutaka GPT ZIP, nian41 48개, `_후보검토/<작가>/{tagged,presumed}`.
  - 02_분석자료: `<post>/contact_sheet.jpg,timing.json`, `impact/<post>/f시작-끝.jpg`, `impact_candidates_*.csv`.
  - 03_스타일지식베이스: 문서, observations, tag_overrides, impact_reference.
- **원본 확인:** Sakugabooru 공개 URL `https://www.sakugabooru.com/data/<md5>.<ext>`에서 임시로 받고 확인 뒤 지운다. md5는 catalog.csv 또는 후보 manifest에 있다.
- **도구:** tools/sakuga_timing.py(`--run S:E` 연속 시트), tools/impact_scan.py, tools/sakuga_collect.py, tools/pose_extract.py.
- **서버 임시 폴더(scratchpad)는 새 세션에 없다.** 필요한 시트는 Drive 02에서 다시 받는다.

## 검증 상태

- `python -m unittest discover -s tests -v` 통과(마지막 실행 2026-10-17).
- 모든 시각 판독은 [추론]이고 timing.json 수치는 [실측]이다. 하위 에이전트 단독 판독은 `cross_check`에 표시돼 있다.

## 규칙

- 토큰·키를 출력하지 않는다.
- 영상 원본·contact sheet·남의 작화는 GitHub(공개)에 올리지 않고 Drive에만 둔다.
- Drive 삭제는 사용자 승인 후에만 한다.
- 자동 승인 거부·로그인/위험 제어 차단은 우회하지 않는다.
- 사용자 대화와 문서는 한국어로 쓰고, 중간 진행 안내도 한국어로 쓴다.
- 문서·aggregate 메타데이터 커밋은 상시 허가돼 있다.
- 혼자 가능한 일은 자율 진행한다. 표를 갱신할 때 완료 행은 선행 조건·상태 칸 모두 **완료**, 진행 중 행은 선행 조건 칸에 **진행 중**으로 적는다.
