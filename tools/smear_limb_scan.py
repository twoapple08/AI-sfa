"""부위 고정(pose-anchored) 스미어 후보 탐지 v2. 의미 확정/학습 아님.

기존 `smear_candidate_scan.py`(화면 전체 색 경계 질감)의 실패 원인:
  1) 인물 영역 분리 실패 — 빨강 배관·초록 블록·회청색 천 같은 배경도 인물색 마스크로 들어감.
  2) 의미 판정 실패 — 머리카락·벌린 손가락·옷단·신발 외곽도 같은 톱니 질감.
  3) 시간 변화 — 인물은 2장 단위(투스), 카메라는 1장 단위로 움직여 앞뒤 장 차이가 배경 이동에 묻힘.
그래서 이 판은 질감보다 '어디에 있는가'를 먼저 본다.
  A. 인물 영역: RTMW 관절의 인물색 판정 + 뼈대 주변 영역과 인물색 마스크의 교집합만 쓴다.
  B. 후보 생성: 각 인물의 손목/발목 끝 창(팔꿈치/무릎→손목/발목 방향으로 조금 연장)만 본다.
     관절이 없는 큰 인물색 덩어리(화면 밖에서 들어오는 팔다리)는 별도 'no_pose' 후보로 둔다.
  C. 의미 특징: 같은 인물 머리 영역을 뺀 뒤, 가는 색 가닥(끝이 뾰족한 길쭉한 돌기)과 검은 속도선의
     '개수 × 방향 일치도', 그리고 장 사이 상대 이동(몸통 기준)을 쓴다.
점수는 보정 확률이 아니다. 계수는 개발 구간에서만 정하고 시험 구간에서 따로 잰다(문서 참조).
"""
import argparse, gzip, hashlib, json
from pathlib import Path
import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
LIMBS = {'arm_l': (7, 9), 'arm_r': (8, 10), 'leg_l': (13, 15), 'leg_r': (14, 16)}
EDGES = [(5, 7), (7, 9), (6, 8), (8, 10), (11, 13), (13, 15), (12, 14), (14, 16), (5, 6), (11, 12), (5, 11), (6, 12), (0, 5), (0, 6)]
PARAMS = dict(min_kp=2.0, window=0.6, head=0.5, body_width=0.55, dark=80, strand_aspect=2.5,
              w_color=1.0, w_dark=0.6, motion_ref=0.25, no_pose_area=0.01)


def color_masks(rgb):
    a = rgb.astype(np.float32)
    r, g, b = (a[:, :, i] for i in range(3))
    s = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)[:, :, 1]
    return {'red': ((r > 1.22 * g) & (r > 1.10 * b) & (r > 45) & (s > 45)).astype(np.uint8),
            # 초록 블록 오인을 막으려고 파랑이 초록보다도 커야 한다(기존 판은 g>1.06r만 봄).
            'blue': ((b > 1.13 * r) & (g > 1.06 * r) & (b > 1.04 * g) & (b > 40) & (s > 40)).astype(np.uint8)}


def load_rtmw(path, y_offset=63):
    out = {}
    for line in gzip.open(path, 'rt'):
        d = json.loads(line)
        ks = []
        for p in d['p']:
            k = np.array(p['k'], float)
            k[:, 1] -= y_offset
            ks.append(k)
        out[int(d['f'])] = ks
    return out


def torso(k):
    return float(max(20.0, np.linalg.norm((k[5, :2] + k[6, :2]) / 2 - (k[11, :2] + k[12, :2]) / 2)))


def assign_actors(masks, people, p=PARAMS):
    """RTMW 인물마다 몸통 관절 주변 인물색 비율로 빨강/파랑을 정한다. 같은 색이 둘이면 더 강한 쪽만."""
    best = {}
    for k in people:
        votes = {}
        for actor, m in masks.items():
            v, n = 0.0, 0
            for i in (5, 6, 11, 12, 7, 8, 13, 14):
                if k[i, 2] < p['min_kp']:
                    continue
                x, y = int(k[i, 0]), int(k[i, 1])
                if 0 <= x < m.shape[1] and 0 <= y < m.shape[0]:
                    v += float(m[max(0, y - 6):y + 7, max(0, x - 6):x + 7].mean())
                    n += 1
            votes[actor] = v / max(1, n)
        actor = max(votes, key=votes.get)
        if votes[actor] < 0.25:
            continue
        if actor not in best or votes[actor] > best[actor][0]:
            best[actor] = (votes[actor], k)
    return {a: k for a, (_, k) in best.items()}


