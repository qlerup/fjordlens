"""Exact video frames for reviewing face detections in People."""
import hashlib
import math
import os
import tempfile
from contextlib import closing
from pathlib import Path

from flask import abort, send_file


def decorate(items):
    for item in items:
        if not item.get('is_video'):
            continue
        faces = item.get('faces', [])
        timed = [face for face in faces if face.get('frame_sec') is not None]
        if not timed:
            # Older detections may not have a timestamp. Show the face crop,
            # never a box over an unrelated default video poster.
            if faces:
                item['thumb_url'] = f"/api/face-thumb/{faces[0]['id']}"
            item['thumbnail_faces'] = []
            continue
        face = max(
            timed,
            key=lambda candidate: (
                float(candidate.get('confidence') or 0),
                float((candidate.get('pixel_box') or [0, 0, 0, 0])[2] or 0)
                * float((candidate.get('pixel_box') or [0, 0, 0, 0])[3] or 0),
                int(candidate.get('id') or 0),
            ),
        )
        item['thumb_url'] = f"/api/people/video-frame/{face['id']}?t={face['frame_sec']}"
        item['person_frame_sec'] = face['frame_sec']
        item['thumbnail_faces'] = [face]
    return items


def register(app, fjordlens):
    @app.get('/api/people/video-frame/<int:face_id>')
    def api_person_video_frame(face_id):
        with closing(fjordlens.get_conn()) as conn:
            row = conn.execute('SELECT f.frame_sec,p.rel_path FROM faces f JOIN photos p ON p.id=f.photo_id WHERE f.id=?', (face_id,)).fetchone()
        if not row:
            abort(404)
        rel = row['rel_path']
        if not fjordlens._is_rel_path_allowed_for_current_user(rel):
            abort(403)
        seconds = row['frame_sec']
        if seconds is None or not math.isfinite(seconds) or seconds < 0 or Path(rel).suffix.lower() not in fjordlens.VIDEO_EXTS:
            abort(404)
        root = fjordlens.UPLOAD_DIR if rel.startswith('uploads/') else fjordlens.PHOTO_DIR
        source = (root / (rel.split('/', 1)[1] if rel.startswith('uploads/') else rel)).resolve()
        if not source.is_relative_to(root.resolve()) or not source.is_file():
            abort(404)
        stat = source.stat()
        key = hashlib.sha256(f'{rel}:{seconds}:{stat.st_mtime_ns}:{stat.st_size}'.encode()).hexdigest()
        output = fjordlens.THUMB_DIR / f'person-video-{key}.jpg'
        if not output.exists():
            content = fjordlens._extract_video_frame_bytes(source, rel, seconds)
            if not content:
                abort(503, 'Snapshot kunne ikke hentes.')
            output.parent.mkdir(parents=True, exist_ok=True)
            descriptor, temporary = tempfile.mkstemp(prefix='person-frame-', suffix='.tmp', dir=output.parent)
            try:
                with os.fdopen(descriptor, 'wb') as handle:
                    handle.write(content)
                os.replace(temporary, output)
            finally:
                Path(temporary).unlink(missing_ok=True)
        response = send_file(output, mimetype='image/jpeg', conditional=True)
        response.headers['Cache-Control'] = 'private, no-cache'
        return response
