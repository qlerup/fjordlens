"""Persistent, shared folder catalogue. Browsing never discovers files on the NAS.

SQLite triggers maintain topology and coalesce cover work in the same transaction
as photo changes, including uploads performed by other processes. Original media
are never opened by this module. The directory discovery worker is separate from
both HTTP requests and the cover worker; an unavailable NAS cannot block browsing.
"""
from contextlib import closing
from datetime import datetime, timezone
import json
import hashlib
import logging
import os
from pathlib import Path
import sqlite3
import threading
import time
from urllib.parse import quote, unquote

log = logging.getLogger(__name__)
_BLOCKED = {'@eadir', '#recycle'}


def normalize(path):
    path = str(path or '').replace('\\', '/').strip('/')
    parts = path.split('/') if path else []
    if any(not p or p.startswith('.') or p.lower() in _BLOCKED or '\x00' in p for p in parts):
        raise ValueError('Invalid folder path')
    if parts and parts[0] in {'originals', 'converted'}:
        raise ValueError('Internal storage path')
    return '/'.join(parts)


def folder_from_rel(rel):
    rel = str(rel or '')
    for prefix in ('uploads/originals/', 'uploads/converted/', 'uploads/'):
        if rel.startswith(prefix):
            return normalize(rel[len(prefix):].rpartition('/')[0])
    return None


def ancestors(path):
    while path:
        yield path
        path = path.rpartition('/')[0]


def ensure_path(conn, path):
    """Register empty folders too. The caller owns the transaction."""
    path = normalize(path)
    for value in reversed(list(ancestors(path))):
        parent, _, name = value.rpartition('/')
        conn.execute('INSERT OR IGNORE INTO folder_index(path,parent,name) VALUES(?,?,?)', (value, parent, name))


def mark_dirty(conn, path):
    conn.executemany('INSERT OR IGNORE INTO folder_index_dirty(path) VALUES(?)', ((p,) for p in ancestors(path)))


def _photo_paths(ref):
    # A recursive SELECT inside INSERT is supported inside SQLite triggers.
    tail = f"CASE WHEN substr({ref}.rel_path,1,18)='uploads/originals/' THEN substr({ref}.rel_path,19) WHEN substr({ref}.rel_path,1,18)='uploads/converted/' THEN substr({ref}.rel_path,19) ELSE substr({ref}.rel_path,9) END"
    return f"""WITH RECURSIVE parts(path,parent,name,rest) AS (
      SELECT '', '', '', {tail} WHERE substr({ref}.rel_path,1,8)='uploads/'
      UNION ALL
      SELECT CASE WHEN path='' THEN substr(rest,1,instr(rest,'/')-1) ELSE path||'/'||substr(rest,1,instr(rest,'/')-1) END,
             path, substr(rest,1,instr(rest,'/')-1), substr(rest,instr(rest,'/')+1)
      FROM parts WHERE instr(rest,'/')>1 AND substr(rest,1,1)<>'.'
        AND lower(substr(rest,1,instr(rest,'/')-1)) NOT IN ('@eadir','#recycle')
        AND NOT (path='' AND substr(rest,1,instr(rest,'/')-1) IN ('originals','converted'))
    ) SELECT path,parent,name FROM parts WHERE path<>''"""


def install(conn):
    """Atomic migration, including upgrades from the short-lived v1 catalogue."""
    conn.execute('SAVEPOINT folder_catalogue_install')
    try:
        _install(conn)
        conn.execute('RELEASE folder_catalogue_install')
    except Exception:
        conn.execute('ROLLBACK TO folder_catalogue_install')
        conn.execute('RELEASE folder_catalogue_install')
        raise


