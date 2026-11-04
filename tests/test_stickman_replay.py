import sys
import unittest
import tempfile
import zipfile
import os
import json
import hashlib
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

    def test_relative_folder_regenerates_instead_of_reusing_the_bundled_output(self):
        script=b"from pathlib import Path\nimport zipfile\np=Path(__file__).parent/'output.sfa'\nassert not p.exists()\nwith zipfile.ZipFile(p,'w') as z:z.writestr('output.xml','<Sequence/>')\n"
        stale=b'not the generated SFA'
        manifest={'files':{'build.py':hashlib.sha256(script).hexdigest(),
                           'output.sfa':hashlib.sha256(stale).hexdigest()},
                  'replay':{'code_sha256':{},'producer':'build.py','output':'output.sfa',
                            'expected_xml_sha256':hashlib.sha256(b'<Sequence/>').hexdigest()}}
        with tempfile.TemporaryDirectory() as d:
            bundle=Path(d)/'input.zip'
            with zipfile.ZipFile(bundle,'w') as z:
                z.writestr('build.py',script);z.writestr('output.sfa',stale)
                z.writestr('manifest.json',json.dumps(manifest))
            previous=Path.cwd()
            try:
                os.chdir(d);report=replay(bundle,'fresh')
            finally:os.chdir(previous)
            self.assertTrue(report['xml_identical']);self.assertEqual(report['exit_code'],0)

    def test_manual_and_inferred_inputs_cannot_be_silently_substituted(self):
        with tempfile.TemporaryDirectory() as d:
            bundle=Path(d)/'changed.zip';data=b'changed manual keys'
            manifest={'files':{'keys.json':hashlib.sha256(data).hexdigest()},
                'replay':{'locked_decisions':[{'path':'keys.json','kind':'manual_pose',
                            'sha256':hashlib.sha256(b'approved keys').hexdigest()}]}}
            with zipfile.ZipFile(bundle,'w') as z:
                z.writestr('keys.json',data);z.writestr('manifest.json',json.dumps(manifest))
            with self.assertRaises(ValueError):replay(bundle,Path(d)/'new')
