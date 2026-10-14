# AI-sfa 현재 인수인계 — 2026-10-14

## 목표·사용자 지침

- 한국어 소통. 사용자는 PC 없는 루팅 안 된 Android/Termux 환경. GitHub 반영 허용, 앱 제작자의 역공학 허가를 받았다고 설명했다.
- 먼저 Stick Fighter51.0.0의 모든 창작/편집 기능을 분석·명세·실제 앱 검증한다. 최소 SFA 생성으로 목표를 축소하지 않는다.
- 현재 우선순위: ① 채우기·구멍·겹침 순서 ② 글로우 강도·범위·합성 ③ 생성·삭제와 프레임 사이 보간.
- 사쿠가 수집·학습·AI 연결·Android 패키징은 보류. 현재 학습된 AI/완성 렌더 엔진/APK가 없다. 나무위키 금지.
- FPS 순서는 **(트위닝 FPS, 재생 FPS)**. 레이어 조작은 전체 프레임에 적용되는 제작 보조 기능. DB frame_id로 UI 범위를 추론하지 않는다.
- 편집 작업 공간과 흰 출력 사각형을 구분한다. 좌표를0–100으로 강제 제한/중앙 이동하지 않는다. 화면 밖 도형도 진입·채우기·글로우 참조 때문에 임의 삭제하지 않는다.
- APK/SFA/영상/역컴파일 소스/추출 프레임을 공개 저장소에 올리지 않는다. 보고서·집계·직접 작성한 도구만 반영한다.
- 사용자 추가 요청: 정확도를 유지하며 토큰 낭비를 적극 줄이고, 효율상 필요하면 자율적으로 인수인계와 새 대화 프롬프트를 갱신한다. 실행 지침은 AGENTS.md.

## 최신 체크포인트 — 사용자 실행용 v2 시험 준비

- 사용자가 네 가지 협력 작업(실제 편집 조작/통제 실험/저장 왕복/제작자 문의)을 모두 진행하자고 명시했다. 이전의 “현재 추가 실험 요청 없음”은 이 새 승인으로 대체한다. 전체 기능 무작정 샘플 요청은 여전히 하지 않는다.
- build_priority_probes.py와 examples/priority_probes_v2/:00왕복,01채우기/구멍/순서8초,02글로우12초,03무보간7초/보간14초,04한프레임UI기초,05수동링크2초. 파일6개와안내를AI-sfa-priority-tests-v2.zip으로제공한다.
- 사용자 세부 안내: docs/PRIORITY-PROBE-USER-GUIDE.md. 제작자에게 사용자가 직접 보낼 문안: docs/DEVELOPER-REQUEST-KO.txt. 자동발송 없음. 실제 메뉴 위치/아이콘은 미확인이므로 없는 메뉴를 추정하지 않는다.
- 먼저00의가져온직후재저장/설정후재저장/MP4/설정기록. 가져오기오류면다음통제시험을중단하고결과를받는다. 정상이라면01/02/03의재저장SFA와MP4를순서대로받는다.03은(T,P)=(24,24)와(24,12)두출력.
- UI는04원본에서각각독립적으로늘리기/원근/굽힘/그룹·해제의전후SFA+녹화.05는원본12/13사이수동TweenLink메뉴가확인될때만.일반AC/그룹과혼동금지.
- 22자동검사통과:참조/전체점ID/동일AO의DrawOrder일관성/글로우한변수분리/보간대조.앱실행은미검증이며사용자결과대기. 생성파일의Count/길이는기대값이다.
- 원본/File-2최적화/고정예측/렌더러는변경하지않았다.받은SFA왕복차이를먼저읽고생성속성이실제입력에유지됐는지확인한뒤영상규칙을판정한다.

## 이전 분석 결과 — 기준 ba1f632

