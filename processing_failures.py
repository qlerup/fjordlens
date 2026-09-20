"""Durable per-file failures, independent of whether metadata was indexed."""
from contextlib import closing
from datetime import datetime, timezone
from functools import wraps
import threading


class FailureTracker:
    def __init__(self, connect):
        self.connect = connect
        self.lock = threading.RLock()
        self.retrying = False
        self.progress = {}

    def connection(self):
        conn = self.connect()
        conn.execute('''CREATE TABLE IF NOT EXISTS processing_failures (
            id INTEGER PRIMARY KEY, rel_path TEXT NOT NULL, stage TEXT NOT NULL,
            error TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 1,
            first_failed_at TEXT NOT NULL, last_failed_at TEXT NOT NULL,
            UNIQUE(rel_path, stage))''')
        conn.commit()
        return conn

    def fail(self, rel, stage, error):
        if not rel:
            return
        now = datetime.now(timezone.utc).isoformat()
        with self.lock, closing(self.connection()) as conn:
            conn.execute('''INSERT INTO processing_failures
                (rel_path,stage,error,first_failed_at,last_failed_at) VALUES (?,?,?,?,?)
                ON CONFLICT(rel_path,stage) DO UPDATE SET error=excluded.error,
                attempts=processing_failures.attempts+1, last_failed_at=excluded.last_failed_at''',
                (str(rel), stage, str(error)[:2000], now, now))
            conn.commit()

    def clear(self, rel, stage):
        with self.lock, closing(self.connection()) as conn:
            conn.execute('DELETE FROM processing_failures WHERE rel_path=? AND stage=?', (str(rel), stage))
            conn.commit()

    def items(self):
        with self.lock, closing(self.connection()) as conn:
            return [dict(row) for row in conn.execute('SELECT * FROM processing_failures ORDER BY id')]

    def relocate(self, old, new):
        if not old or not new or old == new:
            return
        with self.lock, closing(self.connection()) as conn:
            conn.execute('''INSERT INTO processing_failures
                (rel_path,stage,error,attempts,first_failed_at,last_failed_at)
                SELECT ?,stage,error,attempts,first_failed_at,last_failed_at
                FROM processing_failures WHERE rel_path=? AND stage!='conversion'
                ON CONFLICT(rel_path,stage) DO NOTHING''', (new, old))
            conn.execute('DELETE FROM processing_failures WHERE rel_path=?', (old,))
            conn.commit()

    def track(self, stage, path, *, false_failure=False, clear_success=True, enabled=None, result_error=None):
        def decorate(fn):
            @wraps(fn)
            def wrapped(*args, **kwargs):
                rel = path(*args, **kwargs)
                if not rel or (enabled and not enabled(rel)):
                    return fn(*args, **kwargs)
                try:
                    result = fn(*args, **kwargs)
                except Exception as exc:
                    self.fail(rel, stage, exc)
                    raise
                error = result_error(result, *args, **kwargs) if result_error else None
                if error:
                    self.fail(rel, stage, error)
                elif false_failure and result is False:
                    self.fail(rel, stage, 'Behandlingen returnerede intet resultat. Se serviceloggen for detaljer.')
                elif clear_success:
                    self.clear(rel, stage)
                return result
            return wrapped
        return decorate

    def retry(self, items, handler):
        """One pass, one file/stage at a time. Failures remain until actual success."""
        try:
            for item in items:
                with self.lock:
                    self.progress['current'] = item['rel_path']
                # A normal background run may have resolved or updated this failure.
                current = next((r for r in self.items() if r['id'] == item['id']), None)
                if current and current['last_failed_at'] == item['last_failed_at']:
                    try:
                        handler(item['rel_path'], item['stage'])
                    except Exception as exc:
                        self.fail(item['rel_path'], item['stage'], exc)
                with self.lock:
                    self.progress['processed'] += 1
        finally:
            with self.lock:
                self.retrying = False
                self.progress['current'] = None

    def register(self, app, handler, busy=lambda: False):
        from flask import jsonify, request
        from flask_login import current_user, login_required

        @app.route('/api/processing-failures', methods=['GET', 'POST'])
        @login_required
        def processing_failures():
            if not getattr(current_user, 'is_admin', False):
                return jsonify(ok=False, error='Kun administratorer kan se og genkøre fejlede filer.'), 403
            with self.lock:
                items = self.items()
                if request.method == 'POST':
                    if self.retrying or busy():
                        return jsonify(ok=False, error='Vent til den igangværende behandling er færdig.'), 409
                    data = request.get_json(silent=True) or {}
                    if not isinstance(data, dict):
                        return jsonify(ok=False, error='Ugyldig forespørgsel.'), 400
                    ids = data.get('ids')
                    if ids is not None:
                        if not isinstance(ids, list) or any(type(i) is not int for i in ids):
                            return jsonify(ok=False, error='Ugyldigt valg af filer.'), 400
                        items = [row for row in items if row['id'] in ids]
                    order = {'conversion': 0, 'metadata': 1, 'thumbnails': 2, 'faces': 3, 'embeddings': 4, 'descriptions': 5}
                    items.sort(key=lambda row: (order.get(row['stage'], 99), row['id']))
                    self.progress = dict(total=len(items), processed=0, current=None)
                    self.retrying = bool(items)
                    if items:
                        threading.Thread(target=self.retry, args=(items, handler), daemon=True).start()
                return jsonify(ok=True, items=items, running=self.retrying, progress=dict(self.progress))
