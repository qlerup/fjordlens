"""Materialized People list statistics for fast /api/people responses."""
from __future__ import annotations

import re
import threading
import time
from typing import Any

from flask import jsonify, request

_STATS_WORKER_LOCK = threading.Lock()
_STATS_WORKER_STARTED = False


_STILL_SQL = "f.frame_sec IS NULL AND " + " AND ".join(
    f"LOWER(COALESCE(ph.ext,'')) != '{ext}' AND LOWER(ph.rel_path) NOT LIKE '%{ext}'"
    for ext in ('.mp4', '.m4v', '.mov', '.avi', '.mkv', '.webm', '.3gp'))

_COVER_ORDER_SQL = """
    CASE WHEN COALESCE(f.confidence, 0) >= 0.70 THEN 1 ELSE 0 END DESC,
    CASE
      WHEN COALESCE(ph.width,0) > 0 AND COALESCE(ph.height,0) > 0
           AND (1.0 * COALESCE(f.bbox_w,0) * COALESCE(f.bbox_h,0))
               / (1.0 * ph.width * ph.height) BETWEEN 0.02 AND 0.45
      THEN 1 ELSE 0
    END DESC,
    CASE WHEN COALESCE(f.bbox_w,0) >= 72 AND COALESCE(f.bbox_h,0) >= 72 THEN 1 ELSE 0 END DESC,
    CASE
      WHEN COALESCE(f.bbox_h,0) > 0
           AND (1.0 * COALESCE(f.bbox_w,0) / COALESCE(f.bbox_h,1)) BETWEEN 0.55 AND 1.90
      THEN 1 ELSE 0
    END DESC,
    COALESCE(f.confidence, 0) DESC,
    (COALESCE(f.bbox_w, 0) * COALESCE(f.bbox_h, 0)) DESC,
    f.id DESC
"""


def _ensure_people_stats_columns(conn) -> bool:
    """Add materialized People-list columns. Return True when a full backfill is needed."""
    cols = {str(row[1]) for row in conn.execute("PRAGMA table_info(people)").fetchall()}
    changed = False

    for name, ddl in (
        ("cover_policy_version", "ALTER TABLE people ADD COLUMN cover_policy_version INTEGER NOT NULL DEFAULT 0"),
        ("face_count", "ALTER TABLE people ADD COLUMN face_count INTEGER NOT NULL DEFAULT 0"),
        ("cover_face_id", "ALTER TABLE people ADD COLUMN cover_face_id INTEGER"),
        ("cover_dirty", "ALTER TABLE people ADD COLUMN cover_dirty INTEGER NOT NULL DEFAULT 1"),
    ):
        if name in cols:
            continue
        try:
            conn.execute(ddl)
            changed = True
        except Exception:
            # Another gunicorn worker may have performed the same migration.
            pass

    conn.commit()

    cols = {str(row[1]) for row in conn.execute("PRAGMA table_info(people)").fetchall()}
    required = {"face_count", "cover_face_id", "cover_dirty"}
    if not required.issubset(cols):
        raise RuntimeError("People statistics columns could not be created")

    if changed:
        return True

    # Detect an old/stale deployment cheaply. Triggers keep these values correct
    # after this feature is installed, so a full check is only needed at startup.
    assigned = conn.execute(
        "SELECT COUNT(*) AS c FROM faces WHERE person_id IS NOT NULL"
    ).fetchone()
    stored = conn.execute(
        "SELECT COALESCE(SUM(face_count),0) AS c FROM people"
    ).fetchone()
    assigned_count = int(assigned["c"] or 0) if assigned else 0
    stored_count = int(stored["c"] or 0) if stored else 0
    if assigned_count != stored_count:
        return True

    missing_cover = conn.execute(
        """
        SELECT 1
        FROM people
        WHERE COALESCE(cover_policy_version,0) != 2
        LIMIT 1
        """
    ).fetchone()
    return bool(missing_cover)


