import unittest
from unittest.mock import patch
import app as fl
import test_manager_role as fixtures
from hub_session_guard import HubAccessSnapshot, HubAccessUnavailable


class HubSessionRevocationTests(unittest.TestCase):
    setUpBase = fixtures.ManagerRoleTests.setUp
    tearDownBase = fixtures.ManagerRoleTests.tearDown
    client = fixtures.ManagerRoleTests.client

    def setUp(self):
        self.setUpBase()
        self.users = [{'id':77, 'username':'user', 'role':'user'}]
        with fl.closing(fl.get_conn()) as conn:
            conn.execute('UPDATE users SET hub_user_id=77 WHERE id=3')
            fl._set_user_allowed_folders(conn,3,[{'folder_path':'uploads/private','permission':'view'}])
            conn.commit()
        self.patches = [patch.object(fl,'_FJORDHUB_URL','http://hub.test'), patch.object(fl,'_FJORDHUB_API_KEY','test-only'),
                        patch.object(fl,'_hub_api',side_effect=self.hub)]
        for p in self.patches: p.start()
        fl.app.extensions['hub_session_snapshot'].expires = 0

    def tearDown(self):
        for p in reversed(self.patches): p.stop()
        fl.app.extensions['hub_session_snapshot'].expires = 0
        self.tearDownBase()

    def hub(self, path, payload=None, method='POST'):
        if path == '/api/hub/apps/users': return {'ok':True,'items':self.users}
        if path == '/api/hub/sso-verify' and self.users: return dict(self.users[0],ok=True)
        return {'ok':False}

    def test_revocation_blocks_api_media_and_other_sessions_then_allows_fresh_login_after_regrant(self):
        first, second = self.client(3), self.client(3)
        self.assertEqual(first.get('/api/photos').status_code,200)
        self.users = []
        fl.app.extensions['hub_session_snapshot'].expires = 0
        denied = first.post('/api/photos/delete',json={'photo_ids':[1]})
        self.assertEqual(denied.status_code,401)
        self.assertEqual(denied.json['error_code'],'access_revoked')
        self.assertTrue((fl.UPLOAD_DIR/'originals/private/a.jpg').exists())
        self.assertEqual(second.get('/api/auth/access').json['error_code'],'access_revoked')
        self.assertEqual(first.get('/api/auth/access').json['error_code'],'access_revoked')
        self.assertEqual(self.client(3).get('/api/viewable/uploads/originals/private/a.jpg').status_code,401)
        self.assertEqual(first.get('/hub-login?token=denied').location,'/login')
        self.users = [{'id':77,'username':'user','role':'user'}]
        fl.app.extensions['hub_session_snapshot'].expires = 0
        self.assertEqual(first.get('/hub-login?token=fresh').status_code,302)
        self.assertEqual(first.get('/api/me').status_code,200)

    def test_hub_outage_blocks_requests_without_reporting_revocation_or_destroying_session(self):
        user=self.client(3)
        with patch.object(fl,'_hub_api',return_value={'ok':False}):
            result=user.get('/api/photos')
            self.assertEqual(result.status_code,503)
            self.assertEqual(result.json['error_code'],'hub_unavailable')
            with user.session_transaction() as session: self.assertEqual(session['_user_id'],'3')
        self.assertEqual(user.get('/api/auth/access').json['authenticated'],True)

    def test_valid_empty_membership_is_different_from_transport_failure_and_cache_is_bounded(self):
        now=[1.0]; users=[{'id':77,'username':'user'}]; calls=[]
        snapshot=HubAccessSnapshot(lambda *a,**k: calls.append(1) or {'ok':True,'items':list(users)},clock=lambda:now[0])
        self.assertIsNotNone(snapshot.member({'id':77}))
        users.clear(); now[0]=5.9
        self.assertIsNotNone(snapshot.member({'id':77}))
        now[0]=6.0
        self.assertIsNone(snapshot.member({'id':77}))
        self.assertEqual(len(calls),2)
        snapshot.call=lambda *a,**k:{'ok':False}; now[0]=11
        with self.assertRaises(HubAccessUnavailable): snapshot.member({'id':77})
