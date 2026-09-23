"""Retry known per-file log failures using server-owned targets."""
import threading


PREFIX_STAGES = {
    'postprocess_index': 'metadata',
    'postprocess_thumb': 'thumbnails',
    'rethumb_single': 'thumbnails',
    'postprocess_faces_queue': 'faces',
    'postprocess_ai': 'embeddings',
    'postprocess_ai_desc': 'descriptions',
    'weather_index': 'weather',
}


def retry_target(item):
    if not item or item.get('event') != 'error' or not item.get('rel_path'):
        return None
    stage = PREFIX_STAGES.get(str(item.get('error', '')).split(':', 1)[0])
    return (item['rel_path'], stage) if stage else None


def missing_stages(row, *, thumbnail_exists, faces, embeddings, descriptions):
    """Plan only unfinished, enabled work; zero detected faces is still complete."""
    stages = []
    if not thumbnail_exists:
        stages.append('thumbnails')
    if faces and not row.get('faces_indexed_at'):
        stages.append('faces')
    if embeddings and str(row.get('embedding_json') or '').strip() in {'', '[]', 'null'}:
        stages.append('embeddings')
    if descriptions and (not str(row.get('ai_desc_caption') or '').strip()
                         or str(row.get('ai_desc_tags') or '').strip() in {'', '[]', 'null'}):
        stages.append('descriptions')
    return stages


class LogRetries:
    def __init__(self, tracker, lookup, handler, log, busy):
        self.tracker, self.lookup, self.handler = tracker, lookup, handler
        self.log, self.busy = log, busy
        self.states = {}

    def describe(self, item):
        with self.tracker.lock:
            return dict(item, retry_stage=(retry_target(item) or (None, None))[1],
                        retry=dict(self.states.get(item['id'], {})))

    def run(self, log_id, rel, stage):
        result = {'status': 'failed'}
        try:
            self.log('log_retry_started', rel_path=rel, stage=stage, original_log_id=log_id)
            self.handler(rel, stage)
            remaining = next((item for item in self.tracker.items()
                              if item['rel_path'] == rel and item['stage'] == stage), None)
            if remaining:
                raise RuntimeError(remaining['error'])
            result = {'status': 'succeeded'}
            self.log('log_retry_done', rel_path=rel, stage=stage, original_log_id=log_id)
        except Exception as exc:
            result = {'status': 'failed', 'error': str(exc)}
            self.log('log_retry_fail', rel_path=rel, stage=stage,
                     original_log_id=log_id, error=str(exc))
        finally:
            with self.tracker.lock:
                self.states[log_id] = result
                self.tracker.retrying = False

    def register(self, app):
        from flask import jsonify, request
        from flask_login import current_user, login_required

        @app.route('/api/logs/<int:log_id>/retry', methods=['GET', 'POST'])
        @login_required
        def retry_log(log_id):
            if not getattr(current_user, 'is_admin', False):
                return jsonify(ok=False, error='Kun administratorer kan genkøre fejlede trin.'), 403
            item = self.lookup(log_id)
            target = retry_target(item)
            if not target:
                return jsonify(ok=False, error='Denne log kan ikke genkøres.'), 404
            with self.tracker.lock:
                previous = self.states.get(log_id, {})
                if request.method == 'POST' and previous.get('status') not in {'running', 'succeeded'}:
                    if self.tracker.retrying or self.busy():
                        return jsonify(ok=False, error='Vent til den igangværende behandling er færdig, og prøv igen.'), 409
                    self.tracker.retrying = True
                    self.states[log_id] = {'status': 'running'}
                    try:
                        threading.Thread(target=self.run, args=(log_id, *target), daemon=True).start()
                    except Exception:
                        self.tracker.retrying = False
                        self.states.pop(log_id, None)
                        raise
                return jsonify(ok=True, **self.states.get(log_id, {'status': 'idle'}))
