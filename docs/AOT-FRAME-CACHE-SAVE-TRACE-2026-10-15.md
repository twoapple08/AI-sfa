# 프레임 객체 캐시·레이어 이동·저장/불러오기 연결 — 2026-10-15

- 기존 AOT/ELF 캐시를 재사용한 정적 추적이다.
- 이 보고서의 렌더용 프레임 캐시는 `Frame` 데이터 객체를 보관한다.
- EditorFrameCache의 Picture 기록, glow 이미지, hole 경로 캐시와 서로 다른 층이다.
- 실제 앱의 지속 편집·픽셀 결과는 검증하지 않았다.

## 확인한 결론

| 동작 | 확인된 역할 | 근거 주소 |
|---|---|---|
| get renderable cache | 정수 FrameID로 remove 후 같은 객체 재삽입, 최근 사용 순서 갱신 | main 0x51fb7c–0x51fbfc |
| put | Frame.field7 ID 사용, 같은 키의 다른 객체 폐기, 최대 12개 초과 시 가장 앞 객체 제거 | main 0x51fea0–0x520008 |
| take | ID로 remove하고 객체 반환, 폐기하지 않음 | main 0x524d34–0x524d88 |
| evict / clear | 제거 대상의 AO map 해제와 AO 목록 null 처리; clear는 전체 순회 후 map.clear | main 0x52403c, 0x552fac |
| markFrameDataDirty | 화면 상태 field_ef를 true로 설정 | main 0x5b9a4c |
| markCanvasDirty | 현재 FrameID 캐시 제거, steady 문맥 해제, field_d3 카운터 증가 및 notifier 전달 | main 0x5243e8 |
| saveCurrentFrame | 현재 프레임과 dirty가 있을 때 SaveFrame; 정상 반환 뒤 dirty=false와 history 기록 | main 0x5ccf44, closure 0x5cd010 |

- 확인한 map 키에는 수정 버전 튜플이 없다.
- 화면 알림 카운터는 존재하지만 이 FrameID 키와 합치지 않는다.
- dirty 설정 자체는 캐시 제거도 DB 저장도 아니다.
- 캐시의 12는 Frame 개수 제한이며 이미지 개수나 MB 예산이 아니다.

## 캐시 적중·누락과 편집 객체 인계

- `_loadRenderableFrame`의 측정 closure(0x51fbfc)는 get 적중 시 해당 Frame을 즉시 반환한다.
- 누락 시 DataAccess로 GetFrameById → GetLayersForFrame → GetAnimationObjectsForFrame/AddAnimationObject → repairGroupFlags → put → close를 수행한다.
- 이 확인만으로 모든 fill 공급 세부 경로까지 확정하지 않는다.

- `_disposeRenderableFrame`(0x520008)과 evict의 해제는 Frame.ReleaseAnimationObjectMap 및 AO 목록 null 처리다.
- ReleaseAnimationObjectMap(sequences/frame.dart 0x5185ec)은 field23을 null로 만든다.
- 이 경로를 native Image.dispose나 전역 glow/hole 캐시 전체 초기화로 해석하지 않는다.

- `_loadFrameDetails`(0x5249c4)는 받은 Frame의 AO 목록과 layer 목록이 이미 비어 있지 않으면 그 객체를 반환한다.
- 보충이 필요하면 FrameID로 take를 호출하며, 적중 객체를 폐기하지 않고 사용한다.
- 이후 layer 조회/필요 시 repair 및 AO 목록의 null·empty 검사에 따른 DB 보충, repairGroupFlags를 거친다.
- 따라서 재불러오기가 항상 새 AO 객체를 DB에서 생성한다는 결론은 틀리다.

- `_bindLoadedFrame`(0x51f2e0)은 프레임 ID 집합으로 retain을 호출한다.
- retain의 필터 closure(0x3475c0)는 set.contains 결과를 반전하므로 집합 밖 키를 evict한다.
- 이어 setState closure(0x524130)가 활동에 Frame을 bind하고 markCanvasDirty·상호작용 문맥 해제·dirty=false·주변 프레임 목록 초기화를 수행한다.
- 바인딩 후 onion 갱신과 adjacent prefetch도 예약한다.
- 모든 prefetch 실행 시점이나 재생 캐시까지 추적 완료한 것은 아니다.

