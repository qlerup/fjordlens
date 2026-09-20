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

    def test_scan_reports_live_counts_before_finishing(self):
        existing = 'uploads/originals/Album/ready.heic'
        missing = 'uploads/originals/Album/missing.heic'
        self.indexed(existing)
        self.file('uploads/converted/Album/ready.jpg')
        snapshots = []
        rows, skipped = fl._bulk_conversion_missing_rows(
            [{'rel_path': existing}, {'rel_path': missing}], '.jpg', snapshots.append)
        self.assertTrue(any(p['check_stage'] == 'metadata' for p in snapshots))
        scans = [p for p in snapshots if p['check_stage'] == 'files']
        self.assertEqual([p['checked'] for p in scans], [0, 1, 2])
        self.assertEqual(scans[1]['skipped'], 1)
        self.assertEqual(scans[-1]['pending'], 1)
        self.assertEqual(scans[-1]['check_total'], 2)
        self.assertEqual(skipped, 1)
        self.assertEqual(rows, [{'rel_path': missing}])

    def test_disk_discovery_deduplicates_preserves_uploader_and_excludes_generated_files(self):
        known = 'uploads/originals/nested/known.HEIC'
        orphan = 'uploads/originals/nested/unindexed.HEIF'
        legacy = 'uploads/old/legacy.heic'
        for rel in [known, orphan, legacy, 'uploads/converted/ignore.heic',
                    'uploads/originals/@eaDir/ignore.heic', 'uploads/originals/.temp.heic',
                    'uploads/originals/._resource.heic']:
            self.file(rel)
        snapshots = []
        with patch.object(fl, 'library_source_enabled', return_value=False):
            rows = fl._bulk_conversion_disk_rows(
                [{'rel_path': known, 'uploaded_by': 'Anna'}], {'.heic', '.heif'}, snapshots.append)
        self.assertEqual({r['rel_path'] for r in rows}, {known, orphan, legacy})
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0]['uploaded_by'], 'Anna')
        self.assertEqual(snapshots[-1]['added'], 2)

    def test_disk_scan_includes_library_only_when_enabled(self):
        library = fl.DATA_DIR / 'test_library'
        library.mkdir()
        (library / 'source.MOV').write_bytes(b'movie')
        with patch.object(fl, 'PHOTO_DIR', library):
            with patch.object(fl, 'library_source_enabled', return_value=False):
                self.assertEqual(fl._bulk_conversion_disk_rows([], {'.mov'}), [])
            with patch.object(fl, 'library_source_enabled', return_value=True):
                rows = fl._bulk_conversion_disk_rows([], {'.mov'})
                self.assertEqual(rows, [{'rel_path': 'source.MOV', 'uploaded_by': None}])

    def test_disk_only_originals_convert_once_and_never_duplicate_on_rerun(self):
        for kind, ext, suffix in [('heic', '.HEIC', '.jpg'), ('raw', '.DNG', '.jpg'), ('mov', '.MOV', '.mp4')]:
            rel = f'uploads/originals/{kind}/unindexed{ext}'
            source = self.file(rel)
            destination = fl.UPLOAD_DIR / 'converted' / kind / ('unindexed' + suffix)
            def convert(src, dst, *args, **kwargs):
                dst.write_bytes(b'converted data')
            def extract(path, output_rel, **kwargs):
                with fl.closing(fl.get_conn()) as conn:
                    meta = {row['name']: None for row in conn.execute('PRAGMA table_info(photos)')}
                meta.update(rel_path=output_rel, filename=path.name, ext=path.suffix,
                            file_size=path.stat().st_size, metadata_json={}, exif_json={}, ai_tags=[])
                return meta
            with (patch.object(fl, 'library_source_enabled', return_value=False),
                  patch.object(fl, kind + '_keep_originals_enabled', return_value=True),
                  patch.object(fl, '_convert_on_local_storage', side_effect=convert) as converter,
                  patch.object(fl, 'extract_metadata', side_effect=extract)):
                first = getattr(fl, '_convert_existing_' + kind)()
                self.assertEqual(first['processed'], 1)
                self.assertEqual(first['errors'], 0)
                self.assertTrue(source.exists())
                second = getattr(fl, '_convert_existing_' + kind)()
                self.assertEqual(second['processed'], 0)
                self.assertEqual(second['skipped'], 1)
                converter.assert_called_once()
            self.assertEqual(list(destination.parent.iterdir()), [destination])

    def test_disk_only_original_with_existing_output_never_reaches_converter(self):
        for kind, ext, suffix in [('heic', '.heic', '.jpg'), ('raw', '.dng', '.jpg'), ('mov', '.mov', '.mp4')]:
            self.file(f'uploads/originals/{kind}/ready{ext}')
            destination = self.file(f'uploads/converted/{kind}/ready{suffix}')
            with (patch.object(fl, 'library_source_enabled', return_value=False),
                  patch.object(fl, '_convert_on_local_storage') as converter):
                result = getattr(fl, '_convert_existing_' + kind)()
            converter.assert_not_called()
            self.assertEqual(result['skipped'], 1)
            self.assertEqual(list(destination.parent.iterdir()), [destination])

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
