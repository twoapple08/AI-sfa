"""동작 토큰(모델 출력) → 캐릭터 시트를 입힌 스틱맨 .sfa (단계 6 연결부).

순서: 토큰 묶음들(처음 + 이어 만들기 조각들)을 이어 붙임 → motion_tokens.decode → 화면 밖으로 나간 골반 위치 보정(선택)
→ 몸 굵기(거리 굵기, 몸통 길이로) → motion_ir.compile_ir(sheets=캐릭터 시트 v3 read_all) → .sfa
사용: python tools/tokens_to_sfa.py <토큰 json(목록 또는 목록의 목록)> <캐릭터 시트.sfa> <출력.sfa> [--center]
"""
import json, math, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import motion_tokens as MT, motion_ir as M, char_sheet as CS  # noqa: E402
from stickman_clip import distance_thickness  # noqa: E402


def join(chunks):
    """조각 토큰을 하나로: 첫 조각은 그대로, 다음 조각은 <motion>…</motion> 껍질을 벗겨 잇는다(첫 키 간격 토큰이 앞 조각 마지막 키와의 간격)."""
    out = ['<motion>']
    for c in chunks:
        out += [t for t in c if t not in ('<motion>', '</motion>')]
    return out + ['</motion>']


def build(tokens, sheet_path=None, center=False, name='generated'):
    if tokens and isinstance(tokens[0], list):
        tokens = join(tokens)
    ir = MT.decode(tokens)
    if ir is None:
        raise ValueError('토큰을 동작으로 되돌릴 수 없다')
    a = ir['actors'][0]; J = a['joints']; N = ir['frames']
    if center:   # 첫 장 골반을 화면 가운데 아래쪽(50, 70)으로 옮긴다
        dx, dy = 50 - J['pelvis'][0][0], 70 - J['pelvis'][0][1]
        for k in J: J[k] = [[p[0] + dx, p[1] + dy] for p in J[k]]
    S = [math.hypot((J['neck'][n][0] - J['pelvis'][n][0]) * 11.52, (J['neck'][n][1] - J['pelvis'][n][1]) * 6.48) for n in range(N)]
    th, _ = distance_thickness(__import__('numpy').array(S), ((73.3, 1.0), (376.4, 5.0)))
    a['thickness'] = [{str(o): round(float(th[n]), 3) for o in range(1, 12)} for n in range(N)]
    sheets = {0: CS.read_all(sheet_path)} if sheet_path else None
    return ir, M.compile_ir(ir, name=name, sheets=sheets)


if __name__ == '__main__':
    toks = json.load(open(sys.argv[1], encoding='utf-8'))
    ir, root = build(toks, sys.argv[2], center='--center' in sys.argv, name=os.path.splitext(os.path.basename(sys.argv[3]))[0])
    M.save_sfa(root, sys.argv[3], os.path.splitext(os.path.basename(sys.argv[3]))[0])
    print('장', ir['frames'], '→', sys.argv[3])
