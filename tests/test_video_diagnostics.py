import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

import app as core
import test_video_autoplay_settings as fixtures


class VideoDiagnosticsTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.VideoAutoplaySettingsTests()
        self.fixture.setUp()
        self.client = self.fixture._authenticated_client()
        with core.closing(core.get_conn()) as conn:
            conn.execute("INSERT INTO photos(id,rel_path,filename,ext) VALUES(1,?,?,?)",
                         ('uploads/originals/album/a.mp4', 'a.mp4', '.mp4'))
            conn.execute("INSERT INTO photos(id,rel_path,filename,ext) VALUES(2,?,?,?)",
                         ('uploads/originals/elsewhere/b.mp4', 'b.mp4', '.mp4'))
            conn.commit()
        self.log = patch.object(core, 'log_event').start()
        self.addCleanup(patch.stopall)
        self.addCleanup(self.fixture.tearDown)

    def test_records_browser_error_with_authorized_path_and_bounded_fields(self):
        response = self.client.post('/api/media/playback-error/1', json={
            'code': 3, 'message': 'x' * 1000, 'network_state': 3, 'ready_state': 0,
            'http_status': 200, 'content_type': 'video/mp4',
            'url': '/api/share/SECRET/view/1', 'rel_path': 'forged.mp4',
        })
        self.assertEqual(response.status_code, 200)
        data = self.log.call_args.kwargs
        self.assertEqual(data['rel_path'], 'uploads/originals/album/a.mp4')
        self.assertEqual(data['error'], 'video_playback: decode')
        self.assertEqual(data['playback']['http_status'], 200)
        self.assertEqual(len(data['playback']['message']), 300)
        self.assertNotIn('SECRET', str(data))

    def test_login_and_file_access_are_required(self):
        self.assertEqual(core.app.test_client().post('/api/media/playback-error/1', json={'code': 3}).status_code, 401)
        with patch.object(core, '_is_rel_path_allowed_for_current_user', return_value=False):
            self.assertEqual(self.client.post('/api/media/playback-error/1', json={'code': 3}).status_code, 404)
        self.log.assert_not_called()

    def test_invalid_payloads_are_rejected(self):
        for body in ([], {}, {'code': True}, {'code': 5}, {'code': '3'}):
            with self.subTest(body=body):
                self.assertEqual(self.client.post('/api/media/playback-error/1', json=body).status_code, 400)
        self.log.assert_not_called()

    def test_video_response_supports_initial_range_seek_and_head(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / 'originals/album/a.mp4'
            path.parent.mkdir(parents=True)
            path.write_bytes(b'0123456789')
            with patch.object(core, 'UPLOAD_DIR', root):
                for span, expected in (('0-1', b'01'), ('5-9', b'56789')):
                    response = self.client.get('/api/viewable/uploads/originals/album/a.mp4',
                                               headers={'Range': f'bytes={span}'})
                    self.assertEqual(response.status_code, 206)
                    self.assertEqual(response.data, expected)
                    self.assertEqual(response.mimetype, 'video/mp4')
                    self.assertEqual(response.headers['Content-Range'], f'bytes {span}/10')
                    response.close()
                response = self.client.head('/api/viewable/uploads/originals/album/a.mp4')
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.data, b'')
                self.assertEqual(response.content_length, 10)
                response.close()

    def test_share_report_is_scoped_to_authorized_share(self):
        token = self.fixture._add_share()
        client = core.app.test_client()
        self.assertEqual(client.post('/api/share/invalid/playback-error/1', json={'code': 3}).status_code, 403)
        self.assertEqual(client.post(f'/api/share/{token}/playback-error/2', json={'code': 3}).status_code, 404)
        self.log.assert_not_called()
        self.assertEqual(client.post(f'/api/share/{token}/playback-error/1', json={
            'code': 4, 'message': f'Failed to open /api/share/{token}/view/1',
        }).status_code, 200)
        self.assertEqual(self.log.call_args.kwargs['error'], 'video_playback: source_not_supported')
        self.assertNotIn(token, str(self.log.call_args.kwargs))
