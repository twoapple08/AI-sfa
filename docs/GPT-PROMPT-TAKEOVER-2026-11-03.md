# GPT 일시 전담 프롬프트(2026-11-03) — Claude 주간 사용량 소진 대비

사용자가 "GPT에게 맡긴다"고 말하면 아래 블록을 GPT(새 세션 가능)에 붙여 넣는다. Claude가 돌아오면 GPT 작업을 읽고 검토한다.

```
AI-sfa 프로젝트를 Claude 대신 일시적으로 네가 전담한다(사용자 지시: Claude 주간 사용량 소진 기간). 모든 답은 한국어로만 쓴다.

[저장소·브랜치] GitHub twoapple08/AI-sfa, 브랜치 claude/new-session-gknz4t만 쓴다(main은 읽지도 쓰지도 않는다). Google Drive AI-sfa 폴더도 본다.

[먼저 읽을 것] AGENTS.md → HANDOFF.md('현재 우선순위', '바로 할 일') → docs/HANDOFF-PROMPT.md → docs/STICKMAN-OVERLAP-BUGS-2026-11-03.md → docs/STICKMAN-CLIP-1032-1271-2026-11-03.md

[전담 기간 동안 허용·변경]
- 이번 기간에는 분석·제안뿐 아니라 구현도 네가 한다: tools/·tests/ 코드 수정, 시험 실행, 결과물(SFA·비교 영상) 생성, 문서·HANDOFF 갱신, 커밋·푸시.
- Claude가 하던 규칙을 그대로 따른다: 근거 표시 구분(파일·코드 / CPU 계산 / 원본 눈 판독 / 추론), 원본 크기로 판정, 측정으로 가를 것은 측정, 눈 판정·방향 결정은 사용자에게 묻기.
- 커밋 전 저장소 루트에서 `python -m unittest discover -s tests` 전체 통과를 확인한다(실패 시 커밋하지 않고 보고).

[할 일 — 순서]
1. 스틱맨 인물 겹침 다리 버그(빨강 1217 무릎, 1222·1227 쭉 뻗은 발차기, 비슷한 버그): docs/STICKMAN-OVERLAP-BUGS-2026-11-03.md의 가설 1–4를 원본·RTMW로 가르고, 240장 전체 후보를 찾고, 우선순위대로 고친다. 고친 뒤 `tools/stickman_clip.py`(명령은 그 문서에 있음)로 다시 만들어 사용자에게 비교 영상과 SFA를 보여 주고 판정을 받는다. 경과는 docs/STICKMAN-OVERLAP-DEBATE-2026-11-03.md에 'GPT 전담' 표시로 남긴다.
2. 1단계 Kaggle 2회차(aisfa-seq-train 판 7, 예상 종료 11-03 01:00–01:45 UTC): Kaggle에 접근할 수 없으면 사용자에게 Kaggle 출력(log.jsonl, 판정 시트)을 Drive `02_분석자료/seq/run2_2026-11-03/`에 올려 달라고 하고, 올라오면 `tools/seq_trend.py`로 1회차와 같은 조건끼리 비교해 보고한다(그림 먼저). 3회차 실행은 사용자 허락 뒤에만.

[지킬 것]
- 원본 영상·추출 프레임·관절 원좌표 전체·가중치·앱 녹화는 저장소에 넣지 않는다(Drive만, 소량 발췌 표는 가능). 토큰·키를 출력하지 않는다.
- 기존 판정 기록 JSON(docs/CLAUDE-*·GPT-*)은 고치지 않는다. 애니메이터별 학습 범위 규칙은 다시 해석하지 않는다.
- GPU 실행·학습은 사용자 허락 뒤에만. 기본 스틱맨·직선 몸통 유지(곡선 몸통·실루엣 보류).
- SFA 규칙: 점 ID는 장마다 새로, 오브젝트 ID는 장끼리 유지, (24, 24). 화면 틀 밖 좌표 허용.
- 저장 전 브랜치 최신을 받아 다른 변경을 덮지 않는다.

[Claude 복귀 대비]
- 의미 있는 단계마다 HANDOFF.md의 '바로 할 일'을 현재 상태로 갱신하고, 바꾼 코드·이유·검증 결과를 docs/GPT-TAKEOVER-LOG-2026-11-03.md에 날짜순으로 남긴다(커밋 SHA 포함).
- 사용자가 Claude로 돌아간다고 하면 마지막 커밋 SHA와 Claude에게 붙일 짧은 전달 문구를 준다.
```
