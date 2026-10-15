# 기능별 근거와 남은 검증 — 2026-10-15 15:15 KST

기준 체크포인트: 0da2d7966090c981ed6c02e0dc517a9e006142c7. 기존 보고서의 결과를 분류한 문서이며 새 기능 시험·원본 영상 분석·AOT/ELF 검증을 수행한 결과가 아니다. 전체 기능 목록의 완성을 뜻하지 않는다.

## 현재 작업 조건

이번 세션의 실행 환경은 unavailable이고 터미널 도구가 제공되지 않는다. 비공개 AOT/ELF 캐시의 현재 존재·내용을 확인할 수 없다. 캐시 삭제나 손상을 확인한 것은 아니다. GitHub 문서는 접근 가능하여 완료/미완 범위를 정리했다. 앱의 라이선스 응답4로 계측 앱의 지속 편집이 막힌 이전 상태와 이번 분석 환경 접근 불가는 별개의 장애다. 사용자 PC·학교 Wi-Fi가 이번 환경 장애의 원인이라고 단정하지 않는다.

## 기능별 구분

| 항목 | 기존 실제 앱·저장/영상 표본 | 정적 분석으로 연결한 범위 | 남은 핵심 |
|---|---|---|---|
| 채우기·구멍 | 01의 단순 사각형 구멍, 윤곽 방향 반전, 겹침 출력 관찰 | contour 경로 조합·보간 대응·저장/공유 복원 | 복잡한 윤곽/부분 경계와 픽셀 재현 전체 검증 |
| 객체·채우기 순서 | FR 목록 반전 후에도 겹침 결과 유지; 반대 DrawOrder 지정은 왕복 중 바뀌어 의도한 시험 불성립 | DB 정렬·draw unit 배치·그룹 단위·DrawOrder 저장 | 일반 AO 순서 변경 UI가 있는지부터 식별하고 실제 mutation/저장/캐시 연결 확인 |
| 독립 객체 glow | 02 수평선의 radius/thickness/alpha, 기본선 알파0, 독립 객체 두 개 중첩 표본 | 객체별 backend·shader 수학·cache key·영향 unit 전파 | 곡선/링/연결 그룹을 포함한 전체 픽셀·blend 결과 |
| 그룹·해제 | 04에서 AC/Flags 변화와 동반 이동·해제 후 독립 이동 | UI Flags→구조 갱신, 기반 그룹 참조 상대화↔복원 | 중첩·올그룹·잠금·그룹 트위닝의 전체 계약; 그룹 이동 표본을 그룹 glow 합성 검증으로 세지 않음 |
| 크기 변형·늘이기 | 04 UI 크기 적용 후 ObjectScale2 유지; 손끝 드래그와 전체 확대가 누적된 표본 | 프레임 상세 배율 저장/복원 및 비양수 보정 | 손끝 드래그 전파 수학 전체. 02 입력2→왕복1을 기능 무효로 일반화 금지 |
| 원근 | 04 첫 표본의 사영변환 적합, 두 번째 표본의 아핀 좌표 변화/속성 배율 관찰 | 이 문서는 기존 UI 결과를 분류 | 핸들별 행렬·굵기/배율 계산, 곡선·원·범위 밖 점 처리 전체 |
| 생성·삭제·보간 | 03 동일ID 이동/알파 중간값, 새ID 교체 누락, FR 생성·삭제 비대칭 표본 | fill 대응·실패 fallback·점 override/삭제 표시 | root 수명, moved point·연결 전체 분기, 임의 작품 일반화 |
| 수동 트위닝 잇기 | 05 다른ID 두 원의 링크 후 중간 원 복구, 축소 영상에서 해당 한 장 차이 | 기존 AOT의 링크 유형/점순서/충돌 검사 근거 | 복수·충돌·역방향·다른 유형·FR 대응 전체 |
| 레이어 위·아래 이동 | 이 표에서 실제 앱 검증 완료로 세지 않음 | UI→같은 sequence의 번호 교환→현재 SaveFrame→render cache 제거 | 현재 프레임의 메모리 목록/필드 변화와 실제 앱 결과 |
| 내보내기·FPS | 기존 01–05 출력의 길이/프레임수 관찰 | (T 트위닝,P 재생) timeline, Dart Picture→Java 인코더 연결 | 모든 FPS 조합·renderer backend·완전한 픽셀 동일성 |

실제 표본은 [01–03 결과](PRIORITY-V2-RESULTS-2026-10-14.md), [04–05 결과](UI-04-05-RESULTS-2026-10-15.md)를 따른다. 이전 보고서 말미의 당시 ‘다음 작업’은 최신 체크포인트보다 우선하지 않는다.

정적 근거는 [DRAW-GLOW](AOT-DRAW-GLOW-TRACE-2026-10-15.md), [FILL-TWEEN](AOT-FILL-TWEEN-TRACE-2026-10-15.md), [GROUP-SHADER-TIMELINE](AOT-GROUP-SHADER-TIMELINE-TRACE-2026-10-15.md), [DIRTY-PROPAGATION](AOT-DIRTY-PROPAGATION-TRACE-2026-10-15.md), [FRAME-CACHE-SAVE](AOT-FRAME-CACHE-SAVE-TRACE-2026-10-15.md), [SAVED-VALUES](AOT-SAVED-VALUES-TRACE-2026-10-15.md), [SHARED-RESTORE](AOT-SHARED-RESTORE-TRACE-2026-10-15.md), [ROOT-FLAGS-LAYER-SWAP](AOT-ROOT-FLAGS-LAYER-SWAP-TRACE-2026-10-15.md)에 있다. 이 목록은 기존 보고서의 대체 구현이나 새로운 증명이 아니다.

## 환경 복구 후 바로 할 작업

1. 기존 캐시 경로만 먼저 확인한다. 정상 캐시가 있으면 재설치·재추출 없이 재사용한다.
2. main.dart의 _moveSelectedLayer(0x5bc818), setState closure(0x5bd008)와 활동의 UpdateLayerSelectionAfterMove(0x5bd12c)에서 현재 프레임 메모리 변경의 미확인 부분만 추적한다. DB helper/이미 확인한 cache eviction은 반복 분석하지 않는다.
3. 일반 AO 앞/뒤 순서 UI의 존재·실제 dispatch를 식별한다. 함수명이 비슷하거나 UpdateAnimationObjectDrawOrder가 있다는 이유만으로 UI 경로를 확정하지 않는다. 기존 0x50ce1c 호출은 객체 생성 경로였으므로 일반 순서 UI의 증거로 쓰지 않는다.
4. 새로 닫은 연결만 보고서에 추가하고, 실제 앱 시험이 필요한 항목과 계속 구분한다. 오늘 표 정리 때문에 이전 시험을 재요청하지 않는다.

이 문서의 상태는 제한된 표본과 기존 정적 근거에 관한 것이다. 완성도 백분율, 모든 기능 완료, 앱과 동일한 렌더러 완성으로 환산하지 않는다. ‘굽힘’은 사용자 정정대로 존재하지 않는 기능으로 제외한다. PREVIDEO 고정 예측·File-2 보호·학습/AI 연결 보류를 유지한다.
