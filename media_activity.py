"""Per-file processing/deletion leases shared by threads and web workers."""
import json
import os
import time
import threading
import uuid
from contextlib import closing, contextmanager
from functools import wraps


def canonical(rel):
    rel = str(rel or '').replace('\\', '/').strip('/')
    for prefix in ('uploads/originals/', 'uploads/converted/'):
        if rel.startswith(prefix):
            return 'uploads/' + rel[len(prefix):]
    return rel


def overlaps(left, right):
    files, folders = left
    other_files, other_folders = right
    def inside(path, folder):
        return path == folder or path.startswith(folder + '/')
    return (bool(files & other_files)
            or any(inside(path, folder) for path in files for folder in other_folders)
            or any(inside(path, folder) for path in other_files for folder in folders)
            or any(inside(a, b) or inside(b, a) for a in folders for b in other_folders))


class MediaActivity:
    def __init__(self, connect, process_start):
        self.connect = connect
        self.process_start = process_start
        self.pending = {}
        self.pending_lock = threading.RLock()

    def acquire(self, kind, rels, folders=()):
        files = set(filter(None, map(canonical, rels)))
        folders = set(filter(None, map(canonical, folders)))
        token = uuid.uuid4().hex
        with closing(self.connect()) as conn:
            conn.execute('CREATE TABLE IF NOT EXISTS media_activity(token TEXT PRIMARY KEY, kind TEXT, pid INTEGER, started TEXT, files TEXT, folders TEXT)')
            conn.commit()
            conn.execute('BEGIN IMMEDIATE')
            for row in conn.execute('SELECT * FROM media_activity WHERE kind<>?', (kind,)).fetchall():
                _, existing_kind, pid, started, existing_files, existing_folders = row
                try:
                    os.kill(pid, 0)
                    alive = not started or self.process_start(pid) == started
                except ProcessLookupError:
                    alive = False
                except PermissionError:
                    alive = True
                if not alive:
                    conn.execute('DELETE FROM media_activity WHERE token=?', (row[0],))
                    continue
                if kind != existing_kind and overlaps((files, folders), (set(json.loads(existing_files)), set(json.loads(existing_folders)))):
                    conn.commit()
                    return None
            conn.execute('INSERT INTO media_activity VALUES(?,?,?,?,?,?)',
                         (token, kind, os.getpid(), self.process_start(os.getpid()), json.dumps(sorted(files)), json.dumps(sorted(folders))))
            conn.commit()
        return token

    def release(self, token):
        with closing(self.connect()) as conn:
            conn.execute('DELETE FROM media_activity WHERE token=?', (token,))
            conn.commit()

    def queue(self, rel):
        key = canonical(rel)
        with self.pending_lock:
            if key not in self.pending:
                while (token := self.acquire('processing', [rel])) is None:
                    time.sleep(.05)
                self.pending[key] = token

    def dequeue(self, rels=None):
        with self.pending_lock:
            keys = list(self.pending) if rels is None else list(map(canonical, rels))
            for key in keys:
                token = self.pending.pop(key, None)
                if token:
                    self.release(token)

    @contextmanager
    def processing(self, rels, consume_queue=False):
        # Only a conflicting deletion can delay this file; unrelated work proceeds.
        while (token := self.acquire('processing', rels)) is None:
            time.sleep(.05)
        try:
            if consume_queue:
                self.dequeue(rels)
            yield
        finally:
            self.release(token)

    def track(self, paths, *, consume_queue=False):
        def decorate(operation):
            @wraps(operation)
            def wrapped(*args, **kwargs):
                with self.processing(paths(*args, **kwargs), consume_queue=consume_queue):
                    return operation(*args, **kwargs)
            return wrapped
        return decorate
