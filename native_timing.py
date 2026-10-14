"""Timing model derived from the Android native exporter in Stick Fighter 51.0.0.

This models frame scheduling, not the Flutter renderer or full object interpolation.
Uses exact rational arithmetic; Java float32 edge cases are not reproduced.
"""
import argparse
from fractions import Fraction
import json


def export_plan(frame_count, tween_fps, playback_fps):
    for value in (frame_count, tween_fps, playback_fps):
        if type(value) is not int or value <= 0:
            raise ValueError('frame count and FPS must be positive integers')
    enabled = tween_fps > playback_fps
    output_fps = tween_fps if enabled else playback_fps
    # Java Math.round for nonnegative N*T/P, modeled without float32 rounding.
    total = ((2 * frame_count * tween_fps + playback_fps) // (2 * playback_fps)
             if enabled else frame_count)
    return {'source_frames': frame_count, 'tween_fps': tween_fps,
            'playback_fps': playback_fps, 'interpolation_enabled': enabled,
            'output_fps': output_fps, 'output_frames': total,
            'source_duration_seconds': frame_count / playback_fps,
            'encoded_duration_seconds': total / output_fps}


def sample_at(frame_count, tween_fps, playback_fps, index):
    plan = export_plan(frame_count, tween_fps, playback_fps)
    if type(index) is not int or not 0 <= index < plan['output_frames']:
        raise ValueError('output index out of range')
    position = (Fraction(index * playback_fps, tween_fps)
                if plan['interpolation_enabled'] else Fraction(index))
    start = min(int(position), frame_count - 1)
    end = min(start + 1, frame_count - 1)
    return {'from_frame': start, 'to_frame': end,
            'alpha': float(position - start), 'hold': start == end}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('frames', type=int)
    parser.add_argument('--fps', nargs=2, type=int, metavar=('TWEEN', 'PLAYBACK'), required=True)
    parser.add_argument('--sample', type=int)
    args = parser.parse_args()
    try:
        result = export_plan(args.frames, *args.fps)
        if args.sample is not None:
            result['sample'] = sample_at(args.frames, *args.fps, args.sample)
        print(json.dumps(result, indent=2))
    except ValueError as exc:
        parser.exit(1, f'Error: {exc}\n')