def _install_people_stats_triggers(conn) -> None:
    """Keep counts cheap and mark only affected cover photos for recomputation."""
    conn.executescript(
        """
        CREATE TRIGGER IF NOT EXISTS fjordlens_people_stats_face_insert
        AFTER INSERT ON faces
        WHEN NEW.person_id IS NOT NULL
        BEGIN
          UPDATE people
          SET face_count = COALESCE(face_count,0) + 1,
              cover_dirty = 1
          WHERE id = NEW.person_id;
        END;

        CREATE TRIGGER IF NOT EXISTS fjordlens_people_stats_face_delete
        AFTER DELETE ON faces
        WHEN OLD.person_id IS NOT NULL
        BEGIN
          UPDATE people
          SET face_count = CASE
                WHEN COALESCE(face_count,0) > 0 THEN face_count - 1
                ELSE 0
              END,
              cover_face_id = CASE
                WHEN cover_face_id = OLD.id THEN NULL
                ELSE cover_face_id
              END,
              cover_dirty = 1
          WHERE id = OLD.person_id;
        END;

        CREATE TRIGGER IF NOT EXISTS fjordlens_people_stats_face_person_change
        AFTER UPDATE OF person_id ON faces
        WHEN OLD.person_id IS NOT NEW.person_id
        BEGIN
          UPDATE people
          SET face_count = CASE
                WHEN COALESCE(face_count,0) > 0 THEN face_count - 1
                ELSE 0
              END,
              cover_face_id = CASE
                WHEN cover_face_id = OLD.id THEN NULL
                ELSE cover_face_id
              END,
              cover_dirty = 1
          WHERE id = OLD.person_id;

          UPDATE people
          SET face_count = COALESCE(face_count,0) + 1,
              cover_dirty = 1
          WHERE id = NEW.person_id;
        END;

        CREATE TRIGGER IF NOT EXISTS fjordlens_people_stats_face_rank_change
        AFTER UPDATE OF confidence, bbox_x, bbox_y, bbox_w, bbox_h, frame_sec, photo_id ON faces
        WHEN NEW.person_id IS NOT NULL AND OLD.person_id IS NEW.person_id
        BEGIN
          UPDATE people SET cover_dirty = 1 WHERE id = NEW.person_id;
        END;

        CREATE TRIGGER IF NOT EXISTS fjordlens_people_stats_photo_type_change
        AFTER UPDATE OF ext, rel_path ON photos
        BEGIN
          UPDATE people SET cover_dirty=1 WHERE id IN (
            SELECT person_id FROM faces WHERE photo_id=NEW.id AND person_id IS NOT NULL
          );
        END;

        CREATE TRIGGER IF NOT EXISTS fjordlens_people_stats_photo_dims_change
        AFTER UPDATE OF width, height ON photos
        BEGIN
          UPDATE people
          SET cover_dirty = 1
          WHERE id IN (
            SELECT DISTINCT person_id
            FROM faces
            WHERE photo_id = NEW.id AND person_id IS NOT NULL
          );
        END;
        """
    )
    conn.commit()


def _backfill_people_stats(conn) -> None:
    """One-time migration: compute all counts and best cover faces in batch."""
    conn.execute(
        "UPDATE people SET face_count=0, cover_face_id=NULL, cover_dirty=0, cover_policy_version=2"
    )

    count_rows = conn.execute(
        """
        SELECT person_id, COUNT(*) AS c
        FROM faces
        WHERE person_id IS NOT NULL
        GROUP BY person_id
        """
    ).fetchall()
    if count_rows:
        conn.executemany(
            "UPDATE people SET face_count=? WHERE id=?",
            [(int(row["c"] or 0), int(row["person_id"])) for row in count_rows],
        )

    # This heavier ranking runs only for migration/backfill, never on each People request.
    cover_rows = conn.execute(
        f"""
        WITH ranked AS (
          SELECT
            f.person_id,
            f.id AS face_id,
            ROW_NUMBER() OVER (
              PARTITION BY f.person_id
              ORDER BY {_COVER_ORDER_SQL}
            ) AS rn
          FROM faces f
          LEFT JOIN photos ph ON ph.id = f.photo_id
          WHERE f.person_id IS NOT NULL AND ({_STILL_SQL})
        )
        SELECT person_id, face_id
        FROM ranked
        WHERE rn=1
        """
    ).fetchall()
    if cover_rows:
        conn.executemany(
            "UPDATE people SET cover_face_id=?, cover_dirty=0 WHERE id=?",
            [(int(row["face_id"]), int(row["person_id"])) for row in cover_rows],
        )

    conn.execute(
        "UPDATE people SET cover_dirty=0 WHERE COALESCE(face_count,0)=0"
    )
    conn.commit()


