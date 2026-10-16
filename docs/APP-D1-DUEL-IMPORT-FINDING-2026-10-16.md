# 결투 시연 SFA의 앱 가져오기 결과와 원인 조사 — 2026-10-16

## 앱 관찰 (사용자 제공: 앱 내보내기 MP4 1920×1080 264프레임, 편집 화면 녹화 61초)

- `tools/make_duel.py` 첫 버전(duel.sfa)을 가져오면 **선·곡선·원 외곽선이 한 픽셀도 그려지지 않는다.** 내보내기 프레임 104·10의 어두운 픽셀(R+G+B<150)은 0개다. 선만 있는 임팩트 프레임 66–68도 바탕색만 보인다.
- **채우기(FR)는 그려진다:** 땅 다각형, 큐브 면, 연기·폭발 원 채우기, 카나다 쐐기.
- 편집 화면에서도 같다. 그래서 내보내기 단계가 아니라 가져온 데이터를 그리는 단계의 문제다.
- 편집 화면은 캔버스 밖 도형도 보여 준다. 화면 밖으로 6000px 늘인 땅 다각형이 캔버스 바깥을 덮었다.
- 원 채우기 일부가 현과 쐐기 모양으로 잘려 보였다.

## 정적 근거 (비공개 AOT 캐시, `import_animation_activity.dart`)

- **AO ID→객체 map은 가져오기 전체에서 하나다.**
  - startElement의 AO 처리(0x50a8d4–0x50aa7c)는 handler.field_47 map에서 AO ID를 찾는다. 없을 때만 `CreateNewAnimationObject`(TypeId·Color 인수)를 호출하고 map에 넣는다.
  - field_47은 handler 생성자(0x50e398)에서만 설정된다. Frame endElement(0x50dc4c–0x50dce8)는 field_63/67/6b를 null로 하고 field_5f를 clear할 뿐, field_47은 비우지 않는다.
  - 따라서 같은 AO ID는 프레임이 달라도 같은 객체로 이어진다.
- `ThicknessScale`은 double parse 후 0.05 이하이면 1.0으로 바꾼다(0x50aabc–0x50aaf0).
- 앱에서 확인된 기존 프로브(probes_v1)의 규칙:
  - 같은 AO ID는 모든 프레임에서 같은 TypeId·점 수·연결이다.
  - Frame ID는 500000+n, AP ID는 10000000+n·1000+k다.
  - 프레임별 DrawOrder 변경은 기대대로 반영되지 않았다(APP-VERIFICATION 14).

## 첫 버전과 다른 점, 원인 가설

첫 버전은 프레임마다 AO ID를 그리기 순서대로 1부터 다시 매겼다. 같은 ID가 프레임에 따라 선·곡선·원·채우기 경계로 바뀌었고, Frame ID 1..264와 AP ID 1..도 작은 연속값이었다.

**가설:** 객체 정체성이 프레임 사이에서 어긋나 선 그리기가 사라졌다. 다만 정확한 소실 경로(점 압축 정렬, 상세 상속 등)는 **미확인**이다. 위 정적 근거는 "ID가 시퀀스 전체 정체성"이라는 데까지만 보여 준다.

## 수정 (duel_v2)

- AO ID를 풀로 고정했다. 풀 = (층, 종류[, 다각형 변 수]), ID = 슬롯.
  - 결과: 944개 ID, 형태 충돌 0.
- DrawOrder = ID이고, 층(배경 → 중간 → 인물 → 효과) 순서로 ID 범위를 배정했다. 각 층 안에서는 채우기를 먼저 둔다.
- Frame ID = 500000+n, AP ID = 10000000+n·10000+k.
- 다각형은 캔버스 ±60px로 자른다(Sutherland–Hodgman). 변은 최대 40개다.

## 남은 확인 (앱)

1. duel_v2를 가져와 선이 보이는지 확인한다.
2. 보이지 않으면 분리 파일 두 개를 가져와 원인을 가른다. 둘 다 48프레임이다.
   - A: ID 범위만 프로브식, 객체는 섞인 그대로
   - B: 객체만 고정, ID는 작은 연속값
3. 결과가 나오기 전에는 "ID 정체성이 원인"을 확정 규칙으로 쓰지 않는다.

## 2차 앱 결과 (같은 날, 사용자 제공 내보내기 3개)

- duel_v2·diag_A·diag_B 모두 **선은 여전히 0픽셀**이다. 이로써 "AO ID 재사용·ID 범위" 가설은 선 소실의 원인으로 **기각**된다.
- duel_v2에서는 원 채우기의 현·쐐기 모양 잘림이 사라졌고 채우기 순서도 맞다. 따라서 그 잘림은 ID 재사용 때문이었을 가능성이 있다.

### 추가 정적 근거

- 선 폭 = paint 폭 × (sequence.thickness/100, 현재 sequence가 없으면 1) × AO.field_37(ThicknessScale) ÷ DPR이다(SetPaintThickness 0x4152bc).
- DrawBaseObject(0x4150b8)는 폭 ≤ 0이면 그리지 않고 반환한다(0x415148–0x41516c). 채우기는 이 경로를 거치지 않는다.
- 가져오기는 CreateNewSequence로 thickness=100인 sequence를 만든다(0x36f2cc).
- 저장 경로: StoreImportedFrame → `_storeRoot`(frame_root, animation_object_detail) / `_writeImportedDetails` / frame_base 루트 상속.
- 어느 값이 0이 되는지는 **미확인**이다.

## 3차 시험 (판별용)

- `diag_C_attributes`: 앱에서 확인된 프로브 곡선(1)을 기준으로 둔다. 그 옆에 duel식 객체를 속성 하나씩 바꿔 나란히 놓았다.
  - 2 duel식 선 그대로
  - 3 ThicknessScale "1.0"
  - 4 부호 있는 검정 색값
  - 5 GlowThickness 20
  - 6 모두 프로브식
  - 7 duel식 곡선
  - 8 원 외곽선
  - 9 외곽선 있는 채운 사각형
- `diag_D_attributes_plus_450`: diag_C와 같고, 아래쪽에 duel식 짧은 선 450개를 더했다.
- 판정
  - 프로브 곡선(1)까지 사라지면 파일/규모 수준 원인
  - 프로브만 보이면 객체 속성 원인 → 보이는 열로 해당 속성을 특정
  - C에서는 보이고 D에서만 사라지면 객체 수 원인
