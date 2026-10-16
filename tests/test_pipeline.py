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
from pipeline import setup_env

VIDEO = b'fake-video-bytes' * 100
POSTS = [{'id': i, 'md5': hashlib.md5(VIDEO).hexdigest(), 'file_url': f'https://files.example/{i}.mp4',
          'file_ext': 'mp4', 'file_size': len(VIDEO), 'width': 1280, 'height': 720, 'score': i,
          'rating': 's', 'created_at': 0, 'source': 'https://twitter.example', 
          'tags': 'yutaka_nakamura smears fighting some_show animated kanada_light_flare presumed'} for i in range(1, 6)]
TAGS = [{'name': 'yutaka_nakamura', 'type': 1, 'count': 900}, {'name': 'smears', 'type': 0, 'count': 5000},
        {'name': 'fighting', 'type': 0, 'count': 8000}, {'name': 'some_show', 'type': 3, 'count': 40},
        {'name': 'animated', 'type': 0, 'count': 100000}, {'name': 'presumed', 'type': 5, 'count': 30000},
        {'name': 'kanada_light_flare', 'type': 4, 'count': 1300}]   # type numbers as on live Sakugabooru


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
            self.assertEqual(posts[0]['typed_tags']['technique'], ['kanada_light_flare'])
            self.assertEqual(posts[0]['typed_tags']['meta'], ['presumed'])
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
            self.assertEqual(stats['top']['technique'][0], ['kanada_light_flare', 5])
            self.assertIn('technique_tags', rows[0])

    def test_md5_mismatch_is_rejected(self):
        bad = [dict(POSTS[0], md5='0' * 32)]
        client = cs.Client(delay=0, opener=fake_opener)
        with tempfile.TemporaryDirectory() as d:
            Path(d, 'posts.jsonl').write_text(json.dumps(bad[0]) + '\n', encoding='utf-8')
            cs.cmd_media(client, d, max_files=5)
            self.assertEqual(list(Path(d, 'media').glob('*.mp4')), [])


    def test_media_match_filters_tags_and_rating(self):
        posts = [dict(POSTS[0], id=1), dict(POSTS[1], id=2, rating='e'),
                 dict(POSTS[2], id=3, tags=POSTS[2]['tags'] + ' cgi'), dict(POSTS[3], id=4, tags='running')]
        self.assertTrue(cs.post_matches(posts[0], 'fighting -cgi rating:s,q'))
        self.assertTrue(cs.post_matches(posts[0], 'rating:safe'))
        self.assertFalse(cs.post_matches(posts[1], 'rating:s'))
        self.assertFalse(cs.post_matches(posts[2], '-cgi'))
        self.assertFalse(cs.post_matches(posts[3], 'fighting'))
        posts.append(dict(POSTS[4], id=5, tags=POSTS[4]['tags'] + ' western'))     # cartoons never taken
        client = cs.Client(delay=0, opener=fake_opener)
        with tempfile.TemporaryDirectory() as d:
            Path(d, 'posts.jsonl').write_text(''.join(json.dumps(p) + '\n' for p in posts), encoding='utf-8')
            cs.cmd_media(client, d, max_files=10, match='fighting -cgi rating:s')
            self.assertEqual([p.name for p in Path(d, 'media').glob('*.mp4')], ['1.mp4'])
            cs.cmd_media(client, d, max_files=10)
            self.assertNotIn('5.mp4', [p.name for p in Path(d, 'media').glob('*.mp4')])
            cs.cmd_stats(d)
            stats = json.loads(Path(d, 'stats.json').read_text(encoding='utf-8'))
            self.assertEqual(stats['posts'], 4)


    def test_any_of_terms(self):
        self.assertTrue(cs.post_matches({'tags': 'impact_frames smears'}, '~fighting ~impact_frames -cgi'))
        self.assertFalse(cs.post_matches({'tags': 'character_acting'}, '~fighting ~impact_frames'))

    def test_old_titles_score_and_curate(self):
        years = {'old_show': [2004, 2005], 'franchise': [1979, 1980], 'new_season': [2016, 2016],
                 'long_runner': [1999, 9999]}
        new = {'id': 1, 'score': 50, 'width': 1920, 'height': 1080, 'tags': 'fighting',
               'typed_tags': {'copyright': ['franchise', 'new_season']}}
        old = dict(new, id=2, typed_tags={'copyright': ['old_show']})
        unknown_43 = dict(new, id=3, width=640, height=480, typed_tags={'copyright': ['nobody_knows']})
        low = dict(new, id=4, score=3)
        runner_hd = dict(new, id=5, typed_tags={'copyright': ['long_runner']})
        runner_43 = dict(runner_hd, width=640, height=480)
        self.assertFalse(cs.is_old(runner_hd, years))                    # recent episode of a long runner
        self.assertTrue(cs.is_old(runner_43, years))
        self.assertEqual(cs.post_year(new, years), 2016)                 # newest season wins
        self.assertEqual([cs.reject_reason(p, years, 'fighting', 10) for p in (new, old, unknown_43, low)],
                         [None, 'old', 'old', 'score'])
        with tempfile.TemporaryDirectory() as d:
            Path(d, 'posts.jsonl').write_text(''.join(json.dumps(p) + '\n' for p in (new, old, unknown_43, low)),
                                              encoding='utf-8')
            Path(d, cs.YEARS_FILE).write_text(json.dumps(years), encoding='utf-8')
            Path(d, 'media').mkdir()
            for i in (1, 2, 3, 4):
                Path(d, 'media', f'{i}.mp4').write_bytes(b'x')
                Path(d, 'media', f'{i}.shots.json').write_text('{}')
            cs.cmd_curate(d, 'fighting', 10)
            self.assertEqual(sorted(p.name for p in Path(d, 'media').iterdir()), ['1.mp4', '1.shots.json'])
            self.assertTrue(Path(d, 'excluded', 'old', '2.shots.json').exists())

    def test_anilist_batch_parsing(self):
        seen = []

        def fake_post(payload, delay):
            seen.append(payload['query'])
            return {'data': {'a0': {'media': [{'startDate': {'year': 2013}, 'endDate': {'year': 2023},
                                               'status': 'FINISHED'}]}, 'a1': {'media': []}}}
        out = cs.anilist_years(['attack_on_titan', 'no_such_show_series'], post=fake_post)
        self.assertEqual(out, {'attack_on_titan': [2013, 2023], 'no_such_show_series': None})
        self.assertIn('"attack on titan"', seen[0])
        self.assertIn('"no such show"', seen[0])                       # "_series" suffix dropped


