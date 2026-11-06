# SFA 구조·그리는 단어체계 — 후속 검토용(2026-11-06)

```text
AI-sfa, claude/new-session-gknz4t 브랜치만 사용(main 금지), 한국어로 답한다.
사용자는 SFA 구조 관련 시스템 조사에 이어 “스파가 애니메이션을 그리는 방식인 단어체계도 포함”이라고 명시했다.
AGENTS.md → HANDOFF.md → docs/GPT-SFA-STRUCTURE-VOCABULARY-2026-11-06.md 전체를 읽는다.

출처/코드 지문: data/research/sfa_structure_sources_2026-11-06.json (15시스템, 선택 파일16개).
합성 CPU 근거: tools/sfa_structure_probe.py, data/research/sfa_structure_probe_2026-11-06.json.
OpenToonz의 TThickQuadratic와 TEdge(stroke/w0/w1), Synfig의 공유 값, VAC의 시간별 위상, fontTools 곡선 변환, DeepSVG/StrokeNUWA/OmniSVG/StarVector의 학습 어휘를 비교했다.

핵심:
- 실제 SFA 저장 요소 / 그리기·편집 의미 / 우리가 만든 학습 어휘를 구분한다.
- 현재 sfa_tokens는 이미 도형/연결/면 의미를 담지만 한 장 렌더 목적이라 Flags를 버린다. 합성 왕복에서 선2·점4·좌표집합·AC수2가 유지돼도 관절 역할은1→0이다. 이 반례를 새 앱 검증이나 현재 compose의 공통 결함으로 확대하지 않는다. 스틱맨은 별도 편집망 컴파일러를 쓴다.
- AC를 모두 관절/좌표 동일화로 취급하지 않는다. FR은 선별 T 구간이며 AC 없는 선으로도 칠할 수 있다.
- fontTools 비교는 합성 좌표 단위/4001표본이다. S곡선은 기존2조각 오차5.41299, 적응14조각0.09060(허용값0.1). 여러 변형의 조각 수 맞춤은 의미적 대상 대응/FS remap을 대신하지 않는다.
- 그림/편집/장간 대상 보존을 따로 검사한다. 새 단어체계는 미채택 초안이며 기존 기본값·모델·규칙은 바꾸지 않았다.

기존 진동→가면→걷기 수정은 뒤이은 구조 검토로 보류·미완. 외부 편집기/모델·새 GPU/학습/유료 API/사용자 원본 다운로드 없음. 후속은 보존할 편집 의미를 포함한 작은 표현 왕복 비교부터 제안한다.

보고서 §9의 추가4후보도 읽는다: Vitruvion/SketchGen의 도형+참조 제약 학습을 우선하고, LayerInbetween의 가림/장간 획 대응, GarmentCode의 곡선 부품/인터페이스를 후속으로 둔다. 초기 공식 자료 대조이며 SFA 적용/실행은 미검증이다.
```
