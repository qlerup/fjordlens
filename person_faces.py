"""Move an explicitly selected set of faces without changing their photos."""
import json
import math
import secrets
import sqlite3
import threading
from contextlib import closing
from urllib.parse import quote

import numpy as np

from flask import jsonify, request


_REVIEW_JOBS: dict[str, dict] = {}
_REVIEW_JOBS_LOCK = threading.RLock()
_REVIEW_MARGIN = 0.03
_REVIEW_BATCH_SIZE = 64


def _face_vector(value):
    try:
        parsed = json.loads(value) if value else None
        if not isinstance(parsed, list) or not parsed:
            return None
        vector = [float(component) for component in parsed]
        return vector if all(math.isfinite(v) for v in vector) and any(vector) else None
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
        'face_url': f"/api/face-thumb/{int(row['face_id'])}",
        'image_url': image_url,
        'full_url': image_url if ext in {'.mp4', '.mov', '.m4v', '.avi', '.mkv', '.webm'} else f"/api/viewable/{quote(str(row['rel_path']))}",
        'pixel_box': [float(row[key] or 0) for key in ('bbox_x', 'bbox_y', 'bbox_w', 'bbox_h')],
        'source_size': [width, height],
        'exact_frame': ext in {'.mp4', '.mov', '.m4v', '.avi', '.mkv', '.webm'} and row['frame_sec'] is not None,
        'box_available': ext not in {'.mp4', '.mov', '.m4v', '.avi', '.mkv', '.webm'} or row['frame_sec'] is not None,
        'box': {
            'x': max(0.0, float(row['bbox_x'] or 0) / width),
            'y': max(0.0, float(row['bbox_y'] or 0) / height),
            'w': max(0.0, float(row['bbox_w'] or 0) / width),
            'h': max(0.0, float(row['bbox_h'] or 0) / height),
        },
    }


def _unit_face_vector(raw):
    vector = _face_vector(raw)
    if vector is None:
        return None
    array = np.asarray(vector, dtype=np.float64)
    length = np.linalg.norm(array)
    if not np.isfinite(length) or length <= 0:
        return None
    return (array / length).astype(np.float32)


def _reference_profile(entries):
    matrix = np.stack([vector for _, vector in entries])
    photo_ids = np.asarray([photo_id for photo_id, _ in entries], dtype=np.int64)
    photos, inverse, counts = np.unique(photo_ids, return_inverse=True, return_counts=True)
    photo_sums = np.zeros((len(photos), matrix.shape[1]), dtype=np.float32)
    np.add.at(photo_sums, inverse, matrix)
    return {'matrix': matrix, 'photo_ids': photo_ids, 'sum': matrix.sum(axis=0),
            'photos': {int(pid): (photo_sums[i], int(counts[i])) for i, pid in enumerate(photos)}}


def _profile_scores(profile, queries, query_photos, exclude_photo=False):
    """Use two independent photo references when available, plus the centroid.

    A source query and all other frames/faces of its own photo/video are left
    out of BOTH the nearest-face comparison and the recomputed centroid.
    """
    references = profile['matrix']
    scores = queries @ references.T
    centroid_sums = np.repeat(profile['sum'][None, :], len(queries), axis=0)
    photo_counts = np.full(len(queries), len(profile['photos']), dtype=np.int32)
    if exclude_photo:
        for i, photo_id in enumerate(query_photos):
            found = profile['photos'].get(int(photo_id))
            if found is not None:
                scores[i, profile['photo_ids'] == photo_id] = -1.0
                centroid_sums[i] -= found[0]
                photo_counts[i] -= 1
    lengths = np.linalg.norm(centroid_sums, axis=1)
    centroids = np.full(len(queries), -1.0, dtype=np.float32)
    valid = (lengths > 1e-6) & (photo_counts > 0)
    centroids[valid] = np.einsum('ij,ij->i', queries[valid], centroid_sums[valid]) / lengths[valid]
    best_indices = np.argmax(scores, axis=1)
    best = scores[np.arange(len(queries)), best_indices].copy()
    best_photos = profile['photo_ids'][best_indices]
    for i, photo_id in enumerate(best_photos):
        scores[i, profile['photo_ids'] == photo_id] = -1.0
    second = scores.max(axis=1)
    face_scores = np.where(photo_counts >= 2, second, best)
    return np.clip(centroids, -1, 1), np.clip(face_scores, -1, 1), photo_counts


