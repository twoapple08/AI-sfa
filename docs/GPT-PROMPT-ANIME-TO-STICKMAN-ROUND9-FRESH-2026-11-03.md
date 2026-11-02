# GPT 새 세션용 프롬프트 — 스틱맨 토론 9차 답 + 시제품 1 검토 (2026-11-03)

아래 블록 전체를 새 GPT 세션에 붙여 넣는다. GPT는 GitHub 저장소와 Google Drive를 직접 볼 수 있으므로, 파일은 경로로 가리키고 내용을 붙이지 않는다.

```
AI-sfa 프로젝트의 'Claude ↔ GPT 토론'을 이어서 한다. 모든 답은 한국어로만 쓴다.

[저장소·브랜치]
- GitHub: twoapple08/AI-sfa, 브랜치 claude/new-session-gknz4t (main은 옛 단계라 읽지도 쓰지도 않는다)
- Google Drive: AI-sfa 폴더(아래 경로)

[주제]
"애니 사람 캐릭터의 움직임을 스틱맨(Stick Fighter 앱 .sfa)으로 어떻게 전환할까." Claude와 GPT가 근거로 토론하고, 채택은 사용자가 정한다. 3D는 배제하지 않지만 3D에 매몰되지 않는다(2D와 같은 자리에서 실험으로 겨룸). 필수 조건은 앱에서 연결 유지 + 포즈 편집 가능이다.

[먼저 읽을 것 — 이 순서로, 필요한 부분만]
1. AGENTS.md: '스틱맨 움직임'과 맨 아래 (11-02 밤) 애니 → 스틱맨 항목
2. HANDOFF.md: '현재 우선순위'와 '바로 할 일 2'
3. docs/ANIME-TO-STICKMAN-DEBATE-2026-11-02.md: 맨 끝의 '8차 — GPT 답' 요약, '9차 — Claude 답', '9차 보완', '사용자 판정·지시 기록'
4. 네(GPT) 지난 답: docs/GPT-ANIME-TO-STICKMAN-ROUND8-2026-11-02.md, docs/GPT-ROUND8-GEOMETRY-AUDIT-2026-11-02.json
5. 시제품 1 보고: docs/STICKMAN-PROTO-2D-B300-334-2026-11-03.md, 수치 data/stickman_motion/proto2d_B300-334_report_2026-11-03.json
6. 코드: tools/rtmw_to_stickman_2d.py, tests/test_rtmw_to_stickman_2d.py, tools/drawing_segments.py(check_verified), tests/test_check_verified.py

[Drive 자료]
- 시제품 1 산출물: AI-sfa/02_분석자료/stickman_proto_2026-11-03/
  - B300-334_compare.mp4(24fps), B300-334_compare_slow.mp4(6fps): 원본 | 원본 + 피팅(초록 왼쪽·주황 오른쪽, 노랑 RTMW, 빨강 X = 뺀 점) | SFA 렌더
  - B300-334_2d_L90sym.sfa, B_joints.json(장별 관절 px), B_report.json, B300-334_compare_sheet.jpg
- 입력: 원본 AI-sfa/01_원본영상/nian41/x_self_posts/1913231262086463573.mp4(SHA-256 57369470…), RTMW AI-sfa/02_분석자료/포즈_RTMW/nian41/1913231262086463573.jsonl.gz(SHA-256 6c790516…)

[해 줄 것]
1. 9차 Claude 답과 9차 보완에 대한 동의·반박·보완을 근거와 함께 짧게. 특히
   - 중점 모델 24/13 채택, 2D 고정 반폭의 약점(실제 RTMW 골반 폭 0.325–0.421, 어깨 폭 0.503–0.693/몸통)과 '2D 장별 가로폭 배율은 별도 조건'이라는 처리
   - 시제품 1이 '대상 × 범위 상수 배율'을 깨고 장별 배율을 쓴 것, L90 리그에서 몸통이 35/35장 짧아진 불균형
2. 9차 6번 질문 — 진행 방식 전환(토론은 결정이 필요할 때만, 구현 세부는 Claude가 바로 만들고 GPT는 결과물을 검토)에 동의·반대와 이유, 반대면 대안
3. 시제품 1 결과물 검토(2차 의견, 사용자 판정이 최종): 비교 영상을 원본 크기로 보고, 원본 동작으로 읽히는지, 가장 어색한 장과 원인 후보(리그·배율·관측 오류·가림 등)를 장 번호로. 작은 시트만으로 단정하지 말 것.

[지킬 것]
- 근거 표시를 구분한다: 파일·코드 확인 / CPU 계산 / 인공 검산 / 원본 영상 눈 판독 / 추론·제안. 인공 검산을 실제 애니 품질 측정으로 옮겨 적지 않는다.
- 2D 시제품 우선 진행을 유지한다. 새 측정 라운드나 긴 반박 라운드를 열지 않는다.
- GPU 실행·학습을 하지 않는다. 원본 영상·추출 프레임을 저장소에 올리지 않는다. 기존 판정 기록(docs/CLAUDE-*·GPT-* JSON)은 고치지 않는다. 애니메이터별 학습 범위 규칙은 다시 해석하지 않는다.

[저장]
- 답 전문(요약 아님)을 docs/GPT-ANIME-TO-STICKMAN-ROUND9-2026-11-03.md로 claude/new-session-gknz4t 브랜치에 저장한다. 계산 자료가 있으면 docs/GPT-ROUND9-*.json으로 함께 둔다. main에는 쓰지 않는다.
- 저장 전에 브랜치 최신을 다시 받아 다른 변경을 덮지 않는다.
- 저장 뒤 사용자에게 커밋 SHA, GitHub 링크, Claude에게 붙여 넣을 짧은 전달 문구 하나를 준다.
```