class Hardware(unittest.TestCase):
    def test_tiers_follow_vram_not_names(self):
        self.assertEqual(hwprofile.tier_for(None, 16), 'cpu')
        self.assertEqual(hwprofile.tier_for(4.0, 16), 'low')
        self.assertEqual(hwprofile.tier_for(8.0, 32), 'mid')
        self.assertEqual(hwprofile.tier_for(16.0, 32), 'high')
        profile = hwprofile.detect('.')
        self.assertIn(profile['tier'], hwprofile.TIER_DEFAULTS)

    def test_torch_channel_follows_driver_and_architecture(self):
        self.assertEqual(setup_env.torch_channel(None, None), 'cpu')
        self.assertEqual(setup_env.torch_channel(6.1, 12.6), 'cu126')    # GTX 1050 Ti, driver 560
        self.assertEqual(setup_env.torch_channel(6.1, 13.0), 'cu126')    # Pascal dropped from cu128+
        self.assertEqual(setup_env.torch_channel(8.9, 12.6), 'cu126')    # RTX 4070 on an old driver
        self.assertEqual(setup_env.torch_channel(8.9, 13.0), 'cu130')
        self.assertEqual(setup_env.torch_channel(12.0, 12.8), 'cu128')   # RTX 5060 needs cu128+
        self.assertEqual(setup_env.torch_channel(12.0, 12.6), 'cpu')     # driver too old for Blackwell


if __name__ == '__main__':
    unittest.main()
