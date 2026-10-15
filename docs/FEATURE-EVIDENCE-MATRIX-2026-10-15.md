# 기능별 근거와 남은 검증 — 2026-10-15

최초 분류 기준: 0da2d7966090c981ed6c02e0dc517a9e006142c7. 이후 연결/올그룹/이동 정적 근거를 추가했다. 기존 보고서의 결과를 분류한 문서이며 최초 표 정리는 새 검증 결과가 아니며, 15:59 갱신의 새 AOT/ELF 근거는 아래 LAYER-MEMORY 보고서로 구분한다. 전체 기능 목록의 완성을 뜻하지 않는다.

## 현재 작업 조건

15:15 KST에는 실행 환경이 unavailable이었으나 15:59 KST에 기존 AOT/ELF 캐시·터미널 접근이 복구됐다. 캐시 재추출이나 도구 설치 없이 재사용했다. 신규 레이어 메모리 정적 근거는 [LAYER-MEMORY](AOT-LAYER-MEMORY-TRACE-2026-10-15.md)이며 새 실제 앱·영상 검증은 없다. 계측 앱의 license4 차단은 별개로 유지된다.

## 기능별 구분

| 항목 | 기존 실제 앱·저장/영상 표본 | 정적 분석으로 연결한 범위 | 남은 핵심 |
|---|---|---|---|
| 채우기·구멍 | 01의 단순 사각형 구멍, 윤곽 방향 반전, 겹침 출력 관찰 | contour 경로 조합·보간 대응·저장/공유 복원 | 복잡한 윤곽/부분 경계와 픽셀 재현 전체 검증 |
| 객체·채우기 순서 | FR 목록 반전 후에도 겹침 결과 유지; 반대 DrawOrder 지정은 왕복 중 바뀌어 의도한 시험 불성립 | DB 정렬·draw unit 배치·그룹 단위·DrawOrder 저장 | 일반 AO 순서 변경 UI는 제한된 이름·문자열 검색에서 미식별; 상세 3탭의 확인한 경로에도 미식별; 앱 전체 부재 증명 아님 |
| 독립 객체 glow | 02 수평선의 radius/thickness/alpha, 기본선 알파0, 독립 객체 두 개 중첩 표본 | 객체별 backend·shader 수학·cache key·영향 unit 전파 | 곡선/링/연결 그룹을 포함한 전체 픽셀·blend 결과 |
| 그룹·해제 | 04에서 AC/Flags 변화와 동반 이동·해제 후 독립 이동 | UI Flags→구조 갱신, 기반 그룹 참조 상대화↔복원 | 중첩·그룹 트위닝·잠금 UI의 전체 계약; 올그룹 상자/레이어 필터·모서리 확대·회전 보조는 새 정적 근거 참조; 그룹 이동 표본을 그룹 glow 합성 검증으로 세지 않음 |
| 크기 변형·늘이기 | 04 UI 크기 적용 후 ObjectScale2 유지; 손끝 드래그와 전체 확대가 누적된 표본 | 상세 패널 pending 일괄 적용·pivot 선택·c+m(p−c)·두 속성 배율과 저장/복원 | 대상 closure/AO ID 중복 제거 연결은 확인; 손끝 drag의 도구/점 유형 분기·branch 경계·트리 ID 정렬과 잔여 map 순서 확인; 전체 hit-test·비정상 연결은 미완. 02 입력2→왕복1을 기능 무효로 일반화 금지 |
| 원근 | 04 첫 표본의 사영변환 적합, 두 번째 표본의 아핀 좌표 변화/속성 배율 관찰 | 일반8핸들·시작snapshot·사영/쌍선형 선택·실패fallback·좌표저장(아래 원근 보고서) | 올가미→AllGroup 및 선택screenmap키 필터도 확인; 앞단tap·곡선/원 최종 픽셀·실제 수치 경계 |
| 생성·삭제·보간 | 03 동일ID 이동/알파 중간값, 새ID 교체 누락, FR 생성·삭제 비대칭 표본 | fill 대응·실패 fallback·점 override/삭제 표시 | root 해제·moved run/잔차·outgoing연결저장·객체/Index보간 신규확인; rebase/compaction·비정상 연결·임의 작품 일반화 미완 |
| 수동 트위닝 잇기 | 05 다른ID 두 원의 링크 후 중간 원 복구, 축소 영상에서 해당 한 장 차이 | 기존 AOT의 링크 유형/점순서/충돌 검사 근거 | 뒤key정렬·자연ID충돌·TypeId/동위치Index검사 확인; UI 전체·역방향·복합FR 실제 결과 미완 |
| 레이어 위·아래 이동 | 이 표에서 실제 앱 검증 완료로 세지 않음 | UI→메모리 Layer번호/AO LayerId/활성선택 교환→sequence DB 교환/현재 SaveFrame→cache 제거 | 실제 앱 결과·DB 실패 rollback·동적 정렬 대상의 전체 해석 |
| 내보내기·FPS | 기존 01–05 출력의 길이/프레임수 관찰 | (T 트위닝,P 재생) timeline, Dart Picture→Java 인코더, 별도재생Frame/Picture/Image버퍼·clock 연결 | 모든 FPS 조합·renderer backend·완전한 픽셀 동일성 |

