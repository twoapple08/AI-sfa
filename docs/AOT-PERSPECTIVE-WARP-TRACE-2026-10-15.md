# 원근 도구의 선택·핸들·사영/쌍선형 분기 — 2026-10-15

기존 main.dart AOT와 ELF를 재사용해 원근 도구의 정상 프레임 편집 경로를 추적했다. 기존 04 영상·SFA를 다시 분석하지 않았고 새 실제 앱 시험도 하지 않았다. 공개하는 것은 직접 작성한 규칙·주소 및 명령 일치 여부뿐이다.

## 선택과 드래그 기준

_collectPerspectiveConnectedAnchorPoints(0x5d8768)는 GetAllConnectedAnimationObjects를 호출하고, 각 AO의 점을 ID→AP map에 putIfAbsent로 모은 뒤 시작 점도 같은 방식으로 포함한다. 대상 AO의 확장 규칙은 [연결 대상 보고서](AOT-CONNECTED-TARGET-REFLECTION-TRACE-2026-10-15.md)를 재사용한다. 이 helper를 현재 화면의 모든 객체·모든 프레임을 고르는 명령으로 일반화하지 않는다. 앞단 tap anchor/hit-test와 올가미의 모든 선택 경계는 미완이다.

_handleFramePerspectivePanStart(0x5f3b1c)는 Frame·Sequence·선택 상태가 없으면 반환한다. 전역 올가미 설정이 켜진 경로는 _handleFrameLassoPanStart로 위임한다. 일반 경로는 핸들 hit-test 후 편집 context를 buildTree=false로 만들고, 선택 anchor를 map에서 찾아 현재 점들의 화면 좌표를 수집한다.

시작 closure0x5f4a14는 현재 quad를 sourceQuad로, 수집한 화면 좌표 map을 sourceAnchorScreenPositions로 copyWith에 전달한다(0x5f4abc). drag session은 핸들과 시작 quad 복사본을 보관하고 moved=false로 시작한다. _PerspectiveSelectionState 생성자는 quad/source/origin 목록 및 화면좌표 map을 복사해 수정 불가 형태로 보관한다. 따라서 매 이벤트에서 직전 결과에 변형을 누적 적용하는 규칙으로 구현하면 안 된다.

## 여덟 핸들

_applyPerspectiveHandleDrag(0x5ee148)는 입력 quad를 복사한다. 네 점이 아니면 그 복사본을 그대로 반환한다. 아래 Q0…Q3은 순서대로 배치된 네 꼭짓점이며 P는 현재 화면 포인터다. 표의 번호는 enum 내부 index다.

| index | 변형 |
|---|---|
| 0 | Q0=P |
| 1 | Q0.y=Q1.y=P.y, 각 x 유지 |
| 2 | Q1=P |
| 3 | Q1.x=Q2.x=P.x, 각 y 유지 |
| 4 | Q2=P |
| 5 | Q2.y=Q3.y=P.y, 각 x 유지 |
| 6 | Q3=P |
| 7 | Q0.x=Q3.x=P.x, 각 y 유지 |

이 helper는 화면 x/y 축에 맞추어 변의 두 좌표를 놓는다. 기울어진 변의 법선 방향으로만 이동시키는 일반 변형 수식으로 바꾸면 다른 동작이 된다. 여기서 음수 좌표나 출력 사각형 밖 좌표를 clamp하지 않는다.

_hitTestPerspectiveHandle(0x5f3db4)는 현재 quad로 핸들 위치 map을 만들고 화면 거리 제곱을 비교한다. 초기 한계324=18²이며, 그 이하인 가장 가까운 후보로 갱신한다. 거리가 같아도 갱신하므로 최종 동률 선택은 순회 순서의 영향을 받는다. 이는 화면 논리 단위이며 MP4 픽셀로 단정하지 않는다. 핸들 위치 map 자체의 모든 예외·순서 규약은 별도 미완이다.

## 적용 전 유효성은 ‘볼록 사각형’ 검사가 아니다

_isValidPerspectiveQuad(0x5ee000)는 점 수4·모든 좌표 finite를 확인한 뒤 모든 점 쌍 거리의 최댓값이2보다 큰지를 확인한다. 면적·변 교차·볼록성 검사로 해석하면 틀린다. 이 검사 통과만으로 사영행렬의 역행렬이나 모든 내부 점의 유효성이 보장되는 것도 아니다.

