"""Admission control, enabled only for FjordHub-managed installations."""
from contextlib import contextmanager
from functools import wraps
import json
import os
from pathlib import Path
import threading
import time
from urllib.request import urlopen

MIB = 1024**2


def current_memory():
    for name in ('/sys/fs/cgroup/memory.current', '/sys/fs/cgroup/memory/memory.usage_in_bytes'):
        try:
            return int(Path(name).read_text().strip())
        except (OSError, ValueError):
            continue
    raise RuntimeError('Kan ikke læse containerens RAM-forbrug')


class MemoryBudget:
    def __init__(self, service=None):
        self.enabled = os.environ.get('FJORDLENS_MEMORY_GUARD') == '1'
        self.service = service or os.environ.get('FJORDLENS_MEMORY_SERVICE', 'fjordlens-ai')
        self.url = os.environ.get('FJORDLENS_MEMORY_URL', 'http://fjordlens-updater:8090/memory')
        self.lock = threading.RLock()
        self.reserved = 0
        self.local = threading.local()
        self.last = {}

    def status(self):
        if not self.enabled:
            return {'ok': True, 'enabled': False}
        try:
            with urlopen(self.url, timeout=2) as response:
                result = json.load(response)
            if not result.get('enabled') or not result.get('ok'):
                raise RuntimeError(result.get('error') or 'RAM-styring er ikke klar')
            return result
        except Exception as exc:
            return {'ok': False, 'enabled': True, 'error': str(exc)}

    def available(self, status):
        if not status.get('ok') or status.get('pressure'):
            return 0
        cap = status.get('containers', {}).get(self.service, {}).get('limit_bytes', 0)
        return max(0, int(cap) - current_memory() - self.reserved - 64*MIB)

    @contextmanager
    def slot(self, estimate, timeout=45):
        if not self.enabled:
            yield
            return
        old = getattr(self.local, 'reserved', 0)
        additional = max(0, int(estimate) - old)
        deadline = time.monotonic() + timeout
        while True:
            status = self.status()
            with self.lock:
                self.last = status
                if additional == 0 or self.available(status) >= additional:
                    self.reserved += additional
                    self.local.reserved = old + additional
                    break
            if time.monotonic() >= deadline:
                raise RuntimeError('RAM-budget: behandlingen afventer ledig hukommelse; prøv igen senere')
            time.sleep(0.5)
        try:
            yield
        finally:
            with self.lock:
                self.reserved -= additional
                self.local.reserved = old

    def guard(self, estimate):
        def decorate(fn):
            @wraps(fn)
            def wrapped(*args, **kwargs):
                cost = estimate() if callable(estimate) else estimate
                with self.slot(cost):
                    return fn(*args, **kwargs)
            return wrapped
        return decorate


MEMORY = MemoryBudget()
