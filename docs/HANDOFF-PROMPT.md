# 인수인계 (2026-10-19, 사용자 A 판정 31건 반영·묶음 애니메이터별 정리 시점)

https://github.com/twoapple08/AI-sfa 작업을 이어서 한다. 작업 브랜치는 `ccr-bccf15a6-d6ee46`이다. fetch 후 이 브랜치에서 계속한다(시스템이 다른 브랜치를 배정해도 사용자 지정이 우선).

**읽기 순서:** AGENTS.md → 이 문서 → docs/IMPACT-V2-CRITERIA-2026-10-18.md 3차 보완(최신 판정 규칙) → docs/STYLE-KB-ROOTS-2026-10-16.md H3절 4)(A 판정 결과). 작업표는 docs/COORDINATION-PHASE2-2026-10-17.md다. 주제 문서는 필요할 때만 연다. 직전 인수인계: docs/history/HANDOFF-PROMPT-2026-10-19a-archive.md.

## 0-1. 이번 세션에서 끝낸 일 (2026-10-19)

| 작업 | 결과 | 기록 |
|---|---|---|
| 사용자 A(애매) 판정 31/50 반영 | 아님 22, 옆 프레임에 실제 임팩트 3, 임팩트 4, 반반 2. 32–50번 19건 미판정 | `data/style_kb/judge_lists/A_user_judgement_2026-10-19.csv`, tag_overrides(629행, `train_weight` 열·`borderline` 상태 신설) |
| 실제 임팩트 위치 재측정(Claude 원본 확인) | 24304 f203–209, 162980 f310, 70207 f394–398(학습 제외), 78337 f378–379, 253949 f32–33 | 같은 CSV `corrected_frames` |
| 하위 에이전트 비교 | 최종은 50건 모두 unsure라 비교 불가. 기울었던 15건 중 일치 13·불일치 2 | STYLE-KB H3 4) |
| 판정 기준 3차 보완 | 앞뒤 연속(동화) 확인 필수, 먼지·섬광·집중선·옷 가림 등 '아님' 유형, 반반·학습 비중 | IMPACT-V2-CRITERIA 3차, TAG-RULES 끝 절 |
| 연속성 지표·문맥 시트 도구 | tools/judge_context.py(경계 에지 상관 ≥0.6 = 동화 의심 경고) | STYLE-KB H3 4) 보정 수치 |
| Drive 묶음 애니메이터별 정리 | `사용자판정_{A,B,C}/<애니메이터>/<구간 폴더>/` + 폴더마다 `문맥시트_f…jpg` + 판정표.csv에 animator·cont·continuity_warning·nearby_impact_rows 열 | 아래 1절 |

- 사용자 지적(2026-10-19): 영상에는 임팩트가 있는데 사진(PNG)에는 없는 경우가 많다(1/4속 영상이 앞뒤 12프레임을 더 담기 때문, 프레임 번호 어긋남은 아님). 애매 구간은 절반 이상이 아님. 앞뒤 장면과 이어지는 동화를 한 장만 보고 임팩트로 본 경우가 많다.

## 0. 지난 세션에서 끝낸 일 (2026-10-18)

| 작업 | 결과 | 기록 |
|---|---|---|
| 임팩트 전체 재검사(411영상) | 후보 2,625 → 임팩트 314, 부분 29, 애매 50, 아님 1,896, 제작 자료 제외 336 | `data/style_kb/impact_v2_judgement_2026-10-18.csv`, tag_overrides 반영 |
| 기법 자료 수집·관찰(815클립) | 이타노 뚜렷 125·일부 238, 쿠츠나 뚜렷 76·일부 197 | `data/style_kb/technique_obs_2026-10-18.csv` |
| yutaka 인체 범위 보충(160클립) | 몸 움직임 있음 123 | `data/style_kb/yutaka_body_obs_2026-10-18.csv` |
| 지식베이스 재집계 | STYLE-KB-ROOTS H3절 | docs/STYLE-KB-ROOTS-2026-10-16.md |

- 판독 방식: 판정판(여러 후보·클립을 한 장에 모은 이미지)을 하위 에이전트가 1차 판독했다. Claude가 표본을 감사하고 사용자 확정 구간과 대조했다.
  - 임팩트: 사용자 확정 55구간 중 52 재발견, 사용자 '아님' 판정과 충돌 0
- 그래서 새로 찾은 임팩트는 tag_overrides에 **candidate**로만 넣었다. 확정은 사용자 판정이 필요하다.
- 백그라운드 작업(재검사 411, 수집 821)은 모두 끝났다. 다시 돌릴 필요가 없다.

## 1. 다음 할 일 (순서대로)

1. **사용자 판정 나머지 반영(최우선).** 사용자가 세 묶음을 직접 보고 판정 중이다(2026-10-18 지시: "셋 다 따로 정리해, 내가 다 직접 보고 검증할게"). 2026-10-19에 A 1–31번을 받아 반영했다.

