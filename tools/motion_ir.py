"""움직임 중간 표현 v1(재계획 단계 1, docs/REPLAN-PLAN-DRAFT-2026-11-05.md).

생성기는 SFA 점 좌표를 직접 쓰지 않고 이 중간 표현(장마다 인물 관절 12개 + 가시성 + 굵기 + 카메라)을 만든다.
.sfa는 컴파일러가 만든다(고정 뼈대 profiles/stickman_2d_v1.json, 기존 stickman_clip.person_aos 재사용).

형식(JSON, schema "motion-ir/1"):
  fps [24,24], aspect 0.5625, frames N
  actors[]: slot, color('blue'|'red'|ARGB 정수), joints{이름: [[x,y] | null]*N}(화면 %), thickness[N] = {객체 번호: 굵기},
            hidden[N] = 그 장에서 안 그리는 객체 번호 목록(가림·화면 밖), smear[N] = '스미어로 대체' 객체 번호 목록
            (그리지 않음, 나중 스미어 단계 입력 — 사용자 11-05), head_fill[N] bool,
            facing[N] = 몸이 향한 방향(도, 0 정면 · 90 캐릭터 오른쪽이 화면 앞으로 돌아선 측면(=시트 '우측') · 180 후면 · 270 '좌측'), 모르면 null
            (가면 등 방향 있는 액세서리의 시트 칸 선택용 — 사용자 11-05 "가면이 정면만 봄")
  camera[N]: [dx, dy, zoom] (v1은 기록만, 컴파일에 쓰지 않음)
  timeline[]: {start, end, text, tags[]} (태그·시간 구간 설명 자리)
관절 이름: head_t head_b neck pelvis elb_r wri_r elb_l wri_l kne_r ank_r kne_l ank_l

사용: python tools/motion_ir.py extract 입력.sfa 출력.json
      python tools/motion_ir.py compile 입력.json 출력.sfa
      python tools/motion_ir.py roundtrip 입력.sfa   (추출 → 컴파일 → 기본 11객체 대조)
"""
import copy, json, sys, zipfile, xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pose_to_stickman import BODY  # noqa: E402

AO0, PT0 = 4560000, 5680000
JOINTS = ['head_t', 'head_b', 'neck', 'pelvis', 'elb_r', 'wri_r', 'elb_l', 'wri_l', 'kne_r', 'ank_r', 'kne_l', 'ank_l']
LINE_COLOR = {'blue': -16776961, 'red': -65536}
COLOR_NAME = {v: k for k, v in LINE_COLOR.items()}


def pid_names(moving_head):
    """객체 번호 → [(점 번호, 관절 이름)] (stickman_clip.person_aos와 같은 규칙)."""
    m = {}
    for oid, _typ, pts in BODY:
        m[oid] = [(pid, name) for pid, name, _fl, _ac in pts]
    if moving_head:
        m[1] = [(1, 'head_t'), (2, 'head_b')]
        m[11] = [(21, 'neck'), (22, 'head_b')]
    return m


def load(path):
    z = zipfile.ZipFile(path)
    return ET.fromstring(z.read([n for n in z.namelist() if n.endswith('.xml')][0]))