def person_region(shape, k, p=PARAMS):
    t = torso(k)
    reg = np.zeros(shape, np.uint8)
    w = max(3, int(p['body_width'] * t))
    for a, b in EDGES:
        if k[a, 2] >= p['min_kp'] and k[b, 2] >= p['min_kp']:
            cv2.line(reg, tuple(map(int, k[a, :2])), tuple(map(int, k[b, :2])), 1, w)
    for i in range(17):
        if k[i, 2] >= p['min_kp']:
            cv2.circle(reg, tuple(map(int, k[i, :2])), int(0.45 * t), 1, -1)
    # 스미어는 팔다리 끝에서 멀리 늘어지므로 끝 관절 주변을 더 넓게 허용한다.
    for _, (e, w2) in LIMBS.items():
        if k[w2, 2] >= p['min_kp']:
            cv2.circle(reg, tuple(map(int, k[w2, :2])), int(1.1 * t), 1, -1)
    return reg


def head_zone(shape, k, p=PARAMS):
    z = np.zeros(shape, np.uint8)
    pts = k[0:5][k[0:5, 2] >= p['min_kp']]
    if len(pts):
        c = pts[:, :2].mean(0)
        cv2.circle(z, (int(c[0]), int(c[1])), int(p['head'] * torso(k)), 1, -1)
    return z


def _strands(binary, aspect, min_area):
    """끝이 가는 길쭉한 조각들의 개수, 방향 일치도(0~1), 대표 각도, 조각 화소 마스크."""
    n, lab, stats, _ = cv2.connectedComponentsWithStats(binary, 8)
    angles, keep = [], []
    for i in range(1, n):
        if stats[i, 4] < min_area:
            continue
        ys, xs = np.nonzero(lab == i)
        if len(xs) < 3:
            continue
        cov = np.cov(np.stack([xs, ys]).astype(np.float32))
        ev, evec = np.linalg.eigh(cov)
        if ev[0] <= 1e-6 or (ev[1] / ev[0]) ** .5 < aspect:
            continue
        angles.append(np.arctan2(evec[1, 1], evec[0, 1]))
        keep.append(i)
    sel = np.isin(lab, keep) if keep else np.zeros(binary.shape, bool)
    if not angles:
        return 0, 0.0, None, sel
    a = np.array(angles)
    vec = np.array([np.cos(2 * a).mean(), np.sin(2 * a).mean()])
    return len(angles), float(np.hypot(*vec)), float(np.arctan2(vec[1], vec[0]) / 2), sel


def window_features(gray, actor_mask, center, radius, exclude, scale, p=PARAMS):
    H, W = gray.shape
    win = np.zeros((H, W), np.uint8)
    cv2.circle(win, (int(center[0]), int(center[1])), int(radius), 1, -1)
    A = actor_mask & win & (1 - exclude)
    area = int(A.sum())
    if area < 30:
        return None
    min_area = max(4, int(3 * scale * scale))
    feats, strand_px = {}, np.zeros((H, W), bool)
    # thin: 화면 기준 고정 폭(1152폭에서 약5px) — 스미어 가닥은 가늘고 손가락은 이보다 굵다.
    # wide: 창 크기 비례(기존 v2a) — 굵은 지그재그도 놓치지 않게.
    for name, k in (('thin', max(3, int(round(5 * scale)) | 1)), ('wide', max(3, int(round(0.1 * radius)) | 1))):
        opened = cv2.morphologyEx(A, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k)))
        n, c, ang, sel = _strands((A - opened).astype(np.uint8), p['strand_aspect'], min_area)
        feats[name] = (n, c, ang)
        strand_px |= sel
    near = cv2.dilate(A, np.ones((5, 5), np.uint8)) & win
    dark = ((gray < p['dark']) & (near > 0)).astype(np.uint8)
    dark = dark & (1 - cv2.morphologyEx(dark, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8)))
    nd, cd, ad, seld = _strands(dark, p['strand_aspect'] + 1.0, min_area)
    strand_px |= seld
    ys, xs = np.nonzero(strand_px) if strand_px.any() else np.nonzero(A)
    nt, ct, at = feats['thin']
    nw, cw, aw = feats['wide']
    return dict(area=area, color_strands=nw, color_coherence=round(cw, 3), thin_strands=nt, thin_coherence=round(ct, 3),
                dark_strands=nd, dark_coherence=round(cd, 3),
                box=[int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1],
                strand_angle=next((x for x in (aw, at, ad) if x is not None), None))


