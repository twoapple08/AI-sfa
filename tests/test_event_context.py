import copy
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import event_context as E
import motion_tokens as MT
from motion_information_probe import synthetic

ROOT = Path(__file__).resolve().parents[1]


class EventContextTests(unittest.TestCase):
    def setUp(self):
        self.event = json.loads((ROOT / 'data/research/anime_smear_event_2026-11-06.json').read_text())
        self.context = E.create(self.event, 0, range(1376, 1408))

    def test_roundtrip_retains_unknowns_and_unconfirmed_evidence(self):
        self.context['event']['future_field'] = {'shape': None, 'note': '미확정'}
        out = E.loads(E.dumps(self.context))
        self.assertEqual(out, self.context)
        self.assertFalse(out['event']['training_ready'])
        self.assertFalse(out['event']['validation']['exact_smear_boundaries_verified'])

    def test_source_is_not_changed_when_view_is_sliced(self):
        part = E.slice_context(self.context, 14, 20)
        self.assertEqual(part['source_indices'], list(range(1390, 1396)))
        self.assertEqual(E.phase_runs(part), [dict(phase_index=0, local_inclusive=[0, 2]),
                         dict(phase_index=1, local_inclusive=[3, 3]), dict(phase_index=2, local_inclusive=[4, 5])])
        self.assertEqual(part['event'], self.event)
        self.assertEqual(E.concatenate([E.slice_context(self.context, 0, 17),
                                       E.slice_context(self.context, 17, 32)]), self.context)

    def test_new_interpolated_frame_stays_unknown(self):
        part = E.slice_context(self.context, 14, 16)
        out = E.remap(part, [0, None, 1])
        self.assertEqual(out['source_indices'], [1390, None, 1391])
        self.assertEqual(len(E.phase_runs(out)), 2)
        self.assertEqual(out['event'], self.event)

    def test_repeats_and_reversal_require_explicit_mapping(self):
        part = E.slice_context(self.context, 14, 17)
        self.assertEqual(E.remap(part, [2, 2, 1, 0])['source_indices'], [1392, 1392, 1391, 1390])

    def test_invalid_mapping_does_not_guess(self):
        for value in [-1, 32, True, 1.5]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                E.remap(self.context, [value])

    def test_mismatched_source_or_actor_cannot_be_merged(self):
        for field, value in [('actor_slot', 1), ('event', dict(self.event, case_id='other'))]:
            other = copy.deepcopy(self.context); other[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                E.concatenate([self.context, other])

    def test_invalid_source_bounds_or_nan_rejected(self):
        for change in ('bounds', 'nan', 'verified'):
            bad = copy.deepcopy(self.context)
            if change == 'bounds': bad['source_indices'][0] = 99999
            elif change == 'nan': bad['event']['uncertainty_score'] = float('nan')
            else: bad['alignment_status'] = 'verified'
            with self.subTest(change=change), self.assertRaises(ValueError):
                E.dumps(bad)

    def test_input_event_not_mutated(self):
        self.context['event']['uncertainties'].clear()
        self.assertTrue(self.event['uncertainties'])

    def test_legacy_timing_change_requires_explicit_realignment(self):
        motion = synthetic()  # 실제 원본의 자세가 아닌 운반 시험용12장
        context = E.create(self.event, 0, range(1390, 1402))
        self.assertTrue(E.check_motion_binding(context, motion))
        decoded = MT.decode(MT.encode(motion))
        self.assertEqual(decoded['frames'], 11)
        with self.assertRaises(ValueError):
            E.check_motion_binding(context, decoded)

    def test_unknown_or_duplicate_actor_rejected(self):
        for actors in [[{'slot': 1}], [{'slot': 0}, {'slot': 0}]]:
            with self.subTest(actors=actors), self.assertRaises(ValueError):
                E.check_motion_binding(self.context, {'frames': 32, 'actors': actors})


if __name__ == '__main__':
    unittest.main()