def extract(root):
    frames = root.findall('Frame')
    N = len(frames)
    slots = sorted({(int(a.get('ID')) - AO0) // 100 for f in frames for a in f.findall('AO') if 0 <= int(a.get('ID')) - AO0 < 1000})
    actors = []
    for slot in slots:
        J = {k: [None] * N for k in JOINTS}
        th, hid, fill, color = [None] * N, [[] for _ in range(N)], [False] * N, None
        for n, f in enumerate(frames):
            aos = {int(a.get('ID')) - AO0 - slot * 100: a for a in f.findall('AO') if 0 < int(a.get('ID')) - AO0 - slot * 100 <= 11}
            if not aos: continue
            moving = 11 in aos
            names = pid_names(moving)
            base = PT0 + n * 1000 + slot * 100
            for oid, a in aos.items():
                for p in a.findall('AP'):
                    nm = dict(names.get(oid, [])).get(int(p.get('ID')) - base)
                    if nm and J[nm][n] is None:
                        J[nm][n] = [float(p.get('X')), float(p.get('Y'))]
                c = int(a.get('Color'))
                if oid != 11:
                    if c == 0: hid[n].append(oid)
                    elif color is None: color = COLOR_NAME.get(c, c)
                th[n] = th[n] or {}
                th[n][str(oid)] = float(a.get('ThicknessScale'))   # 객체마다(한 장 안에서도 부위별로 다를 수 있음)
            fill[n] = any(x.find('FS') is not None and x.find('FS').get('ObjId') == str(AO0 + slot * 100 + 1) for x in f.findall('FR'))
        actors.append(dict(slot=slot, color=color, joints=J, thickness=th, hidden=hid, smear=[[] for _ in range(N)], head_fill=fill,
                           facing=[None] * N))   # 스틱맨 SFA에는 방향 정보가 없다 — 포즈 자료 등에서 따로 채운다
    return dict(schema='motion-ir/1', fps=[24, 24], aspect=float(root.get('HeightWidthRatio', 0.5625)), frames=N,
                actors=actors, camera=[[0.0, 0.0, 1.0] for _ in range(N)], timeline=[])


def hold_drawings(ir):
    """원본 그림 구간(actor['drawings'])마다 가운데 장의 관절·굵기·방향을 그 구간 모든 장에 복사한 새 중간 표현(끊어 보여 주기 판).
    기본 추출은 키포즈 사이를 PCHIP으로 이어 24장 모두 움직인다(부드러운 판). 사용자 판정용 비교(11-05):
    애니메이터 유지 리듬(2s·3s)을 그대로 보여 줄지 정하려고 같은 자료로 두 판을 만든다. 구간 밖 장·가운데 장이 빈 구간은 그대로 둔다."""
    import copy
    out = copy.deepcopy(ir)
    for a in out['actors']:
        for s, e in a.get('drawings') or []:
            m = (s + e) // 2
            if not (0 <= s <= e < out['frames']) or a['joints']['neck'][m] is None:
                continue
            for n in range(s, e + 1):
                for k in a['joints']:
                    a['joints'][k][n] = copy.copy(a['joints'][k][m])
                a['thickness'][n] = dict(a['thickness'][m])
                if a.get('facing'):
                    a['facing'][n] = a['facing'][m]
    return out


DESPIKE = dict(min_jump=0.6, back=0.3, cos=-0.7)   # 몸통 단위


def despike(ir, min_jump=None, back=None, cos=None):
    """한 장만 튀었다가 바로 돌아오는 끝점(팔꿈치·손목·무릎·발목, 골반 기준)을 앞뒤 장 평균으로 바꾼 새 중간 표현과 바꾼 목록.
    조건: n-1→n, n→n+1 이동이 모두 몸통 min_jump 이상, 방향이 반대(코사인 < cos), 거의 원래 자리로 돌아옴(|합| < back × |n-1→n|).
    11-05 사용자 '갑자기 파밧 하고 튀는 모션'. 기준은 승인 10초판에서 바뀌는 장이 거의 없게 잡는다(진짜 빠른 타격 보존)."""
    import copy
    min_jump = DESPIKE['min_jump'] if min_jump is None else min_jump
    back = DESPIKE['back'] if back is None else back
    cos = DESPIKE['cos'] if cos is None else cos
    out = copy.deepcopy(ir); fixed = []
    asp = ir.get('aspect', 0.5625)
    for a in out['actors']:
        J = a['joints']; N = len(J['neck'])
        P = lambda k, i: None if J[k][i] is None or J['pelvis'][i] is None else (J[k][i][0] - J['pelvis'][i][0], (J[k][i][1] - J['pelvis'][i][1]) * asp)
        tor = [((J['neck'][i][0] - J['pelvis'][i][0]) ** 2 + ((J['neck'][i][1] - J['pelvis'][i][1]) * asp) ** 2) ** 0.5
               for i in range(N) if J['neck'][i] is not None and J['pelvis'][i] is not None]
        if not tor: continue
        T = sorted(tor)[len(tor) // 2]
        for k in ('elb_r', 'wri_r', 'elb_l', 'wri_l', 'kne_r', 'ank_r', 'kne_l', 'ank_l'):
            for n in range(1, N - 1):
                p0, p1, p2 = P(k, n - 1), P(k, n), P(k, n + 1)
                if None in (p0, p1, p2): continue
                d1 = (p1[0] - p0[0], p1[1] - p0[1]); d2 = (p2[0] - p1[0], p2[1] - p1[1])
                m1 = (d1[0] ** 2 + d1[1] ** 2) ** 0.5; m2 = (d2[0] ** 2 + d2[1] ** 2) ** 0.5
                if m1 < min_jump * T or m2 < min_jump * T: continue
                if (d1[0] * d2[0] + d1[1] * d2[1]) / (m1 * m2) >= cos: continue
                if ((d1[0] + d2[0]) ** 2 + (d1[1] + d2[1]) ** 2) ** 0.5 >= back * m1: continue
                q0, q2, pv = J[k][n - 1], J[k][n + 1], J['pelvis']
                J[k][n] = [pv[n][0] + ((q0[0] - pv[n - 1][0]) + (q2[0] - pv[n + 1][0])) / 2,
                           pv[n][1] + ((q0[1] - pv[n - 1][1]) + (q2[1] - pv[n + 1][1])) / 2]
                fixed.append((a.get('slot'), n, k))
    return out, fixed


BRIDGE = dict(max_gap=3, rel=0.8, abs_max=3.0, dev=0.6)   # 기본 경로 미적용(11-05): n41_23 가림 21–24장은 잡지만 n41_12에서 틀린 앞뒤 장을 이어 악화. 30구간 212/1183장 변경
BRIDGE_CHAIN = {'elb_r': ('wri_r',), 'elb_l': ('wri_l',), 'kne_r': ('ank_r',), 'kne_l': ('ank_l',)}


def _off_line(J, k, i, j, asp, T):
    """낮은 점수 장 i..j-1의 관절(골반 기준)이 앞(i-1)·뒤(j) 장을 이은 직선 보간에서 가장 많이 벗어난 거리(몸통 단위)."""
    P = lambda n: None if J[k][n] is None or J['pelvis'][n] is None else (J[k][n][0] - J['pelvis'][n][0], (J[k][n][1] - J['pelvis'][n][1]) * asp)
    p0, p1 = P(i - 1), P(j)
    if None in (p0, p1): return 0.0
    m = 0.0
    for n in range(i, j):
        q = P(n)
        if q is None: continue
        t = (n - i + 1) / (j - i + 1)
        m = max(m, ((q[0] - p0[0] - (p1[0] - p0[0]) * t) ** 2 + (q[1] - p0[1] - (p1[1] - p0[1]) * t) ** 2) ** 0.5 / T)
    return m


def bridge_occlusions(ir, scores, max_gap=None, rel=None, abs_max=None, dev=None):
    """짧게 가려진 팔다리(파편·이펙트가 지나가 점수가 확 떨어진 1–max_gap장)를 앞뒤 정상 장 사이 직선으로 잇는다(골반 기준).
    낮음 = 점수 < rel × 그 관절의 구간 점수 중앙값 이고 < abs_max. 부모(팔꿈치·무릎)를 이으면 자식(손목·발목)도 잇는다.
    11-05 사용자 n41_23 '감속 효과 중 갑자기 다리가 파박 튐': 22–24장 날아가는 판자가 다리를 가려 무릎 점수 3.5→2.0–2.5.
    10초판 장면 데이터의 '전후 관측으로 키 좌표 보완'을 점수로 자동화한 것(원본 판독 아님). scores = {slot: {관절: [점수|None]}}.
    반환: 새 중간 표현, 이은 (인물, 장, 관절) 목록."""
    import copy
    c = dict(BRIDGE, **{k: v for k, v in dict(max_gap=max_gap, rel=rel, abs_max=abs_max, dev=dev).items() if v is not None})
    out = copy.deepcopy(ir); done = []; asp = ir.get('aspect', 0.5625)
    for a in out['actors']:
        J = a['joints']; N = len(J['neck']); sc = scores.get(a.get('slot'), {})
        tor = [((J['neck'][n][0] - J['pelvis'][n][0]) ** 2 + ((J['neck'][n][1] - J['pelvis'][n][1]) * asp) ** 2) ** 0.5
               for n in range(N) if J['neck'][n] is not None and J['pelvis'][n] is not None]
        if not tor: continue
        T = sorted(tor)[len(tor) // 2]
        for k in ('elb_r', 'wri_r', 'elb_l', 'wri_l', 'kne_r', 'ank_r', 'kne_l', 'ank_l'):
            v = sc.get(k)
            if not v: continue
            good = [x for x in v if x is not None]
            if not good: continue
            med = sorted(good)[len(good) // 2]
            low = [x is not None and x < c['rel'] * med and x < c['abs_max'] for x in v]
            i = 0
            while i < N:
                if not low[i]: i += 1; continue
                j = i
                while j < N and low[j]: j += 1
                if 0 < i and j < N and j - i <= c['max_gap'] and _off_line(J, k, i, j, asp, T) >= c['dev']:
                    for kk in (k,) + BRIDGE_CHAIN.get(k, ()):
                        p0, p1, q0, q1 = J[kk][i - 1], J[kk][j], J['pelvis'][i - 1], J['pelvis'][j]
                        if None in (p0, p1, q0, q1): continue
                        r0 = (p0[0] - q0[0], p0[1] - q0[1]); r1 = (p1[0] - q1[0], p1[1] - q1[1])
                        for n in range(i, j):
                            if J['pelvis'][n] is None: continue
                            t = (n - i + 1) / (j - i + 1)
                            J[kk][n] = [J['pelvis'][n][0] + r0[0] + (r1[0] - r0[0]) * t, J['pelvis'][n][1] + r0[1] + (r1[1] - r0[1]) * t]
                            done.append((a.get('slot'), n, kk))
                i = j
    return out, sorted(set(done))


CALM = dict(win=7, body_max=0.08, path_min=1.2, net_ratio=0.3, min_rev=0, low_score=3.0)   # 몸통 단위·장. body_max 0.08: 승인 10초판 바뀐 장 0/480, n41_04 25/27 (0.12면 10초판 55장)


def calm_limbs(ir, win=None, body_max=None, path_min=None, net_ratio=None, min_rev=None, wrist_score=None):
    """몸(목·골반·무릎·발목, 골반 기준과 골반 자체)이 거의 멈춰 있는데 한 팔(팔꿈치·손목)만 앞뒤로 진동하면
    검출 잡음(옷자락을 팔로, 좌우 팔 바꿔 잡기)으로 보고 그 창의 팔을 골반 기준 중앙값 자세로 둔다. 새 중간 표현과 바꾼 (인물, 장, 관절) 목록.
    11-05 사용자 n41_04 '슬로우모션처럼 옷이 빠르게 펄럭이는 연출인데 양팔이 파바박 움직임'.
    조건(창 win장): 몸 관절 평균 이동 < body_max, 팔 끝 경로 > path_min, 순이동/경로 < net_ratio, 방향 뒤집힘 ≥ min_rev, (wrist_score {slot: {'r': [...], 'l': [...]}}가 있으면) 손목 점수 창 중앙값 < low_score."""
    import copy
    c = dict(CALM, **{k: v for k, v in dict(win=win, body_max=body_max, path_min=path_min, net_ratio=net_ratio, min_rev=min_rev).items() if v is not None})
    asp = ir.get('aspect', 0.5625); out = copy.deepcopy(ir); changed = []
    for a in out['actors']:
        J = a['joints']; N = len(J['neck'])
        def rel(k, i):
            if J[k][i] is None or J['pelvis'][i] is None: return None
            return (J[k][i][0] - J['pelvis'][i][0], (J[k][i][1] - J['pelvis'][i][1]) * asp)
        tor = [((J['neck'][i][0] - J['pelvis'][i][0]) ** 2 + ((J['neck'][i][1] - J['pelvis'][i][1]) * asp) ** 2) ** 0.5
               for i in range(N) if J['neck'][i] is not None and J['pelvis'][i] is not None]
        if not tor: continue
        T = sorted(tor)[len(tor) // 2]
        dist = lambda p, q: (((p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2) ** 0.5) / T
        new = {k: list(J[k]) for k in J}
        for side in ('r', 'l'):
            arm = (f'elb_{side}', f'wri_{side}')
            for i in range(0, N - c['win'] + 1):
                idx = range(i, i + c['win'])
                body = []
                for k in ('neck', 'kne_r', 'kne_l', 'ank_r', 'ank_l'):
                    P = [rel(k, j) for j in idx]
                    if None in P: body = None; break
                    body += [dist(P[j], P[j - 1]) for j in range(1, len(P))]
                pv = [J['pelvis'][j] for j in idx]
                if body is None or None in pv: continue
                move = [dist((pv[j][0], pv[j][1] * asp), (pv[j - 1][0], pv[j - 1][1] * asp)) for j in range(1, len(pv))]
                # 골반 자체 이동은 따로 본다(골반 기준 0 이동인 관절들과 평균하면 몸 전체 평행 이동이 묽어진다 — 시험 반례)
                if sum(body) / len(body) >= c['body_max'] or sum(move) / len(move) >= c['body_max']: continue
                W_ = [rel(f'wri_{side}', j) for j in idx]
                if None in W_: continue
                path = sum(dist(W_[j], W_[j - 1]) for j in range(1, len(W_)))
                if path <= c['path_min'] or dist(W_[-1], W_[0]) / path >= c['net_ratio']: continue
                # 잡음은 거의 매 장 방향이 뒤집힌다. 진짜 휘두르기(n41_11 채찍)는 몇 장에 걸쳐 한 방향으로 간다
                D = [(W_[j][0] - W_[j - 1][0], W_[j][1] - W_[j - 1][1]) for j in range(1, len(W_))]
                rev = sum(1 for d0, d1 in zip(D, D[1:]) if d0[0] * d1[0] + d0[1] * d1[1] < 0)
                if rev < c['min_rev']: continue
                # 손목 검출 점수(있을 때): 창 중앙값이 low_score 이상이면 진짜 팔 동작으로 보고 두지 않는다.
                # n41_04(옷자락 펄럭임) 손목 점수 <3 비율 69%, 팔을 잘 잡은 n41_11(채찍)·16·21은 11–18%
                if wrist_score is not None:
                    sc = [v for v in (wrist_score.get(a.get('slot'), {}).get(side) or [None] * N)[i:i + c['win']] if v is not None]
                    if not sc or sorted(sc)[len(sc) // 2] >= c['low_score']: continue
                for k in arm:
                    P = [rel(k, j) for j in idx]
                    if None in P: continue
                    mx = sorted(p[0] for p in P)[len(P) // 2]; my = sorted(p[1] for p in P)[len(P) // 2]
                    for j in idx:
                        new[k][j] = [J['pelvis'][j][0] + mx, J['pelvis'][j][1] + my / asp]
                        changed.append((a.get('slot'), j, k))
        for k in new: J[k] = new[k]
    return out, sorted(set(changed))


def compile_ir(ir, name='motion_ir', sheets=None):
    """sheets: {slot: char_sheet.read(...) 한 칸 또는 char_sheet.read_all(...) 여러 칸} — 그 인물에 캐릭터 시트 색·액세서리를 입힌다(단계 1-②).
    여러 칸이면 장마다 facing에 가장 가까운 칸을 쓴다(모르면 정면)."""
    sheets = sheets or {}
    sim_state = {}   # 흔들리는 액세서리의 장 사이 상태(인물·액세서리별)
    from stickman_clip import person_aos
    N = ir['frames']
    parts = [f'<Sequence Name="{name}" HeightWidthRatio="{ir["aspect"]}" RatioX="16" RatioY="9" FrameCount="{N}" BackgroundColor="-1">']
    for n in range(N):
        parts.append(f'<Frame BackgroundColor="-1" ID="{5000 + n}" Position="{n}"><LayerDef ID="0" Name="Layer 1" Visible="true" Locked="false" />')
        for a in ir['actors']:
            # 화면 % → 가로세로 같은 단위(16:9)로: 머리 접촉 제약(A안)은 실제 거리로 계산해야 원본과 같다
            sx, sy = 16.0, 16.0 * ir['aspect']
            Jn = {k: (v[n][0] * sx / 100, v[n][1] * sy / 100) for k, v in a['joints'].items() if v[n] is not None}
            need = ('head_t', 'neck', 'pelvis', 'elb_r', 'wri_r', 'elb_l', 'wri_l', 'kne_r', 'ank_r', 'kne_l', 'ank_l')
            if any(k not in Jn for k in need): continue   # 관절이 빠진 장은 그 인물을 그리지 않는다(단계 2 자동 추출: 풀이 범위 밖 장)
            if 'head_b' not in Jn: Jn.pop('head_b', None)
            off = set(a['hidden'][n]) | set(a['smear'][n])
            vis = [o for o in range(1, 12) if o not in off]
            color = a['color'] if isinstance(a['color'], str) else 'blue'
            tn = a['thickness'][n] or {}
            xml = person_aos(n, a['slot'], Jn, lambda p, sx=sx, sy=sy: (p[0] / sx * 100, p[1] / sy * 100), color, 1.0, visible_segments=vis)
            for oid_s, t in tn.items():   # 객체별 굵기
                aid = f'ID="{AO0 + a["slot"] * 100 + int(oid_s)}" '
                i = xml.find('<AO ' + aid)
                if i >= 0:
                    j = xml.find('ThicknessScale="', i) + len('ThicknessScale="'); k = xml.find('"', j)
                    xml = xml[:j] + f'{t:.3f}' + xml[k:]
            if not isinstance(a['color'], str):
                xml = xml.replace(f'Color="{LINE_COLOR["blue"]}"', f'Color="{a["color"]}"')
            if not a['head_fill'][n]:
                i = xml.find('<FR ')
                if i >= 0: xml = xml[:i]
            sh = sheets.get(a['slot'])
            if sh is not None:
                import char_sheet as CS
                fc = a.get('facing') or [None] * N
                rigged = 'accs' in sh                       # CS.rig(read_all(...)): 연속 방향(칸 사이를 섞음)
                if not rigged and 'joints' not in sh:       # 여러 칸(read_all) → 이 장의 몸 방향에 맞는 칸(가면 방향 2/3)
                    sh = CS.pick_view(sh, fc[n])
                xml = xml.replace(f'Color="{LINE_COLOR[color]}"', f'Color="{(sh["base"] if rigged else sh)["body_color"]}"')
                Jp = {k: tuple(v[n]) for k, v in a['joints'].items() if v[n] is not None}
                if 'head_b' not in Jp: Jp['head_b'] = Jp['neck']
                body_th = (tn.get('2') if tn else None) or 1.0
                i = xml.find('<FR ')
                if rigged:   # 연속 방향 + 흔들리는 망토(사슬 계산, 몸 뒤/앞 두 사본)
                    behind, acc = CS.rig_frame(sh, fc[n], n, a['slot'], Jp, body_th, sim_state)
                    xml = behind + xml
                    i = xml.find('<FR ', len(behind))
                else:
                    acc = CS.accessory_xml(sh, n, a['slot'], Jp, body_th)
                xml = (xml[:i] + acc + xml[i:]) if i >= 0 else xml + acc
            parts.append(xml)
        parts.append('</Frame>')
    parts.append('</Sequence>')
    root = ET.fromstring(''.join(parts))
    if sheets:
        declare_all_first(root, [a['slot'] for a in ir['actors']])
    return root


def _slot_of(aid):
    import char_sheet as CS
    i = int(aid)
    if 0 <= i - AO0 < 1000: return (i - AO0) // 100
    if 0 <= i - CS.ACC_AO0 < 100000: return (i - CS.ACC_AO0) // 1000
    return None


def declare_all_first(root, slots):
    """앱은 오브젝트 앞뒤를 '파일 전체에서 처음 나온 순서'로 정한다(FORMAT.md 10-29). 첫 장에 없던 인물은 그 인물의 모든 오브젝트
    (망토 뒤 사본·몸·가면·망토 앞 사본)가 나중에 등록돼 다른 인물 앞으로 나온다(11-05 사용자 '망토 레이어 버그').
    → 첫 장에 없는 인물은 처음 나오는 장의 오브젝트를 투명(Color 0, 채움 없음)으로 첫 장에 미리 넣고, 첫 장 오브젝트를 인물 순서로 정렬."""
    frames = root.findall('Frame')
    if not frames: return
    f0 = frames[0]
    have0 = {_slot_of(a.get('ID')) for a in f0.findall('AO')}
    pid = [960000000]
    for s in slots:
        if s in have0: continue
        src = next((f for f in frames[1:] if any(_slot_of(a.get('ID')) == s for a in f.findall('AO'))), None)
        if src is None: continue
        remap = {}
        for a in src.findall('AO'):
            if _slot_of(a.get('ID')) != s: continue
            c = copy.deepcopy(a); c.set('Color', '0')
            for ap in c.findall('AP'):
                remap[ap.get('ID')] = str(pid[0]); ap.set('ID', str(pid[0])); pid[0] += 1
            f0.append(c)
        for a in f0.findall('AO'):
            if _slot_of(a.get('ID')) == s:
                for ac in a.iter('AC'):
                    ac.set('ConnPtId', remap.get(ac.get('ConnPtId'), ac.get('ConnPtId')))
    aos = f0.findall('AO'); frs = f0.findall('FR')
    for x in aos + frs: f0.remove(x)
    order = {s: i for i, s in enumerate(slots)}
    for a in sorted(aos, key=lambda a: order.get(_slot_of(a.get('ID')), 99)):   # 같은 인물 안 순서는 그대로(안정 정렬)
        f0.append(a)
    for x in frs: f0.append(x)
    # DrawOrder도 같은 순위로(11-05: 몸 뒤 망토 사본이 파일에서 먼저 나와도 DrawOrder가 커서 앱·렌더러 모두 몸 앞에 그렸다).
    # 파일 전체 처음 나온 순서 = DrawOrder 순위 → 물리 순서·DrawOrder 어느 쪽을 쓰든 같은 앞뒤.
    rank = {}
    for f in frames:
        for a in f.findall('AO'):
            rank.setdefault(a.get('ID'), len(rank))
    for f in frames:
        for a in f.findall('AO'):
            a.set('DrawOrder', str(1000 + rank[a.get('ID')]))


def base_signature(root):
    """기본 11객체의 (장, 객체 ID) → (종류, 색, 굵기, 점(ID, Flags, X, Y, 연결)들) — 대조용."""
    out = {}
    for n, f in enumerate(root.findall('Frame')):
        for a in f.findall('AO'):
            i = int(a.get('ID')) - AO0
            if not (0 <= i < 1000 and 0 < i % 100 <= 11): continue
            lo = PT0 + n * 1000   # 기본 뼈대 점 범위 안의 연결만(근경 면 등 표시층으로 가는 연결은 v1 범위 밖)
            pts = tuple((p.get('ID'), p.get('Flags'), round(float(p.get('X')), 3), round(float(p.get('Y')), 3),
                         tuple(sorted(c.get('ConnPtId') for c in p.findall('AC') if lo <= int(c.get('ConnPtId')) < lo + 1000))) for p in a.findall('AP'))
            out[(n, a.get('ID'))] = (a.get('TypeId'), a.get('Color'), round(float(a.get('ThicknessScale')), 3), pts)
    return out


def roundtrip(path):
    src = load(path)
    ir = extract(src)
    out = compile_ir(ir)
    A, B = base_signature(src), base_signature(out)

    def same(a, b, tol=0.002):
        # 종류·색·굵기·점 ID·Flags·연결은 정확히, 좌표는 0.002% 이내(소수 넷째 자리 반올림을 한 번 더 거침)
        if b is None or a[:3] != b[:3] or len(a[3]) != len(b[3]): return False
        return all(p[0] == q[0] and p[1] == q[1] and p[4] == q[4] and abs(p[2] - q[2]) <= tol and abs(p[3] - q[3]) <= tol for p, q in zip(a[3], b[3]))
    diff = [k for k in A if not same(A[k], B.get(k))]
    extra = [k for k in B if k not in A]
    return dict(frames=ir['frames'], actors=len(ir['actors']), base_objects=len(A), mismatched=len(diff), missing_or_extra=len(extra),
                first_mismatch=(diff[:1] and dict(key=diff[0], src=A[diff[0]], out=B.get(diff[0]))) or None), ir, out


def save_sfa(root, path, name):
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(name + '.xml', ET.tostring(root, encoding='utf-8', xml_declaration=True))


if __name__ == '__main__':
    cmd = sys.argv[1]
    if cmd == 'extract':
        json.dump(extract(load(sys.argv[2])), open(sys.argv[3], 'w'), ensure_ascii=False)
    elif cmd == 'compile':
        save_sfa(compile_ir(json.load(open(sys.argv[2]))), sys.argv[3], Path(sys.argv[3]).stem)
    elif cmd == 'roundtrip':
        rep, _, _ = roundtrip(sys.argv[2])
        print(json.dumps(rep, ensure_ascii=False, default=str)[:2000])
