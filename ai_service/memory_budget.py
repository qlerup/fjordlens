"""Admission control, enabled only for FjordHub-managed installations."""
from contextlib import contextmanager
from functools import wraps
import json
import os
from pathlib import Path
import threading
import time
import uuid
from urllib.request import Request, urlopen

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
        if status.get('mode') == 'host_global':
            return max(0, int(status.get('available_bytes', 0)))
        cap = status.get('containers', {}).get(self.service, {}).get('limit_bytes', 0)
        # A previously fetched budget must never override a newer hard cap.
        try:
            hard = Path('/sys/fs/cgroup/memory.max').read_text().strip()
            if hard != 'max':
                cap = min(int(cap), int(hard))
        except (OSError, ValueError):
            pass
        return max(0, int(cap) - current_memory() - self.reserved - 64*MIB)

    def reservation(self, action, token, amount=0):
        request = Request(self.url.rstrip('/') + '/' + action,
                          data=json.dumps({'token': token, 'service': self.service, 'bytes': amount}).encode(),
                          headers={'Content-Type': 'application/json'}, method='POST')
        try:
            with urlopen(request, timeout=2) as response:
                return json.load(response)
        except (OSError, ValueError) as exc:
            return {'ok': False, 'granted': False, 'error': str(exc)}

    def _heartbeat(self, token, stopped):
        while not stopped.wait(20):
            result = self.reservation('renew', token)
            if not result.get('ok'):
                print(f'memory_lease_renew_failed service={self.service}', flush=True)

    @contextmanager
    def slot(self, estimate, timeout=45):
        if not self.enabled:
            yield
            return
        old = getattr(self.local, 'reserved', 0)
        additional = max(0, int(estimate) - old)
        deadline = None if timeout is None else time.monotonic() + timeout
        waiting = False
        token = uuid.uuid4().hex
        shared = False
        while True:
            status = self.status()
            with self.lock:
                self.last = status
                shared = status.get('mode') == 'host_global'
                if additional == 0:
                    granted = True
                elif shared:
                    result = self.reservation('reserve', token, additional)
                    granted = bool(result.get('ok') and result.get('granted'))
                else:
                    # During a rolling upgrade an older governor still applies
                    # its old caps. Retain that protection until it is upgraded.
                    granted = self.available(status) >= additional
                if granted:
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
                    scope = 'hele FjordHub' if shared else self.service
                    reason = f'{scope}: {available//MIB} MiB ledig jobplads, kræver {additional//MIB} MiB'
                raise RuntimeError(f'RAM-budget: {reason}; ventede {timeout:g} sekunder')
            time.sleep(0.5)
        heartbeat_stop = threading.Event()
        heartbeat = None
        if shared and additional:
            heartbeat = threading.Thread(target=self._heartbeat, args=(token, heartbeat_stop), daemon=True)
            heartbeat.start()
        try:
            if waiting:
                print(f'memory_resume service={self.service}', flush=True)
            yield
        finally:
            if heartbeat:
                heartbeat_stop.set()
                heartbeat.join(timeout=3)
                if not self.reservation('release', token).get('ok'):
                    print(f'memory_lease_release_failed service={self.service}', flush=True)
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
