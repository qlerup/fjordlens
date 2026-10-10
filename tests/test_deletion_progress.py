import json
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import app as fl
import deletion_progress
import test_manager_role as fixtures


class DeletionProgressTests(unittest.TestCase):
    setUp = fixtures.ManagerRoleTests.setUp
    tearDown = fixtures.ManagerRoleTests.tearDown
    client = fixtures.ManagerRoleTests.client

    def events(self, client, paths):
        response = client.post('/api/settings/upload-folder-delete', json={'paths':paths,'progress':True}, buffered=False)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers['X-Accel-Buffering'], 'no')
        events = [json.loads(line) for chunk in response.response for line in chunk.decode().splitlines() if line]
        response.close()
        return events

    def test_live_counts_include_originals_converted_and_legacy_files(self):
        paths = []
        for root in ('originals', 'converted', ''):
            folder = fl.UPLOAD_DIR / root / 'DeleteMe'
            folder.mkdir(parents=True, exist_ok=True)
            for index in range(8):
                path = folder / f'{index}.jpg'
                path.write_bytes(b'test')
                paths.append(path)
        original_unlink = Path.unlink
        def slow_unlink(path, *args, **kwargs):
            original_unlink(path, *args, **kwargs)
            if path in paths:
                time.sleep(.02)
        with patch.object(Path, 'unlink', slow_unlink):
            events = self.events(self.client(1), ['DeleteMe'])
        progress = [e for e in events if e['type'] == 'progress']
        self.assertTrue(any(e['phase'] == 'deleting' and 0 < e['done'] < 24 for e in progress), progress)
        self.assertTrue(all(e['total'] == 24 for e in progress if e['phase'] != 'counting'))
        self.assertTrue(any(e['phase'] == 'cleanup' and e['done'] == 24 for e in progress))
        self.assertTrue(events[-1]['data']['ok'], events[-1])
        self.assertEqual(events[-1]['data']['removed_files'], 24)
        self.assertFalse(any(path.exists() for path in paths))

    def test_streamed_permissions_validate_every_folder_before_deleting(self):
        events = self.events(self.client(3), ['private'])
        self.assertEqual(events[-1]['status'], 403)
        self.assertFalse(events[-1]['data']['ok'])
        self.assertTrue((fl.UPLOAD_DIR / 'originals/private/a.jpg').exists())

    def test_partial_failure_reports_exact_successful_file_count(self):
        folder = fl.UPLOAD_DIR / 'originals/DeleteMe'
        folder.mkdir(parents=True, exist_ok=True)
        for index in range(5):
            (folder / f'{index}.jpg').write_bytes(b'test')
        original_unlink, removed = Path.unlink, []
        def fail_third(path, *args, **kwargs):
            if path.parent == folder:
                if len(removed) == 2:
                    raise PermissionError('Test disk failure')
                original_unlink(path, *args, **kwargs)
                removed.append(path)
            else:
                original_unlink(path, *args, **kwargs)
        with patch.object(Path, 'unlink', fail_third):
            events = self.events(self.client(1), ['DeleteMe'])
        self.assertEqual(events[-1]['status'], 400)
        self.assertFalse(events[-1]['data']['ok'])
        progress = [e for e in events if e['type'] == 'progress']
        self.assertEqual(progress[-1]['done'], 2)
        self.assertEqual(len(list(folder.iterdir())), 3)
