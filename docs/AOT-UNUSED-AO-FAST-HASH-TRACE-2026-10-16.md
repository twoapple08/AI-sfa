# 미사용 객체 정리와 Frame 변경 해시 — 2026-10-16

복구된 동일 ELF/AOT의 남은 두 함수를 추적했다. 기존 개별 점 삭제·history caller 결과는 재사용한다. 새 앱·영상 시험은 없다. 서버 복구 자체와 이번 새 함수 의미 분석을 구분한다.

## 미사용 AO는 실제 점과 가상 기반 점을 모두 검사

`_cleanupUnusedAnimationObjects`(0x3662a4)는 입력 AO ID가 비면 반환하고, 중복 제거한 후보 C를 만든다. 후보가 아닌 모든 AO를 이 helper가 처음부터 순회해 삭제하는 구조가 아니다.

먼저 후보 ID chunk별로 **frame_root의 frame이 아닌 실제 anchor_point**가 참조하는 AO ID 집합 A를 구한다(0x366328/0x3663a8/0x36645c/0x366480). 현재 삭제 중인 frame 하나로 한정한 점 조회가 아니다. 그다음 C에서 A에 없는 후보만 모아 `_figuresShownFromRoots`(0x366bc8)에 보낸다(0x3666ec–0x3667a4). 반환 집합 R을 A에 합친 뒤 C 중 그 합집합에 없는 ID만 삭제 대상으로 만든다(0x3667b0/0x366870–0x366918).

정상 정수 ID 입력에서 정리하면 **D = C \ (A ∪ R)**다. 실제 점 하나가 다른 비root frame에 남아 있거나, 아래 조건의 가상 기반 점 하나가 남아 있으면 이 정리의 삭제 대상에서 빠진다. 객체 목록에 없다는 이유만으로 현재 frame 편집 시 sequence 전체의 해당 AO 정의를 지우는 것으로 구현하면 다르다.

### ‘Shown’은 저장 구조의 잔존 검사다

`_figuresShownFromRoots`는 후보가 비었거나 frame_base가 하나도 없으면 빈 set을 반환한다. `_hasFrameBases`(0x366f0c)는 frame_base 존재 여부를 SELECT 1/LIMIT 1로 확인한다.

나머지는 후보별로 root 점 rp와 frame_root r, 그것을 참조하는 frame_base b를 연결해 아래가 존재하는지 검사한다.

- rp의 AO ID가 해당 후보 ID다.
- rank = r.first_point_id − rp.ID가 b.point_count보다 작다.
- 가상 ID V = b.first_point_id + rank에 실제 anchor_point 행이 없다.
- 같은 V의 frame_base_removed_point 행도 없다.

근거는 0x366cd0/0x366d84/0x366d8c/0x366db8이다. 읽은 SQL은 layer.visible/locked, viewport 또는 render plan 가시성을 검사하지 않는다. 이 함수 이름의 shown을 ‘현재 화면에 보임’으로 번역하지 않는다. 해당 SQL에 없는 rank≥0 조건이나 removed 행의 추가 frame 조건을 임의로 붙이지 않는다. 정상 root/ID 자료의 전제를 넘어 malformed DB의 모든 결과를 보장한 것은 아니다.

### 최종 삭제의 순서

D가 비면 DB 삭제 없이 반환한다. 나머지는 chunk별로 fill 참조 정리→animation_object_detail→figure_definition_part→animation_object 행 삭제로 연결된다(0x366920/0x36693c/0x3669a0/0x366a64/0x366aa8/0x366aec). 이 helper 안에서 별도의 새 transaction을 시작하는 경로로 세지 않는다. 바깥 선택 객체/프레임 삭제 caller의 transaction과 구분한다.

fill의 구멍/outer 처리와 공유 표현 차이는 [LAYER-MERGE-DELETE-ADD](AOT-LAYER-MERGE-DELETE-ADD-TRACE-2026-10-15.md)를 재사용한다. 삭제 원자성·동시 외부 수정·모든 root 수명의 증명으로 확대하지 않는다.

## GetFastHash는 전체 상태 동등성 검사가 아니다

