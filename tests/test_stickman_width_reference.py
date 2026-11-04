import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from stickman_width_reference import reference_radius


class TestWidthReference(unittest.TestCase):
    def test_receding_reference_cannot_grow_back_to_a_fixed_missing_width(self):
        keys={'10':80,'14':40,'18':20}
        values=[reference_radius(f,keys,.6) for f in range(10,19)]
        self.assertTrue(all(a>=b for a,b in zip(values,values[1:])))
        self.assertEqual(values[-1],12)
        self.assertNotIn(50,values)

    def test_unknown_width_is_rejected_instead_of_defaulting_to_50(self):
        with self.assertRaises(ValueError):reference_radius(10,{})
        with self.assertRaises(ValueError):reference_radius(9,{'10':20,'12':10})
        with self.assertRaises(ValueError):reference_radius(10,{'10':float('nan')})
