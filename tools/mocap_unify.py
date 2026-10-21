"""모캡 4종(CMU·LaFAN1·Bandai·AMASS) 관절 npz를 공통 18관절로 통일하고 동작 목록을 만든다.

사용: python tools/mocap_unify.py <scratch data 폴더> <출력 폴더> <목록 csv>
입력(각 tools/cmu_amc.py·bvh_pos.py·amass_joints.py 출력): cmu/npz30, lafan1_npz30, bandai_npz30, amass/npz30
     CMU 설명은 cmu/index.json(trials.desc)에서 읽는다.
출력: <출력>/<자료>.npz (pos [전체 프레임, 18, 3] float16, start·length [클립], clip 이름, fps 30)
      목록 csv: 자료, 클립, 프레임, 초, 설명, 태그(키워드로 붙인 공격·피격·넘어짐 등), 키(m)

관절 대응은 '관절 위치'끼리 맞춘다. BVH는 관절 이름 위치가 그 뼈의 시작점이고, CMU 변환(cmu_amc.py)은 뼈 끝점이다.
척추·목·머리는 자료마다 뼈 나눔이 달라 근사 대응이다(키·팔다리 길이 비교에는 영향 없음).
"""
import csv
import glob
import json
import os
import re
import sys

import numpy as np

JOINTS = ["pelvis", "spine", "neck", "head", "l_shoulder", "r_shoulder", "l_elbow", "r_elbow", "l_wrist", "r_wrist",
          "l_hip", "r_hip", "l_knee", "r_knee", "l_ankle", "r_ankle", "l_toe", "r_toe"]
PARENTS = [-1, 0, 1, 2, 2, 2, 4, 5, 6, 7, 0, 0, 10, 11, 12, 13, 14, 15]

MAP = {
    # CMU: cmu_amc.py는 뼈 끝점을 그 뼈 이름으로 저장한다(예: lfemur 끝 = 무릎). 손목은 lradius 다음 lwrist 끝
    "cmu": ["root", "lowerback", "lowerneck", "upperneck", "lclavicle", "rclavicle", "lhumerus", "rhumerus",
            "lwrist", "rwrist", "lhipjoint", "rhipjoint", "lfemur", "rfemur", "ltibia", "rtibia", "lfoot", "rfoot"],
    "lafan1": ["Hips", "Spine1", "Neck", "Head", "LeftArm", "RightArm", "LeftForeArm", "RightForeArm", "LeftHand",
               "RightHand", "LeftUpLeg", "RightUpLeg", "LeftLeg", "RightLeg", "LeftFoot", "RightFoot", "LeftToe",
               "RightToe"],
    "bandai": ["Hips", "Spine", "Neck", "Head", "UpperArm_L", "UpperArm_R", "LowerArm_L", "LowerArm_R", "Hand_L",
               "Hand_R", "UpperLeg_L", "UpperLeg_R", "LowerLeg_L", "LowerLeg_R", "Foot_L", "Foot_R", "Toes_L",
               "Toes_R"],
    "amass": ["pelvis", "spine2", "neck", "head", "left_shoulder", "right_shoulder", "left_elbow", "right_elbow",
              "left_wrist", "right_wrist", "left_hip", "right_hip", "left_knee", "right_knee", "left_ankle",
              "right_ankle", "left_foot", "right_foot"],
}
DIRS = {"cmu": "cmu/npz30", "lafan1": "lafan1_npz30", "bandai": "bandai_npz30", "amass": "amass/npz30"}

TAGS = [  # (태그, 정규식) — 설명·파일 이름에 대해 대소문자 무시
    ("공격", r"punch|kick|strike|jab|hook|uppercut|slash|sword|attack|karate|martial|boxing|boxer|fight|hit|elbow|knee_|stab"),
    ("방어·회피", r"block|dodge|duck|guard|evade|parry"),
    ("피격·넘어짐", r"fall|stumble|push|hit_|knock|getup|get_up|get up|lie|collapse|die"),
    ("점프·공중", r"jump|hop|leap|flip|cartwheel|somersault|vault"),
    ("달리기", r"run|sprint|dash|jog"),
    ("걷기", r"walk|step"),
    ("구르기·바닥", r"roll|crawl|ground|floor|sit"),
    ("춤", r"dance|salsa|ballet|breakdance"),
    ("던지기·잡기", r"throw|catch|grab|pick|lift|carry"),
    ("감정 표현", r"angry|happy|sad|proud|tired|active|feminine|masculine|chimpira|musical|old|youthful|elderly"),
]


def tags(text):
    return [t for t, p in TAGS if re.search(p, text, re.I)]


def main():
    root, out, lst = sys.argv[1:4]
    os.makedirs(out, exist_ok=True)
    cmu_desc = {}
    p = os.path.join(root, "cmu/index.json")
    if os.path.exists(p):
        cmu_desc = {k: v["desc"] for k, v in json.load(open(p))["trials"].items()}
    rows = []
    for src, d in DIRS.items():
        files = sorted(glob.glob(os.path.join(root, d, "*.npz")))
        if not files:
            continue
        chunks, starts, lens, names = [], [], [], []
        total = 0
        for f in files:
            z = np.load(f)
            nm = list(z["names"])
            idx = [nm.index(j) for j in MAP[src]]
            pos = z["pos"][:, idx].astype(np.float32)
            if len(pos) < 2 or not np.isfinite(pos).all():
                continue
            clip = os.path.basename(f)[:-4]
            chunks.append(pos.astype(np.float16))
            starts.append(total)
            lens.append(len(pos))
            names.append(clip)
            total += len(pos)
            desc = cmu_desc.get(clip, "") if src == "cmu" else clip.replace("__", "/")
            head = pos[:, 3, 1] - np.minimum(pos[:, 14, 1], pos[:, 15, 1])
            rows.append([src, clip, len(pos), round(len(pos) / 30, 1), desc, ";".join(tags(desc + " " + clip)),
                         round(float(np.median(head)), 2)])
        np.savez_compressed(os.path.join(out, src + ".npz"), pos=np.concatenate(chunks), start=np.array(starts),
                            length=np.array(lens), clip=np.array(names), joints=np.array(JOINTS),
                            parents=np.array(PARENTS), fps=30)
        print(src, len(names), "클립", total, "프레임", round(total / 30 / 3600, 2), "시간", flush=True)
    with open(lst, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["자료", "클립", "프레임", "초", "설명", "태그", "머리_발목_높이m"])
        w.writerows(rows)


if __name__ == "__main__":
    main()
