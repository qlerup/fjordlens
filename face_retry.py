"""Pause a face queue on service outages without consuming pending photos."""
import threading
import time
from processing_failures import ServiceUnavailable


def retry_video_frame(extract, detect, allowed, notify, attempts=2, delay=2):
    """Retry the same timestamp, retaining decoded bytes if only AI failed.

    Empty face lists are successful. Missing bytes/results are failures;
    the caller logs exhausted frames and decides whether the video can finish.
    """
    frame = None
    for attempt in range(1, attempts + 1):
        if not allowed():
            raise RuntimeError('stopped')
        error = None
        try:
            if frame is None:
                frame = extract()
            if not allowed():
                raise RuntimeError('stopped')
            if not frame:
                frame = None
                error = 'Video frame could not be decoded'
            else:
                faces = detect(frame)
                if faces is not None:
                    return faces
                error = 'Face detection returned no result'
        except ServiceUnavailable as exc:
            error = str(exc)
        if attempt == attempts:
            raise RuntimeError(f'Video frame failed after {attempts} attempts: {error}')
        notify(attempt, error)
        deadline = time.monotonic() + delay * attempt
        while time.monotonic() < deadline:
            if not allowed():
                raise RuntimeError('stopped')
            time.sleep(min(0.1, max(0, deadline-time.monotonic())))


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
