# 인수인계 프롬프트 (2026-10-27 밤 — 영상 스타일 AI 1단계, GPT↔Claude 태그 토론)

https://github.com/twoapple08/AI-sfa 작업을 이어서 한다. 작업 브랜치는 `ccr-bccf15a6-d6ee46`이다. 시작할 때 fetch·merge하고, 시스템이 다른 브랜치를 배정하면 같은 HEAD를 그 브랜치에도 푸시한다. **모든 답을 한국어로만 쓴다.**

**읽기 순서:** AGENTS.md → HANDOFF.md(현재 우선순위·바로 할 일·막힌 것·환경) → docs/DEBATE-SHOT-TAGS-2026-10-27.md(토론 쟁점과 Claude 입장). 필요할 때만 docs/REVIEW-GPT-SHOT-TAGS-2026-10-27.md(Claude 검토), docs/GPT-REVIEW-SHOT-TAGS-2026-10-27.md(GPT 검토), docs/REF-SFA-FILE-BUILDER-2026-10-27.md(SFA 로딩·가볍게 만들기).

## 목표 한 줄
지금은 1단계: 나카무라 이펙트 **영상** 스타일 AI(Wan2.1 T2V 1.3B LoRA). SFA 변환은 2단계.

## 이번 세션의 진행 방식 — 토론
- 사용자가 GPT와 Claude 사이 메시지를 중계한다. GPT 메시지가 오면 **반대할 것은 근거(시트 장 번호·측정값)로 반대하고, 맞는 것은 인정하고, 더 나은 방법이 있으면 찾아 제안**한다. 동의를 위해 동의하지 않는다.
- 근거가 필요하면 시트를 직접 보거나 측정한다(scratch가 없으면 HANDOFF '환경'의 Drive 경로에서 필요한 시트만 받는다). 결론마다 무엇이 바뀌는지(태그·학습 자료) 한 줄로.
- 태그가 바뀌면 GPT가 Drive 같은 파일 ID로 갱신 → Claude가 받아 대조 → 저장소 `data/style_kb/ai_results/gpt_SHOT_MOTION_*`에 GPT 원본 그대로 반영 → `tools/wan_lora_dataset.py`로 학습 자료 재생성·검사 → wanlora.zip 같은 Drive ID에 덮어쓰기.
- 토론과 별개로 PC 학습(`tools/pc_wan_lora.bat`)은 지금 자료로 돌려도 된다.

## 사용자와 일하는 방식
- 먼저 답하고 계획(무엇·왜·얼마나)을 말한 뒤 작업. 결과는 영상·시트로 먼저 보여 주고 문제를 정직하게(예측이 틀리면 틀렸다고).
- GPT는 눈 판정·태깅, Claude는 측정·처리·검증·학습 준비·1차 평가. 다 GPT에 맡기지 않는다.
- 3D 금지, SFA 글로우 값은 정수, 24fps 리듬 보존. 원본·결과 SFA/mp4·학습 자료는 Drive·scratch만, 토큰·키 출력 금지.
