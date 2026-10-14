import unittest
from native_timing import export_plan, sample_at


class NativeTimingTests(unittest.TestCase):
    def test_matches_two_app_exports(self):
        for source, output, duration in [(122, 610, 122/12), (90, 450, 7.5)]:
            plan = export_plan(source, 60, 12)
            self.assertEqual(plan['output_frames'], output)
            self.assertEqual(plan['output_fps'], 60)
            self.assertAlmostEqual(plan['encoded_duration_seconds'], duration)

    def test_equal_rates_have_no_intermediates(self):
        self.assertEqual(export_plan(48, 24, 24)['output_frames'], 48)
        self.assertFalse(export_plan(48, 24, 24)['interpolation_enabled'])

    def test_lower_tween_rate_uses_native_original_rate(self):
        plan = export_plan(48, 12, 24)
        self.assertEqual(plan['output_fps'], 24)
        self.assertEqual(plan['output_frames'], 48)

    def test_intermediate_and_last_frame_hold(self):
        self.assertAlmostEqual(sample_at(122, 60, 12, 1)['alpha'], 0.2)
        last = sample_at(122, 60, 12, 609)
        self.assertEqual((last['from_frame'], last['to_frame']), (121, 121))
        self.assertTrue(last['hold'])

    def test_rounding_and_invalid_input(self):
        self.assertEqual(export_plan(5, 30, 12)['output_frames'], 13)
        for value in [0, -1, True]:
            with self.assertRaises(ValueError):
                export_plan(value, 60, 12)
        with self.assertRaises(ValueError):
            sample_at(5, 60, 12, 25)
