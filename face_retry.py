"""Pause a face queue on service outages without consuming pending photos."""
import threading
import time
from processing_failures import ServiceUnavailable


class FaceRetryGate:
    def __init__(self, notify, delay=5):
        self.notify = notify
        self.delay = delay
        self.lock = threading.Lock()
        self.probe = threading.Lock()
        self.paused = False
        self.retry_at = 0

    def run(self, operation, allowed):
        while allowed():
            with self.lock:
                paused = self.paused
            acquired = False
            try:
                if paused:
                    acquired = self.probe.acquire(timeout=0.25)
                    if not acquired:
                        continue
                    while allowed() and time.monotonic() < self.retry_at:
                        time.sleep(0.1)
                    if not allowed():
                        break
                result = operation()
                with self.lock:
                    if acquired and self.paused:
                        self.paused = False
                        self.notify('')
                return result
            except ServiceUnavailable as exc:
                with self.lock:
                    self.retry_at = time.monotonic() + self.delay
                    if not self.paused:
                        self.paused = True
                        self.notify(str(exc))
            finally:
                if acquired:
                    self.probe.release()
        raise RuntimeError('stopped')
