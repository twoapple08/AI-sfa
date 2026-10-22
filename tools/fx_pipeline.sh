#!/bin/bash
# 이펙트 분리(Kaggle v3) 결과가 모이면 한 번에: 받기 → 시간 변화 → 층 형태 사전 → 생성 → 비교 → 대표 장면 이펙트만 SFA → Drive 올리기.
# 시험: NO_UPLOAD=1 이면 Drive 올리기·저장소 복사를 하지 않는다.
# 사용: bash tools/fx_pipeline.sh <작업 폴더> <나카무라 영상 폴더> <effects.txt 폴더(effects.txt·palette.txt)>
# 결과(원본 유래 마스크·형태·SFA)는 작업 폴더와 Drive에만 둔다. 집계 수치(json)만 저장소 data/p3/에 복사한다.
set -u
W=${1:?작업 폴더}; V=${2:?영상 폴더}; FX=${3:?effects 폴더}
cd "$(dirname "$0")/.." || exit 1
mkdir -p "$W/masks" "$W/out"
rclone copy "gdrive:AI-sfa/02_분석자료/이펙트_분리" "$W/masks" --include "*_v3.npz" 2>/dev/null
echo "마스크 $(ls "$W"/masks/*_v3.npz | wc -l)개"
rclone copy "gdrive:AI-sfa/02_분석자료/이펙트_분리" "$W/masks" --include "*_ink.npz" 2>/dev/null  # 임팩트(서버 처리)
python3 tools/fx_timing.py "$W/masks" "$V" data/p3/fx_segments_2026-10-22.csv "$W/out/fx_timing.json" > "$W/out/fx_timing.log" 2>&1
python3 tools/fx_timing.py "$W/masks" "$V" data/p3/fx_segments_impact_2026-10-22.csv "$W/out/fx_timing_impact.json" > "$W/out/fx_timing_impact.log" 2>&1
python3 - "$W" <<'PY'
import csv, sys  # 두 구간 목록을 합쳐 형태 사전을 한 번에 뽑는다
w = sys.argv[1]
rows = [r for f in ("data/p3/fx_segments_2026-10-22.csv", "data/p3/fx_segments_impact_2026-10-22.csv") for r in csv.DictReader(open(f, encoding="utf-8"))]
with open(f"{w}/out/segments_all.csv", "w", newline="", encoding="utf-8") as fh:
    d = csv.DictWriter(fh, fieldnames=["post_id", "start", "end", "tags", "exclude"]); d.writeheader(); d.writerows(rows)
PY
[ -n "${NO_UPLOAD:-}" ] || cp "$W/out/fx_timing.json" "data/p3/fx_timing_$(date +%F).json"
[ -n "${NO_UPLOAD:-}" ] || cp "$W/out/fx_timing_impact.json" "data/p3/fx_timing_impact_$(date +%F).json"
python3 tools/fx_shapes.py "$W/masks" "$V" "$W/out/segments_all.csv" "$W/out/fx_shapes.txt" 2>&1 | tail -1
python3 tools/fx_shape_sheets.py "$W/out/fx_shapes.txt" "$W/sheets"  # 형태 판정 시트(GPT: docs/GPT-PROMPT-FX-SHAPES-2026-10-22.md)
[ -n "${NO_UPLOAD:-}" ] || rclone copy "$W/sheets" "gdrive:AI-sfa/02_분석자료/이펙트_형태시트" 2>/dev/null
rclone copy "gdrive:AI-sfa/02_분석자료/이펙트_형태사전" "$W/out" --include "impact_books.txt" 2>/dev/null  # 임팩트 프레임 v2(fx_impact_book.py)
BOOKS=$([ -s "$W/out/impact_books.txt" ] && echo "$W/out/impact_books.txt")
APPROVED=$(ls data/style_kb/ai_results/gpt_FXS_*.csv 2>/dev/null | tail -1)  # 판정이 있으면 '맞음'만 쓴다
for k in explosion smoke debris impact impact_frame; do
  python3 tools/fx_gen.py "$FX/effects.txt" "$FX/palette.txt" "$W/out/gen_$k.sfa" --kind "$k" --seed 1 \
    --shapes "$W/out/fx_shapes.txt" ${APPROVED:+--approved "$APPROVED"} ${BOOKS:+--impact-books "$BOOKS"} --check "$W/out/gen_$k.jpg" > /dev/null 2>&1
  python3 tools/fx_compare.py "$W/out/gen_$k.sfa" "$W/out/cmp_$k.json" --real "$W/out/fx_timing.json" \
    --type "$(case $k in impact) echo explosion;; impact_frame) echo impact_silhouette;; *) echo "$k";; esac)" \
    --real-impact "$W/out/fx_timing_impact.json" > "$W/out/cmp_$k.txt" 2>&1
done
[ -n "${NO_UPLOAD:-}" ] || rclone copy "$W/out" "gdrive:AI-sfa/04_SFA시험작/이펙트_생성/파이프라인_$(date +%m%d_%H%M)" 2>/dev/null
echo "끝: $W/out (Drive 04_SFA시험작/이펙트_생성/파이프라인_*)"