실제 표본은 [01–03 결과](PRIORITY-V2-RESULTS-2026-10-14.md), [04–05 결과](UI-04-05-RESULTS-2026-10-15.md)를 따른다. 이전 보고서 말미의 당시 ‘다음 작업’은 최신 체크포인트보다 우선하지 않는다.

정적 근거는 [DRAW-GLOW](AOT-DRAW-GLOW-TRACE-2026-10-15.md), [FILL-TWEEN](AOT-FILL-TWEEN-TRACE-2026-10-15.md), [GROUP-SHADER-TIMELINE](AOT-GROUP-SHADER-TIMELINE-TRACE-2026-10-15.md), [DIRTY-PROPAGATION](AOT-DIRTY-PROPAGATION-TRACE-2026-10-15.md), [FRAME-CACHE-SAVE](AOT-FRAME-CACHE-SAVE-TRACE-2026-10-15.md), [SAVED-VALUES](AOT-SAVED-VALUES-TRACE-2026-10-15.md), [SHARED-RESTORE](AOT-SHARED-RESTORE-TRACE-2026-10-15.md), [ROOT-FLAGS-LAYER-SWAP](AOT-ROOT-FLAGS-LAYER-SWAP-TRACE-2026-10-15.md)에 있다. 이 목록은 기존 보고서의 대체 구현이나 새로운 증명이 아니다.

## 자율 진행 체크포인트

앞서 안내한 원근 tap/custom/저장·보간의 확인 가능한 정상 경로를 진행했고 다음 근거를 추가했다.

- [SELECTION-CUSTOM](AOT-PERSPECTIVE-SELECTION-CUSTOM-TRACE-2026-10-15.md): visible T2 후보·bounds 점수·fallback·custom 저장 차이.
- [FILL-MOVED-CODEC](AOT-FILL-MOVED-CODEC-TRACE-2026-10-15.md): 공유 fill 바이트 표현·t 정규화·moved run/bit residual·outgoing 연결 저장.
- [ROOT-RELEASE](AOT-ROOT-RELEASE-TRACE-2026-10-15.md): 해제 guard·잔여 점/연결/이동/상세 구체화·unreferenced root 정리.
- [PLAYBACK-BUFFER](AOT-PLAYBACK-BUFFER-TRACE-2026-10-15.md): 원본/출력/화면 Image별 재사용·예산·폐기와 clock.
- [OBJECT-TWEEN-PAIR](AOT-OBJECT-TWEEN-PAIR-TRACE-2026-10-15.md): 앞AO/Index 대응·링크 충돌·속성 정수화·앞 그룹ID 공급.

PC는 사용자20:26 보고로 현재 사용 불가다. 서버 cache는 정상이며 사용자 추가 시험을 요구하지 않았다. 작은 체크포인트마다 자율 작업을 멈추지 않는 지침을 AGENTS에 추가했다.

미확인 정적 범위는 GroupFlagRepair/RepairGroupFlags, 전체 UI/undo·custom fill prune, rebase/compaction 및 오류 입력 계약이다. 상세 변형 fallback은 GDT의 실제 대상 mapping이 기존 cache에 없어 미해결이다. 일반 앞뒤/별도 잠금 UI는 미식별이며 같은 이름 검색을 반복하지 않는다. 이들을 모두 실물에서만 해결할 수 있는 문제로 바꾸어 적지 않는다.

픽셀/backend 동등성·모든 UI 조작 결과·비정상 입력의 실제 결과는 새 실물 검증 없이 완료로 세지 않는다. 기존 계측 앱 license4 차단은 유지된다. 독립 분석 가능 항목 전체를 소진했다거나 완전한 animating AI가 만들어졌다는 의미는 아니다.

이 문서의 상태는 제한된 표본과 기존 정적 근거에 관한 것이다. 완성도 백분율, 모든 기능 완료, 앱과 동일한 렌더러 완성으로 환산하지 않는다. ‘굽힘’은 사용자 정정대로 존재하지 않는 기능으로 제외한다. PREVIDEO 고정 예측·File-2 보호·학습/AI 연결 보류를 유지한다.
