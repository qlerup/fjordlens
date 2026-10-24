import json
from unittest.mock import patch

import pytest
import app as fl
import photo_move
import test_folder_move as folder_tests


@pytest.fixture
def setup():
    fixture = folder_tests.FolderMoveTests()
    fixture.setUp()
    # JPEGs are not conversion source formats. Describe this legacy pair with
    # explicit links, as real indexed converted media do.
    with fl.closing(fl.get_conn()) as conn:
        conn.execute('UPDATE photos SET metadata_json=? WHERE id=?',
                     (json.dumps({'conversion': {
                         'from_rel_path': 'uploads/originals/Old/Album/Nested/file.jpg',
                         'to_rel_path': 'uploads/converted/Old/Album/Nested/file.jpg',
                     }}), fixture.photo_id))
        conn.commit()
    with patch.object(fl, '_current_user_folder_permission_for_rel', lambda rel, conn=None: 'edit'):
        yield fixture
    fixture.tearDown()


def move(ids, parent='New', new_name=''):
    with fl.app.test_request_context('/api/photos/move', method='POST', json=dict(photo_ids=ids, parent=parent, new_name=new_name)):
        result = photo_move.move_selected(fl)
        if isinstance(result, tuple):
            return result[1], result[0].get_json()
        return result.status_code, result.get_json()


def test_selected_moves_original_and_converted_preserving_id_and_metadata(setup):
    before = 'uploads/originals/Old/Album/Nested/file.jpg'
    converted = 'uploads/converted/Old/Album/Nested/file.jpg'
    with fl.closing(fl.get_conn()) as conn:
        conn.execute('UPDATE photos SET metadata_json=?,favorite=1 WHERE id=?',
                     (json.dumps({'conversion': {'from_rel_path': before, 'to_rel_path': converted}, 'caption': 'Keep me'}), setup.photo_id))
        conn.commit()
    status, data = move([setup.photo_id], '', 'New album')
    assert status == 200, data
    assert data['moved'] == 1 and data['moved_files'] == 2
    for kind in ('originals', 'converted'):
        assert (fl.UPLOAD_DIR/kind/'New album/file.jpg').read_bytes() == kind.encode()
        assert not (fl.UPLOAD_DIR/kind/'Old/Album/Nested/file.jpg').exists()
    with fl.closing(fl.get_conn()) as conn:
        row = conn.execute('SELECT * FROM photos WHERE id=?', (setup.photo_id,)).fetchone()
        assert row['rel_path'] == 'uploads/originals/New album/file.jpg' and row['favorite'] == 1
        metadata = json.loads(row['metadata_json'])
        assert metadata['caption'] == 'Keep me'
        assert metadata['conversion']['to_rel_path'] == 'uploads/converted/New album/file.jpg'
        assert conn.execute("SELECT 1 FROM folder_index WHERE path='New album'").fetchone()


def test_conflict_auto_renames_pair_and_keeps_existing_bytes(setup):
    for kind in ('originals', 'converted'):
        dest = fl.UPLOAD_DIR/kind/'New'; dest.mkdir()
        (dest/'file.jpg').write_bytes(b'existing')
        (dest/'file (2).jpg').write_bytes(b'existing two')
    status, data = move([setup.photo_id])
    assert status == 200, data
    assert data['renamed'] == 1
    for kind in ('originals', 'converted'):
        assert (fl.UPLOAD_DIR/kind/'New/file.jpg').read_bytes() == b'existing'
        assert (fl.UPLOAD_DIR/kind/'New/file (2).jpg').read_bytes() == b'existing two'
        assert (fl.UPLOAD_DIR/kind/'New/file (3).jpg').read_bytes() == kind.encode()
    with fl.closing(fl.get_conn()) as conn:
        assert conn.execute('SELECT filename FROM photos WHERE id=?', (setup.photo_id,)).fetchone()[0] == 'file (3).jpg'