## 레이어 위·아래 이동 UI

아래 이동(0x5bc7e4)은 false, 위 이동(0x5bd570)은 true로 `_moveSelectedLayer`(0x5bc818)에 들어간다. 이 함수는 대상/이웃 선택과 경계 검사를 거쳐 DB BeginTransaction → SwapLayersAndContentGlobal → SaveFrame → CommitTransaction → FinishTransaction → close를 호출한다(0x5bcbd4–0x5bcc28).

정상 DB 처리 뒤 setState의 실제 closure(0x5bd008)가 renderable map의 모든 키를 복사하여 evict한다(0x5bd07c). 주변 프레임 목록 field11b/11f를 빈 목록으로 바꾸고 markCanvasDirty를 호출한다(0x5bd098–0x5bd0a4). 이어 layer 상호작용 상태를 정리하고 UpdateLayerSelectionAfterMove를 호출한다. 바깥 함수는 onion refresh·adjacent prefetch를 예약하고 전체 canvas history를 지운 뒤 현재 기록을 남긴다.

- 이는 레이어 이동 UI의 캐시 폐기 연결이다.
- 개별 AO의 앞/뒤 보내기 UI나 모든 DrawOrder 대입 경로를 확인한 결과로 확대하지 않는다.
- SwapLayersAndContentGlobal 내부 SQL과 모든 프레임의 메모리 변경 방식은 별도 추적 대상이다.

## 저장 경계

- 수정 figure 확정 `_commitModifyFigureMutation`(0x5cce1c)은 조건을 통과하면 현재 ID evict → drag/steady 문맥 해제 → markFrameDataDirty → saveCurrentFrame 순서로 연결된다.
- `_saveCurrentFrame` 측정 closure는 DataAccess.SaveFrame과 close를 호출하며 자체 렌더 캐시 evict는 보이지 않는다.
- 저장 정상 반환 뒤에만 dirty=false/history에 도달한다.

- DataAccess.SaveFrame(0x3575d0)의 중첩 closure(0x3578b0)에서 transaction, 프레임 존재 검사와 insert/update, PruneInvalidFillRegions, AO 공급, 누락 AO 정리, `_saveFiguresChangedOnly`(0x357b60), layer 저장 처리, `_replaceFrameFillRegions`(0x357fc8), commit/finish가 연결된다.
- 프레임 저장과 PNG/MP4 내보내기는 구분한다.
- `_saveFiguresChangedOnly`의 필드별 비교 및 fill segment 직렬화는 아직 열지 않았다.

## 검증과 다음 단계

- 62개 선택 명령을 비공개 ELF PT_LOAD에서 직접 읽어 Capstone 결과와 기존 AOT 목록을 대조했고 모두 일치했다.
- Dart 레지스터 별칭과 compressed `stur NULL`의 w22 폭을 정규화했다.
- 공개 audit에는 주소와 일치 여부만 포함한다.
- 이전 표본과 겹칠 수 있어 누적 독립 검증 수로 합산하지 않는다.
- 이 검사는 전체 함수 의미나 런타임 렌더 결과의 증명이 아니다.

- 문서만 변경했다.
- 기존 unit/probe/영상 분석, 설치·페어링·휴대폰 시작 시험을 반복하지 않았다.
- PC 확보와 학교 Wi-Fi 제약은 기존 인계 상태를 유지하며 지금 사용자 추가 작업은 없다.

다음은 `_saveFiguresChangedOnly`의 DrawOrder/Flags/glow/point 저장 비교 → `_replaceFrameFillRegions`와 segment 재공급 → SwapLayersAndContentGlobal 내부 및 일반 AO 순서 변경 UI 연결이다. 재생 전용 캐시의 폐기 경계는 남겨 둔다.
