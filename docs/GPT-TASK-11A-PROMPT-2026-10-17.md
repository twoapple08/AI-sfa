# GPT 작업 11a 시작 메시지 (2026-10-17)

권장 설정: GPT 최상위 추론 모델, 추론 강도 높음. 작업 9를 한 같은 대화에 보낸다.

---

작업 9 결과는 Claude가 확인해 반영했어. 연필 9구간은 전부 confirmed가 됐어. 8구간은 Claude가 원본 프레임으로 대조해 일치했고, 290900 157은 사용자가 직접 보고 "섞였지만 연필 비중이 더 크다"고 판정해서 연필로 넣었어. 형식 검사(115구간 누락 0, 같은 태그 중복 0)도 통과했어. 보고서: Drive `03_스타일지식베이스/IMPACT-PENCIL-CROSSCHECK-2026-10-17.md`.

이제 **작업 11a — 최근작 97건 분석 + 임팩트 분류**를 시작해 줘. 조정안(`COORDINATION-PHASE2-2026-10-17.md`) 2단계의 GPT 몫이야. Claude는 같은 시간에 11b(구작·연도 미확인 144건)를 해.

**자료 (Drive `AI-sfa/`)**
- 목록: `02_분석자료/작업목록_11a_GPT_2026-10-17.csv` (97건 = 영상 80 + 이미지·GIF. 열: post_id, url, era_year, work, ext, parent_id, folder). 범위는 era 2009년 이후야.
- 게시물별 분석 자료: `02_분석자료/<post_id>/contact_sheet.jpg`, `timing.json`. 작업 1–9 때와 같은 형식이야.
- 임팩트 후보: `02_분석자료/impact/impact_candidates_rest.csv` (열: post_id,start,end,pre_class). 연속 프레임 시트는 `02_분석자료/impact/<post_id>/f시작-끝.jpg`. 후보가 없는 게시물은 폴더에 impact.json만 있어.
- 원본은 네가 보관한 358건을 써. 시트만으로 판단이 안 서면 원본을 프레임 단위로 열어 봐.
- 기준: `03_스타일지식베이스/TAG-RULES-2026-10-17.md`(연필/디지털 정의, 섞인 프레임 처리), `impact_reference/`(연필·디지털 예시).

**규칙**
1. 학습 범위는 이펙트·배경·연출뿐이야. 에반게리온은 목록에 없지만, 보이면 제외로 표시만 해.
2. parent_id로 묶인 같은 장면의 다른 판본(GIF·스크린샷)은 한 장면으로 세. 따로 관찰을 쓰지 말고 대표 게시물에 `same_scene` 목록으로 붙여.
3. 각 관찰에 `old_new_common`을 붙여: 이미 지식베이스에 있는 구작(2008년 이전) 기법과 같은 것이 보이면 true, 아니면 false, 판단 불가는 "미확인". true면 어떤 기법인지 한 줄로 적어.
4. 임팩트 분류는 작업 9와 같은 방식이야. 연필은 `impact_frames_pencil`, 디지털은 `impact_frames_digital`, 판단이 안 서면 `impact_frames` + uncertain. 섞인 프레임은 비중이 큰 쪽으로 분류하고 basis에 "섞임(연필 우세)"처럼 적어. 흐린 가로 문지름 결은 블러로 오판하기 쉬우니 애매하면 uncertain으로 둬.
5. 연필 판정은 모두 candidate로 내 줘. Claude가 표본을 원본으로 대조해서 두 AI가 일치하면 confirmed로 올려.
6. Sakugabooru 태그에 없는데 보이는 기법(yutapon_cubes, debris, smears 등)은 태그 보정 행(add)으로 적어. 근거 프레임 번호를 꼭 넣어.
7. 판독은 전부 [추론]으로, timing.json 수치는 [실측]으로 구분해. 원본·시트는 공개 업로드하지 마.

**출력 (Drive `03_스타일지식베이스/`에 올리고 링크를 알려 줘)**
- `gpt_observations_11a_2026-10-17.jsonl`: 작업 1차 `gpt_observations_2026-10-17.jsonl`과 같은 필드(post, artist, work, timing, timing_note, effects, direction, background, sfa, url, evidence, credit, era_year, era_confidence, learn_scope)에 `old_new_common`, `same_scene`을 더해.
- `impact_rejudge_11a_2026-10-17.csv`: 열은 `post_id,tag,action,frames,basis,grade,status`(작업 9와 같음).
- 짧은 보고서 `GPT-11A-REPORT-2026-10-17.md`: 집계(관찰 수, 같은 장면 묶음 수, 연필·디지털·불확실 구간 수, old_new_common true 수와 대표 기법), 못 연 파일과 이유.

양이 많으면 40건쯤씩 나눠서 중간 결과를 먼저 올려도 돼. 그럴 땐 파일 이름에 `_part1`처럼 붙여 줘.
