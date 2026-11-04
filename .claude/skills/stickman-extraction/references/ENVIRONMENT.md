# 환경과 복원

현재 CPU 환경 관측(2026-11-04): Python3.12, NumPy2.3.5, SciPy1.17.0, Pillow12.3.0, opencv-python-headless5.0.0.93, skia-python144.1, scikit-image0.26.0, torch2.15.0+cpu, torchvision0.29.2+cpu, requests2.34.2. 관측값이며 모든 버전 조합을 새 설치 검증한 lockfile은 아니다. Python3.11+ 권장(hashlib.file_digest).

복원/자료 검사는 Python 표준 라이브러리만 필요하다. 고정 SFA 재현은 NumPy/SciPy를 사용한다. 전체 CPU시험/원본 판독/렌더는 위 패키지가 사용된다. 새 포즈 모델/ONNX/전체 영상 추론이 필요하지 않은 고정 재현에 불필요한 모델 다운로드/GPU 설치를 하지 않는다. tools의 모든 선택 패키지를 일괄 설치하지 않는다.

저장소는 지정 브랜치 하나만 clone/fetch한다. 기존 캐시를 SHA로 확인해 재사용한다. private-data/working-cache/에는175파일(선택NPZ47,피팅NPZ54,JSON/분석코드 등)이 있다. 캐시 입력/코드가 맞는지 확인하고 맞지 않으면 억지 사용/해시 갱신하지 않는다.

원본: private-data/sources/video.mp4(1152×720,4216장,24fps)와 rtmw.jsonl.gz. 원본 전체는 휴대 묶음에서 제외하며 Drive manifest에서 별도로 받는다. 기본 고정 재현에는 필요하지 않다. 전처리/비율 판정은 원본 크기로 하며 crop은y63..711이다.

기존 환경변수는 RCLONE_GDRIVE_AUTH_B64/KAGGLE_USERNAME/KAGGLE_API_TOKEN 등이 있었다. 새 환경에 값이 주입됐다는 보장이 아니다. 값/토큰/키/서명키 출력 금지. 이 파일과 휴대 묶음에 자격증명은 없다. 앱 서명키·모델 가중치·원본 APK/역컴파일물도 휴대 묶음 대상이 아니다.

전체 시험: 저장소 루트에서 python -m unittest discover -s tests. 커밋 전 별도 종료코드0과OK를 확인한다. UI/앱 설치는 서버 CPU시험으로 대신했다고 말하지 않는다. CPU 재현은 새 비공개 폴더에서 tools/stickman_replay.py로 하고 replay_result.json의 XML 동치/결정11개를 확인한다.
