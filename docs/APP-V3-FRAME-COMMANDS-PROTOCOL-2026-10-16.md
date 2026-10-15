# APP-V3 시간축 프레임 명령 — 정적 예측과 내보내기 검사 — 2026-10-16

기준 main은 `afc4be303b3e7b0099fc0f8d7cc62bd469adb50e`다. 이 문서는 2026-10-16 정적 결과 중 **앱 SFA 내보내기로 관측할 수 있는 것**과 관측할 수 없는 것을 나누고, 관측 가능한 항목을 판정하는 시드·검사 도구·절차를 추가한다. **새 실제 앱 시험 결과는 아직 없다.** 검사 도구의 단위시험은 정적 해석을 옮긴 모의 붙여넣기에 대한 것이며 앱 검증이 아니다.

## 이번 환경의 차단

이 Claude Code 클라우드 환경에는 과거 `/workspace/scratch/.../private-recovery` 경로가 없고, 사용자가 올린 Drive 백업(`drive.google.com`, `drive.usercontent.google.com`, `docs.google.com`)은 환경 네트워크 정책에서 403으로 거부됐다. 원본 APK도 이 환경에 없어 AOT 재추출로 대신할 수 없다. 따라서 이번에는 **새 AOT 함수 분석을 수행하지 않았다.** 일반 AO 앞뒤 순서·별도 잠금 UI 같은 미식별 callback 탐색은 캐시 복구 후 다음 작업으로 남긴다.

## 정적 결과의 관측 가능성 대조

| 정적 결과(근거 보고서) | SFA 내보내기로 관측 | 기존 실물 표본 | 이번 판정 방법 |
|---|---|---|---|
| 앞/뒤 빈 frame 삽입, 앞/뒤 붙여넣기, 복사, 삭제의 callback 연결(TIMELINE-FRAME-COMMANDS) | 가능: frame 수·Position·내용 | 없음. 00–05는 시간축 명령을 사용하지 않음 | 아래 절차 1–5 |
| 같은 sequence·유일 AO ID면 AO ID 유지, 점은 새 ID, outgoing 연결은 새 점 map으로 재작성 | 가능: 한 파일 안의 원본/복사 frame 비교 | 00 왕복에서 AO ID가 frame 공통, AP ID는 frame별 고유라는 저장 형식만 확인. 복사 경로 자체는 아님 | `ao_ids_kept`, `point_ids_new`, `connections_remapped` |
| 그룹 Flags를 최종 부모로 해석해 `(새부모ID<<6)\|(Flags&0x2f)\|0x10`, 해석 실패 시 `Flags&0x2f`(GROUP-REPAIR) | 가능: Flags 상위값이 같은 파일의 AP ID를 가리킴 | 04 grouped의 93598163=(1462471<<6)\|16\|3, 1462471은 위선 기준점 ID([APK-GROUP-LINK](APK-GROUP-LINK-TRACE-2026-10-15.md)). 내보내기 Flags가 AP ID를 쓴다는 전제의 실물 근거 | `flags_remapped_to_root_parent`. 시드에 자식→자식→부모 사슬 포함 |
| fill segment의 ObjId/점 ID 재작성, 대응 없는 점은 −1, t/contour 유지, ring 형식 | 가능 | 01/00은 가져오기·왕복 형식만 확인 | `fill_regions_remapped`, ring은 관측값 기록(`ring_segment_form`) |
| 붙여넣기 frame에 clipboard 배경색 저장 | 가능: Frame.BackgroundColor | 없음 | 시드 두 frame의 배경을 다르게 함. `background_kept` |
| 빈 frame은 AO 없이 현재 frame의 layer 구조 복제 | 부분: LayerDef는 원래 sequence 전체에 공통이라 약한 판정 | 사용자 확인: 레이어 조작은 전체 frame 적용 | `empty_frame@…_layers_from_neighbour`. 배경은 예측 없이 기록 |
| 모든 frame 삭제 시 position0 새 frame 생성 | 가능 | 없음 | 절차 5. UI가 마지막 삭제를 막으면 그 자체를 기록 |
| 다른 sequence 붙여넣기의 새 AO ID | 파일 간 ID 비교가 무의미해 ID 정책은 관측 불가 | 없음 | 선택 절차 6: 내용 보존만 육안·도구 요약으로 비교 |
| root prefix 재사용·sqlite_sequence/가상 base 예약(ROOT-COPY-DB-BRANCHES), unused AO A∪R 정리(UNUSED-AO-FAST-HASH) | 불가: 내보내기는 frame별 전체 객체를 쓰며 DB 내부 행을 보이지 않음 | 없음 | 정적 결과로만 유지. 앱 데이터 DB 직접 접근은 현재 수단 없음 |
| Frame.GetFastHash 포함 필드 | 간접(undo 기록 여부)만 가능하나 caller별 예측이 없음 | 없음 | 예측 없는 시험은 해석할 수 없어 보류 |

## 추가한 자료

