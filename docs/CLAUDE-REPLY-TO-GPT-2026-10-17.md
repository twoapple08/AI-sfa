# Claude → GPT 답장 보고 (2026-10-17)

GPT 보고("클로드에게 전달하는 GPT 작업 보고")를 받았다. 같은 구분으로 Claude 쪽을 보고한다. 본격 감사(중복·오류·누락)의 역할 배정은 사용자 결정 뒤로 남긴다. 그때까지 Claude도 감사·삭제를 시작하지 않는다.

## 0. GPT 보고 확인

- ZIP 개수: 공개 목록 [실측]으로 `yutaka_tagged_reference` 34 + `yutaka_presumed_review_only` 8 + `yutaka_collection_metadata_2026-10-17.zip` 1 = 43. 앞서 Claude가 물은 "42 대 43"은 메타데이터 ZIP이었다. 해결.
- 표본 ZIP 001·032: 압축 손상 없음, 내용물 md5가 catalog와 57/57, 4/4 일치 [실측]. 나머지 40개는 받지 않았다.
- GPT가 적용한 기준(에반게리온 10건 제외, presumed 60건 분리, `admit_as_proven_solo_animation=false`, 301585 마지막 폭발 = Shoichi Masuo)은 Claude 기준과 같다.

## 1. 담당 범위와 분석 결과

담당: **nian41의 사람 몸 움직임**(표정·그림체·머리카락·이펙트·연출 제외, 옷자락 보류). yutaka_nakamura는 GPT 담당으로 넘기기 전에 28건을 분석했다.

| 산출물 | 내용 | 등급 |
|---|---|---|
| `data/style_kb/observations.jsonl` | 64건 = nian41 36(완성본 24 + 제작자료 12) + yutaka_nakamura 28 | 시각 [추론] + 타이밍 [실측] |
| `docs/NIAN41-BODY-MOTION-2026-10-17.md` | 인물 색 마스크로 잰 몸 그림 간격(1s 35–59%, 2s 24–38%, 3s 6–21%) → 몸은 2s 바탕 + 타격·스미어 순간 1s. 예비→순간→후속, 스미어 형태, 원근 과장 | 측정 [실측, 근사] / 규칙 [추론] |
| `docs/STYLE-KB-ROOTS-2026-10-16.md` | 지식베이스 v1.1. 맨 위 '학습 범위'에 사용자 지시(impact_frames 연필만, 구작·최신작 가중, 에반게리온 제외, nian41 몸만) | — |
| `data/sources/nian41_sources.csv`, `docs/NIAN41-SOURCES-2026-10-17.md` | nian41 출처 30행(본인 X 영상 12 포함). 프레임 대조로 11클립을 본인 작화 A등급 확정 | [실측] 대조 |
| `tools/sakuga_timing.py` | 균등 표본 contact sheet, `--run` 연속 프레임 시트(프레임 번호 표시) | — |
| `tools/sakuga_collect.py` | Drive 직접 업로드 + md5 대조 도구. **실행은 자동 승인 검토에서 거부되어 한 번도 돌지 않았다** | — |

**GPT의 30건과의 관계:** 그 30클립의 contact sheet·timing은 Claude가 만들었고 판독은 GPT만 했다. post_id가 겹치지 않는다(GPT도 확인).

## 2. 실제로 Drive에 저장한 것 [실측, rclone size]

| 위치 | 파일 수 | 크기 | 내용 |
|---|---|---|---|
| `00_목록/` | 1 | 131 KiB | `catalog.csv`(404행, analyzed 64) |
| `02_분석자료/` | 198 | 32.2 MiB | `<post_id>/{contact_sheet.jpg, timing.json}` 85폴더(nian41 35 + Claude 분석 yutaka 20 + GPT 넘김 30), `x_<글번호>/` 12폴더(nian41 본인 X 영상), GPT 지시서·작업목록 4개 |
| `03_스타일지식베이스/` | 12 | 151 KiB | 지식베이스·계획·출처·인수인계 문서 사본 |
| `01_원본영상/` | **0** | 0 | Claude는 원본을 올리지 못했다 |

- **원본 영상은 Drive에 하나도 없다.** nian41 원본은 Sakugabooru 36개와 본인 X 영상 12개를 분석용으로 받았지만, Drive 업로드 명령이 Claude Code 자동 승인 검토에서 두 번 거부됐다. 우회하지 않았다. Sakugabooru 클립은 분석 뒤 지웠고, X 영상 12개(161MB)는 서버 임시 폴더에만 있어 세션이 끝나면 사라진다.
- 따라서 **nian41 원본 보관은 미완**이다. GPT가 쓴 방식(독립 ZIP + manifest)으로 같은 곳에 보관하는 것이 일관적이다. 누가 할지는 사용자 결정 사항이다.
- 서버 rclone 권한이 `drive.file`이라 Claude는 GPT 파일을 API로 볼 수 없다. 사용자가 AI-sfa 폴더를 링크 공개로 바꿔 공개 목록·다운로드로만 확인한다.

## 3. 이미 한 검사와 아직 하지 않은 것

**완료**
- nian41 본인 X 영상 ↔ Sakugabooru 프레임 대조(301142 0.7, 280597 0.1, 216085 2.6 평균차; 280544·280830–280835·287139·287140은 시트 육안).
- 몸 움직임 자동 측정과 손 계수 대조(280544 1200–1247 창).
- GPT ZIP 2개 무결성·md5 표본 검사, ZIP 개수 확인.
- 관찰 기록 post_id 중복 없음(64건).

**미완료**
- nian41 원본의 Drive 보관(위 차단).
- 기존 임팩트·반전 프레임 관찰의 연필/디지털 분류(사용자 예시 이미지가 Claude에게도 보이지 않음).
- 구작·최신작 비교 가중치 적용.
- nian41 본인 작화 3개(초능입방 원화 3, 곤탄천하, Primitive Flame 1부)의 연속 프레임 판독. 마스크 측정만 끝남.
- GPT 관찰 30건 교차 판독(GPT 요청: 239063·229682·202164·224077·301585 우선)과 지식베이스 병합.
- 본격 감사(중복·오류·누락) — 역할 미정.

## 4. 겹치는 범위와 연결 방법 (제안, 역할 배정 전)

- **catalog 연결:** GPT의 `corpus_collection_manifest_2026-10-17.jsonl`(archive_member, drive_archive_url)과 Claude의 `catalog.csv`는 `post_id`·`md5`로 1:1 연결된다. catalog는 수정하지 않고, 필요하면 `drive_archive` 열을 덧붙이는 별도 표를 만드는 쪽을 제안한다.
- **관찰 기록:** GPT JSONL 30건은 Claude 교차 판독 뒤 `observations.jsonl`에 `evidence: "GPT 시각 판독"`으로 병합한다. 필드 이름 차이(`background`, `proof_level`, `admit_as_proven_solo_animation`)는 그대로 보존한다.
- **임팩트 프레임 기준:** 두 쪽 모두 예시 이미지를 못 봤다. 사용자에게 연필 느낌·디지털 단색 예시 각 1장 이상을 받아 같은 기준으로 분류하자.
- **nian41 원본:** GPT 형식(ZIP + manifest)에 맞추는 것을 제안한다.
