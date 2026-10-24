"""Uploads must never expose an unregistered or incomplete import candidate."""
import sqlite3
from pathlib import Path
from unittest.mock import patch
import unittest

import app as fl
import test_upload_conversion_uploader as fixtures


class UploadAtomicCommitTests(unittest.TestCase):
    setUp = fixtures.UploadConversionUploaderTests.setUp
    tearDown = fixtures.UploadConversionUploaderTests.tearDown

    def commit(self, visitor=None):
        return fl._commit_uploaded_file(
            self.upload_target, 'uploads/originals/', 'album', self.incoming,
            'clip.mp4', None, 'Anna', share_visitor_id=visitor)

    def prepare(self):
        self.incoming = fl.DATA_DIR / 'incoming.mp4'
        self.incoming.write_bytes(b'complete upload')
        self.upload_target = fl.UPLOAD_DIR / 'originals' / 'album'
        self.rel = 'uploads/originals/album/clip.mp4'

    def row(self):
        with fl.closing(fl.get_conn()) as conn:
            return conn.execute('SELECT * FROM photos WHERE rel_path=?', (self.rel,)).fetchone()

    def test_interrupted_copy_never_becomes_a_direct_import(self):
        self.prepare()

        def interrupted(src, dst):
            Path(dst).write_bytes(b'partial')
            raise OSError('transfer interrupted')

        with patch.object(fl.shutil, 'copy2', side_effect=interrupted):
            with self.assertRaisesRegex(OSError, 'transfer interrupted'):
                self.commit()
        self.assertEqual(list(self.upload_target.iterdir()), [])
        self.assertIsNone(self.row())
        self.assertEqual(self.incoming.read_bytes(), b'complete upload')

    def test_database_failure_retains_transfer_without_publishing(self):
        self.prepare()
        with patch.object(fl, 'get_conn', side_effect=sqlite3.OperationalError('database is locked')):
            with self.assertRaisesRegex(sqlite3.OperationalError, 'database is locked'):
                self.commit()
        self.assertEqual(list(self.upload_target.iterdir()), [])
        self.assertIsNone(self.row())
        self.assertTrue(self.incoming.exists())

    def test_ownership_is_durable_before_publish_for_user_and_share(self):
        replace = fl.os.replace
        for visitor in (None, 'share-visitor-id'):
            with self.subTest(visitor=visitor):
                self.prepare()

                def publish(src, dst):
                    row = self.row()
                    self.assertEqual(row['uploaded_by'], 'Anna')
                    self.assertEqual(row['share_visitor_id'], visitor)
                    self.assertEqual(row['filename'], 'clip.mp4')
                    self.assertFalse(Path(dst).exists())
                    replace(src, dst)

                with patch.object(fl.os, 'replace', side_effect=publish) as publish_call, patch.object(fl, '_queue_uploaded_rel'):
                    ok, name, error = self.commit(visitor)
                publish_call.assert_called_once()
                self.assertTrue(ok, error)
                self.assertEqual(name, 'clip.mp4')
                self.assertFalse(self.incoming.exists())
                (self.upload_target / name).unlink()
                with fl.closing(fl.get_conn()) as conn:
                    conn.execute('DELETE FROM photos WHERE rel_path=?', (self.rel,))
                    conn.commit()

    def test_publish_failure_rolls_back_registration(self):
        self.prepare()
        with patch.object(fl.os, 'replace', side_effect=OSError('publish failed')):
            with self.assertRaisesRegex(OSError, 'publish failed'):
                self.commit()
        self.assertIsNone(self.row())
        self.assertTrue(self.incoming.exists())
        self.assertEqual(list(self.upload_target.iterdir()), [])

    def test_source_cleanup_failure_does_not_retry_committed_upload(self):
        self.prepare()
        unlink = Path.unlink

        def cleanup(path, *args, **kwargs):
            if path == self.incoming:
                raise PermissionError('source busy')
            return unlink(path, *args, **kwargs)

        with patch.object(Path, 'unlink', cleanup), patch.object(fl, '_queue_uploaded_rel') as queue:
            ok, name, error = self.commit()
        self.assertTrue(ok, error)
        self.assertEqual(name, 'clip.mp4')
        self.assertEqual(self.row()['uploaded_by'], 'Anna')
        queue.assert_called_once_with('Anna', self.rel)
