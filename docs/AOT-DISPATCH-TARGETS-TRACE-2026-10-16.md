# 동적 목록 호출의 실제 target 복구 — 2026-10-16

과거에는 AOT annotation의 GDT 슬롯만으로 실제 메서드명을 확정하지 않았다. 이번에는 복구한 분석 VM이 동일 원본 snapshot을 로드한 뒤 갖는 **dispatch table 자체**를 비공개로 읽었다. 따라서 ‘기존 cache에 mapping이 없음’은 이 선택 항목들의 현행 차단 사유가 아니다. 실제 Android 편집/렌더 실행은 아니다.

## 실제 표에서 읽은 관계

동일 Dart SDK의 ARM64 DispatchTable.kOriginElement는4096, 로드된 표 길이는57,043이다. Blutter에 `--dispatch-only` 진단 출력을 추가하여 LoadInfo 후 이 표만 기록하고 반환했다. 기존 AOT/PP/objs 전체 분석을 다시 실행하지 않는다. 원본 snapshot이나 앱 알고리즘을 패치하지 않았으며, 이 추가 tool 코드는 메타데이터 출력용이다.

ARM64 호출의 표 index는 **4096 + 실제 수신 객체 cid + signed selector offset**이다. 로드 주소를 빼서 libapp 상대 target을 얻고, 같은 snapshot의 함수 이름 metadata와 실제 target의 ELF 명령을 대조했다. 표 전체·원본 코드·ASLR 주소는 공개하지 않는다.

SDK가 확인한 Array/ImmutableArray/GrowableObjectArray class ID는 각각90/91/92다.

| 수신 class ID | selector | 실제 target | 확인한 역할 |
|---:|---:|---:|---|
| 90,91 | +0x85e4 | 0x4d6064 | Array first |
| 92 | +0x85e4 | 0x4d5ff4 | GrowableList first |
| 92 | +0x8cb1 | 0x4b87d0 | GrowableList iterator |
| 92 | +0xbc49 | 0x3f95fc | GrowableList removeLast |
| 92 | +0x9780 | 0x4acd38 | GrowableList last |

first target은 길이를 검사하고 index0의 원소를 읽는다. last는 길이−1의 원소를 읽으며 removeLast는 마지막 원소를 얻고 길이를 줄이는 helper를 호출한다. 이름만 매칭한 결과와 구분한다. 실제 caller에서 사용하지 않는 다른 cid를 이 selector에 임의로 대입하여 나온 주소는 해당 메서드의 유효한 dispatch 증거로 쓰지 않는다. 표의 공간 재사용 때문에 selector 하나를 전 클래스 공통 이름표로 바꿀 수 없다.

## 과거 미확정 항목에 주는 결론

1. **상세 변형 pivot fallback:** modify_figure_dialog 0x635898–0x635924는 대상 첫 AO를 직접 GrowableList.first로 얻고, 해당 AO의 점 목록이 비어 있지 않으면 +0x85e4를 호출한다. 정상 생성/읽기 경로의 Array/ImmutableArray/GrowableList 점 목록에서는 이것이 **그 첫 AO의 첫 점**이다. 기존 T2 우선 선택이 앞에 있으므로 언제나 첫 점을 pivot으로 쓴다는 뜻은 아니다. 다른 AO까지 찾아 평균/중심점으로 바꾸지 않는다. [MODIFY-PANEL-TRANSFORM](AOT-MODIFY-PANEL-TRANSFORM-TRACE-2026-10-15.md)의 나머지 선택·변형식은 유지한다.
2. **AdoptLiveLayerState:** 활성 layer가 새 목록에 없을 때 0x60452c–0x60455c는 같은 목록 계열의 first Layer 번호를 활성값으로 사용한다. 과거의 ‘동적 getter 미확정’은 이 정상 목록 계열에 대해 해소된다. Layer ID 최솟값을 별도로 찾는 함수는 아니다. 호출 전 목록 순서와 구분한다.
3. **layer merge 대표와 frame copy의 layer fallback:** 0x5b9104–0x5b912c 및 0x368a28–0x368a48의 목록 getter도 해당 목록 계열에서 first다. merge의 대표는 map entry가 보관한 AO 인스턴스 목록의 첫 항목이며 모든 frame 중 가장 빠른 시간·최소ID·첫 점을 새로 찾는 의미가 아니다. copy fallback은 그 시점의 layer 목록 첫 항목이다.
4. **일반 history stack:** 실제 GrowableList 수신자의 +0xbc49/removeLast와 +0x9780/last mapping도 복구했다. 기존 FILL-PRUNE-HISTORY의 역할 추론을 해당 class ID에서 직접 보강한다. 모든 collection subtype 또는 UI의 전체 호출을 동적으로 실행한 것은 아니다.

‘첫 점/첫 layer 단정 금지’라는 과거 지침은 근거 없는 슬롯 추측을 막기 위한 것이었다. 이번 수신 목록 계열과 실제 표·본문으로 확인한 정상 경로까지 미확정으로 남겨 같은 탐색을 반복하지 않는다. 반대로 다른 수신 클래스·미확인 selector까지 해결된 것으로 확대하지 않는다.

## 검증·보존

[감사](AOT-DISPATCH-TARGETS-AUDIT-2026-10-16.json)는6개 class/selector mapping과16개 명령 확인을 기록한다. 기존 direct GrowableList.first 호출도 같은 target으로 연결된다. 전체 VM table의 의미·실제 앱·픽셀 증명이 아니다.

비공개 `private-recovery/dispatch_out/dispatch-targets.csv`, `dispatch-summary.json`, decoder 검사 스크립트와 진단 tool을 보존한다. 다음에는 같은 표가 있는지 먼저 확인하고 전체 재추출·tool rebuild를 반복하지 않는다. runtime의 실제 수신 cid가 이 표에서 확인한 계열 밖이면 그 객체 class를 별도로 확인한다.
