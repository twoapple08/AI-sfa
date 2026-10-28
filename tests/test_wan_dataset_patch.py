import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))
from wan_dataset_patch import person_sentence  # noqa: E402


class PersonSentenceTest(unittest.TestCase):
    def t(self, **kw):
        base = {"clip": "x", "person": "medium", "kind": "body", "frames": "all", "fx_link": "none", "unsure": False}
        base.update(kw)
        return person_sentence(base)

    def test_none_and_unsure_add_nothing(self):
        self.assertEqual(self.t(person="none", kind="none"), "")
        self.assertEqual(self.t(unsure=True), "")

    def test_close_up_parts(self):
        self.assertEqual(self.t(person="large", kind="face"), "A close-up of a character's face is visible.")
        self.assertEqual(self.t(person="large", kind="robot_part", fx_link="strike"), "A close-up of a giant robot's arm strikes with the impact.")

    def test_size_plural_brief_and_links(self):
        self.assertEqual(self.t(person="small"), "A small, distant character is visible.")
        self.assertEqual(self.t(kind="several", frames="some"), "Several characters are briefly visible.")
        self.assertEqual(self.t(person="large", kind="robot", fx_link="emits"), "A giant robot emits the effect.")
        self.assertEqual(self.t(kind="creature", fx_link="hit", frames="some"), "A creature is briefly hit by the effect.")


if __name__ == '__main__':
    unittest.main()
