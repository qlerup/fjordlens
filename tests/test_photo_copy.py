import json
import os
from pathlib import Path
from unittest.mock import patch

from PIL import Image
import pytest
import app as fl
import photo_copy
import test_folder_move as folder_tests


@pytest.fixture
def setup():
    fixture = folder_tests.FolderMoveTests()
    fixture.setUp()
    with (patch.object(fl, 'CONVERSION_WORK_DIR', Path(fixture.temp.name)/'conversion_work'),
          patch.object(fl, '_current_user_folder_permission_for_rel', lambda rel, conn=None: 'edit'),
          patch.object(fl, '_queue_uploaded_rel') as queue,
          patch.object(fl, '_ensure_upload_postprocess_running', return_value=True) as start):
        fixture.queue, fixture.start = queue, start
        yield fixture
    fixture.tearDown()


def copy(ids, parent='New', new_name=''):
    with fl.app.test_request_context('/api/photos/copy', method='POST', json=dict(photo_ids=ids, parent=parent, new_name=new_name)):
        result = fl.api_copy_photos.__wrapped__()
        if isinstance(result, tuple):
            return result[1], result[0].get_json()
        return result.status_code, result.get_json()


def pair(fixture):
    original = 'uploads/originals/Old/Album/Nested/photo.HEIC'
    converted = 'uploads/converted/Old/Album/Nested/photo_2.jpg'
    for rel in (original, converted):
        path = fl.UPLOAD_DIR / rel.removeprefix('uploads/')
        path.write_bytes(rel.encode())
    metadata = {'conversion': {'from_rel_path': original, 'to_rel_path': converted, 'converted_at': '2025-01-02'},
                'converted_from_rel': original}
    with fl.closing(fl.get_conn()) as conn:
        conn.execute('UPDATE photos SET rel_path=?,filename=?,metadata_json=?,favorite=1,captured_at=? WHERE id=?',
                     (converted, 'photo_2.jpg', json.dumps(metadata), '2020-02-03T04:05:06', fixture.photo_id))
        conn.commit()
    return original, converted


def test_copies_pair_with_new_ids_and_preserves_source_bytes_and_dates(setup):
    original, converted = pair(setup)
    for rel in (original, converted):
        os.utime(fl._disk_path_from_rel_path(rel), (1000000000, 1000000000))
    status, data = copy([setup.photo_id], '', 'New album')
    assert status == 200, data
    assert data['copied'] == 1 and data['copied_files'] == 2
    assert data['photo_ids'] != [setup.photo_id]
    for rel in (original, converted):
        source = fl._disk_path_from_rel_path(rel)
        target = fl.UPLOAD_DIR / ('originals' if rel == original else 'converted') / 'New album' / Path(rel).name
        assert source.read_bytes() == target.read_bytes() == rel.encode()
        assert target.stat().st_mtime == source.stat().st_mtime
        assert target.stat().st_ino != source.stat().st_ino
    with fl.closing(fl.get_conn()) as conn:
        row = conn.execute('SELECT * FROM photos WHERE id=?', (data['photo_ids'][0],)).fetchone()
        assert row['thumb_name'] is None and row['checksum_sha256'] is None
        assert row['favorite'] == 1
        assert row['captured_at'] == '2020-02-03T04:05:06'
        metadata = json.loads(row['metadata_json'])
        assert metadata['conversion']['from_rel_path'] == 'uploads/originals/New album/photo.HEIC'
        assert metadata['conversion']['to_rel_path'] == row['rel_path']
        assert metadata['conversion']['converted_at'] == '2025-01-02'
        assert conn.execute('SELECT rel_path FROM photos WHERE id=?', (setup.photo_id,)).fetchone()[0] == converted
    setup.queue.assert_called_once_with('test', row['rel_path'])
    setup.start.assert_called_once_with('test')


