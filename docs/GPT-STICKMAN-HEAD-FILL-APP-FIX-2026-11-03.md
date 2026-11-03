# 실제 앱의 머리 채움 누락·저장 형식 수정 — 2026-11-03

## 결과부터

[사용자 실제 앱 / 모바일 v1.1 기존 파일 / 수정 파일 비교 시트](https://drive.google.com/file/d/10RRubQYjDBHfrgATc_eq4o38zQOTK2_J/view). 오른쪽 두 그림은 서버의 안드로이드 네이티브 그래픽 시험이며 실제 휴대폰 재확인과 구분한다.

- 수정 SFA: https://drive.google.com/file/d/1o3cTOMY9X9keVJczwIJqBuYbXZU5Erb_/view
- 미리보기: https://drive.google.com/file/d/1mwzRLeyrf0CsylfOdsd9bgnZ5jH3RhKe/view
- 자료 폴더: https://drive.google.com/drive/folders/1-8_VxWKolOdaPoderhWqDqcx7UU31F34

최근 근경 다리 연속 면 시험판에서 **머리 채움 경계469건의 저장 정보만** 고쳤다. 기존240장·5,207객체·10,434점·471채움(흰 머리469+근경 다리 면2),모든 AO/점/AC/색/굵기/순서/머리 숙임·접합·접촉·근경 면을 보존했다. 뼈대를 재피팅하거나 장면 좌표를 변경하지 않았다. 수정 파일의 실제 Stick Fighter 재열기/편집은 사용자 확인이 필요하다.

## 공통 원인 — 근거 구분

**사용자 실제 앱 녹화 판독:** 40.85초 녹화에서 여러 장의 머리 내부로 팔과 회색 이전 장이 비친다. 재생127·178장 부근에서 특히 명확하다. 개별 포즈 문제가 아니라 여러 장에서 같은 채움 누락 증상이다.

**파일·코드:** 직렬화기 `stickman_clip.person_aos`가 머리 FS에 ObjId/StartT/EndT/Contour만 쓰고 Kind를 빠뜨렸다. 서버 렌더러와 모바일 v1.0은 채움 종류/점 참조를 충분히 검증하지 않아 원 전체로 그렸고, 이전 검사도 흰 Color와 채움 존재 여부만 확인했다. 수집된 실제 SFA의 단일 원 채움1,293건은 전부 Kind=1이었다. `docs/AOT-FILL-MOVED-CODEC-TRACE-2026-10-15.md`와 `docs/AOT-FILL-PATH-TRACE-2026-10-15.md`도 Kind1=원 전체,Kind0=참조/구간이 있는 경계임을 구분한다.

**해석:** 종류 없는 불완전한 저장 표현이 뷰어의 관대한 처리에 가려진 공통 결함이다. 특정 장에서 머리가 사라지는 포즈 오류로 다루지 않는다. 실제 앱 XML 가져오기에서 누락 필드가 어떤 기본값으로 변환되는지까지 새로 추적한 것은 아니므로,앱 재확인 전 수정 성공을 확정하지 않는다.

## 구현

- 모든 신규 머리 채움은 `<FS Kind="1" ObjId="머리 원 ID" Contour="0"/>`로 저장한다. edge의 점/T 필드를 섞지 않는다.
- `stickman_quality.py`는 흰색 존재뿐 아니라 단일 원 전체 종류·소유 원·외곽 번호·edge 필드 혼입까지 검사한다. 옛 파일은 새 검사에서469건 실패하고 수정 파일은0건이다.
- `stickman_head_fill.py`는 해시 고정 기존 파일에서 해당 FS만 수정한다. 입력 덮어쓰기·없는/다중/다른 색 채움 추측 생성은 거부한다. 숨긴 부분 인물의 머리 채움을 새로 만들지 않는다. `--surface`로 근경 면 검사도 유지한다.
- 고정 리그의11객체 구조와 ID는 유지한다. 프로필 `serialization_revision=2`,채움 종류를 포함한 저장 형식 지문으로 갱신했다. 이전 지문이 색만 보고 Kind 누락을 놓친 허점을 보완했다. 새 장면마다 코드 수정하는 기능이 아니다.

재현 명령:

```bash
python tools/stickman_head_fill.py /비공개/surface_trial.sfa /비공개/head_fill_app_fixed_1032-1271.sfa \
  --scene scenes/nian41_1032-1271.json --width 1152 --crop-y 63 \
  --surface scenes/nian41_1032-1271_limb_surface_trial.json \
  --expect-input-sha256 <입력 파일 SHA256> --report /비공개/report.json
```

최신 면 포함 수정본 SHA-256: `6e820c62ff58c80fd9cf9dfce1116419a43c8c23ebe30f31e4bd37cb2ef93c4a`.
면 없는 직전 기본판도 같은 방법으로 수정해 비공개 캐시에 보존했다. 그 SHA는 `9d151351d277a65cca43c42c43890575bf8f8c3aa2cac25f0aca0d1bdb6ae9f4`이다. 사용자에게 제공하는 주 파일은 면 포함판이다.

## CPU·모바일 검증 범위

수정 전후 전240장의 모든 AO XML이 완전히 동일하다. 바뀐 FS만 되돌리면 전체 XML도 완전 일치한다. 수정은 재실행해도 추가 변경0건이다. 서버 렌더240장도 픽셀 전부 동일했고24fps·240장·10초 영상을 만들었다. 이 동일성은 관대한 서버 뷰어가 문제를 감췄다는 반례이며 앱 정상 증명으로 쓰지 않는다.

루트 Python 전체240개 시험이 통과했다(새4개). 새 시험은 뷰어 픽셀이 같아도 잘못된 Kind를 저장 검사에서 거부하는 반례,FS만 변경/다른 면 보존/멱등성,숨긴 머리와 모호한 채움 보호,파일 해시·입력 보호를 포함한다. 모바일 v1.1은 종류·점 소유·구간·윤곽을 검사하고 정상 원 채움과 불완전 채움을 구분한다. 별도 모바일 시험 결과/설치는 `docs/SFA-VIEWER-1.1-2026-11-03.md`를 따른다.

이전 “흰 머리 검사 통과”·“서버 렌더 정상” 기록은 그때의 제한된 검사 결과다. 실제 앱의 채움 호환성까지 검증했다는 뜻으로 재사용하지 않는다. 서버 Android 그래픽 시험과 실제 휴대폰 재열기를 구분한다. Kaggle은 사용자가 Claude 모니터링으로 위임한 별도 작업이므로 이번 수정으로 추가 실행/학습을 하지 않았다.