- `build_frame_command_probe.py` → `examples/frame_commands_v3/06_frame_commands_seed.sfa`, `manifest.json`. 2 frame·Layer 2개, 연결된 삼각형+fill, 자식→자식→부모 그룹 사슬(AO20/21/22), glow·굵기1.5 원과 Kind1 ring fill, frame별 다른 배경. 그룹 Flags는 생성기가 쓴 값이며 가져오기에서 복구될 수 있다. **판정은 시드가 아니라 앱 내보내기끼리 비교한다.**
- `tools/check_frame_commands.py BEFORE.sfa AFTER.sfa [--json 보고.json]`: 표준 라이브러리만 사용해 Termux에서도 실행할 수 있다. ID 없는 내용 서명으로 두 내보내기의 frame을 정렬하고, 새 frame을 빈 frame/같은 sequence 붙여넣기로 분류해 위 예측을 판정한다. 원본과 복사본 내용이 같으면 이전 내보내기와 같은 점 ID를 가진 쪽을 원본으로 본다. 내보내기마다 ID가 재배정되면 방향을 `ambiguous_best_of_both`로 표시한다.
- `tests/test_frame_commands.py`: 정상 모의 붙여넣기(앞/뒤)·ID 재배정·빈 frame·마지막 삭제 재생성의 통과와, 점 ID 재사용·Flags 원값 복사·배경 변경의 실패 검출을 시험한다.

## 앱 절차 — 사용자가 시간을 낼 때만

필요한 반환물은 **작은 SFA 6개**뿐이다. 영상·화면녹화·설정 사진은 필요 없다. FPS는 판정 대상이 아니지만 기존 형식대로 (트위닝,재생)=(24,24)를 그대로 둔다.

0. 시드를 새 프로젝트로 가져와 수정 없이 내보내기 → `06_a_import.sfa`
1. 첫 frame 선택 → 현재 frame 복사 → 뒤에 붙여넣기 → `06_b_paste_after.sfa`
2. 세 번째 frame(시드의 두 번째) 선택 → 앞에 붙여넣기(clipboard는 1의 복사본) → `06_c_paste_before.sfa`
3. 첫 frame 선택 → 앞에 빈 frame → `06_d_insert_empty.sfa`
4. 방금 만든 빈 frame 삭제 → `06_e_delete.sfa`
5. frame이 하나 남을 때까지 삭제 후 마지막 하나도 삭제 시도 → `06_f_delete_last.sfa`. 버튼이 비활성이거나 확인창이 거부되면 그 사실만 적는다.
6. (선택) 1의 clipboard를 다른 프로젝트에 붙여넣고 그 프로젝트 내보내기 → `06_g_cross_sequence.sfa`

7. (선택, 축 고정) 아무 프레임의 한 점을 편집 메뉴에서 세로 축 고정을 켠 채 비스듬히 드래그 → `06_h_axis_fix.sfa`. 직전 내보내기와 비교해 그 점의 X 불변·Y 변화를 확인한다(근거 [AXIS-FIX](AOT-AXIS-FIX-DRAWORDER-WRITERS-TRACE-2026-10-16.md)). 검사 도구 자동 판정은 없고 좌표 비교로 기록한다.

판정은 연속 쌍 a→b, b→c, c→d, d→e, e→f에 검사 도구를 실행한다. 기대 사건은 각각 `paste_same_sequence`(pasted_after_source), `paste_same_sequence`(pasted_before_source), `empty_frame`, 제거만 있는 변화, `last_frame_delete_recreated_empty_frame0`이다. a는 시드와 직접 비교하지 않는다.

## 해석 규칙

- pass는 **내보내기에서 보이는 상태가 정적 해석과 모순되지 않음**이다. DB 내부 경로(root 재사용·ID 예약·unused 정리)를 증명하지 않는다.
- fail은 곧바로 정적 해석 오류가 아니다. 가져오기 복구·내보내기 재배정·조작 실수를 먼저 구분한다. 특히 `source_ao_ids_unique`가 info이면 빠른 경로 전제가 깨진 것이다.
- 정적 보고서의 ‘앞/뒤’는 시간축 위치이며 AO DrawOrder 조작이 아니다. 일반 AO 앞뒤 순서 UI는 여전히 미식별이다.
- 결과는 이 문서의 새 절에 기록하고 기존 00–05 결론이나 PREVIDEO/File-2 보호 자료를 바꾸지 않는다. 반환 SFA·영상 원본은 공개하지 않고 집계만 반영한다.

## 남은 일

1. 분석 캐시 복구(환경 Network access에 Drive 도메인 허용, 또는 접근 가능한 다른 전달 경로) 후 미식별 UI callback(일반 AO 앞뒤 순서, 별도 잠금 전환) 정적 추적.
2. 위 절차의 실제 앱 결과 수집·판정.
3. 모든 기능을 쓰는 제작·저장·내보내기 검증은 이 모듈을 첫 단위로 삼아 이어 설계한다. 실제 렌더/backend pixel·곡선/링/그룹 합성은 계속 미완이다.

검증: `python -m unittest discover -s tests -v` 28개 통과(이번 신규 6개 포함). 생성 시드는 `sfa.validate` 오류 없음, 그룹 Flags는 2³¹ 미만. 기존 probe 파일은 재생성하지 않았다.

