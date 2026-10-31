# GPT 작업 1 — yutaka_nakamura 358건 연도표 (2026-10-17, Claude 조정)

조정안 `COORDINATION-PHASE2-2026-10-17.md`의 순서 1번이다. **이번에는 연도표만** 한다. 임팩트 재판정(순서 11)은 Claude가 `02_분석자료/impact/` 시트를 올렸다고 사용자가 알려 줄 때까지 대기한다. 시트 없이 예비 분류로 대신하지 않는다.

## 대상

Drive에 보관한 yutaka_nakamura 358건 전부(일반 태그 298 + presumed 60). 에반게리온 10건은 제외 상태 그대로 둔다. 기준 목록은 GPT의 `corpus_collection_manifest_2026-10-17.jsonl`이다.

## 연도 기준 (합의된 정의)

- **그 장면이 실린 판본의 최초 방영·공개일.**
  - TV: 그 회차의 첫 방송일(일본 첫 방송 기준).
  - OP·ED: 그 OP·ED가 처음 방송된 회차의 방송일.
  - 극장판: 최초 개봉일(일본 기준).
  - OVA·웹·광고·뮤직비디오: 최초 공식 공개일.
- Sakugabooru 게시일, 재업로드일, 블루레이 발매일은 쓰지 않는다. 단, 블루레이에서 작화를 고친 판본이면 `episode`에 BD라고 적고 원래 방송일과 BD 발매일을 `note`에 둘 다 적는다.
- 회차 특정: Sakugabooru `source`(예: `#25 (S2 #12)`, `NCOP2`, `BD`)와 작품 태그로 정한다. 통산 회차와 시즌 회차가 같이 있으면 둘 다 적는다.
- 같은 장면의 다른 판본(parent_id로 묶인 GIF·스크린샷·원화 비교 등)은 부모 게시물과 같은 날짜를 쓴다.
- 일러스트·원화 사진처럼 방영 장면이 아닌 자료는 `episode`에 종류를 적고, 공개일을 알면 그 날짜, 모르면 미확인.

## 출력

CSV(UTF-8), 358행. 열 이름은 정확히 아래와 같다.

```
post_id,work,episode,era_date,era_year,basis_url,confidence,note
```

- `era_date`: YYYY-MM-DD. 일까지 모르면 YYYY-MM 또는 YYYY.
- `basis_url`: 날짜 근거 페이지(공식 사이트, 방송 목록, 위키 등). 여러 건을 같은 근거로 쓰면 같은 URL을 반복한다.
- `confidence`: `high`(공식·방송 목록으로 회차와 날짜 둘 다 확인) / `medium`(회차는 확실, 날짜는 2차 출처) / `low`(회차 추정) / `unknown`(못 찾음, `era_date` 비움).
- `note`: 판단 이유, BD 수정 여부, 회차 추정 근거.

저장: Drive `AI-sfa/00_목록/yutaka_era_table_2026-10-17.csv`. 끝나면 사용자에게 링크와 함께 요약(행 수, confidence별 개수, 가장 오래된·최신 연도, unknown 목록)을 보내 준다.

## 규칙

- 모르는 것은 추측으로 채우지 않는다. unknown으로 둔다.
- 영상·이미지를 공개된 곳에 올리지 않는다. 로그인 차단을 우회하지 않는다.
- 다른 작업(분석·임팩트·삭제)은 하지 않는다.
