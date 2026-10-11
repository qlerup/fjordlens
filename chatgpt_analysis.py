"""Bounded, admin-only photo experiments. No photo-library writes or automatic retries."""
import base64
import hashlib
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
from pillow_heif import register_heif_opener
import rawpy
from werkzeug.exceptions import RequestEntityTooLarge

from chatgpt_connection import CodexRPC
from chatgpt_analysis_schema import PROMPT, PROMPT_VERSION, SCHEMA, SCHEMA_VERSION

MAX_BYTES = 20 * 1024 * 1024
RAW_EXTENSIONS = {'.dng', '.cr2', '.cr3', '.nef', '.arw', '.rw2', '.raf', '.orf', '.srw', '.pef', '.raw'}
register_heif_opener()
RUN_SECONDS = 180
RESULT_SECONDS = 900
ERROR = 'Analysen kunne ikke gennemføres. Kontrollér ChatGPT-forbindelsen, og prøv igen.'
CONFIG = {'features.shell_tool': False, 'features.unified_exec': False,
          'features.multi_agent': False, 'features.js_repl': False,
          'features.apply_patch_freeform': False, 'features.remote_plugin': False,
          'features.apps': False, 'web_search': 'disabled', 'history.persistence': 'none'}


class AnalysisError(ValueError):
    pass


def prepare_image(stream, filename=''):
    raw = stream.read(MAX_BYTES + 1)
    if not raw or len(raw) > MAX_BYTES:
        raise AnalysisError('Vælg et billede på højst 20 MB.')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            if Path(filename).suffix.lower() in RAW_EXTENSIONS:
                # Decode the sensor image, never a potentially tiny embedded preview.
                with rawpy.RawPy() as sensor:
                    sensor.open_buffer(io.BytesIO(raw))
                    if sensor.sizes.width * sensor.sizes.height > 40_000_000:
                        raise AnalysisError('Billedet må højst være 40 megapixel.')
                    # Accessing sizes already unpacks in rawpy 0.24; do not unpack twice.
                    source = Image.fromarray(sensor.postprocess(use_camera_wb=True,
                        output_color=rawpy.ColorSpace.sRGB, output_bps=8,
                        half_size=min(sensor.sizes.width, sensor.sizes.height) >= 4096))
            else:
                source = Image.open(io.BytesIO(raw))
            with source:
                if source.format not in {None, 'JPEG', 'PNG', 'WEBP', 'HEIF'}:
                    raise AnalysisError('Vælg et JPG-, PNG-, WebP-, HEIC- eller RAW-billede.')
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
    except (UnidentifiedImageError, OSError, ValueError, rawpy.LibRawError, rawpy.NotSupportedError,
            Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        if isinstance(exc, AnalysisError):
            raise
        raise AnalysisError('Billedet kunne ikke læses. Vælg et gyldigt JPG-, PNG-, WebP-, HEIC- eller understøttet RAW-billede.') from None


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


def usage_status(data, remaining=None, allow_exhausted=False):
    """Conservatively check every returned pool; never infer capacity from resets."""
    pools = data.get('rateLimitsByLimitId')
    if not pools:
        snapshot = data.get('rateLimits')
        pools = {snapshot.get('limitId') or 'codex': snapshot} if isinstance(snapshot, dict) else {}
    windows = []
    capacity_blocked = False
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
                                used_percent=used, remaining_percent=100-used, duration_minutes=window.get('windowDurationMins'),
                                resets_at=window.get('resetsAt')))
        if pool.get('rateLimitReachedType') or pool.get('spendControlReached') is True:
            capacity_blocked = True
    ordinary_allowed = data.get('ordinaryUsageAllowed') is True
    if capacity_blocked and not allow_exhausted:
        raise AnalysisError('Kontoens kapacitetsgrænse er nået. Testen bruger ikke ekstra betalt kapacitet.')
    if not windows or not ordinary_allowed and not allow_exhausted:
        raise AnalysisError('Almindelig inkluderet kapacitet kunne ikke bekræftes. Intet billede er sendt til analyse.')
    if remaining is not None and any(w['remaining_percent'] <= remaining for w in windows):
        raise AnalysisError(f'Testen afventer reset ved forbrugsgrænsen på {remaining} % tilbage.')
    return dict(windows=windows, measured_at=int(time.time()), remaining_percent=remaining,
                ordinary_allowed=ordinary_allowed, capacity_blocked=capacity_blocked)


def budget_settings(store, remaining=None):
    with store.db() as db:
        db.execute('BEGIN IMMEDIATE')
        settings = store.read(db, 'analysis_budget') or dict(remaining_percent=50, wait=None)
        if remaining is not None:
            if type(remaining) is not int or not 0 <= remaining <= 99:
                raise AnalysisError('Vælg en grænse mellem 0 og 99 procent tilbage.')
            settings['remaining_percent'] = remaining
            store.write(db, 'analysis_budget', settings)
    return settings


