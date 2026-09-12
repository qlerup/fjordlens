"""Move an explicitly selected set of faces without changing their photos."""
import json
import secrets
import sqlite3
from contextlib import closing

from flask import jsonify, request


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
