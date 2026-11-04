"""고정 각도 와이드샷의 배경 판(2026-11-05 사용자 제안): 카메라가 평행 이동만 하는 컷을 이어 붙여 큰 배경 판을 만들고,
판 위에서 투시도 선을 한 번만 딴 뒤, 장마다 카메라 위치만큼 옮겨 SFA에 배치한다(배경 객체 ID는 모든 장에서 같음).
사용: PL_SP=<scratch> python plate.py 시작 끝 출력장,출력장,...  (원화 장번호, 완성본 = 원화+7)
비공개 scratch 전용."""
import json, math, os, sys, copy, zipfile, xml.etree.ElementTree as ET
import cv2, numpy as np, torch
SP = os.environ['PL_SP']
sys.path.insert(0, SP + '/scripts'); sys.path.insert(0, '/home/user/AI-sfa/tools')
import perspective_lines as PL
import sfa_render as R

F0, F1 = int(sys.argv[1]), int(sys.argv[2])
OUTF = [int(v) for v in sys.argv[3].split(',')]
W, H = 960, 540
orb = cv2.ORB_create(3000)


def final(f):
    PL.B.set(1, f + 7); ok, im = PL.B.read()
    return cv2.resize(im, (W, H), interpolation=cv2.INTER_AREA)


def shift(a_img, a_p, b_img, b_p):
    """b 안의 점 = a 안의 점 + t(평행 이동, 배경 특징점만)."""
    ga, gb = cv2.cvtColor(a_img, cv2.COLOR_BGR2GRAY), cv2.cvtColor(b_img, cv2.COLOR_BGR2GRAY)
    k1, d1 = orb.detectAndCompute(ga, (1 - a_p) * 255); k2, d2 = orb.detectAndCompute(gb, (1 - b_p) * 255)
    if d1 is None or d2 is None or len(k1) < 20 or len(k2) < 20:   # 특징점 부족(전환·어두운 장): 위상 상관으로
        (sx, sy), resp = cv2.phaseCorrelate(np.float32(ga), np.float32(gb))
        return np.array([sx, sy]), 0, 1.0
    m = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True).match(d1, d2)
    if len(m) < 20:
        (sx, sy), resp = cv2.phaseCorrelate(np.float32(ga), np.float32(gb))
        return np.array([sx, sy]), 0, 1.0
    src = np.float32([k1[x.queryIdx].pt for x in m]); dst = np.float32([k2[x.trainIdx].pt for x in m])
    A, inl = cv2.estimateAffinePartial2D(src, dst, method=cv2.RANSAC, ransacReprojThreshold=2.0)
    return A[:, 2].astype(float), int(inl.sum()), float(np.hypot(A[0, 0], A[1, 0]))


# 1) 장마다 판 위치(off_f: 판 좌표 = 장 좌표 + off_f), 이웃 장 이동을 이어서
frames = list(range(F0, F1 + 1))
imgs, pms, off, log = {}, {}, {F0: np.zeros(2)}, []
for f in frames:
    imgs[f] = final(f); pms[f] = PL.person_for(f)[1]
for a, b in zip(frames, frames[1:]):
    t, n, sc = shift(imgs[a], pms[a], imgs[b], pms[b])
    off[b] = off[a] - t
    log.append((b, round(float(t[0]), 1), round(float(t[1]), 1), n, round(sc, 4)))
xs = [o[0] for o in off.values()]; ys = [o[1] for o in off.values()]
ox, oy = -min(xs), -min(ys)
PW, PH = int(math.ceil(max(xs) + ox + W)), int(math.ceil(max(ys) + oy + H))
PW, PH = (PW + 7) // 8 * 8, (PH + 7) // 8 * 8   # 선화 모델이 8의 배수 크기에서 같은 크기로 출력
for f in off: off[f] = off[f] + (ox, oy)
print('판 크기', PW, PH, '이동 범위 x', round(min(xs), 1), round(max(xs), 1), 'y', round(min(ys), 1), round(max(ys), 1),
      '대응 최소', min(l[3] for l in log), '배율 범위', min(l[4] for l in log), max(l[4] for l in log))

