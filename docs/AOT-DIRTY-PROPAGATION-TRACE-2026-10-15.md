# 객체 변경→그룹 glow·채우기/구멍 갱신 전파 — 2026-10-15

- 기존 AOT/PP/원본 ELF의 정적 호출·인수·저장 슬롯을 추적했다.
- 앱의 실제 수정/영상/픽셀 시험이 아니며 원본·역컴파일 코드·assembly를 공개하지 않는다.
- 이전 CACHE-BOUNDARY의 남은 생성자 의존 표를 연결했다.

## 1. record가 만드는 세 가지 역참조

- _FrameRecord 생성자(0x4291b4)는 먼저 BuildDrawPlan을 만들고, 현재 AO/FR의 목록 위치를 알아내는 두 HashMap.identity를 만든다(0x42a254–0x42a314).
- 숫자 ID를 객체 identity와 혼동하지 않는다.
- 별도로 **AO.ID→같은 ID를 가진 AO 목록 위치들의 List<int>**를 만든다(0x42a4cc–0x42a55c).
- 이 부분은 같은 ID에 마지막 객체 하나만 남기는 map이 아니다.

생성자는 plan의 모든 FrameDrawUnit을 순회한다. 앞 보고서의 unit.field_b=null이면 그룹 glow-only unit, 객체가 있으면 그 객체의 fill/본체 unit이라는 정의와 연결된다.

| record 슬롯 | 목록 위치별 저장 내용 | 공급 |
|---|---|---|
| field_4f | AO→자기 객체의 fill/본체 unit index | 객체 unit.field_b를 AO identity map으로 조회,현재 unit index 저장(0x42a7c8–0x42a814) |
| field_53 | AO→자신이 속한 그룹 glow unit index | glow-only unit.field_7의 AO를 순회,identity map 조회 후 현재 index 저장(0x42a5e8–0x42a78c) |
| field_57 | FR→그 FR이 그려지는 객체 unit index | 객체 unit.field_17의 FR을 identity map으로 찾아 현재 index 저장(0x42a828–0x42a994) |
| field_5b (_followers) | AO→그 AO를 경계로 참조하는 fill unit index들의 Int64List | 아래 segment ObjId 역참조·중복 제거 |

- 없는 연결의 int index 배열은 −1 초기값을 사용한다.
- 목록 위치와 unit index는 SFA 영구 ID가 아니다.
- 실제 렌더링 차례는 앞에서 생성한 plan의 unit 순서다.

## 2. 구멍도 fill 의존성에 들어간다

- 객체 unit에 들어 있는 각 FR의 field_17 **전체 segment 목록**을 순회한다(0x42a9a4–0x42aa10).
- 각 segment.field_b=ObjId를 앞의 AO.ID→목록 위치들 map에서 찾아, 해당 AO 위치마다 현재 fill unit index를 Set에 추가한다(0x42aa10–0x42ab44).
- segment의 contourIndex가 0인지 검사해 hole을 제외하는 분기는 이 loop에 없다.

- field_17이 전체 경계 목록이라는 점은 _storedFillContours(0x367de4)가 같은 목록을 읽고 segment.field_33=contourIndex로 나누는 것과 연결했다(0x367e1c/0x367e64).
- 따라서 outer와 hole 모두 같은 FR을 그리는 unit에 의존한다.
- hole 전용의 별도 draw unit을 새로 만드는 방식은 아니다.

- 동일한 AO가 한 FR에서 여러 segment로 참조되거나, 여러 FR이 같은 객체 unit에 포함되면 Set이 unit index 중복을 제거한다.
- 만들어진 AO위치→Set을 forEach로 순회해 Int64List로 복사하고 _followers 배열에 넣는다(0x42abb4/0x42abe8,closure0x42d7e0).
- 저장 순서를 임의 정렬이라고 부르지 않는다.

- 이 연결은 **그 FR이 현재 plan의 unit에 배정되어 있을 때**의 규칙이다.
- 존재하지 않는 ObjId는 조회된 AO 위치가 없어 연결되지 않는다.
- 고아 FR이 어떤 unit에 배정되는지까지 이 역참조 코드만으로 확정하지 않는다.

## 3. 좌표/속성 변화의 영향 집합

