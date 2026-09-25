"""Move an explicitly selected set of faces without changing their photos."""
import json
import math
import secrets
import sqlite3
import threading
from contextlib import closing
from urllib.parse import quote

from flask import jsonify, request


_REVIEW_JOBS: dict[str, dict] = {}
_REVIEW_JOBS_LOCK = threading.RLock()
_REVIEW_MARGIN = 0.0


def _face_vector(value):
    try:
        parsed = json.loads(value) if value else None
        if not isinstance(parsed, list) or not parsed:
            return None
        return [float(component) for component in parsed]
    except (TypeError, ValueError):
        return None


def _cosine(first, second):
    if not first or not second or len(first) != len(second):
        return -1.0
    numerator = sum(left * right for left, right in zip(first, second))
    first_length = math.sqrt(sum(value * value for value in first))
    second_length = math.sqrt(sum(value * value for value in second))
    return numerator / (first_length * second_length) if first_length and second_length else -1.0


def _average_vector(vectors):
    valid = [vector for vector in vectors if vector]
    if not valid:
        return None
    size = len(valid[0])
    same_size = [vector for vector in valid if len(vector) == size]
    if not same_size:
        return None
    return [sum(vector[index] for vector in same_size) / len(same_size) for index in range(size)]


def _set_review_job(job_id, **patch):
    with _REVIEW_JOBS_LOCK:
        current = dict(_REVIEW_JOBS.get(job_id) or {})
        current.update(patch)
        _REVIEW_JOBS[job_id] = current


def _review_preview(row):
    width = max(1.0, float(row['width'] or 0))
    height = max(1.0, float(row['height'] or 0))
    ext = str(row['ext'] or '').lower()
    if ext in {'.mp4', '.mov', '.m4v', '.avi', '.mkv', '.webm'} and row['frame_sec'] is not None:
        image_url = f"/api/people/video-frame/{int(row['face_id'])}?t={float(row['frame_sec'])}"
    elif row['thumb_name']:
        image_url = f"/api/thumbs/{quote(str(row['thumb_name']))}"
    else:
        image_url = f"/api/viewable/{quote(str(row['rel_path']))}"
    return {
        'face_id': int(row['face_id']),
        'photo_id': int(row['photo_id']),
        'image_url': image_url,
        'box': {
            'x': max(0.0, float(row['bbox_x'] or 0) / width),
            'y': max(0.0, float(row['bbox_y'] or 0) / height),
            'w': max(0.0, float(row['bbox_w'] or 0) / width),
            'h': max(0.0, float(row['bbox_h'] or 0) / height),
        },
    }


def _run_face_review(job_id, source_id, fjordlens):
    try:
        source_person_id = None if source_id == 'unknown' else int(source_id)
        with closing(fjordlens.get_conn()) as conn:
            target_rows = conn.execute(
                """
                SELECT id, name, centroid_json FROM people
                                WHERE COALESCE(hidden,0)=0
                """
            ).fetchall()
            targets = []
            own_centroid = None
            for row in target_rows:
                person_id = int(row['id'])
                vector = _face_vector(row['centroid_json'])
                if vector is None:
                    embedding_rows = conn.execute(
                        "SELECT embedding_json FROM faces WHERE person_id=? AND embedding_json IS NOT NULL",
                        (person_id,),
                    ).fetchall()
                    vector = _average_vector([_face_vector(candidate['embedding_json']) for candidate in embedding_rows])
                if vector is None:
                    continue
                if person_id == source_person_id:
                    own_centroid = vector
                    continue
                name = str(row['name'] or '').strip()
                if not name or name.lower().startswith(('ukendt', 'unknown')):
                    continue
                targets.append((person_id, name, vector))

            source_where = 'f.person_id IS NULL' if source_person_id is None else 'f.person_id=?'
            source_params = () if source_person_id is None else (source_person_id,)
            rows = conn.execute(
                f"""
                  SELECT f.id AS face_id, f.photo_id, f.embedding_json, f.frame_sec, f.bbox_x, f.bbox_y, f.bbox_w, f.bbox_h,
                      p.rel_path, p.ext, p.thumb_name, p.width, p.height
                FROM faces f INNER JOIN photos p ON p.id=f.photo_id
                WHERE {source_where} AND f.embedding_json IS NOT NULL
                ORDER BY f.id
                """,
                source_params,
            ).fetchall()
            _set_review_job(job_id, status='running', total=len(rows), scanned=0)
            groups = {}
            threshold = float(getattr(fjordlens, 'FACE_MATCH_THRESHOLD_CENTROID', 0.45))
            for index, row in enumerate(rows, start=1):
                if not fjordlens._is_rel_path_allowed_for_current_user(row['rel_path'], conn):
                    _set_review_job(job_id, scanned=index)
                    continue
                vector = _face_vector(row['embedding_json'])
                if vector is None:
                    _set_review_job(job_id, scanned=index)
                    continue
                best_id, best_name, best_score = None, '', -1.0
                for person_id, name, centroid in targets:
                    score = _cosine(vector, centroid)
                    if score > best_score:
                        best_id, best_name, best_score = person_id, name, score
                own_score = _cosine(vector, own_centroid) if own_centroid else -1.0
                if best_id is not None and best_score >= threshold and (source_person_id is None or best_score >= own_score + _REVIEW_MARGIN):
                    group = groups.setdefault(best_id, {'target_id': best_id, 'target_name': best_name, 'faces': [], 'best_score': best_score})
                    group['faces'].append(_review_preview(row))
                    group['best_score'] = max(group['best_score'], best_score)
                elif source_person_id is not None and own_score < threshold:
                    group = groups.setdefault('unmatched', {'target_id': None, 'target_name': 'Ingen sikker match', 'faces': [], 'best_score': own_score})
                    group['faces'].append(_review_preview(row))
                    group['best_score'] = max(group['best_score'], own_score)
                _set_review_job(job_id, scanned=index)
            results = []
            for group in groups.values():
                group['count'] = len(group['faces'])
                group['face_ids'] = [face['face_id'] for face in group['faces']]
                group['previews'] = group['faces'][:4]
                results.append(group)
            results.sort(key=lambda group: (-group['count'], -group['best_score'], group['target_name'].casefold()))
            _set_review_job(job_id, status='done', results=results, scanned=len(rows), total=len(rows), error=None)
    except Exception as exc:
        _set_review_job(job_id, status='error', error=str(exc))