## 변형 선택

_applyPerspectiveWarpToAnchorPoints(0x5ebd20)에서 호출하는 _warpPerspectivePoints(0x5ebfa4)의 인수 순서는 **목적 quad D, 원본 quad S, 원본 화면좌표 map**이다. SetupParameters 이름 대신 실제 재배치와 caller field 전달을 확인했다.

각 quad Q의 signed span을 다음처럼 정의한다.

- H(Q)=((Q1.x+Q2.x)−(Q0.x+Q3.x))/2
- V(Q)=((Q3.y+Q2.y)−(Q0.y+Q1.y))/2

_shouldUsePerspectiveLinearFlipWarp(0x5edb30)는 정상 finite 네 점 입력에서 다음을 확인한다. 가로 또는 세로 축 중 하나라도 조건에 맞으면 쌍선형 경로를 먼저 선택한다.

1. 목적 span의 절댓값 ≤0.5.
2. 원본·목적 span의 절댓값이 각각 >0.5이고 부호가 다름.

그 외에는 사영 경로를 먼저 시도한다. 선택한 경로가 null을 반환하면 쌍선형 경로를 호출한다(처음부터 쌍선형을 선택했다가 실패한 경우 같은 helper가 다시 호출되는 제어 흐름도 포함). NaN/inf의 부호 규칙까지 이 간단한 식으로 일반화하지 않는다.

따라서 원근 도구는 항상 homography 하나를 사용하는 기능이 아니다. 기존 04 표본의 사영 적합/아핀 변화 관찰과 별개로, 이번에는 그 선택 분기의 정적 근거를 확보했다. 해당 표본이 정확히 어느 branch를 실행했는지 새로 입증한 것은 아니다.

## 사영변환과 실패

_buildPerspectiveTransform(0x5ec3f4)은 네 대응점에서 두 식씩, 8개 미지수의 선형계를 구성한다. 원본 점(x,y), 목적 점(X,Y), 미지수를 a…h라 쓰면 다음 관계다.

X=(a x+b y+c)/(g x+h y+1), Y=(d x+e y+f)/(g x+h y+1).

_solveAugmentedLinearSystem(0x5ecc9c)은 각 열에서 아래 행들의 pivot 절댓값을 비교해 큰 행을 고르고, 최대값이1e−7 미만이면 null을 반환한다(0x5ecee0–0x5ed334). 선택 행 교환·pivot 나누기·다른 행 제거가 이어지며, 작은 제거 계수는 건너뛰는 분기가 있다. 이 문서는 전체 비정상 행렬에 대한 수치해석 보장을 제시하지 않는다.

_PerspectiveTransform.mapPoint(0x5ec264)는 w=gx+hy+1을 계산한다. w가 finite가 아니거나 |w|<1e−6이면 null이다. 나눗셈 뒤 X/Y도 finite여야 한다. _resolvePerspectiveProjectivePositions는 어느 원본 점 하나라도 mapping에 실패하면 부분 결과를 반환하지 않고 전체 null로 나가 쌍선형 fallback으로 이어진다.

## 쌍선형 변형

_resolvePerspectiveBilinearPositions(0x5ed5b8)는 원본 quad의 축 정렬 bounding rect를 구한다. 원본 네 점이 finite여야 하고 rect의 폭·높이가 각각1e−6 이상이어야 한다. 목적 quad의 역쌍선형 좌표를 푸는 함수가 아니다.

원본 화면 점 p에 대해 u=(p.x−left)/width, v=(p.y−top)/height를 구한다. 그다음 목적 quad에서 위쪽 D0→D1을 u로 보간하고 아래쪽 D3→D2를 u로 보간한 두 점을 다시 v로 보간한다.

p'=(1−v)[(1−u)D0+uD1]+v[(1−u)D3+uD2].

이 구간에 u/v clamp는 없다. rect 바깥 점에는 외삽이 가능하다. 결과 점 하나라도 finite가 아니면 전체 null이다. 원본 rect가 지나치게 작으면 이 fallback도 실패하므로 모든 조작이 항상 성공하는 것은 아니다.

## 좌표 저장·재그리기

