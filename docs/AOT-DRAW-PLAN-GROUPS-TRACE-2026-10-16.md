# 그리기 계획: 레이어·연결 묶음·채우기 배정 — 2026-10-16

복구한 같은 ELF/AOT에서 확인했다. [감사](AOT-DRAW-PLAN-GROUPS-AUDIT-2026-10-16.json)는 선택 명령 20곳의 Capstone/AOT 대조다. 실제 사용자 작품 영상 대조([USER-ARTWORK-1](USER-ARTWORK-1-RENDER-CHECK-2026-10-16.md))로 결과를 검증했다.

## Frame.BuildDrawPlan(0x42b910)

1. 레이어 목록이 비어 있으면 "Layer 1"(번호 0) 기본 Layer를 만든다(0x42b9a4–0x42b9b8).
2. 프레임의 AO 목록으로 `FillRegionsByFigure`를 만든다(0x42bae8–0x42bb0c). 이어서 `_ResolveConnectedObjectGlowGroupIds`로 AO→묶음 ID map을 얻는다(0x42bb1c).
3. 레이어 목록을 순서대로 순회한다. Layer의 visible(field13)이 false이면 건너뛴다(0x42bbb8/0x42bbc0).
4. 레이어마다 `_BuildLayerObjectGroups`(0x42bbe4)의 묶음 목록을 순회한다. 묶음마다 glow용 FrameDrawUnit을 만든다(0x42bc34).
5. 묶음의 구성원을 순서대로 보며 `FillRegionsByFigure.take(AO ID)`(0x42bd64)로 그 구성원이 가져갈 채우기를 받는다. 구성원마다 (채우기+본체) FrameDrawUnit을 만든다(0x42bdcc).

따라서 그리는 순서는 다음과 같다.

**레이어 목록 순서(앞이 아래) → 레이어 안 묶음 순서 → 묶음마다 [모든 구성원 glow] → 구성원마다 [가져간 채우기 → 본체]**

숨긴 레이어는 그리지 않는다. 이는 APP-T1의 hidden_layer 결과와 같다.

## Frame._BuildLayerObjectGroups(0x42c2c8)

프레임 AO 목록을 **목록 순서대로** 순회하며 LayerId(field7)가 현재 레이어인 객체만 고른다(0x42c370–0x42c378). 객체의 묶음 ID는 map에서 찾고, 없으면 자기 AO ID를 쓴다(0x42c37c–0x42c3a0). LinkedHashMap에 넣으므로 묶음 순서는 그 묶음의 첫 구성원이 목록에 처음 나온 순서다. **같은 연결 묶음이라도 레이어가 다르면 레이어마다 따로 그려진다.**

## Frame._ResolveConnectedObjectGlowGroupIds(0x42c53c)

모든 AO의 점을 순회해 점 ID→소유 AO 맵을 만든다(GetAnchorPoints 0x42c698). 다음으로 각 점의 연결 목록(field2b, 0x42cab0)의 대상 소유 AO와, `AnchorPoint.ResolveGroupParentId`(0x42cbac)가 찾은 부모의 소유 AO를 closure로 합친다(union). 마지막으로 AO마다 묶음 대표 ID를 `putIfAbsent`로 기록한다(0x42cd38). 중간의 조건 분기는 iterator moveNext(GDT −0x1000)이며, glow 유무 같은 객체 필터가 아니다.

**결론:** glow 묶음은 그룹 Flags만이 아니라 **AC(점 연결)로 이어진 모든 객체의 연결 묶음**이다. 관절로 연결된 스틱맨은 한 묶음이 되어, 모든 glow가 본체들 아래에 깔린다.

## 실물 검증과 남은 것

- 사용자 작품 244프레임에서 이 순서를 적용해 평균 MAE가 1.155(레이어 순서만 반영한 렌더러)에서 0.908이 됐다. 같은 날 glow 폭 × ThicknessScale 발견도 함께 반영된 수치다.
- `FillRegionsByFigure`의 키(어느 ObjId로 색인되는지)는 본문 closure(0x42d798)를 읽지 않았다. 렌더러는 "참조 객체 중 묶음 순서상 첫 구성원이 가져간다"로 근사한다. outer segment만 색인하는지 등 세부는 미확인이다.
- 보간 프레임(InterpolatedFrame)의 그리기 경로가 같은 계획을 쓰는지는, 보간 호출자도 그룹 helper를 먼저 호출한다는 기존 근거(0x793260/0x793534)와 실물 대조로만 확인했다. 본문 전체는 읽지 않았다.