def _start_face_review(source_id, fjordlens):
    job_id = secrets.token_urlsafe(18)
    _set_review_job(job_id, status='queued', source_id=source_id, scanned=0, total=0, results=[], error=None)
    threading.Thread(target=_run_face_review, args=(job_id, source_id, fjordlens), daemon=True).start()
    return job_id


def move_faces(conn, data, fjordlens):
    ids = data.get('face_ids')
    if not isinstance(ids, list) or not ids or len(ids) > 5000 or any(type(i) is not int or i <= 0 for i in ids):
        raise ValueError('Vælg mellem 1 og 5000 ansigter.')
    ids = sorted(set(ids))
    source = data.get('source_id')
    if source != 'unknown' and (type(source) is not int or source <= 0):
        raise ValueError('Ugyldig person.')
    source = None if source == 'unknown' else source
    action = data.get('action')
    if action not in ('hide', 'create', 'assign'):
        raise ValueError('Ugyldig handling.')
    conn.execute('BEGIN IMMEDIATE')
    rows = []
    for face_id in ids:
        row = conn.execute('SELECT f.person_id,p.rel_path FROM faces f JOIN photos p ON p.id=f.photo_id WHERE f.id=?', (face_id,)).fetchone()
        if row is None or row['person_id'] != source:
            raise ValueError('Ansigterne er ændret. Genindlæs personen og vælg igen.')
        if not fjordlens._is_rel_path_allowed_for_current_user(row['rel_path'], conn):
            raise PermissionError('Du har ikke adgang til et af billederne.')
        rows.append(row)
    if action == 'assign':
        target = data.get('target_id')
        if type(target) is not int or target == source:
            raise ValueError('Vælg en anden person.')
        person = conn.execute('SELECT id,name FROM people WHERE id=? AND COALESCE(hidden,0)=0', (target,)).fetchone()
        if person is None:
            raise ValueError('Personen findes ikke eller er skjult.')
        name = person['name']
    else:
        name = data.get('name', '')
        if action == 'hide':
            name = 'Skjulte ansigter · ' + secrets.token_hex(6)
        if not isinstance(name, str) or not name.strip() or len(name.strip()) > 160:
            raise ValueError('Skriv et navn på højst 160 tegn.')
        name = name.strip()
        if conn.execute('SELECT id FROM people WHERE LOWER(name)=LOWER(?)', (name,)).fetchone():
            raise ValueError('Navnet findes allerede. Vælg personen i listen.')
        target = conn.execute('INSERT INTO people(name,created_at,hidden) VALUES(?,?,?)',
                              (name, fjordlens.now_iso(), int(action == 'hide'))).lastrowid
    conn.executemany('UPDATE faces SET person_id=? WHERE id=?', [(target, i) for i in ids])
    # Compute inside this transaction; the older helper commits on its own.
    for pid in {source, target} - {None}:
        vectors = []
        for row in conn.execute('SELECT embedding_json FROM faces WHERE person_id=?', (pid,)):
            try:
                value = json.loads(row['embedding_json'])
                if isinstance(value, list) and value:
                    vectors.append([float(v) for v in value])
            except (ValueError, TypeError):
                pass
        centroid = fjordlens._compute_centroid(vectors)
        conn.execute('UPDATE people SET centroid_json=? WHERE id=?', (json.dumps(centroid) if centroid else None, pid))
    conn.commit()
    return {'ok': True, 'target_id': target, 'name': name, 'face_ids': ids}


def register(app, fjordlens, can_manage):
    @app.post('/api/people/face-review')
    def api_person_face_review_start():
        if not can_manage():
            return jsonify(ok=False, error='Forbidden'), 403
        data = request.get_json(silent=True) or {}
        source_id = data.get('source_id')
        if source_id != 'unknown' and (type(source_id) is not int or source_id <= 0):
            return jsonify(ok=False, error='Ugyldig person.'), 400
        return jsonify(ok=True, job_id=_start_face_review(source_id, fjordlens))

    @app.get('/api/people/face-review/<job_id>')
    def api_person_face_review_status(job_id):
        if not can_manage():
            return jsonify(ok=False, error='Forbidden'), 403
        with _REVIEW_JOBS_LOCK:
            job = dict(_REVIEW_JOBS.get(job_id) or {})
        if not job:
            return jsonify(ok=False, error='Analysen findes ikke.'), 404
        return jsonify(ok=True, **job)

    @app.post('/api/people/faces/selection')
    def api_person_face_selection():
        if not can_manage():
            return jsonify(ok=False, error='Forbidden'), 403
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify(ok=False, error='Ugyldigt valg.'), 400
        try:
            with closing(fjordlens.get_conn()) as conn:
                return jsonify(move_faces(conn, data, fjordlens))
        except PermissionError as exc:
            return jsonify(ok=False, error=str(exc)), 403
        except (ValueError, sqlite3.IntegrityError) as exc:
            return jsonify(ok=False, error=str(exc)), 409
