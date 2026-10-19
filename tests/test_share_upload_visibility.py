"""Visibility applies to gallery, direct files, uploads and existing share edits."""
import io
import unittest
from unittest.mock import patch
from PIL import Image
from werkzeug.security import generate_password_hash
import app as lens
import test_download_dates_and_share_permissions as fixtures


class ShareUploadVisibilityTests(unittest.TestCase):
    setUp = fixtures.DownloadDatesAndSharePermissionsTests.setUp
    tearDown = fixtures.DownloadDatesAndSharePermissionsTests.tearDown
    _add_jpeg = fixtures.DownloadDatesAndSharePermissionsTests._add_jpeg
    _add_share = fixtures.DownloadDatesAndSharePermissionsTests._add_share

    def _prepare(self):
        own, _ = self._add_jpeg('album','mine.jpg')
        other, _ = self._add_jpeg('album','theirs.jpg')
        nested, _ = self._add_jpeg('album/secret','hidden.jpg')
        self._add_share('private-link','album',can_upload=1,can_delete=1)
        guest = lens.app.test_client()
        self.assertEqual(guest.get('/api/share/private-link/info').status_code,200)
        with guest.session_transaction() as session:
            owner = session['share_visitor_id']
        with lens.closing(lens.get_conn()) as db:
            db.execute('UPDATE share_links SET show_others_uploads=0')
            db.execute('UPDATE photos SET share_visitor_id=? WHERE id=?',(owner,own))
            db.execute('UPDATE photos SET share_visitor_id=? WHERE id IN (?,?)',('someone-else',other,nested))
            db.commit()
        return guest, own, other

    def test_gallery_direct_files_zip_and_delete_reject_other_visitors(self):
        guest, own, other = self._prepare()
        with patch.object(lens,'_sync_upload_folder_from_disk'):
            response = guest.get('/api/share/private-link/photos')
        result = response.get_json()
        self.assertEqual([r['id'] for r in result['items']],[own])
        self.assertEqual(result['total'],1)
        self.assertEqual(result['folders'],[])
        self.assertNotIn('share_visitor_id',result['items'][0])
        self.assertIn('no-store',response.headers['Cache-Control'])
        for endpoint in ('thumb','original','view','download'):
            self.assertEqual(guest.get(f'/api/share/private-link/{endpoint}/{other}').status_code,404)
        response = guest.get(f'/api/share/private-link/original/{own}')
        self.assertEqual(response.status_code,200)
        response.close()
        with patch.object(lens,'_send_photos_download_zip',return_value={"ok":True}) as zipped:
            guest.post('/api/share/private-link/download-zip',json={'photo_ids':[own,other]})
            self.assertEqual([r['id'] for r in zipped.call_args.args[0]],[own])
        guest.post('/api/share/private-link/delete',json={'photo_ids':[other]})
        with lens.closing(lens.get_conn()) as db:
            self.assertIsNotNone(db.execute('SELECT id FROM photos WHERE id=?',(other,)).fetchone())
        second = lens.app.test_client()
        with second.session_transaction() as session:
            session['share_name_1']='Same name'
        with patch.object(lens,'_sync_upload_folder_from_disk'):
            self.assertEqual(second.get('/api/share/private-link/photos').get_json()['items'],[])

    def test_logged_in_user_requires_folder_permission_and_admin_retains_access(self):
        guest, own, other = self._prepare()
        with lens.closing(lens.get_conn()) as db:
            db.execute('INSERT INTO users(username,password_hash,is_admin,role,created_at) VALUES(?,?,?,?,?)',
                       ('reader',generate_password_hash('test-password'),0,'user',lens.now_iso()))
            db.commit()
        with guest.session_transaction() as session:
            session['_user_id']='2'
            session['_fresh']=True
        self.assertEqual(guest.get(f'/api/share/private-link/original/{other}').status_code,404)
        with lens.closing(lens.get_conn()) as db:
            db.execute('INSERT INTO user_folder_access(user_id,folder_path,created_at) VALUES(?,?,?)',
                       (2,'album',lens.now_iso()))
            db.commit()
        response = guest.get(f'/api/share/private-link/original/{other}')
        self.assertEqual(response.status_code,200)
        response.close()
        response = self.client.get(f'/api/share/private-link/original/{other}')
        self.assertEqual(response.status_code,200)
        response.close()

    def test_toggle_creation_edit_existing_and_preserve_if_omitted(self):
        (lens.UPLOAD_DIR/'originals'/'album').mkdir(parents=True)
        payload={'folder_paths':['album'],'permission':'upload','expires_value':0,'show_others_uploads':False}
        created=self.client.post('/api/shares',json=payload)
        self.assertEqual(created.status_code,200)
        self.assertIs(created.get_json()['show_others_uploads'],False)
        items=self.client.get('/api/admin/shares?include_inactive=1').get_json()['items']
        item=items[0]
        self.assertIs(item['show_others_uploads'],False)
        sid=item['id']
        payload.pop('show_others_uploads')
        response=self.client.put(f'/api/admin/shares/{sid}',json=payload)
        self.assertIs(response.get_json()['show_others_uploads'],False)
        for enabled in (True,False):
            payload['show_others_uploads']=enabled
            response=self.client.put(f'/api/admin/shares/{sid}',json=payload)
            self.assertEqual(response.status_code,200)
            self.assertIs(response.get_json()['show_others_uploads'],enabled)
        payload['show_others_uploads']='false'
        self.assertEqual(self.client.put(f'/api/admin/shares/{sid}',json=payload).status_code,400)

    def test_switch_existing_link_takes_effect_immediately(self):
        guest, own, other=self._prepare()
        for enabled in (True,False):
            response=self.client.put('/api/admin/shares/1',json={'folder_paths':['album'],'permission':'manage',
                                     'expires_value':0,'show_others_uploads':enabled})
            self.assertEqual(response.status_code,200)
            with patch.object(lens,'_sync_upload_folder_from_disk'):
                items=guest.get('/api/share/private-link/photos').get_json()['items']
            self.assertEqual({r['id'] for r in items},{own,other} if enabled else {own})
            response=guest.get(f'/api/share/private-link/original/{other}')
            self.assertEqual(response.status_code,200 if enabled else 404)
            response.close()

    def test_multipart_upload_records_session_owner(self):
        guest, own, other=self._prepare()
        image=io.BytesIO();Image.new('RGB',(12,12)).save(image,'JPEG');image.seek(0)
        with patch.object(lens,'_ensure_upload_postprocess_running'), patch.object(lens,'_queue_uploaded_rel'):
            response=guest.post('/api/share/private-link/upload',data={'files':(image,'fresh.jpg')},content_type='multipart/form-data')
        self.assertEqual(response.status_code,200,response.get_json())
        with guest.session_transaction() as session:
            owner=session['share_visitor_id']
        with lens.closing(lens.get_conn()) as db:
            row=db.execute("SELECT share_visitor_id FROM photos WHERE filename='fresh.jpg'").fetchone()
        self.assertEqual(row['share_visitor_id'],owner)
        with patch.object(lens,'_sync_upload_folder_from_disk'):
            names={r['filename'] for r in guest.get('/api/share/private-link/photos').get_json()['items']}
        self.assertIn('fresh.jpg',names)
        self.assertNotIn('theirs.jpg',names)

    def test_schema_upgrade_preserves_existing_behavior_and_is_repeatable(self):
        self._add_jpeg('album','old.jpg')
        self._add_share('old-link','album')
        lens.init_db();lens.init_db()
        with lens.closing(lens.get_conn()) as db:
            self.assertEqual(db.execute('SELECT show_others_uploads FROM share_links').fetchone()[0],1)

    def test_tus_upload_owner_persists_and_other_browser_cannot_resume(self):
        import base64
        guest, own, other=self._prepare()
        content=io.BytesIO();Image.new('RGB',(12,12)).save(content,'JPEG');data=content.getvalue()
        headers={'Tus-Resumable':'1.0.0','Upload-Length':str(len(data)),
                 'Upload-Metadata':'filename '+base64.b64encode(b'tus.jpg').decode()}
        created=guest.post('/api/share/private-link/upload/tus',headers=headers)
        self.assertEqual(created.status_code,201)
        location=created.headers['Location']
        stranger=lens.app.test_client()
        self.assertEqual(stranger.head(location,headers={'Tus-Resumable':'1.0.0'}).status_code,403)
        with patch.object(lens,'_queue_uploaded_rel'):
            response=guest.patch(location,data=data,headers={'Tus-Resumable':'1.0.0','Upload-Offset':'0',
                                 'Content-Type':'application/offset+octet-stream'})
        self.assertEqual(response.status_code,204)
        with guest.session_transaction() as session:
            owner=session['share_visitor_id']
        with lens.closing(lens.get_conn()) as db:
            row=db.execute("SELECT share_visitor_id FROM photos WHERE filename='tus.jpg'").fetchone()
        self.assertEqual(row['share_visitor_id'],owner)

    def test_metadata_conversion_preserves_ownership(self):
        guest, own, other=self._prepare()
        source='uploads/originals/album/mine.jpg'
        converted=lens.UPLOAD_DIR/'converted/album/mine.jpg'
        converted.parent.mkdir(parents=True,exist_ok=True)
        Image.new('RGB',(12,12)).save(converted,'JPEG')
        rel='uploads/converted/album/mine.jpg'
        meta=lens.extract_metadata(converted,rel,generate_thumb=False)
        lens._attach_conversion_metadata(meta,from_rel_path=source,to_rel_path=rel,from_ext='.jpg',to_ext='.jpg')
        lens.upsert_photo(meta)
        with lens.closing(lens.get_conn()) as db:
            rows=db.execute('SELECT share_visitor_id FROM photos WHERE rel_path IN (?,?)',(source,rel)).fetchall()
        self.assertEqual(len(rows),2)
        self.assertTrue(rows[0][0])
        self.assertEqual(rows[0][0],rows[1][0])

    def test_converted_download_fallback_cannot_expose_another_visitors_file(self):
        guest, own, other=self._prepare()
        with lens.closing(lens.get_conn()) as db:
            row=db.execute('SELECT rel_path FROM photos WHERE id=?',(other,)).fetchone()
        others_path=lens.UPLOAD_DIR/row['rel_path'][len('uploads/'):]
        with patch.object(lens,'_resolve_download_path',return_value=others_path):
            response=guest.get(f'/api/share/private-link/download/{own}?mode=converted')
            self.assertEqual(response.status_code,404)
            response=guest.post('/api/share/private-link/download-zip',json={'photo_ids':[own],'mode':'converted'})
            self.assertEqual(response.status_code,404)

    def test_reused_upload_path_cannot_keep_previous_visitor_ownership(self):
        guest, own, other=self._prepare()
        source=lens.UPLOAD_DIR/'originals/album/mine.jpg'
        lens._upsert_uploaded_stub('uploads/originals/album/mine.jpg',source,'Normal user')
        response=guest.get(f'/api/share/private-link/original/{own}')
        self.assertEqual(response.status_code,404)
