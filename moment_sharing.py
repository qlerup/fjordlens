"""Revocable public slideshow links scoped to a fixed selection of media."""
import hashlib
import json
import secrets
from contextlib import closing
from flask import abort, jsonify, render_template, request, send_file, url_for
from flask_login import current_user, login_required


def admin_items(g, include_inactive):
    with closing(g['get_conn']()) as conn:
        rows = conn.execute('SELECT rowid AS share_id,* FROM moment_shares ORDER BY created_at DESC').fetchall()
    items = []
    for row in rows:
        expired = g['_share_is_expired'](row['expires_at'])
        active = not row['revoked'] and not expired
        if not include_inactive and not active:
            continue
        link = url_for('shared_moment_view', token=row['token_plain'], _external=True) if row['token_plain'] else ''
        items.append(dict(id=-row['share_id'], kind='moment', share_name=row['title'], permission='view',
                          expires_at=row['expires_at'], created_at=row['created_at'], last_used_at=row['last_used_at'],
                          active=active, revoked=bool(row['revoked']), expired=expired, link=link, link_available=bool(link)))
    return items


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
        if not row or row['status'] == 'dismissed' or row['revoked'] or g['_share_is_expired'](row['expires_at']):
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
                conn.execute('UPDATE moment_shares SET revoked=1 WHERE moment_id=?', (moment_id,))
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
            expires_at, error = g['_share_expires_at_from_body'](request.get_json(silent=True) or {}, default_value=7, default_unit='days')
            if error:
                raise service.EditError(error)
            conn.execute('INSERT INTO moment_shares (token_hash,moment_id,title,script_json,created_at,token_plain,expires_at) VALUES(?,?,?,?,?,?,?)',
                         (hashlib.sha256(token.encode()).hexdigest(), moment_id, row['title'], json.dumps(script, ensure_ascii=False), g['now_iso'](), token, expires_at))
            conn.commit()
        return jsonify(ok=True, url=url_for('shared_moment_view', token=token), expires_at=expires_at)

    @app.get('/m/<token>')
    def shared_moment_view(token):
        row, _ = load(token)
        with closing(g['get_conn']()) as conn:
            conn.execute('UPDATE moment_shares SET last_used_at=? WHERE token_hash=?', (g['now_iso'](), row['token_hash']))
            conn.commit()
        response = app.make_response(render_template('shared_moment.html', share_token=token, title=row['title']))
        response.headers['Referrer-Policy'] = 'no-referrer'
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Robots-Tag'] = 'noindex, nofollow'
        return response

    @app.route('/api/admin/moment-shares/<int:share_id>', methods=['PUT', 'DELETE'])
    @app.route('/api/admin/moment-shares/<int:share_id>/<action>', methods=['POST'])
    @login_required
    def admin_moment_share(share_id, action=None):
        if not getattr(current_user, 'is_admin', False):
            abort(403)
        body = request.get_json(silent=True) or {}
        if action not in (None, 'revoke', 'activate', 'extend'):
            abort(404)
        with closing(g['get_conn']()) as conn:
            row = conn.execute('SELECT * FROM moment_shares WHERE rowid=?', (share_id,)).fetchone()
            if not row:
                abort(404)
            if request.method == 'DELETE':
                conn.execute('DELETE FROM moment_shares WHERE rowid=?', (share_id,))
            elif action == 'revoke':
                conn.execute('UPDATE moment_shares SET revoked=1 WHERE rowid=?', (share_id,))
            else:
                expires_at, error = g['_share_expires_at_from_body'](body, default_value=7, default_unit='days')
                if error:
                    return jsonify(ok=False, error=error), 400
                title = str(body.get('share_name', row['title'])).strip()[:240] or row['title']
                revoked = 0 if action == 'activate' else row['revoked']
                conn.execute('UPDATE moment_shares SET title=?,expires_at=?,revoked=? WHERE rowid=?', (title, expires_at, revoked, share_id))
            conn.commit()
        return jsonify(ok=True)

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
