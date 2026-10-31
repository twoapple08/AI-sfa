# 3자 작업 조정안 v1 (2026-10-17, Claude 결정)

**사용자 지시(2026-10-17):** "조정사항이 있을 시 조정은 모두 Claude에게 맡김." 이 문서가 GPT·Claude·Gemini 역할 배정의 현재 기준이다. 사용자가 바꾸라고 하면 그 지시가 우선한다.

## 1. 조정 결과 요약

| 담당 | 맡는 일 |
|---|---|
| **GPT** | ① nian41 원본 Drive 보관(Claude 서버가 업로드 차단돼 대신 맡음) ② yutaka 외부 영상 7개 장면 중복·귀속 검토 ③ yutaka 분석 계속(아래 순서) ④ 사용자 예시를 받은 뒤 yutaka impact_frames 연필/디지털 분류 |
| **Claude** | ① 메타데이터 감사(이 문서 2절, **완료**) ② GPT 관찰 30건 교차 판독·지식베이스 병합 ③ nian41 몸 움직임 분석 계속 ④ GPT·Gemini 결과의 최종 대조와 지식베이스 통합 ⑤ 조정 |
| **Gemini** | ① 후보 6명 평가 ② Claude의 nian41 몸 움직임 규칙 교차 검증 (`GEMINI-PASTE-2026-10-17.md` 그대로) |

원칙: 수집·대량 보관은 실제로 업로드가 되는 GPT, 측정·대조·통합은 서버에서 영상을 프레임 단위로 다룰 수 있는 Claude, 독립 검증은 Gemini.

## 2. 메타데이터 감사 결과 (Claude, 완료) [실측]

GPT의 `corpus_collection_manifest_2026-10-17.jsonl`(공개 링크로 받음)과 Claude의 `data/catalog.csv`를 post_id·md5로 대조했다.

| 항목 | 결과 |
|---|---|
| manifest 행 | 368 (verified 358, 에반게리온 제외 10) |
| catalog yutaka 행 | 368 |
| catalog에만 있음 / manifest에만 있음 | 0 / 0 |
| 제외 10건이 보관됨 | 0 |
| 보관 안 됐는데 제외도 아님(누락) | 0 |
| md5 기대값≠실제 | 0 |
| manifest md5 ≠ catalog md5 | 0 |
| 보관본 md5 중복 | 0 |
| Drive 크기 검증 실패 | 0 |
| ZIP 수 | 42 (+ 메타데이터 ZIP 1) |
| presumed 보관 | 60 |
| Claude 관찰 28건 중 보관 안 된 것 | 0 |
| 파일 형식 | mp4 277, jpg 54, gif 14, png 13 |

**장면 중복(파일은 다름):** 보관본 중 74건이 Sakugabooru `parent_id`를 갖고, 그중 **71건은 부모 게시물도 보관됨**(예: 306329의 하위 7건, 250758의 하위 2건). 같은 장면의 GIF·스크린샷·다른 판본이다. **지우지 않는다.** 대신 통계·규칙 근거를 셀 때 부모-자식을 한 장면으로 센다.

아직 하지 않은 것: 다른 인코딩·재편집으로 같은 장면인데 parent_id가 없는 경우(시각 대조 필요), 모든 영상 전체 디코딩 검사, ZIP 40개 직접 다운로드 검사(표본 2개만 함).

## 3. GPT에게 맡기는 일 (순서대로)

### ① nian41 원본 Drive 보관

Claude 서버의 업로드가 자동 승인 검토에서 막혀, nian41 원본 보관을 GPT가 맡는다. GPT의 yutaka 방식(독립 ZIP ≤90MiB + `manifest.json`, `originals/<id>_<md5>.<ext>`)을 그대로 쓴다. 위치: `AI-sfa/01_원본영상/nian41/`.

- Sakugabooru `nian41` 태그 36개: `https://www.sakugabooru.com/post?tags=nian41`. md5는 `catalog.csv`의 nian41 행과 같아야 한다.
- nian41 본인 X 영상 12개(본인 게시 A등급). 아래 URL은 공개 영상 주소이며 Claude가 받은 파일의 md5·크기를 함께 적었다. 화질 변형이 달라 md5가 다를 수 있으니, 다르면 GPT가 받은 파일의 md5를 새로 기록하고 표시한다.