- docs/FILL-GLOW-TWEEN-ANALYSIS-2026-10-14.md: 최신 APK/SFA/영상 대조. docs/BOUNDARY-AUDIT-2026-10-14.json: 좌표/ID 없는5경계 집계.
- File-2 84/85 공통1,752AO는 기본 선/글로우 알파 모두0. 앞에서 공통AO만 참조하는2,163FR은 모두 배경색. 뒤에는 배경색2,163+흰FR1. 38/39 공통1,734AO도 기본 선 알파0이며 남는6글로우 곡선 자체는 출력 아래. 공통AO 수로 밝은 형상 유지를 판단하지 않는다.
- **관찰 정정:** 원본39 위치(출력77)는 인물 잔존이 아니라 암부. 출력75는 인물/격자,76/77은800×450에서RGB16 단색. 기존 감사 JSON과 충돌한 비교 서술을 정정했다. 최초 고정 예측은 보존했다.
- 네이티브Y2.i.d/k: 공통AO 후보 → 모든 경계가 후보AO인FR 필터 → 경계signature/topology 대응. 미대응 앞FR 유지 분기, 부분T/색 보간 관찰. 전체 Flutter 규칙으로 확대하지 않는다.
- 네이티브Kind1 전체 원/이차곡선 부분T분할/EVEN_ODD/레이어별FR→글로우→선 패스 관찰. **X2.a.m/Y2.j가contour_index를 로드/보유하지 않으므로 Flutter 구멍 처리를 대신할 수 없다.** 큰 렌더 함수는 역컴파일 경고도 있다.
- 실물glow.frag shader bundle에 Gaussian계열ring/stroke coverage가 있다. uniform단위/사전알파/blend mode/경로선택은 미확인. 네이티브 원본/중간 굵기식도 다르다. 제공영상에 어느 경로가 실행됐는지는 미확인.
- tools/audit_sfa_boundaries.py는 읽기전용 XML 집계 도구. 렌더러가 아니다. 기존18검사 통과,5경계 집계는 별도 계산과 일치. 이 성공을 앱 전체 기능 완료로 세지 않는다.

## 반드시 보존할 검증 상태

- 두 famous user 작품: File-1 원본120 → 24FPS/240출력/10초, File-2 원본114 → 24FPS/228출력/9.5초. 사용자 설정(24,12). 최초 예측은 색채 고리·얼굴 세부·글로우·겹침·중간 암전을 놓쳐100%정확하지 않았다.
- docs/PREVIDEO-PREDICTIONS-2026-10-14.md 및 PREVIDEO-FRAME-AUDIT.json은3278146의 고정 예측. 정답에 맞춰 변경하지 않는다. 비교/정정은VIDEO-PREDICTION-COMPARISON-2026-10-14.md에 별도로 기록한다.
- **File-2 최적화는 최초 예측100%정확이라는 사용자 조건을 충족하지 못했다.** 재압축/삭제/병합/원본수정 금지 상태 유지.
- v1은16구간/768원본. (24,24) 반환 영상은24FPS/768출력/32초.14구간 표본 일치,13 레이어 프레임별 기대 철회,14 DrawOrder 전환 기대 불일치. 전체 픽셀 일치/실제 편집 버튼 재현이 아니다.
- DrawOrder는frame_id 없는animation_object 공통속성. 동일AO의 프레임별 상충값 처리와 importer는 미확인. APP-V1-ROUNDTRIP 재저장 요청은 현재 우선순위 뒤로 보류한다.
- 10_screen:5원본 모두 검정 스틱맨이 음수Y로 출력 위쪽 밖에 있고 글로우0. 실제 출력은흰색. 회색 편집 공간/플레이어 검정 여백과 구분. 이 사례의(T,P)는 별도 명시되지 않았다.

## 다음 작업과 중단점

