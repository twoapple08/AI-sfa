# root 재기반 조건과 idle 압축 호출 — 2026-10-15

- 기존 AOT/ELF의 `_rebaseOnRoot`, `_holdsRootExactly`, main menu 압축 진입을 분석했다.
- `File-2` 재압축을 실행한 것이 아니며 원본 파일은 수정하지 않았다.
- compaction 내부의 모든 단계·예외·수명 보장은 아직 미완이다.

## 재기반 guard

`_rebaseOnRoot`(0x36a3f0)의 입력을 대상 frame F, 후보 root R, 대상 첫 점 ID B, 점수 N으로 적는다. 대상 범위 끝은 `B+N−1`이다.

1. N>0이고 F에 기존 frame_base가 없어야 한다.
2. 대상 점 ID 범위에 F 이외 frame의 점이 없어야 한다. 다른 frame_base의 가상 점 범위와 겹쳐도 실패한다.
3. R의 frame_root 행이 있고 root point_count≥N이어야 한다.
4. 대상 점을 `rootID = rootFirst − (framePointID−B)`로 연결했을 때, 같은 AO ID·index_number인 점의 SQL count가 정확히 N이어야 한다.
5. `_holdsRootExactly`(0x36a920)의 점·연결·상세 검사를 통과해야 실제 삭제와 frame_base 삽입을 한다.

첫 점끼리 단순 더하기나 좌표 근사만 비교하는 검사가 아니다. root의 실제 점 ID가 감소하는 표현과 대상의 증가하는 가상 ID를 구분한다.

## ‘같다’의 실제 범위

| 검사 | 확인한 조건 |
|---|---|
| 점 | 위 ID 대응과 AO ID, SQL `IS`로 index/x/y/selectable/anchor type 비교. Flags는 root 그룹 참조를 대상 B 기준으로 복원한 값과 일치해야 함. 비그룹 root flags는 `&0x2f`. 일치 count=N. |
| 연결 | 대상 범위의 outgoing 수 = 중복 제거 쌍 수 = 양 끝이 범위 안이며 root 대응 연결과 일치한 수 = root 해당 범위 outgoing 수. 중복/바깥 연결을 단순히 버리고 통과시키는 비교가 아님. |
| 상세 | root 상세마다 F의 같은 AO 상세가 정확히 1행이면 색·ThicknessScale·ObjectScale·glow4값을 SQL `IS`로 비교. F에 0행이면 root 값이 기본값일 때만 동등. 2행 이상이면 실패. 동등 root 상세 수가 root 상세 수와 같아야 함. |

- 이때 상세 기본값은 ARGB−16777216, ThicknessScale1, ObjectScale1, GlowRadius0, GlowColor−1, GlowAlpha255, GlowThickness20이다.
- root에 없는 대상 상세를 전부 제거하는 검사는 아니며, 이후 삭제도 root에 같은 AO 상세가 있는 대상 행만 처리한다.
- DrawOrder·LayerId·fill·배경색까지 이 SQL 하나가 모두 비교한다고 확대하지 않는다.

- 통과하면 대상 ID 범위의 outgoing 연결→점 행을 삭제하고, root에 대응 행이 있는 대상 상세를 삭제한 뒤 `(F,R,B,N)` frame_base를 삽입하여 true를 반환한다.
- 실패 guard는 false다.
- incoming 연결을 전부 다시 쓰는 루프나 이 함수 안의 별도 transaction 시작은 확인한 몸체에 없다.
- 이 사실만으로 외부 참조 안전성·전체 caller의 transaction 계약을 생략해서는 안 된다.

## idle 압축과 DB 재작성은 별도

- main menu `_compactStorageWhileIdle`(0x4f8574)은 재작성 중 플래그가 꺼져 있고 `_isIdleOnMainMenu`가 참일 때 진행한다.
- 원본 frame 압축 단계는 stopwatch 경과가 6ms 미만인 동안 `CompactStoredFrames`를 반복한다.
- **단계 시작 전** 검사이므로 개별 DB 단계까지 6ms 안에 끝난다는 보장은 아니다.
- 단계가 더 없다는 결과가 오면 해당 단계 완료 플래그를 켜고 반환한다.
- 이후 호출의 별도 경로에서 DB 재작성 필요성을 판정한다.

- `CompactStoredFrames`(0x4f9950)는 현재 DB identity와 같은 `_Compaction` 상태를 재사용하며 다르면 새 상태를 만든다.
- frame scope−1 안의 closure가 transaction→`_compactionStep`→commit→실패수 0→finish로 연결된다.
- 확인한 처리 대상 예외 분기는 실패수 증가·진행 job 해제·cursor 증가 후 실패수≤3을 반환하며, 실패수>3이면 이후 진입에서 false다.
- 모든 예외가 삼켜진다는 뜻은 아니다.
- 별도 finish→rethrow 경로도 있다.

- `ShouldRewriteCompactly`(0x4f965c)는 DB가 없거나 transaction depth>0이면 false다.
- 이 guard를 통과하면 page_size<4096 또는 auto_vacuum!=2이면 true다.
- 그 외에는 `freelist_count * page_size >= 8MiB` **그리고** `4*freelist_count >= page_count`일 때 true다.
- boxed Smi의 값 4는 auto_vacuum의 정수 2로 읽었다.

- main menu는 필요하면 idle 여부 callback을 전달해 `RewriteCompactly`를 시작하고 whenComplete를 등록한다.
- 그 후 free room 반환/타이머 종료 경로는 따로 있다.
- 실제 Rewrite 내부 임시파일·rename·실패복구 전체는 이 보고서에서 완료로 세지 않는다.

## 근거와 제한

- `data_access.dart` 위 함수와 `main.dart`의 좁은 주소창을 읽었다.
- [선택 명령 감사](AOT-ROOT-REBASE-IDLE-AUDIT-2026-10-15.json)는 원본 ELF/Capstone 일치만 뜻하며 SQL 실행·실제 저장 결과·전체 의미 증명은 아니다.
- 다른 보고서와 표본수를 독립 누적 합산하지 않는다.
- 신규 설치·페어링·실물 시험·기존 영상/SFA 재분석·unit/probe 재실행 없이 작성했다.
