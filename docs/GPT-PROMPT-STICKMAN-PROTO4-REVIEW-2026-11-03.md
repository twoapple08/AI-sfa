# GPT 답장 프롬프트 — 스틱맨 시제품 4(A 1500–1523) 결과물 검토(2026-11-03, 기존 GPT 세션용)

```
claude/new-session-gknz4t 브랜치(main 아님)를 받아 줘. 스틱맨 시제품 3(B 300–334, 키포즈 보간)은 사용자가 '부드러워졌다'고 판정했다. 이번에는 같은 방식을 다른 장면 A 1500–1523(파란 인물, 2명 중 선택)에 적용한 시제품 4다. 설계 토론이 아니라 결과물 검토만 부탁한다.

읽을 것: docs/STICKMAN-PROTO4-A1500-1523-2026-11-03.md, tools/rtmw_to_stickman_2d_v2.py(frame_disp, auto_thr, drawing_segments, keypose_fit, forward의 hp·hs), tests/test_rtmw_to_stickman_2d_v2.py, data/stickman_motion/proto4_A1500-1523_report_2026-11-03.json
볼 것(Drive): AI-sfa/02_분석자료/stickman_proto_2026-11-03/A1500-1523/ 의 _compare.mp4·_compare_slow.mp4·.sfa·_joints.json. 원본·RTMW 경로는 시제품 1 때와 같다.

확인해 줄 것(짧게, 근거 표시 구분: 파일·코드 / CPU 계산 / 원본 눈 판독 / 추론):
1. A가 2컷 작화이고 그림 구간 13개(2장씩)가 원본과 맞는가. 어깨 좌우 뒤집힘(1507·1509·1515·1523)이 실제 몸 돌리기인가, RTMW 좌우 바뀜인가(원본 크기로).
2. 가장 어색한 장과 원인 후보(장 번호로). 반폭 벡터 보간이 몸 돌리기를 그럴듯하게 보이게 하는가.
3. 문서의 '여캐·작품별 비율 대비' 메모에 빠진 위험이 있는가.

사용자 판정이 최종이다. 새 설계 라운드를 열지 말고, 문제가 없으면 '이견 없음'과 눈 판독 요약 몇 줄만 답해 줘. 고칠 것이 있으면 전문을 docs/GPT-STICKMAN-PROTO4-REVIEW-2026-11-03.md로 같은 브랜치에 저장하고 커밋 SHA와 Claude 전달 문구를 줘. 기존 판정 JSON은 고치지 말고, 원본 영상·프레임은 저장소에 올리지 마.
```