def relative_motion(rt, f, actor_k, actor, masks_prev_fn, idx, back=(1, 2, 3)):
    """같은 인물의 끝 관절이 이전 다른 그림 대비 몸통 기준으로 얼마나 움직였는지(몸통 길이 단위)."""
    t = torso(actor_k)
    cur = actor_k[idx, :2] - (actor_k[11, :2] + actor_k[12, :2]) / 2
    best = 0.0
    for b in back:
        prev = masks_prev_fn(f - b)
        if prev is None or actor not in prev:
            continue
        pk = prev[actor]
        if pk[idx, 2] < PARAMS['min_kp']:
            continue
        old = pk[idx, :2] - (pk[11, :2] + pk[12, :2]) / 2
        best = max(best, float(np.linalg.norm(cur - old)) / t)
    return best


def score(feat, motion, p=PARAMS):
    s_color = feat['color_strands'] * feat['color_coherence']
    s_dark = feat['dark_strands'] * feat['dark_coherence']
    texture = p['w_color'] * s_color + p['w_dark'] * s_dark
    return float(texture * (0.5 + 0.5 * min(1.0, motion / p['motion_ref'])))


class Scanner:
    def __init__(self, frames_dir, rtmw, source_start, p=PARAMS):
        self.files = {source_start + i: f for i, f in enumerate(sorted(Path(frames_dir).glob('*.png')))}
        self.rt, self.p, self._act = rtmw, p, {}

    def rgb(self, f):
        return cv2.cvtColor(cv2.imread(str(self.files[f])), cv2.COLOR_BGR2RGB)

    def actors(self, f):
        if f not in self.files:
            return None
        if f not in self._act:
            self._act[f] = assign_actors(color_masks(self.rgb(f)), self.rt.get(f, []), self.p)
        return self._act[f]

    def scan_frame(self, f):
        p = self.p
        rgb = self.rgb(f)
        gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
        H, W = gray.shape
        scale = W / 1152
        masks = color_masks(rgb)
        acts = self.actors(f)
        out = []
        for actor, k in acts.items():
            t = torso(k)
            region = person_region(gray.shape, k)
            excl = head_zone(gray.shape, k)
            m = masks[actor] & region
            for limb, (e, w) in LIMBS.items():
                if k[w, 2] < p['min_kp']:
                    continue
                d = k[w, :2] - k[e, :2] if k[e, 2] >= p['min_kp'] else np.zeros(2)
                c = k[w, :2] + 0.25 * d
                feat = window_features(gray, m, c, max(25 * scale, p['window'] * t), excl, scale)
                if feat is None:
                    continue
                mot = relative_motion(self.rt, f, k, actor, self.actors, w)
                feat.update(actor=actor, part=limb, motion=round(mot, 3), anchor='pose',
                            score=round(score(feat, mot), 4), status='needs_review')
                out.append(feat)
        # 관절 없는 인물색의 큰 덩어리: 화면 밖 인물의 팔다리 진입(예: 거대 발차기).
        for actor, m in masks.items():
            if actor in acts:
                continue
            n, lab, stats, _ = cv2.connectedComponentsWithStats(m, 8)
            for i in range(1, n):
                if stats[i, 4] < p['no_pose_area'] * H * W:
                    continue
                x, y, w_, h_, _ = stats[i]
                comp = (lab == i).astype(np.uint8)
                c = (x + w_ / 2, y + h_ / 2)
                feat = window_features(gray, comp, c, max(w_, h_), np.zeros_like(comp), scale)
                if feat is None:
                    continue
                feat.update(actor=actor, part='unknown', motion=None, anchor='no_pose',
                            score=round(score(feat, p['motion_ref']), 4), status='needs_review')
                out.append(feat)
        return sorted(out, key=lambda c: -c['score'])


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--frames', type=Path, required=True)
    ap.add_argument('--rtmw', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--source-start', type=int, default=0)
    ap.add_argument('--rtmw-y-offset', type=int, default=63)
    a = ap.parse_args()
    dest = a.output.resolve()
    if dest == ROOT or ROOT in dest.parents or dest.exists():
        ap.error('새 비공개 출력 경로 필요')
    sc = Scanner(a.frames, load_rtmw(a.rtmw, a.rtmw_y_offset), a.source_start)
    rows = []
    for f in sorted(sc.files):
        rows.append(dict(source_index=f, file=sc.files[f].name, candidates=sc.scan_frame(f)))
    dest.mkdir(parents=True)
    rep = dict(schema='smear-candidate-scan/1', variant='limb-anchored-v2', params=PARAMS, frames=len(rows),
               candidate_regions=sum(len(r['candidates']) for r in rows), semantic_smear_detection_verified=False,
               probability_calibrated=False, training_ready=False, rows=rows)
    (dest / 'candidates.private.json').write_text(json.dumps(rep, ensure_ascii=False, indent=1))
    print({k: v for k, v in rep.items() if k not in ('rows', 'params')})


if __name__ == '__main__':
    main()
