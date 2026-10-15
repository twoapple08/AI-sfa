# 서버 분석 환경 복구 결과 — 2026-10-16

사용자는 02:02 KST에 서버 도구 설치·다운로드·AOT 재추출을 복구 예외로 명시 허용했고, 02:06에는 원래 지시가 ‘완료했고 필요 없는 작업의 불필요한 반복 방지’라고 정정했다. 작업 종류를 일률적으로 금지하는 해석은 정정한다. 이 권한과 정확한 취지는 AGENTS/HANDOFF/재개 프롬프트에 유지한다.

## 복구와 검사

기존 원본 APKS의 libapp.so/libflutter.so/바이너리 glow.frag를 비공개로 복구했다. 세 SHA-256은 기존 FLUTTER-TOOLS/GROUP-SHADER-TIMELINE 보고서와 모두 일치한다. 원본 작품·영상 재분석이나 폰 설치/페어링/시작 시험은 하지 않았다.

과거와 같은 Blutter commit `4a60ac648bf448c5a7596437243bcd0b9376fdf0`, Dart SDK commit `98116461144f4429ab873f8497023a5ec3b08127`을 사용했다. Dart3.12.0/ARM64/compressed pointers, snapshot `41be3daaabd524b8aa7423bc24584957`과 맞는다. Python venv의 CMake/Ninja/Capstone/pyelftools 및 ICU74 헤더로 도구를 복구했다. 로컬 변경은 dependency 경로와 Ninja -j2이며 AOT 해석 알고리즘을 변경하지 않았다.

초기 복구 이전의 설치/clone 자동 검토 거절은 과거 기록이다. 새 명시적 허용 후 설치·다운로드가 통과했다. 빌드 후 Capstone SONAME `libcapstone.so.5`의 로컬 링크를 보완하고 추출이 종료0으로 완료됐다. 현재 도구가 없는 상태가 아니다.

| 출력 | 이번 복구 | 기존 기록 |
|---|---:|---:|
| 전체 파일 | 671 | 671 |
| asm 파일 | 666 | 666 |
| 전체 bytes | 86,508,012 | 86,508,012 |
| 주소·크기 선언 블록 | 12,752 | 12,752 |

이는 수량 대조이며 모든 출력 파일의 과거 checksum을 대조한 뜻은 아니다. 같은 원본 ELF에서 기존 호출 주소3곳을 새 Capstone으로 읽어 실제 bl 대상이 기존 근거와 일치하는 것도 확인했다. 전체 함수 의미·실제 앱 실행·backend 픽셀 동등성을 새로 검증한 것은 아니다. 감사는 [복구 집계](ANALYSIS-RECOVERY-AUDIT-2026-10-16.json)에 있다.

## 비공개 백업

`AI-sfa-analysis-cache-2026-10-16.zip`을 비공개로 저장했다. AOT/PP/objs, 입력 ELF·shader, 실행 바이너리, 읽기용 Python 디코더 모듈과 필요한 라이브러리·복원 안내를 포함한다. 803개 payload 파일, archive 40,381,872 bytes이며 ZIP CRC와 manifest의 모든 파일 길이/SHA-256을 검사했다. 공개 레포에는 이 요약/집계만 넣는다.

다음 환경에서 현재 경로가 없으면 이 **기존 백업을 먼저 찾아 복원**한다. 살아 있는 캐시가 있는데 다시 SDK 전체 빌드를 반복하지 않는다. Python 환경/라이브러리 호환성은 실제 복원 시 확인한다. 백업의 존재는 다음 환경에서 자동 접근을 보장하는 뜻은 아니다.

## 현재 경로와 다음 작업

현재 `/workspace/scratch/5a16c98ed7ee/private-recovery/` 아래에 `blutter_out`, `evidence`, `venv`, `blutter/bin`, `depsroot`가 있다. AOT는 `blutter_out/asm/sfa`, PP/objs는 `blutter_out`이다. 읽기 도우미는 `asm_window.py`와 `window.py`. 원본·메타데이터·전체 로그를 공개 출력하지 않는다.

남은 정적 분석은 `_cleanupUnusedAnimationObjects`/`_figuresShownFromRoots`, `Frame.GetFastHash`, 실제 시간축 callback이다. 복구 후 실제 시간축 후보 `_insertEmptyFrame`0x5105ac, `_deleteCurrentFrame`0x5a9f5c, `_pasteFrame`0x5ac4b8, `_copyCurrentFrame`0x5b171c를 찾았다. 이름 발견을 동작 분석 완료로 세지 않는다.

실제 앱 렌더 검증은 별개다. 이 서버는 x86_64이고 현재 adb/Android emulator 실행 도구가 관측되지 않았으며, 기존 계측 앱은 license4 지속 편집 차단 이력이 있다. 따라서 현재 환경 복구를 실행 검증 성공이라고 보고하지 않는다. 라이선스 우회나 학습·AI 통합을 진행하지 않는다.


## 정상 분석 재개 후 갱신

비공개 백업의 동일 파일을 version1로 갱신해 dispatch 표/진단 tool과 새 검증 스크립트도 포함했다. 실제 snapshot 표를 읽는 선택 진단 모드를 추가했으며 전체 AOT를 다시 분석하지 않는다. [UNUSED/HASH](AOT-UNUSED-AO-FAST-HASH-TRACE-2026-10-16.md), [FRAME 명령](AOT-TIMELINE-FRAME-COMMANDS-TRACE-2026-10-16.md), [DISPATCH](AOT-DISPATCH-TARGETS-TRACE-2026-10-16.md)로 분석을 재개했다. 남은 실제 작업은 최신 HANDOFF를 따른다.
