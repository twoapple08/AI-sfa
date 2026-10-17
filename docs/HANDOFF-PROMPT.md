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

## 현재 상태 (2026-10-18) [실측 수치]

- 작업표 1–14는 완료했다(docs/COORDINATION-PHASE2-2026-10-17.md).
- `data/style_kb/observations.jsonl` 289건. yutaka는 1475·430을 사용자 지시로 폐기했다.
- catalog: analyzed 333 / indexed 69 / discarded 2.
- `data/style_kb/tag_overrides.csv` 316행.
  - impact_frames_pencil confirmed **28**: 두 AI 일치 16 + 사용자 판정 12. 85724(yukina)는 이제 학습 대상이다.
  - impact_frames_digital candidate 163, confirmed 1(302394 0–13).
  - impact_frames_cel_light 40, bw_direction 4, bw_silhouette_direction 1, pencil_texture_reference 17.
  - 상세: docs/IMPACT-PENCIL-CROSSCHECK-2026-10-17.md.
- 302394(비질란테 S2 #12, 2026-03) 이후 방영된 작품에는 임팩트 프레임이 없다. 309107은 흑백 연출이다.
- 사용자 관찰(가설): 나카무라의 디지털 임팩트는 비교적 최근이고, 그 이전 작품은 연필선이다.
  - 재검토 목록: `data/style_kb/digital_impact_before_302394_2026-10-18.csv`(디지털 시대 134행).
  - 기준 연도는 사용자 결정을 기다린다.

## 다음 할 일 (순서대로)

1. **작업 15 — 승낙 3명 편입**(절차 v1의 4–10단계).
   - riooo: tagged 46개의 contact sheet로 "큰 전투씬"인지 판정한다(태그 1차 후보 13개). 불은 관찰에서 뺀다.
   - optical-core: 28개.
   - yukina_kosaka: 43개(presumed 18개 제외). impact_frames 태그가 있는 24개부터 연필 임팩트를 판정한다.
   - 색인(3단계 완료): `data/sakuga/candidates/intake_index_riooo_optical-core_2026-10-18.csv`, `intake_index_yukina_kosaka_2026-10-18.csv`.
   - 다음 단계는 4(회차·연도 검증, Sakugabooru source 기준) → 7(contact sheet·timing, impact_scan) → 8–10.
   - 원본은 Drive `01_원본영상/_후보검토/<작가>/tagged/`.
   - 판정 결과는 원 해상도로 확인하고, 연필은 두 AI 일치나 사용자 판정이 있어야 확정한다.
2. **작업 14 완료(2026-10-18):** docs/STYLE-KB-ROOTS-2026-10-16.md H절, `data/style_kb/old_new_common_table_2026-10-18.csv`.
   - 세 시기(셀 ≤1999 / 2000–2008 / 2009+)에 모두 나오는 상위 기법: 방사 집중선, 역광 실루엣, 불티, 전경 가림, 2톤 연기, 번개, 다층 화염, 각진 파편.
   - 최신 위주: 별 섬광, 제한 팔레트.
   - 연필 임팩트는 2010–2020년에만 있어 공통 기법이 아니라 그 시기의 특징으로 기록했다.
   - 키워드 집계 기반 근사치다. 다음 개선: 편입 3명 자료가 들어오면 다시 집계한다.
3. **임팩트 정의 재적용.**
   - 1–8프레임 디지털 구간의 흑백 교대(극성 전환)를 측정한다. 방법은 TAG-RULES 끝 절.
   - 전환이 1–2회뿐인 5구간(281184 75–84, 290900 462–471, 228636 291–299, 182469 350–362, 210085 106–125)을 다시 나눈다.
4. **사용자 결정 대기:** 디지털 임팩트를 쓰기 시작한 경계 연도. 결정되면 그 이전 '디지털' 구간을 연필 쪽으로 다시 판정한다.
5. 우선순위 낮음:
   - 11b 확인 대기 구간(경계 20곳)
   - 프레임 번호가 없는 태그 보정 행
   - nian41 옷자락 범위 결정
   - PC방 포즈 추론

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
- **도구:** tools/sakuga_timing.py(`--run S:E` 연속 시트), tools/impact_scan.py, tools/sakuga_collect.py, tools/pose_extract.py.
- **서버 임시 폴더(scratchpad)는 새 세션에 없다.** 필요한 시트는 Drive 02에서 다시 받는다.

## 검증 상태

- `python -m unittest discover -s tests -v` 통과(마지막 실행 2026-10-18).
- 모든 시각 판독은 [추론]이고 timing.json 수치는 [실측]이다. 하위 에이전트 단독 판독은 `cross_check`에 표시돼 있다.

## 규칙

- 토큰·키를 출력하지 않는다.
- 영상 원본·contact sheet·남의 작화는 GitHub(공개)에 올리지 않고 Drive에만 둔다.
- Drive 삭제는 사용자 승인 후에만 한다.
- 자동 승인 거부·로그인/위험 제어 차단은 우회하지 않는다.
- 사용자 대화와 문서는 한국어로 쓰고, 중간 진행 안내도 한국어로 쓴다.
- 문서·aggregate 메타데이터 커밋은 상시 허가돼 있다.
- 혼자 가능한 일은 자율 진행한다. 표를 갱신할 때 완료 행은 선행 조건·상태 칸 모두 **완료**, 진행 중 행은 선행 조건 칸에 **진행 중**으로 적는다.
