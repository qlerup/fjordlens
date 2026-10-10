"""Bounded, admin-only photo experiments. No photo-library writes or automatic retries."""
import base64
import io
import json
import math
import queue
import shutil
import tempfile
import threading
import time
import uuid
import warnings
from contextlib import contextmanager
from pathlib import Path

from flask import Blueprint, jsonify, request
from flask_login import current_user
from jsonschema import Draft202012Validator
from PIL import Image, ImageOps, UnidentifiedImageError
from werkzeug.exceptions import RequestEntityTooLarge

from chatgpt_connection import CodexRPC
from chatgpt_analysis_schema import PROMPT, PROMPT_VERSION, SCHEMA, SCHEMA_VERSION

MAX_BYTES = 20 * 1024 * 1024
RUN_SECONDS = 180
RESULT_SECONDS = 900
MARGIN = 2
ERROR = 'Analysen kunne ikke gennemføres. Kontrollér ChatGPT-forbindelsen, og prøv igen.'
CONFIG = {'features.shell_tool': False, 'features.unified_exec': False,
          'features.multi_agent': False, 'features.js_repl': False,
          'features.apply_patch_freeform': False, 'features.remote_plugin': False,
          'features.apps': False, 'web_search': 'disabled', 'history.persistence': 'none'}


class AnalysisError(ValueError):
    pass


def prepare_image(stream):
    raw = stream.read(MAX_BYTES + 1)
    if not raw or len(raw) > MAX_BYTES:
        raise AnalysisError('Vælg et billede på højst 20 MB.')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(raw)) as source:
                if source.format not in {'JPEG', 'PNG', 'WEBP'}:
                    raise AnalysisError('Vælg et JPG-, PNG- eller WebP-billede.')
                if source.width * source.height > 40_000_000:
                    raise AnalysisError('Billedet må højst være 40 megapixel.')
                image = ImageOps.exif_transpose(source)
                image.thumbnail((2048, 2048), Image.Resampling.LANCZOS)
                if image.mode in {'RGBA', 'LA'} or 'transparency' in image.info:
                    rgba = image.convert('RGBA')
                    image = Image.new('RGB', rgba.size, 'white')
                    image.paste(rgba, mask=rgba.getchannel('A'))
                else:
                    image = image.convert('RGB')
                output = io.BytesIO()
                # Re-encode pixels only: filename, EXIF and GPS never leave FjordLens.
                image.save(output, format='JPEG', quality=90)
                return output.getvalue()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise AnalysisError('Billedet kunne ikke læses. Vælg et gyldigt JPG-, PNG- eller WebP-billede.') from None


@contextmanager
def connected_rpc(store, executable):
    ident = uuid.uuid4().hex
    with store.db() as db:
        db.execute('BEGIN IMMEDIATE')
        operation = store.read(db, 'account_operation')
        if operation and operation['expires_at'] > time.time():
            raise AnalysisError('ChatGPT-forbindelsen er optaget af en anden handling. Prøv igen om lidt.')
        store.write(db, 'account_operation', dict(id=ident, expires_at=time.time() + RUN_SECONDS))
    try:
        with _connected_rpc(store, executable) as rpc:
            yield rpc
    finally:
        with store.db() as db:
            db.execute('BEGIN IMMEDIATE')
            operation = store.read(db, 'account_operation')
            if operation and operation['id'] == ident:
                db.execute('DELETE FROM account_operation')


