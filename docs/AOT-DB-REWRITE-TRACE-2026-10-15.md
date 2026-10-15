# DB 재작성의 교체 조건과 실패 경로 — 2026-10-15

기존 AOT/ELF에서 `DataAccess.RewriteCompactly`(0x4f8914)와 closure·release 경로를 확인했다. 실제 DB 재작성이나 File-2 최적화를 실행한 것이 아니다. [ROOT-REBASE-IDLE](AOT-ROOT-REBASE-IDLE-TRACE-2026-10-15.md)의 ‘재작성 필요’ 판정 뒤 실제 작업을 잇는다.

## 복사본 작성과 검사

공유 DB·저장 경로가 있고 transaction depth≤0이어야 시작한다. 임시 경로는 원래 경로에 `.compact`를 붙인다. 원본 DB의 totalChanges와 `PRAGMA data_version`을 기록한 후 이전 임시 파일과 그 `-journal`을 정리한다. 정리 helper는 각 파일 삭제 실패를 처리하고 나머지를 계속한다.

별도 isolate closure 0x4f91a8은 원본을 **readOnly OpenMode**로 열고 `page_size=4096`, `auto_vacuum=INCREMENTAL` 설정 뒤 `VACUUM INTO`로 임시 경로를 생성한다. readOnly라는 해석은 enum 메타데이터의 ordinal0·이름과 대조했다. 원본 연결을 닫고 복사본을 열어 `PRAGMA quick_check`의 **첫 행 첫 값**이 `ok`인지 검사한다. 다르면 StateError를 던진다. DB 내용 전체의 의미 동등성이나 모든 검사 행을 별도로 대조하는 코드는 아니다. 정상/예외 경로의 연결 close가 구분돼 있다.

## await 뒤 재검사

isolate 완료 뒤 다음 조건이 모두 유지되어야 교체를 진행한다.

- 현재 공유 DB identity가 처음 DB와 같다.
- transaction depth≤0이다.
- 원본 totalChanges와 data_version이 각각 처음 값과 같다.
- 전달한 main-menu 상태가 여전히 idle이다.

하나라도 실패하면 임시 파일 정리 helper를 호출하고 false를 반환한다. 따라서 복사 시작 후 수정이 생긴 원본을 그냥 덮어쓰는 정상 경로는 아니다. 이것이 임의 외부 프로세스와의 모든 경쟁을 원자적으로 막는다는 보장은 별개다.

## release와 파일 교체

`release`(0x4f9050)는 공유 DB 포인터를 null로 바꾼 뒤 WAL FULL checkpoint를 시도하고 DB를 닫는다. transaction depth·상태와 성공 stack도 초기화한다. checkpoint 예외를 처리해도 close 쪽으로 이어지는 경로가 있다. 이 호출 뒤 원래 경로의 `-wal` 존재 여부와 길이를 검사한다.

WAL이 있고 길이가0보다 크면 임시 파일을 정리하고 원래 DB를 다시 열어 false를 반환한다. WAL이 없거나 비었으면 원래 `-wal`, `-shm`을 삭제 시도하고, 임시 `.compact`를 원래 경로로 renameSync한 뒤 공유 DB를 다시 열어 true를 반환한다. sidecar 삭제 실패 처리와 rename 실패 처리를 같은 성공으로 해석하지 않는다.

확인한 외부 실패 handler는 임시 파일 정리 후 false를 반환한다. 이 handler 몸체에는 모든 실패 위치에서 `_openShared`를 즉시 재호출하는 공통 복구 루프가 없다. 반면 WAL 잔존 중단과 정상 rename 뒤에는 명시적인 reopen이 있다. 이 차이만으로 데이터 손실이나 앱 복구 불가를 단정하지 않는다. 이후 `_requireDatabase` 동작, OS rename·전원 중단·파일 시스템 오류의 실제 결과까지 완전히 검증한 것은 아니다. 별도 backup-rename/fsync 복구 프로토콜도 이 몸체에서 확인되지 않았다.

## 근거·한계

중심 주소는 0x4f8a0c/18(변경값 기록), 0x4f8a58/64(isolate/await), 0x4f8a74–e0(재검사), 0x4f8b08(release), 0x4f8ba4/bb0(WAL), 0x4f8dc4(sidecar 삭제), 0x4f8e3c/44(rename/reopen), 0x4f927c(VACUUM), 0x4f92a8/9308(quick_check), 0x4f93e8(임시 정리)다. 공개 역컴파일 코드/원본 DB는 첨부하지 않았다.

[선택 명령 감사](AOT-DB-REWRITE-AUDIT-2026-10-15.json)는 원본 ELF/Capstone 대조이며 전체 의미·실제 파일 I/O·crash 복구 보장은 아니다. 다른 보고서 표본과 독립 누적 합산하지 않는다. 새 설치·페어링·폰 시험·기존 영상 분석·unit/probe 재실행은 하지 않았다. 프레임 compaction 내부 단계는 이 DB 파일 재작성과 별도의 미완 범위다.