앞 보고서의 _holdsValues가 false이면 update는 현재 속성을 임시 값 목록에 만들고, 기존 snapshot을 덮어쓰기 전에 글로우의 변경 전후 상태를 비교한다. glow 활성 판정은 여기서 Radius>0 AND GlowAlpha>0다.

- 기존 Radius>0과 기존 GlowAlpha>0이면 glow 갱신 필요.
- 아니면 새 Radius>0과 새 GlowAlpha>0인지 확인.
- 둘 다 비활성이면 이 검사에서는 glow unit을 추가하지 않는다.

즉 **oldActive OR newActive**다(0x42e3fc–0x42e4a4). 새 상태만 검사하면 기존 glow를 끌 때 갱신이 빠질 수 있는데, 읽은 코드는 이전 상태도 포함한다. W/sigma·shader 선택 조건 전체를 이 간단 활성 검사와 동일하게 해석하지 않는다.

속성 snapshot을 갱신한 뒤 영향 unit Set에 다음을 추가한다:

1. 자기 fill/본체 unit: field_4f 값이 0이상일 때(0x42e560).
2. 그룹 glow unit: oldActive OR newActive이고 field_53이 0이상일 때(0x42e568–0x42e5c8).
3. 자신의 _followers가 null이 아니면 그 안의 모든 fill unit(0x42e61c).

- 따라서 outer/hole 경계 AO의 점을 움직여 _holdsValues 차이가 생기면, 그 AO의 본체뿐 아니라 연결 FR을 포함한 unit도 갱신 대상으로 들어간다.
- 그룹 glow unit 하나를 갱신하면 그 unit은 그룹 구성원의 DrawGlowEffect를 순회한다.
- 그룹 실루엣 하나를 union blur한다는 뜻은 아니다.

- 형상에 영향 없는 색 변경에서도 _holdsValues 차이를 통해 followers가 갱신 대상으로 들어갈 수 있다.
- 읽은 코드는 모든 속성 차이를 geometry 변경으로 정밀 분류해 최소량만 재기록하는 알고리즘이 아니다.
- 재기록된 unit 내부에서 holed-path/glow image key가 같으면 별도 geometry cache를 재사용할 수 있다.

FR 색은 별도 loop에서 field_f와 저장된 색 snapshot을 비교한다. 다르면 snapshot을 바꾸고 field_57의 unit을 영향 Set에 넣는다(0x42e6c8–0x42e76c). FR색만 바꾸는 경우 AO 글로우를 반드시 다시 그린다고 일반화하지 않는다.

## 4. 그룹 Flags와 구조 재생성

- AnchorPoint.GetXml의 Flags는 field_f다(0x5af644–0x5af650).
- _FrameRecord.update는 point identity·ID(field_1b)뿐 아니라 이 Flags도 보관된 값과 비교한다(0x42e10c–0x42e190).
- 다르면 null을 반환하는 구조 부적합 경로다.
- 이는 x/y/Index가 달라진 경우의 값 비교·부분 갱신과 구분된다.

- 실제 _handleFrameGroupTap 경로에서 Flags의 상위 그룹 참조/비트 0x10을 조합해 field_f에 저장하거나 해제하는 명령을 확인했다(0x5e61d4–0x5e61f4,해제 0x5e5a74–0x5e5a94).
- 따라서 그룹 조작 뒤 다음 paint의 Flags 대조가 부적합하면 기존 record/plan을 계속 쓰지 않고 CACHE-BOUNDARY의 새 _FrameRecord→BuildDrawPlan 경로로 연결된다.
- 직접 프레임 조작의 모든 분기를 실행시험한 것은 아니다.

FrameDrawPlanCache.fits만 보고 ‘Flags 변경이 무시된다’고 판단하면 편집기 쪽 구조 검사를 빠뜨린다. 반대로 이 EditorFrameCache guard가 존재한다고 view/export의 모든 캐시에도 동일한 guard가 있다고 가정해서는 안 된다.

## 5. 실제 채우기 변경과 레이어 병합 사례

_applyFillTapResult(0x5e40e8)의 읽은 UI 적용 경로:

- 제거할 기존 index가 있으면 Frame.field_33의 FR 목록에서 해당 index를 제거한다.
- 추가할 경계가 있으면 새 FrameFillRegion을 만들고 color를 저장한다.
- segment 목록을 List.from(growable:false)로 복사하고 makeFixedListUnmodifiable를 거쳐 새 FR.field_17에 넣고 Frame FR 목록에 추가한다(0x5e41bc–0x5e4244).

