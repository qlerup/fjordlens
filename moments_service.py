"""Persistence and editing for moments; shares the application's auth and DB helpers."""
import json
import threading
import time
import uuid
from contextlib import closing
from datetime import date, datetime
from functools import wraps

from flask import jsonify, request
from flask_login import login_required, current_user

from moments_engine import discover, photo_date, country_for_name
import moment_places
import moment_folders
import moment_titles

_scan_context = threading.local()


def _report_progress(g, progress):
    token = getattr(_scan_context, 'token', None)
    if token:
        with closing(g['get_conn']()) as conn:
            conn.execute('UPDATE moment_scan_state SET result_json=? WHERE id=1 AND token=? AND running=1',
                         (json.dumps(progress), token))
            conn.commit()


def migrate(conn):
    conn.execute('''CREATE TABLE IF NOT EXISTS moment_shares (
        token_hash TEXT PRIMARY KEY, moment_id INTEGER NOT NULL,
        title TEXT NOT NULL, script_json TEXT NOT NULL, created_at TEXT NOT NULL)''')
    share_columns = {r[1] for r in conn.execute('PRAGMA table_info(moment_shares)')}
    for name, definition in (('token_plain', 'TEXT'), ('expires_at', 'TEXT'), ('last_used_at', 'TEXT'), ('revoked', 'INTEGER NOT NULL DEFAULT 0')):
        if name not in share_columns:
            conn.execute(f'ALTER TABLE moment_shares ADD COLUMN {name} {definition}')
    columns = {r[1] for r in conn.execute("PRAGMA table_info(moments)")}
    for name, definition in (("evidence_json", "TEXT NOT NULL DEFAULT '{}'"),
                             ("user_edited", "INTEGER NOT NULL DEFAULT 0"),
                             ("revision", "INTEGER NOT NULL DEFAULT 0")):
        if name not in columns:
            conn.execute(f"ALTER TABLE moments ADD COLUMN {name} {definition}")
    conn.execute("CREATE TABLE IF NOT EXISTS moment_settings (id INTEGER PRIMARY KEY CHECK(id=1), home_json TEXT)")
    conn.execute("CREATE TABLE IF NOT EXISTS moment_place_cache (point TEXT PRIMARY KEY, result_json TEXT NOT NULL, expires REAL NOT NULL)")
    moment_folders.upgrade_suggestions(conn)
    conn.execute("""CREATE TABLE IF NOT EXISTS moment_scan_state
        (id INTEGER PRIMARY KEY CHECK(id=1), token TEXT, started REAL, running INTEGER, result_json TEXT)""")
    # Upgrade automatic suggestions without changing saved or manually edited titles.
    for row in conn.execute("""SELECT id,title,evidence_json,start_date,end_date FROM moments
            WHERE kind='event' AND status='suggested' AND user_edited=0
            AND COALESCE(video_status,'none') NOT IN ('queued','running','rendering')""").fetchall():
        info = json.loads(row['evidence_json'] or '{}')
        attraction = info.get('attraction')
        title = moment_places.attraction_title(attraction, info.get('occasion')) if attraction else None
        if title:
            title = moment_titles.format_title(title, row['start_date'], row['end_date'])
        if title and title != row['title']:
            conn.execute("""UPDATE moments SET title=?,script_json=NULL,subtitle=NULL,
                video_status='none',video_rel_path=NULL,video_error=NULL,revision=revision+1
                WHERE id=?""", (title, row['id']))
    moment_titles.upgrade(conn)


def scan_status(g):
    with closing(g["get_conn"]()) as conn:
        row = conn.execute("SELECT * FROM moment_scan_state WHERE id=1").fetchone()
    if not row:
        return dict(ok=True, running=False, result=None)
    running = bool(row["running"] and time.time() - row["started"] < 3600)
    result = json.loads(row["result_json"]) if row["result_json"] else None
    if row["running"] and not running:
        result = dict(ok=False, error="Søgningen blev afbrudt eller tog for lang tid. Start den igen.")
    return dict(ok=True, running=running, elapsed_seconds=max(0, int(time.time() - row["started"])),
                progress=(result or dict(phase='grouping')) if running else None,
                result=None if running else result)