# 2) 인물 뺀 픽셀의 중앙값으로 판. 기준은 '부서지기 전' 상태(11-05 사용자): PLATE_UNTIL 장까지만 쓴다.
#    부서진 벽·떨어진 파편은 판이 아니라 그 장부터 생기는 요소 트랙으로 다룬다.
UNTIL = int(os.environ.get('PLATE_UNTIL', F1))
use = [f for f in frames if f <= UNTIL][::2]
stack = np.full((len(use), PH, PW, 3), np.nan, np.float32)
for i, f in enumerate(use):
    M = np.float32([[1, 0, off[f][0]], [0, 1, off[f][1]]])
    w = cv2.warpAffine(imgs[f].astype(np.float32), M, (PW, PH), flags=cv2.INTER_LINEAR, borderValue=np.nan)
    v = cv2.warpAffine((1 - pms[f]).astype(np.uint8), M, (PW, PH), flags=cv2.INTER_NEAREST, borderValue=0)
    w[v == 0] = np.nan
    stack[i] = w
# 인물이 오래 머문 자리의 그림자는 중앙값에 남는다. 그림자는 배경보다 어두우므로 밝기 순 상위 백분위(PLATE_PCT, 기본 75)로 고른다.
PCT = float(os.environ.get('PLATE_PCT', 75))
lum = np.nanmean(stack, 3)
cnt = np.sum(~np.isnan(lum), 0)
rank = np.argsort(np.where(np.isnan(lum), np.inf, lum), 0)          # 밝기 오름차순, 빈칸은 뒤로
k = np.clip(np.round((cnt - 1) * PCT / 100).astype(int), 0, None)
idx = np.take_along_axis(rank, k[None], 0)[0]
plate = np.take_along_axis(stack, idx[None, ..., None].repeat(3, -1), 0)[0]
plate[cnt == 0] = np.nan
hole = np.isnan(plate[..., 0])
plate = np.nan_to_num(plate, nan=0).astype(np.uint8)
plate = cv2.inpaint(plate, hole.astype(np.uint8), 5, cv2.INPAINT_TELEA) if hole.any() else plate
cv2.imwrite(SP + '/slice/plate/plate.png', plate)
print('판 사용 장', use[0], '~', use[-1], len(use), '장, 빈칸 비율', round(float(hole.mean()), 4))

# 3) 판 위에서 투시도 선 한 번
PL.W, PL.H = PW, PH
nob = np.zeros((PH, PW), np.uint8)
la, segs = PL.lineart_segs(plate, nob)
rng = np.random.default_rng(0)
vp1, sc1 = PL.estimate_vp(segs, rng)
vp = [vp1]
rest = [s for s in segs if PL.is_axis(s) or PL.dir_to_vp(s, vp1) >= PL.VP_DEG]
vp2, sc2 = PL.estimate_vp(rest, rng)
if vp2 is not None and sc2 > 0.25 and math.hypot(vp2[0] - vp1[0], vp2[1] - vp1[1]) > 80: vp.append(vp2)
lines, other, st = PL.snap(segs, vp)
gray = cv2.GaussianBlur(cv2.cvtColor(plate, cv2.COLOR_BGR2GRAY), (3, 3), 0)
ev = cv2.dilate(((cv2.Canny(gray, 25, 70) > 0) | (la < 200)).astype(np.uint8), np.ones((3, 3), np.uint8))
lines, grown = PL.extend(lines, ev)
lines, nc = PL.corners(lines)
lines = [l for l in lines if math.hypot(l[0][0] - l[1][0], l[0][1] - l[1][1]) >= PL.MIN_OUT]
lines, lay = PL.layout(lines, vp[0])
# 바닥의 가로 띠는 창으로 든 빛·그림자 경계일 뿐 구조가 아니다(11-05 사용자) → 구조선에서 뺀다(명암은 나중 채색 단계).
if os.environ.get('PLATE_FLOOR', '0') != '1':
    lines = [l for l in lines if l[2] != 'floorx']; lay['floor_lines'] = 0
other = [o for o in other if math.hypot(o[0][0] - o[1][0], o[0][1] - o[1][1]) >= 60]
allines = lines + other