@contextmanager
def _connected_rpc(store, executable):
    with store.db() as db:
        record = store.read(db, 'connection')
    if not record:
        raise AnalysisError('Tilslut først din ChatGPT-konto.')
    with tempfile.TemporaryDirectory(prefix='fjordlens-analysis-') as directory:
        home = Path(directory)
        home.chmod(0o700)
        work = home / 'work'
        work.mkdir()
        auth_path = home / 'auth.json'
        auth_path.write_text(json.dumps(record['codex_auth']), encoding='utf-8')
        auth_path.chmod(0o600)
        # Separate empty cwd avoids project instructions, skills and configuration.
        config_lines = ['cli_auth_credentials_store = "file"', 'forced_login_method = "chatgpt"',
                        'web_search = "disabled"', 'history.persistence = "none"', '[features]']
        config_lines += [f'{k.split(".", 1)[1]} = false' for k in CONFIG if k.startswith('features.')]
        (home / 'config.toml').write_text('\n'.join(config_lines), encoding='utf-8')
        rpc = None
        try:
            rpc = CodexRPC(home, executable)
            rpc.deadline = time.monotonic() + 150
            rpc.request('initialize', {'clientInfo': {'name': 'fjordlens', 'title': 'FjordLens', 'version': '1.1'}})
            rpc.send({'method': 'initialized', 'params': {}})
            account = rpc.request('account/read', {'refreshToken': True}).get('account') or {}
            if account.get('type') != 'chatgpt':
                raise AnalysisError('ChatGPT-login er udløbet. Tilslut kontoen igen.')
            yield rpc, work
        finally:
            if rpc:
                rpc.close()
            # Persist token rotation, but never resurrect logout/replaced credentials.
            if auth_path.exists():
                refreshed = json.loads(auth_path.read_text(encoding='utf-8'))
                with store.db() as db:
                    db.execute('BEGIN IMMEDIATE')
                    current = store.read(db, 'connection')
                    if current and current['codex_auth'] == record['codex_auth']:
                        current['codex_auth'] = refreshed
                        store.write(db, 'connection', current)


def list_models(rpc):
    models, cursor = [], None
    for _ in range(10):
        data = rpc.request('model/list', {'limit': 100, 'includeHidden': False, 'cursor': cursor})
        models.extend(m for m in data.get('data', []) if 'image' in m.get('inputModalities', ['text', 'image']))
        cursor = data.get('nextCursor')
        if not cursor:
            return models
    raise AnalysisError('Modellisten kunne ikke indlæses fuldstændigt.')


def usage_status(data, threshold):
    """Conservatively check every returned pool; never infer capacity from resets."""
    pools = data.get('rateLimitsByLimitId')
    if not pools:
        snapshot = data.get('rateLimits')
        pools = {snapshot.get('limitId') or 'codex': snapshot} if isinstance(snapshot, dict) else {}
    windows = []
    for ident, pool in pools.items():
        if not isinstance(pool, dict):
            raise AnalysisError('Forbrugsstatus er ukendt. Intet billede er sendt til analyse.')
        for key in ['primary', 'secondary']:
            window = pool.get(key)
            if window is None:
                continue
            used = window.get('usedPercent') if isinstance(window, dict) else None
            if type(used) not in (int, float) or not math.isfinite(used) or not 0 <= used <= 100:
                raise AnalysisError('Forbrugsstatus er ukendt. Intet billede er sendt til analyse.')
            windows.append(dict(pool=ident, label=pool.get('limitName') or ident, window=key,
                                used_percent=used, duration_minutes=window.get('windowDurationMins'),
                                resets_at=window.get('resetsAt')))
        if pool.get('rateLimitReachedType') or pool.get('spendControlReached') is True:
            raise AnalysisError('Kontoens kapacitetsgrænse er nået. Testen bruger ikke ekstra betalt kapacitet.')
    if not windows or data.get('ordinaryUsageAllowed') is not True:
        raise AnalysisError('Almindelig inkluderet kapacitet kunne ikke bekræftes. Intet billede er sendt til analyse.')
    if any(w['used_percent'] >= threshold - MARGIN for w in windows):
        raise AnalysisError(f'Testen er stoppet ved forbrugsgrænsen på {threshold} % (2 procentpoints sikkerhedsmargin).')
    return dict(windows=windows, measured_at=int(time.time()), threshold=threshold, safety_margin=MARGIN)


def validate_result(text):
    if len(text) > 256_000:
        raise AnalysisError('Analysesvaret er for stort.')
    try:
        def reject_constant(value):
            raise ValueError('Non-JSON number')
        result = json.loads(text, parse_constant=reject_constant)
        Draft202012Validator(SCHEMA).validate(result)
    except Exception:
        raise AnalysisError('ChatGPT returnerede et ugyldigt analysesvar. Prøv igen.') from None
    return result


