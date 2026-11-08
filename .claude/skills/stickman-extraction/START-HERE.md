# 여기서 시작

이 폴더는 **코드·규칙·사례·실제 비공개 자료를 찾는 입구**다. 전체 프로젝트 목적부터는 저장소 `docs/NEW-COLLABORATOR-ONBOARDING-2026-11-04.md`를 읽는다. 신규자도 목적/구조/규칙/현재 기준/실행/실패/남은 일을 순서대로 따라갈 수 있다.

|위치|역할|
|---|---|
|`SKILL.md`|현재 처리 절차/규칙. 과거 상충 지시를 최신 결론으로 정리|
|`references/PROJECT-OVERVIEW.md`|프로젝트 전체와 두 부품의 관계|
|`references/CURRENT-STATE.md`|최신 결과/검증/미완/바로 할 일|
|`references/SESSION-LEDGER.md`|이번 세션 전체 경과와 상세 변경 로그|
|`references/DECISIONS-AND-LIMITS.md`|유효 사용자 결정/금지/미채택/일반화 한계|
|`references/SMEAR-PIPELINE.md`|스틱맨 다음 단계: 스미어 탐지·배치·모양·검사·영상 절차와 입력 위치(11-08)|
|`references/ENVIRONMENT.md`|의존성과 환경 복원|
|`data/artifact_manifest.json`|13종 파일의 정확 Drive ID/크기/SHA/역할/필수 여부|
|`data/archive_inventory.json`|중첩 ZIP 포함752개 파일 항목 지문 색인|
|`data/generalization_cases.json`|원본 색인3개를 출처와 함께 합친24개 개발사례|
|`scripts/restore_data.py`|내용 지문으로 자료 복원/검사/안전 추출|
|`private-data/`|실제자료. Git 제외, Drive에 보존|

현재 환경 private-data/에는3개 단계별 개발자료 ZIP,최신 SFA/재현/증거,이전 재현,관측·피팅캐시,변환기 출제감사·실행근거,원본 영상/RTMW를 모았다. latest/inputs/와 working-cache/에는 각각 최신 고정판단/47선택+54피팅 캐시를 풀어 두었다. 원본/좌표/앱자료/결과물을 Git에 강제로 추가하지 않는다. 다른 환경에는 휴대 묶음+Drive manifest로 복원한다.

Drive 인계 폴더: https://drive.google.com/drive/folders/1UQ9rJ3H-VYc7l1kAqVDNjebe8b-2baKK

휴대 묶음은 작은 문서/실행입력 묶음과3개 기존 개발자료 ZIP으로 나뉜다. 기존 ZIP 링크를 재사용해 대용량 중복 업로드를 피했다. 폴더의 인수인계_파일목록.json을 참고해 내려받은 뒤 다음을 실행한다.

```bash
python .claude/skills/stickman-extraction/scripts/restore_data.py --import-path /내려받은폴더
python .claude/skills/stickman-extraction/scripts/restore_data.py
python tools/stickman_replay.py .claude/skills/stickman-extraction/private-data/latest/replay.zip --destination /비공개/새_재현폴더
```

필수9종이 빠지면 복원 검사 exit2와 필요한 Drive ID가 나온다. 원본 전체 영상/RTMW와 이전2종 재현은 선택 항목이며 최신 고정 재현에 필수가 아니다. 자료/코드 해시 불일치나 사용자 눈 판정 대기를 완료로 바꾸지 않는다. Claude가 이 스킬을 발견하려면 지정 브랜치 저장소가 있어야 하며 외부 Claude 계정에 자동 장착되는 방식은 아니다.

최종전달물/검증기록은 docs/HANDOFF-DELIVERY-2026-11-04.md와data/handoff_delivery.json. 휴대묶음에서만꺼낸코드/입력의실제재생성도XML일치를확인했다.