| X 글 ID | 연도 | 영상 URL | Claude 받은 md5 | 크기(B) |
|---|---|---|---|---|
| 1534075160545878017 | 2022 | https://video.twimg.com/ext_tw_video/1534075102643597314/pu/vid/1280x520/uRGXkj6FWa7Jg27-.mp4 | d6ef4c6fddd2010a256b8bcc56d76d6f | 4191205 |
| 1534078885696000000 | 2022 | https://video.twimg.com/ext_tw_video/1534078818415259648/pu/vid/1280x520/VqdwKsOLFbQR6qZ7.mp4 | 2e5cb28d1e769a59ee0e4eab3f41a95b | 1477438 |
| 1567691748968906752 | 2022 | https://video.twimg.com/ext_tw_video/1567691674331287552/pu/vid/444x248/r44oSAbZwFOI4Itr.mp4 | ac9d89b0cd99e6aa0e8681a9b60caa8a | 331073 |
| 1569962812805644289 | 2022 | https://video.twimg.com/ext_tw_video/1569962730874093570/pu/vid/444x722/9G0zx1Vqiiqb3mBF.mp4 | 4346b8f7688d3d2006cb0655ac00998f | 548545 |
| 1613887197383622656 | 2023 | https://video.twimg.com/ext_tw_video/1613886859045896192/pu/vid/1280x720/vCi4hDosMqM8gILO.mp4 | 1f9d120986c0340b4a682aea30f0545b | 11094542 |
| 1613887377965211649 | 2023 | https://video.twimg.com/ext_tw_video/1613887069633540099/pu/vid/1280x720/KnnUsMF5dViFRhPL.mp4 | eabb78ed56ed4ea7e2ebea3dd2541f48 | 17157874 |
| 1913231262086463573 | 2025 | https://video.twimg.com/amplify_video/1913230817725382656/vid/avc1/1152x720/NNSRXlDNZ-Tyqx-H.mp4 | 26683118ab962259deab0df613a2c113 | 34716419 |
| 1913481070839742689 | 2025 | https://video.twimg.com/amplify_video/1913480806426980352/vid/avc1/872x480/_TvwueNlbClzDGkp.mp4 | 22d2ac9254364a8238c431184d356848 | 5758319 |
| 1913589758644908348 | 2025 | https://video.twimg.com/amplify_video/1913589621298270208/vid/avc1/1280x718/oyUiv5h9iOyXhCyO.mp4 | 50ad133dd0e6d7f3e8476420128bcb59 | 10495930 |
| 1937399147772137658 | 2025 | https://video.twimg.com/amplify_video/1937398858709106688/vid/avc1/666x1082/JB_gtpJy6f-UBipj.mp4 | 0bc3238b5c02eea82e02247666af2834 | 27570954 |
| 1943223713455051062 | 2025 | https://video.twimg.com/amplify_video/1943223503043399681/vid/avc1/1280x720/PIcrvOcWgAX6WPKE.mp4 | 2031669cd3f9d51a0fb0e3687f322709 | 32126627 |
| 2029588466376511962 | 2026 | https://video.twimg.com/amplify_video/2029588131645992960/vid/avc1/1280x720/0S54oiZ2EPjIcy2I.mp4 | 092fcdc2f2485814f6c17d0179d1bcc1 | 17879247 |

  - manifest에 X 글 URL(`https://x.com/nian4111/status/<ID>`), 본문 요지(`docs/NIAN41-SOURCES-2026-10-17.md`), 대응 Sakugabooru post를 함께 적는다.
- 끝나면 `corpus_collection_manifest`와 같은 형식의 nian41 manifest를 `00_목록`에 둔다. Claude가 2절과 같은 방식으로 대조한다.

### ② yutaka 외부 영상 7개

catalog와 장면 중복(재인코딩 포함)인지, 담당 구간이 증명되는지 검토한다. 학습 편입은 지금처럼 보류. 에반게리온(taisen_nge09)은 학습 제외 유지.

### ③ yutaka 분석 계속

- 대상: 보관된 일반 태그 298건 중 Claude 28 + GPT 30을 뺀 것. presumed 60건은 계속 별도.
- **순서:** 최근작부터. 각 기법은 구작에도 있는지 함께 적어 '구작·최신작 공통'을 표시한다(사용자 지시: 공통 기법 중요도 상향).
- 부모-자식(parent_id) 묶음은 한 장면으로 센다.
- 형식은 `gpt_observations_2026-10-17.jsonl`과 같게 하고, `era`(방영·공개 연도)와 `old_new_common`(true/false/미확인) 필드를 추가한다.

### ④ impact_frames 분류 (사용자 예시 이미지 도착 후)

yutaka 보관본 중 `impact_frames` 태그가 있거나 관찰에서 임팩트 프레임이 보인 것을 **연필 느낌 / 디지털 단색 / 불확실**로 나눈다. 연필 느낌만 학습 대상(사용자 필수 조건). Claude가 일부를 표본으로 다시 본다.