def read_job(store, db):
    job = store.read(db, 'test_analysis')
    if job and job['expires_at'] <= time.time():
        db.execute('DELETE FROM test_analysis')
        return None
    if job and job['state'] == 'running' and job['deadline'] <= time.time():
        job.update(state='failed', error='Testen udløb eller blev afbrudt ved en servergenstart. Prøv igen.')
        store.write(db, 'test_analysis', job)
    return job


def update_job(store, ident, **changes):
    with store.db() as db:
        db.execute('BEGIN IMMEDIATE')
        job = read_job(store, db)
        if job and job['id'] == ident and job['state'] == 'running':
            job.update(changes)
            store.write(db, 'test_analysis', job)


def run_analysis(store, ident, image, model, threshold, executable):
    try:
        with connected_rpc(store, executable) as (rpc, work):
            available = list_models(rpc)
            selected = next((m for m in available if m['model'] == model), None)
            if not selected:
                raise AnalysisError('Den valgte model understøtter ikke billedinput på denne konto.')
            usage = usage_status(rpc.request('account/rateLimits/read'), threshold)
            update_job(store, ident, usage=usage)
            thread = rpc.request('thread/start', dict(model=model, modelProvider='openai', cwd=str(work),
                approvalPolicy='never', sandbox='read-only', ephemeral=True, config=CONFIG,
                baseInstructions=PROMPT, developerInstructions='Ingen værktøjer. Kun billedanalyse efter schema.'))
            thread_id = thread['thread']['id']
            turn = rpc.request('turn/start', dict(threadId=thread_id, model=model,
                effort=selected.get('defaultReasoningEffort'), outputSchema=SCHEMA,
                input=[dict(type='text', text=PROMPT),
                       dict(type='image', url='data:image/jpeg;base64,' + base64.b64encode(image).decode())]))
            turn_id = turn['turn']['id']
            messages = {}
            deadline = min(time.monotonic() + 100, rpc.deadline)
            while time.monotonic() < deadline:
                try:
                    message = rpc.notifications.pop(0) if rpc.notifications else rpc.messages.get(timeout=1)
                except queue.Empty:
                    continue
                if message is None:
                    raise AnalysisError(ERROR)
                if 'id' in message:
                    rpc.send(dict(id=message['id'], error={'code': -32601, 'message': 'Tools are disabled'}))
                    raise AnalysisError('Modellen forsøgte at bruge et værktøj. Testen er afbrudt.')
                params = message.get('params', {})
                if params.get('threadId') != thread_id or params.get('turnId', turn_id) != turn_id:
                    continue
                if message.get('method') == 'item/completed':
                    item = params.get('item', {})
                    if item.get('type') == 'agentMessage' and item.get('phase') != 'commentary':
                        messages[item['id']] = item.get('text', '')
                    elif item.get('type') in {'commandExecution', 'fileChange', 'mcpToolCall', 'webSearch'}:
                        raise AnalysisError('Modellen forsøgte at bruge et værktøj. Testen er afbrudt.')
                if message.get('method') == 'turn/completed':
                    completed = params.get('turn', {})
                    if completed.get('id') != turn_id or completed.get('status') != 'completed':
                        raise AnalysisError(ERROR)
                    for item in completed.get('items', []):
                        if item.get('type') == 'agentMessage' and item.get('phase') != 'commentary':
                            messages[item['id']] = item.get('text', '')
                    result = validate_result('\n'.join(messages.values()))
                    update_job(store, ident, state='completed', result=result, metadata=dict(
                        image_id=None, model=model, provider='chatgpt', prompt_version=PROMPT_VERSION,
                        schema_version=SCHEMA_VERSION, analyzed_at=int(time.time()), temporary=True))
                    return
            raise AnalysisError('Analysen tog for lang tid. Prøv igen.')
    except AnalysisError as error:
        update_job(store, ident, state='failed', error=str(error))
    except Exception:
        update_job(store, ident, state='failed', error=ERROR)