- 이는 기존 FR의 segment를 그 자리에서 수정하는 구현이 아니다.
- 추가/삭제는 FR 목록 길이 또는 항목 identity 대조를 통해 record 재생성 조건으로 이어질 수 있다.
- 이 함수가 모든 색 변경·구멍 편집 기능의 유일한 적용자라고 주장하지 않는다.

- 그리기 순서는 _mergeLayerDown(0x5b86f4) 한 사례를 확인했다.
- 병합 중 AO 목록을 sort하고(0x5b9690), 성공 후 _evictRenderableFrameCache→_markFrameDataDirty→_loadFrame을 호출한다(0x5b97c8/0x5b9830/0x5b9840). 따라서 이 사례를 ‘DrawOrder 숫자만 바꾸고 기존 모든 렌더 캐시를 유지’한다고 읽으면 틀린다.
- 이름이 비슷한 compareDrawOrder/resolveDrawOrder closure를 전역 정렬 정책으로 확대하지 않는다.

**미완:** 레이어 병합 이외 모든 순서 변경 UI의 계약, FR segment 인스턴스의 모든 변경자, view/renderable-frame 캐시의 revision/eviction 전체 키. 이번에는 한 UI 사례와 구조 guard까지 연결했으며 전 기능 수정 후 갱신 보장으로 집계하지 않는다.

## 6. 정적 산출 관계 예시

아래는 index 관계를 설명하기 위한 예시이며 실제 사용자 SFA나 앱 시험이 아니다.

| 변경 | 이번 연결에서 영향 Set에 들어가는 단위 |
|---|---|
| AO A 좌표 변경, 활성 glow 있음 | A의본체 unit + A그룹 glow unit + A를참조하는 FR들의 unit |
| hole AO H 좌표 변경 | H본체 + 활성 조건의 H그룹 glow + H가구멍경계인 FR의 unit |
| A glow를 활성→비활성으로 변경 | A본체 + 기존활성에따른그룹 glow + followers |
| A glow가 변경 전후 모두 비활성 | A본체 + followers; 이 활성검사로 glow unit 추가안함 |
| FR색만 변경 | 해당 FR이배정된 unit |
| 그룹 연결 Flags 변경 | 구조불일치→record 재생성/새 plan 경로 |

Set이 중복을 제거하므로 자기 unit에 포함된 FR이 다시 참조되어도 같은 index는 한 번만 남는다. 이후 paint는 기존 보고서의 부분 기록 조건/전체 재기록 경로를 선택한다.

## 7. 검증과 다음 단계

- 새 54명령 ELF PT_LOAD/Capstone 대조 통과. 압축 pointer 비교 0x42a5e8의 symbolic `cmp w0,NULL`은 실제폭 w22로 정규화했음을 audit에 기록했다.
- AOT-DIRTY-PROPAGATION-AUDIT-2026-10-15.json. 이전 54/65표본과 일부 중복이 있으므로 서로 다른 명령 수로 단순 합산하지 않는다.

- 문서만 변경했다.
- 기존 unittest/probe/영상/설치/페어링/휴대폰 시작 시험은 반복하지 않았다.
- PC 확보·학교 Wi-Fi 제약 상태에서 지금 사용자 추가작업은 없다.
- license응답 4/runtimepixel 미확인과 보호 자료 상태를 유지한다.

- **정확한 다음:** _evictRenderableFrameCache/_markFrameDataDirty와 renderable-frame cache의 identity/revision key를 확인하고, 일반 그리기 순서 변경 UI 및 FR 변환/segment 교체 호출자로 이어진다.
- 외부 DB 저장·다시불러오기에서 편집/재생 캐시가 어떤 범위로 폐기되는지 구분한다.
- 폐기와 디스크 데이터 변환을 같은 단계로 묶지 않는다.

캐시:e23c9fd610d3/private/blutter_out/asm/sfa/{main.dart,original_port/editor/editor_frame_cache.dart,original_port/sequences/{anchor_point,frame_fill_region}.dart},PP/원본 ELF/venv. 신규검사 5a16c98ed7ee/private-trace/{validate_dirty_propagation.py,dirty-propagation-validation.json}. 문서 worktree5a16c98ed7ee/AI-sfa-publish. 옛 dirtyworktree·원본보존.