def start_scan(g):
    token = uuid.uuid4().hex
    with closing(g["get_conn"]()) as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT * FROM moment_scan_state WHERE id=1").fetchone()
        if row and row["running"] and time.time()-row["started"] < 3600:
            return dict(ok=False, error="Momentsøgning kører allerede"), 409
        conn.execute("""INSERT INTO moment_scan_state(id,token,started,running,result_json) VALUES(1,?,?,1,NULL)
            ON CONFLICT(id) DO UPDATE SET token=excluded.token,started=excluded.started,running=1,result_json=NULL""", (token, time.time()))
        conn.commit()

    def run():
        _scan_context.token = token
        try:
            result = complete_detection(g)
        except Exception as error:
            result = dict(ok=False, error=str(error))
        finally:
            del _scan_context.token
        with closing(g["get_conn"]()) as conn:
            conn.execute("UPDATE moment_scan_state SET running=0,result_json=? WHERE id=1 AND token=?", (json.dumps(result), token))
            conn.commit()
    try:
        threading.Thread(target=run, daemon=True).start()
    except Exception:
        with closing(g["get_conn"]()) as conn:
            conn.execute("UPDATE moment_scan_state SET running=0 WHERE token=?", (token,))
            conn.commit()
        raise
    return dict(ok=True, started=True), 200


def complete_detection(g):
    """Continue bounded lookup batches automatically while they make progress."""
    with closing(g['get_conn']()) as conn:
        before = {row['id']: row['revision'] for row in conn.execute('SELECT id,revision FROM moments')}
    deadline = time.monotonic() + 300
    while True:
        result = g['_run_moment_detection']()
        debug = result.get('debug', {})
        if (not result.get('ok') or not debug.get('poi_pending') or not debug.get('poi_lookups')
                or time.monotonic() >= deadline):
            break
    if result.get('ok'):
        with closing(g['get_conn']()) as conn:
            after = {row['id']: row['revision'] for row in conn.execute('SELECT id,revision FROM moments')}
        result['created'] = len(after.keys() - before.keys())
        result['updated'] = sum(after[mid] != revision for mid, revision in before.items() if mid in after)
        result['retired'] = len(before.keys() - after.keys())
    return result


