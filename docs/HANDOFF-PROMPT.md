# 인수인계 (2026-10-18 세션 종료 시점)

https://github.com/twoapple08/AI-sfa 작업을 이어서 한다. 작업 브랜치는 `ccr-bccf15a6-d6ee46`이다. fetch 후 이 브랜치에서 계속한다(시스템이 다른 브랜치를 배정해도 사용자 지정이 우선).

**읽기 순서:** AGENTS.md → 이 문서 → docs/TAG-RULES-2026-10-17.md(끝 세 절: 임팩트 정의 개정, 연필/디지털 경계) → docs/TECHNIQUE-ITANO-KUTSUNA-2026-10-18.md. 작업표는 docs/COORDINATION-PHASE2-2026-10-17.md다. 주제 문서는 필요할 때만 연다. 직전 인수인계: docs/history/HANDOFF-PROMPT-2026-10-18-archive.md.

## 0. 새 세션에서 가장 먼저 할 일: 지난 세션 백그라운드 작업 확인

지난 세션에서 백그라운드 작업 2개를 돌렸다. 세션이 끝날 때까지 다 끝났는지는 알 수 없다. 백그라운드 실행은 2시간 제한이 있고, 컨테이너가 회수되면 함께 멈춘다. 처리된 결과는 항목마다 Drive에 올라가 있다.

| 작업 | 대상 수 | 결과 위치(Drive `AI-sfa/`) | 완료 판정 파일 |
|---|---|---|---|
| ① 임팩트 프레임 전체 재검사 | 411(yutaka 영상 294 + 편입 117) | `02_분석자료/impact_v2/<post>/`(impact.json, v2_f*.jpg 후보 시트) | `<post>/impact.json` |
| ② 기법 자료 수집(이타노 서커스·쿠츠나 번개) | 821(받지 않음 6 포함) | 원본 `01_원본영상/기법_itano_circus/`·`기법_kutsuna_lightning/`, 분석 `02_분석자료/기법/<post>/`(contact_sheet.jpg, timing.json, done.json) | `<post>/done.json` |

**순서**
1. 환경을 확인한다.
   - rclone이 없으면 공식 릴리스를 받아 SHA256을 대조한 뒤 설치한다(서버 분석 도구 복구 허용 범위).
   - Drive 접근(`rclone lsd gdrive:AI-sfa`)과 ffmpeg가 되는지 본다.
2. 완료 개수를 센다. 반드시 `--files-only`를 붙인다. 빼면 폴더까지 세어져 수가 부풀려진다.
   ```
   rclone lsf -R --files-only --include '*/impact.json' gdrive:AI-sfa/02_분석자료/impact_v2 | wc -l   # 목표 411
   rclone lsf -R --files-only --include '*/done.json' gdrive:AI-sfa/02_분석자료/기법 | wc -l        # 목표 821
   ```
   - **① 임팩트 재검사는 2026-10-18에 411/411 완료**됐다(실패 0).
     - 후보 구간 2,625개: yutaka 1,933, riooo 291, yukina 215, optical-core 186.
     - 후보가 있는 게시물은 332, 시트는 1,777장이다.
   - ② 기법 수집은 같은 날 285/821에서 새 드라이버로 다시 시작했다. 위 명령으로 현재 수를 확인한다.
   - 다운로드 실패(DOWNLOAD_FAIL)는 결과가 없어 목표에 못 미칠 수 있다. 드라이버를 다시 돌리면 재시도한다.
3. 덜 끝났으면 드라이버를 실행해 이어서 처리한다.
   - 두 드라이버 모두 Drive에 완료 파일이 있는 항목은 건너뛰고, 처리한 항목은 바로 Drive에 올린다.
   - 오래 걸리므로 run_in_background로 실행하고, 2시간 제한으로 멈추면 다시 실행한다. 둘을 동시에 돌려도 된다(4코어 기준 3 + 2 workers).
   ```
   python tools/run_impact_v2.py --work <scratchpad>/impact_v2 --workers 3
   python tools/collect_technique.py --work <scratchpad>/tech --workers 2
   ```
   - 원본은 Sakugabooru(`/data/<md5>.<ext>`)에서 받아 md5를 대조하고, 쓴 뒤 지운다.
4. 두 작업이 목표 수에 도달하면 아래 작업 순서로 넘어간다.

## 1. 다음 작업 순서

1. **임팩트 후보 판정.**
   - `impact_v2/<post>/v2_f*.jpg` 시트를 보고 임팩트 프레임인지만 판정한다. 연필/디지털은 규칙으로 정해진다(아래 2절).
   - 후보 구간 목록은 각 `impact.json`의 `runs`에 있다.
   - 어두운 장면의 오검출이 많다(예: 75463).
   - 판정한 결과로 처리할 것:
     - tag_overrides의 impact_frames_pencil candidate 163행(옛 디지털 160 포함)을 confirmed나 not_impact로 정한다.
     - 새로 찾은 구간은 추가한다.
   - 애매한 구간은 원 해상도 묶음으로 만들어 사용자 판정을 받는다. 묶음 형식은 작업 15와 같다(구간 앞뒤 2프레임 PNG + 1/4속 영상 + 판정표.csv, Drive `02_분석자료/연필판정_작업15_28구간` 참고).
   - 토큰을 아끼려면 판정 기준을 담아 하위 에이전트에 1차 분류를 맡기고, 표본을 감사한다. 하위 에이전트 판독은 cross_check에 표시한다.
