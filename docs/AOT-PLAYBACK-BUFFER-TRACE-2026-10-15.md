# 재생 Frame·Picture·Image 버퍼 경계 — 2026-10-15

- 기존 view_sequence_activity.dart와 playback_timeline.dart AOT를 추적했다.
- 편집 EditorFrameCache 및 MP4 export와 구분한다.
- 실제 앱 성능/FPS/픽셀 검증을 추가하지 않았다.

## 원본 Frame 데이터

- getFrameAt(0x5183bc)은 원본 frame **위치 index** 범위를 검사하고 index→Frame cache를 조회한다.
- hit도 _ensureFrameLoaded를 호출한다.
- miss는 Sequence.GetFrames에서 해당 index의 Frame을 얻고 필요 데이터 공급 뒤 cache에 넣는다.
- 편집 renderable Frame cache의 FrameID 키와 다르다.

- _getCachedFrame(0x5192fc)은 remove/reinsert로 최근 사용 순서를 갱신한다.
- _putCachedFrame(0x51851c)은 insert 뒤 100개를 넘으면 첫 키 하나를 제거하고 그 Frame의 AO map을 해제한다.
- native Picture/Image 폐기가 아니다.

- _ensureFrameLoaded(0x5185f8)는 AO 목록/읽은 FrameID Set을 확인해 이미 공급된 자료를 재사용하거나 GetAnimationObjectsForFrame→Frame.AddAnimationObject로 공급한다.
- _rememberFrameReadHere(0x5187ec)는 이 화면이 읽은 Frame identity별로 AO 점 수 합계를 기록한다.
- 누적 점 수가 500000을 넘고 추적 Frame 수가 2를 넘는 동안 오래된 항목의 AO 목록과 map을 null로 만들고 읽은 ID Set에서 제거한다(0x5189d0/9e8→0x518a94/98/abc).500000은 byte 한도가 아니다.
- 따라서 위치 cache에 Frame 객체가 남아 있어도 상세 AO 데이터는 다시 필요할 수 있다.

## 출력별 Picture와 보간 plan

- _record(0x63f8cc)는 PlaybackEnumeration.outputAt(outputIndex)로 앞/뒤 원본 index 및 보간 위치를 얻는다.
- 원본·끝점 동일·뒤 frame 없음 등 분기는 원본 Frame을 RecordPicture에 넘긴다.
- 두 다른 Frame 사이의 보간이면 FrameInterpolationPlan.apply 후 배경색 보간과 RecordPicture로 이어진다.

직전 보간 plan(thread.field3b)은 앞/뒤 Frame **identity 쌍**이 같을 때 재사용한다(0x63fa50/68). 불일치면 뒤 Frame의 TweenLinks를 공급하여 새 plan을 만든다. 이 분기에는 색/점 전부의 변경 버전 키가 없으므로 ‘같은 객체를 임의 수정해도 항상 안전한 plan’이라고 일반화하지 않는다.

- ViewSequencePlayerView.RecordPicture(0x516dc0)는 새 PictureRecorder/Canvas→배경·clip/DrawInformation→FrameDrawPlanCache.planFor와 Frame.Draw→endRecording으로 간다.
- 편집 EditorFrameCache.paint를 호출하는 경로가 아니다.
- 기하/글로우의 공유 cache까지 사용하지 않는다는 뜻은 아니다.

- 결과는 outputIndex→Picture? map(thread.field2f)에 저장한다(0x63fb7c). 실패/예외는 FlutterError.reportError 후 null도 저장할 수 있다.
- null entry와 아예 없는 key를 구분해야 한다.
- native approximateBytesUsed를 누적한다.
- 전 출력의 완성 픽셀 배열을 미리 만드는 방식이 아니다.

## 선행 기록과 화면용 Image

_recordAhead(0x63f0b8)의 루프는 현재 위치에서 최대 120후보를 본다. 다음 조건에서 그 호출의 선행 작업을 멈춘다.

- Stopwatch.elapsedMicroseconds≥6000.
- Picture map 항목 수≥120.
- Picture approximate byte 합계≥0x4000000(64MiB).

- 각 제한은 검사 시점 기준이다.
- 개별 RecordPicture 뒤 전체 사용량이 항상 한계 이내라는 보장은 아니다.
- 이 값들을 앱 전체 GPU/RAM 사용량 상한으로 쓰지 않는다.

