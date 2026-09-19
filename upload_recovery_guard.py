"""Guard upload recovery against permanently unreadable JPEG stubs.

FjordLens intentionally keeps failed upload stubs in the photos table so transient
post-processing failures can be retried. A permanently corrupt JPEG would
therefore be re-added to every later upload. This module wraps only the recovery
merge step: newly uploaded files still get their first normal processing attempt,
while an older recovered JPEG is skipped when Pillow can prove that the source
file itself is unreadable.

The database stub is deliberately kept. That prevents the disk synchronizer from
rediscovering the same managed upload, while the original file remains untouched.
"""

from pathlib import Path
from typing import Iterable

from PIL import Image, UnidentifiedImageError

_PATCH_FLAG = "_fjordlens_unreadable_recovery_guard_installed"
_JPEG_SUFFIXES = {".jpg", ".jpeg", ".jpe"}


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
    """Install the recovery filter once for the imported FjordLens app module."""
    if getattr(core, _PATCH_FLAG, False):
        return

    original = getattr(core, "_merge_recovered_uploaded_rels", None)
    if not callable(original):
        return

    def guarded_merge(uploaded_by, uploaded_rels: Iterable[str] | None, *args, **kwargs):
        current = list(uploaded_rels or [])
        current_set = {str(rel) for rel in current}
        merged = original(uploaded_by, current, *args, **kwargs)

        filtered = []
        for rel in merged:
            rel_text = str(rel)
            # Never block a file on its first upload attempt. Only recovered
            # entries from older jobs are eligible for the permanent-error guard.
            if rel_text in current_set:
                filtered.append(rel)
                continue

            if _is_permanently_unreadable_recovery_jpeg(core, rel_text):
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
    setattr(core, _PATCH_FLAG, True)
