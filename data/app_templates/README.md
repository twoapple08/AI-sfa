# 앱 기본 제공 오브젝트 틀

- `stickman_default.sfa`: Stick Fighter가 기본으로 주는 스틱맨(사용자가 앱에서 새로 만들어 내보냄, 2026-11-02). 10조각(머리 원 + 몸통 + 팔 4 + 다리 4), 관절점 없음, 파란점은 골반 하나.
  `tools/pose_to_stickman.py`의 `BODY`가 이 구조(Flags·Index·연결)를 그대로 옮긴 것이고, `tests/test_pose_to_stickman.py`가 둘이 같은지 검사한다.
- 학습 목록(`data/user_sfa/index.csv`)에는 넣지 않는다.
