"""Reversible discovery privacy, independent of folder ownership/access rights."""
from contextlib import closing
from io import BytesIO
import json

from flask import g as request_state, has_request_context, jsonify, request, send_file
from flask_login import current_user, login_required
from PIL import Image, ImageFilter


def logical_path(path):
    path = str(path or '').replace('\\', '/').strip('/')
    for prefix in ('uploads/originals/', 'uploads/converted/', 'uploads/'):
        if path.startswith(prefix):
            return path[len(prefix):]
    return path


def migrate(conn):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS private_folders (folder_path TEXT PRIMARY KEY);
        CREATE VIEW IF NOT EXISTS discovery_photos AS
        SELECT photos.* FROM photos WHERE NOT EXISTS (
          SELECT 1 FROM private_folders pf WHERE
            instr(CASE
              WHEN substr(photos.rel_path,1,18)='uploads/originals/' THEN substr(photos.rel_path,19)
              WHEN substr(photos.rel_path,1,18)='uploads/converted/' THEN substr(photos.rel_path,19)
              WHEN substr(photos.rel_path,1,8)='uploads/' THEN substr(photos.rel_path,9)
              ELSE photos.rel_path END, pf.folder_path || '/')=1
        );
        CREATE VIEW IF NOT EXISTS discovery_faces AS
        SELECT faces.* FROM faces JOIN discovery_photos dp ON dp.id=faces.photo_id;
    """)


def private_parent(conn, path):
    logical = logical_path(path)
    rows = conn.execute('SELECT folder_path FROM private_folders ORDER BY length(folder_path)').fetchall()
    return next((r[0] for r in rows if logical == r[0] or logical.startswith(r[0] + '/')), None)


def private_for_response(get_conn, path):
    paths = getattr(request_state, '_private_folder_paths', None) if has_request_context() else None
    if paths is None:
        with closing(get_conn()) as conn:
            paths = tuple(r[0] for r in conn.execute('SELECT folder_path FROM private_folders'))
        if has_request_context():
            request_state._private_folder_paths = paths
    logical = logical_path(path)
    return any(logical == p or logical.startswith(p + '/') for p in paths)


def inside_folder(path, folder):
    """A thumbnail browsing context must explicitly contain the photo."""
    folder = logical_path(folder)
    if not folder or any(part in ('', '.', '..') for part in folder.split('/')):
        return False
    return logical_path(path).startswith(folder + '/')


def blurred_thumbnail(path):
    # Deliberately discard identifying detail before resizing; originals stay intact.
    with Image.open(path) as source:
        size = source.size
        image = source.convert('RGB').resize((2, 2), Image.Resampling.BOX)
        image = image.resize(size, Image.Resampling.BICUBIC).filter(ImageFilter.GaussianBlur(max(size) / 8))
        output = BytesIO()
        image.save(output, format='JPEG', quality=80)
    output.seek(0)
    response = send_file(output, mimetype='image/jpeg', conditional=False, etag=False)
    response.headers['Cache-Control'] = 'private, no-store'
    return response


def moment_is_private(conn, ids):
    ids = list(ids)
    for offset in range(0, len(ids), 500):
        batch = ids[offset:offset+500]
        marks = ','.join('?' for _ in batch)
        if conn.execute(f'SELECT 1 FROM photos WHERE id IN ({marks}) AND id NOT IN (SELECT id FROM discovery_photos) LIMIT 1', batch).fetchone():
            return True
    return False


def active_centroids(conn, compute):
    vectors = {}
    for row in conn.execute('SELECT person_id,embedding_json FROM discovery_faces WHERE person_id IS NOT NULL AND embedding_json IS NOT NULL'):
        try:
            vector = json.loads(row['embedding_json'])
            if isinstance(vector, list) and vector:
                vectors.setdefault(row['person_id'], []).append(vector)
        except (TypeError, ValueError):
            continue
    return {pid: compute(items) for pid, items in vectors.items()}


def register(app, g):
    @app.route('/api/folder-privacy', methods=['GET', 'POST'])
    @login_required
    def api_folder_privacy():
        if not getattr(current_user, 'can_manage_media', False):
            return jsonify(ok=False, error='Forbidden'), 403
        body = request.get_json(silent=True) if request.method == 'POST' else request.args
        if not isinstance(body, dict) and request.method == 'POST':
            return jsonify(ok=False, error='Ugyldig forespørgsel'), 400
        try:
            path = g['_normalize_folder_acl_path'](body.get('folder'))
            path = logical_path(path)
            if not path or path in ('uploads', 'originals', 'converted'):
                raise ValueError()
        except (TypeError, ValueError):
            return jsonify(ok=False, error='Vælg en mappe'), 400
        with closing(g['get_conn']()) as conn:
            if request.method == 'POST':
                value = body.get('private')
                if not isinstance(value, bool):
                    return jsonify(ok=False, error='Ugyldig privatmarkering'), 400
                conn.execute('BEGIN IMMEDIATE')
                if value:
                    conn.execute('INSERT OR IGNORE INTO private_folders VALUES (?)', (path,))
                else:
                    conn.execute('DELETE FROM private_folders WHERE folder_path=?', (path,))
                conn.commit()
            parent = private_parent(conn, path)
        if request.method == 'POST':
            with closing(g['get_conn']()) as conn:
                ids = {int(r[0]) for r in conn.execute('SELECT id FROM people')}
            g['_recompute_person_centroids_bulk'](ids)
        return jsonify(ok=True, folder=path, private=parent is not None,
                       inherited=parent is not None and parent != path, private_parent=parent)
