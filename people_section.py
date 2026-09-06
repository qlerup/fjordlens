"""FjordLens People-section performance and manager access fixes.

Kept outside the monolithic app.py so the optimization can be enabled without
changing unrelated photo-library code. Registered from wsgi.py in production.
"""
from __future__ import annotations

import json
import sqlite3
from functools import wraps
from typing import Any, Dict, Optional

from flask import current_app, jsonify, request
from flask_login import current_user


def _acl_sql(prefixes: Optional[list[str]], photo_alias: str = "ph") -> tuple[str, list[Any]]:
    if prefixes is None:
        return "", []
    clauses: list[str] = []
    params: list[Any] = []
    for pref in prefixes:
        clauses.append(f"({photo_alias}.rel_path=? OR {photo_alias}.rel_path LIKE ?)")
        params.extend([pref, pref + "/%"])
    return ("(" + " OR ".join(clauses) + ")" if clauses else "0=1"), params


def _person_sort_key(item: Dict[str, Any]) -> tuple[int, int, str]:
    raw_id = str((item or {}).get("id") or "").strip().lower()
    name = str((item or {}).get("name") or "").strip()
    unknown = raw_id == "unknown" or name.lower().startswith(("ukendt", "unknown"))
    try:
        count = max(0, int((item or {}).get("count") or 0))
    except Exception:
        count = 0
    return (1 if unknown else 0, -count, name.casefold())