def budget_status(store, data):
    """Persist a pause until a fresh snapshot confirms each blocked window reset."""
    usage = usage_status(data, allow_exhausted=True)
    now = time.time()
    with store.db() as db:
        db.execute('BEGIN IMMEDIATE')
        settings = store.read(db, 'analysis_budget') or dict(remaining_percent=50, wait=None)
        account = store.read(db, 'connection') or {}
        identity = account.get('codex_auth', {}).get('tokens', {}).get('account_id') or account.get('email', '')
        account_key = hashlib.sha256(str(identity).encode()).hexdigest()
        if settings.get('account') not in (None, account_key):
            settings['wait'] = None
        settings['account'] = account_key
        windows = {(w['pool'], w['window']): w for w in usage['windows']}
        wait = settings.get('wait')
        holds = {}
        for previous in (wait or {}).get('windows', []):
            key = (previous['pool'], previous['window'])
            current = windows.get(key)
            old_reset = previous.get('resets_at')
            new_reset = (current or {}).get('resets_at')
            known = type(old_reset) in (int, float) and math.isfinite(old_reset) and old_reset > 0
            reset = bool(current and usage['ordinary_allowed'] and not usage['capacity_blocked'] and (
                known and now >= old_reset and type(new_reset) in (int, float) and new_reset > old_reset
                and current['used_percent'] < previous['used_percent']
                or not known and current['used_percent'] == 0 and previous['used_percent'] > 0))
            if not reset:
                holds[key] = previous
        for key, window in windows.items():
            if window['remaining_percent'] <= settings['remaining_percent']:
                holds.setdefault(key, window)
        settings['wait'] = dict(since=(wait or {}).get('since', int(now)), windows=list(holds.values())) if holds else None
        settings['usage'] = usage
        store.write(db, 'analysis_budget', settings)
    if not holds and (not usage['ordinary_allowed'] or usage['capacity_blocked']):
        raise AnalysisError('Almindelig inkluderet kapacitet kunne ikke bekræftes. Intet billede er sendt til analyse.')
    resets = [w.get('resets_at') for w in holds.values()]
    reset_at = max(resets) if resets and all(type(r) in (int,float) and math.isfinite(r) and r > now for r in resets) else None
    return dict(remaining_percent=settings['remaining_percent'], waiting=bool(holds),
                reset_at=reset_at, usage=usage, fresh=True)


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


def run_analysis(store, ident, image, model, executable):
    try:
        with connected_rpc(store, executable) as (rpc, work):
            available = list_models(rpc)
            selected = next((m for m in available if m['model'] == model), None)
            if not selected:
                raise AnalysisError('Den valgte model understøtter ikke billedinput på denne konto.')
            budget = budget_status(store, rpc.request('account/rateLimits/read'))
            update_job(store, ident, usage=budget['usage'])
            if budget['waiting']:
                update_job(store, ident, state='waiting', error=f"Afventer kontoens reset. Stopgrænse: {budget['remaining_percent']} % tilbage.")
                return
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
                budget = budget_status(store, rpc.request('account/rateLimits/read'))
                return jsonify(ok=True, models=[dict(id=m['model'], label=m['displayName'],
                                                      default=m.get('isDefault', False)) for m in entries], budget=budget)
        except AnalysisError as error:
            return jsonify(ok=False, error=str(error)), 409
        except Exception:
            return jsonify(ok=False, error='Modeller kunne ikke indlæses. Kontrollér ChatGPT-login.'), 503

    @bp.route('/api/ai/chatgpt/analysis-budget', methods=['GET', 'PUT'])
    def budget():
        if request.method == 'PUT':
            value = (request.get_json(silent=True) or {}).get('remaining_percent')
            if type(value) is not int or not 0 <= value <= 99:
                return jsonify(ok=False, error='Vælg en grænse mellem 0 og 99 procent tilbage.'), 400
            budget_settings(store, value)
        try:
            executable = shutil.which('codex')
            if not executable:
                raise AnalysisError('Opdatér FjordLens-containeren for at bruge ChatGPT.')
            with connected_rpc(store, executable) as (rpc, _):
                status = budget_status(store, rpc.request('account/rateLimits/read'))
            return jsonify(ok=True, budget=status)
        except AnalysisError as error:
            settings = budget_settings(store)
            return jsonify(ok=True, budget=dict(remaining_percent=settings['remaining_percent'],
                waiting=bool(settings.get('wait')), usage=settings.get('usage'), fresh=False, error=str(error)))
        except Exception:
            return jsonify(ok=False, error='Kontoens aktuelle kapacitet kunne ikke hentes.'), 503

    @bp.post('/api/ai/chatgpt/test-analysis')
    def start():
        request.max_content_length = MAX_BYTES + 1024 * 1024
        try:
            upload = request.files.get('image')
            model = request.form.get('model', '')
            value = request.form.get('remaining_percent')
            legacy = request.form.get('threshold')
            remaining = int(value) if value is not None else 100-int(legacy) if legacy is not None else budget_settings(store)['remaining_percent']
            if not upload or not model or len(model) > 120 or not 0 <= remaining <= 99:
                raise AnalysisError('Vælg billede, model og en grænse mellem 0 og 99 procent tilbage.')
            image = prepare_image(upload.stream, upload.filename or '')
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
                settings = store.read(db, 'analysis_budget') or dict(wait=None)
                settings['remaining_percent'] = remaining
                store.write(db, 'analysis_budget', settings)
            try:
                threading.Thread(target=run_analysis, args=(store, ident, image, model, executable),
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
