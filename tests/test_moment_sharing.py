import json
import unittest
from pathlib import Path
from PIL import Image
import app
import moment_cinema
from tests import test_moments_v2 as legacy


class MomentSharingTests(unittest.TestCase):
    setUp = legacy.MomentEditingTests.setUp
    tearDown = legacy.MomentEditingTests.tearDown
    _insert_photo = legacy.MomentEditingTests._insert_photo
    make_moment = legacy.MomentEditingTests.make_moment

    def test_public_link_is_scoped_revocable_and_has_no_library_access(self):
        moment = self.make_moment()
        ids = json.loads(moment['photo_ids_json'])
        script = [dict(type='photo',photo_id=ids[0],duration=5,design_version=moment_cinema.VERSION)]
        with app.closing(app.get_conn()) as conn:
            conn.execute('UPDATE moments SET script_json=? WHERE id=?',(json.dumps(script),moment['id']))
            rel = conn.execute('SELECT rel_path FROM photos WHERE id=?',(ids[0],)).fetchone()[0]
            conn.commit()
        path = app.UPLOAD_DIR / rel.split('/',1)[1]
        path.parent.mkdir(parents=True,exist_ok=True)
        Image.new('RGB',(40,40),'red').save(path)
        response = self.client.post(f"/api/moments/{moment['id']}/share")
        self.assertEqual(response.status_code,200)
        url = response.get_json()['url']
        token = url.split('/')[-1]
        public = app.app.test_client()
        self.assertEqual(public.get(url).status_code,200)
        shared = public.get(f'/api/moment-share/{token}').get_json()['item']
        self.assertEqual(set(shared['photos']),{str(ids[0])})
        self.assertEqual(public.get(shared['photos'][str(ids[0])]['original_url']).status_code,200)
        self.assertEqual(public.get(f'/api/moment-share/{token}/media/{ids[1]}').status_code,404)
        self.assertNotEqual(public.get('/api/moments').status_code,200)
        self.assertNotEqual(public.post(f"/api/moments/{moment['id']}/share").status_code,200)
        listing = self.client.get('/api/admin/shares?include_inactive=1').get_json()['items']
        share = next(s for s in listing if s.get('kind') == 'moment')
        self.assertTrue(share['link'].endswith(url))
        self.assertTrue(share['expires_at'])
        admin_url = f"/api/admin/moment-shares/{abs(share['id'])}"
        self.assertNotEqual(public.post(admin_url+'/revoke').status_code,200)
        self.assertEqual(self.client.post(admin_url+'/revoke').status_code,200)
        self.assertEqual(public.get(url).status_code,404)
        self.assertEqual(public.get(shared['photos'][str(ids[0])]['original_url']).status_code,404)
        self.assertEqual(self.client.post(admin_url+'/activate',json={'expires_value':7}).status_code,200)
        self.assertEqual(public.get(url).status_code,200)
        with app.closing(app.get_conn()) as conn:
            conn.execute("UPDATE moment_shares SET expires_at='2000-01-01T00:00:00Z'")
            conn.commit()
        self.assertEqual(public.get(url).status_code,404)
        self.assertEqual(public.get(f'/api/moment-share/{token}').status_code,404)
        self.assertEqual(self.client.post(admin_url+'/extend',json={'expires_value':30}).status_code,200)
        self.assertEqual(public.get(url).status_code,200)
        self.assertEqual(self.client.put(admin_url,json={'share_name':'Test', 'expires_value':0}).status_code,200)
        updated = self.client.get('/api/admin/shares?include_inactive=1').get_json()['items'][0]
        self.assertEqual(updated['share_name'],'Test')
        self.assertIsNone(updated['expires_at'])
        self.assertEqual(self.client.delete(f"/api/moments/{moment['id']}/share").status_code,200)
        self.assertEqual(public.get(url).status_code,404)
        self.assertEqual(public.get(shared['photos'][str(ids[0])]['original_url']).status_code,404)
