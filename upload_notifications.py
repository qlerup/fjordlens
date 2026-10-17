"""Durable upload summaries. Hub downtime never interrupts media processing."""
from contextlib import contextmanager
import json
import logging
from pathlib import Path
import sqlite3
import threading
import uuid

LOG = logging.getLogger(__name__)
ERROR_FIELDS = ('index_errors', 'thumb_errors', 'faces_errors', 'ai_errors', 'ai_desc_errors')


def summary_event(user, rels, result, video_exts, *, stopped=False, failed=False):
    paths = list(dict.fromkeys(rels))
    stats = {key: max(0, int(result.get(key) or 0)) for key in (
        'indexed', 'heic_converted', 'faces_done', 'face_count', 'ai_done', 'ai_desc_done', *ERROR_FIELDS)}
    stats.update(files=len(paths), videos=sum(Path(p).suffix.lower() in video_exts for p in paths))
    stats['images'] = stats['files'] - stats['videos']
    stats.update({key: bool(result.get(key)) for key in ('faces_enabled', 'ai_enabled', 'ai_desc_enabled')})
    return {'type': 'upload_finished', 'event_id': uuid.uuid4().hex,
            'uploader': str(user or 'Direkte import')[:90], 'stats': stats,
            'status': 'failed' if failed else 'stopped' if stopped else 'completed'}


class UploadNotifications:
    def __init__(self, root, api, enabled, autostart=True):
        self.path = Path(root) / 'upload-notifications.sqlite3'
        self.api, self.enabled = api, enabled
        self.lock = threading.Lock()
        if autostart and enabled():
            threading.Thread(target=self.run, daemon=True, name='upload-notifications').start()

    @contextmanager
    def connect(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(self.path, timeout=10)
        con.execute('CREATE TABLE IF NOT EXISTS pending(event_id TEXT PRIMARY KEY, payload TEXT NOT NULL)')
        try:
            with con:
                yield con
        finally:
            con.close()

    def enqueue(self, event):
        if not self.enabled():
            return
        with self.connect() as con:
            con.execute('INSERT OR IGNORE INTO pending VALUES(?,?)', (event['event_id'], json.dumps(event)))

    def flush(self):
        if not self.enabled() or not self.lock.acquire(blocking=False):
            return
        try:
            with self.connect() as con:
                rows = con.execute('SELECT event_id,payload FROM pending ORDER BY rowid LIMIT 50').fetchall()
            for event_id, raw in rows:
                response = self.api('/api/hub/apps/notifications', json.loads(raw))
                if not response.get('ok'):
                    return
                with self.connect() as con:
                    con.execute('DELETE FROM pending WHERE event_id=?', (event_id,))
        finally:
            self.lock.release()

    def run(self):
        wait = threading.Event()
        while True:
            try:
                self.flush()
            except Exception:
                LOG.warning('Upload summary delivery unavailable; will retry')
            wait.wait(10)
