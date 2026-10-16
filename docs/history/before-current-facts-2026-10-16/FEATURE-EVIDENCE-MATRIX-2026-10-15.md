# 기능별 근거와 남은 검증 — 2026-10-15

- 최초 분류 기준: 0da2d7966090c981ed6c02e0dc517a9e006142c7. 이후 연결/올그룹/이동 정적 근거를 추가했다.
- 기존 보고서의 결과를 분류한 문서이며 최초 표 정리는 새 검증 결과가 아니며, 15:59 갱신의 새 AOT/ELF 근거는 아래 LAYER-MEMORY 보고서로 구분한다.
- 전체 기능 목록의 완성을 뜻하지 않는다.

## 현재 작업 조건

- **최신 2026-10-16:** 서버 분석 환경과 비공개 백업 복구 완료. 실제 dispatch 표로 정상 목록의 first/last/removeLast를 확인했고, unused AO 잔존 조건·FastHash 포함 필드·실제 시간축 명령 경로를 새로 연결했다.
- 아래 과거 캐시 부재/해당 getter 미확정 항목은 현행 상태가 아니다.
- 새 [DISPATCH](AOT-DISPATCH-TARGETS-TRACE-2026-10-16.md), [HASH/UNUSED](AOT-UNUSED-AO-FAST-HASH-TRACE-2026-10-16.md), [FRAME 명령](AOT-TIMELINE-FRAME-COMMANDS-TRACE-2026-10-16.md)을 따른다.
- 실제 앱/전체 UI/pixel 미완은 유지한다.

- **2026-10-16 현행 환경 정정:** 아래의 서버 cache 정상은 당시 상태다.
- 현재 분석 캐시/도구 경로가 없고 공개 저장소만 복구했다.
- [현행 준비 상태](ANALYSIS-READINESS-2026-10-16.md)와 [기능 근거 색인](FEATURE-CONTRACT-INDEX-2026-10-16.json)을 따른다.
- 새 AOT/실물 결과는 추가하지 않았다.

- 15:15 KST에는 실행 환경이 unavailable이었으나 15:59 KST에 기존 AOT/ELF 캐시·터미널 접근이 복구됐다.
- 캐시 재추출이나 도구 설치 없이 재사용했다.
- 신규 레이어 메모리 정적 근거는 [LAYER-MEMORY](AOT-LAYER-MEMORY-TRACE-2026-10-15.md)이며 새 실제 앱·영상 검증은 없다.
- 계측 앱의 license4 차단은 별개로 유지된다.

## 기능별 구분

| 항목 | 기존 실제 앱·저장/영상 표본 | 정적 분석으로 연결한 범위 | 남은 핵심 |
|---|---|---|---|
| 채우기·구멍 | 01의 단순 사각형 구멍, 윤곽 방향 반전, 겹침 출력 관찰 | contour 경로 조합·보간 대응·저장/공유 복원 | 복잡한 윤곽/부분 경계와 픽셀 재현 전체 검증 |
| 객체·채우기 순서 | FR 목록 반전 후에도 겹침 결과 유지; 반대 DrawOrder 지정은 왕복 중 바뀌어 의도한 시험 불성립 | DB 정렬·draw unit 배치·그룹 단위·DrawOrder 저장 | 일반 AO 순서 변경 UI는 제한된 이름·문자열 검색에서 미식별; 상세 3탭의 확인한 경로에도 미식별; 앱 전체 부재 증명 아님 |
| 독립 객체 glow | 02 수평선의 radius/thickness/alpha, 기본선 알파 0, 독립 객체 두 개 중첩 표본 | 객체별 backend·shader 수학·cache key·영향 unit 전파 | 곡선/링/연결 그룹을 포함한 전체 픽셀·blend 결과 |
| 그룹·해제 | 04에서 AC/Flags 변화와 동반 이동·해제 후 독립 이동 | UI Flags→구조 갱신, 기반 그룹 참조 상대화↔복원 | 중첩·그룹 트위닝·잠금 UI의 전체 계약; 올그룹 상자/레이어 필터·모서리 확대·회전 보조는 새 정적 근거 참조; 그룹 이동 표본을 그룹 glow 합성 검증으로 세지 않음 |
| 크기 변형·늘이기 | 04 UI 크기 적용 후 ObjectScale2 유지; 손끝 드래그와 전체 확대가 누적된 표본 | 상세 패널 pending 일괄 적용·pivot 선택·c+m(p−c)·두 속성 배율과 저장/복원 | 대상 closure/AO ID 중복 제거 연결은 확인; 손끝 drag의 도구/점 유형 분기·branch 경계·트리 ID 정렬과 잔여 map 순서 확인; 전체 hit-test·비정상 연결은 미완. 02 입력 2→왕복 1을 기능 무효로 일반화 금지 |
| 원근 | 04 첫 표본의 사영변환 적합, 두 번째 표본의 아핀 좌표 변화/속성 배율 관찰 | 일반 8핸들·시작 snapshot·사영/쌍선형 선택·실패 fallback·좌표저장(아래 원근 보고서) | 올가미→AllGroup 및 선택 screenmap키 필터도 확인; 앞단 tap·곡선/원 최종 픽셀·실제 수치 경계 |
| 생성·삭제·보간 | 03 동일 ID 이동/알파 중간값, 새 ID 교체 누락, FR 생성·삭제 비대칭 표본 | fill 대응·실패 fallback·점 override/삭제 표시 | root 해제·moved run/잔차·outgoing연결저장·객체/Index보간 신규확인; rebase/compaction 정상 정적 경로는 아래 추가 보고서에서 확인; 비정상 연결·임의 작품 일반화 미완 |
| 수동 트위닝 잇기 | 05 다른 ID 두 원의 링크 후 중간 원 복구, 축소 영상에서 해당 한 장 차이 | 기존 AOT의 링크 유형/점순서/충돌 검사 근거 | 뒤 key정렬·자연 ID충돌·TypeId/동위치 Index검사 확인; UI 전체·역방향·복합 FR 실제 결과 미완 |
| 레이어 위·아래 이동·병합·삭제·추가 | 이 표에서 실제 앱 검증 완료로 세지 않음 | UI→메모리/sequence DB 교환·cache 제거; 병합 기존 순서 슬롯 재배정 / 삭제 기반 참조·fill 정리 / 전체 frame 정의 추가 / history 초기화 | 실제 앱 결과·DB 실패 rollback·동적 정렬 대상의 전체 해석 |
| 내보내기·FPS | 기존 01–05 출력의 길이/프레임수 관찰 | (T 트위닝,P 재생) timeline, Dart Picture→Java 인코더, 별도재생 Frame/Picture/Image버퍼·clock 연결 | 모든 FPS 조합·renderer backend·완전한 픽셀 동일성 |