# 방 틀만(11-05 사용자 "천장도 면으로, 중간 기둥 같은 것도 다 빼 봐"): 네 경계선 + 안쪽 벽 사각형 = 바닥·천장·좌우 벽·안쪽 벽 5면.
# 보·기둥·세부·기타 선은 모두 뺀다. 면 채색은 나중(확인 그림에서만 면을 색으로 구분).
BOX = os.environ.get('PLATE_BOX', '0') == '1'
faces = None
if BOX:
    vx, vy = vp[0]
    ray = {}
    for a, b, k in lines:
        if k != 'room': continue
        side = 'right' if b[0] > vx else 'left'; lvl = 'floor' if b[1] > vy else 'ceil'
        ray[f'{lvl}_{side}'] = (math.atan2(b[1] - vy, b[0] - vx), a, b)
    assert len(ray) == 4, sorted(ray)
    xl = max(ray['floor_left'][1][0], ray['ceil_left'][1][0]); xr = min(ray['floor_right'][1][0], ray['ceil_right'][1][0])
    cn = {n: PL.ray_point_at(vp[0], ray[n][0], x=(xl if n.endswith('left') else xr)) for n in ray}
    # 왼쪽 열린 공간(11-05 사용자 "왼쪽 열린 공간으로 둬", PLATE_OPEN_LEFT=1 기본): 왼벽·왼쪽 경계선 없음,
    # 바닥·천장·안쪽 벽이 판 왼쪽 끝까지 이어진다.
    OPEN_L = os.environ.get('PLATE_OPEN_LEFT', '1') == '1'
    if OPEN_L:
        ty, by = cn['ceil_right'][1], cn['floor_right'][1]
        cn['ceil_left'], cn['floor_left'] = (0.0, ty), (0.0, by); xl = 0.0
    allines = [(cn[n], ray[n][2], 'room') for n in ray if not (OPEN_L and n.endswith('left'))]
    allines += [(cn['ceil_left'], cn['ceil_right'], 'room'), (cn['floor_left'], cn['floor_right'], 'room'),
                (cn['ceil_right'], cn['floor_right'], 'room')] + ([] if OPEN_L else [(cn['ceil_left'], cn['floor_left'], 'room')])
    yy, xx = np.mgrid[0:PH, 0:PW]
    th = np.arctan2(yy - vy, xx - vx)
    A = {n: ray[n][0] for n in ray}
    faces = np.full((PH, PW), 3, np.uint8)                                   # 3 왼쪽 벽
    faces[(th > A['ceil_left']) & (th < A['ceil_right'])] = 1               # 1 천장
    faces[(th >= A['ceil_right']) & (th < A['floor_right'])] = 2            # 2 오른쪽 벽
    faces[(th >= A['floor_right']) & (th < A['floor_left'])] = 0            # 0 바닥
    if OPEN_L:   # 왼쪽: 안쪽 벽 위 = 천장, 아래 = 바닥
        lft = (faces == 3) | ((faces != 2) & (xx < cn['ceil_right'][0]))
        faces[lft & (yy < cn['ceil_right'][1])] = 1; faces[lft & (yy > cn['floor_right'][1])] = 0
    inside = (xx >= xl) & (xx <= xr)
    top = np.interp(xx, [xl, xr], [cn['ceil_left'][1], cn['ceil_right'][1]]); bot = np.interp(xx, [xl, xr], [cn['floor_left'][1], cn['floor_right'][1]])
    faces[inside & (yy >= top) & (yy <= bot)] = 4                            # 4 안쪽 벽
    lay = dict(lay, box=dict(back_wall=[round(xl), round(cn['ceil_left'][1]), round(xr), round(cn['floor_left'][1])]))
    print('방 틀만: 선', len(allines), '안쪽 벽', lay['box'])
print('판 소실점', [[round(v[0]), round(v[1])] for v in vp], '선', len(lines), '기타', len(other), lay)

vis = np.full_like(plate, 255)
if faces is not None:   # 면 구분 확인용 색(바닥·천장·오른벽·왼벽·안쪽 벽)
    FC = np.array([[170, 200, 230], [200, 180, 160], [160, 200, 170], [190, 170, 200], [220, 220, 220]], np.uint8)
    vis = FC[faces]