1. Flutter Contour 경로 생성·채우기 planner/유효성·그리기 순서를 추적한다.
2. shader uniform 배율·알파·blend mode·연결 객체 합성·fallback 선택을 추적한다.
3. Flutter TweenLink/생성·삭제·점index/FR 대응을 네이티브 관찰 및 영상 경계와 대조한다.
4. 사용자 승인한 v2 시험 결과를 받아 importer 왕복→실제출력→실제버튼연산 순서로 분석한다. 추가 작품/전체기능일괄샘플은요청하지않는다.
5. 이후 실제 늘리기/원근/굽힘/그룹/연결/기준점/잠금 등 편집 연산 및 importer 초기 설정을 확인한다.

미확인과 막힌 이유의 목록은 docs/OPEN-QUESTIONS.md. 위 순서가 현재 작업이며 이전 기록 속 “다음 요청”은 현행 지침이 아니다.

## 읽기 경로 — 현재 대화에서 읽은 것은 반복하지 말 것

- 새 대화: 이 문서와AGENTS.md → 최신 추가 분석 문서. 기능 전체 범위가 필요하면FEATURE-COVERAGE.md.
- 채우기/글로우/보간: FILL-GLOW-TWEEN-ANALYSIS-2026-10-14.md, 필요한 경우NATIVE-TWEEN-FINDINGS.md/APK-EVIDENCE-51.0.0.md.
- 영상 사실: VIDEO-PREDICTION-COMPARISON-2026-10-14.md 및 필요한 프레임의VIDEO-FRAME-AUDIT.json. JSON 전체를 대화에 출력하지 않는다.
- 출력 범위: EDITOR-OUTPUT-BOUNDS.md. v1: FEATURE-PROBE-GUIDE.md/APP-VERIFICATION.md.
- 과거 전체 기록: docs/history/HANDOFF-2026-10-14-before-compaction.md. 충돌 확인/역사 추적 때만 읽는다.

## 환경·도구·파일 복구

- 저장소 표준 라이브러리 Python: sfa.py, native_timing.py, build_feature_probes.py, tests/. HTML preview는 채우기/글로우/앱보간을 재현하지 않는 근사다.
- tools/audit_sfa_boundaries.py는 스트리밍 집계. File-2 XML372,172,417바이트/최대15,552AO. sfa.read_sfa의32MiB 한계를 임의 해제하지 않는다.
- 기존 소규모 samples:01_base~09_tween, anonymous user File-1/2(122/90원본,(60,12)), wave/probes. 필요할 때 해당 자료만 복구한다.
- 이번 대화 환경: /workspace/scratch/6d77389e706a/AI-sfa. 원본은 형제evidence/, jadx1.5.6·역컴파일·libapp·shader는형제private/. 존재 여부는 다음 환경에서 보장되지 않는다. 필요 경로만 확인하고 없으면 원본 이름으로Library에서 복구한다.
- 주요 원본 이름: STICK FIGHTER (51.0.0).apks, Anonymous famous user file-1.sfa/file-2.sfa,1000326603.mp4/1000326604.mp4,10_screen.sfa. 체크섬은 근거 문서 참조.
- APK는Flutter AOT+Android 혼합. JADX의Java출력을Flutter전체소스로 해석하지 않는다. 이번전체JADX는62오류. 앱실행/adb는이번분석에서사용하지못했다.
- GitHub connector 쓰기 성공. 터미널push 인증 실패 이력을 연결 재설정 필요로 확대하지 않는다. 쓰기 전최신head/tree확인,expected_sha보호. 다른대화의변경을보존한다.
- 이전 변경이원격반영돼도로컬HEAD가뒤처질수있다. 먼저실제바이트/원격SHA를비교해중복커밋을피한다. 무조건reset/덮어쓰기금지.

## 검증 명령

저장소 루트에서 필요한 검사만 실행한다. 분석문서만 바뀌면 이미통과한검사를반복하지않는다.

```bash
python -m unittest discover -s tests -v
python tools/audit_sfa_boundaries.py '<File-2 경로>' --pairs 38:39 72:73 84:85 94:95 103:104
```

새대화프롬프트: docs/HANDOFF-PROMPT.md. 인수인계 시 완료/미확인/다음행동/금지사항을 갱신한다.