## 4. Claude가 하는 일

1. GPT 관찰 30건 교차 판독: 239063·229682·202164·224077·301585 먼저, 이어 나머지를 표본으로. 판독이 같으면 `observations.jsonl`에 `evidence: "GPT 시각 판독"`으로 병합하고, 다르면 양쪽 판독을 함께 남긴다.
2. nian41 몸 움직임: 본인 작화 3개(초능입방 원화 3, 곤탄천하, Primitive Flame 1부) 연속 프레임 판독.
3. GPT nian41 manifest가 오면 2절 방식으로 대조.
4. Gemini 결과가 오면 Claude 규칙과 대조해 지식베이스에 반영.

## 4-1. GPT 대조 답변 반영 (v1.1, 2026-10-17)

GPT 답변(`docs/GPT-TO-CLAUDE-RECONCILIATION-2026-10-17.md`)은 이 조정안 이전에 쓰였다. 반영 사항:

- **ZIP 내용 CSV**(`00_목록/GPT-YUTAKA-ZIP-CONTENTS-2026-10-17.csv`, PDF 사본 사용자 제공): Claude가 PDF 텍스트를 추출해 manifest와 대조 [실측] — 358행, post_id·md5 358/358 일치, 차이 0.
- **연도 기준 합의:** 장면이 들어간 판본의 **최초 방영·공개일**(TV 회차 첫 방송일, 극장판 최초 개봉일, 독립작 최초 공식 공개일). 게시일·재업로드일은 쓰지 않는다. 수정판은 원작일과 분리. 근거 없으면 미확인. 3절 ③의 `era`는 이 기준을 따른다.
- **임팩트 예비 분류(GPT 30건, [추론]):** `data/style_kb/impact_prelim_gpt_2026-10-17.csv`. 연필 느낌 후보 2(280210, 281565), 디지털 단색 9, 불확실 18, 에반게리온 제외 1. 사용자 예시와 대조한 최종 채택은 0건. 3절 ④에서 예시 도착 후 확정한다. 분류 단위는 프레임이며 클립 전체 제외가 아니다.
- **감사 역할:** GPT 답변의 "담당 미정"은 이 조정안으로 대체된다. 메타데이터 감사는 Claude가 끝냈고(2절), 장면 중복 시각 대조·전체 디코딩 검사는 아직 미배정이다 — 필요해지면 Claude가 추가 배정한다.

## 4-2. 변경 (v1.2, 2026-10-17)

- **GPT 담당 ① 취소 — nian41 원본은 Claude가 보관 완료.** 사용자가 Drive 업로드·수정 권한을 다시 허가했고, 이번에는 서버 업로드가 통과했다. `01_원본영상/nian41/`에 Sakugabooru 36(catalog md5와 Drive md5 일치) + 본인 X 영상 12(`x_self_posts/`, 로컬과 Drive md5 일치) = 48개, 753.4 MB [실측]. 목록: `00_목록/nian41_drive_manifest_2026-10-17.jsonl`(저장소 `data/sources/`). GPT는 nian41 원본을 다시 받지 않는다.
- **자체 태그 규칙 추가:** `docs/TAG-RULES-2026-10-17.md`, `data/style_kb/tag_overrides.csv`. 새 태그 `impact_frames_pencil`(학습)·`impact_frames_digital`(제외). 영상에 보이는데 Sakugabooru 태그가 없으면(예: yutapon_cubes) 보정 파일에 add. GPT 담당 ④(impact 분류)와 ③(분석)은 이 태그와 파일 형식을 쓴다.
- 사용자 지시로 위 범위 외 작업은 대기한다.

## 4-3. Gemini 지시 갱신 (v1.3)

Gemini 최신 기준은 `docs/GEMINI-NEW-SESSION-PROMPT-2026-10-17.md`(새 대화용 단독 프롬프트, UPDATE-PROMPT를 대체). 작업 A 후보 6명 평가(임팩트 연필/디지털·구작·최신작 지속성 추가), B nian41 규칙 검증(대상 영상이 본인 작화 확정임을 명시), C 승낙 작가 편입 절차 검토. 앞선 GEMINI-PASTE는 대체된다.

## 5. 공통 규칙

- 사용자 최신 기준: impact_frames 연필 느낌만(최중요), 구작·최신작 공통 기법 가중, 에반게리온 제외, nian41은 몸 움직임만.
- 원본·contact sheet는 공개 GitHub에 올리지 않는다. 삭제는 사용자 승인 없이 하지 않는다.
- 결과는 사용자를 통해 서로 전달한다. 충돌이 생기면 Claude가 이 문서를 고쳐 조정한다.