def register(app, store, protect, no_cache):
    bp = Blueprint('chatgpt_analysis', __name__)
    bp.before_request(protect)
    bp.after_request(no_cache)

    @bp.errorhandler(RequestEntityTooLarge)
    def too_large(error):
        return jsonify(ok=False, error='Vælg et billede på højst 20 MB.'), 413

    @bp.get('/api/ai/chatgpt/test-models')
    def models():
        executable = shutil.which('codex')
        if not executable:
            return jsonify(ok=False, error='Opdatér FjordLens-containeren for at bruge ChatGPT.'), 503
        try:
            with connected_rpc(store, executable) as (rpc, _):
                entries = list_models(rpc)
                return jsonify(ok=True, models=[dict(id=m['model'], label=m['displayName'],
                                                      default=m.get('isDefault', False)) for m in entries])
        except AnalysisError as error:
            return jsonify(ok=False, error=str(error)), 409
        except Exception:
            return jsonify(ok=False, error='Modeller kunne ikke indlæses. Kontrollér ChatGPT-login.'), 503

    @bp.post('/api/ai/chatgpt/test-analysis')
    def start():
        request.max_content_length = MAX_BYTES + 1024 * 1024
        try:
            upload = request.files.get('image')
            model = request.form.get('model', '')
            threshold = int(request.form.get('threshold', '80'))
            if not upload or not model or len(model) > 120 or not 5 <= threshold <= 100:
                raise AnalysisError('Vælg billede, model og en forbrugsgrænse mellem 5 og 100 %.')
            image = prepare_image(upload.stream)
            executable = shutil.which('codex')
            if not executable:
                raise AnalysisError('Opdatér FjordLens-containeren for at bruge ChatGPT.')
            with store.db() as db:
                db.execute('BEGIN IMMEDIATE')
                job = read_job(store, db)
                if job and job['state'] == 'running':
                    return jsonify(ok=False, error='En testanalyse er allerede i gang. Vent til den er færdig.'), 409
                if not store.read(db, 'connection'):
                    raise AnalysisError('Tilslut først din ChatGPT-konto.')
                ident = uuid.uuid4().hex
                job = dict(id=ident, owner=str(current_user.id), state='running',
                           deadline=time.time() + RUN_SECONDS, expires_at=time.time() + RESULT_SECONDS)
                store.write(db, 'test_analysis', job)
            try:
                threading.Thread(target=run_analysis, args=(store, ident, image, model, threshold, executable),
                                 daemon=True).start()
            except Exception:
                update_job(store, ident, state='failed', error=ERROR)
                raise AnalysisError(ERROR) from None
            return jsonify(ok=True, id=ident, state='running'), 202
        except (AnalysisError, ValueError) as error:
            return jsonify(ok=False, error=str(error) if isinstance(error, AnalysisError) else 'Ugyldig forbrugsgrænse.'), 400

    @bp.get('/api/ai/chatgpt/test-analysis/<ident>')
    def status(ident):
        with store.db() as db:
            db.execute('BEGIN IMMEDIATE')
            job = read_job(store, db)
        if not job or job['id'] != ident or job['owner'] != str(current_user.id):
            return jsonify(ok=False, error='Testresultatet er udløbet. Start en ny test.'), 404
        return jsonify(ok=True, **{k: v for k, v in job.items() if k not in {'owner', 'deadline'}})

    @bp.delete('/api/ai/chatgpt/test-analysis/<ident>')
    def discard(ident):
        with store.db() as db:
            db.execute('BEGIN IMMEDIATE')
            job = read_job(store, db)
            if job and job['id'] == ident and job['owner'] == str(current_user.id):
                if job['state'] == 'running':
                    return jsonify(ok=False, error='Analysen er stadig i gang.'), 409
                db.execute('DELETE FROM test_analysis')
        return jsonify(ok=True)

    app.register_blueprint(bp)