def _run_face_review(job_id, source_id, fjordlens):
    try:
        source_person_id = None if source_id == 'unknown' else int(source_id)
        threshold = float(getattr(fjordlens, 'FACE_MATCH_THRESHOLD_CENTROID', 0.45))
        face_threshold = float(getattr(fjordlens, 'FACE_MATCH_THRESHOLD', threshold))
        with closing(fjordlens.get_conn()) as conn:
            people = {int(row['id']): str(row['name'] or '').strip() for row in conn.execute(
                'SELECT id,name FROM people WHERE COALESCE(hidden,0)=0')}
            target_ids = {pid for pid, name in people.items() if pid != source_person_id
                          and name and not name.lower().startswith(('ukendt', 'unknown'))}
            source_where = 'f.person_id IS NULL' if source_person_id is None else 'f.person_id=?'
            source_params = () if source_person_id is None else (source_person_id,)
            rows = conn.execute(f"""
                SELECT f.id AS face_id,f.photo_id,f.embedding_json,f.frame_sec,f.bbox_x,f.bbox_y,f.bbox_w,f.bbox_h,
                       p.rel_path,p.ext,p.thumb_name,p.width,p.height
                FROM faces f JOIN photos p ON p.id=f.photo_id
                WHERE {source_where} ORDER BY f.id
            """, source_params).fetchall()
            _set_review_job(job_id, status='running', phase='references', total=len(rows), scanned=0)
            # Cache path decisions; one group photo may have dozens of faces.
            allowed_paths = {}
            def allowed(path):
                if path not in allowed_paths:
                    allowed_paths[path] = fjordlens._is_rel_path_allowed_for_current_user(path, conn)
                return allowed_paths[path]
            entries = {}
            reference_count = 0
            for row in conn.execute("""
                SELECT f.person_id,f.photo_id,f.embedding_json,p.rel_path
                FROM faces f JOIN people person ON person.id=f.person_id
                JOIN photos p ON p.id=f.photo_id
                WHERE COALESCE(person.hidden,0)=0 AND f.embedding_json IS NOT NULL
            """):
                pid = int(row['person_id'])
                if pid != source_person_id and pid not in target_ids:
                    continue
                if not allowed(row['rel_path']):
                    continue
                vector = _unit_face_vector(row['embedding_json'])
                if vector is not None:
                    entries.setdefault((pid, len(vector)), []).append((int(row['photo_id']), vector))
                    reference_count += 1
            profiles = {key: _reference_profile(values) for key, values in entries.items()}
            del entries
            groups = {}
            valid_rows = {}
            skipped = 0
            for row in rows:
                vector = _unit_face_vector(row['embedding_json']) if allowed(row['rel_path']) else None
                if vector is None:
                    skipped += 1
                else:
                    valid_rows.setdefault(len(vector), []).append((row, vector))
            scanned = skipped
            kept = 0
            _set_review_job(job_id, phase='matching', reference_faces=reference_count, scanned=scanned)
            for dimension, dimension_rows in valid_rows.items():
                candidates = sorted(pid for pid in target_ids if (pid, dimension) in profiles)
                for offset in range(0, len(dimension_rows), _REVIEW_BATCH_SIZE):
                    batch = dimension_rows[offset:offset+_REVIEW_BATCH_SIZE]
                    queries = np.stack([vector for _, vector in batch])
                    photos = [int(row['photo_id']) for row, _ in batch]
                    own_profile = profiles.get((source_person_id, dimension))
                    if own_profile is not None:
                        own_centroid, own_faces, own_counts = _profile_scores(own_profile, queries, photos, exclude_photo=True)
                    else:
                        own_centroid = own_faces = np.full(len(batch), -1.0)
                        own_counts = np.zeros(len(batch), dtype=int)
                    # Compare excess above the appropriate configured threshold
                    # so face/centroid thresholds can differ without bias.
                    own_strength = np.maximum(own_centroid-threshold, own_faces-face_threshold)
                    scores = np.full((len(batch), len(candidates)), -2.0, dtype=np.float32)
                    similarities = np.full_like(scores, -1.0)
                    supports = np.zeros((len(batch), len(candidates)), dtype=int)
                    for j, pid in enumerate(candidates):
                        centroid_scores, face_scores, photo_counts = _profile_scores(profiles[(pid, dimension)], queries, photos)
                        scores[:, j] = np.maximum(centroid_scores-threshold, face_scores-face_threshold)
                        similarities[:, j] = np.where(centroid_scores-threshold >= face_scores-face_threshold,
                                                       centroid_scores, face_scores)
                        supports[:, j] = photo_counts
                    for i, (row, _) in enumerate(batch):
                        best_id, best_strength, runner_up = None, -2.0, -2.0
                        best_similarity = -1.0
                        support = 0
                        if candidates:
                            order = np.argsort(scores[i])[::-1]
                            best_index = int(order[0])
                            best_id = candidates[best_index]
                            best_strength = float(scores[i, best_index])
                            best_similarity = float(similarities[i, best_index])
                            runner_up = float(scores[i, order[1]]) if len(order)>1 else -2.0
                            support = int(supports[i, best_index])
                        better = (best_id is not None and best_strength >= 0
                                  and best_strength >= float(own_strength[i]) + _REVIEW_MARGIN
                                  and best_strength >= runner_up + _REVIEW_MARGIN)
                        if better:
                            key, name = best_id, people[best_id]
                            reason = 'better_match'
                        elif own_strength[i] < 0:
                            key, name = 'unmatched', 'Kræver manuel gennemgang'
                            reason = ('no_reference' if own_counts[i] == 0 and best_strength < 0 else
                                      'ambiguous' if best_strength >= 0 else 'weak_match')
                        else:
                            kept += 1
                            continue
                        group = groups.setdefault(key, {'target_id': best_id if better else None,
                            'target_name': name, 'faces': [], 'best_score': -1.0})
                        preview = _review_preview(row)
                        preview.update(reason=reason, reference_photos=support if better else int(own_counts[i]))
                        group['faces'].append(preview)
                        group['best_score'] = max(group['best_score'], best_similarity)
                    scanned += len(batch)
                    _set_review_job(job_id, scanned=scanned)
            results = []
            for group in groups.values():
                group['count'] = len(group['faces'])
                group['face_ids'] = [face['face_id'] for face in group['faces']]
                group['previews'] = group['faces'][:4]
                results.append(group)
            results.sort(key=lambda group: (group['target_id'] is None, -group['count'], group['target_name'].casefold()))
            suggested = sum(group['count'] for group in results if group['target_id'] is not None)
            manual = sum(group['count'] for group in results if group['target_id'] is None)
            _set_review_job(job_id, status='done', results=results, scanned=len(rows), total=len(rows),
                            suggested=suggested, manual_review=manual, kept=kept, skipped=skipped, error=None)
    except Exception as exc:
        _set_review_job(job_id, status='error', error=str(exc))


def _start_face_review(source_id, fjordlens):
    with _REVIEW_JOBS_LOCK:
        # Reopening the dialog must not start a second full vector comparison.
        for existing_id, job in _REVIEW_JOBS.items():
            if job.get('source_id') == source_id and job.get('status') in ('queued', 'running'):
                return existing_id
        finished = [key for key, job in _REVIEW_JOBS.items() if job.get('status') in ('done', 'error')]
        for key in finished[:-19]:
            _REVIEW_JOBS.pop(key, None)
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
