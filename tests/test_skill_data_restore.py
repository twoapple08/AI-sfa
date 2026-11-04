import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import zipfile


SCRIPT = Path(__file__).resolve().parents[1]/'.claude/skills/stickman-extraction/scripts/restore_data.py'
spec = importlib.util.spec_from_file_location('skill_data_restore', SCRIPT)
restore = importlib.util.module_from_spec(spec)
spec.loader.exec_module(restore)


class SkillDataRestoreTests(unittest.TestCase):
    def test_hash_matching_import_ignores_renamed_download_and_wrong_file(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            (base/'download').mkdir()
            good = base/'download/renamed.bin'; good.write_bytes(b'good')
            (base/'download/wrong.bin').write_bytes(b'evil')
            manifest = {'artifacts': [dict(id='x',local_path='archives/x.zip',bytes=4,
                                         sha256=restore.digest(good),required=True)]}
            self.assertEqual(restore.import_files(manifest, base/'private', [base/'download']), ['x'])
            self.assertEqual(restore.inventory(manifest, base/'private')[0]['state'], 'verified')
            (base/'private/archives/x.zip').write_bytes(b'evil')
            with self.assertRaises(ValueError):
                restore.import_files(manifest, base/'private', [base/'download'])

    def test_zip_rejects_traversal_before_writing_and_rejects_tamper(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory); archive = base/'bad.zip'
            with zipfile.ZipFile(archive, 'w') as bundle:
                bundle.writestr('good.json', '{}'); bundle.writestr('../outside', 'bad')
            with self.assertRaises(ValueError):
                restore.extract_verified_zip(archive, restore.digest(archive), base/'output')
            self.assertFalse((base/'output').exists())
            with self.assertRaises(ValueError):
                restore.extract_verified_zip(archive, '0'*64, base/'output')

    def test_extract_replay_inputs_only_to_new_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory); archive = base/'ok.zip'
            with zipfile.ZipFile(archive, 'w') as bundle:
                bundle.writestr('keys/key.json', json.dumps({'manual': True}))
            restore.extract_verified_zip(archive, restore.digest(archive), base/'out')
            self.assertTrue(json.loads((base/'out/keys/key.json').read_text())['manual'])
            with self.assertRaises(ValueError):
                restore.extract_verified_zip(archive, restore.digest(archive), base/'out')

    def test_import_rejects_destination_symlink_escape(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory); (base/'private').mkdir(); (base/'outside').mkdir()
            (base/'private/archives').symlink_to(base/'outside', target_is_directory=True)
            with self.assertRaises(ValueError):
                restore.target(base/'private', 'archives/input.zip')


if __name__ == '__main__':
    unittest.main()