def _refresh_dirty_covers(fjordlens, limit: int = 96) -> int:
    """Refresh only changed covers, ranking a whole batch in one SQL query."""
    with fjordlens.closing(fjordlens.get_conn()) as conn:
        rows = conn.execute(
            """
            SELECT id
            FROM people
            WHERE COALESCE(cover_dirty,0)=1
            ORDER BY id
            LIMIT ?
            """,
            (max(1, int(limit)),),
        ).fetchall()
        if not rows:
            return 0

        person_ids = [int(row["id"]) for row in rows]
        placeholders = ",".join("?" for _ in person_ids)
        cover_rows = conn.execute(
            f"""
            WITH ranked AS (
              SELECT
                f.person_id,
                f.id AS face_id,
                ROW_NUMBER() OVER (
                  PARTITION BY f.person_id
                  ORDER BY {_COVER_ORDER_SQL}
                ) AS rn
              FROM faces f
              LEFT JOIN photos ph ON ph.id=f.photo_id
              WHERE f.person_id IN ({placeholders}) AND ({_STILL_SQL})
            )
            SELECT person_id, face_id
            FROM ranked
            WHERE rn=1
            """,
            person_ids,
        ).fetchall()
        cover_by_person = {
            int(row["person_id"]): int(row["face_id"])
            for row in cover_rows
            if row["person_id"] is not None and row["face_id"] is not None
        }

        conn.executemany(
            "UPDATE people SET cover_face_id=?, cover_dirty=0 WHERE id=?",
            [(cover_by_person.get(pid), pid) for pid in person_ids],
        )
        conn.commit()
        return len(person_ids)


def _cover_worker_loop(fjordlens) -> None:
    while True:
        try:
            processed = _refresh_dirty_covers(fjordlens)
        except Exception:
            processed = 0
        time.sleep(0.08 if processed else 0.8)


def _start_cover_worker(fjordlens) -> None:
    global _STATS_WORKER_STARTED
    with _STATS_WORKER_LOCK:
        if _STATS_WORKER_STARTED:
            return
        _STATS_WORKER_STARTED = True
        thread = threading.Thread(
            target=_cover_worker_loop,
            args=(fjordlens,),
            name="fjordlens-people-cover-stats",
            daemon=True,
        )
        thread.start()


def _unknown_bucket(conn) -> dict[str, Any] | None:
    count_row = conn.execute(
        "SELECT COUNT(DISTINCT photo_id) AS c FROM faces WHERE person_id IS NULL"
    ).fetchone()
    count = int(count_row["c"] or 0) if count_row else 0
    if count <= 0:
        return None

    face_row = conn.execute(
        f"""
        SELECT f.id
        FROM faces f
        LEFT JOIN photos ph ON ph.id=f.photo_id
        WHERE f.person_id IS NULL AND ({_STILL_SQL})
        ORDER BY {_COVER_ORDER_SQL}
        LIMIT 1
        """
    ).fetchone()
    cover_id = int(face_row["id"]) if face_row and face_row["id"] is not None else None
    return {
        "id": "unknown",
        "name": "Ukendte",
        "count": count,
        "thumb_url": f"/api/face-thumb/{cover_id}" if cover_id else None,
    }


