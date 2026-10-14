# AI-sfa 인수인계 — 2026-10-14

## 이 파일부터 읽기

사용자는 한국어로 소통하며, PC 없는 루팅 안 된 Android/Termux 환경이다. GitHub `twoapple08/AI-sfa`에 구현 반영을 허용했다. 앱 제작자의 역공학 허가를 받았다고 설명했다. APK/사용자 작품 자체와 역컴파일 원본을 공개 저장소에 올리지 않는다.

## 현재 최우선 목표와 사용자 결정

### 최신 체크포인트 — 2026-10-14 v1 반환 영상 분석

- `1000326586.mp4`를 첨부 로컬 파일로 받아 분석. 사용자 인코딩 설명 (24,24), 실측 1920×1080/24FPS/768프레임/32초. 디코딩 프레임 수도 768이다.
- 각 구간 5장씩 총 80 표본 비교: 01–12/15/16은 기대 변화와 표본 일치. **13 레이어 표시, 14 순서 전환은 기대 불일치.** 두 구간은 48프레임 전체의 색 영역 검사도 수행했다. 전체 기능 완료나 정확한 픽셀 일치는 아니다.
- 입력/영상 체크섬, 시점, 관찰 범위는 `docs/APP-VERIFICATION.md`. 원본 영상/추출 프레임은 공개하지 않았다. 생성 manifest는 재생성 초기값으로 유지하며 실제 결과 기록과 구분한다.
- APK-ORDER-01 추가: draw_order는 frame_id 없는 animation_object 테이블의 도형 공통 속성. 같은 AO ID의 순서를 프레임별로 바꾼 시험 설계가 앱 DB와 맞지 않을 가능성. importer 정책/출력 경로 원인은 미확인이며 앱 오류로 단정하지 않는다.
- 사용자 보고: 생성 시 FPS에 관계없이 가져온 뒤 (60,12)로 고정되는 것으로 관찰. 정확한 시험 조합과 강제 초기화/설정 승계 원인은 미확인. 가져오기와 (24,24) 출력 단계를 구분한다.
- **다음 요청은 APP-V1-ROUNDTRIP: 앱에 가져온 합본을 수정 없이 SFA로 다시 내보낸 파일 1개**. LayerDef.Visible/DrawOrder/동일 AO ID/FPS 관련 속성을 비교하고 그 뒤 필요한 실험만 요청한다. 전체 영상과 FPS 설정 화면은 다시 요청하지 않는다.
- 사쿠가/학습/AI 연결은 계속 보류. 기존 자동 검사 18개는 이전 체크포인트에서 통과했으며 이번에는 Python/생성 데이터를 변경하지 않았다.


### 정적 조사 체크포인트

- 최초 4164103에서 깨끗하게 clone했고 이후 문서 변경 acf1496을 원격에 반영했다. 다음 변경도 최신 원격 head/tree와 expected_sha로 보호한다.
- 제공 APKS 체크섬 일치 확인. ARM64 SQL/문자열의 오프셋·한계는 APK-EVIDENCE-51.0.0.md. jadx/adb/Flutter가 없어 추가 Java 역컴파일/앱 실행은 수행하지 않았다.
- 분할은 base.apk/split_config.arm64_v8a.apk 등 실제 이름으로 판별. 원본/추출물은 저장소 밖에 유지했다.

**먼저 Stick Fighter의 모든 창작/편집 기능을 분석·명세·검증하고, 기능을 하나씩 사용하는 시험 애니메이션을 만든다. 그 뒤 AI 입력 연결과 자료 학습을 진행한다.**

- 색상/알파/채우기/개별 굵기/글로우/늘리기/원근/변형/그룹/연결/레이어/트위닝 모두 핵심 범위.
- 최소 기능 SFA 생성으로 목표를 축소하지 않는다. 적은 도형으로 표현할 수 있는 경우 불필요한 오브젝트 증식을 피한다. 고정 개수 제한으로 잔상/파편 등 필요한 표현을 훼손하지 않는다.
- 커스텀 제작 UI를 별도 앱에 복제하는 것은 우선 제외하지만, 기존 캐릭터와 도형에 쓰이는 기능과 저장 데이터는 분석한다.
- 나무위키를 참고하지 않는다. 현재 APK·제공 파일·앱 결과가 근거.
- FPS 표기는 항상 **(트위닝 FPS, 재생 FPS)**. (24,24)는 추가 보간 없음. (60,12)는 원본 초당12 → 보간 출력60.
- 사용자에게 모든 기능 샘플을 무작정 요청하지 않는다. 분석 후 꼭 필요한 통제 실험만 요청한다.
- 사용자는 효율적인 시점에 이 인수인계 파일을 갱신하고 새 대화용 프롬프트를 제공하길 명시적으로 요청했다.

