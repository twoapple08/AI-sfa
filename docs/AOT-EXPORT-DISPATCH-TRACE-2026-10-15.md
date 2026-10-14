# AOT 내보내기 중간 형식·Android 인코더 연결 — 2026-10-15

기존 AOT/PP/ELF와 Java 추출 캐시를 사용했다. 실제 사용자 영상의 실행 backend·픽셀/색 일치를 새로 검증한 것은 아니다. 공개는 직접 작성 해석과 집계만이다.

## 1. Optimized의 실제 호출 연결

ExportVideoAsyncTask.doInBackground(0x629024)는 ExportToVideoOptimized(0x629064)를 호출한다(0x629054). 그 closure(0x629150)가 PlaybackEnumeration, 출력 크기, 프레임/보간 준비, 중간 파일 기록, 인코더 호출을 담당한다.

이 읽은 경로에서 선택하는 것은 Dart 렌더러 대 Java 객체 렌더러가 아니라 **중간 형식 raw RGBA 대 PNG 이미지 묶음**이다. 두 저장 함수는 같은 _recordExportPicture를 사용한다.

| 경로 | Dart 프레임 생성 | 플랫폼 메서드 |
|---|---|---|
| raw | drawAndAppendRawRgba → _recordExportPicture → Picture.toImage → Image.toByteData(rawRgba) → frames.rgba에 append | encodeVideoFromRawRgbaFile |
| PNG | drawAndSave → _recordExportPicture → Picture.toImage → Image.toByteData(png) → frame_00000.png 형식 기록 | encodeVideoFromImageSequence |

호출 근거: raw 0x62a3e0/0x62e0fc/0x62e140/0x62e160, PNG 0x62a464/0x62c160/0x62c1a4/0x62c1c4. PP ImageByteFormat 이름 rawRgba(index0), png(index4)를 확인했다. raw가 rawStraightRgba라는 주장은 하지 않는다.

_recordExportPicture의 동기 Draw/Picture 기록은 기존 DPR1 wrapper와 연결된다. Picture.toImage 이후 비동기 전체가 그 override 안이라는 뜻은 아니다. Frame/InterpolatedFrame의 실제 Draw를 영상 pixel로 재측정한 것이 아니다.

## 2. 중간 형식 선택 조건

closure는 _getDirectoryUsableSpace(0x629800)를 기다린 뒤(0x629810) 출력 크기 width×height×4×N을 예상 raw bytes로 계산한다(0x629840–0x629850). N은 이 경로에서 사용하는 PlaybackEnumeration.field_2b의 산출 개수이며 0x629678–0x629680에서 읽힌다. Timeline 생성자에는 이 개수를 산출·저장하는 경로가 있다. 전체 endpoint/FPS 규칙을 이번 검사로 확정하지 않는다.

확인한 분기:
- N≤0이면 raw 선택 false.
- 사용 가능 bytes 값이 있으면 예상raw bytes+536,870,912≤사용 가능 bytes일 때 raw true.
- 사용 가능 공간 값이 null이면 예상raw bytes≤2,147,483,648일 때 raw true.
- 나머지 false는 PNG 기록 경로다.

boolean은 context.field_37에 저장(0x6298b4), 프레임 저장 분기에서 사용(0x62a38c), 마지막 인코더 선택에서 다시 사용(0x633b40–0x633b48). 이 선택을 codec 지원 여부 검사라고 이름 붙이면 틀린다. 확인한 지역에서 codec capability 호출은 이 boolean 공급자가 아니다.

image 확장 선택용 context.field_3b는 false로 초기화된다(0x6298b8). 마지막 closure는 이 값에 따라 jpg/png를 선택할 수 있지만, 현재 읽은 export closure의 저장 함수는 PNG이고 이 flag의 재대입은 찾지 않았다. 확인한 경로는 PNG→inputExtension png 연결이다. JPG 플랫폼 지원이 존재한다는 사실만으로 export가 자동 JPEG 최적화를 한다고 주장하지 않는다.

raw/PNG 중간 기록 실패나 인코더 실패 후 다른 형식으로 전체 작업을 자동 재시도한다는 규칙은 확인하지 않았다. 사전 선택과 실패 fallback을 구분한다.

## 3. 플랫폼 브리지와 Android 호출자

PP MethodChannel의 이름은 sfa/platform_bridge, StandardMethodCodec이다(pp+0x3180). Dart main:
- _encodeRawRgbaFileToVideo(0x515424) → invokeMethod(0x515514), inputFilePath/outputFilePath/frameRate/width/height.
- _encodeImageSequenceToVideo(0x5157dc) → invokeMethod(0x5158ec), inputDirPath/outputFilePath/frameRate/inputExtension.

마지막 export closure 0x633b20는 raw bridge(0x633bb4) 또는 image bridge(0x633c3c)를 고른다. 응답 success/message가 ExportResult로 연결되는 코드가 있다. 실패가 사용자 영상에서 실제 발생했는지는 알 수 없다.