def test_same_names_in_selection_both_moved(setup):
    path = fl.UPLOAD_DIR/'originals/Other'; path.mkdir()
    (path/'file.jpg').write_bytes(b'other')
    with fl.closing(fl.get_conn()) as conn:
        cursor = conn.execute("INSERT INTO photos(rel_path,filename,ext) VALUES('uploads/originals/Other/file.jpg','file.jpg','.jpg')")
        second = cursor.lastrowid; conn.commit()
    status, data = move([setup.photo_id, second])
    assert status == 200, data
    assert data['moved'] == 2 and data['renamed'] == 1
    assert {p.read_bytes() for p in (fl.UPLOAD_DIR/'originals/New').glob('*.jpg')} == {b'originals', b'other'}


@pytest.mark.parametrize('parent,name', [('../outside',''), ('originals',''), ('New','../outside')])
def test_bad_paths_do_not_change_files(setup, parent, name):
    assert move([setup.photo_id], parent, name)[0] == 400
    assert (fl.UPLOAD_DIR/'originals/Old/Album/Nested/file.jpg').exists()


def test_all_permissions_checked_before_moving_and_private_stays_private(setup):
    with patch.object(fl, '_current_user_folder_permission_for_rel', lambda rel, conn=None: 'view' if '/New' in rel else 'edit'):
        assert move([setup.photo_id])[0] == 403
    with fl.closing(fl.get_conn()) as conn:
        conn.execute("INSERT INTO private_folders VALUES ('Old')"); conn.commit()
    assert move([setup.photo_id])[0] == 409
    assert (fl.UPLOAD_DIR/'originals/Old/Album/Nested/file.jpg').exists()
    with fl.closing(fl.get_conn()) as conn:
        conn.execute("INSERT INTO private_folders VALUES ('New')"); conn.commit()
    assert move([setup.photo_id])[0] == 200


def test_partial_disk_failure_rolls_back_files_and_db(setup):
    original_move = photo_move.move_file
    calls = []
    def fail_second(source, target):
        calls.append(source)
        if len(calls) == 2:
            raise OSError('test disk failure')
        original_move(source, target)
    with patch.object(photo_move, 'move_file', fail_second):
        assert move([setup.photo_id])[0] == 500
    for kind in ('originals', 'converted'):
        assert (fl.UPLOAD_DIR/kind/'Old/Album/Nested/file.jpg').read_bytes() == kind.encode()
        assert not (fl.UPLOAD_DIR/kind/'New').exists()
    with fl.closing(fl.get_conn()) as conn:
        assert '/Old/' in conn.execute('SELECT rel_path FROM photos WHERE id=?', (setup.photo_id,)).fetchone()[0]


def test_new_folder_name_conflict_and_active_upload_stop_before_moving(setup):
    (fl.UPLOAD_DIR/'originals/New').mkdir()
    assert move([setup.photo_id], '', 'New')[0] == 409
    with patch.object(fl, '_any_upload_transfer_active', lambda: True):
        assert move([setup.photo_id])[0] == 409


def test_database_failure_rolls_back_paths_and_file_moves(setup):
    with patch.object(fl.folder_index, 'ensure_path', side_effect=RuntimeError('test database failure')):
        assert move([setup.photo_id])[0] == 500
    for kind in ('originals', 'converted'):
        assert (fl.UPLOAD_DIR/kind/'Old/Album/Nested/file.jpg').exists()
        assert not (fl.UPLOAD_DIR/kind/'New').exists()
    with fl.closing(fl.get_conn()) as conn:
        assert '/Old/' in conn.execute('SELECT rel_path FROM photos WHERE id=?', (setup.photo_id,)).fetchone()[0]


def test_exclusive_destination_keeps_concurrent_file(tmp_path):
    source, target = tmp_path/'source.jpg', tmp_path/'target.jpg'
    source.write_bytes(b'source'); target.write_bytes(b'target')
    with pytest.raises(FileExistsError):
        photo_move.move_file(source, target)
    assert source.read_bytes() == b'source' and target.read_bytes() == b'target'