## 배포할 AI와 구분

현재 학습된 AI나 Android APK 앱은 없다. 있는 것은 Python SFA 도구·일부 네이티브 시간축 구현·명세와 시험 파일이다. 모델에 '완전히 학습/58000% 이해'시켰다고 주장하지 않는다. 검증된 명세와 엔진을 AI가 호출하는 방식이 권장안이다.

후속 목표만 기록: Sakugabooru의 별1개 이상 작품, 원어/한국어 태그(smears→스미어)와 자연어 동시 입력, 사용자 기기의 로컬 실행. 지금 수집/다운로드/학습/모델 선택/Android 패키징으로 진행하지 않는다. 별 표시 의미도 아직 미확인이다. 직접 웹 조회는 520으로 실패했다.

## 저장소 사용

- `sfa.py`: ZIP/XML 읽기·검사·보존 재저장, 기본 스틱맨 wave, 근사 HTML preview. 표준 라이브러리만 사용.
- `native_timing.py`: APK 네이티브 export의 시간축 모델. 전체 Flutter 보간 재현 아님.
- `build_feature_probes.py`: 16개 기능 상태 시험과 합본/ZIP/manifest 재생성.
- `tests/`: 현재 **18개 자동 검사** 통과.
- `examples/wave_test.sfa`: 원본48프레임 팔 흔들기. 사용자가 앱에 가져와 영상 출력 성공. 반환 영상은 24FPS/48프레임/2초였지만 가져오기 직후 UI는 (60,12)였다고 설명.
- `examples/probes_v1/`: 16개 × 48프레임, 합본768프레임. (24,24)에서32초 목표. **반환 영상 14구간 표본 일치, 13/14구간 기대 불일치.** 최대20AO/프레임.
- `docs/FEATURE-PROBE-GUIDE.md`: 시간대별 검사표와 미검증 범위.

실행은 반드시 저장소 루트에서:

```bash
python -m unittest discover -s tests -v
python build_feature_probes.py
python sfa.py validate examples/probes_v1/feature_probes_v1.sfa
python native_timing.py 122 --fps 60 12 --sample 1
```

## 근거 파일과 관찰

대화에 첨부된 파일은 원래 작업 환경에서는 `upload/`에 있었다. 임시 환경이 사라졌으면 필요할 때 파일 이름으로 사용자 Library에서 찾아 materialize하거나 사용자에게 해당 파일만 다시 요청한다. 역컴파일 결과는 저장소에 없다.

- `01_base.sfa`~`05_same.sfa`: 기본/팔/이동/프레임수/동일 자세. ZIP 내부 XML 하나.
- `06_shapes.sfa`, `07_custom.sfa`, `08_layers.sfa`: 기본 도형, 채우기, 두 레이어.
- `09_tween.sfa.sfa`: 5프레임, (24,24) 영상 `1000326550.mp4`: 24FPS/5프레임/0.208333초.
- `Anonymous user file-1.sfa`(XML 이름 연습)122프레임 → `1000326557.mp4`610프레임/60FPS/10.166667초.
- `Anonymous user file-2.sfa`(팡)90프레임 → `1000326558.mp4`450프레임/60FPS/7.5초.
- 위 두 사용자 작품은 (60,12). 원본/영상은 공개하지 않음.
- `1000326576.mp4`: wave 가져오기 반환 영상,24FPS/48프레임/2초.
- `STICK FIGHTER (51.0.0).apks`: Skit으로 정상 추출, 본체와 ARM64/ja/ko/xxhdpi 분할 포함. App Manager/Shizuku로 재추출할 필요 없음. 패키지 com.sG.stickfighter.activities, versionCode51000.
- APKS SHA256 `c1c39e031f0fc4a904755f08c45406e4fd3c894dafe1e506c0c0ac7dd78eff76`.

## APK 조사 방법과 확정 범위

원래 환경에서 `/tmp/stickfighter-apks/part-3.apk`가 base, part-4가 ARM64였다. Java와 jadx1.5.6을 사용. 출력 `/tmp/stickfighter-code/sources/`. MainActivity의 큰 export 메서드는 일반 decompile 실패 → fallback으로 `/tmp/stickfighter-MainActivity-fallback.java` 생성. Flutter AOT libapp.so는 `/tmp/stickfighter-libapp.so`. 이 경로들의 존재는 새 환경에서 보장 안 됨.

