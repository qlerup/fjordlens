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


def _clean_inactive_cache(text, *, legacy=False):
    stats = {key: int(value) for key, value in (line.split() for line in text.splitlines())}
    if any(value < 0 for value in stats.values()):
        raise ValueError('Negative memory statistic')
    prefix = 'total_' if legacy and 'total_inactive_file' in stats else ''
    inactive = stats[prefix + 'inactive_file']
    file_bytes = stats[prefix + ('cache' if legacy else 'file')]
    # Shared memory, dirty pages and pages being written back are not spare job RAM.
    protected = sum(stats.get(prefix + key, 0) for key in
                    (('shmem', 'dirty', 'writeback') if legacy else ('shmem', 'file_dirty', 'file_writeback')))
    return max(0, min(inactive, file_bytes) - protected)


def current_memory():
    """Admission working set: raw cgroup usage less clean, inactive file cache.

    Docker's hard cap still includes every page. Only the job-admission estimate
    discounts cache that Linux can reclaim; missing stats fall back to raw usage.
    """
    for name, legacy in (('/sys/fs/cgroup/memory.current', False),
                         ('/sys/fs/cgroup/memory/memory.usage_in_bytes', True)):
        try:
            usage = int(Path(name).read_text().strip())
        except (OSError, ValueError):
            continue
        try:
            cache = _clean_inactive_cache(Path(name).with_name('memory.stat').read_text(), legacy=legacy)
            # Separate kernel reads can straddle reclaim. Inconsistent samples
            # must not create artificial headroom.
            if 0 <= cache <= usage:
                return usage - cache
        except (OSError, ValueError, KeyError):
            pass
        return usage
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
        deadline = None if timeout is None else time.monotonic() + timeout
        waiting = False
        while True:
            status = self.status()
            with self.lock:
                self.last = status
                if additional == 0 or self.available(status) >= additional:
                    self.reserved += additional
                    self.local.reserved = old + additional
                    break
            if not waiting:
                print(f'memory_wait service={self.service} required_mib={additional//MIB}', flush=True)
                waiting = True
            if deadline is not None and time.monotonic() >= deadline:
                if not status.get('ok'):
                    reason = status.get('error') or 'Ingen gyldig budgetmåling'
                elif status.get('pressure'):
                    reason = 'Systemets RAM-reserve er under pres'
                else:
                    with self.lock:
                        available = self.available(status)
                    reason = f'{self.service}: {available//MIB} MiB ledig jobplads, kræver {additional//MIB} MiB'
                raise RuntimeError(f'RAM-budget: {reason}; ventede {timeout:g} sekunder')
            time.sleep(0.5)
        try:
            if waiting:
                print(f'memory_resume service={self.service}', flush=True)
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
