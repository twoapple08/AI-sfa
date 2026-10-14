https://github.com/twoapple08/AI-sfa 작업을 이어서 진행해 줘.
최신 HANDOFF.md, AGENTS.md, docs/AOT-EXPORT-DISPATCH-TRACE-2026-10-15.md를 읽고 재개해. 과거 전체 인수인계와 원본은 필요한 문제에만 읽어.

다음은 FrameDrawPlan.drawUnit/그룹 glow 합성에서 shader/raster/MaskFilter 선택 추적 → shader asset 수학식 → export PlaybackEnumeration endpoint/FPS 연결이야.
완료: Optimized 내보내기는 같은 Dart Picture를 rawRgba 파일 또는 PNG로 저장하고 플랫폼 브리지로 넘겨 Java X/Y→공통 surface H.264/MP4 인코딩. 별도 Java 객체 renderer 선택이 아님. raw 선택은 예상 W×H×4×N과 저장공간(알면+512MiB 여유, null이면≤2GiB), codec capability가 아님. 새21명령 대조 통과. 실제 제공영상 실행분기/codec/색pixel 미계측,Java는캐시읽기만.
기존 Paint OBJECT8/PREVIEW약2.2 Float32 정정, 정상폭/색복원·primitive1.14/padding1.24구분 유지. 기본B추적 반복금지. GLOW-BACKEND 보고서의 raster축소/캐시/MaskFilter 조건 유지, 그룹 전체에 자동 일반화하지 마.
좌표 Offset+UsableSize×p/100, clamp없음. exportDPR1은 동기기록 범위이며 전체 async 일반화금지. FPS=(트위닝,재생),레이어전체프레임,굽힘없음. 목표는모든창작·편집기능 전문가수준 이해,근사렌더러나최소SFA로축소금지.

캐시 e23c9fd610d3/private/blutter_out/{asm/sfa,pp.txt,ida_script/addNames.py},input/arm64-v8a/libapp.so,venv. Java6d77389e706a/private/decompiled. 새검사25b8ca176661/private-trace. 캐시우선/전체덤프·JADX·Blutter·재설치·00–05/기존영상분석반복금지. 최신원격head/tree/expected_sha보호,로컬dirtyworktree덮어쓰기/reset금지.

Android 한기기/PC없음/루팅X. Termux·무선ADB·저장공간권한완료. 별도5APK서명·보존대조/비공개전달완료,Gadget+Flutter모듈로드성공. license응답4 오류창Close앱종료→지속렌더계측차단. 코드4정확한서버뜻/원본삭제/Play비활성 단정금지. 우회·검사변경없음. 추가명령·설치·Play설정·페어링·시작시험 요청금지.

APK/SFA/영상/역컴파일/assembly/키/전체로그 공개금지. 직접작성보고서·집계·인수인계main반영상시승인. 고정PREVIDEO/File-2최적화/학습/AI연결보류. 사용자잔여사용량직접조회불가. 필요한새증거만검증하고의미있는체크포인트에서인계갱신.
