import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))
from caption_window import _frame_refs, window_caption  # noqa: E402


def shot(cap, targets, last=30, cuts=(0,), rhythm=None):
    return {'shot': 'sx', 'cuts': list(cuts), 'caption_en': cap,
            'segments': [{'frames': [0, last], 'camera': ['고정'], 'relation': '없음', 'targets': targets,
                          'rhythm': rhythm or [[0, last, '1s']]}]}


def tgt(name, phases, color=('노랑',)):
    return {'target': name, 'phases': [{'frames': list(f), 'phase': p} for f, p in phases], 'shape': [], 'change': [],
            'color': list(color), 'visibility': '보임'}


class WindowCaptionTest(unittest.TestCase):
    # GPT 토론 2차 예: 빔 3–12, 연기 10–20을 조각 8–17로 자르면 빔은 이미 진행 중(0–4), 연기는 2–9에 보이고 조각 뒤로 이어짐
    def test_gpt_example(self):
        g = shot('nkmr_fx, A yellow beam fires from 3 through 12, then smoke billows at 10-20. Ones; fixed camera, one cut.',
                 [tgt('빔', [((3, 12), '발생')]), tgt('연기', [((10, 20), '팽창')], ('회색',))])
        c = window_caption(g, g['caption_en'], 8, 17)
        self.assertIn('Yellow beam is already visible at 0-4', c)
        self.assertIn('Gray smoke expands at 2-9, continuing beyond the window', c)
        self.assertNotIn('from 0', c)  # 예전 rewrite의 '발생처럼 읽히는' 결함
        self.assertNotIn('then smoke', c)  # 조각 밖 번호가 낀 GPT 문장은 통째로 뺌

    def test_numbers_stay_inside_window(self):
        g = shot('nkmr_fx, Flash at 2-5 precedes mouth cut 29. Hold 27-28 lingers. Ones; one cut.',
                 [tgt('섬광', [((2, 5), '정점'), ((6, 30), '잔류')])], cuts=(0, 29),
                 rhythm=[[0, 26, '1s'], [27, 28, '홀드2'], [29, 30, '1s']])
        for w0, w1 in ((0, 16), (8, 24), (14, 30)):
            c = window_caption(g, g['caption_en'], w0, w1)
            refs, lens = _frame_refs(c)
            self.assertTrue(all(0 <= a <= b <= w1 - w0 for _, a, b in refs), (w0, w1, c))
            self.assertNotIn('mouth cut', c if w1 < 29 else '')

    def test_hold_length_is_intersection(self):
        g = shot('nkmr_fx, A long hold at 0-30. One cut.', [], rhythm=[[0, 30, '홀드31']])
        c = window_caption(g, g['caption_en'], 8, 24)
        self.assertIn('17-frame portion of an ongoing drawing hold at 0-16, continuing beyond the window', c)
        self.assertIn('No visible effects', c)

    def test_whole_shot_keeps_gpt_caption(self):
        g = shot('nkmr_fx, Yellow flash at 0-4 fades by 12. Ones; fixed camera, one cut.', [tgt('섬광', [((0, 12), '발생')])], last=19)
        self.assertEqual(window_caption(g, g['caption_en'], 0, 16), g['caption_en'])

    def test_last_visible_frame(self):
        g = shot('nkmr_fx, Dust rises at 0-30.', [tgt('불티', [((20, 30), '잔류')])])
        self.assertIn('through the last visible frame', window_caption(g, g['caption_en'], 10, 30))

    # GPT 표본 검토(3차) 회귀
    def test_rapid_expansion_wording(self):
        g = shot('nkmr_fx, Dust at 0-30.', [tgt('먼지', [((0, 5), '잔류'), ((12, 15), '급팽창')], ('회색',))])
        c = window_caption(g, g['caption_en'], 2, 18)
        self.assertIn('rapidly expands at 10-13', c)
        self.assertNotIn('bursts', c)

    def test_color_change_target_drops_colors_when_partial(self):
        t = tgt('불', [((0, 30), '잔류')], ('주황', '빨강'))
        t['change'] = ['색 단계 변화']
        g = shot('nkmr_fx, Glow at 0-30.', [t])
        self.assertNotIn('orange', window_caption(g, g['caption_en'], 0, 16))
        self.assertNotIn('shifting', window_caption(g, g['caption_en'], 0, 16))

    def test_simultaneous_camera(self):
        g = shot('nkmr_fx, Smoke at 0-30.', [])
        g['segments'][0]['camera'] = ['팬', '줌아웃']
        c = window_caption(g, g['caption_en'], 0, 16)
        self.assertIn('tracking with pullback', c)
        self.assertNotIn('then', c)

    def test_period_numbers_are_not_frames(self):
        g = shot('nkmr_fx, White flashes repeat every 8 frames, with pairs at cycle offsets 1-2 and 5-6. One cut.', [], last=19)
        self.assertIn('offsets 1-2 and 5-6', window_caption(g, g['caption_en'], 1, 17))

    def test_no_merge_across_cut(self):
        g = {'shot': 'sx', 'cuts': [0, 10], 'caption_en': 'nkmr_fx, Flash.', 'segments': [
            {'frames': [0, 9], 'camera': ['불명'], 'relation': '', 'rhythm': [[0, 9, '1s']], 'targets': [tgt('섬광', [((2, 9), '잔류')])]},
            {'frames': [10, 30], 'camera': ['줌인', '흔들림'], 'relation': '', 'rhythm': [[10, 30, '1s']], 'targets': [tgt('섬광', [((10, 30), '잔류')])]}]}
        c = window_caption(g, g['caption_en'], 0, 20)
        self.assertEqual(c.count('Yellow flash'), 2)
        self.assertIn('in the new shot', c)
        self.assertIn('camera unclear before 10, then shaky push-in from 10', c)

    def test_whole_shot_not_reused_when_dropped_frames_start_rhythm(self):
        g = shot('nkmr_fx, Flash at 2. Mainly ones, final two-frame hold; one cut.', [tgt('섬광', [((2, 27), '잔류')])], last=27,
                 rhythm=[[0, 25, '1s'], [26, 27, '홀드2']])
        self.assertNotEqual(window_caption(g, g['caption_en'], 0, 24), g['caption_en'])


if __name__ == '__main__':
    unittest.main()
