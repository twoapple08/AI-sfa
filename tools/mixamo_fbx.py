"""Mixamo FBX(캐릭터 없음) → 공통 18관절 3D 좌표(미터, Y 위, 30fps). Blender 파이썬 모듈(bpy)로 읽는다.

사용(bpy가 깔린 Python 3.11): python tools/mixamo_fbx.py <FBX 폴더> <출력 폴더> [--index mixamo_index.csv]
출력: <출력>/<파일이름>.npz (pos [프레임, 18, 3] float32, names, parents, fps) — tools/mocap_unify.py 공통 18관절 순서
- 관절 위치 = 뼈 머리(head)의 월드 좌표. Mixamo 뼈 이름(mixamorig:Hips 등)으로 대응한다.
- Blender는 Z 위 → (x, z, -y)로 Y 위. 단위는 키(머리-발목)로 확인해 cm이면 0.01배.
Mixamo 파일은 개인용 학습 자료이고 저장소에 넣지 않는다.
"""
import argparse
import glob
import os
import sys

import numpy as np

JOINTS = ["pelvis", "spine", "neck", "head", "l_shoulder", "r_shoulder", "l_elbow", "r_elbow", "l_wrist", "r_wrist",
          "l_hip", "r_hip", "l_knee", "r_knee", "l_ankle", "r_ankle", "l_toe", "r_toe"]
PARENTS = [-1, 0, 1, 2, 2, 2, 4, 5, 6, 7, 0, 0, 10, 11, 12, 13, 14, 15]
BONES = ["Hips", "Spine1", "Neck", "Head", "LeftArm", "RightArm", "LeftForeArm", "RightForeArm", "LeftHand",
         "RightHand", "LeftUpLeg", "RightUpLeg", "LeftLeg", "RightLeg", "LeftFoot", "RightFoot", "LeftToeBase",
         "RightToeBase"]


def find_bone(pose_bones, name):
    for pb in pose_bones:
        n = pb.name.split(":")[-1]
        if n == name or n.endswith("_" + name) or n == "mixamorig" + name:
            return pb
    return None


def convert(path):
    import bpy
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=path, automatic_bone_orientation=False)
    arm = next((o for o in bpy.context.scene.objects if o.type == "ARMATURE"), None)
    if arm is None or arm.animation_data is None or arm.animation_data.action is None:
        return None, "뼈대·동작 없음"
    pbs = [find_bone(arm.pose.bones, b) for b in BONES]
    if any(p is None for p in pbs):
        return None, "뼈 이름 불일치: " + ",".join(b for b, p in zip(BONES, pbs) if p is None)
    sc = bpy.context.scene
    f0, f1 = (int(round(v)) for v in arm.animation_data.action.frame_range)
    fps = sc.render.fps / sc.render.fps_base
    out = []
    for f in range(f0, f1 + 1):
        sc.frame_set(f)
        mw = arm.matrix_world
        out.append([list(mw @ pb.head) for pb in pbs])
    P = np.array(out, np.float32)
    P = np.stack([P[..., 0], P[..., 2], -P[..., 1]], -1)  # Z 위 → Y 위
    h = np.median(P[:, 3, 1] - np.minimum(P[:, 14, 1], P[:, 15, 1]))
    if h > 10:  # cm 단위
        P *= 0.01
    if abs(fps - 30) > 0.5:  # 30fps로 다시 뽑기(선형 보간)
        t = np.arange(len(P)) / fps
        tn = np.arange(0, t[-1] + 1e-9, 1 / 30)
        P = np.stack([[np.interp(tn, t, P[:, j, k]) for k in range(3)] for j in range(18)], -1).transpose(1, 0, 2)
        fps = 30.0
    return P.astype(np.float32), fps


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("out")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    files = sorted(glob.glob(os.path.join(a.src, "**", "*.fbx"), recursive=True))
    ok = bad = 0
    for k, f in enumerate(files):
        dst = os.path.join(a.out, os.path.splitext(os.path.basename(f))[0] + ".npz")
        if os.path.exists(dst):
            continue
        try:
            P, info = convert(f)
        except Exception as e:  # 깨진 파일 하나로 전체가 멈추지 않게
            P, info = None, f"오류 {e}"
        if P is None or len(P) < 2:
            bad += 1
            print("건너뜀", os.path.basename(f), info, file=sys.stderr)
            continue
        np.savez_compressed(dst, pos=P, names=np.array(JOINTS), parents=np.array(PARENTS), fps=info)
        ok += 1
        if (k + 1) % 100 == 0:
            print(k + 1, "/", len(files), flush=True)
    print("완료", ok, "실패", bad)


if __name__ == "__main__":
    main()
