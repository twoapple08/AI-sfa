"""Pipeline tools with a fake HTTP opener (no network)."""
import hashlib
import io
import json
import tempfile
import unittest
import urllib.parse
from pathlib import Path

from pipeline import collect_sakuga as cs
from pipeline import hwprofile

VIDEO = b'fake-video-bytes' * 100
POSTS = [{'id': i, 'md5': hashlib.md5(VIDEO).hexdigest(), 'file_url': f'https://files.example/{i}.mp4',
          'file_ext': 'mp4', 'file_size': len(VIDEO), 'width': 1280, 'height': 720, 'score': i,
          'rating': 's', 'created_at': 0, 'source': 'https://twitter.example', 
          'tags': 'yutaka_nakamura smears fighting some_show animated'} for i in range(1, 6)]
TAGS = [{'name': 'yutaka_nakamura', 'type': 1, 'count': 900}, {'name': 'smears', 'type': 0, 'count': 5000},
        {'name': 'fighting', 'type': 0, 'count': 8000}, {'name': 'some_show', 'type': 3, 'count': 40},
        {'name': 'animated', 'type': 5, 'count': 100000}]


class FakeResp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def fake_opener(req, timeout=0):
    url = req.full_url
    q = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
    if '/tag.json' in url:
        return FakeResp(json.dumps(TAGS).encode())
    if '/post.json' in url:
        page, limit = int(q['page'][0]), int(q['limit'][0])
        return FakeResp(json.dumps(POSTS[(page - 1) * limit: page * limit]).encode())
    return FakeResp(VIDEO)


class Collector(unittest.TestCase):
    def test_tags_posts_resume_media_stats(self):
        client = cs.Client(delay=0, opener=fake_opener)
        with tempfile.TemporaryDirectory() as d:
            cs.cmd_tags(client, d)
            cs.cmd_posts(client, d, 'fighting', max_posts=3, per_page=2)
            cs.cmd_posts(client, d, 'fighting', max_posts=10, per_page=2)     # resume, no duplicates
            posts = list(cs.iter_posts(d))
            self.assertEqual([p['id'] for p in posts], [1, 2, 3, 4, 5])
            self.assertEqual(posts[0]['typed_tags']['artist'], ['yutaka_nakamura'])
            self.assertEqual(posts[0]['typed_tags']['copyright'], ['some_show'])
            cs.cmd_media(client, d, max_files=2)
            cs.cmd_media(client, d, max_files=10)                               # skips verified files
            media = sorted(p.name for p in Path(d, 'media').glob('*.mp4'))
            self.assertEqual(media, [f'{i}.mp4' for i in range(1, 6)])
            side = json.loads(Path(d, 'media', '1.json').read_text(encoding='utf-8'))
            self.assertNotIn('copyright', side['training_tags'])               # work titles excluded
            rows = Path(d, 'index.csv').read_text(encoding='utf-8-sig').splitlines()
            self.assertEqual(len(rows), 6)
            cs.cmd_stats(d)
            stats = json.loads(Path(d, 'stats.json').read_text(encoding='utf-8'))
            self.assertEqual(stats['top']['artist'][0], ['yutaka_nakamura', 5])

    def test_md5_mismatch_is_rejected(self):
        bad = [dict(POSTS[0], md5='0' * 32)]
        client = cs.Client(delay=0, opener=fake_opener)
        with tempfile.TemporaryDirectory() as d:
            Path(d, 'posts.jsonl').write_text(json.dumps(bad[0]) + '\n', encoding='utf-8')
            cs.cmd_media(client, d, max_files=5)
            self.assertEqual(list(Path(d, 'media').glob('*.mp4')), [])


class Hardware(unittest.TestCase):
    def test_tiers_follow_vram_not_names(self):
        self.assertEqual(hwprofile.tier_for(None, 16), 'cpu')
        self.assertEqual(hwprofile.tier_for(4.0, 16), 'low')
        self.assertEqual(hwprofile.tier_for(8.0, 32), 'mid')
        self.assertEqual(hwprofile.tier_for(16.0, 32), 'high')
        profile = hwprofile.detect('.')
        self.assertIn(profile['tier'], hwprofile.TIER_DEFAULTS)


if __name__ == '__main__':
    unittest.main()
