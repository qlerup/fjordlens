import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch
import app as fl
import test_upload_conversion_uploader as fixtures
from pending_uploads import PendingUploads
from PIL import Image


class PendingUploadTests(unittest.TestCase):
    setUp = fixtures.UploadConversionUploaderTests.setUp
    tearDown = fixtures.UploadConversionUploaderTests.tearDown

    def staged(self, rel):
        path = fl._staged_upload_path(rel)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b'original upload')
        return path

    def output(self, rel):
        path = fl.UPLOAD_DIR / rel.removeprefix('uploads/')
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b'converted file')
        return path

    def test_scan_finds_disk_only_files_and_journal_after_restart(self):
        rel = 'uploads/originals/old/photo.HEIC'
        self.staged(rel)
        journal = PendingUploads(fl.DATA_DIR)
        journal.save(['uploads/originals/earlier.MOV'])
        result = PendingUploads(fl.DATA_DIR).discover(fl.CONVERSION_WORK_DIR / 'pending', fl.SUPPORTED_EXTS)
        self.assertEqual(set(result), {rel, 'uploads/originals/earlier.MOV'})

    def test_scan_requires_separate_start_and_preserves_reviewed_selection(self):
        rel = 'uploads/originals/old/photo.HEIC'
        self.staged(rel)
        with (fl.app.test_request_context('/api/uploads/pending-recovery', method='POST', json={'action': 'scan'}),
              patch.object(fl, 'current_user', SimpleNamespace(is_admin=True)),
              patch.object(fl, '_start_bulk_conversion_job') as start):
            data = fl.api_pending_upload_recovery.__wrapped__().get_json()
            self.assertEqual(data['count'], 1)
            start.assert_not_called()
        self.staged('uploads/originals/new/new.MOV')
        preview = fl.DATA_DIR / 'pending_upload_previews' / (data['token'] + '.json')
        self.assertEqual(json.loads(preview.read_text()), [rel])

    def test_reuse_publishes_original_without_creating_another_conversion(self):
        for ext, suffix in [('.HEIC', '.jpg'), ('.DNG', '.jpg'), ('.MOV', '.mp4')]:
            source = f'uploads/originals/old/photo{ext}'
            target = f'uploads/converted/old/photo{suffix}'
            local = self.staged(source)
            output = self.output(target)
            with (patch.object(fl, 'heic_keep_originals_enabled', return_value=True),
                  patch.object(fl, 'raw_keep_originals_enabled', return_value=True),
                  patch.object(fl, 'mov_keep_originals_enabled', return_value=True),
                  patch.object(fl, '_convert_on_local_storage') as convert):
                result = fl._queued_upload_conversion(source, 'gentle', existing_rel=target)
            self.assertTrue(result['success'])
            self.assertFalse(local.exists())
            self.assertEqual((fl.UPLOAD_DIR / source.removeprefix('uploads/')).read_bytes(), b'original upload')
            self.assertEqual(output.read_bytes(), b'converted file')
            convert.assert_not_called()
            self.assertFalse(output.with_stem(output.stem + '_1').exists())

    def test_conflicting_original_is_not_overwritten_or_removed(self):
        source = 'uploads/originals/old/photo.HEIC'
        local = self.staged(source)
        original = self.output(source)
        with patch.object(fl, 'heic_keep_originals_enabled', return_value=True):
            with self.assertRaisesRegex(RuntimeError, 'andet indhold'):
                fl._publish_recovered_original(source)
        self.assertTrue(local.exists())
        self.assertEqual(original.read_bytes(), b'converted file')

    def test_failed_later_stage_stays_in_journal_after_original_moves_then_retries(self):
        source = 'uploads/originals/old/photo.HEIC'
        target = 'uploads/converted/old/photo.jpg'
        self.staged(source)
        self.output(target)
        calls = []
        def pipeline(user, rels, **kwargs):
            calls.append(rels)
            fl._publish_recovered_original(source)
            return {'indexed': 1, 'faces_errors': 1 if len(calls) == 1 else 0}
        with (patch.object(fl, 'heic_keep_originals_enabled', return_value=True),
              patch.object(fl, '_postprocess_uploaded_rels', side_effect=pipeline)):
            first = fl._recover_pending_uploads([source])
            self.assertEqual(first['remaining'], 1)
            self.assertEqual(PendingUploads(fl.DATA_DIR).read(), [source])
            second = fl._recover_pending_uploads([source])
            self.assertEqual(second['remaining'], 0)
            self.assertEqual(PendingUploads(fl.DATA_DIR).read(), [])

    def test_conversion_failure_keeps_local_original_and_journal(self):
        source = 'uploads/originals/old/photo.HEIC'
        local = self.staged(source)
        with (patch.object(fl, 'heic_convert_on_upload_enabled', return_value=True),
              patch.object(fl, '_postprocess_uploaded_rels', return_value={'indexed': 1})):
            result = fl._recover_pending_uploads([source])
        self.assertEqual(result['remaining'], 1)
        self.assertGreater(result['errors'], 0)
        self.assertTrue(local.exists())

    def test_missing_deleted_original_recovers_using_converted_file(self):
        source = 'uploads/originals/old/photo.HEIC'
        target = 'uploads/converted/old/photo.jpg'
        self.output(target)
        PendingUploads(fl.DATA_DIR).save([source])
        with patch.object(fl, '_postprocess_uploaded_rels', return_value={'indexed': 1}) as process:
            result = fl._recover_pending_uploads([source])
        self.assertEqual(process.call_args.args[1], [target])
        self.assertEqual(result['remaining'], 0)

    def test_existing_conversion_runs_real_metadata_thumbnail_pipeline_without_duplicate(self):
        source = 'uploads/originals/old/photo.HEIC'
        target = 'uploads/converted/old/photo.jpg'
        local = self.staged(source)
        output = self.output(target)
        Image.new('RGB', (32, 24), color='blue').save(output)
        fl._upsert_uploaded_stub(source, local, 'Anna')
        with (patch.object(fl, 'heic_convert_on_upload_enabled', return_value=True),
              patch.object(fl, 'heic_keep_originals_enabled', return_value=True),
              patch.object(fl, 'faces_auto_index_enabled', return_value=False),
              patch.object(fl, 'ai_auto_ingest_enabled', return_value=False),
              patch.object(fl, 'ai_desc_auto_ingest_enabled', return_value=False),
              patch.object(fl, '_convert_on_local_storage') as converter):
            result = fl._recover_pending_uploads([source])
        self.assertEqual(result['errors'], 0)
        self.assertEqual(result['remaining'], 0)
        converter.assert_not_called()
        self.assertFalse(local.exists())
        self.assertTrue((fl.UPLOAD_DIR / source.removeprefix('uploads/')).is_file())
        with fl.closing(fl.get_conn()) as conn:
            row = conn.execute('SELECT uploaded_by,thumb_name FROM photos WHERE rel_path=?', (target,)).fetchone()
        self.assertEqual(row['uploaded_by'], 'Anna')
        self.assertTrue(row['thumb_name'])
        self.assertEqual(list(output.parent.iterdir()), [output])