| 묶음 | Drive `AI-sfa/02_분석자료/` | 구간 | 목록(저장소) | 상태 |
|---|---|---|---|---|
| A 애매 | `사용자판정_A_애매50/` | 50 | `judge_lists/A_unsure_50.csv` → 판정 기록 `A_user_judgement_2026-10-19.csv` | 31 반영, 32–50 대기 |
| B 신규 임팩트 후보 | `사용자판정_B_신규임팩트후보303/` | 303(연필 277 + 부분 26) | `judge_lists/B_new_impact_candidates_303.csv` | 대기(3건은 A에서 사용자 확인, 판정표에 미리 기입) |
| C v2 미검출 기존 후보 | `사용자판정_C_v2미검출_기존후보84/` | 84(1행은 frames=all, PNG 없음) | `judge_lists/C_v2_undetected_84.csv` | 대기 |

   - **Drive 구조(2026-10-19 사용자 지시로 애니메이터별 정리):** `<묶음>/<애니메이터>/<번호_post_f구간>/`. 애니메이터 폴더는 yutaka_nakamura·riooo·optical-core·yukina_kosaka, C에만 `기타_katsumi_ishizuka(반려)` 1건. 폴더 이름의 번호는 판정표 no와 같다.
   - 각 구간 폴더: 앞뒤 2프레임 PNG + slow_quarter.mp4(앞뒤 12프레임 더) + `문맥시트_f…jpg`(영상과 같은 범위, 프레임 번호, 후보=노란 테두리, 다른 임팩트 행=하늘색 테두리).
   - 판정표.csv(묶음 최상위, 애니메이터 순): animator, cont, continuity_warning(≥0.6 '앞뒤와 이어짐(동화 의심)'), nearby_impact_rows 열 추가. A는 user_judgement·user_note·train_weight·corrected_frames를 채웠다. 애니메이터 폴더마다 `판정표_<애니메이터>.csv`도 있다. 동화 의심 경고: A 8, B 34, C 4건. 업로드 확인(2026-10-19): 문맥 시트 A 50·B 303·C 83장, 구간 폴더 수 일치.
   - 묶음이 사라지면: `tools/make_judge_bundle.py <list.csv> <작업폴더> <Drive 대상>`으로 만든 뒤 `tools/judge_context.py <판정표.csv> <원본폴더> <출력>`으로 문맥 시트·열을 붙이고 애니메이터 폴더로 올린다(원본은 Sakugabooru md5 대조로 받는다).
   - 사용자가 판정을 주면 tag_overrides를 갱신한다(방식은 TAG-RULES 끝 절).
     - 임팩트 → confirmed(연필; 302394만 디지털), 비중 언급이 있으면 train_weight low/exclude
     - 부분 → impact_frames_partial confirmed, 반반 → borderline(low)
     - 아님 → `impact_frames` not_impact(원문·분류)
     - 사진엔 없고 영상에만 있다고 하면 문맥 원본에서 실제 위치를 찾아 confirmed로 넣고 후보 구간은 not_impact
     - A의 임팩트·부분은 새 행으로 추가한다(기존 후보 행이 같은 구간이면 그 행을 갱신).
   - 판정마다 하위 에이전트 판정과 다른 건수를 세어 STYLE-KB H3에 기록한다(B는 v2 최종 impact/partial, C는 v2 미검출이 비교 기준).
   - Gemini 판정(docs/GEMINI-TASK-JUDGE-ABC-2026-10-19.md)은 사용자 판정이 아니므로 별도 기록, 사용자 확인 전까지 candidate.
2. **'학습'의 다음 형태 결정(사용자).** 2026-10-19 질문에 사용자 답은 '선호 없음'이었다 → 아직 미결정. 모델 훈련은 계속 허가되지 않은 상태로 둔다. B·C 판정이 끝나면 다시 묻는다.
   - SFA 규칙·시험작(04_SFA시험작)으로 검증할지, 모델 훈련으로 갈지 정한다. 모델 훈련은 아직 허가되지 않았다.
   - SFA로 가면 H·H2·H3절의 '이식 제안'을 시험작 사양으로 만든다.
3. 보완(필요할 때):
   - 기법 클립의 정밀 프레임 구간 재측정(지금은 16칸 표본 근사)
   - yutaka 인물 타이밍(인물 영역만 재는 포즈 추론, PC방)
   - 판정판에서 빠진 yutaka 8클립(contact sheet 없음)
4. 우선순위 낮음: 11b 경계 20곳, 프레임 번호 없는 태그 보정 행, impact_scan2 오검출 개선(사용자 지적: 동화 연속 장면 오검출 많음 → judge_context.py 연속성 지표를 검출 단계에 넣는 안. 단 컷이 바뀌는 먼지·섬광은 못 거른다), 239055 f213(앞 프레임과 같음 — 확정 구간 번호 어긋남 의심, 원본 확인 필요).

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
- **판정은 한 장이 아니라 앞뒤 ±12프레임 연속으로 한다(2026-10-19).** 앞뒤와 이어지는 동화, 먼지·연기·충격파, 섬광, 집중선·고속 이동 배경, 옷이 화면을 가림, 물·전기 이펙트, 실루엣 연출만 빌린 장면은 흑백이어도 아니다(IMPACT-V2-CRITERIA 3차).
- 학습 비중: 실루엣·강조 없는 단색 번쩍임·수준 낮음·추구미 아님 = low, 추구미 전혀 아님 = exclude, 사용자 "반은 맞음" = borderline.
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
| tag_overrides.csv | 629행(2026-10-19): 연필 confirmed 59·candidate 361, 부분 confirmed 2·candidate 26, borderline 2, `impact_frames` not_impact 34, cel_light 40, 디지털 confirmed 1. `train_weight` 열 추가 |
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
  - 02_분석자료: `<post>/`(contact_sheet·timing), `impact/`(v1), `impact_v2/`, `기법/`, 사용자판정_A_애매50·B_신규임팩트후보303·C_v2미검출_기존후보84, 연필판정_작업15_28구간, 연필보류_12구간
  - 03_스타일지식베이스: 문서·observations·tag_overrides
- **도구:**
  - tools/impact_scan2.py(개정 정의 검출), tools/run_impact_v2.py, tools/collect_technique.py(Drive 기준 재개, 둘 다 완료됨)
  - 판정 기준: docs/IMPACT-V2-CRITERIA-2026-10-18.md(하위 에이전트용 임팩트 판정 기준)
  - tools/make_judge_bundle.py(사용자 판정 묶음 생성)
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