## 실제 앱 결과 — 2026-10-16 사용자 반환 SFA 6개

반환 파일은 `seed_no_edit`(a), `1Paste`(b), `2Paste`(c), `new_frame`(d), `new_frame_del`(e), `all_del`(f)이다. 원본은 공개하지 않는다. 연속 쌍 a→b…e→f에 검사 도구를 실행했고 **5쌍 모두 실패 0건**이다. 아래는 내보내기 상태 관측이며 DB 내부 경로를 증명하지 않는다.

| 단계 | 관측 | 정적 예측과의 관계 |
|---|---|---|
| a 가져오기 | 프레임 ID 2290/2291, AO ID 51504–51510 재배정, DrawOrder=새 AO ID. 시드의 자식→자식→부모 사슬에서 손자 점(AO22)의 Flags 상위값이 원래 자식 점이 아니라 **최상위 부모 점(AO20 Index0, 1462529)**을 가리킴(93601875=(1462529<<6)\|0x13) | 가져오기 단계의 그룹 복구가 부모를 최종 부모로 평탄화함. 붙여넣기 이전에 이미 평탄화되어, 붙여넣기의 평탄화 자체는 이 표본으로 따로 관측되지 않음 |
| b 첫 프레임 복사→붙여넣기 | 새 프레임 2294가 위치1(원본 바로 뒤). AO ID 7개 유지, 점 ID 14개 전부 새 값, 연결·그룹 Flags·채우기 참조 재작성, 레이어·배경 유지 | 같은 sequence 빠른 복사 경로 예측과 일치(검사 15항목 통과) |
| c 세 번째 프레임에서 붙여넣기 | 새 프레임 2297이 위치2, 선택했던 2293은 위치3으로 밀림. 내용은 첫 프레임 복사본과 같음 | 현재 위치에 넣는 ‘앞에 붙여넣기’(index 그대로) 분기와 부합 |
| d 새 프레임 | 빈 프레임 2298이 위치1. AO 0, 레이어 2개(이웃과 동일), 배경 4279769112(시퀀스 배경과 같음) | 빈 frame+현재 frame 레이어 구조 복제 예측과 일치. 어느 프레임을 선택한 상태였는지는 미기록이라 앞/뒤 분기는 미확정 |
| e 빈 프레임 삭제 | 2298만 제거, 나머지 프레임 ID·점 ID 그대로 | 단일 frame 삭제와 일치 |
| f 모두 삭제 | 하단 휴지통으로 하나씩 삭제(사용자 확인). 남은 프레임 ID 2297, AO 0, **레이어 1개** | `_deleteCurrentFrame`의 마지막 삭제→`CreateNewFrame`(기본 Layer1만) 예측과 내용이 일치. 원래 2297은 AO7·레이어2였으므로 같은 행이 남은 것이 아니라 새 frame으로 해석. ID 재사용은 **추정**: 앱에는 AUTOINCREMENT가 없는 기존 DB를 다루는 분기가 있고([ROOT-COPY-DB-BRANCHES](AOT-ROOT-COPY-DB-BRANCHES-TRACE-2026-10-16.md)), 그런 frame 테이블이면 rowid=남은 최대+1로 재사용된다. 기기 DB 스키마는 직접 보지 않았다 |

추가 관측:

- a→b 사이에 원래 두 프레임의 ID가 2290/2291에서 2292/2293으로 바뀐 것은 사용자가 1Paste부터 시드를 새로 가져왔기 때문이다(사용자 확인).
- b→c 사이에 2295/2296이 건너뛰어졌다. 다른 동작이 frame ID를 소비했을 수 있다.
- 같은 프로젝트 안의 연속 내보내기에서는 프레임 ID와 점 ID가 유지됐다(c→d→e).
- ring(Kind1) segment는 내보내기에서 끝점·T 속성 없이 기록됐다.

검사기는 이 결과로 보완했다. 내용이 같은 프레임이 여럿일 때 처음 보는 프레임 ID, 없으면 가장 큰 프레임 ID를 새 프레임으로 본다(frame 테이블이 AUTOINCREMENT라서). 이 보완 전에는 방향을 ‘모호’로 표시했다.

### 하단 버튼과 정적 callback 대응 — 사용자 화면 확인

사용자가 제공한 시퀀스 화면에서 하단 버튼은 왼쪽부터 `← 붙여넣기`, `◂ 새 프레임`, `수정`, `복사`, `▸ 새 프레임`, `→ 붙여넣기` 순서이고, 프레임 삭제는 휴지통 아이콘이다. 사용자 설명대로 새 프레임은 현재 프레임 기준 앞/뒤에 같은 배경색의 프레임을 추가한다. 이는 `_pasteFrame(true/false)`·`_insertEmptyFrame(true/false)`·`_copyCurrentFrame`·`_requestDeleteCurrentFrame` 연결과 대응한다(화살표 방향↔true/false 대응은 c의 앞 붙여넣기 결과로 ←=현재 위치 삽입을 확인. ◂/▸는 d에서 어느 쪽을 눌렀는지 미기록). 절차 문서의 ‘앞에 빈 frame’은 `◂ 새 프레임`을 뜻한다.
