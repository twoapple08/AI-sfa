"""AMASS(SMPL-X) 묶음 → 몸 관절 3D 좌표(미터, Y 위, 30fps). 압축을 풀지 않고 tar에서 바로 읽는다.

사용: python tools/amass_joints.py <SMPLX_NEUTRAL.npz> <AMASS tar.bz2> <출력 폴더> [--fps 30]
출력: <출력>/<데이터셋>__<경로>.npz (pos [프레임, 22, 3] float32, names, parents, fps) — tools/cmu_amc.py와 같은 형식
관절은 SMPL-X 몸 22개(골반~손목). 정점은 계산하지 않고 관절 회귀 + 순운동학만 한다.
AMASS는 Z 위 좌표계라 (x, z, -y)로 바꿔 Y 위로 맞춘다. AMASS 원본은 저장소에 넣지 않는다.
"""
import argparse
import io
import os
import tarfile

import numpy as np
import torch
from smplx.lbs import batch_rigid_transform, batch_rodrigues, blend_shapes, vertices2joints

NAMES = ["pelvis", "left_hip", "right_hip", "spine1", "left_knee", "right_knee", "spine2", "left_ankle",
         "right_ankle", "spine3", "left_foot", "right_foot", "neck", "left_collar", "right_collar", "head",
         "left_shoulder", "right_shoulder", "left_elbow", "right_elbow", "left_wrist", "right_wrist"]
NJ = 22


class Body:
    def __init__(self, model_path):
        m = np.load(model_path, allow_pickle=True)
        self.v = torch.tensor(m["v_template"], dtype=torch.float64)[None]
        self.sd = torch.tensor(m["shapedirs"], dtype=torch.float64)
        self.jr = torch.tensor(m["J_regressor"], dtype=torch.float64)
        par = m["kintree_table"][0].astype(np.int64)
        par[0] = -1
        self.parents = torch.tensor(par)

    def joints(self, poses, trans, betas):
        n = len(poses)
        b = torch.tensor(betas, dtype=torch.float64)[None]
        vs = self.v + blend_shapes(b, self.sd[:, :, :b.shape[1]])
        J = vertices2joints(self.jr, vs).expand(n, -1, -1)
        rot = batch_rodrigues(torch.tensor(poses, dtype=torch.float64).reshape(-1, 3)).reshape(n, -1, 3, 3)
        Jt, _ = batch_rigid_transform(rot, J.contiguous(), self.parents, dtype=torch.float64)
        p = (Jt[:, :NJ] + torch.tensor(trans, dtype=torch.float64)[:, None]).numpy()
        return np.stack([p[..., 0], p[..., 2], -p[..., 1]], -1)  # Z 위 → Y 위


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("model")
    ap.add_argument("tar")
    ap.add_argument("out")
    ap.add_argument("--fps", type=float, default=30)
    a = ap.parse_args()
    body = Body(a.model)
    os.makedirs(a.out, exist_ok=True)
    parents = body.parents[:NJ].numpy()
    n = skip = 0
    with tarfile.open(a.tar, "r:bz2") as t:
        for mem in t:
            if not mem.name.endswith("_stageii.npz"):
                continue
            dst = os.path.join(a.out, mem.name[:-len("_stageii.npz")].replace("/", "__") + ".npz")
            if os.path.exists(dst):
                skip += 1
                continue
            d = np.load(io.BytesIO(t.extractfile(mem).read()), allow_pickle=True)
            fr = float(d["mocap_frame_rate"])
            step = max(1, round(fr / a.fps))
            poses, trans = d["poses"][::step], d["trans"][::step]
            if len(poses) < 2:
                continue
            pos = np.concatenate([body.joints(poses[i:i + 2000], trans[i:i + 2000], d["betas"])
                                  for i in range(0, len(poses), 2000)]).astype(np.float32)
            np.savez_compressed(dst, pos=pos, names=np.array(NAMES), parents=parents, fps=fr / step)
            n += 1
            if n % 200 == 0:
                print(n, flush=True)
    print("완료", n, "건너뜀", skip)


if __name__ == "__main__":
    main()