`Frame.GetFastHash`(0x51cb64)는 호출할 때마다 순회해 정수 해시를 반환한다. 본문에는 계산 결과를 Frame의 해시 cache 슬롯에 저장하고 재사용하는 경로가 없다. 별도의 ‘FastHash cache 무효화’를 가정할 필요가 없다. 단, 입력 AO는 `GetAnimationObjects`가 반환하는 현재 메모리 목록이다. 그 getter는 목록이 null이면 빈 목록을 만들어 보관하고 반환하며 여기서 DB를 다시 읽지는 않는다(0x34eb9c–0x34ec1c). 따라서 DB가 외부에서 바뀌었다는 이유만으로 이 함수가 새 값을 자동 로드한다고 해석하면 안 된다.

일반 정수·유한 좌표 입력의 주요 연산은 M=0x7fffffff, mix(h,k)=(31h+k)&M이다. 초기 h=(Frame.Position.hashCode+527)&M이며 Position은 GetPosition/Frame XML의 Position 공급과 같은 field17이다(0x34eb28/0x5ae934/0x51cb84).

| 순회 | 넣는 값과 순서 |
|---|---|
| Frame의 fill 목록 순서 | 각 FR의 ARGB(fieldf).hashCode → 전체 segment 개수.hashCode |
| 현재 AO 목록 순서 | AO ID(field57).hashCode → AO ARGB(field4f).hashCode → DrawOrder(field2f).hashCode |
| 각 AO의 anchor 목록 순서 | round(x×10000).hashCode → round(y×10000).hashCode → Flags(fieldf).hashCode |

색 field를 혼동하지 않도록 AnimationObject XML의 Color→field4f(0x5af264/0x5af274), TypeId→field47(0x5af22c/0x5af23c), LayerId→field7(0x5af29c/0x5af2ac)도 대조했다. field4f를 TypeId로 추측하면 해시 포함 범위를 잘못 적게 된다. FR의 fieldf 색은 기존 DIRTY-PROPAGATION 근거를 재사용한다.

양자화 상수는 PP의 **64-bit double 10000**, 곱셈과 LibcRound 후 정수 변환이다(0x51cf58–0x51cfac,0x51d010–0x51d060). 표시용 문자열 비교나 epsilon을 직접 비교하는 함수가 아니다. 좌표는 1e−4 단위의 반올림 칸으로 들어간다. NaN/무한대/정수 변환 한계의 전체 결과는 이번 정상 입력 수식으로 확정하지 않는다.

이 본문은 layer 정의/활성 layer, AO LayerId·TypeId·ThicknessScale·ObjectScale·glow 속성, 점 ID·Index·outgoing 연결, fill segment의 각 참조/좌표/contour 내용을 직접 fold하지 않는다. fill에서는 색과 개수만 넣는다. AO/점 순서는 결과에 영향을 줄 수 있지만 해시 충돌 없는 식별자는 아니다.

따라서 다른 항목이 같을 때 x=1과 x=1.00001은 반올림된 정수10000으로 같아지고, FR의 색·segment 개수는 같고 경계 참조만 바뀌어도 이 해시에는 같은 값이 들어갈 수 있다. 이 예시는 함수의 정보 손실을 설명하는 산술상 사례이며 새 앱 시험이 아니다. 반대로 AO 색은 실제 포함되므로 ‘모든 색 변경을 놓친다’고 일반화하면 틀린다.

`_historySignatureOf`는 이 해시와 별도 tween link signature를 조합한다. custom history의 전체 `sameFrameForHistory`와는 다른 범위다. 특정 편집 UI의 undo가 반드시 누락된다는 결론은 각 기록 caller·강제 기록/적용 조건까지 확인해야 하며 이 본문만으로 단정하지 않는다. 기존 [FILL-PRUNE-HISTORY](AOT-FILL-PRUNE-HISTORY-TRACE-2026-10-15.md)의 stack/복원/비교 근거는 유지한다.

## 검증과 남은 범위

[감사](AOT-UNUSED-AO-FAST-HASH-AUDIT-2026-10-16.json)는 선택 명령73곳을 같은 ELF의 Capstone 결과와 AOT 명령에 대조한 기록이다. Dart register alias를 정규화했고 모두 일치했다. 전체 의미/실제 앱 검증으로 세거나 과거 표본과 독립 합산하지 않는다. 문서/집계만 추가해 기존 unit/probe·영상·폰 시험을 반복하지 않았다.

두 helper의 정상 정적 경로와 해시의 포함 필드·자체 cache 부재를 미수행 목록에서 뺀다. 실제 시간축 caller와 복사 내부, 실패·수명·UI/픽셀 전체 검증은 별도다. 이 보고서가 모든 독립 분석의 종료를 뜻하지 않는다.