2. **기법 구간 관찰.**
   - itano_circus·kutsuna_lightning 클립마다 contact sheet로 기법이 나오는 프레임 구간을 찾고 관찰을 작성한다. 관찰 항목은 TECHNIQUE 문서에 있다.
   - kutsuna는 작업 15의 번개 관찰(riooo·yukina)과 대조한다.
   - 반려 작가 공동 태그 kutsuna 21건은 쿠츠나 학습용으로만 쓴다(done.json의 `scope`).
3. **yutaka 인체 범위 보충 관찰.**
   - 분석한 297건의 contact sheet(`02_분석자료/<post>/`)로 머리카락·복장의 움직임 표현과 몸 움직임을 보충한다.
     - 머리카락: 덩어리 분할, 흩날림 타이밍
     - 복장: 옷자락 펄럭임, 뒤따름
     - 몸 움직임: 포즈 간격, 1s/2s, 스미어, 무게 이동
   - 항목명은 docs/NIAN41-BODY-MOTION-2026-10-17.md와 맞춘다. 얼굴·표정·그림체는 보지 않는다.
4. **지식베이스 재집계.**
   - STYLE-KB-ROOTS H·H2절을 새 관찰(기법·인체·임팩트)로 갱신하고, SFA 이식 방법과 우선순위를 정리한다.
5. **사용자 결정 필요:** '학습'의 다음 형태.
   - SFA 규칙·시험작(04_SFA시험작)으로 검증할지, 모델 훈련으로 갈지 정해야 한다. 지금은 모델 훈련이 허가되지 않았다.
   - 모델 훈련으로 가면 프레임 단위로 정답을 표시한 학습 데이터 형식이 별도로 필요하다.
6. 우선순위 낮음: 11b 경계 20곳, 프레임 번호 없는 태그 보정 행, PC방 포즈 추론(yutaka 포함), impact_scan2 오검출 개선.

## 2. 학습 범위와 임팩트 규칙 (2026-10-18 기준)

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
- 부분 임팩트(화면 일부만)는 `impact_frames_partial`로 따로 센다.
- 셀 시대(≤1999) 단색 섬광은 `impact_frames_cel_light`로 학습에서 제외한다.
- TV판에서 명도가 낮아진 임팩트(218857 등)는 학습할 때 밝은 흰색·검정 조합으로 변환한다.

## 3. 현재 자료 수 [실측]

| 항목 | 수 |
|---|---|
| yutaka 게시물(catalog) | 366: 분석 297, 색인만 69 / 폐기 2 |
| nian41 분석 | 36 |
| 편입 3명 | 117(+ presumed 25 별도 보관), 연도표 `data/sakuga/candidates/intake_step4_era_2026-10-18.csv` |
| observations.jsonl | 378: yutaka 250, nian41 36, 편입 89, 제외 기록 3 |
| tag_overrides.csv | 356행: 연필 confirmed 52 / candidate 163, partial 2, 302394 디지털 6, cel_light 40 |
| 기법 태그 목록 | itano_circus 462, kutsuna_lightning 362(`data/sakuga/techniques/`) |

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
  - 02_분석자료: `<post>/`(contact_sheet·timing), `impact/`(v1), `impact_v2/`, `기법/`, 연필판정_작업15_28구간, 연필보류_12구간
  - 03_스타일지식베이스: 문서·observations·tag_overrides
- **도구:**
  - tools/impact_scan2.py(개정 정의 검출), tools/run_impact_v2.py, tools/collect_technique.py(Drive 기준 재개)
  - tools/sakuga_timing.py(`--run S:E` 연속 시트), tools/sakuga_index.py(태그 색인), tools/intake_step4_era.py, tools/pose_extract.py
  - tools/impact_scan.py(v1, 연필 누락이 있어 대체됨)
- **주의:**
  - 반복문 안 ffmpeg는 표준입력을 가로챈다(`-nostdin`, stdin=DEVNULL).
  - `pkill -f <이름>`은 그 이름이 든 자기 셸까지 죽인다. PID로 kill한다.
  - `rclone lsf --include`로 셀 때는 `--files-only`를 붙인다.
  - Wikipedia API는 429로 막혀 WebFetch로 확인했다. YouTube는 oEmbed만 된다.
  - scratchpad는 새 세션에 없다.
- **Sakugabooru 태그 위키(태그 옆 '?'):** `https://www.sakugabooru.com/wiki.json?query=<태그>`

## 검증 상태

- `python -m unittest discover -s tests -v` 통과(2026-10-18 마지막 커밋 기준).
- 시각 판독은 [추론], timing·극성·검출 지표는 [실측]이다. 편입 관찰은 Claude 단독(cross_check 표시)이다.

## 규칙

- 토큰·키를 출력하지 않는다.
- 영상 원본·contact sheet·남의 작화는 GitHub(공개)에 올리지 않고 Drive에만 둔다.
- Drive 삭제는 사용자 승인 후에만 한다.
- 자동 승인 거부·로그인/위험 제어 차단은 우회하지 않는다.
- 사용자 대화와 문서는 한국어로 쓰고, 중간 진행 안내도 한국어로 쓴다.
- 문서·aggregate 메타데이터 커밋은 상시 허가돼 있다.
- 혼자 가능한 일은 자율 진행한다. 표를 갱신할 때 완료 행은 선행 조건·상태 칸 모두 **완료**, 진행 중 행은 선행 조건 칸에 **진행 중**으로 적는다.
