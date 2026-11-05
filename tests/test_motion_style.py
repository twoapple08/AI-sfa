import os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))
import motion_style as MS

NAMES = ['head_t', 'head_b', 'neck', 'pelvis', 'elb_r', 'wri_r', 'elb_l', 'wri_l', 'kne_r', 'ank_r', 'kne_l', 'ank_l']


def make_ir(wri_keys, holds):
    """wri_keys[i] = i번째 그림의 오른 손목 x(%), holds[i] = 그 그림 유지 장 수. 나머지 관절은 고정."""
    frames, D, xs = 0, [], []
    for x, h in zip(wri_keys, holds):
        D.append([frames, frames + h - 1]); xs += [x] * h; frames += h
    base = dict(head_t=[50, 20], head_b=[50, 28], neck=[50, 30], pelvis=[50, 50], elb_r=[55, 35], elb_l=[45, 35],
                wri_l=[45, 45], kne_r=[52, 65], ank_r=[52, 80], kne_l=[48, 65], ank_l=[48, 80])
    J = {k: [list(base[k]) for _ in range(frames)] for k in NAMES if k != 'wri_r'}
    J['wri_r'] = [[x, 40] for x in xs]
    return dict(frames=frames, aspect=0.5625, actors=[dict(slot=0, joints=J, drawings=D)])


class MotionStyle(unittest.TestCase):
    def test_hold_counts_skip_ends(self):
        a = MS.measure(make_ir([60, 60.5, 61, 61.5, 62], [5, 2, 3, 2, 7]))['actors'][0]
        self.assertEqual(a['hold'], {'1': 0, '2': 2, '3': 1, '4+': 0})   # 첫·끝 그림(5·7장) 제외

    def test_anticipation_and_stop(self):
        # 손목이 뒤로(55) 빠졌다가 앞으로 크게(80) 치고, 그 그림을 5장 멈춘다
        a = MS.measure(make_ir([60, 60, 57, 55, 80, 80, 80], [2, 2, 2, 2, 5, 2, 2]))['actors'][0]
        self.assertGreaterEqual(a['anticipation']['with_antic'], 1)
        self.assertGreaterEqual(a['stop_after_fast']['with_stop'], 1)

    def test_no_backswing_no_anticipation(self):
        # 반례: 뒤로 빼지 않고 바로 치면 예비 동작이 없어야 한다. 유지 장이 모두 같으면 멈춤도 없어야 한다
        a = MS.measure(make_ir([60, 60, 60, 60, 80, 80, 80], [2, 2, 2, 2, 2, 2, 2]))['actors'][0]
        self.assertEqual(a['anticipation']['with_antic'], 0)
        self.assertEqual(a['stop_after_fast']['with_stop'], 0)

    def test_no_drawings(self):
        ir = make_ir([60], [10]); ir['actors'][0]['drawings'] = []
        self.assertEqual(MS.measure(ir)['actors'][0]['drawings'], 0)


if __name__ == '__main__':
    unittest.main()


class HoldDrawings(unittest.TestCase):
    def test_hold_copies_middle_and_keeps_original(self):
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))
        import motion_ir as M
        ir = make_ir([60, 70, 80], [3, 2, 3])
        # 부드러운 판처럼 그림 구간 안에서도 손목을 조금씩 움직여 둔다
        for n in range(ir['frames']): ir['actors'][0]['joints']['wri_r'][n][0] += n * 0.1
        a0 = ir['actors'][0]
        a0['thickness'] = [{'1': 1.0 + n} for n in range(ir['frames'])]
        a0['facing'] = [float(n) for n in range(ir['frames'])]
        h = M.hold_drawings(ir)['actors'][0]
        for s, e in a0['drawings']:
            m = (s + e) // 2
            for n in range(s, e + 1):
                self.assertEqual(h['joints']['wri_r'][n], a0['joints']['wri_r'][m])
                self.assertEqual(h['thickness'][n], a0['thickness'][m])
                self.assertEqual(h['facing'][n], a0['facing'][m])
        self.assertNotEqual(a0['joints']['wri_r'][0], a0['joints']['wri_r'][1])   # 원본은 바뀌지 않음

    def test_hold_without_drawings_is_identity(self):
        import motion_ir as M
        ir = make_ir([60, 70], [2, 2]); ir['actors'][0]['drawings'] = []
        self.assertEqual(M.hold_drawings(ir)['actors'][0]['joints'], ir['actors'][0]['joints'])
