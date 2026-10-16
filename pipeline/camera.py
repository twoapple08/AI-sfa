#!/usr/bin/env python3
"""Per-frame 2D camera (zoom / pan / roll) of a shot, estimated from the background.

Each consecutive frame pair is matched with ORB features outside the people (their boxes are
masked), and one similarity transform is fitted with RANSAC. Chaining them gives C_t, a 2x3
matrix mapping world coordinates (= the shot's first frame) to screen pixels of frame t.
Characters are then cleaned in world coordinates, so a zoom-out does not look like the body
growing and a limb hidden by the frame in a close-up can borrow its shape from a wide frame.
Held frames and flat backgrounds (too few features) give identity steps: no camera move assumed.
"""
import cv2
import numpy as np

WIDTH = 320          # analysis width
MIN_INLIERS = 15
PAD = 0.15           # mask people with boxes grown by 15%


def _step(ga, gb, mask):
    orb = cv2.ORB_create(800)
    ka, da = orb.detectAndCompute(ga, mask)
    kb, db = orb.detectAndCompute(gb, mask)
    if da is None or db is None or len(ka) < MIN_INLIERS or len(kb) < MIN_INLIERS:
        return None
    matches = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True).match(da, db)
    if len(matches) < MIN_INLIERS:
        return None
    src = np.float32([ka[m.queryIdx].pt for m in matches])
    dst = np.float32([kb[m.trainIdx].pt for m in matches])
    m, inl = cv2.estimateAffinePartial2D(src, dst, method=cv2.RANSAC, ransacReprojThreshold=1.5)
    if m is None or inl is None or int(inl.sum()) < MIN_INLIERS:
        return None
    return m


def _mask(shape, boxes, scale):
    h, w = shape
    mask = np.full((h, w), 255, np.uint8)
    for x0, y0, x1, y1 in boxes:
        px, py = PAD * (x1 - x0), PAD * (y1 - y0)
        a = (int(max(0, (x0 - px) * scale)), int(max(0, (y0 - py) * scale)))
        b = (int(min(w - 1, (x1 + px) * scale)), int(min(h - 1, (y1 + py) * scale)))
        cv2.rectangle(mask, a, b, 0, -1)
    return mask


def estimate(frames, boxes_per_frame, full_width):
    """frames: BGR or gray images of one shot (any size), boxes_per_frame: person boxes in full-res
    pixels per frame. Returns [C_t] as 2x3 float arrays (world -> full-res screen), C_0 = identity."""
    grays = [f if f.ndim == 2 else cv2.cvtColor(f, cv2.COLOR_BGR2GRAY) for f in frames]
    r = grays[0].shape[1] / full_width                       # analysis px per full-res px
    S, S_inv = np.diag([r, r, 1.0]), np.diag([1 / r, 1 / r, 1.0])
    cams, cum = [np.eye(3)[:2].copy()], np.eye(3)
    for t in range(1, len(grays)):
        step = None
        if np.count_nonzero(cv2.absdiff(grays[t - 1], grays[t]) > 20) > 0.0003 * grays[t].size:
            mask = _mask(grays[t].shape, list(boxes_per_frame[t - 1]) + list(boxes_per_frame[t]), r)
            step = _step(grays[t - 1], grays[t], mask)
        m = np.eye(3) if step is None else S_inv @ np.vstack([step, [0, 0, 1]]) @ S
        cum = m @ cum
        cams.append(cum[:2].copy())
    return cams


def scale_of(c):
    return float(np.hypot(c[0][0], c[1][0]))


def to_world(c, pts):
    """Screen points (N,2) of the frame with camera c -> world."""
    m = np.vstack([np.asarray(c, float), [0, 0, 1]])
    inv = np.linalg.inv(m)
    p = np.asarray(pts, float)
    return p @ inv[:2, :2].T + inv[:2, 2]


def to_screen(c, pts):
    c = np.asarray(c, float)
    return np.asarray(pts, float) @ c[:, :2].T + c[:, 2]
