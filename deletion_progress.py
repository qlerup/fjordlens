"""Stream deletion progress without storing jobs or buffering every file event."""
import json
import os
import queue
import threading
from pathlib import Path

from flask import Response, copy_current_request_context, current_app, stream_with_context


def stream_delete(operation):
    events = queue.Queue(maxsize=1)
    app = current_app._get_current_object()
    latest_progress = None

    def publish(event):
        nonlocal latest_progress
        if event['type'] == 'progress':
            latest_progress = event.copy()
        elif event['type'] == 'result':
            event['progress'] = latest_progress
        try:
            events.get_nowait()
        except queue.Empty:
            pass
        events.put_nowait(event)

    @copy_current_request_context
    def run():
        try:
            response = app.make_response(operation(lambda progress: publish({'type': 'progress', **progress})))
            data = response.get_json() or {}
            publish({'type': 'result', 'status': response.status_code, 'data': data})
        except Exception:
            app.logger.exception('Folder deletion failed')
            publish({'type': 'result', 'status': 500, 'data': {'ok': False, 'error': 'Sletningen blev afbrudt.'}})

    threading.Thread(target=run, daemon=True).start()

    @stream_with_context
    def generate():
        while True:
            try:
                event = events.get(timeout=10)
            except queue.Empty:
                event = {'type': 'keepalive'}
            if event['type'] == 'result' and event.get('progress'):
                # A terminal result must not hide the last counts in the single-slot queue.
                yield json.dumps(event.pop('progress'), ensure_ascii=False) + '\n'
            yield json.dumps(event, ensure_ascii=False) + '\n'
            if event['type'] == 'result':
                break

    return Response(generate(), mimetype='application/x-ndjson',
                    headers={'Cache-Control': 'no-store', 'X-Accel-Buffering': 'no'})


def _walk_error(error):
    raise error


def count_files(root):
    total = 0
    for directory, dirs, files in os.walk(root, followlinks=False, onerror=_walk_error):
        total += len(files)
        total += sum((Path(directory) / name).is_symlink() for name in dirs)
    return total


def remove_tree(root, removed):
    """Count each successful unlink; never follow symlink directories."""
    root = Path(root)
    base = root.resolve()
    for directory, dirs, files in os.walk(root, topdown=False, followlinks=False,
                                         onerror=_walk_error):
        parent = Path(directory)
        parent.resolve().relative_to(base)
        for name in files:
            path = parent / name
            # Verify the parent again before touching files, including on Windows.
            path.parent.resolve().relative_to(base)
            path.unlink()
            removed()
        for name in dirs:
            path = parent / name
            path.parent.resolve().relative_to(base)
            if path.is_symlink():
                path.unlink()
                removed()
            else:
                path.resolve().relative_to(base)
                path.rmdir()
    root.rmdir()
