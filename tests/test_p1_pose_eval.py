import json
import os
import sys
import tempfile
import unittest

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))
import p1_pose_eval  # noqa: E402


def write(root, model, frames):
    d = os.path.join(root, model)
    os.makedirs(d, exist_ok=True)
    clip = {"animator": "a", "id": "1", "start": 0}
    json.dump({"clip": clip, "frames": frames}, open(os.path.join(d, "a_1_0.json"), "w"))


class P1PoseEvalTest(unittest.TestCase):
    def test_agreement_swap_and_detection(self):
        rng = np.random.default_rng(0)
        base = np.c_[rng.uniform(100, 300, (17, 2)), np.ones(17)]
        moving = [base + [i * 2, 0, 0] for i in range(6)]
        swapped = [m.copy() for m in moving]
        for a, b in p1_pose_eval.LR:
            swapped[3][[a, b]] = swapped[3][[b, a]]
        with tempfile.TemporaryDirectory() as root:
            write(root, "good1", [[{"kp": m.tolist()}] for m in moving])
            write(root, "good2", [[{"kp": m.tolist()}] for m in moving])
            write(root, "good3", [[{"kp": m.tolist()}] for m in moving])
            write(root, "swapper", [[{"kp": m.tolist()}] for m in swapped])
            write(root, "empty", [[] for _ in moving])
            r = p1_pose_eval.eval_all(root)["result"]
        self.assertEqual(r["good1"]["_all"]["det"], 1.0)
        self.assertEqual(r["empty"]["_all"]["det"], 0.0)
        self.assertEqual(r["good1"]["_all"]["agree"], 1.0)
        self.assertEqual(r["good1"]["_all"]["swap"], 0.0)
        self.assertGreater(r["swapper"]["_all"]["swap"], 0.0)
        self.assertAlmostEqual(r["good1"]["_all"]["jitter"], 0.0)


if __name__ == "__main__":
    unittest.main()