실제 표본은 [01–03 결과](PRIORITY-V2-RESULTS-2026-10-14.md), [04–05 결과](UI-04-05-RESULTS-2026-10-15.md)를 따른다. 이전 보고서 말미의 당시 ‘다음 작업’은 최신 체크포인트보다 우선하지 않는다.

- 정적 근거는 [DRAW-GLOW](AOT-DRAW-GLOW-TRACE-2026-10-15.md), [FILL-TWEEN](AOT-FILL-TWEEN-TRACE-2026-10-15.md), [GROUP-SHADER-TIMELINE](AOT-GROUP-SHADER-TIMELINE-TRACE-2026-10-15.md), [DIRTY-PROPAGATION](AOT-DIRTY-PROPAGATION-TRACE-2026-10-15.md), [FRAME-CACHE-SAVE](AOT-FRAME-CACHE-SAVE-TRACE-2026-10-15.md), [SAVED-VALUES](AOT-SAVED-VALUES-TRACE-2026-10-15.md), [SHARED-RESTORE](AOT-SHARED-RESTORE-TRACE-2026-10-15.md), [ROOT-FLAGS-LAYER-SWAP](AOT-ROOT-FLAGS-LAYER-SWAP-TRACE-2026-10-15.md)에 있다.
- 이 목록은 기존 보고서의 대체 구현이나 새로운 증명이 아니다.

## 자율 진행 체크포인트

앞서 안내한 원근 tap/custom/저장·보간의 확인 가능한 정상 경로를 진행했고 다음 근거를 추가했다.

- [SELECTION-CUSTOM](AOT-PERSPECTIVE-SELECTION-CUSTOM-TRACE-2026-10-15.md): visible T2 후보·bounds 점수·fallback·custom 저장 차이.
- [FILL-MOVED-CODEC](AOT-FILL-MOVED-CODEC-TRACE-2026-10-15.md): 공유 fill 바이트 표현·t 정규화·moved run/bit residual·outgoing 연결 저장.
- [ROOT-RELEASE](AOT-ROOT-RELEASE-TRACE-2026-10-15.md): 해제 guard·잔여 점/연결/이동/상세 구체화·unreferenced root 정리.
- [PLAYBACK-BUFFER](AOT-PLAYBACK-BUFFER-TRACE-2026-10-15.md): 원본/출력/화면 Image별 재사용·예산·폐기와 clock.
- [OBJECT-TWEEN-PAIR](AOT-OBJECT-TWEEN-PAIR-TRACE-2026-10-15.md): 앞 AO/Index 대응·링크 충돌·속성 정수화·앞 그룹 ID 공급.

- PC는 사용자 20:26 보고로 현재 사용 불가다.
- 서버 cache는 정상이며 사용자 추가 시험을 요구하지 않았다.
- 작은 체크포인트마다 자율 작업을 멈추지 않는 지침을 AGENTS에 추가했다.

