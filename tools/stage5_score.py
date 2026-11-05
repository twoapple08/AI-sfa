"""단계 5 끝 기준 ①(스타일 특징이 애니메이터 자료 분포 범위 안) 채점: 생성 동작 토큰 → motion_style 특징 → 기준 자료와 비교.
- 유지 리듬 분포(1·2·3·4+장) L1 거리, 예비 동작 비율 차이. 기준 = data/stage2/style_features_2026-11-05.json(nian41).
- 같은 계산을 기준 자료 자체 토큰(되돌린 것)에도 해서 '되돌림만으로 생기는 차이'를 기준선으로 함께 낸다.
사용: from stage5_score import style_score; style_score([토큰 목록, ...])
"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import motion_tokens as MT, motion_style as MS  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def style_score(token_lists, ref='nian41'):
    base = json.load(open(f'{ROOT}/data/stage2/style_features_2026-11-05.json', encoding='utf-8'))['aggregate'][ref]
    irs = [MT.decode(t) for t in token_lists]
    ms = [dict(file=str(i), **MS.measure(ir)) for i, ir in enumerate(irs) if ir is not None]
    if not ms:
        return dict(n=0)
    agg = MS.aggregate(ms)
    l1 = sum(abs(agg['hold_share'][k] - base['hold_share'][k]) for k in base['hold_share'])
    def rate(a): return a['anticipation']['with_antic'] / max(a['anticipation']['n'], 1)
    return dict(n=len(ms), hold_share=agg['hold_share'], hold_l1=round(l1, 3),
                anticipation=round(rate(agg), 3), anticipation_ref=round(rate(base), 3))
