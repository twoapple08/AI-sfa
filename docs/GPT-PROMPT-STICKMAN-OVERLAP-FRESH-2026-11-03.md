# GPT 새 세션 프롬프트 — 스틱맨 인물 겹침 다리 버그 토론 1차(2026-11-03)

아래 블록 전체를 새 GPT 세션에 붙여 넣는다. GPT는 GitHub·Drive를 직접 본다.

```
AI-sfa 프로젝트의 'Claude ↔ GPT 토론'을 새로 시작한다. 모든 답은 한국어로만 쓴다.

[저장소·브랜치]
- GitHub: twoapple08/AI-sfa, 브랜치 claude/new-session-gknz4t (main은 옛 단계라 읽지도 쓰지도 않는다)
- Google Drive: AI-sfa 폴더

[배경 한 줄]
애니(nian41 영상) 인물의 움직임을 RTMW 2D 관절 → 키포즈 피팅 → Stick Fighter 앱 .sfa 기본 스틱맨으로 바꾼다. 두 인물(파랑·빨강) 10초 구간까지 만들었고, 사용자가 '인물끼리 겹치는 곳에서 다리를 못 따라가거나 쭉 뻗은 다리를 못 잡는' 버그를 짚었다. 이 버그와 비슷한 버그를 찾아 고치는 것을 토론 형식으로 정한다. 채택·눈 판정은 사용자가 한다.

[먼저 읽을 것 — 이 순서로]
1. docs/STICKMAN-OVERLAP-BUGS-2026-11-03.md (이번 토론의 출발 문서: 사용자 지시, 근거 표, 원인 가설 1–4, 지킬 것)
2. docs/STICKMAN-CLIP-1032-1271-2026-11-03.md (지금까지의 처리와 리뷰 1·2 경과)
3. 코드: tools/stickman_clip.py, tools/rtmw_to_stickman_2d_v2.py(run_core, keypose_fit, fit_all, smooth_keys, leg_facing, fix_knees, fix_edge_side), tools/rtmw_to_stickman_2d.py(pick_target strict), tools/stickman_variants.py(basic_joints)
4. 필요하면: HANDOFF.md의 '바로 할 일 2', AGENTS.md의 스틱맨 관련 항목

[Drive 자료] AI-sfa/02_분석자료/stickman_proto_2026-11-03/
- overlap_bugs/user_marked_1187-1227.jpg (사용자가 동그라미 친 3곳: 빨강 1217·1222·1227)
- overlap_bugs/overlap_evidence_1212-1230.json (빨강 다리 RTMW 점·점수·주변 색·화면 끝, 사람 수, 상자 IoU, 출력 위치)
- clip1032-1271/ (SFA, 비교 영상, joints.json, report.json)
- 입력: 01_원본영상/nian41/x_self_posts/1913231262086463573.mp4, 02_분석자료/포즈_RTMW/nian41/1913231262086463573.jsonl.gz

[1차에서 해 줄 것 — 네가 먼저 독립 분석]
1. 표시된 3곳(빨강 1217·1222·1227)의 원인을 원본 크기 프레임과 RTMW 원자료로 판정해 줘. 문서의 가설 1–4 각각 지지/반박/판단 불가를 근거와 함께. 다른 원인이 있으면 추가.
2. 240장 전체에서 비슷한 버그(겹침·사람 수 3명 이상·상자 쪼개짐·다른 인물 색 위의 점·뻗은 팔다리가 짧아짐 등)를 찾는 판별 기준을 제안하고, 가능하면 실제로 돌려 후보 장 목록을 내 줘(장 번호, 인물, 부위, 증상, 근거 종류).
3. 고칠 방법 후보를 우선순위로(예: RTMW 사람 합치기·재배정, 관측 신뢰도 낮추기, 길이 상한/분위, 키 고르기에서 이상 키 제외 등). 각 후보의 반례·부작용도 같이.
4. Claude에게 확인하거나 측정을 부탁할 것.

[지킬 것]
- 근거 표시를 구분한다: 파일·코드 / CPU 계산 / 원본 눈 판독 / 추론·제안. 작은 시트만으로 단정하지 말고 원본 크기로 본다.
- 원본 영상·추출 프레임·관절 원좌표 전체를 저장소에 올리지 않는다(소량 발췌 표는 가능). 기존 판정 기록 JSON(docs/CLAUDE-*·GPT-*)은 고치지 않는다. 코드는 고치지 말고 제안만 한다(구현은 Claude).
- GPU 실행·학습을 하지 않는다. 기본 스틱맨·직선 몸통 유지(곡선·실루엣 보류).

[저장]
- 답 전문(요약 아님)을 docs/GPT-STICKMAN-OVERLAP-ROUND1-2026-11-03.md로 claude/new-session-gknz4t 브랜치에 저장한다. 계산 자료는 docs/GPT-STICKMAN-OVERLAP-ROUND1-*.json으로(원좌표 전체 금지). main에는 쓰지 않는다. 저장 전에 브랜치 최신을 받아 다른 변경을 덮지 않는다.
- 저장 뒤 사용자에게 커밋 SHA, GitHub 링크, 새 Claude 세션에 붙여 넣을 짧은 전달 문구 하나를 준다.
```