def _fast_people_list(fjordlens, original):
    """Replace /api/people's per-person N+1 queries with one ranked batch query."""

    @wraps(original)
    def view():
        include_hidden = request.args.get("include_hidden") in {"1", "true", "True"}
        try:
            with fjordlens.closing(fjordlens.get_conn()) as conn:
                acl_prefixes = fjordlens._current_user_acl_prefixes(conn)
                acl_where, acl_params = _acl_sql(acl_prefixes)

                # The old endpoint executed COUNT + "best thumbnail face" once per
                # person. Rank all visible faces in one pass instead.
                photo_join = (
                    "LEFT JOIN photos ph ON ph.id = f.photo_id"
                    if acl_prefixes is None
                    else "INNER JOIN photos ph ON ph.id = f.photo_id"
                )
                hidden_where = "" if include_hidden else "AND COALESCE(p.hidden,0)=0"
                acl_filter = f"AND {acl_where}" if acl_prefixes is not None else ""

                ranked_rows = conn.execute(
                    f"""
                    WITH ranked_faces AS (
                        SELECT
                            p.id AS person_id,
                            p.name AS person_name,
                            COALESCE(p.hidden,0) AS person_hidden,
                            f.id AS face_id,
                            COUNT(*) OVER (PARTITION BY p.id) AS face_count,
                            ROW_NUMBER() OVER (
                                PARTITION BY p.id
                                ORDER BY
                                    CASE WHEN COALESCE(f.confidence, 0) >= 0.70 THEN 1 ELSE 0 END DESC,
                                    CASE WHEN f.frame_sec IS NOT NULL THEN 1 ELSE 0 END DESC,
                                    CASE
                                        WHEN COALESCE(ph.width,0) > 0
                                         AND COALESCE(ph.height,0) > 0
                                         AND (1.0 * COALESCE(f.bbox_w,0) * COALESCE(f.bbox_h,0))
                                             / (1.0 * ph.width * ph.height) BETWEEN 0.02 AND 0.45
                                        THEN 1 ELSE 0
                                    END DESC,
                                    CASE
                                        WHEN COALESCE(f.bbox_w,0) >= 72
                                         AND COALESCE(f.bbox_h,0) >= 72
                                        THEN 1 ELSE 0
                                    END DESC,
                                    CASE
                                        WHEN COALESCE(f.bbox_h,0) > 0
                                         AND (1.0 * COALESCE(f.bbox_w,0) / COALESCE(f.bbox_h,1))
                                             BETWEEN 0.55 AND 1.90
                                        THEN 1 ELSE 0
                                    END DESC,
                                    COALESCE(f.confidence, 0) DESC,
                                    (COALESCE(f.bbox_w,0) * COALESCE(f.bbox_h,0)) DESC,
                                    f.id DESC
                            ) AS rn
                        FROM faces f
                        INNER JOIN people p ON p.id = f.person_id
                        {photo_join}
                        WHERE f.person_id IS NOT NULL
                        {hidden_where}
                        {acl_filter}
                    )
                    SELECT person_id, person_name, person_hidden, face_id, face_count
                    FROM ranked_faces
                    WHERE rn=1
                    """,
                    acl_params,
                ).fetchall()

                people: list[Dict[str, Any]] = []
                for row in ranked_rows:
                    face_id = int(row["face_id"])
                    people.append(
                        {
                            "id": int(row["person_id"]),
                            "name": row["person_name"],
                            "count": int(row["face_count"] or 0),
                            "thumb_url": f"/api/face-thumb/{face_id}",
                            "hidden": bool(int(row["person_hidden"] or 0)),
                        }
                    )
                    try:
                        fjordlens._enqueue_face_thumb_generation(face_id)
                    except Exception:
                        pass

                # Preserve the existing special "Unknown" bucket semantics:
                # its count is distinct photos, not number of face rows.
                if acl_prefixes is None:
                    unknown_count_row = conn.execute(
                        "SELECT COUNT(DISTINCT photo_id) AS c FROM faces WHERE person_id IS NULL"
                    ).fetchone()
                    unknown_face_row = conn.execute(
                        """
                        SELECT f.id
                        FROM faces f
                        LEFT JOIN photos ph ON ph.id = f.photo_id
                        WHERE f.person_id IS NULL
                        ORDER BY
                            CASE WHEN COALESCE(f.confidence, 0) >= 0.70 THEN 1 ELSE 0 END DESC,
                            CASE WHEN f.frame_sec IS NOT NULL THEN 1 ELSE 0 END DESC,
                            CASE
                                WHEN COALESCE(ph.width,0) > 0 AND COALESCE(ph.height,0) > 0
                                 AND (1.0 * COALESCE(f.bbox_w,0) * COALESCE(f.bbox_h,0))
                                     / (1.0 * ph.width * ph.height) BETWEEN 0.02 AND 0.45
                                THEN 1 ELSE 0
                            END DESC,
                            CASE
                                WHEN COALESCE(f.bbox_w,0) >= 72 AND COALESCE(f.bbox_h,0) >= 72
                                THEN 1 ELSE 0
                            END DESC,
                            CASE
                                WHEN COALESCE(f.bbox_h,0) > 0
                                 AND (1.0 * COALESCE(f.bbox_w,0) / COALESCE(f.bbox_h,1))
                                     BETWEEN 0.55 AND 1.90
                                THEN 1 ELSE 0
                            END DESC,
                            COALESCE(f.confidence,0) DESC,
                            (COALESCE(f.bbox_w,0) * COALESCE(f.bbox_h,0)) DESC,
                            f.id DESC
                        LIMIT 1
                        """
                    ).fetchone()
                else:
                    unknown_count_row = conn.execute(
                        f"""
                        SELECT COUNT(DISTINCT f.photo_id) AS c
                        FROM faces f
                        INNER JOIN photos ph ON ph.id = f.photo_id
                        WHERE f.person_id IS NULL AND {acl_where}
                        """,
                        acl_params,
                    ).fetchone()
                    unknown_face_row = conn.execute(
                        f"""
                        SELECT f.id
                        FROM faces f
                        INNER JOIN photos ph ON ph.id = f.photo_id
                        WHERE f.person_id IS NULL AND {acl_where}
                        ORDER BY
                            CASE WHEN COALESCE(f.confidence, 0) >= 0.70 THEN 1 ELSE 0 END DESC,
                            CASE WHEN f.frame_sec IS NOT NULL THEN 1 ELSE 0 END DESC,
                            CASE
                                WHEN COALESCE(ph.width,0) > 0 AND COALESCE(ph.height,0) > 0
                                 AND (1.0 * COALESCE(f.bbox_w,0) * COALESCE(f.bbox_h,0))
                                     / (1.0 * ph.width * ph.height) BETWEEN 0.02 AND 0.45
                                THEN 1 ELSE 0
                            END DESC,
                            CASE
                                WHEN COALESCE(f.bbox_w,0) >= 72 AND COALESCE(f.bbox_h,0) >= 72
                                THEN 1 ELSE 0
                            END DESC,
                            CASE
                                WHEN COALESCE(f.bbox_h,0) > 0
                                 AND (1.0 * COALESCE(f.bbox_w,0) / COALESCE(f.bbox_h,1))
                                     BETWEEN 0.55 AND 1.90
                                THEN 1 ELSE 0
                            END DESC,
                            COALESCE(f.confidence,0) DESC,
                            (COALESCE(f.bbox_w,0) * COALESCE(f.bbox_h,0)) DESC,
                            f.id DESC
                        LIMIT 1
                        """,
                        acl_params,
                    ).fetchone()

                unknown_count = int(unknown_count_row["c"] or 0) if unknown_count_row else 0
                if unknown_count > 0:
                    unknown_face_id = int(unknown_face_row["id"]) if unknown_face_row else None
                    unknown_item: Dict[str, Any] = {
                        "id": "unknown",
                        "name": "Ukendte",
                        "count": unknown_count,
                        "thumb_url": (
                            f"/api/face-thumb/{unknown_face_id}" if unknown_face_id is not None else None
                        ),
                    }
                    people.append(unknown_item)
                    if unknown_face_id is not None:
                        try:
                            fjordlens._enqueue_face_thumb_generation(unknown_face_id)
                        except Exception:
                            pass

                # Preserve the existing "maybe this person" suggestions for
                # automatically named unknown clusters.
                try:
                    person_items_by_id: Dict[int, Dict[str, Any]] = {}
                    person_ids: list[int] = []
                    for item in people:
                        try:
                            pid = int((item or {}).get("id"))
                        except Exception:
                            continue
                        person_items_by_id[pid] = item
                        person_ids.append(pid)

                    if person_ids:
                        placeholders = ",".join("?" for _ in person_ids)
                        centroid_rows = conn.execute(
                            f"SELECT id, centroid_json FROM people WHERE id IN ({placeholders})",
                            person_ids,
                        ).fetchall()
                        centroid_by_id: Dict[int, list[float]] = {}
                        for row in centroid_rows:
                            try:
                                raw = json.loads(row["centroid_json"]) if row["centroid_json"] else None
                                if isinstance(raw, list) and raw:
                                    centroid_by_id[int(row["id"])] = [float(x or 0.0) for x in raw]
                            except Exception:
                                continue

                        known_pool: list[tuple[int, str, list[float]]] = []
                        unknown_targets: list[int] = []
                        for pid, item in person_items_by_id.items():
                            vector = centroid_by_id.get(pid)
                            if not vector or (item or {}).get("hidden"):
                                continue
                            name = str((item or {}).get("name") or "")
                            if name.strip().lower().startswith(("ukendt", "unknown")):
                                unknown_targets.append(pid)
                            else:
                                known_pool.append((pid, name, vector))

                        if (
                            known_pool
                            and unknown_targets
                            and fjordlens.FACE_MAYBE_THRESHOLD < fjordlens.FACE_MATCH_THRESHOLD_CENTROID
                        ):
                            for unknown_pid in unknown_targets:
                                vector = centroid_by_id.get(unknown_pid)
                                if not vector:
                                    continue
                                best_id = None
                                best_name = ""
                                best_score = -1.0
                                for known_pid, known_name, known_vector in known_pool:
                                    score = fjordlens._cosine(vector, known_vector)
                                    if score > best_score:
                                        best_id = known_pid
                                        best_name = known_name
                                        best_score = score
                                if (
                                    best_id is not None
                                    and best_name
                                    and best_score >= fjordlens.FACE_MAYBE_THRESHOLD
                                    and best_score < fjordlens.FACE_MATCH_THRESHOLD_CENTROID
                                ):
                                    target = person_items_by_id.get(unknown_pid)
                                    if target is not None:
                                        target["maybe_person_id"] = int(best_id)
                                        target["maybe_person_name"] = str(best_name)
                                        target["maybe_score"] = round(float(best_score), 4)
                except Exception:
                    pass

                people.sort(key=_person_sort_key)
                return jsonify({"ok": True, "items": people})
        except sqlite3.OperationalError:
            # Older/atypical SQLite builds without window functions should keep
            # working; they simply fall back to the original implementation.
            current_app.logger.warning(
                "Fast People query unavailable; falling back to legacy /api/people",
                exc_info=True,
            )
            return original()
        except Exception:
            current_app.logger.exception(
                "Fast People query failed; falling back to legacy /api/people"
            )
            return original()

    return view


