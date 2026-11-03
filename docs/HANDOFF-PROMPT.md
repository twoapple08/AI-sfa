# AI-sfa 작업 재개 — 2026-11-03 추출 기술 v1·최종 검토 완료

모든 답은 한국어로 쓴다. 작업은 twoapple08/AI-sfa의 **claude/new-session-gknz4t 하나**에서 한다. main은 읽거나 쓰지 않는다. 지정 원격 브랜치 최신을 받고 저장 전 다른 변경을 보존한다. 사용자 허용으로 GPT가 Claude 사용량 소진 기간의 분석·구현·시험·문서·커밋·푸시까지 맡는다.

## 읽을 순서

1. AGENTS.md 전체.
2. HANDOFF.md의 현재 우선순위·바로 할 일·사용자 결정 대기.
3. docs/GPT-TAKEOVER-LOG-2026-11-03.md 최신 절과 기간 커밋.
4. 1단계: docs/GPT-SEQ-RUN2-COMPARISON-2026-11-03.md.
5. 2단계: `.claude/skills/stickman-extraction/SKILL.md` → `docs/STICKMAN-EXTRACTION-V1.md` → `docs/GPT-STICKMAN-FINAL-REVIEW-2026-11-03.md`.
6. 기존 근거를 다룰 때 docs/STICKMAN-OVERLAP-DEBATE-2026-11-03.md의 5차 종결 → docs/STICKMAN-CLIP-1032-1271-2026-11-03.md. 키 경계 검토는 docs/GPT-STICKMAN-CANDIDATE-REVIEW-2026-11-03.md.

## 현재 상태·할 일

- **최신 사용자 정정:** Claude 스킬은 사전 준비, GPT 전담 계속. 검토에서 발견한1056–57 손목·1114–15 다리·1234–35 파랑 누락/빨강 혼입은 실제 수정했다. `docs/GPT-STICKMAN-REVIEW-FINDINGS-FIX-2026-11-03.md`와 최신 HANDOFF0번을 먼저 읽는다. 수정 후보6장·나머지234장 동일·전체219개 시험 OK. 사용자 눈 판정 대기. 아래 기준판/검토 기록은 수정 전 이력이다.

- Kaggle 2회차는 pull·save-ckpt·같은 조건 비교를 마쳤다. rc0·resumed=true·누적 순수900.009분 도달. 최종78709걸음. 이어하기 자료 aisfa-seq-ckpt ready. Drive AI-sfa/02_분석자료/seq/run2_2026-11-03/에 로그·판정시트·비교그림이 있다.
- 최종 공식 위치31/45는 필요30을 넘으나 미완료34/92(허용9)로 전체 미통과다. 1회차 마지막과 같은 폭854 비교도 안정적 개선 확인 안 됨. 마지막의 max상한은 앞선 추세 상한과 달라 직접 우열 비교하지 않는다.
- 다음은 종료 학습·반복 생성 개선 방식을 정하고 작은 비교를 설계하는 일이다. CPU 진단은 아래처럼 완료했다. **3회차·GPU·학습은 사용자 허락 뒤에만** 한다.
- 스틱맨 최신 기준: Drive `stickman_proto_2026-11-03/straight_sweep_corrected_2026-11-03/straight_sweep_effect_fixed.sfa`. 사용자 “크게 튀는 건 없어 보임” 확인 후 최종 검토·v1 절차 정착을 요청했다. 파일 링크/해시/재현 자료는 `data/stickman_motion/extraction_v1_2026-11-03.json`.
- 머리 A안 접합·숙임·앱 편집은 사용자 정상 확인. 내부 투명 연결을 가진11객체다. 직선 몸통·거리 굵기·흰 머리 유지. 틀 밖 부모/완전 결측 자식 사슬15건 보정, 접촉5구간13장, 빨강1137–1138 부분 다리/직선 무릎,1116–1117 이펙트 가림 다리 키를 적용했다.1048–1049는 근접 회피라 접촉 제약을 제거한 상태다.
- 새 장면마다 뼈대 코드를 수정하지 않는다. `profiles/stickman_2d_v1.json` 고정, `scenes/*.json`의 tracks/partials/contacts로 보완. `tools/stickman_finalize.py`는 동결 투영 입력에서 장면만 재적용하고 `tools/stickman_quality.py`가 저장본을 검사한다. Claude용 스킬과 기술 가이드의 명령을 사용한다. 이펙트 가림/접촉 자동 인식까지 구현된 것은 아니다.
- 최종 검토:240장 개요와 후보/주요 구간 원본30장 판독, 구조·접촉 위반0, 전 구간 재현240장 XML 동일, 전체219개 시험 OK. 이번 기술 정착 단계에서 승인 SFA를 바꾸지 않았다.1056–1057 파랑 손목·1114–1115 타격 전 빨강 다리 관측 오류·1234–1235 컷 초반 파랑 검출 누락과 기존1217 무릎/1137 골반 한계는 남는다. 전체 자동 정답으로 확대하지 않는다.
- 검토에서 발견한 확인 가능한 오류는 실제 수정·검증·결과 제공까지 수행한다. GPU·Kaggle3회차·학습은 별도 허락 전 실행하지 않는다.
- Kaggle CPU 진단은 완료: `docs/GPT-SEQ-GENERATION-DIAGNOSIS-2026-11-03.md`. 미완료34개는 모두 한도 직전 강제 EOS. CPU6장에서는 초기 형상 오류·후반 반복, 정답 끝 접두열6/6에서 EOS 미선택. 공식 GPU 재판정으로 세지 않는다.

## 규칙·보호·환경

- 근거를 파일·코드 / CPU 계산 / 원본 눈 판독 / 추론으로 구분한다. 결과는 그림 먼저. 눈 판정·방향 결정은 사용자에게 묻는다.
- 2D 유지, 직선 몸통·거리 굵기·부드러운 보간. 자세·원근·가림에 따른 신체 길이 변화 허용. 모든 머리 내부 흰색·인물색 윤곽.
- SFA: 점 ID 장마다 새로, 오브젝트 ID 유지, 인물당 Flags3 하나. 투영 모드는 목선 포함11오브젝트·단일 연결망. (트위닝, 재생)=(24,24), 화면 밖 좌표 허용.
- 원본·추출 프레임·전체 관절·앱 녹화·가중치·judge-pairs는 저장소에 넣지 않는다. 기존 판정 JSON·확인 경계·애니메이터별 학습 규칙을 고치지 않는다.
- 커밋 전 루트 python -m unittest discover -s tests 전체 통과 확인. 실패하면 커밋하지 않는다. 시험과 커밋은 별도 명령으로 한다.
- 저장소 /workspace/AI-sfa, 비공개 캐시 /workspace/ai-sfa-private/. 현재 원본·RTMW·머리 A안·motion_audit·straight_sweep_fix·final_review와 seq_run1·seq_run2·seq_compare·seq_diag가 있다. 세션 소실 시 HANDOFF의 Drive 경로·해시와 Kaggle에서 필요한 자료만 복구한다.
- Claude 복귀 시 GPT 로그와 기간 커밋부터 읽게 하고 마지막 SHA와 짧은 전달 문구를 준다.
