# AI-sfa 현재 인수인계 — 2026-10-15

## 목표·상시 지침

- 한국어 소통. Stick Fighter51.0.0의 **모든 창작·편집 기능 분석과 실제 앱 검증**이 목표다. 최소SFA생성/렌더근사로목표축소금지. 사쿠가수집/학습/AI연결은보류.
- 직접작성보고서·집계·작업지침은main반영상시승인. 쓰기전최신head/tree/expected_sha확인,다른변경보존. 시스템자동승인거부우회금지.
- 공개금지: APK/SFA/영상/역컴파일소스/assembly/키/전체런타임로그. 레포에원본또는역컴파일코드첨부금지.
- FPS=(트위닝,재생). 레이어UI는전체프레임제작보조. 굽힘기능없음. 편집공간/출력사각형구분,음수·화면밖좌표임의삭제/중앙이동금지.
- 기존00–05시험/자료분석완료. 재출력·추가작품·제작자문의금지. 기존추출·도구설치·시험은새변경/실패관련필요없으면반복금지.
- 정확도유지하며캐시/읽은내용재사용·좁은출력·실제명령검증. AGENTS.md준수. 사용자잔여주간사용량직접조회불가. 인수인계필요시체크포인트저장후docs/HANDOFF-PROMPT.md제공.

## 현행 체크포인트 — 렌더 좌표/DPR·여백 확인, Paint B 미해결

먼저 AGENTS.md와 **docs/AOT-RENDER-CONTEXT-TRACE-2026-10-15.md**를 읽는다. 다른보고서는해당문제에필요할때만.

- X=OffsetX+UsableWidth×x/100,Y동일. original/interpolated변환동일,좌표clamp/DPR직접나눗셈없음.
- DrawInformation은캔버스치수·strokeoverflowpadding·height/width비율로중앙fit. ratio0은9/16기본. 외부Canvas줌/이동/clip과구분.
- DPR=staticoverride→implicitView DPR→1. _withExportRenderDevicePixelRatio는동기callback동안override1,정상/예외시복원. _recordExportPicture의Picture/Draw범위및Optimized의DrawInformation범위확인. 전체async/backend/사용자영상DPR1확정금지.
- paddinghelper기본baseStrokeWidth8≠모든실제Paint B. curve안정화round(1.14×w×D)/D,여백circle배율1.24. 실제Paint.strokeWidth의B는SetPaintThickness/glow입력. 초기OBJECT/PREVIEW_PAINT슬롯0→비영값공급경로는아직닫지못함. 8로메우거나실제항상0이라고확정금지.
- glow shader→rasterplan/cache→MaskFilter호출순서확인. live선택조건/전체cachehit/영상backend미확인.
- 새14명령ELF/Capstone표본통과. 이전Path/FR/생성/unit시험반복없음. 정적추적성공=전체함수의미/실물픽셀성공아님.
- **정확한 다음:** 실제Paint B의plan/caller/primitive 변경·복원과출력dispatch먼저연결. Frame.DrawBaseObject/보간객체_restorePaint·Frame/Picture/native경계필요부분만. 이후shaderload lifecycle/rasterhit/hole캐시키·무효화. 전체파일덤프금지.
- 일시exec-server끊김후재연결/캐시/새검증성공. 사용자ADB실패/캐시손실판정금지.

## 필요한 이전 정적 사실·근거

| 주제 | 현행 근거·제한 |
|---|---|
| 채우기 보간 | AOT-FILL-TWEEN-TRACE-2026-10-15.md: rawsignature→유일canonical후보대응. paired색보간,앞held t<1유지/뒤held t1만. 경계보간실패시t.5기준앞/뒤segments+보간색. '모든FR앞색유지'금지. field_33=contourIndex. |
| 구멍·경계 | AOT-FILL-PATH-TRACE-2026-10-15.md: outer0실패전체null/hole실패생략. 개별contour evenOdd후holes순차difference. 거리>0.1Path좌표연결lineTo/close. 선Tclamp없음/곡선clamp분할/arc기준각+2πT. |
| 공급·그룹·glow | AOT-DRAW-GLOW-TRACE-2026-10-15.md: getter DB자동조회없음/null빈목록만DB공급. DB정렬COALESCE(draw_order,id),id. 비연속그룹A(g),B(h),C(g)→A,C,B. shader11=d1/sigma로정정,10=W/2,12일반0/링1. blend입력Paint상속/초기srcOver. |
| import/링크 | AOT-PATH-TRACE-2026-10-15.md: importer DrawOrder/ObjectScale미조회→생성ID순서/default1. 수동링크TypeId/Index/충돌검사. 모든import/general링크정책확정금지. |
| UI실측 | UI-04-05-RESULTS-2026-10-15.md: '굽힘없음',그룹Flags상위ID참조/AC,원대원TweenLink출력복구. 전체기능완료아님. |
| 00–03영상 | PRIORITY-V2-RESULTS-2026-10-14.md,ROUNDTRIP-V2-RESULT-2026-10-14.md. 기존측정/왕복변화재분석금지. |

