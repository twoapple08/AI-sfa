"""USB 꾸러미: 영상·제외 클립·임시 파일을 빼고 결과만 담는다."""
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'tools'))
import pack_usb


class PackUsb(unittest.TestCase):
    def test_results_only(self):
        with tempfile.TemporaryDirectory() as d:
            data = Path(d, 'data_sakuga')
            for rel in ['posts.jsonl', 'copyright_years.json', 'media/1.mp4', 'media/1.shots.json',
                        'media/1.pose.npz', 'media/2.mp4.part', 'media/3.tmp', 'excluded/old/4.mp4',
                        'excluded/old/4.shots.json', 'preview/1_test/a.sfa']:
                (data / rel).parent.mkdir(parents=True, exist_ok=True)
                (data / rel).write_bytes(b'x')
            n, _ = pack_usb.pack(data, Path(d, 'out.zip'))
            names = set(zipfile.ZipFile(Path(d, 'out.zip')).namelist())
            self.assertEqual(names, {'data_sakuga/posts.jsonl', 'data_sakuga/copyright_years.json',
                                     'data_sakuga/media/1.shots.json', 'data_sakuga/media/1.pose.npz',
                                     'data_sakuga/preview/1_test/a.sfa'})
            self.assertEqual(n, 5)
            self.assertFalse(Path(d, 'out.zip.part').exists())


if __name__ == '__main__':
    unittest.main()