기존 Java 캐시 연결:
- A3/AbstractActivityC0076f.java:461는 같은 channel을 W2.e handler에 등록한다.
- W2/e.java:115–131 raw 메서드의 인수를 읽고 W2.g thread를 시작한다. W2/g.java:run → MainActivity.t.
- W2/e.java:806 이후 image 메서드는 thread → MainActivity.s.
- MainActivity.s → V4.b.X, MainActivity.t → V4.b.Y.
- X/Y는 공통 V4.b.V 인코딩 루프를 사용한다.

이 Java 연결은 캐시의 decompiled 구현 읽기다. Dart 명령표본 검증을 Java의 전체 bytecode 검증으로 세지 않는다.

## 4. Java는 완성된 프레임을 인코딩한다

V4.b.X는 frame_%05d.extension을 0부터 순서대로 찾는다. 첫 이미지의 bounds로 크기를 읽고 각 Bitmap을 디코딩한다. 필요하면 encoder 크기로 필터링해 스케일한 뒤 GLUtils.texSubImage2D로 올린다. 다음 파일이 없으면 공급 종료다. decode 실패는 실패 경로이며 불완전한 중간 파일의 조용한 보완 규칙으로 해석하지 않는다.

V4.b.Y는 짝수 정규화 크기×4로 frame bytes를 계산한다. file length가 한 프레임보다 작거나 frame bytes의 배수가 아니면 실패한다. direct ByteBuffer로 한 프레임씩 읽고 GL_RGBA/GL_UNSIGNED_BYTE로 glTexSubImage2D한다. 한 프레임 미만의 read는 오류, 정상 EOF는 공급 종료다.

공통 V4.b.V:
- MediaCodec.createEncoderByType(H.264 MIME), surface input 설정.
- color 관련 설정을 넣은 configure가 실패하면 이를 제외한 설정으로 새 codec configure를 시도한다.
- createInputSurface → EGL surface → W2.r texture renderer.
- MediaMuxer(output,0), codec.start, 프레임 공급/출력 drain.
- EGL presentation time은 index×1,000,000,000/max(frameRate,1) ns.
- EGL swap 후 codec drain, 입력 종료 signal/end 처리 경로.

W2.r의 fragment shader는 업로드된 texture를 샘플링해 출력하는 구현이다. 이 renderer를 Stick Fighter 객체/채우기/글로우를 Java로 다시 그리는 구현으로 부르면 안 된다. 이미 그려진 이미지를 인코더 입력 surface로 옮기는 단계다. texture flip/색 공간/alpha와 최종 출력 픽셀 차이는 별도 검증 범위다.

V4.b.P의 정적 codec 설정:
- bitrate = clamp(width×height×frameRate×18/100, 2,000,000, 40,000,000).
- frame-rate = 전달 rate, I-frame interval = 1.
- surface color-format = 2130708361.
- 첫 configure 설정에 color-standard1/color-range2/color-transfer3, SDK≥29에서 max-bframes0.
실제 기기 codec의 준수/최종 색·bitrate·hardware/software 선택은 미계측이다.

출력 축은 Dart _normalizeEvenDimension(0x6335e8), Java MainActivity.t/o0에서도 최소2/홀수내림 정규화한다. 이것을 사용자 좌표 수정이나 offscreen 객체 제거와 혼동하지 않는다.

## 5. 검증·인수인계

신규 Dart 명령 21곳 ELF PT_LOAD/Capstone 대조 모두 통과. audit AOT-EXPORT-DISPATCH-AUDIT-2026-10-15.json. 기존 단위시험/probe/영상 분석/휴대폰 시작 시험을 반복하지 않았다. 레포 코드 변경은 없고 보고서·인계 문서만 변경했다.

해결: Optimized → raw/PNG 저장 선택 → 같은 Dart Picture 생성 → 플랫폼 브리지 → Android X/Y → 공통 surface H.264/MP4 루프를 연결했다.
남음: 사용자가 제공했던 영상의 어느 분기 실행인지, 실제 codec·색·pixel 결과, 그룹 글로우 별도 선택, shader asset 수학식, export timeline endpoint/FPS 전체 규칙. 캐시 경로가 연결되었다는 이유로 전체 Stick Fighter 이해 완료를 주장하지 않는다.

새 대화의 첫 작업: **FrameDrawPlan.drawUnit/그룹 glow 합성 경로에서 shader/raster/MaskFilter 선택을 추적**한다. 그다음 shader asset 구조·수학식 확인, export PlaybackEnumeration endpoint/FPS 연결을 확인한다. 기존 원본/00–05영상은 재분석하지 않고 정적 경로를 먼저 연결한다. runtime 계측은 기존 license 응답4 차단 상태를 유지하며 변경/우회/재설치/폰 명령 요청은 없다.

캐시: e23c9fd610d3/private/blutter_out/asm/sfa/{main.dart,original_port/activities/sequence_action_activity.dart,original_port/sequences/playback_timeline.dart},pp.txt,ELF/venv. Java 6d77389e706a/private/decompiled/sources/{A3/AbstractActivityC0076f.java,W2/{e,g,r}.java,com/sG/stickfighter/activities/MainActivity.java,V4/b.java}. 새 검사 25b8ca176661/private-trace/{validate_export_dispatch.py,export-dispatch-validation.json}.