def test_pair_is_renamed_together_when_either_variant_or_staging_conflicts(setup):
    original, converted = pair(setup)
    existing = fl.UPLOAD_DIR/'originals/New/photo.HEIC'
    existing.parent.mkdir(parents=True)
    existing.write_bytes(b'existing')
    staged = fl._staged_upload_path('uploads/originals/New/photo_1.HEIC')
    staged.parent.mkdir(parents=True)
    staged.write_bytes(b'staged')
    status, data = copy([setup.photo_id])
    assert status == 200, data
    assert data['renamed'] == 1
    assert (fl.UPLOAD_DIR/'originals/New/photo_2.HEIC').read_bytes() == original.encode()
    assert (fl.UPLOAD_DIR/'converted/New/photo_2_2.jpg').read_bytes() == converted.encode()
    assert existing.read_bytes() == b'existing' and staged.read_bytes() == b'staged'


def test_same_folder_and_same_names_in_selection_are_independent_copies(setup):
    source = fl.UPLOAD_DIR/'originals/Other/file.jpg'
    source.parent.mkdir(); source.write_bytes(b'other')
    with fl.closing(fl.get_conn()) as conn:
        second = conn.execute("INSERT INTO photos(rel_path,filename) VALUES('uploads/originals/Other/file.jpg','file.jpg')").lastrowid
        conn.commit()
    status, data = copy([setup.photo_id, second], 'Old/Album/Nested')
    assert status == 200, data
    assert data['copied'] == 2 and data['renamed'] == 2
    dest = fl.UPLOAD_DIR/'originals/Old/Album/Nested'
    assert (dest/'file.jpg').read_bytes() == b'originals'
    assert {(dest/'file_1.jpg').read_bytes(), (dest/'file_2.jpg').read_bytes()} == {b'originals', b'other'}


def test_original_is_optional_if_previous_conversion_deleted_it(setup):
    original, converted = pair(setup)
    fl._disk_path_from_rel_path(original).unlink()
    status, data = copy([setup.photo_id])
    assert status == 200, data
    assert data['copied_files'] == 1
    assert fl._disk_path_from_rel_path(converted).exists()


@pytest.mark.parametrize('parent,name', [('../escape', ''), ('originals', ''), ('New', '../escape')])
def test_invalid_paths_leave_source_untouched(setup, parent, name):
    assert copy([setup.photo_id], parent, name)[0] == 400
    assert (fl.UPLOAD_DIR/'originals/Old/Album/Nested/file.jpg').exists()
    setup.start.assert_not_called()


def test_requires_source_read_and_destination_upload_and_private_destination(setup):
    with patch.object(fl, '_current_user_folder_permission_for_rel', lambda rel, conn=None: 'view'):
        assert copy([setup.photo_id])[0] == 403
    with patch.object(fl, '_current_user_folder_permission_for_rel', lambda rel, conn=None: None if '/Old/' in rel else 'edit'):
        assert copy([setup.photo_id])[0] == 403
    with patch.object(fl, '_current_user_folder_permission_for_rel', lambda rel, conn=None: 'upload' if rel == 'uploads/New' else 'view'):
        assert copy([setup.photo_id])[0] == 200
    with fl.closing(fl.get_conn()) as conn:
        conn.execute("INSERT INTO private_folders VALUES ('Old')"); conn.commit()
    assert copy([setup.photo_id], 'Public')[0] == 409
    with fl.closing(fl.get_conn()) as conn:
        conn.execute("INSERT INTO private_folders VALUES ('Private')"); conn.commit()
    assert copy([setup.photo_id], 'Private')[0] == 200


