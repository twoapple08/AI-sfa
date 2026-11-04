# 신규 참여자 인계 전달 기록 — 2026-11-04

인계 구현·문서·복원 도구 커밋: `3ec48fe77da6ad389ff430563d3a1d313644b5d8` (지정브랜치 push완료). 이후 이 문서/전달색인/SHA 기록만 추가하며 공통 생성코드·프로필·장면좌표는 바꾸지 않았다. 최신 배포 묶음의 소스 커밋과 파일 SHA는 아래 파일목록에 기록한다.

- [인계 폴더](https://drive.google.com/drive/folders/1UQ9rJ3H-VYc7l1kAqVDNjebe8b-2baKK)
- [신규 참여자용 문서·스킬·코드·최신 실행입력 휴대 묶음](https://drive.google.com/file/d/18AougwWq2h7sMc9DDaVL22rRzf4Gl6iN/view)
- [전체 파일목록·추가 개발자료3개·원본 연결·지문](https://drive.google.com/file/d/1LFAK6ck7Dfd8mkSPYcdBQyVRQn6oNOf-/view)
- [처음 참여자 안내](https://drive.google.com/file/d/1uBMTzLq2eW4WYvq_gJeLJuRzlHWGZ0mb/view)
- [이번 세션 전체 경과](https://drive.google.com/file/d/1uSITVyF7gQXUWVXa6f4ASBxO4U3Y_FKb/view)
- [Claude에게 보낼 프롬프트](https://drive.google.com/file/d/1G8kUpZoNDzrbpXDnTWh8Xwmr01PCR12K/view)

현재 로컬 스킬 private-data/에는13종 실제파일과 최신입력/캐시를 모았고 Git제외를 확인했다. 휴대 묶음은 코드/문서/스킬/최신판실행입력/캐시/이전재현/변환기근거/제보현황을 포함한다. 전체 개발자료를 복원하려면 기존3개자료ZIP을 추가로 내려받아 restore_data.py에 준다. 원본전체/RTMW는 별도 선택 Drive파일이다. 토큰·키·서명키·가중치·원본APK/역컴파일물은 미포함.

검증: 전체308시험OK·27.350초·exit0,새폴더13종 지문복원/필수9종ready,47선택/54피팅캐시 복원,새폴더11고정판단 재생성/XML일치,**휴대 묶음에서만 꺼낸 코드·입력으로도 최종XML일치**. 최신코드지문229개 검증. 휴대 묶음 내부 파일별지문과 ZIP CRC도 확인한다. 단순 폴더복사만 하고 재현 완료로 세지 않았다.

이검증은 보존중간입력→최종파일 범위다. 새원본눈판정자동생성/1440장전수눈승인/실제앱/새영상일반화/학습정답으로 확대하지 않는다. 기존24사례는같은영상/중첩개발자료(held_out=false/training_ready=false). 현재남은사용자스크린샷5개는원본보존,이전7첨부원파일부재는현황에표시했다. Kaggle추가조회/학습실행은하지않았다. 실제Claude설치/실행/담당이관을완료했다고말하지않는다.
