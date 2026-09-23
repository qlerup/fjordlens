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

FAILURE_EVENTS = {'ai_embed_fail': 'embeddings', 'ai_desc_fail': 'descriptions',
                  'ai_desc_runtime_error_stop': 'descriptions', 'ai_desc_external_fail': 'descriptions'}
SUCCESS_EVENTS = {'weather_indexed': 'weather', 'weather_saved': 'weather',
                  'thumb_saved': 'thumbnails', 'rethumb_single_ok': 'thumbnails',
                  'faces_index_done': 'faces'}
STAGES = {'metadata', 'conversion', 'thumbnails', 'faces', 'embeddings', 'descriptions', 'weather'}


def is_error_log(item):
    event = str(item.get('event') or '').lower()
    try:
        has_errors = float(item.get('errors') or 0) > 0
    except (TypeError, ValueError):
        has_errors = bool(item.get('errors'))
    return bool(item.get('error') or has_errors or event == 'error'
                or event.endswith(('_error', '_fail', '_failed')))


def unresolved_error_logs(items):
    resolved = set(resolved_log_ids(items))
    return [item for item in items if is_error_log(item) and item['id'] not in resolved]


class StageRetryError(RuntimeError):
    def __init__(self, message, stages):
        super().__init__(message)
        self.stages = stages


def failure_targets(item):
    rel = item.get('rel_path')
    if not rel:
        return []
    event = item.get('event')
    if event == 'log_retry_fail':
        stages = item.get('failed_stages')
        if not stages:
            stages = [part.split(':', 1)[0] for part in str(item.get('error', '')).split('; ')
                      if part.split(':', 1)[0] in STAGES]
        return [(rel, stage) for stage in (stages or [item.get('stage')]) if stage in STAGES]
    if event == 'error':
        prefix = str(item.get('error', '')).split(':', 1)[0]
        stage = item.get('stage') or PREFIX_STAGES.get(prefix)
        if not stage and str(rel).startswith('weather:'):
            stage = 'weather'
        if not stage:
            stage = {'heic_bulk': 'conversion', 'raw_bulk': 'conversion',
                     'mov_bulk': 'conversion', 'rethumb_missing': 'thumbnails'}.get(prefix)
    else:
        stage = FAILURE_EVENTS.get(event)
    return [(rel, stage)] if stage in STAGES else []


def resolved_log_ids(items):
    """A later committed success resolves only older errors for that file/stage."""
    successes = {}
    for item in items:
        stage = item.get('stage') if item.get('event') == 'processing_stage_done' else SUCCESS_EVENTS.get(item.get('event'))
        if stage and item.get('rel_path'):
            successes[(item['rel_path'], stage)] = max(int(item['id']), successes.get((item['rel_path'], stage), 0))
    return [item['id'] for item in items if (targets := failure_targets(item))
            and all(successes.get(target, 0) > int(item['id']) for target in targets)]


def retry_target(item):
    targets = failure_targets(item or {})
    return targets[0] if targets and targets[0][1] != 'conversion' and not str(targets[0][0]).startswith('weather:') else None


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
                     original_log_id=log_id, error=str(exc), failed_stages=getattr(exc, 'stages', [stage]))
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
            if item.get('resolved'):
                return jsonify(ok=True, status='succeeded')
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
