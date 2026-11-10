"""원본 인물색이 받쳐 주지 않는 스틱맨 조각을 숨긴다(자동 가시성, 2026-11-10).

10초본에서는 '없는 부위를 그리지 않기'를 장마다 손으로(partials/visible_views) 처리했다. 새 구간 근접
장면에서 자동 추출이 머리·몸통·다리를 지어내는 문제가 그대로 반복되어 공통 규칙으로 옮긴다.

규칙(측정, 해부학 정답 아님):
- 조각 선 위 표본점 중 화면 안 점이 충분할 때만 판정한다(틀 밖 좌표는 원래 허용).
- 선 조각: 화면 안 표본점이 그 인물색(팽창 마스크)에 닿는 비율 < line_min 이면 숨김.
- 머리 원: 원 안 화소 중 인물색 비율 < head_min 이면 숨김.
- body_gate: 머리나 몸통이 받쳐지지 않는 장(몸을 지어낸 장)에서만 숨긴다. 승인 10초에 조건 없이 켜면
  480 중 96건·166조각(대부분 빠른 아래팔)을 지워 과잉이었다(11-10 측정).
- protected={(장, 인물)}: 사람이 지정한 장(partials/visible_views)은 건드리지 않는다.
숨긴 조각은 같은11객체 틀에서 Color만 숨겨지므로 연결/편집 구조는 그대로다.
"""
import numpy as np

SEGMENTS = {1: ('head_t', 'head_b'), 2: ('neck', 'pelvis'), 3: ('elb_r', 'neck'), 4: ('wri_r', 'elb_r'),
            5: ('elb_l', 'neck'), 6: ('wri_l', 'elb_l'), 7: ('pelvis', 'kne_r'), 8: ('kne_r', 'ank_r'),
            9: ('pelvis', 'kne_l'), 10: ('kne_l', 'ank_l')}


def actor_masks(rgb, dilate=13):
    import cv2
    a = rgb.astype(np.float32)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    s = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)[..., 1]
    raw = {'red': (r > 1.22 * g) & (r > 1.10 * b) & (r > 45) & (s > 45),
           'blue': (b > 1.13 * r) & (g > 1.06 * r) & (b > 1.04 * g) & (b > 40) & (s > 40)}
    k = np.ones((dilate, dilate), np.uint8)
    return {c: cv2.dilate(m.astype(np.uint8), k) > 0 for c, m in raw.items()}


def segment_support(mask, p, q, samples=32, min_inside=8):
    h, w = mask.shape
    t = np.linspace(0, 1, samples)
    pts = (np.asarray(p, float)[None] * (1 - t[:, None]) + np.asarray(q, float)[None] * t[:, None]).round().astype(int)
    inside = (pts[:, 0] >= 0) & (pts[:, 0] < w) & (pts[:, 1] >= 0) & (pts[:, 1] < h)
    if inside.sum() < min_inside:
        return None
    return float(mask[pts[inside, 1], pts[inside, 0]].mean())


def head_support(mask, head_t, head_b, min_inside=0.5):
    h, w = mask.shape
    c = (np.asarray(head_t, float) + np.asarray(head_b, float)) / 2
    r = max(float(np.linalg.norm(np.subtract(head_t, head_b))) / 2, 1.)
    yy, xx = np.ogrid[:h, :w]
    circ = (xx - c[0]) ** 2 + (yy - c[1]) ** 2 <= r * r
    if circ.sum() < min_inside * np.pi * r * r:
        return None
    return float(mask[circ].mean())


def auto_visibility(poses, frames, read_rgb, crop_y, protected=frozenset(), line_min=0.35, head_min=0.10, body_gate=True, min_torso=80.):
    """poses: 장 목록[{인물: 관절(원본 화소)}], read_rgb(n)->잘린 프레임 RGB(높이=원본-crop_y). 결과와 기록을 돌려준다."""
    import copy
    out = copy.deepcopy(poses)
    log = []
    for i, frame in enumerate(frames):
        row = out[i]
        if not any(j is not None and (frame, c) not in protected for c, j in row.items()):
            continue
        masks = actor_masks(read_rgb(frame))
        for actor, j in row.items():
            if j is None or (frame, actor) in protected or actor not in masks:
                continue
            m = masks[actor]
            if np.linalg.norm(np.subtract(j['neck'], j['pelvis'])) < min_torso:
                continue  # 먼 작은 인물은 색 영역이 가늘어 받침 판정이 틀린다(승인 10초 1080·1242 등에서 과잉 숨김)
            shift = lambda p: np.asarray(p, float) - [0, crop_y]
            visible = list(j.get('_visible_segments', range(1, 11)))
            hidden = {}
            for seg in list(visible):
                a, b = SEGMENTS[seg]
                if a not in j or b not in j:
                    continue
                sup = head_support(m, shift(j[a]), shift(j[b])) if seg == 1 else segment_support(m, shift(j[a]), shift(j[b]))
                if sup is not None and sup < (head_min if seg == 1 else line_min):
                    hidden[seg] = round(sup, 3)
            # 몸을 지어낸 장(머리나 몸통이 받쳐지지 않음)에서만 숨긴다. 정상 장의 빠른 팔다리(스미어 등)는 그대로 둔다.
            if body_gate and not ({1, 2} & set(hidden)):
                hidden = {}
            if hidden:
                j['_visible_segments'] = [s for s in visible if s not in hidden]
                log.append(dict(frame=frame, actor=actor, hidden=hidden, visible=list(j['_visible_segments'])))
    return out, log


def plan_from_report(report, scene):
    """stickman_clip 보고서의 auto_visibility 기록 → stickman_quality --visibility-plan 형식."""
    return dict(schema=1, start=scene['start'], end=scene['end'], source_sha256=scene.get('source_sha256'),
                events=[dict(actor=x['actor'], start=x['frame'], end=x['frame'], visible_segments=sorted(x['visible']))
                        for x in report.get('auto_visibility', [])])


if __name__ == '__main__':
    import json, sys
    report, scene, out = sys.argv[1:4]
    json.dump(plan_from_report(json.load(open(report)), json.load(open(scene))), open(out, 'w'), ensure_ascii=False)
