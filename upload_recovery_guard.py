"""One-shot retry policy for FjordLens upload post-processing.

Each upload gets one normal pass. When that complete pass is finished, only files
from that upload which FjordLens still considers recoverable are retried once.
Files that are still pending after the retry are marked terminal and are excluded
from recovery on later uploads.

The terminal marker is stored under DATA_DIR so the policy survives container
restarts. Re-uploading the same relative path clears its old terminal marker and
gives the new upload a fresh normal attempt + one retry.
"""

import json
import os
import threading
from pathlib import Path
from typing import Iterable

from PIL import Image, UnidentifiedImageError

_PATCH_FLAG = "_fjordlens_one_shot_upload_retry_installed"
_JPEG_SUFFIXES = {".jpg", ".jpeg", ".jpe"}
_STATE_LOCK = threading.RLock()
_STATE_FILE = "upload_terminal_failures.json"


def _state_path(core) -> Path | None:
    data_dir = getattr(core, "DATA_DIR", None)
    if data_dir is None:
        return None
    return Path(data_dir) / _STATE_FILE


def _load_terminal(core) -> set[str]:
    path = _state_path(core)
    if path is None or not path.is_file():
        return set()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        values = payload.get("terminal", []) if isinstance(payload, dict) else payload
        return {str(v) for v in values if str(v).strip()}
    except Exception:
        return set()


def _save_terminal(core, values: set[str]) -> None:
    path = _state_path(core)
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps({"terminal": sorted(values)}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    os.replace(tmp, path)


def _clear_terminal(core, rels: Iterable[str]) -> None:
    rels = {str(rel) for rel in rels}
    if not rels:
        return
    with _STATE_LOCK:
        values = _load_terminal(core)
        changed = values.intersection(rels)
        if changed:
            values.difference_update(rels)
            _save_terminal(core, values)


def _mark_terminal(core, rels: Iterable[str]) -> None:
    rels = {str(rel) for rel in rels}
    if not rels:
        return
    with _STATE_LOCK:
        values = _load_terminal(core)
        before = len(values)
        values.update(rels)
        if len(values) != before:
            _save_terminal(core, values)


def _source_path(core, rel_path: str) -> Path | None:
    rel = str(rel_path or "").replace("\\", "/").lstrip("/")
    if not rel:
        return None

    upload_dir = getattr(core, "UPLOAD_DIR", None)
    if upload_dir is not None:
        leaf = rel[len("uploads/") :] if rel.startswith("uploads/") else rel
        candidate = Path(upload_dir) / leaf
        if candidate.is_file():
            return candidate

    staged_path = getattr(core, "_staged_upload_path", None)
    if callable(staged_path):
        try:
            candidate = Path(staged_path(rel_path))
        except Exception:
            candidate = None
        if candidate is not None and candidate.is_file():
            return candidate

    return None


def _is_permanently_unreadable_recovery_jpeg(core, rel_path: str) -> bool:
    """Keep the earlier corrupt-JPEG protection as a fast permanent-failure guard."""
    source = _source_path(core, rel_path)
    if source is None or source.suffix.lower() not in _JPEG_SUFFIXES:
        return False

    try:
        with Image.open(source) as image:
            image.verify()
        return False
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError):
        return True


def init_upload_recovery_guard(core) -> None:
    """Install one-shot retry and terminal recovery filtering once."""
    if getattr(core, _PATCH_FLAG, False):
        return

    raw_merge = getattr(core, "_merge_recovered_uploaded_rels", None)
    raw_postprocess = getattr(core, "_postprocess_uploaded_rels", None)
    if not callable(raw_merge):
        return

    def guarded_merge(uploaded_by, uploaded_rels: Iterable[str] | None, *args, **kwargs):
        current = list(uploaded_rels or [])
        current_set = {str(rel) for rel in current}
        merged = raw_merge(uploaded_by, current, *args, **kwargs)

        with _STATE_LOCK:
            terminal = _load_terminal(core)

        filtered = []
        for rel in merged:
            rel_text = str(rel)

            # An explicitly current upload always gets a fresh chance.
            if rel_text in current_set:
                filtered.append(rel)
                continue

            # Never resurrect a file which already exhausted its single retry.
            if rel_text in terminal:
                continue

            # Backward compatibility for old corrupt JPEG stubs created before
            # terminal markers existed.
            if _is_permanently_unreadable_recovery_jpeg(core, rel_text):
                _mark_terminal(core, [rel_text])
                logger = getattr(core, "logger", None)
                if logger is not None:
                    logger.warning(
                        "Skipping permanently unreadable recovered upload: %s",
                        rel_text,
                    )
                continue

            filtered.append(rel)

        return filtered

    core._merge_recovered_uploaded_rels = guarded_merge

    if callable(raw_postprocess):
        def one_shot_postprocess(uploaded_by, uploaded_rels, *args, **kwargs):
            current = [str(rel) for rel in (uploaded_rels or [])]
            if current:
                # A deliberate re-upload of the same path starts a new lifecycle.
                _clear_terminal(core, current)

            first_result = raw_postprocess(uploaded_by, uploaded_rels, *args, **kwargs)
            if not current:
                return first_result

            # Ask FjordLens' own recovery logic which CURRENT files are still
            # incomplete. This avoids guessing based on file extension or result
            # counters and keeps conversion/thumbnail/index failures together.
            try:
                pending_after_first = {
                    str(rel)
                    for rel in raw_merge(uploaded_by, [], *args, **kwargs)
                }.intersection(current)
            except TypeError:
                pending_after_first = {
                    str(rel) for rel in raw_merge(uploaded_by, [])
                }.intersection(current)

            if not pending_after_first:
                return first_result

            logger = getattr(core, "logger", None)
            if logger is not None:
                logger.warning(
                    "Retrying %d failed upload item(s) once after workflow completion",
                    len(pending_after_first),
                )

            retry_rels = [rel for rel in current if rel in pending_after_first]
            raw_postprocess(uploaded_by, retry_rels, *args, **kwargs)

            try:
                still_pending = {
                    str(rel)
                    for rel in raw_merge(uploaded_by, [], *args, **kwargs)
                }.intersection(pending_after_first)
            except TypeError:
                still_pending = {
                    str(rel) for rel in raw_merge(uploaded_by, [])
                }.intersection(pending_after_first)

            if still_pending:
                _mark_terminal(core, still_pending)
                if logger is not None:
                    logger.warning(
                        "%d upload item(s) still failed after retry; suppressing future automatic retries: %s",
                        len(still_pending),
                        ", ".join(sorted(still_pending)),
                    )

            return first_result

        core._postprocess_uploaded_rels = one_shot_postprocess

    setattr(core, _PATCH_FLAG, True)