- 추가로 [GROUP-REPAIR](AOT-GROUP-REPAIR-TRACE-2026-10-15.md), [FILL-PRUNE-HISTORY](AOT-FILL-PRUNE-HISTORY-TRACE-2026-10-15.md), [ROOT-REBASE-IDLE](AOT-ROOT-REBASE-IDLE-TRACE-2026-10-15.md)를 연결했다.
- 그룹 비정상 참조·순환과 DB 반영, fill 구조 정리·custom undo 정상경로·일반 복원 live LayerId/DrawOrder 보존·history 비교, root 재기반 완전일치 조건·idle wrapper/재작성 guard를 확인했다.
- 각각 57/178/62 선택 명령 대조이며 전체 의미/실물 증명은 아니다.

- 추가로 [DB-REWRITE](AOT-DB-REWRITE-TRACE-2026-10-15.md)(52선택명령), [COMPACTION-PHASES](AOT-COMPACTION-PHASES-TRACE-2026-10-15.md)(178선택명령)를 연결했다.
- 프레임 압축 정상 단계·PlainRanks·moved 병합과 파일 교체 guard/실패 경로, 일반 undo/redo의 frame별 stack·hash/async guard를 확인했다.
- 실제 압축 실행·무손실/실패 원자성 증명은 아니다.

- [LAYER-MERGE-DELETE-ADD](AOT-LAYER-MERGE-DELETE-ADD-TRACE-2026-10-15.md)(138선택명령)에서 병합의 target/source 순서·기존 DrawOrder 슬롯 재배정, 삭제의 root 가상 참조·fill 정리, 전체 frame 레이어 추가와 merge/delete history 초기화를 추가 확인했다.
- 공유 fill의 outer 제거는 빈 segment region 유지, 기존 SQL 표현은 region 행 삭제라는 차이도 구분했다.
- 이 명령의 정상 정적 경로를 다시 미수행으로 표시하지 않는다.
- [EDITOR-MENU-DELETE-CALLER](AOT-EDITOR-MENU-DELETE-CALLER-TRACE-2026-10-15.md)(65선택명령)에서 실제 도구 모드 route와 선택 객체 삭제의 현재 frame 대상·저장/history 연결도 확인했다.
- CurrentFrameDialog 이름으로 시간축 frame복사/삽입 입구를 가정한 것은 정정했다.
- 미완은 실제 시간축 명령 caller·unused AO 정리 helper·GetFastHash 계약(개별 점 삭제 기본 흐름은 ROOT-FLAGS-LAYER-SWAP에서 재사용)이다.
- 전체 UI coverage·hash 내부·동적 호출 실제 target·오류 입력/외부 수정/전체 수명 계약도 미완이다.
- 상세 변형 fallback은 GDT의 실제 대상 mapping이 기존 cache에 없어 미해결이다.
- 일반 앞뒤/별도 잠금 UI는 미식별이며 같은 이름 검색을 반복하지 않는다.
- 이들을 모두 실물에서만 해결할 수 있는 문제로 바꾸어 적지 않는다.

- 픽셀/backend 동등성·모든 UI 조작 결과·비정상 입력의 실제 결과는 새 실물 검증 없이 완료로 세지 않는다.
- 기존 계측 앱 license4 차단은 유지된다.
- 독립 분석 가능 항목 전체를 소진했다거나 완전한 animating AI가 만들어졌다는 의미는 아니다.

- 이 문서의 상태는 제한된 표본과 기존 정적 근거에 관한 것이다.
- 완성도 백분율, 모든 기능 완료, 앱과 동일한 렌더러 완성으로 환산하지 않는다.
- ‘굽힘’은 사용자 정정대로 존재하지 않는 기능으로 제외한다.
- PREVIDEO 고정 예측·File-2 보호·학습/AI 연결 보류를 유지한다.


- 2026-10-16 추가: [ROOT-COPY-DB-BRANCHES](AOT-ROOT-COPY-DB-BRANCHES-TRACE-2026-10-16.md)에서 root prefix(절반이상) 재사용/새 root/source rebase시도/targetbase 범위·점 ID예약 schema·같은/다른 sequence AO DB복사 정상분기를 49선택명령으로 보충했다.
- 실제복사/실패보장·전체 UI coverage는 별개다.

2026-10-16 추가: [APP-V3](APP-V3-FRAME-COMMANDS-PROTOCOL-2026-10-16.md)에서 시간축 명령 정적 결과를 SFA 관측 가능/불가로 나누고 시드·검사 도구·절차를 추가했다. 실제 앱 결과는 아직 없고 root/ID 예약/unused 정리는 내보내기로 관측 불가로 분류했다.

- 2026-10-16 추가: [AXIS-FIX-DRAWORDER-WRITERS](AOT-AXIS-FIX-DRAWORDER-WRITERS-TRACE-2026-10-16.md)(49선택명령).
- DrawOrder 쓰기 경로 전수 조사로 생성·복사·import·병합·undo 외 일반 AO 앞뒤 UI 경로가 나오지 않았다(부재 증명 아님).
- 잠금 열은 layer_def.is_locked뿐이며, 잠금형 편집 보조인 축 고정(세로/가로 배타, 일반 점 드래그만, 환경설정 미저장)과 회전 스냅 UI를 연결했다.
