# 현재 클립의 일반화 개선용 자료 보존 — 2026-11-04

[일반화 개선용 개발 사례 묶음](https://drive.google.com/file/d/1SaU05lYnojutccID8aQyC3obx1_L9ZFD/view)(약16.57MB)에 현재432–1871/60초 클립의 자료와9종 사례 색인을 보존했다. [순수 데이터 보존본](https://drive.google.com/file/d/1LkJb49DTWzuNRfrMAyYgWTFHvLMAEhrr/view)은 같은 최신결과/재현자료의17파일·약16.56MB다. 원본 영상/전체RTMW는 기존Drive 경로와SHA로 연결하고 중복 업로드하지 않았다. 키/토큰/가중치는 없다.

보존 내용: 최신 SFA/비교영상/원본 크기 시트,고정 입력·선택 관측·피팅/실험 이력,수동 표시 키·보간 포즈·가림/부분 가시성·기존 접촉/회피·폭 추론·면 연결,전체292시험과 독립폴더XML일치 증거. 과거 미채택 손/발 부속/상세면 결과는 이력이며 최신 결과로 쓰지 않는다. ZIP무결성/파일SHA대조 완료.

공개 색인은 `data/stickman_motion/generalization_cases/nian41_clip432-1871_2026-11-04.json`이다. 좌표 전체/원본/상세 자료는 Drive에만 있다.9사례는 부분 종아리 누락,축소팔/앞팔,양팔 중복,직선 스미어 차기,전경 가림 구겨짐,손 확대 전신오인,혼합 근경 부위,멀어질 때 폭 증가,회피를 접촉으로 오판한 사건이다. 증상·공통 원인·처리·수동 입력·사용자 판정·한계를 구분했다.

이 자료의 용도는 **일반화 개선을 위한 개발 사례/회귀 자료**다. 이미 수정에 사용한 클립이므로 `development_known_clip`,held_out=false,training_ready=false로 고정했다. 수동 보정·숨은 추론을 자동 추출 정답으로 세지 않는다. 일부 사용자 긍정을 전체 클립 합격으로 확대하지 않는다. 새 영상에 공통 규칙만 적용한 결과는 별도의 미사용 자료로 저장/판정해야 한다.

기존 구간 재현은 지정코드 dea13677bb36e45d6e5aaf6df0914e3db5286d6e와 필수 재현묶음16HzUYldzaihjFrbVajCM4iMEEDFas3Y9,stickman_replay.py를 따른다. 이번 보존은 새 학습/GPU 실행이나 모델이 사례를 학습했다는 뜻이 아니다.