def test_partial_copy_and_database_failures_rollback_only_new_files(setup):
    pair(setup)
    real_copy = photo_copy.copy_file
    calls = []
    def fail_second(source, target):
        calls.append(target)
        if len(calls) == 2:
            raise OSError('disk full')
        real_copy(source, target)
    with patch.object(photo_copy, 'copy_file', fail_second):
        assert copy([setup.photo_id])[0] == 500
    assert not (fl.UPLOAD_DIR/'originals/New').exists()
    assert not (fl.UPLOAD_DIR/'converted/New').exists()
    with patch.object(fl.folder_index, 'ensure_path', side_effect=RuntimeError('database failure')):
        assert copy([setup.photo_id])[0] == 500
    with fl.closing(fl.get_conn()) as conn:
        assert conn.execute('SELECT COUNT(*) FROM photos').fetchone()[0] == 1
    assert not (fl.UPLOAD_DIR/'originals/New').exists()
    assert not (fl.UPLOAD_DIR/'converted/New').exists()
    setup.start.assert_not_called()


def test_exclusive_copy_preserves_concurrent_file(tmp_path):
    source, target = tmp_path/'source', tmp_path/'target'
    source.write_bytes(b'source'); target.write_bytes(b'target')
    with pytest.raises(FileExistsError): photo_copy.copy_file(source, target)
    assert source.read_bytes() == b'source' and target.read_bytes() == b'target'


def test_symlinks_missing_sources_busy_and_duplicate_ids(setup, tmp_path):
    with patch.object(fl, '_any_upload_transfer_active', return_value=True):
        assert copy([setup.photo_id])[0] == 409
    (fl.UPLOAD_DIR/'originals/Link').symlink_to(tmp_path, target_is_directory=True)
    assert copy([setup.photo_id], 'Link')[0] == 400
    assert copy([999999])[0] == 404
    assert copy([setup.photo_id, setup.photo_id])[1]['copied'] == 1
    (fl.UPLOAD_DIR/'originals/Old/Album/Nested/file.jpg').unlink()
    assert copy([setup.photo_id])[0] == 404


def test_postprocess_failure_keeps_recoverable_committed_copy(setup):
    setup.start.side_effect = RuntimeError('worker unavailable')
    status, data = copy([setup.photo_id])
    assert status == 200 and data['postprocess_pending']
    assert (fl.UPLOAD_DIR/'originals/New/file.jpg').exists()
    assert fl._recover_uploaded_rels_missing_postprocess('test') == ['uploads/originals/New/file.jpg']


def test_full_pipeline_reindexes_converted_copy_without_conversion_or_deleting_original(setup):
    original, converted = pair(setup)
    Image.new('RGB', (24, 16), 'blue').save(fl._disk_path_from_rel_path(converted))
    status, data = copy([setup.photo_id])
    assert status == 200, data
    rel = 'uploads/converted/New/photo_2.jpg'
    with (patch.object(fl, 'faces_auto_index_enabled', return_value=True),
          patch.object(fl, 'ai_auto_ingest_enabled', return_value=True),
          patch.object(fl, 'ai_desc_auto_ingest_enabled', return_value=True),
          patch.object(fl, '_run_face_slot_queue', return_value={}) as faces,
          patch.object(fl, '_embed_uploaded_photo_if_needed') as embeddings,
          patch.object(fl, '_describe_uploaded_photo_if_needed') as descriptions,
          patch.object(fl, '_convert_on_local_storage') as convert):
        result = fl._postprocess_uploaded_rels('test', [rel], workflow_mode='gentle')
    assert result['indexed'] == 1 and result['index_errors'] == 0, result
    convert.assert_not_called()
    faces.assert_called_once()
    embeddings.assert_called_once()
    descriptions.assert_called_once()
    with fl.closing(fl.get_conn()) as conn:
        row = conn.execute('SELECT * FROM photos WHERE id=?', (data['photo_ids'][0],)).fetchone()
        metadata = json.loads(row['metadata_json'])
        assert metadata['conversion']['from_rel_path'] == 'uploads/originals/New/photo.HEIC'
        assert metadata['conversion']['to_rel_path'] == rel
        assert row['captured_at'] == '2020-02-03T04:05:06'
        assert row['checksum_sha256'] and row['thumb_name']
        assert (fl.THUMB_DIR/row['thumb_name']).exists()
    assert (fl.UPLOAD_DIR/'originals/New/photo.HEIC').read_bytes() == original.encode()
