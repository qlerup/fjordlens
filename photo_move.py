"""Move selected upload media and their conversion counterparts without changing IDs."""
from contextlib import closing
import errno
import json
import os
from pathlib import Path
import shutil

from flask import jsonify, request


class MoveError(ValueError):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def move_file(source, target):
    """Exclusive destination creation: a concurrent file can never be overwritten."""
    try:
        os.link(source, target, follow_symlinks=False)
    except OSError as exc:
        if exc.errno not in (errno.EXDEV, errno.EPERM, errno.EOPNOTSUPP):
            raise
        try:
            with source.open('rb') as incoming, target.open('xb') as outgoing:
                try:
                    shutil.copyfileobj(incoming, outgoing)
                    outgoing.flush()
                    os.fsync(outgoing.fileno())
                except BaseException:
                    target.unlink(missing_ok=True)
                    raise
            shutil.copystat(source, target)
        except FileExistsError:
            raise
        except BaseException:
            target.unlink(missing_ok=True)
            raise
    try:
        source.unlink()
    except BaseException:
        target.unlink(missing_ok=True)
        raise


def rewrite(value, mapping):
    if isinstance(value, str):
        return mapping.get(value, value)
    if isinstance(value, list):
        return [rewrite(item, mapping) for item in value]
    if isinstance(value, dict):
        return {key: rewrite(item, mapping) for key, item in value.items()}
    return value


