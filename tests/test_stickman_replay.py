import sys
import unittest
import tempfile
import zipfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from stickman_replay import replay,safe_relative


class TestReplay(unittest.TestCase):
    def test_bundle_cannot_escape_the_new_folder(self):
        for name in ['../outside','/outside',r'a\..\outside']:
            with self.assertRaises(ValueError):safe_relative(name)
        with tempfile.TemporaryDirectory() as d:
            bundle=Path(d)/'bad.zip'
            with zipfile.ZipFile(bundle,'w') as z:z.writestr('../outside','x')
            with self.assertRaises(ValueError):replay(bundle,Path(d)/'new')
            self.assertFalse((Path(d)/'outside').exists())

    def test_existing_folder_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):replay('absent.zip',d)