- _finishAhead(0x63e478)는 현재부터 최대 4후보를 보되, Picture가 있고 finished map에 아직 없는 첫 후보 하나를 Image로 만든 뒤 반환한다.
- 호출당 4개를 모두 변환한다고 읽으면 틀린다.
- 새 Image 추정치(계산한 정수 폭×높이×4)를 기존 Image 예산에 더해 64MiB를 넘으면 만들지 않는다(0x63e688–6a4).

- FinishPicture(0x63e94c)는 배치 이동·축척을 적용해 Picture를 새로 기록하고 toImageSync한 뒤 임시 Picture를 dispose한다.
- 기존 Picture 자체가 Image로 대체되어 사라지는 것은 아니다.
- _FinishedImage에는 Image·imageRect·Placement·추정 byte가 들어간다.

- _finishedFor(0x63f6a8)는 outputIndex로 찾은 Image의 Placement5개 double을 현재 배치와 비교한다.
- 배율, 화면 origin×배율의 소수 부분, 논리 폭·높이가 다르면 해당 finished 항목을 제거하고 null을 반환한다.
- 소수 부분은 floor를 뺀 값이며 절대 origin 좌표 전체를 key로 비교하는 것이 아니다.

_onTick은 Picture가 있고 due이면 finished Image를 찾고, 없을 때도 Picture와 null Image를 ShowPlaybackPicture에 전달한다(0x63e2f4–34c). ShowPlaybackPicture는 표시 Image와 Picture를 각각 교체한다. 이 전달 경로만으로 실제 Flutter backend의 모든 fallback 픽셀이 동일함을 증명하지 않는다.

## 만료와 소유권

_releaseOutputsBehind(0x63f278)는 현재 표시 output은 보존하고, 현재에서의 순방향 거리(루프 재생 시 wrap)가 120미만인 범위 밖의 key를 _removeBuffered로 제거한다. _removeBuffered는 finished Image 먼저 제거, Picture map remove, approximate byte 차감 순서다.

화면에 현재 표시 중인 Picture/Image와 동일하면 그 제거 함수가 바로 dispose하지 않는다(0x51a06c/0x51a194). 표시 교체 함수도 thread.OwnsPicture/OwnsImage 여부를 확인한 뒤 자원을 폐기한다. map에서 뺐다는 사실만으로 화면이 아직 쓰는 native 자원을 즉시 파기한다고 해석하지 않는다.

- InvalidatePlayback→InvalidateBuffer는 DisposePictures와 보간 plan/열거 상태 null 처리를 거친다.
- 실행 중 상태에서는 열거/clock을 다시 만든다.
- 원본 Frame cache clear와는 별도다.
- _clearFrameCache(0x552768)는 보관 Frame의 AO map을 해제하고 위치 map을 비우는 함수다.

## 재생 clock과 export FPS의 구분

- PlaybackClock은 열거에서 정한 FPS를 사용하며 초기화에서 최소 1로 만든다.
- 첫 shown은 기준 시간/표시 counter를 보관한다.
- 이후 k의 목표 시간은 기준시간+정수나눗셈((k−기준 counter)×1000000/FPS)이다.
- isDue는 현재시간에 min(정수 period의 절반,8000µs)을 더해 목표와 비교한다(0x63f850–87c).

shown은 목표보다 한 정수 period 이상 **초과**해 늦으면 기준시간/counter를 현재로 다시 잡는다(0x63f5a0/5a4). _onTick의 확인한 경로는 표시 counter를 한 번 증가시키며, 지연량만큼 원본 frame을 건너뛰는 공식을 이 구간에서 사용하지 않는다. 모든 ticker/OS 정지·백그라운드 동작까지 보장한 결과는 아니다.

- 이는 실시간 화면 스케줄링이다.
- export의 (T 트위닝,P 재생) 타임라인/프레임 생성 규칙을 이 clock의 지연 보정으로 대체하면 안 된다.
- export 근거는 GROUP-SHADER-TIMELINE 및 EXPORT-DISPATCH 보고서를 재사용한다.

## 검증과 제한

- 선택 명령 대조는 AOT-PLAYBACK-BUFFER-AUDIT-2026-10-15.json이다.
- Frame identity·출력 index·Placement의 재사용/해제 정상 경계를 확인했으며 실제 앱 측정이나 GPU 픽셀 검증은 아니다.
- 예산 숫자를 성능 보장으로 사용하지 않는다.
- 기존 영상·폰·unit/probe 시험은 반복하지 않았다.