def move_selected(fl):
    body = request.get_json(silent=True) or {}
    moved, created = [], []
    committed = False
    try:
        ids = body.get('photo_ids')
        if not isinstance(ids, list) or not ids or len(ids) > 500 or any(type(i) is not int or i <= 0 for i in ids):
            raise MoveError('Vælg mellem 1 og 500 billeder ad gangen.')
        ids = list(dict.fromkeys(ids))
        parent = body.get('parent')
        if not isinstance(parent, str):
            raise MoveError('Vælg en destinationsmappe.')
        try:
            parent = fl.folder_index.normalize(parent)
            name = body.get('new_name', '')
            if not isinstance(name, str) or '/' in name or '\\' in name:
                raise ValueError()
            name = name.strip()
            destination = fl.folder_index.normalize(parent + '/' + name if parent and name else name or parent)
        except ValueError:
            raise MoveError('Ugyldig destinationsmappe.') from None
        if (fl._any_upload_transfer_active() or fl._any_regular_upload_postprocess_running()
                or fl.UPLOAD_FOLDER_SYNC_RUNNING or fl._direct_upload_active_rels_snapshot()
                or fl._pending_upload_rels_snapshot()):
            raise MoveError('Vent til upload og mappebehandling er afsluttet.', 409)
        with closing(fl.get_conn()) as conn:
            conn.execute('BEGIN IMMEDIATE')
            permission_rel = 'uploads/' + (parent if name else destination)
            if not fl._perm_allows(fl._current_user_folder_permission_for_rel(permission_rel, conn), 'edit'):
                raise MoveError('Du har ikke adgang til destinationsmappen.', 403)
            rows = conn.execute('SELECT id,rel_path,metadata_json FROM photos WHERE id IN (' + ','.join('?' for _ in ids) + ')', ids).fetchall()
            if len(rows) != len(ids):
                raise MoveError('Et af de valgte billeder findes ikke længere.', 404)
            mapping = {}
            renamed = 0
            for row in rows:
                rel = row['rel_path']
                if not rel.startswith('uploads/'):
                    raise MoveError('Kun billeder i uploads-mapper kan flyttes.')
                if not fl._perm_allows(fl._current_user_folder_permission_for_rel(rel, conn), 'edit'):
                    raise MoveError('Du har ikke adgang til at flytte alle valgte billeder.', 403)
                if fl.folder_privacy.private_parent(conn, rel) and not fl.folder_privacy.private_parent(conn, destination):
                    raise MoveError('Billeder fra en privat mappe skal flyttes til en privat mappe.', 409)
                related_paths = fl._related_photo_rel_paths_for_delete(rel, row['metadata_json'])
                if rel in mapping:
                    continue
                for related in related_paths:
                    if not related.startswith('uploads/'):
                        raise MoveError('Ugyldig billedsti.')
                    if not fl._perm_allows(fl._current_user_folder_permission_for_rel(related, conn), 'edit'):
                        raise MoveError('Ingen adgang til billedets original eller konverterede kopi.', 403)
                number = 1
                while True:
                    candidates = {}
                    for related in related_paths:
                        prefix = next((p for p in ('uploads/originals/', 'uploads/converted/') if related.startswith(p)), 'uploads/')
                        leaf = Path(related)
                        filename = leaf.name if number == 1 else f'{leaf.stem} ({number}){leaf.suffix}'
                        candidates[related] = prefix + (destination + '/' if destination else '') + filename
                    if all(before == after or (after not in mapping.values()
                            and not (fl.UPLOAD_DIR / after[len('uploads/'):]).exists()
                            and not conn.execute('SELECT 1 FROM photos WHERE rel_path=?', (after,)).fetchone())
                            for before, after in candidates.items()):
                        mapping.update(candidates)
                        renamed += number > 1
                        break
                    number += 1
                    if number > 10000:
                        raise MoveError('Kunne ikke finde et ledigt filnavn.', 409)
            base = fl.UPLOAD_DIR.resolve()
            operations = []
            def checked(rel):
                path = fl.UPLOAD_DIR / rel[len('uploads/'):]
                path.resolve().relative_to(base)
                if any(p.is_symlink() for p in [path, *path.parents] if p != base and base in p.parents):
                    raise MoveError('Symbolske links kan ikke flyttes.')
                return path
            for before, after in mapping.items():
                source, target = checked(before), checked(after)
                if before == after:
                    continue
                if target.exists() or conn.execute('SELECT 1 FROM photos WHERE rel_path=?', (after,)).fetchone():
                    raise MoveError('Destinationsmappen blev ændret under flytningen. Prøv igen.', 409)
                if source.exists():
                    if not source.is_file():
                        raise MoveError('Ugyldig billedfil.')
                    operations.append((source, target))
                elif any(row['rel_path'] == before for row in rows):
                    raise MoveError('Et valgt billede mangler på disken.', 404)
            if name and any((fl.UPLOAD_DIR / kind / destination).exists() for kind in ('originals', 'converted', '')):
                raise MoveError('Mappen findes allerede. Vælg den som eksisterende mappe.', 409)
            if not operations:
                raise MoveError('Billederne er allerede i den valgte mappe.')
            for source, target in operations:
                # Recheck boundaries immediately before touching disk.
                source.resolve().relative_to(base); target.resolve().relative_to(base)
                missing = []
                folder = target.parent
                while not folder.exists() and folder != base:
                    missing.append(folder); folder = folder.parent
                for folder in reversed(missing):
                    folder.mkdir(); created.append(folder)
                move_file(source, target)
                moved.append((source, target))
            related_rows = conn.execute('SELECT id,rel_path,metadata_json FROM photos WHERE rel_path IN (' + ','.join('?' for _ in mapping) + ')', list(mapping)).fetchall()
            for row in related_rows:
                metadata = row['metadata_json']
                if metadata:
                    try:
                        metadata = json.dumps(rewrite(json.loads(metadata), mapping), ensure_ascii=False)
                    except (ValueError, TypeError):
                        pass
                after = mapping[row['rel_path']]
                conn.execute('UPDATE photos SET rel_path=?,filename=?,metadata_json=? WHERE id=?', (after, Path(after).name, metadata, row['id']))
            fl.folder_index.ensure_path(conn, destination)
            # Saved manual covers may still point at the selected IDs in their old folder.
            for row in conn.execute('SELECT folder_path FROM folder_previews').fetchall():
                if row[0] in {destination, *(fl.folder_index.folder_from_rel(rel) for rel in mapping)}:
                    conn.execute('DELETE FROM folder_previews WHERE folder_path=?', (row[0],))
                    fl.folder_index.mark_dirty(conn, row[0])
            conn.commit()
            committed = True
        for before, after in mapping.items():
            if before != after:
                try:
                    fl._delete_photoframe_prepared_copy(before)
                except OSError:
                    pass
        return jsonify(ok=True, moved=len(ids), renamed=renamed, moved_files=len(moved), destination=destination, photo_ids=ids)
    except Exception as exc:
        if not committed:
            rollback_failed = False
            for source, target in reversed(moved):
                try:
                    move_file(target, source)
                except OSError:
                    rollback_failed = True
            for folder in reversed(created):
                try:
                    folder.rmdir()
                except OSError:
                    pass
            if rollback_failed:
                return jsonify(ok=False, error='Flytningen kunne ikke rulles helt tilbage. Kontrollér kilde- og destinationsmappen.'), 500
        if isinstance(exc, MoveError):
            return jsonify(ok=False, error=str(exc)), exc.status
        return jsonify(ok=False, error='Billederne kunne ikke flyttes. Prøv igen.'), 500
