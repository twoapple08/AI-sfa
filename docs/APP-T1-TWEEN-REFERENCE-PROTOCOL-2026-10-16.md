# APP-T1 트위닝 기준 영상 — 시험 파일·예측·요청 — 2026-10-16

목적: `sfa_tween.py`에 옮긴 정적 보간 규칙을 실제 앱 영상으로 판정하고, 기준 렌더러에 보간을 더한다. 근거는 [GROUP-SHADER-TIMELINE](AOT-GROUP-SHADER-TIMELINE-TRACE-2026-10-15.md)(PlaybackEnumeration), [OBJECT-TWEEN-PAIR](AOT-OBJECT-TWEEN-PAIR-TRACE-2026-10-15.md), [FILL-TWEEN](AOT-FILL-TWEEN-TRACE-2026-10-15.md)이다. 기존 실물 표본 03(생성·삭제·FR 유지·알파 보간)과 05(수동 링크)는 이미 확인된 결과로 재사용한다. **이 문서 시점에는 앱 결과가 없다.**

## 코드

- `sfa_tween.py`(표준 라이브러리만 사용): 다음 규칙을 구현했다.
  - 시간축: Q=T(활성일 때), K=max(round(Q/P),1)(0에서 먼 반올림), N=ceil(F·Q/P), t=m/K, 마지막 원본 반복.
  - 객체 짝: 앞 프레임의 **보이는 레이어** 순서로 순회한다. 수동 TweenLink(뒤 프레임의 ID=뒤 AO, From=앞 AO, 충돌 검사 포함)를 먼저 보고, 없으면 같은 ID를 쓴다.
  - 점: Index로 대응하고 좌표는 선형 보간한다.
  - 속성: 색은 채널별로 앞값+round(델타·t), ThicknessScale은 선형, GlowRadius·GlowThickness는 반올림, GlowAlpha는 앞값+trunc(델타·t). ObjectScale은 앞값을 유지한다.
  - 채우기: signature 대응 → 정규화 키가 양쪽 모두 유일할 때 대응. 대응된 것은 색·T를 보간하고, 앞에만 있는 것은 t<1 동안 유지, 뒤에만 있는 것은 t=1에서만 나타난다.
- 근사로 처리한 부분(ASSUMPTION 표시): 중간 프레임 배경은 앞 프레임 값을 쓴다. 채우기 정규화는 회전 비교 대신 정렬로 근사했다.
- `tools/render_video.py`: SFA 전체를 이 규칙과 `sfa_render`로 MP4/PNG 렌더한다.
- 기존 `native_timing.py`(Android 네이티브 인코더 모델: N=round(F·T/P), 연속 t)는 Flutter export 경로(PlaybackEnumeration)와 산식이 다르다. 그대로 보존하되, 렌더러는 `sfa_tween.timeline`을 쓴다. 03 표본(F=168, (24,12)→336)은 두 산식이 같은 값을 내서 둘을 구별하지 못했다. 이번 (30,12) 시험은 K 양자화로 둘을 구별할 수 있다.

## 시험 파일과 예측

`examples/tween_v1/08_tween_reference.sfa`(`python build_tween_probe.py`로 다시 만들 수 있다): 원본 14프레임(사례 7개 × A/B), (트위닝,재생)=(30,12).

**예측:** 출력 30FPS, **35프레임**(약 1.167초), K=3이다. 각 사례 A→B에는 t=1/3, 2/3 중간 프레임이 2장씩 있다. 사례 사이(B→다음 A)는 ID가 달라 짝이 없으므로 중간 1장이 빈 화면이다.

| 사례 | 출력 A / 중간 / B | 정적 예측 |
|---|---|---|
| motion | 1 / 2,3 / 4 | 선이 직선 경로로 이동한다. 색은 채널별 반올림 보간, 굵기 1→3 |
| glow | 6 / 7,8 / 9 | 반경 round(8)=8→16, 두께 round 27→43, 알파 trunc 85→170, 색 보간 |
| hidden_layer | 11 / 12,13 / 14 | **숨긴 레이어의 주황 선은 원본(11,14)에는 그려지고 중간(12,13)에는 없다** |
| links | 16 / 17,18 / 19 | 링크된 흰 선은 미끄러지듯 이동, 링크 없는 주황 선은 중간에 없다 |
| fills | 21 / 22,23 / 24 | 왼쪽(점 참조 −1) 채우기 색은 빨강→파랑으로 보간, 오른쪽(점 ID 참조)은 중간까지 빨강 유지 |
| create_delete | 26 / 27,28 / 29 | A에만 있는 원과 B에만 있는 원 모두 중간에 없다 |
| shapes | 31 / 32,33 / 34 | 곡선 제어점과 원 지름이 선형 보간된다 |

hidden_layer 예측은 APP-V1 13번 관찰(숨긴 레이어가 원본 출력에 남음)과 보간 plan의 visible layer 순회를 결합한 것이다. 실물로 확인되면 "레이어를 숨기면 트위닝 중간 프레임에서만 사라진다"는 실사용 주의가 된다.

## 사용자 요청

1. 새 프로젝트로 가져온다. 수정하지 않는다.
2. (트위닝 FPS, 재생 FPS) = **(30, 12)**로 설정한다.
3. MP4로 내보낸다. 반환물은 MP4 1개다.

## 판정

- 영상의 프레임 수와 FPS를 예측(35, 30)과 비교한다.
- 각 출력 프레임을 `tools/compare_render.py`와 같은 방식으로 `sfa_tween`+`sfa_render` 예측 렌더와 비교한다.
- 위 표의 사례별 관찰을 기록한다. 원본 영상은 공개하지 않는다.