def _install(conn):
    """Idempotent migration; backfill metadata once, never walk the filesystem."""
    legacy = []
    columns = {r[1] for r in conn.execute('PRAGMA table_info(folder_index)')}
    if columns and 'path' not in columns:
        if not {'folder_path', 'parent_path', 'name', 'updated_at'} <= columns:
            raise RuntimeError('Unrecognized folder catalogue schema; original table preserved')
        legacy = [r[0] for r in conn.execute('SELECT folder_path FROM folder_index')]
        conn.execute('ALTER TABLE folder_index RENAME TO folder_index_legacy_v1')
        conn.execute('DROP INDEX IF EXISTS idx_folder_index_parent')
    conn.execute('CREATE TABLE IF NOT EXISTS folder_index(path TEXT PRIMARY KEY, parent TEXT NOT NULL, name TEXT NOT NULL)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_folder_index_parent ON folder_index(parent,name)')
    conn.execute('CREATE TABLE IF NOT EXISTS folder_index_dirty(path TEXT PRIMARY KEY)')
    conn.execute("CREATE TABLE IF NOT EXISTS folder_index_state(id INTEGER PRIMARY KEY CHECK(id=1), version INTEGER NOT NULL DEFAULT 0, revision INTEGER NOT NULL DEFAULT 0, topology INTEGER NOT NULL DEFAULT 0, disk_root TEXT NOT NULL DEFAULT '')")
    conn.execute('INSERT OR IGNORE INTO folder_index_state(id) VALUES(1)')
    for path in legacy:
        try:
            ensure_path(conn, path)
            mark_dirty(conn, normalize(path))
        except ValueError:
            continue
    if columns and 'path' not in columns:
        conn.execute('DROP TABLE folder_index_legacy_v1')
    for table, events in [('folder_index', ('INSERT', 'DELETE')), ('folder_previews', ('INSERT', 'UPDATE', 'DELETE'))]:
        for event in events:
            increment = ', topology=topology+1' if table == 'folder_index' else ''
            conn.execute(f'''CREATE TRIGGER IF NOT EXISTS fi_{table}_{event.lower()} AFTER {event} ON {table}
                BEGIN UPDATE folder_index_state SET revision=revision+1{increment} WHERE id=1; END''')
    for event, refs in [('INSERT', ['NEW']), ('UPDATE OF rel_path,thumb_name', ['OLD', 'NEW']), ('DELETE', ['OLD'])]:
        name = event.split()[0].lower()
        body = ''
        for ref in refs:
            paths = _photo_paths(ref)
            if ref == 'NEW':
                body += f'INSERT INTO folder_index(path,parent,name) SELECT path,parent,name FROM ({paths}) src WHERE NOT EXISTS (SELECT 1 FROM folder_index f WHERE f.path=src.path);\n'
            body += f'INSERT INTO folder_index_dirty(path) SELECT path FROM ({paths}) src WHERE NOT EXISTS (SELECT 1 FROM folder_index_dirty d WHERE d.path=src.path);\n'
        conn.execute(f'CREATE TRIGGER IF NOT EXISTS fi_photos_{name} AFTER {event} ON photos BEGIN {body} END')
    if conn.execute('SELECT version FROM folder_index_state WHERE id=1').fetchone()[0] == 0:
        seen = set()
        for row in conn.execute("SELECT rel_path FROM photos WHERE rel_path >= 'uploads/' AND rel_path < 'uploads0'"):
            try:
                folder = folder_from_rel(row[0])
                if folder and folder not in seen:
                    ensure_path(conn, folder)
                    mark_dirty(conn, folder)
                    seen.add(folder)
            except ValueError:
                continue
        for row in conn.execute('SELECT folder_path FROM folder_owners UNION SELECT folder_path FROM folder_previews'):
            try:
                folder = row[0]
                if folder.startswith('uploads/'):
                    folder = folder[len('uploads/'):]
                ensure_path(conn, folder)
            except ValueError:
                continue
        conn.execute('UPDATE folder_index_state SET version=1 WHERE id=1')


def remove_tree(conn, path):
    path = normalize(path)
    if not path:
        raise ValueError('Cannot delete catalogue root')
    for table, column in [('folder_index', 'path'), ('folder_index_dirty', 'path'), ('folder_previews', 'folder_path')]:
        conn.execute(f'DELETE FROM {table} WHERE {column}=? OR ({column}>=? AND {column}<?)', (path, path+'/', path+'0'))
    mark_dirty(conn, path.rpartition('/')[0])


def rename_tree(conn, old, new):
    old, new = normalize(old), normalize(new)
    if not old or not new or new == old or new.startswith(old+'/'):
        raise ValueError('Invalid folder move')
    rows = conn.execute('SELECT path FROM folder_index WHERE path=? OR (path>=? AND path<?)', (old,old+'/',old+'0')).fetchall()
    ensure_path(conn, new)
    for row in rows:
        ensure_path(conn, new+row[0][len(old):])
    # Existing app moves saved preview selections before calling this function.
    remove_tree(conn, old)
    mark_dirty(conn, new)
    for row in rows:
        mark_dirty(conn, new+row[0][len(old):])


