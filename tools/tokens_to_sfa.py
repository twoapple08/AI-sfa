"""동작 토큰(모델 출력) → 캐릭터 시트를 입힌 스틱맨 .sfa (단계 6 연결부).

순서: 토큰 묶음들(처음 + 이어 만들기 조각들)을 이어 붙임 → motion_tokens.decode → 화면 밖으로 나간 골반 위치 보정(선택)
→ 몸 굵기(거리 굵기, 몸통 길이로) → motion_ir.compile_ir(sheets=CS.rig(캐릭터 시트 v3 read_all)) → .sfa
(11-05 사용자 '망토 레이어가 이상함': read_all만 넘기면 옛 칸 고르기 경로로 가서 망토가 흔들림·앞뒤 구분 없이 늘 몸 앞에 그려졌다 → rig로 넘긴다.)
사용: python tools/tokens_to_sfa.py <토큰 json(목록 또는 목록의 목록)> <캐릭터 시트.sfa> <출력.sfa> [--center] [--facing 도] [--retime]
몸 방향: 동작 토큰에는 방향이 없다(수집 SFA 9,347장 중 방향 자료 0) → 모르면 정면(망토는 몸 뒤). --facing으로 전체 방향을 손으로 준다
(0 정면, 90 우측면, 180 후면, 270 좌측면 — 캐릭터 시트 v3 고리 각도).
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


def build(tokens, sheet_path=None, center=False, name='generated', facing=None, retime=False):
    if tokens and isinstance(tokens[0], list):
        tokens = join(tokens)
    ir = MT.decode(tokens)
    if ir is None:
        raise ValueError('토큰을 동작으로 되돌릴 수 없다')
    return finalize(ir, sheet_path, center, name, facing, retime)


def finalize(ir, sheet_path=None, center=False, name='generated', facing=None, retime=False):
    """동작 자료(motion-ir) → (ir, .sfa 뿌리). build(토큰)와 compose(실제 동작 조각 잇기)가 같이 쓴다."""
    if retime:   # nian41 그림 유지 리듬 입히기(tools/retime.py, 11-06)
        import retime as RT
        ir = RT.retime(ir)
    a = ir['actors'][0]; J = a['joints']; N = ir['frames']
    if facing is not None: a['facing'] = [float(facing)] * N
    if center:   # 골반이 움직인 범위 전체의 가운데를 화면 (50, 60)으로 옮긴다
        # (11-06: 첫 장 골반만 가운데로 옮기면 화면 끝에서 시작한 동작이 뒤에서 화면 밖으로 밀려 — 단계 5 시트 17.7% 장이 화면 밖,
        #  모델 원래 좌표로는 0.2%)
        xs = [p[0] for p in J['pelvis']]; ys = [p[1] for p in J['pelvis']]
        dx, dy = 50 - (min(xs) + max(xs)) / 2, 60 - (min(ys) + max(ys)) / 2
        for k in J: J[k] = [[p[0] + dx, p[1] + dy] for p in J[k]]
    S = [math.hypot((J['neck'][n][0] - J['pelvis'][n][0]) * 11.52, (J['neck'][n][1] - J['pelvis'][n][1]) * 6.48) for n in range(N)]
    th, _ = distance_thickness(__import__('numpy').array(S), ((73.3, 1.0), (376.4, 5.0)))
    a['thickness'] = [{str(o): round(float(th[n]), 3) for o in range(1, 12)} for n in range(N)]
    for k in ('hidden', 'smear'):
        if not a.get(k) or len(a[k]) != N: a[k] = [[] for _ in range(N)]
    if not a.get('head_fill') or len(a['head_fill']) != N: a['head_fill'] = [True] * N
    if not a.get('facing') or len(a['facing']) != N: a['facing'] = [None] * N
    sheets = {0: CS.rig(CS.read_all(sheet_path))} if sheet_path else None
    return ir, M.compile_ir(ir, name=name, sheets=sheets)


if __name__ == '__main__':
    toks = json.load(open(sys.argv[1], encoding='utf-8'))
    fc = float(sys.argv[sys.argv.index('--facing') + 1]) if '--facing' in sys.argv else None
    rt = '--retime' in sys.argv
    ir, root = build(toks, sys.argv[2], center='--center' in sys.argv, facing=fc, retime=rt, name=os.path.splitext(os.path.basename(sys.argv[3]))[0])
    M.save_sfa(root, sys.argv[3], os.path.splitext(os.path.basename(sys.argv[3]))[0])
    print('장', ir['frames'], '→', sys.argv[3])
