"""Durable list for explicitly requested recovery of staged uploads."""
import json
from pathlib import Path
from conversion_jobs import ConversionJob


class PendingUploads:
    def __init__(self, directory):
        self.store = ConversionJob(Path(directory) / 'pending_upload_journal', 'upload-recovery')

    def read(self):
        try:
            return json.loads(self.store.path.read_text(encoding='utf-8'))['items']
        except FileNotFoundError:
            return []

    def save(self, items):
        self.store.save({'items': list(dict.fromkeys(items))})

    def discover(self, root, extensions):
        items = set(self.read())
        root = Path(root)
        if root.exists():
            for path in root.rglob('*'):
                if (path.is_file() and not path.is_symlink() and path.suffix.lower() in extensions
                        and not any(part.startswith('.') or part == '@eaDir'
                                    for part in path.relative_to(root).parts)):
                    items.add('uploads/' + path.relative_to(root).as_posix())
        return sorted(items)