def visibility(conn, uid, prefixes, can_manage=False):
    """Build an exact, segment-aware ACL predicate once per HTTP request."""
    if can_manage:
        visible = lambda path: True
        visible.navigable = visible
        visible.scope = 'all:' + str(uid)
        return visible
    allowed = tuple(prefixes or ())
    owners = dict(conn.execute('SELECT folder_path,user_id FROM folder_owners'))
    def visible(path):
        rel = 'uploads/' + path if path else 'uploads'
        owner = next((owners[p] for p in ancestors(rel) if p in owners), None)
        return (uid > 0 and owner == uid) or any(rel == p or rel.startswith(p+'/') for p in allowed)
    grants = allowed + tuple(path for path, owner in owners.items() if uid > 0 and owner == uid)
    # A grant for A/B also permits navigating through A, but not A's photos,
    # other children or their covers. This preserves the old tree navigation.
    visible.navigable = lambda path: visible(path) or any(p.startswith('uploads/'+path+'/') for p in grants)
    visible.scope = hashlib.sha256(json.dumps([uid, sorted(allowed), sorted(owners.items())], ensure_ascii=False).encode()).hexdigest()[:24]
    return visible


def _thumb_name(url):
    if not isinstance(url, str) or not url.startswith('/api/thumbs/'):
        return None
    name = unquote(url[len('/api/thumbs/'):])
    return name if name and '/' not in name and '\\' not in name and not name.startswith('.') else None


def _saved_urls(raw):
    try:
        value = json.loads(raw or '[]')
        return value[:4] if isinstance(value, list) else []
    except (TypeError, ValueError):
        return []


def list_folders(conn, parent, visible, *, tree=False):
    """Read compact indexed rows and validate only their saved thumbnail refs.

    No cache of permission-filtered responses, no file stat calls, and no
    recomputation on a cache miss. Dirty covers are produced by a worker.
    """
    navigable = getattr(visible, 'navigable', visible)
    if tree:
        return [r[0] for r in conn.execute('SELECT path FROM folder_index ORDER BY path') if navigable(r[0])]
    rows = conn.execute('''SELECT f.path,f.name,p.previews_json FROM folder_index f
        LEFT JOIN folder_previews p ON p.folder_path=f.path WHERE f.parent=? ORDER BY f.name''', (parent,)).fetchall()
    items = [{'path':r[0], 'name':r[1], 'previews':_saved_urls(r[2])} for r in rows if navigable(r[0])]
    # One batched, indexed lookup instead of several DB connections/stat calls
    # per tile. Thumbnail authorization is independent of folder authorization.
    names = list({n for item in items for url in item['previews'] if (n := _thumb_name(url))})
    photos = {}
    for offset in range(0, len(names), 400):
        batch = names[offset:offset+400]
        for name, rel in conn.execute('SELECT thumb_name,rel_path FROM photos WHERE thumb_name IN ('+','.join('?'*len(batch))+')', batch):
            try:
                folder = folder_from_rel(rel)
            except ValueError:
                continue
            if folder is not None and visible(folder):
                photos.setdefault(name, []).append(folder)
    for item in items:
        folder = item['path']
        item['previews'] = [url for url in item['previews'] if any(
            p == folder or p.startswith(folder+'/') for p in photos.get(_thumb_name(url), ()))]
    return items


def refresh_covers(conn, limit=8):
    """Drain coalesced invalidations. All reads/writes share a transaction.

    A concurrent upload either commits before this snapshot or requeues the
    folder afterwards. Deletion cannot be resurrected by a stale cover job.
    """
    done = 0
    for _ in range(limit):
        conn.execute('BEGIN IMMEDIATE')
        try:
            row = conn.execute('SELECT path FROM folder_index_dirty ORDER BY rowid LIMIT 1').fetchone()
            if not row:
                conn.commit()
                break
            path = row[0]
            if conn.execute('SELECT 1 FROM folder_index WHERE path=?', (path,)).fetchone():
                saved = conn.execute('SELECT previews_json FROM folder_previews WHERE folder_path=?', (path,)).fetchone()
                candidates = []
                for prefix in ('uploads/converted/', 'uploads/originals/', 'uploads/'):
                    base = prefix+path
                    candidates.extend(conn.execute('''SELECT rel_path,thumb_name FROM photos
                        WHERE rel_path>=? AND rel_path<? AND coalesce(thumb_name,'')<>''
                        ORDER BY rel_path LIMIT 64''', (base+'/',base+'0')).fetchall())
                candidates = [r for r in candidates if _valid_photo_folder(r[0]) is not None]
                candidates.sort(key=lambda r: _valid_photo_folder(r[0]) != path)
                urls, logical = [], set()
                # Keep explicit/previous selections, even if not in the first 64.
                old = _saved_urls(saved[0]) if saved else []
                for url in old:
                    name = _thumb_name(url)
                    if not name:
                        continue
                    for rel, in conn.execute('SELECT rel_path FROM photos WHERE thumb_name=?', (name,)):
                        folder = _valid_photo_folder(rel)
                        if folder == path or (folder and folder.startswith(path+'/')):
                            if url not in urls:
                                urls.append(url)
                            logical.add(_logical_photo(rel))
                            break
                # A selected 1/2/4-image mosaic stays selected; only fill empty or
                # partially deleted selections, not all previously valid mosaics.
                target = len(old) if old else 4
                for rel, name in candidates:
                    if len(urls) >= target:
                        break
                    key = _logical_photo(rel)
                    url = '/api/thumbs/'+quote(name, safe='')
                    if key not in logical and url not in urls and _thumb_name(url):
                        urls.append(url)
                        logical.add(key)
                if len(urls) == 3:
                    urls = urls[:2]
                payload = json.dumps(urls, ensure_ascii=False)
                if not saved or _saved_urls(saved[0]) != urls:
                    conn.execute('''INSERT INTO folder_previews(folder_path,previews_json,updated_at) VALUES(?,?,?)
                        ON CONFLICT(folder_path) DO UPDATE SET previews_json=excluded.previews_json,updated_at=excluded.updated_at''',
                        (path, payload, datetime.now(timezone.utc).isoformat()))
            conn.execute('DELETE FROM folder_index_dirty WHERE path=?', (path,))
            conn.commit()
            done += 1
        except Exception:
            conn.rollback()
            raise
    return done