- 앱은 Flutter AOT + Android Kotlin/Java 혼합. JADX만으로 Flutter 로직 전체가 복원되는 것은 아니다.
- X2.a: sequence의 fps/thickness, animation_object_detail의 thickness_scale/object_scale 등 로드. DB fps DEFAULT12는 현재 import 경로가12를 강제한다는 증거가 아니다.
- W2.e: SharedPreferences의 smoothness_ 접두사 read/write, 영상 exportFps/tweeningFps 인자.
- libapp 문자열: last_project_fps/smoothness/thickness, PerspectiveKindPanel/perspective-bend 등. **문자열 존재만으로 알고리즘을 안다고 기록하지 않는다.**
- MainActivity.v 네이티브 export: T>P일 때 출력 개수 round(N/P*T), 출력 FPS=T. 아니면 원본N개와P. 출력j 위치=(j/T)*P, 다음 인덱스는 마지막으로 제한. 마지막은 hold.
- Y2.i.d/e: 같은 AO ID로 도형 대응, X/Y 및 일부 색/글로우 속성 선형 보간.
- **추가로 확인:** Y2.c.f3609d는 DB loader X2.a의 `index_number`에서 온다. 따라서 위 네이티브 점 대응 필드는 DB point index다. 현재 XML AP.Index와 importer 사이 직접 연결은 아직 확인 필요. AP.ID 자체와 혼동하지 말 것.
- Y2.g: 표시 영역 너비/높이에 대한 X/Y 백분율, 종횡비 유지.
- Y2.m: TypeId1 선,2 두 점을 지름으로 한 원,3 이차 베지어. 도형별 굵기 최소값/보정 존재.
- Y2.i.a 일반 도형 굵기 배율 max(0.05,sequence.thickness/100*detail.thickness_scale). 이것 하나가 모든 출력의 최종 픽셀 굵기는 아님.

## 데이터 주의

- AO ID는 원본 프레임 사이 유지될 수 있고 AP ID는 바뀜. AC 연결과 FR/FS 참조를 함께 보존.
- Flags 비트의 전체 의미 미확인. 임의로 정리/삭제 금지.
- 실제 작품 FS Kind0에는 endpoint=-1과 부분 경계T, Kind1에는 ObjId만 있는 형태, Contour도 있음. 검증기는 이를 허용하도록 보완함.
- 첫 실제 작품에 TweenLink(ID,From)10개. 전체 의미·참조 방향·Flutter 처리 미확인.
- HTML preview는 근사. 채우기/글로우/정확한 굵기/앱 트위닝 미지원. 실제 앱 결과 대신 사용하지 말 것.

## 남은 주요 작업

1. 영상 비교는 완료. APP-V1-ROUNDTRIP 재저장 SFA를 비교하여 13/14 실패 원인을 좁힌 뒤 필요한 개별 실험만 요청.
2. Flutter SFA importer/exporter와 기본 FPS·전체 굵기 초기화 경로 확인.
3. 실제 편집 도구 늘리기/뒤집기/원근/굽힘/그룹/올그룹/연결 해제의 기준점·범위·직렬화 분석. 이번 좌표 probe는 UI 버튼 알고리즘 재현이 아님.
4. Flutter TweenLink, 생성/삭제/변형/색/채우기/레이어 변경 보간 정책 확인.
5. 복잡한 채우기/구멍·레이어잠금·프레임 편집·편집 보조 UI를 포함한 검사표 확장.
6. 검증 범위가 충분해진 뒤 명령 실행 엔진·AI 연결. 사쿠가 수집과 학습은 보류.

## GitHub 상태와 주의

연결 문제는 해결돼 실제 쓰기 성공. 기존 origin/main 커밋은 도중 다른 대화가 바꿀 수 있으므로 변경 전 최신 head/tree를 읽고 expected_sha로 갱신한다. 사용자 파일/변경을 덮어쓰지 않는다.
원래 로컬 `AI-sfa/`는 최초 로컬 root commit과 원격이 다른 이력이므로 그대로 push하지 말 것. 이후 `AI-sfa-review/`를 새로 clone해 이 시험 작업을 진행했다. 새 대화에서는 깨끗한 clone으로 시작하면 된다.

터미널 git push는 인증이 없었지만 GitHub connector create_blob/create_tree/create_commit/update_ref는 작동했다. 최초403을 이유로 또 연결 설정을 사용자에게 반복 요청하지 말 것. 실제 오류가 재발하면 그때 확인.

## 사용자에게 전달할 결론

16구간 영상은 14구간 표본 일치, 2구간 기대 불일치. 전체 기능 분석/AI/APK 완료가 아니다. 다음은 앱에서 재저장한 합본 SFA 한 파일로 불일치 원인을 좁히는 단계. 새 대화가 필요하면 `docs/HANDOFF-PROMPT.md`를 사용한다.
