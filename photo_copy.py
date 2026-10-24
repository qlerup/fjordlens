"""Copy upload media families, then hand fresh rows to the upload pipeline."""
from contextlib import closing
import json
import os
from pathlib import Path
import shutil

from flask import jsonify, request

from photo_move import MoveError, rewrite


PREFIXES = ('uploads/originals/', 'uploads/converted/', 'uploads/')


def copy_file(source, target):
    """Independent bytes and exclusive creation; never overwrite a racing upload."""
    with source.open('rb') as incoming, target.open('xb') as outgoing:
        try:
            shutil.copyfileobj(incoming, outgoing)
            outgoing.flush()
            os.fsync(outgoing.fileno())
            shutil.copystat(source, target)
        except BaseException:
            target.unlink(missing_ok=True)
            raise


def copy_selected(fl):
    copied, created = [], []
    committed = False
    try:
        body = request.get_json(silent=True)
        if not isinstance(body, dict):
            raise MoveError('Ugyldig anmodning.')
        ids, parent = body.get('photo_ids'), body.get('parent')
        if not isinstance(ids, list) or not ids or len(ids) > 500 or any(type(i) is not int or i <= 0 for i in ids):
            raise MoveError('Vælg mellem 1 og 500 billeder ad gangen.')
        ids = list(dict.fromkeys(ids))
        if not isinstance(parent, str):
            raise MoveError('Vælg en destinationsmappe.')
        try:
            parent = fl.folder_index.normalize(parent)
            name = body.get('new_name', '')
            if not isinstance(name, str) or '/' in name or '\\' in name:
                raise ValueError()
            name = name.strip()
            destination = fl.folder_index.normalize('/'.join(filter(None, (parent, name))))
        except ValueError:
            raise MoveError('Ugyldig destinationsmappe.') from None
        if (fl._any_upload_transfer_active() or fl._any_regular_upload_postprocess_running()
                or fl.UPLOAD_FOLDER_SYNC_RUNNING or fl._direct_upload_active_rels_snapshot()
                or fl._pending_upload_rels_snapshot()):
            raise MoveError('Vent til upload og mappebehandling er afsluttet.', 409)
        actor = fl._audit_actor()
        base = fl.UPLOAD_DIR.resolve()

        def checked(rel):
            if not rel.startswith('uploads/'):
                raise MoveError('Kun billeder i uploads-mapper kan kopieres.')
            path = fl.UPLOAD_DIR / rel[len('uploads/'):]
            try:
                path.resolve().relative_to(base)
            except ValueError:
                raise MoveError('Ugyldig billedsti.') from None
            if any(p.is_symlink() for p in [path, *path.parents] if p != base and base in p.parents):
                raise MoveError('Symbolske links kan ikke kopieres.')
            return path

        with closing(fl.get_conn()) as conn:
            conn.execute('BEGIN IMMEDIATE')
            if not fl._perm_allows(fl._current_user_folder_permission_for_rel('uploads/' + parent, conn), 'upload'):
                raise MoveError('Du har ikke adgang til destinationsmappen.', 403)
            if not fl._perm_allows(fl._current_user_folder_permission_for_rel('uploads/' + destination, conn), 'upload'):
                raise MoveError('Du har ikke adgang til destinationsmappen.', 403)
            rows = conn.execute('SELECT * FROM photos WHERE id IN (' + ','.join('?' for _ in ids) + ')', ids).fetchall()
            if len(rows) != len(ids):
                raise MoveError('Et af de valgte billeder findes ikke længere.', 404)
            if name and any(checked(prefix + destination).exists() for prefix in PREFIXES):
                raise MoveError('Mappen findes allerede. Vælg den som eksisterende mappe.', 409)
            mapping, families = {}, []
            renamed = 0
            for row in rows:
                rel = row['rel_path']
                source = checked(rel)
                if not source.is_file():
                    raise MoveError('Et valgt billede mangler på disken.', 404)
                if rel in mapping:
                    continue  # Both database rows of the same family were selected.
                related = fl._related_photo_rel_paths_for_delete(rel, row['metadata_json'])
                for before in related:
                    checked(before)
                    if not fl._perm_allows(fl._current_user_folder_permission_for_rel(before, conn), 'view'):
                        raise MoveError('Ingen adgang til billedets original eller konverterede kopi.', 403)
                    if fl.folder_privacy.private_parent(conn, before) and not fl.folder_privacy.private_parent(conn, destination):
                        raise MoveError('Billeder fra en privat mappe skal kopieres til en privat mappe.', 409)
                for number in range(10000):
                    candidates = {}
                    for before in sorted(related):
                        prefix = next(p for p in PREFIXES if before.startswith(p))
                        leaf = Path(before)
                        filename = leaf.name if not number else f'{leaf.stem}_{number}{leaf.suffix}'
                        candidates[before] = prefix + (destination + '/' if destination else '') + filename
                    # Check all storage trees as well as staged uploads and database-only
                    # names. A name in another tree must not become a false counterpart.
                    occupied = False
                    for after in candidates.values():
                        filename = Path(after).name
                        for prefix in PREFIXES:
                            variant = prefix + (destination + '/' if destination else '') + filename
                            if (variant in mapping.values() or checked(variant).exists()
                                    or fl._staged_upload_path(variant).exists()
                                    or conn.execute('SELECT 1 FROM photos WHERE rel_path=?', (variant,)).fetchone()):
                                occupied = True
                                break
                        if occupied:
                            break
                    if not occupied:
                        break
                else:
                    raise MoveError('Kunne ikke finde et ledigt filnavn.', 409)
                mapping.update(candidates)
                renamed += bool(number)
                # Queue the ready converted file, so current conversion/delete-original
                # settings cannot alter an already converted, faithful copy.
                existing = [r for r in sorted(related) if checked(r).is_file()]
                canonical = next((r for r in existing if r.startswith('uploads/converted/')), rel)
                canonical_row = conn.execute('SELECT * FROM photos WHERE rel_path=?', (canonical,)).fetchone() or row
                families.append((canonical, canonical_row, related))
            # All selections and permissions have been validated before creating files.
            for before, after in mapping.items():
                source, target = checked(before), checked(after)
                if not source.exists():
                    continue  # Originals deliberately removed by earlier conversion.
                if not source.is_file():
                    raise MoveError('Ugyldig billedfil.')
                missing, folder = [], target.parent
                while not folder.exists() and folder != base:
                    missing.append(folder)
                    folder = folder.parent
                for folder in reversed(missing):
                    folder.mkdir()
                    created.append(folder)
                copy_file(source, target)
                copied.append(target)
            new_ids, rels = [], []
            for before, source_row, related in families:
                after = mapping[before]
                try:
                    metadata = json.loads(source_row['metadata_json'] or '{}')
                except (ValueError, TypeError):
                    metadata = {}
                metadata = rewrite(metadata, mapping) if isinstance(metadata, dict) else {}
                originals = [mapping[r] for r in sorted(related)
                             if not r.startswith('uploads/converted/') and checked(r).is_file()]
                if after.startswith('uploads/converted/') and originals and not metadata.get('conversion'):
                    fl._attach_conversion_metadata(metadata_holder := {'metadata_json': metadata},
                                                   from_rel_path=originals[0], to_rel_path=after)
                    metadata = metadata_holder['metadata_json']
                stat = checked(after).stat()
                cursor = conn.execute('''INSERT INTO photos
                    (rel_path,filename,ext,file_size,metadata_json,uploaded_by,imported_at,favorite,captured_at,gps_lat,gps_lon)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?)''',
                    (after, Path(after).name, Path(after).suffix.lower(), stat.st_size,
                     json.dumps(metadata, ensure_ascii=False), actor, fl.now_iso(), source_row['favorite'],
                     source_row['captured_at'], source_row['gps_lat'], source_row['gps_lon']))
                new_ids.append(cursor.lastrowid)
                rels.append(after)
            fl.folder_index.ensure_path(conn, destination)
            fl.folder_index.mark_dirty(conn, destination)
            conn.commit()
            committed = True
        # Rows without thumbnails are also recoverable by the ordinary upload worker
        # after a restart. Do not roll back committed copies if scheduling fails.
        try:
            for rel in rels:
                fl._queue_uploaded_rel(actor, rel)
            started = fl._ensure_upload_postprocess_running(actor)
            pending = not started and not fl._is_upload_postprocess_running(actor)
        except Exception as exc:
            started, pending = False, True
            fl.log_event('error', error=f'copy_postprocess: {exc}')
        return jsonify(ok=True, copied=len(families), copied_files=len(copied), renamed=renamed,
                       destination=destination, photo_ids=new_ids, postprocess_started=started,
                       postprocess_pending=pending)
    except Exception as exc:
        rollback_failed = False
        if not committed:
            for target in reversed(copied):
                try:
                    target.unlink()
                except OSError:
                    rollback_failed = True
            for folder in reversed(created):
                try:
                    folder.rmdir()
                except OSError:
                    pass
        if rollback_failed:
            return jsonify(ok=False, error='Kopieringen kunne ikke rulles helt tilbage. Kontrollér destinationsmappen.'), 500
        if isinstance(exc, MoveError):
            return jsonify(ok=False, error=str(exc)), exc.status
        fl.log_event('error', error=f'copy_selected: {exc}')
        return jsonify(ok=False, error='Billederne kunne ikke kopieres. Prøv igen.'), 500
