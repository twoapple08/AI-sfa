import tempfile
import unittest
from pathlib import Path

from build_render_probe import build, HOLD
import sfa


class RenderProbe(unittest.TestCase):
    def test_probe_is_valid_and_segments_hold_still(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest, root = build(tmp)
            loaded = sfa.read_sfa(Path(tmp) / '07_render_reference.sfa')
        self.assertEqual(sfa.validate(loaded), [])
        frames = root.findall('Frame')
        self.assertEqual(len(frames), manifest['frames'])
        self.assertLess(max(int(p.get('Flags')) for p in root.iter('AP')), 2 ** 31)
        for seg in manifest['segments']:
            first, last = seg['frames_1based']
            self.assertEqual(last - first + 1, HOLD)
            shapes = {tuple((o.get('ID'), tuple((p.get('X'), p.get('Y')) for p in o.findall('AP')))
                            for o in frames[i - 1].findall('AO')) for i in range(first, last + 1)}
            self.assertEqual(len(shapes), 1, seg['segment'])

    def test_group_segment_has_one_resolvable_child(self):
        from tools.check_frame_commands import parse_frame, resolve_group_root
        manifest, root = build(tempfile.mkdtemp())
        seg = next(s for s in manifest['segments'] if s['segment'] == 'group_glow')
        frame = parse_frame(root.findall('Frame')[seg['frames_1based'][0] - 1])
        statuses = [resolve_group_root(pid, frame['points'])[1] for pid in frame['points']]
        self.assertEqual(statuses.count('ok'), 1)


if __name__ == '__main__':
    unittest.main()