def _make_fast_people_view(app, fjordlens, original):
    def api_people_list_fast():
        include_hidden = request.args.get("include_hidden") in {"1", "true", "True"}

        with fjordlens.closing(fjordlens.get_conn()) as conn:
            # Restricted users need per-folder ACL counts. Keep the original exact
            # behavior for them; admins/managers use the materialized global stats.
            acl_prefixes = fjordlens._current_user_acl_prefixes(conn)
            if acl_prefixes is not None:
                return None

            where = "" if include_hidden else "AND COALESCE(hidden,0)=0"
            rows = conn.execute(
                f"""
                SELECT id, name, COALESCE(hidden,0) AS hidden,
                       COALESCE(face_count,0) AS face_count,
                       cover_face_id
                FROM people
                WHERE COALESCE(face_count,0) > 0
                  {where}
                ORDER BY
                  CASE
                    WHEN LOWER(name) LIKE 'ukendt%' OR LOWER(name) LIKE 'unknown%'
                    THEN 1 ELSE 0
                  END,
                  COALESCE(face_count,0) DESC,
                  name COLLATE NOCASE ASC
                """
            ).fetchall()

            # One grouped query counts distinct source images, not detections or frames.
            counts = {int(r['person_id']): r for r in conn.execute(f"""
                SELECT f.person_id, COUNT(DISTINCT f.photo_id) AS media_count,
                       COUNT(DISTINCT CASE WHEN {_STILL_SQL} THEN f.photo_id END) AS image_count
                FROM faces f JOIN photos ph ON ph.id=f.photo_id
                WHERE f.person_id IS NOT NULL GROUP BY f.person_id
            """).fetchall()}
            people = []
            for row in rows:
                cover_id = int(row["cover_face_id"]) if row["cover_face_id"] is not None else None
                count = counts.get(int(row['id']))
                image_count = int(count['image_count']) if count else 0
                name = str(row['name'] or '').strip()
                unnamed = not name or bool(re.fullmatch(r'(?:Ukendt|Unknown)(?:-\d+)?', name, re.I))
                people.append(
                    {
                        "id": int(row["id"]),
                        "name": row["name"],
                        "count": int(count["media_count"]) if count else 0,
                        "image_count": image_count,
                        "single_find": unnamed and image_count <= 1,
                        "thumb_url": f"/api/face-thumb/{cover_id}" if cover_id else None,
                        "hidden": bool(int(row["hidden"] or 0)),
                    }
                )

            unknown = _unknown_bucket(conn)
            if unknown is not None:
                people.append(unknown)

        return jsonify({"ok": True, "items": people})

    def dispatch():
        fast = api_people_list_fast()
        if fast is not None:
            return fast
        return original()

    dispatch.__name__ = getattr(original, "__name__", "api_people_list")
    dispatch.__doc__ = getattr(original, "__doc__", None)
    return dispatch


def init_people_stats(app, fjordlens) -> None:
    """Install materialized stats and fast-path the People list for unrestricted users."""
    if app.extensions.get("fjordlens_people_stats_v1"):
        return

    try:
        with fjordlens.closing(fjordlens.get_conn()) as conn:
            needs_backfill = _ensure_people_stats_columns(conn)
            _install_people_stats_triggers(conn)
            if needs_backfill:
                started = time.perf_counter()
                _backfill_people_stats(conn)
                elapsed_ms = int((time.perf_counter() - started) * 1000)
                app.logger.info("People statistics backfill completed in %d ms", elapsed_ms)
    except Exception:
        # Keep FjordLens usable if an unusual SQLite/storage setup rejects the
        # optimization; the original People endpoint remains installed.
        app.logger.exception("Could not initialize materialized People statistics")
        return

    original = app.view_functions.get("api_people_list")
    if original is not None:
        app.view_functions["api_people_list"] = _make_fast_people_view(
            app, fjordlens, original
        )

    _start_cover_worker(fjordlens)
    app.extensions["fjordlens_people_stats_v1"] = True
