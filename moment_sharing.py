"""Revocable public slideshow links scoped to a fixed selection of media."""
import hashlib
import json
import secrets
from contextlib import closing
from flask import abort, jsonify, render_template, request, send_file, url_for


def media_ids(script):
    return {value for slide in script for key in ('photo_id', 'background_photo_id', 'second_photo_id')
            if type(value := slide.get(key)) is int}


def register(app, g, managed):
    import moments_service as service

    def load(token):
        if not 32 <= len(token) <= 100:
            abort(404)
        digest = hashlib.sha256(token.encode()).hexdigest()
        with closing(g['get_conn']()) as conn:
            row = conn.execute('SELECT s.*,m.photo_ids_json,m.status FROM moment_shares s JOIN moments m ON m.id=s.moment_id WHERE s.token_hash=?', (digest,)).fetchone()
        if not row or row['status'] == 'dismissed':
            abort(404)
        script = json.loads(row['script_json'])
        if not media_ids(script).issubset(set(json.loads(row['photo_ids_json']))):
            abort(404)
        return row, script

    @app.route('/api/moments/<int:moment_id>/share', methods=['POST', 'DELETE'])
    @managed
    def moment_share(moment_id):
        with closing(g['get_conn']()) as conn:
            row = service._get(conn, moment_id)
        if request.method == 'DELETE':
            with closing(g['get_conn']()) as conn:
                conn.execute('DELETE FROM moment_shares WHERE moment_id=?', (moment_id,))
                conn.commit()
            return jsonify(ok=True)
        import moment_cinema
        if moment_cinema.needs_upgrade(row['script_json']):
            g['_generate_moment_script'](row)
        with closing(g['get_conn']()) as conn:
            row = service._get(conn, moment_id)
            script = json.loads(row['script_json'] or '[]')
            if not script:
                raise service.EditError('Diasshowet kunne ikke oprettes. Prøv igen.')
            token = secrets.token_urlsafe(32)
            conn.execute('INSERT INTO moment_shares VALUES(?,?,?,?,?)',
                         (hashlib.sha256(token.encode()).hexdigest(), moment_id, row['title'], json.dumps(script, ensure_ascii=False), g['now_iso']()))
            conn.commit()
        return jsonify(ok=True, url=url_for('shared_moment_view', token=token))

    @app.get('/m/<token>')
    def shared_moment_view(token):
        row, _ = load(token)
        response = app.make_response(render_template('shared_moment.html', share_token=token, title=row['title']))
        response.headers['Referrer-Policy'] = 'no-referrer'
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Robots-Tag'] = 'noindex, nofollow'
        return response

    @app.get('/api/moment-share/<token>')
    def shared_moment_data(token):
        row, script = load(token)
        photos = {str(pid): dict(original_url=url_for('shared_moment_media', token=token, photo_id=pid),
                                 is_video=any(s.get('photo_id')==pid and s.get('type')=='video' for s in script)) for pid in media_ids(script)}
        response = jsonify(ok=True, item=dict(title=row['title'], script=script, photos=photos))
        response.headers['Cache-Control'] = 'no-store'
        return response

    @app.get('/api/moment-share/<token>/media/<int:photo_id>')
    def shared_moment_media(token, photo_id):
        _, script = load(token)
        if photo_id not in media_ids(script):
            abort(404)
        with closing(g['get_conn']()) as conn:
            photo = conn.execute('SELECT rel_path FROM photos WHERE id=?', (photo_id,)).fetchone()
        if not photo:
            abort(404)
        path = g['_disk_path_from_rel_path'](photo['rel_path'])
        if not path.is_file():
            abort(404)
        path = g['ensure_viewable_copy'](path, photo['rel_path'])
        response = send_file(path, conditional=True, max_age=0)
        response.headers['Cache-Control'] = 'private, no-store'
        response.headers['Referrer-Policy'] = 'no-referrer'
        return response