def _allow_manager_for_people_action(original):
    """Let managers through the existing admin maintenance guard only here.

    The User object is request-local. Temporarily presenting this request as
    admin lets us reuse the original, tested endpoint body and restores the role
    before dispatch returns. Other routes and permissions remain unchanged.
    """

    @wraps(original)
    def view(*args, **kwargs):
        user = current_user._get_current_object()
        role = str(getattr(user, "role", "user") or "user").strip().lower()
        if role != "manager":
            return original(*args, **kwargs)

        previous_role = getattr(user, "role", "manager")
        try:
            user.role = "admin"
            return original(*args, **kwargs)
        finally:
            user.role = previous_role

    return view


def init_people_section(app) -> None:
    """Install People performance/access fixes once per Flask app."""
    if app.extensions.get("fjordlens_people_section_v2"):
        return

    import app as fjordlens

    original_people_list = app.view_functions.get("api_people_list")
    if original_people_list is not None:
        app.view_functions["api_people_list"] = _fast_people_list(
            fjordlens, original_people_list
        )

    # These are content-management actions in the People section. Managers get
    # them; system maintenance, logs, scans, settings and user admin stay admin-only.
    for endpoint in (
        "api_people_train_one",
        "api_people_train_all",
        "api_faces_match_unknown",
        "api_people_hide",
        "api_people_rename",
    ):
        original = app.view_functions.get(endpoint)
        if original is not None:
            app.view_functions[endpoint] = _allow_manager_for_people_action(original)

    app.extensions["fjordlens_people_section_v2"] = True
