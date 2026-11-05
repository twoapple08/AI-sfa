# SFA 뷰어 Windows v1.2 — 2026-11-05

사용자 지시: "윈도우 버전 스파뷰어에서 1v1 삭제, 그리고 저번에 모바일에서 수정되었던 찐 스파에서는 대가리 칠이 깜빡였던 버그 수정했던 것까지 같이 패치해서 1.2 버전으로 업데이트".
(11-03의 '요청된 모바일 뷰어만 v1.1, PC는 범위 밖'은 이번 지시로 PC까지 확장.)

## 배포
- Drive `AI-sfa/07_도구/SFA뷰어/SfaViewer-win-1.2.zip`(1ce2rsPJEK6-ifqXhKLRlA3uGbhjbYOzk, 109,956,018바이트): SfaViewer.exe + ffmpeg.exe + ffmpeg-LICENSE.txt + 읽어보기.txt. 1.0·1.1 zip은 덮어쓰지 않았다. effects.txt는 1v1 삭제로 뺐다.
- zip SHA-256 `887e9b7c18a5a4cdb49e3582bd6d0e8c7e7ef8719f69834eee4b6d247245b74c`, exe `39c088d20cc03e48082d936ef8f1ad8c5226dc3db6309cd7491c706cf2ab3578`. ffmpeg.exe·라이선스는 1.1 zip의 것을 그대로 재사용.

## 바뀐 것
1. **1v1 만들기 삭제:** 첫 화면 '1v1 만들기' 버튼, `SfaViewer/Create.cs`, `SfaCore/Gen/`(Gen.cs·Scene.cs), exe에 넣던 motion_lib.txt. 첫 화면 문구 "만들기 · " 제거. 안드로이드 크리에이터(`creator-android/`)는 건드리지 않음.
2. **머리 채움(FS Kind) 수정 이식 — 모바일 v1.1과 같은 규칙**(docs/SFA-VIEWER-1.1-2026-11-03.md): FS의 Kind(1 원 전체 / 0 경계)를 읽고, Kind 1은 대상이 원·점 2개 이상, Kind 0은 대상 종류·점 수·유한하고 폭 있는 T·Start/EndPtId가 그 객체의 점일 때만 유효. 윤곽에 부적합 조각이 하나라도 있거나 원 전체 조각이 다른 조각과 섞이면 그 윤곽 전체 생략. Kind 1의 T는 0/1로 정규화. 보간(트위닝)의 채움 짝 키에도 종류·유효성 포함. 파일 정보에 '잘못된 채움 경계 n개(그리지 않음)'.
3. 캐시 형식 3→4, 미리보기 폴더 `thumbs`→`thumbs_v12`(옛 잘못된 그림 재사용 방지). 버전 1.2.0.

## 검증
- 리눅스에서 .NET 8 SDK(비공개 /root/dotnet)로 SfaCore + 검사 도구(SfaCheck) 빌드 경고 0, Windows exe 단일 파일 publish 성공.
- 단계 1 시험작(240장): 정상 파일 잘못된 경계 0, Kind="1"을 지운 사본은 469개(모바일 v1.1 기록의 수와 같음). 120장 렌더 비교: 정상은 머리 흰 채움이 몸통 선 끝을 가리고, Kind 없는 사본은 채우지 않아 선이 비침(2,119화소 차이).
- **미확인:** Windows에서 exe 실제 실행(이 환경에 wine 없음). 1.0 때처럼 사용자 PC에서 열기·재생·MP4 내보내기 확인 필요.