for a, b, k in allines:
    cv2.line(vis, tuple(map(int, a)), tuple(map(int, b)), PL.COL[k], 3 if k == 'room' else 1 if k in ('o', 'detail') else 2, cv2.LINE_AA)
cv2.imwrite(SP + '/slice/plate/plate_lines.png', np.vstack([plate, vis]))

# 4) 장마다 옮겨 배치: 배경 객체 ID는 모든 장에서 같고(같은 선), 점 ID는 장마다 새로
seq = ET.Element('Sequence', dict(Name='sfa_slice_plate_v1', HeightWidthRatio='0.5625', RatioX='16', RatioY='9', FrameCount=str(len(OUTF)), BackgroundColor='-1'))
rows = []
for pos, f in enumerate(OUTF):
    fr = ET.SubElement(seq, 'Frame', dict(BackgroundColor='4294967295', ID=str(pos + 1), Position=str(pos)))
    for lid, nm in PL.LAYER_NAMES:
        ET.SubElement(fr, 'LayerDef', dict(ID=str(lid), Name=nm, Visible='true', Locked='false'))
    pid = 1 + pos * 100000
    dx, dy = off[f]
    for oid, (a, b, k) in enumerate(allines, start=1):
        ao = ET.SubElement(fr, 'AO', dict(ID=str(oid), TypeId='1', Color=str(-12566464 if k not in ('o', 'detail') else -7829368), LayerId=str(PL.LAYER_OF[k]),
                                          DrawOrder=str(oid), ThicknessScale='0.35', ObjectScale='1.0', GlowRadius='0', GlowThickness='0', GlowColor='4294967295', GlowAlpha='0'))
        for i, (px_, py_) in enumerate((a, b)):
            ET.SubElement(ao, 'AP', dict(ID=str(pid), Flags=('9', '8')[i], Index=str(i), X=f'{(px_ - dx) / W * 100:.3f}', Y=f'{(py_ - dy) / H * 100:.3f}')); pid += 1
    m = {}
    for ao in PL.sroot.findall('Frame')[f - 432].findall('AO'):
        ao = copy.deepcopy(ao); ao.set('LayerId', '6')
        for ap in ao.iter('AP'): m[ap.get('ID')] = str(pid); ap.set('ID', str(pid)); pid += 1
        fr.append(ao)
    for ac in fr.iter('AC'): ac.set('ConnPtId', m.get(ac.get('ConnPtId'), ac.get('ConnPtId')))
    R.PARAMS.update(pad=0.0, thick_mul=1.0)
    rend = cv2.cvtColor(R.render_frame(seq, fr, W, H)[..., :3].astype(np.uint8), cv2.COLOR_RGB2BGR)
    ov = imgs[f].copy() if f in imgs else final(f)
    for a, b, k in allines:   # 원본 위에 판 선 겹쳐 맞춤 확인
        cv2.line(ov, (int(a[0] - dx), int(a[1] - dy)), (int(b[0] - dx), int(b[1] - dy)), (0, 0, 255), 1, cv2.LINE_AA)
    cv2.putText(rend, f'orig {f}  offset ({dx:.0f},{dy:.0f})', (6, 28), 0, 0.8, (0, 0, 255), 2)
    rows.append(np.hstack([imgs.get(f, ov), ov, rend]))
with zipfile.ZipFile(SP + '/slice/plate/sfa_slice_plate_v1.sfa', 'w', zipfile.ZIP_DEFLATED) as zf:
    zf.writestr('sfa_slice_plate_v1.xml', ET.tostring(seq, encoding='utf-8', xml_declaration=True))
cv2.imwrite(SP + '/slice/plate/plate_frames.png', cv2.resize(np.vstack(rows), None, fx=0.4, fy=0.4))
json.dump(dict(plate=[PW, PH], plate_until=UNTIL, plate_pct=PCT, offsets={str(k): [round(float(v[0]), 2), round(float(v[1]), 2)] for k, v in off.items()}, pair_log=log,
               vp=[[float(v[0]), float(v[1])] for v in vp], layout=lay, lines=len(allines)), open(SP + '/slice/plate/plate_meta.json', 'w'), ensure_ascii=False, indent=1)
print('출력 장', OUTF, '배경 객체', len(allines), '(모든 장 같은 ID)')