def _valid_photo_folder(rel):
    try:
        return folder_from_rel(rel)
    except ValueError:
        return None


def _logical_photo(rel):
    for prefix in ('uploads/converted/', 'uploads/originals/', 'uploads/'):
        if rel.startswith(prefix):
            return rel[len(prefix):].rsplit('.',1)[0].lower()
    return rel


def discover(conn, root):
    """Explicit/background discovery, never invoked by a browse query.

    Additive by design: a disconnected/empty mount must never erase the index.
    Removing externally deleted folders uses the existing explicit delete/sync
    operations; successful app mutations update the catalogue immediately.
    """
    revision = conn.execute('SELECT topology FROM folder_index_state WHERE id=1').fetchone()[0]
    found = set()
    def fail(error):
        raise error
    # Scandir raises on inaccessible/missing roots (os.walk otherwise hides it).
    with os.scandir(root):
        pass
    roots = [(Path(root), True)]
    roots.extend((Path(root)/name, False) for name in ('originals','converted') if (Path(root)/name).is_dir())
    for base, top in roots:
        for current, dirs, _ in os.walk(base, onerror=fail, followlinks=False):
            dirs[:] = [d for d in dirs if not d.startswith('.') and d.lower() not in _BLOCKED
                       and not (top and Path(current)==base and d in {'originals','converted'})
                       and not (Path(current)/d).is_symlink()]
            for name in dirs:
                try:
                    found.add(normalize((Path(current)/name).relative_to(base).as_posix()))
                except ValueError:
                    continue
    conn.execute('BEGIN IMMEDIATE')
    try:
        if conn.execute('SELECT topology FROM folder_index_state WHERE id=1').fetchone()[0] != revision:
            conn.rollback()  # A rename/delete during scanning wins; retry later.
            return False
        for folder in found:
            ensure_path(conn, folder)
        conn.execute('UPDATE folder_index_state SET disk_root=? WHERE id=1', (str(root),))
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        raise


_workers = set()
_worker_lock = threading.Lock()


def start_workers(db_path, upload_root):
    """Called only by production bootstrap. Capture paths, not mutable globals."""
    key = (str(db_path), str(upload_root))
    with _worker_lock:
        if key in _workers:
            return
        _workers.add(key)
    def connect():
        return sqlite3.connect(key[0], timeout=5)
    def covers():
        while True:
            try:
                with closing(connect()) as conn:
                    count = refresh_covers(conn)
                time.sleep(.2 if count else 2)
            except Exception:
                log.exception('Folder cover index update failed; will retry')
                time.sleep(10)
    def directories():
        while True:
            try:
                with closing(connect()) as conn:
                    # Discover additions made outside FjordLens independently of
                    # navigation. Never prune on a missing/offline NAS mount.
                    if discover(conn, key[1]):
                        time.sleep(600)
                        continue
            except OSError:
                log.warning('Folder discovery: upload storage unavailable; preserving index')
            except Exception:
                log.exception('Folder discovery failed; preserving index')
            time.sleep(30)
    for target, name in ((covers,'folder-covers'), (directories,'folder-discovery')):
        threading.Thread(target=target,name=name,daemon=True).start()
