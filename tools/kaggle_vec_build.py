"""Kaggle 노트북(영상 → SFA 딥러닝 학습)을 만든다 (2026-10-29). 출력: tools/kaggle_vec_train.ipynb"""
from kaggle_wan_eval_build import notebook

SETUP = """
**설정:**
1. **Settings → Accelerator → GPU T4 x2**
2. **Settings → Internet → On**
3. (선택) **Add-ons → Secrets**에 `RCLONE_CONFIG_GDRIVE_TOKEN`을 붙이면 결과가 Drive `AI-sfa/02_분석자료/vec/`로 올라간다. 없으면 Output 탭에서 `vec_out.zip`을 받는다.
"""

if __name__ == '__main__':
    notebook("""
# AI-sfa 영상 → SFA 딥러닝 학습 — Kaggle GPU

수집 SFA 361개(4711_2 합작 28개는 최종 시험용으로 뺌)를 그려서 영상으로 인코딩하고, 영상 장마다 '선 가운데·점 자리(선 끝)·선 방향·칠한 면'을 맞히게 학습한다.
**커리큘럼(사용자 10-29):** 1080 → 720 → 480 → 360 순서로 어려워진다. 단계마다 새 해상도 70% + 앞 단계 30%.
저장소(공개)에서 파일·도구를 직접 받으므로 따로 올릴 것은 없다.
""" + SETUP + """
**실행:** 오른쪽 위 **Save Version → Save & Run All (Commit)** — 브라우저를 닫아도 돈다.
예상: 자료 만들기 20–40분 + 짧은 시험 몇 분 + 본 학습 4시간 ≈ 5시간(추정).
결과 `vec_out.zip`: `best.pt`(최종 단계에서 검증이 가장 좋은 모델), `last.pt`, 단계별 `stage*.pt`, `log.jsonl`(손실 기록).
""", "tools/kaggle_vec_worker.py", "--hours 4", "tools/kaggle_vec_train.ipynb", "설치 → 저장소 받기 → 해상도별 자료 → 짧은 시험 → 본 학습 → zip")
