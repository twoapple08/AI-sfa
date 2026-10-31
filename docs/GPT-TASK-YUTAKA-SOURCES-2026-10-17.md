# GPT 작업 지시서 2 — yutaka_nakamura 자료 출처 조사 (2026-10-17)

> Claude가 작성했다. 사용자 공통 지시: Sakugabooru뿐 아니라 애니 자료가 있는 모든 사이트를 찾아, GPT는 **yutaka_nakamura(中村豊)가 그렸다고 증명된 자료**를, Claude는 nian41 자료를 모은다. 태그가 붙는 사이트일수록 좋다. Claude의 nian41 결과와 합칠 수 있도록 형식을 맞춘다.

참고 예시(Claude의 nian41 결과): https://github.com/twoapple08/AI-sfa/blob/ccr-bccf15a6-d6ee46/docs/NIAN41-SOURCES-2026-10-17.md

> **2026-10-17 사용자 변경:** GPT 작업은 'yutaka_nakamura 30클립 관찰'에서 **'세상에 공개된 yutaka_nakamura 자료를 모두 수집한 뒤 분석 진행'**으로 바뀌었다. 30클립 contact sheet는 GPT의 출발 자료로 Drive 02에 그대로 둔다. 이 문서가 GPT의 첫 작업이다. 수집이 끝나면 [지시서 1](GPT-TASK-YUTAKA-EFFECTS-2026-10-17.md)의 관찰 형식으로 분석을 이어 간다.

## 할 일

1. yutaka_nakamura가 담당한 컷·작품을 증명하는 자료가 있는 사이트를 찾는다. 예: Sakugabooru(이미 368개 색인됨), 作画@wiki(atwiki), seesaawiki 스태프 DB, 공식 사이트·공식 SNS 스태프 코멘트, 인터뷰, 원화집·설정집, 블루레이 해설, 크레딧 DB(MyAnimeList, AniDB, ANN, AniList), 본인 SNS가 있다면 그것.
2. 각 자료에 증명 등급을 붙인다.

| 등급 | 뜻 |
|---|---|
| A 본인 게시 | 본인이 직접 담당을 밝힌 자료(본인 SNS, 본인 인터뷰 발언) |
| B 공식·DB 크레딧 | 회차 크레딧, 제작사·감독의 공식 언급, 크레딧 DB |
| C 커뮤니티 태그 | Sakugabooru 등 태그(출처 표기 확인) |
| D 팬 귀속 | 팬 편집·게시물 |

3. 특히 **같은 회차 안에서 어느 컷이 yutaka_nakamura인지** 밝힌 자료(A·B)를 찾는다. Sakugabooru의 `presumed` 61개는 추정이므로, 이를 확정하거나 반박하는 자료가 있으면 따로 표시한다.

## 출력 형식

CSV 한 표(UTF-8). 열 이름은 Claude 것과 같게 한다.

```
site,url,kind,work,proof_level,effects_use,note
```

- `effects_use`: 이펙트·배경·연출 학습에 쓸 수 있는지(최우선/보조/참고/-).
- `note`: 어느 장면·컷인지, 출처 문장 요약, 확인하지 못한 점.
- 확인하지 못한 것은 추측으로 채우지 않는다. "미확인"이라고 쓴다.
- 마지막에 찾아본 사이트 목록(찾았음/없음/접속 불가)을 짧게 붙인다.

## 금지

- 영상·이미지 원본을 공개된 곳에 올리지 않는다. 이번 작업은 **출처 목록(메타데이터)만** 만든다.
- 로그인 차단·접근 제한을 우회하지 않는다.
- 토큰·키를 출력하지 않는다.

## 돌려주는 방법

사용자가 GPT 출력(CSV + 요약)을 Claude에게 붙여 넣는다. Claude가 `data/sources/yutaka_nakamura_sources.csv`로 저장하고 몇 행을 직접 확인한 뒤 지식베이스에 연결한다.