일반 handle pan update는 새 quad 계산→유효성→warp→성공 시 선택 quad 교체 순서다(0x5eba60/6c/b0/e4). warp는 모든 결과 map을 만든 뒤 AP map에 해당 ID가 있으면 화면좌표를 DrawInformation Offset/UsableCanvasSize로 역변환해 백분율 x/y에 저장한다(0x5ebf2c/30). map에서 못 찾은 ID는 건너뛴다. 성공 true가 반드시 실제 좌표 차이 >0이라는 뜻은 아니다.

이 좌표 적용 helper와 일반 update의 확인 구간에는 AO ThicknessScale/ObjectScale/Glow 속성 저장이 없다. 원근 모드 전체에는 올가미·AllGroupDrag로 위임하는 별도 경로도 있으므로 ‘원근 모드의 모든 조작은 속성을 절대 바꾸지 않는다’로 확대하지 않는다. 기존 04의 속성 변화 원인을 이 한 경로만으로 단정하지 않는다.

성공 후 dragMoved와 화면 재그리기로 이어진다. 일반 pan end는 session moved가 true이면 _saveAfterMove를 호출한다(0x5e9288/0x5e92a8). 저장/좌표 diff와 전체 저장 fallback은 [올그룹 보고서](AOT-ALLGROUP-BOX-TRACE-2026-10-15.md)의 기존 확인을 재사용한다.

## 올가미 설정 경로는 AllGroupDrag

_handleFrameLassoPanStart(0x5f4210)→_resolveLassoTarget(0x5f4378)→AllGroupTarget.ofPoints(0x5f4630)→gripAt→시작 closure0x5f4894→AllGroupDrag 생성(0x5f4964) 연결을 확인했다.

_resolveLassoTarget은 기존 원근 선택의 화면좌표 map 키를 Set으로 만들고, 현재 Frame의 AO/점 순회 중 그 ID에 들어 있는 점을 목록에 넣는다. 이 함수가 새 자유곡선 polygon의 내부를 판정하는 것은 아니다. AllGroupTarget.ofPoints는 그 **입력 점 목록**과, 점이 소속된 AO를 AO ID로 중복 제거한 별도 목록을 _inBox에 전달한다. 점의 소유 AO를 모았다는 이유만으로 그 AO의 모든 점을 이 함수가 입력 점 목록에 추가하는 것은 아니다. 일반 collectAllGroupFigures의 표시/잠금 필터를 이 helper가 재실행한다고도 단정하지 않는다.

따라서 좌표 대상 점 목록과 속성 대상 AO 목록은 구분해야 한다. AllGroupDrag의 기존 규칙에 따라 모서리 확대는 입력 점을 옮기고 대상 AO의 t/o/Radius를 바꾼다. 반면 일반 원근 핸들은 위의 warp 좌표 쓰기로 간다. 이 구분은 기존 04 속성 변화의 가능한 코드 경로를 제공하지만, 영상의 해당 동작이 이 경로였다는 새 실제 검증은 아니다.

update는 lasso drag session이 있으면 먼저 dragTo로 가며 일반 homography 경로로 내려가지 않는다(0x5eb974/98c). 끝에서는 canvas dirty/drag session 제거, moved면 leftBox 보관 및 _reselectAfterLasso, 마지막 _saveAfterMove로 이어진다. 재선택은 이전 선택 anchor ID를 현재 Frame map에서 찾아 새 원근 선택을 만들고 실패하면 이전 선택을 유지한다. 완전히 새 polygon 선택으로 바꾼다고 해석하지 않는다.

## 검증·남은 범위

새 선택 명령130개를 ELF/Capstone과 대조해 모두 일치했다. 집계는 AOT-PERSPECTIVE-AUDIT-2026-10-15.json이다. 다른 보고서 표본과 독립 표본 수로 합산하지 않는다. 원본·assembly·실행 로그는 공개하지 않는다. 문서만 변경하여 기존 unit/probe/폰 시험을 반복하지 않았다.

이번에 닫은 것은 일반 프레임 원근 핸들의 선택·변형 방식과 fallback·좌표 저장 경로다. 앞단 tap/자유곡선 선택 전체·원/곡선의 최종 픽셀·수치 경계의 실제 앱 결과·사용자 정의 figure 편집과의 동등성은 미완이다. 다음은 선택 anchor를 결정하는 앞단 tap/hit-test와 사용자 정의 figure 편집 경로의 차이다. 같은 행렬·기존04 영상을 다시 분석하지 않는다.
