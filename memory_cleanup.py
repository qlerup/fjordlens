"""Return unused glibc heap pages without evicting application caches.

Requests and processing jobs both leave freed allocations in glibc arenas.
Trim periodically outside request handlers, including while the app is idle.
Only already-free pages are returned; live objects and models stay loaded.
"""

import ctypes
import logging
import os
import threading

LOG = logging.getLogger(__name__)
INTERVAL_SECONDS = 60


def _load_trim():
    try:
        trim = ctypes.CDLL(None).malloc_trim
    except (AttributeError, OSError):
        LOG.info("Automatic heap cleanup unavailable: libc has no malloc_trim")
        return None
    trim.argtypes = [ctypes.c_size_t]
    trim.restype = ctypes.c_int
    return trim


class HeapCleanup:
    def __init__(self, interval=INTERVAL_SECONDS):
        self.interval = interval
        self._reset()
        if hasattr(os, "register_at_fork"):
            os.register_at_fork(after_in_child=self._reset)

    def _reset(self):
        # A preloaded Gunicorn app must not inherit another process's thread/lock.
        self._lock = threading.Lock()
        self._started = False
        self._stop = threading.Event()

    def start(self):
        with self._lock:
            if self._started:
                return
            self._started = True
            trim = _load_trim()
            if trim is None:
                return
            threading.Thread(
                target=self._run, args=(trim,), name="heap-cleanup", daemon=True
            ).start()

    def _run(self, trim):
        while not self._stop.wait(self.interval):
            try:
                # glibc serializes allocator access. No forced GC, cache clearing,
                # or dependence on an upload/job counter reaching zero.
                trim(0)
            except Exception:
                LOG.exception("Automatic heap cleanup failed")
                return


def install(app):
    cleanup = HeapCleanup()
    app.extensions["heap_cleanup"] = cleanup
    # Starts once per serving worker, not in the preloading Gunicorn master.
    app.before_request(cleanup.start)