## Android 실물 상태 — 추가 사용자 작업 없음

- 사용자PC/추가기기없음·루팅X·Wi-Fi,Android16/SDK36/ARM64. Termux/android-tools/pkgupgrade/무선ADB/저장공간접근완료. 설치·페어링/getprop다시요청금지;실제연결실패시에만복구.
- 원본 com.sG.stickfighter.activities51.0.0/versionCode51000,min24/target36,user0 base+arm64+ja+ko+xxhdpi,DEBUGGABLE없음. user150권한오류는user0사용.
- 별도 com.twoapple08.sfa.instrument/SFA Instrument Test5APK 제작/동일키v1/v2/v3서명·정렬·원본보호항목242대조통과,비공개전달완료. 기존libapp/libflutter보존. gadget script/qjs시작·모듈로그만,서버/Java bridge/렌더Hook없음.
- 실물동일PID12555에서Gadget early/arm64/libflutter/libapp로드성공. LicenseClient기존패키지조회NameNotFound→Play연결/요청성공→응답4예외→오류창,Close시앱종료.라이선스코드4정확한서버뜻미확인(명시invalid package코드는3).원본삭제/Play비활성단정금지.
- 실제지속편집/렌더검증없음.검사변경/우회미실시.추가사용자명령/재설치/Play설정/시작시험요청없음.자세한근거ANDROID-INSTRUMENTATION-BUILD-2026-10-15.md.
- SFA앱밖백업은설치스크립트질문으로안내했으나사용자BACKUP응답원문은없음.완료확정을만들지않는다.

## 보호 상태·검증

- PREVIDEO-PREDICTIONS-2026-10-14.md/PREVIDEO-FRAME-AUDIT.json은3278146고정예측. 정답맞춰수정금지. 비교/정정은별도VIDEO-PREDICTION-COMPARISON.
- File-2최초예측100%조건불충족으로최적화/재압축/삭제/병합/원본수정금지. 영상경계정정/실측은각보고서참조.
- 보고서집계/명령표본은렌더러/완성AI/학습결과아님. 기본HTML preview는근사. sfa.read_sfa32MiB한계임의해제금지.
- 코드변경시필요검사:repo루트 python -m unittest discover -s tests -v. 문서만변경하면기존시험반복안함.

## 캐시·재개

- AOT/ELF: /workspace/scratch/e23c9fd610d3/private/{blutter_out,input/arm64-v8a/libapp.so,venv,depsroot}. asm/sfa,pp.txt,ida_script/addNames.py재사용. Blutter성공은원래Dart소스복원아님.
- 원본base /workspace/scratch/6d77389e706a/evidence/apk/base.apk,분할모음같은evidence/STICK FIGHTER (51.0.0).apks. 기존Java캐시6d77389e706a/private/decompiled.
- 계측도구/빌드 /workspace/scratch/37921248d0d6/private/{instrument-tools,instrument-build}. 전용키sfa-test.jks재사용. 공식tools Apktool3.0.3/signer1.3.0/Gadget17.23.3 ARM64확보됨. 빈도구폴더/다운로드미완은옛상태.
- 비공개ZIP /workspace/scratch/25b8ca176661/output/SFA-Instrument-Startup-2026-10-15.zip,libfile_a9e9671bcd3c8191b95a54915af9aa6d. 원본기반APK공개금지.
- 문서worktree25b8ca176661/AI-sfa;새검사기/집계private-trace/. 이전37921248d0d6/e23c9fd610d3의로컬변경보존.remote반영뒤localHEAD뒤처질수있음;캐시문서덮어쓰기/reset/중복커밋금지.
- reFlutter해당dumpengine404/자체engine빌드미실시이력은FLUTTER-TOOLS-RESULTS-2026-10-15.md.재시도요청없음.
- 압축전인수인계전체보존:docs/history/HANDOFF-2026-10-15-before-render-context.md.현재내용이우선이며역사기록의낡은'다음'을재실행하지않는다.
