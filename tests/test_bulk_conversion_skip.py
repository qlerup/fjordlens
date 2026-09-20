import json
import unittest
from unittest.mock import patch
import app as fl
from test_upload_conversion_uploader import UploadConversionUploaderTests


class BulkConversionSkipTests(unittest.TestCase):
    setUp = UploadConversionUploaderTests.setUp
    tearDown = UploadConversionUploaderTests.tearDown

    def file(self, rel, content=b'existing output'):
        path = fl._disk_path_from_rel_path(rel)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return path

    def indexed(self, rel, metadata=None):
        with fl.closing(fl.get_conn()) as conn:
            conn.execute('INSERT INTO photos(rel_path,filename,metadata_json) VALUES(?,?,?)',
                         (rel, fl.Path(rel).name, json.dumps(metadata or {})))
            conn.commit()

    def test_all_three_buttons_skip_existing_output_on_repeated_runs(self):
        for kind, ext, output in [('heic', '.heic', '.jpg'), ('raw', '.dng', '.jpg'), ('mov', '.mov', '.mp4')]:
            rel = f'uploads/originals/{kind}/source{ext}'
            self.file(rel)
            self.indexed(rel)
            dst = self.file(f'uploads/converted/{kind}/source{output}')
            with patch.object(fl, '_convert_on_local_storage') as convert:
                for _ in range(2):
                    result = getattr(fl, '_convert_existing_'+kind)()
                    self.assertEqual(result['processed'], 0)
                    self.assertEqual(result['skipped'], 1)
                convert.assert_not_called()
            self.assertEqual(dst.read_bytes(), b'existing output')

    def test_missing_and_empty_outputs_remain_candidates(self):
        for kind, ext, output in [('heic', '.heic', '.jpg'), ('raw', '.dng', '.jpg'), ('mov', '.mov', '.mp4')]:
            rel = f'uploads/originals/{kind}/source{ext}'
            rows = [{'rel_path': rel}]
            self.assertEqual(fl._bulk_conversion_missing_rows(rows, output), (rows, 0))
            self.file(f'uploads/converted/{kind}/source{output}', b'')
            self.assertEqual(fl._bulk_conversion_missing_rows(rows, output), (rows, 0))

    def test_linked_numbered_output_is_skipped_but_missing_linked_file_is_not(self):
        source = 'uploads/originals/Album/IMG_12.HEIC'
        target = 'uploads/converted/Album/IMG_12_2.jpg'
        self.indexed(target, {'conversion': {'from_rel_path': source, 'to_rel_path': target}})
        rows = [{'rel_path': source}]
        self.assertEqual(fl._bulk_conversion_missing_rows(rows, '.jpg'), (rows, 0))
        self.file(target)
        self.assertEqual(fl._bulk_conversion_missing_rows(rows, '.jpg'), ([], 1))

    def test_similar_names_and_outputs_linked_to_other_sources_do_not_skip(self):
        source = 'uploads/originals/Album/IMG_12.HEIC'
        target = 'uploads/converted/Album/IMG_12.jpg'
        self.file('uploads/converted/Album/IMG_12_1.jpg')
        self.file(target)
        self.indexed(target, {'conversion': {'from_rel_path': 'uploads/originals/Album/IMG_12.DNG', 'to_rel_path': target}})
        rows = [{'rel_path': source}]
        self.assertEqual(fl._bulk_conversion_missing_rows(rows, '.jpg'), (rows, 0))

    def test_missing_outputs_reach_converter(self):
        for kind, ext in [('heic', '.heic'), ('raw', '.dng'), ('mov', '.mov')]:
            rel = f'uploads/originals/{kind}/source{ext}'
            self.file(rel)
            self.indexed(rel)
            with patch.object(fl, '_convert_on_local_storage', side_effect=RuntimeError('converter reached')) as convert:
                result = getattr(fl, '_convert_existing_'+kind)()
            convert.assert_called_once()
            self.assertEqual(result['errors'], 1)
            self.assertEqual(result['skipped'], 0)

    def test_live_progress_identifies_current_file_and_counts_missing_sources(self):
        for kind, ext in [('heic', '.heic'), ('raw', '.dng'), ('mov', '.mov')]:
            rel = f'uploads/originals/{kind}/source{ext}'
            missing = f'uploads/originals/{kind}/missing{ext}'
            self.file(rel)
            self.indexed(rel)
            self.indexed(missing)
            snapshots = []
            def convert(*args, **kwargs):
                snapshots.append(dict(getattr(fl, kind + '_convert_progress')))
                raise RuntimeError('conversion failed')
            with patch.object(fl, '_convert_on_local_storage', side_effect=convert):
                result = getattr(fl, '_convert_existing_' + kind)()
            self.assertEqual(snapshots[0]['current'], rel)
            self.assertEqual(snapshots[0]['total'], 2)
            self.assertEqual(result['total'], 2)
            self.assertEqual(result['errors'], 2)
            self.assertIsNone(getattr(fl, kind + '_convert_progress')['current'])