def detect_years(g):
    stats = dict(created=0, updated=0)
    with closing(g["get_conn"]()) as conn:
        rows = conn.execute("SELECT id,rel_path,captured_at,modified_fs,created_fs,favorite FROM photos").fetchall()
    by_year = {}
    for row in g["_dedupe_upload_storage_rows"](rows):
        dt = photo_date(dict(row))
        if dt and dt.year < datetime.now().year:
            by_year.setdefault(dt.year, []).append(row)
    with closing(g["get_conn"]()) as conn:
        conn.execute("BEGIN IMMEDIATE")
        for year, photos in by_year.items():
            if len(photos) < g["MOMENT_YEAR_REVIEW_MIN_PHOTOS"]:
                continue
            existing = conn.execute("SELECT * FROM moments WHERE kind='year_review' AND substr(start_date,1,4)=?", (str(year),)).fetchall()
            ids = sorted(r["id"] for r in photos)
            info = dict(version=2, reasons=[f"Højdepunkter fra {year}. Alle {len(ids)} billeder bevares; diasshowet viser et udvalg."],
                        date_basis="Kalenderåret", confidence="high")
            now = g["now_iso"]()
            if existing:
                row = existing[0]
                if len(existing) != 1 or row["status"] != "suggested" or row["user_edited"] or row["video_status"] in ("queued", "running", "rendering"):
                    continue
                if members(row) == set(ids):
                    continue
                conn.execute("""UPDATE moments SET photo_ids_json=?,evidence_json=?,script_json=NULL,
                    subtitle=NULL,video_status='none',video_rel_path=NULL,video_error=NULL,revision=revision+1,updated_at=? WHERE id=?""",
                    (json.dumps(ids), json.dumps(info, ensure_ascii=False), now, row["id"]))
                stats["updated"] += 1
            else:
                insert(conn, dict(kind="year_review", title=f"Året der gik {year}", start_date=f"{year}-01-01",
                    end_date=f"{year}-12-31", photo_ids=ids, cover_photo_id=ids[len(ids)//2], evidence=info), now)
                stats["created"] += 1
        conn.commit()
    return stats


def settings(conn):
    row = conn.execute("SELECT home_json FROM moment_settings WHERE id=1").fetchone()
    return json.loads(row[0]) if row and row[0] else None


def evidence(row):
    return json.loads(row["evidence_json"] or "{}")


def members(row):
    return set(json.loads(row["photo_ids_json"] or "[]"))


def can_view(g, row):
    if not row or row["status"] == "dismissed":
        return False
    if getattr(current_user, "can_manage_media", False):
        return True
    ids = sorted(members(row))
    with closing(g["get_conn"]()) as conn:
        for offset in range(0, len(ids), 500):
            batch = ids[offset:offset+500]
            photos = conn.execute(f"SELECT rel_path FROM photos WHERE id IN ({','.join('?' for _ in batch)})", batch).fetchall()
            if len(photos) != len(batch) or any(not g["_is_rel_visible_for_current_user"](p["rel_path"], conn) for p in photos):
                return False
    return bool(ids)


def insert(conn, candidate, now, *, edited=False, status="suggested"):
    if not edited:
        moment_titles.apply(candidate)
    cur = conn.execute("""INSERT INTO moments
        (kind,status,title,start_date,end_date,primary_place,cover_photo_id,photo_ids_json,
         evidence_json,user_edited,created_at,updated_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        (candidate["kind"], status, candidate["title"], candidate["start_date"], candidate["end_date"],
         candidate.get("primary_place"), candidate["cover_photo_id"], json.dumps(candidate["photo_ids"]),
         json.dumps(candidate["evidence"], ensure_ascii=False), int(edited), now, now))
    return cur.lastrowid


def detect(g):
    with closing(g["get_conn"]()) as conn:
        # Narrow columns keep the scan independent of large embeddings/EXIF blobs.
        rows = conn.execute("""SELECT id,rel_path,captured_at,modified_fs,created_fs,gps_name,gps_lat,gps_lon,
            favorite,uploaded_by,camera_make,camera_model,ai_desc_caption,ai_desc_tags FROM photos""").fetchall()
        home = settings(conn)
    rows = g["_dedupe_upload_storage_rows"](rows)
    candidates, stats, _ = discover(rows, min_photos=g["MOMENT_MIN_PHOTOS"],
                                    min_hours=g["MOMENT_MIN_SPAN_HOURS"], gap_hours=g["MOMENT_GAP_HOURS"], manual_home=home)
    place_stats = moment_places.enrich(candidates, rows, g['get_conn'],
                                       progress=lambda progress: _report_progress(g, progress))
    moment_folders.apply(candidates, rows)
    for candidate in candidates:
        moment_titles.apply(candidate)
    stats.update({f'poi_{key}': value for key, value in place_stats.items()})
    _report_progress(g, dict(phase='saving'))
    with closing(g["get_conn"]()) as conn:
        conn.execute("BEGIN IMMEDIATE")
        if settings(conn) != home:
            raise ValueError("Hjemsted blev ændret under scanningen. Start søgningen igen.")
        existing = list(conn.execute("SELECT * FROM moments WHERE kind != 'year_review'"))
        protected = [r for r in existing if r["status"] != "suggested" or r["user_edited"]]
        available = [r for r in existing if r["status"] == "suggested" and not r["user_edited"]]
        retained = set()
        for candidate in candidates:
            ids = set(candidate["photo_ids"])
            # Removed photos remain in the origin set so they cannot reappear as leftovers.
            blocked = any(ids & (members(r) | set(evidence(r).get("source_photo_ids", []))) for r in protected)
            if blocked:
                stats["rejected_already_covered"] += 1
                continue
            matches = [r for r in available if ids & members(r)]
            now = g["now_iso"]()
            if matches:
                target = max(matches, key=lambda r: len(ids & members(r)))
                retained.add(target["id"])
                previous = evidence(target)
                if (members(target) == ids and candidate['evidence'].get('attraction_lookup_pending')
                        and not candidate['evidence'].get('attraction') and previous.get('attraction')):
                    # An unavailable map service must not erase an already discovered visit.
                    candidate['evidence']['attraction'] = previous['attraction']
                    candidate['evidence']['title_source'] = 'attraction'
                    candidate['evidence'].pop('folder_title', None)
                    candidate['evidence']['reasons'] = [r for r in candidate['evidence']['reasons'] if not r.startswith('Titlen kommer fra mappen')]
                    candidate['title'] = target['title']
                    candidate['primary_place'] = target['primary_place']
                    candidate['evidence']['reasons'].extend(r for r in previous.get('reasons', []) if 'OpenStreetMap' in r)
                if members(target) == ids and evidence(target) == candidate["evidence"] and target["kind"] == candidate["kind"] and target['title'] == candidate['title']:
                    stats["rejected_already_covered"] += 1
                    continue
                if any(r["video_status"] in ("queued", "running", "rendering") for r in matches):
                    retained.update(r["id"] for r in matches)
                    stats["rejected_already_covered"] += 1
                    continue
                conn.execute("""UPDATE moments SET kind=?,title=?,start_date=?,end_date=?,primary_place=?,
                    cover_photo_id=?,photo_ids_json=?,evidence_json=?,script_json=NULL,subtitle=NULL,
                    video_status='none',video_rel_path=NULL,video_error=NULL,revision=revision+1,updated_at=? WHERE id=?""",
                    (candidate["kind"], candidate["title"], candidate["start_date"], candidate["end_date"], candidate["primary_place"],
                     candidate["cover_photo_id"], json.dumps(candidate["photo_ids"]), json.dumps(candidate["evidence"], ensure_ascii=False), now, target["id"]))
                for other in matches:
                    if other["id"] != target["id"]:
                        # Internal supersession is not a user rejection and must not block future scans.
                        conn.execute("DELETE FROM moments WHERE id=?", (other["id"],))
                stats["updated"] += 1
                available = [r for r in available if r not in matches]
                available.append(conn.execute("SELECT * FROM moments WHERE id=?", (target["id"],)).fetchone())
            else:
                new_id = insert(conn, candidate, now)
                stats["created"] += 1
                available.append(conn.execute("SELECT * FROM moments WHERE id=?", (new_id,)).fetchone())
                retained.add(new_id)
        # A corrected home setting or newly learned routine can invalidate an old
        # automatic suggestion. Only unedited suggestions may be retired here.
        for row in available:
            if row["id"] not in retained and row["video_status"] not in ("queued", "running", "rendering"):
                conn.execute("DELETE FROM moments WHERE id=?", (row["id"],))
                stats["retired"] += 1
        conn.commit()
    return stats


class EditError(ValueError):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


_MISSING = object()


def _get(conn, moment_id, revision=_MISSING):
    row = conn.execute("SELECT * FROM moments WHERE id=? AND status != 'dismissed'", (moment_id,)).fetchone()
    if not row:
        raise EditError("Momentet findes ikke længere.", 404)
    if revision is not _MISSING and (type(revision) is not int or revision != row["revision"]):
        raise EditError("Momentet er ændret. Luk og åbn redigeringen igen.", 409)
    if row["video_status"] in ("queued", "running", "rendering"):
        raise EditError("Vent til momentets video er færdig, før du redigerer.", 409)
    return row


def _ids(value):
    if not isinstance(value, list) or not value or any(type(i) is not int or i <= 0 for i in value):
        raise EditError("Vælg mindst ét billede.")
    return sorted(set(value))


def _dates(data):
    try:
        start, end = date.fromisoformat(data["start_date"]), date.fromisoformat(data["end_date"])
    except (KeyError, ValueError, TypeError):
        raise EditError("Angiv gyldige fra- og til-datoer.")
    if start > end:
        raise EditError("Fra-dato skal ligge før til-dato.")
    return start.isoformat(), end.isoformat()


def _photos(conn, ids, *, strict=True):
    result = []
    for offset in range(0, len(ids), 500):
        batch = ids[offset:offset+500]
        result.extend(dict(r) for r in conn.execute(f"SELECT * FROM photos WHERE id IN ({','.join('?' for _ in batch)})", batch))
    if strict and len(result) != len(ids):
        raise EditError("Et eller flere billeder findes ikke længere. Åbn momentet igen.", 409)
    return sorted(result, key=lambda r: (photo_date(r) or datetime.min, r["id"]))


def _manual_evidence(row, ids, reason):
    old = evidence(row)
    return {"version": 2, "reasons": [reason], "confidence": "manual",
            "source_photo_ids": sorted(members(row) | set(ids) | set(old.get("source_photo_ids", []))),
            "date_basis": "Datoer og billeder er valgt manuelt."}


def _update(conn, row, *, title, start, end, ids, now, info):
    from moment_slideshow import retain_edited_script
    conn.execute("""UPDATE moments SET title=?,start_date=?,end_date=?,photo_ids_json=?,
        cover_photo_id=?,evidence_json=?,user_edited=1,revision=revision+1,updated_at=?,script_json=?,
        subtitle=NULL,video_status='none',video_rel_path=NULL,video_error=NULL,
        kind=CASE WHEN kind='year_review' THEN kind ELSE ? END WHERE id=?""",
        (title, start, end, json.dumps(ids), row["cover_photo_id"] if row["cover_photo_id"] in ids else ids[0],
         json.dumps(info, ensure_ascii=False), now, retain_edited_script(row['script_json'], ids), "event" if start == end else "trip", row["id"]))


def register_routes(app, g):
    def managed(fn):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            forbidden = g["_forbid_media_management"]()
            if forbidden:
                return jsonify(forbidden[0]), forbidden[1]
            try:
                return fn(*args, **kwargs)
            except EditError as exc:
                return jsonify(ok=False, error=str(exc)), exc.status
        return login_required(wrapped)

    from moment_sharing import register as register_sharing
    register_sharing(app, g, managed)
    from moment_slideshow import register as register_slideshow
    register_slideshow(app, g, managed)

    @app.route("/api/moments/settings", methods=["GET", "PUT"])
    @managed
    def moment_settings():
        with closing(g["get_conn"]()) as conn:
            if request.method == "PUT":
                forbidden = g["_forbid_user_role_for_maintenance"]()
                if forbidden:
                    return jsonify(forbidden[0]), forbidden[1]
                data = request.get_json(silent=True)
                if not isinstance(data, dict) or "home" not in data:
                    raise EditError("Angiv et hjemsted eller vælg automatisk.")
                home = data["home"]
                if home is not None:
                    if not isinstance(home, dict) or not str(home.get("name") or "").strip():
                        raise EditError("Angiv navnet på dit hjemområde.")
                    home = {"name": str(home["name"]).strip()[:200], "lat": home.get("lat"), "lon": home.get("lon")}
                    if home["lat"] is not None or home["lon"] is not None:
                        try:
                            home["lat"], home["lon"] = float(home["lat"]), float(home["lon"])
                            if not (-90 <= home["lat"] <= 90 and -180 <= home["lon"] <= 180):
                                raise ValueError()
                        except (TypeError, ValueError):
                            raise EditError("Koordinaterne er ugyldige.")
                conn.execute("INSERT INTO moment_settings(id,home_json) VALUES(1,?) ON CONFLICT(id) DO UPDATE SET home_json=excluded.home_json", (json.dumps(home),))
                conn.commit()
            places = [dict(r) for r in conn.execute("""SELECT gps_name AS name, AVG(gps_lat) AS lat,
                AVG(gps_lon) AS lon FROM photos WHERE gps_name IS NOT NULL AND gps_name != ''
                GROUP BY gps_name ORDER BY COUNT(*) DESC LIMIT 1000""")]
            return jsonify(ok=True, home=settings(conn), places=places)

    @app.get("/api/moments/<int:moment_id>/edit-data")
    @managed
    def moment_edit_data(moment_id):
        with closing(g["get_conn"]()) as conn:
            row = _get(conn, moment_id)
            photos = _photos(conn, sorted(members(row)), strict=False)
        item = g["_moment_row_to_public"](row)
        item["photo_ids"] = [p["id"] for p in photos]
        item["photos"] = [_photo_public(p) for p in photos]
        return jsonify(ok=True, item=item)

    def _photo_public(p):
        pub = g["row_to_public"](p)
        dt = photo_date(p)
        return {"id": p["id"], "thumb_url": pub.get("thumb_url"), "date": dt.isoformat() if dt else None,
                "place": p.get("gps_name"), "filename": p.get("filename"),
                "original_url": pub.get("original_url"), "is_video": pub.get("is_video"),
                "width": p.get("width"), "height": p.get("height"),
                "weather": __import__('moment_cinema').weather_label(p)}

    @app.get("/api/moments/photo-search")
    @managed
    def moment_photo_search():
        start, end = _dates(request.args)
        try:
            offset = max(0, int(request.args.get("offset", 0)))
        except ValueError:
            raise EditError("Ugyldig side.")
        place = str(request.args.get("place") or "").strip().casefold()
        with closing(g["get_conn"]()) as conn:
            rows = conn.execute("""SELECT * FROM photos WHERE substr(COALESCE(NULLIF(captured_at,''),
                NULLIF(modified_fs,''),created_fs),1,10) BETWEEN ? AND ?
                ORDER BY COALESCE(NULLIF(captured_at,''),NULLIF(modified_fs,''),created_fs),id""", (start, end)).fetchall()
        rows = g["_dedupe_upload_storage_rows"](rows)
        if place:
            country = country_for_name(place)
            rows = [r for r in rows if place in str(r["gps_name"] or "").casefold()
                    or (country and country_for_name(str(r["gps_name"] or "")) == country)]
        return jsonify(ok=True, photos=[_photo_public(dict(r)) for r in rows[offset:offset+200]], has_more=len(rows)>offset+200)

    @app.patch("/api/moments/<int:moment_id>")
    @managed
    def moment_edit(moment_id):
        data = request.get_json(silent=True)
        if not isinstance(data, dict) or "revision" not in data:
            raise EditError("Åbn momentet igen før redigering.")
        title = str(data.get("title") or "").strip()
        if not title or len(title) > 240:
            raise EditError("Titlen skal være mellem 1 og 240 tegn.")
        start, end = _dates(data)
        ids = _ids(data.get("photo_ids"))
        with closing(g["get_conn"]()) as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = _get(conn, moment_id, data["revision"])
            photos = _photos(conn, ids)
            ids = [p['id'] for p in photos if photo_date(p) and start <= photo_date(p).date().isoformat() <= end]
            if not ids:
                raise EditError('Ingen af de valgte billeder ligger inden for datoerne.')
            _update(conn, row, title=title, start=start, end=end, ids=ids, now=g["now_iso"](),
                    info=_manual_evidence(row, ids, "Du har rettet dette moment. Nye scanninger bevarer dine valg."))
            conn.commit()
        return jsonify(ok=True)

    @app.post("/api/moments/<int:moment_id>/split")
    @managed
    def moment_split(moment_id):
        data = request.get_json(silent=True)
        if not isinstance(data, dict) or "revision" not in data:
            raise EditError("Åbn momentet igen før opdeling.")
        ids = set(_ids(data.get("photo_ids")))
        with closing(g["get_conn"]()) as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = _get(conn, moment_id, data["revision"])
            original = members(row)
            if not ids < original:
                raise EditError("Vælg nogle af billederne til det nye moment; resten bliver i det oprindelige.")
            now = g["now_iso"]()
            new_id = None
            for index, group in enumerate((sorted(original-ids), sorted(ids))):
                photos = _photos(conn, group)
                dates = [photo_date(p).date().isoformat() for p in photos if photo_date(p)]
                start, end = (min(dates), max(dates)) if dates else (row["start_date"], row["end_date"])
                title = f"{row['title']} · del {index+1}"
                info = _manual_evidence(row, group, "Du har opdelt dette moment. Nye scanninger bevarer opdelingen.")
                if index == 0:
                    _update(conn, row, title=title, start=start, end=end, ids=group, now=now, info=info)
                else:
                    new_id = insert(conn, dict(kind="event" if start == end else "trip", title=title, start_date=start,
                        end_date=end, primary_place=row["primary_place"], photo_ids=group, cover_photo_id=group[0], evidence=info),
                        now, edited=True, status=row["status"])
            conn.commit()
        return jsonify(ok=True, id=new_id)

    @app.post("/api/moments/<int:moment_id>/merge")
    @managed
    def moment_merge(moment_id):
        data = request.get_json(silent=True)
        if not isinstance(data, dict) or type(data.get("other_id")) is not int or "revision" not in data or "other_revision" not in data:
            raise EditError("Vælg et andet moment.")
        if data["other_id"] == moment_id:
            raise EditError("Vælg to forskellige momenter.")
        with closing(g["get_conn"]()) as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = _get(conn, moment_id, data["revision"])
            other = _get(conn, data["other_id"], data["other_revision"])
            if "year_review" in (row["kind"], other["kind"]):
                raise EditError("Årsoversigter kan ikke samles med andre momenter.")
            ids = sorted(members(row) | members(other))
            _photos(conn, ids)
            info = _manual_evidence(row, ids, "Du har samlet disse momenter. Nye scanninger bevarer dine valg.")
            info["source_photo_ids"] = sorted(set(info["source_photo_ids"]) | set(evidence(other).get("source_photo_ids", [])))
            now = g["now_iso"]()
            _update(conn, row, title=row["title"], start=min(row["start_date"], other["start_date"]),
                    end=max(row["end_date"], other["end_date"]), ids=ids, now=now, info=info)
            conn.execute("UPDATE moments SET status='dismissed',user_edited=1,revision=revision+1,updated_at=? WHERE id=?", (now, other["id"]))
            if other["status"] == "saved":
                conn.execute("UPDATE moments SET status='saved' WHERE id=?", (moment_id,))
            conn.commit()
        return jsonify(ok=True)
