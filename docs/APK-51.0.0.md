# Stick Fighter 51.0.0 APK 분석 1차

## 입력과 추출 확인

- 사용자 제공 APKS, 패키지 com.sG.stickfighter.activities, versionName 51.0.0, versionCode 51000.
- APKS SHA-256: c1c39e031f0fc4a904755f08c45406e4fd3c894dafe1e506c0c0ac7dd78eff76.
- base.apk와 arm64_v8a, ja, ko, xxhdpi 분할 APK 4개가 포함됨.
- base.apk에 classes.dex/classes2.dex/classes3.dex가 있고 ARM64 분할에는 libapp.so/libflutter.so 등이 존재.
- Skit 추출물로 정적 분석을 시작하는 데 필요한 본체·대상 기기용 네이티브 코드가 확보됨. App Manager/Shizuku로 재추출할 필요 없음. 설치되지 않은 다른 기기용 분할까지 포함됐다는 의미는 아님.

## 확인한 내용

1. Flutter AOT 코드와 Android 코드가 함께 존재한다. Android 쪽은 JADX로 일부 읽을 수 있으나 Flutter 핵심 로직 전체가 Java로 복원되는 것은 아니다. JADX 전체 실행은 일부 오류를 보고했으므로 모든 메서드가 복원됐다고 주장하지 않는다.
2. Android 데이터베이스 접근 코드 X2/a에서 sequence 테이블의 fps/thickness, animation_object_detail의 thickness_scale/object_scale을 읽는 쿼리가 확인된다. sequence.fps에 DEFAULT 12를 추가하는 마이그레이션 코드도 존재한다. 이것이 현재 가져오기 경로가 무조건 12를 적용한다는 증거는 아니다.
3. Android 설정 브리지 W2/e에서 smoothness_ 접두사의 숫자 설정을 SharedPreferences로 읽고 쓰는 코드가 확인된다. Flutter 바이너리에는 last_project_fps / last_project_smoothness / last_project_thickness 문자열과 데이터베이스 쿼리가 존재한다. 가져오기 직후 (60,12)가 된 정확한 초기화 경로는 아직 미확인이다.
4. 영상 내보내기 브리지에는 exportFps / tweeningFps를 별도 인자로 받는 경로가 있다. 이름만으로 두 값의 UI 대응이나 정확한 보간식을 확정하지 않는다.
5. Android 렌더러 Y2/m의 원은 두 점을 지름 양 끝으로 사용한다. 선 굵기 보정과 도형별 렌더링 처리가 존재한다. Flutter 렌더러와 완전히 일치하는지는 별도 확인 필요.
6. 사용자 제공 시험 영상 1000326576.mp4는 1920x1080, 24FPS, 48프레임, 2초. 팔 흔들기 동작을 확인했다. 사용자는 가져오기 당시 UI는 (60,12)였다고 설명했으며, 영상 출력 설정과 가져오기 초기값을 구분해야 한다.

## 다음 확인 대상

동일 입력을 다시 확인한 후속 SQL/문자열 근거와 바이트 위치는 [APK-EVIDENCE-51.0.0.md](APK-EVIDENCE-51.0.0.md)에 기록했다. 실제 앱 결과는 [APP-VERIFICATION.md](APP-VERIFICATION.md)에서 별도로 관리한다.

- 현재 Flutter 가져오기 경로의 FPS/기본 굵기 초기값.
- 트위닝 도형 대응과 TweenLink의 정확한 의미, 생성/삭제 시 보간 처리.
- 전체 굵기와 요소별 굵기/스케일의 결합, Flutter 실제 렌더링과 비교.

APK 원본, 네이티브 바이너리, 역컴파일된 앱 코드는 저장소에 게시하지 않고 분석 결과만 기록한다.
