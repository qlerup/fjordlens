"""Bundled soundtracks and identical equal-power looping for playback and export."""
import hashlib
import json
import math
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent / 'music'


def catalog():
    return json.loads((ROOT / 'catalog.json').read_text(encoding='utf-8'))


def validate(value):
    if not isinstance(value, dict) or set(value) - {'track_id', 'volume'}:
        raise ValueError('Ugyldigt musikvalg.')
    track = value.get('track_id')
    volume = value.get('volume', .23)
    if track is not None and (not isinstance(track, str) or track not in {t['id'] for t in catalog()}):
        raise ValueError('Musiknummeret findes ikke.')
    if type(volume) not in (float, int) or not math.isfinite(volume) or not 0 <= volume <= 1:
        raise ValueError('Lydstyrken skal være mellem 0 og 100 %.')
    return dict(track_id=track, volume=round(volume, 3))


def choice(script, title=''):
    if script and 'music' in script[0]:
        return validate(script[0]['music'])
    title = title.lower()
    mood = 'quiet'
    for key, pattern in [('wedding', r'bryllup|konfirmation|vielse'), ('winter', r'jul|vinter|nytår'),
                         ('year', r'året der gik|års'), ('memory', r'begravelse|mindehøjtid'),
                         ('summer', r'sommer|strand|tyrkiet|alanya'), ('adventure', r'rejse|tur til'),
                         ('playful', r'børn|fødselsdag|legoland|bakken|safari')]:
        if re.search(pattern, title):
            mood = key
            break
    tracks = [t for t in catalog() if t['mood'] == mood]
    index = int(hashlib.sha256(title.encode()).hexdigest()[:8], 16) % len(tracks)
    return dict(track_id=tracks[index]['id'], volume=.23)


def descriptor(script, title='', url=None):
    selection = choice(script, title)
    track = next((t for t in catalog() if t['id'] == selection['track_id']), None)
    return dict(track, volume=selection['volume'], url=url or '/api/moments/music/' + track['id']) if track else None


def register(app):
    from flask import jsonify, send_file, abort
    from flask_login import login_required

    @app.get('/api/moments/music')
    @login_required
    def moment_music_catalog():
        return jsonify(ok=True, items=[dict(t, url='/api/moments/music/' + t['id']) for t in catalog()])

    @app.get('/api/moments/music/<track_id>')
    @login_required
    def moment_music_file(track_id):
        track = next((t for t in catalog() if t['id'] == track_id), None)
        if not track:
            abort(404)
        return send_file(ROOT / track['file'], conditional=True)


def upgrade(conn):
    """Add music once without regenerating any existing manual timeline."""
    for row in conn.execute("SELECT id,title,script_json FROM moments WHERE script_json IS NOT NULL AND COALESCE(video_status,'') NOT IN ('queued','running','rendering')").fetchall():
        script = json.loads(row['script_json'] or '[]')
        if script and 'music' not in script[0]:
            script[0]['music'] = choice(script, row['title'])
            conn.execute("UPDATE moments SET script_json=?,revision=revision+1,video_status='none',video_rel_path=NULL WHERE id=?",
                         (json.dumps(script, ensure_ascii=False), row['id']))
    for row in conn.execute('SELECT token_hash,title,script_json FROM moment_shares').fetchall():
        script = json.loads(row['script_json'] or '[]')
        if script and 'music' not in script[0]:
            script[0]['music'] = choice(script, row['title'])
            conn.execute('UPDATE moment_shares SET script_json=? WHERE token_hash=?',
                         (json.dumps(script, ensure_ascii=False), row['token_hash']))


def loop_parts(samples, fade):
    """Intro then a repeatable cycle: tail/head overlap followed by the middle."""
    import numpy as np
    fade = min(fade, len(samples) // 3)
    phase = np.linspace(0, math.pi / 2, fade, endpoint=True)[:, None]
    seam = samples[-fade:] * np.cos(phase) + samples[:fade] * np.sin(phase)
    return samples[:-fade], np.concatenate((seam, samples[fade:-fade]))


def add_to_video(ffmpeg, video, output, work_dir, music, timeout=1800):
    import numpy as np
    track = ROOT / music['file']
    raw = subprocess.run([ffmpeg, '-v', 'error', '-i', str(track), '-f', 'f32le',
                          '-ar', '44100', '-ac', '2', '-'], capture_output=True, check=True, timeout=timeout).stdout
    samples = np.frombuffer(raw, dtype='<f4').reshape(-1, 2)
    samples = samples[round(music['trim_start'] * 44100):round(music['trim_end'] * 44100)]
    intro, cycle = loop_parts(samples, round(music['crossfade'] * 44100))
    for name, data in [('intro.wav', intro), ('cycle.wav', cycle)]:
        # Float WAV keeps overlap headroom until the user's volume is applied.
        subprocess.run([ffmpeg, '-y', '-v', 'error', '-f', 'f32le', '-ar', '44100', '-ac', '2',
                        '-i', '-', '-c:a', 'pcm_f32le', str(work_dir / name)],
                       input=data.astype('<f4').tobytes(), check=True, timeout=timeout)
    # ffmpeg is always available where rendering works; no separate ffprobe required.
    probe = subprocess.run([ffmpeg, '-hide_banner', '-i', str(video)], capture_output=True, timeout=30)
    match = re.search(r'Duration: (\d+):(\d+):(\d+\.\d+)', probe.stderr.decode(errors='replace'))
    if not match:
        raise RuntimeError('Kunne ikke læse videoens varighed.')
    h, m, s = map(float, match.groups()); duration = h * 3600 + m * 60 + s
    repeats = math.ceil(duration / (len(cycle) / 44100)) + 1
    playlist = work_dir / 'music-concat.txt'
    playlist.write_text("file 'intro.wav'\n" + "file 'cycle.wav'\n" * repeats, encoding='utf-8')
    filters = f"volume={music['volume']},afade=t=in:d=1.5,afade=t=out:st={max(0, duration-2)}:d=2"
    subprocess.run([ffmpeg, '-y', '-v', 'error', '-i', str(video), '-f', 'concat', '-safe', '0',
                    '-i', str(playlist), '-map', '0:v:0', '-map', '1:a:0', '-c:v', 'copy',
                    '-af', filters, '-c:a', 'aac', '-b:a', '192k', '-t', str(duration),
                    '-movflags', '+faststart', '-f', 'mp4', str(output)], check=True, timeout=timeout)
