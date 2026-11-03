# SFA 뷰어 모바일 v1.1 — 2026-11-03

## 배포

사용자가 Drive07도구의 SFA 뷰어를 v1.1로 수정·업로드하라고 요청했고 모바일 버전만으로 범위를 지정했다.

- APK: https://drive.google.com/file/d/1wfJrOYh08UG9w1qdnR65lGFT_8R5tPHS/view
- 설치 안내: https://drive.google.com/file/d/1e7kuF_lux32359xBtLIVOz1IBb01-4Gn/view
- 업로드 위치: AI-sfa/07_도구/SFA뷰어,폴더ID `1sAy18-sCtzrunjICScOehKZSUlevnmqB`.
- 머리 채움 수정 SFA: https://drive.google.com/file/d/1o3cTOMY9X9keVJczwIJqBuYbXZU5Erb_/view
- 실제 앱/모바일 그래픽 비교 시트: https://drive.google.com/file/d/10RRubQYjDBHfrgATc_eq4o38zQOTK2_J/view

기존 v1.0 APK와 Windows 파일을 덮어쓰지 않고 새 모바일 APK/안내를 추가했다. Drive 목록 재조회에서 파일명·크기·위치를 확인했다.

## 문제와 수정

사용자 실제 Stick Fighter 녹화에서 머리 안으로 팔·이전 장이 비쳤다. 생성 SFA의 머리 FS가 Kind를 빠뜨렸는데 모바일 v1.0의 파서/렌더러는 Kind와 점 참조를 읽지 않고 원으로 그려 오류를 감췄다. 저장 SFA 수정은 `docs/GPT-STICKMAN-HEAD-FILL-APP-FIX-2026-11-03.md`를 따른다.

모바일 v1.1은 FS Kind를 읽고 원 전체(1)/경계(0)를 구분한다. 객체 타입·최소 점 수·AP 참조의 소유 객체·유한한 T/유효 구간·원 단독 윤곽을 검사한다. 알 수 없는/빠진 Kind,다른 객체의 점,없는 점,구간 폭0,원 전체를 다른 조각과 같은 윤곽에 넣은 경우는 해당 윤곽을 생략한다. 외곽이 부적합하면 채우지 않고 부적합 구멍은 생략한다. 전체 원의 T는0/1로 정규화한다. 음수 점 참조의 자유 T 경로는 유지한다.

파일 정보에 잘못된 채움 경계 수를 표시한다. 문서 캐시를 version3→4로 바꾸고 JPEG 미리보기 폴더도 frames_v11로 구분해 이전의 잘못된 그림을 재사용하지 않는다. 재생·보간·MP4 내보내기가 같은 새 렌더러를 쓰며,보간의 채움 대응 키에도 종류/유효성을 포함했다. 사용자 선택형 보정 모드나 자동 원 채움 복구를 넣지 않았다.

## 검증

- `assembleRelease testReleaseUnitTest` 종료코드0,모바일9개 시험 전부 통과: 새 HeadFillTest5개·기존 Parser2·Render1·UiShot1.
- 새 시험은 정상 원의 가림과 누락 Kind의 비가림,다른 객체/없는 점 참조,폭0/NaN T,잘못된 원 대상/정수 Kind 래핑,혼합 원 윤곽,캐시 왕복/구버전 거부,실제240장 회귀를 확인한다.
- 실제 입력: 근경 면 포함 기존240장파일의 잘못된 경계469개,수정파일0개. 두 파일의 AO ID/점 좌표는 완전 일치했다. 기존 화면 시험 별칭p1은 수정 파일 복사본이며 별도 원본 표본 수로 세지 않는다.
- Android34 네이티브 그래픽(Robolectric)으로 재생127·178장을 그려 기존 파일의 누락 증상을 재현하고 수정 파일의 흰 채움을 확인했다. 세로/가로/분할/팝업 화면 시험도 통과했다. 실제 휴대폰에서 APK 설치/재생/내보내기 및 실제 Stick Fighter의 수정 SFA 편집 확인은 별도 대기다.
- Python 루트 전체240개 시험 통과. APK의 package/versionName/versionCode·서명·ZIP 정렬 검사를 통과했다. 버전은 `com.aisfa.viewer`,1.1/11이다.

초기 그래픽 단위시험2개는 얇은 선의 안티앨리어싱 색을 단색 파랑으로 기대해 실패했다. 가림 유무를 시험하려는 목적에 맞게 입력 선을 충분히 굵게 바꿔 단색 영역을 비교했고 제품 코드를 시험 기대에 맞춰 바꾸지 않았다. 이후 모바일 전체9개를 재실행해 통과했다.

## 설치·서명

이 환경에는 기존 v1.0의 개인 서명키가 없고 새 빌드의 인증서가 기존 APK와 다름을 실제 비교했다. 같은 applicationId를 유지했으므로 덮어설치할 수 없으며 기존 뷰어 삭제 후 설치가 필요하다. 삭제 시 뷰어의 최근 목록·FPS 설정·캐시가 초기화된다. 외부 SFA 원본은 뷰어가 수정하지 않는다.

이번 서명키는 비공개 로컬 `/workspace/ai-sfa-private/android_build/signing/debug.keystore`에만 보존하고 저장소/공유 Drive에 넣지 않았다. 향후 업데이트는 새 키를 다시 만들기 전에 이 키의 가용성을 확인한다. 환경이 소실되면 동일 키 재사용을 보장하지 않는다.

빌드 환경은 비공개 `android_build/`에 JDK17·Gradle8.11.1·Android SDK35/빌드도구35.0.0을 복구했다. 기존 환경 프록시/CA를 유지했고 TLS 검증을 끄지 않았다. Gradle/시험 프록시 설정과 자격값은 저장소에 넣지 않았다.

APK SHA-256: `27c41663ba08ef234290981291d26033863a5eb05dc0fdb80a7754ba3a0759e1`.
APK 크기: 788876바이트.
기존 인증서 SHA-256: `9a1683266e9f9b98150acc52ada0c827d12a89b01a6796adab0ea9714283b309`.
새 인증서 SHA-256: `f75224110a7b12465dd225abb9df1b26c96209b58745aaa48ef1603c87be73f9`.

코드·시험·문서는 지정 브랜치에 저장하고 원본 녹화·SFA·그림·APK는 Drive/비공개 캐시에만 둔다. Kaggle 모니터링은 사용자 지시대로 Claude에게 맡긴 상태이며 이번 모바일 수정으로 추가 실행하지 않았다.
