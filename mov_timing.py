"""Bake explicitly marked Apple high-frame-rate footage into a 30 fps timeline.

The intent flag does not describe Photos' edited slow-motion ranges. This is
uniform slow motion, never an inference based on frame rate alone.
"""
import json
import logging
import shutil
import subprocess
from fractions import Fraction

INTENT = 'com.apple.quicktime.full-frame-rate-playback-intent'


def slow_motion_factor(metadata):
    if str(metadata.get('format', {}).get('tags', {}).get(INTENT, '')) != '0':
        return 1.0
    video = next((s for s in metadata.get('streams', []) if s.get('codec_type') == 'video'), {})
    try:
        rate = float(Fraction(video.get('r_frame_rate', '0/1')))
        average = float(Fraction(video.get('avg_frame_rate', '0/1')))
    except (ValueError, TypeError, ZeroDivisionError):
        return 1.0
    # A low average can indicate an already retimed timeline. Do not slow it twice.
    if not 100 <= rate <= 480 or not 0.98 <= average / rate <= 1.02:
        return 1.0
    return rate / 30


def probe_slow_motion(src):
    probe = shutil.which('ffprobe')
    if not probe:
        raise RuntimeError('ffprobe is required to preserve MOV playback timing')
    result = subprocess.run([probe, '-v', 'error', '-show_entries',
        'stream=codec_type,r_frame_rate,avg_frame_rate:format_tags='+INTENT,
        '-of', 'json', str(src)], capture_output=True, text=True, check=True, timeout=30)
    factor = slow_motion_factor(json.loads(result.stdout))
    if factor > 1:
        logging.getLogger(__name__).info('Apple slow motion detected: %.3fx duration, 30 fps output', factor)
    return factor


def timing_args(factor, has_audio):
    if factor <= 1:
        return []
    args = ['-vf', f'setpts={factor:.10g}*(PTS-STARTPTS)', '-r', '30',
            '-metadata', INTENT+'=1']
    if has_audio:
        tempo = 1 / factor
        filters = ['asetpts=PTS-STARTPTS']
        while tempo < 0.5:
            filters.append('atempo=0.5')
            tempo *= 2
        filters.append(f'atempo={tempo:.10g}')
        args += ['-af', ','.join(filters)]
    return args
