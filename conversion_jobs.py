"""Shared bulk-conversion status and process-owned exclusion locks."""
import errno
import json
import os
import tempfile
from pathlib import Path


class ConversionJob:
    def __init__(self, directory, kind):
        if kind not in {'heic', 'raw', 'mov', 'upload-recovery', 'postprocess'}:
            raise ValueError('Unknown conversion type')
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path = self.directory / (kind + '.json')
        self.lock_path = self.directory / (kind + '.lock')

    def acquire(self):
        handle = self.lock_path.open('a+b')
        try:
            if os.name == 'nt':
                import msvcrt
                if self.lock_path.stat().st_size == 0:
                    handle.write(b'0')
                    handle.flush()
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return handle
        except OSError as exc:
            handle.close()
            if exc.errno in {errno.EACCES, errno.EAGAIN}:
                return None
            raise

    def save(self, state):
        fd, name = tempfile.mkstemp(dir=self.directory, prefix=self.path.stem + '-', suffix='.tmp')
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as stream:
                json.dump(state, stream, ensure_ascii=False)
            os.replace(name, self.path)
        finally:
            if os.path.exists(name):
                os.unlink(name)

    def status(self):
        lock = self.acquire()
        try:
            try:
                state = json.loads(self.path.read_text(encoding='utf-8'))
            except FileNotFoundError:
                state = {'running': False, 'result': None, 'progress': None}
            if lock is None:
                # The owner can be between acquiring the lock and publishing its first snapshot.
                return {'ok': True, 'running': True, 'result': None,
                        'progress': state.get('progress') or {'phase': 'checking'}}
            if state.get('running'):
                return {'ok': True, 'running': False, 'progress': None,
                        'result': {'ok': False, 'error': 'Konverteringen blev afbrudt af en genstart eller et crash. Start igen for at fortsætte med de manglende filer.'}}
            return {'ok': True, **state}
        finally:
            if lock is not None:
                lock.close()
