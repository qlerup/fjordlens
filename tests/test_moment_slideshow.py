import json
import unittest
from unittest.mock import patch
import app
import moment_cinema
import moment_slideshow
from tests import test_moments_v2 as legacy


class SlideshowEditingTests(unittest.TestCase):
    setUp = legacy.MomentEditingTests.setUp
    tearDown = legacy.MomentEditingTests.tearDown
    _insert_photo = legacy.MomentEditingTests._insert_photo
    make_moment = legacy.MomentEditingTests.make_moment

    def test_saved_timeline_survives_reload_and_is_shared_with_pair_media(self):
        moment = self.make_moment()
        ids = json.loads(moment['photo_ids_json'])
        script = [dict(type='text',text='Ærø og København',duration=4.5),
                  dict(type='pair',photo_id=ids[2],second_photo_id=ids[0],duration=15,weather='Sol · 22 °C')]
        url = f"/api/moments/{moment['id']}/slideshow"
        response = self.client.put(url,json=dict(revision=moment['revision'],script=script))
        self.assertEqual(response.status_code,200,response.get_json())
        with patch.object(app, '_generate_moment_script') as generate:
            item = self.client.get(f"/api/moments/{moment['id']}").get_json()['item']
            generate.assert_not_called()
        self.assertEqual(item['script'][0]['text'],'Ærø og København')
        self.assertEqual(item['script'][1]['second_photo_id'],ids[0])
        self.assertEqual(item['script'][1]['duration'],15)
        self.assertEqual(set(item['photos']),{str(ids[2]),str(ids[0])})
        self.assertEqual(item['photo_ids'],ids)
        self.assertEqual(item['video_status'],'none')
        self.assertEqual(self.client.put(url,json=dict(revision=moment['revision'],script=script)).status_code,409)
        with patch.object(moment_cinema,'VERSION',999):
            self.assertFalse(moment_cinema.needs_upgrade(json.dumps(item['script'])))
        link = self.client.post(f"/api/moments/{moment['id']}/share").get_json()['url']
        public = app.app.test_client().get('/api/moment-share/'+link.split('/')[-1]).get_json()['item']
        self.assertEqual(public['script'],item['script'])
        self.assertEqual(set(public['photos']),set(item['photos']))

    def test_access_invalid_media_and_invalid_durations_cannot_change_saved_script(self):
        moment = self.make_moment()
        pid = json.loads(moment['photo_ids_json'])[0]
        url = f"/api/moments/{moment['id']}/slideshow"
        viewer = app.app.test_client()
        with viewer.session_transaction() as session:
            session['_user_id'] = '2'; session['_fresh'] = True
        body = dict(revision=moment['revision'],script=[dict(type='photo',photo_id=pid,duration=5)])
        self.assertEqual(viewer.put(url,json=body).status_code,403)
        for script in ([dict(type='photo',photo_id=999999,duration=5)],
                       [dict(type='photo',photo_id=pid,duration=-1)],
                       [dict(type='video',photo_id=pid)],
                       [dict(type='pair',photo_id=pid,second_photo_id=pid,duration=5)], []):
            self.assertEqual(self.client.put(url,json=dict(body,script=script)).status_code,400)
        self.assertEqual(self.client.put(url,json=body).status_code,200)

    def test_video_duration_is_always_natural(self):
        result = moment_slideshow.validate([dict(type='video',photo_id=1,duration=2)],{1:dict(ext='.mp4')},{'.mp4'})
        self.assertIsNone(result[0]['duration'])

    def test_membership_changes_preserve_text_and_drop_removed_media(self):
        script = [dict(type='text',text='Vores egen overskrift',script_edited=True,background_photo_id=1),
                  dict(type='pair',photo_id=1,second_photo_id=2,label='Sommer'),dict(type='photo',photo_id=3)]
        kept = json.loads(moment_slideshow.retain_edited_script(json.dumps(script),[2]))
        self.assertEqual(len(kept),2)
        self.assertEqual(kept[0]['text'],'Vores egen overskrift')
        self.assertNotIn('background_photo_id',kept[0])
        self.assertEqual(kept[1]['type'],'photo')
        self.assertEqual(kept[1]['photo_id'],2)

    def test_pairs_keep_chronology_and_only_use_available_weather(self):
        rows = [legacy.photo(i,f'2024-07-10T12:{i:02}:00','Berlin, Germany',width=800,height=1200) for i in range(12)]
        rows[0]['metadata_json'] = json.dumps(dict(weather=dict(weather_label_da='Sol',temperature_2m=22.3)))
        script = moment_cinema.timeline(dict(title='Berlin',primary_place='Berlin',start_date='2024-07-10',end_date='2024-07-10'),rows)
        media = [s for s in script if s['type'] != 'text']
        self.assertTrue(any(s['type']=='pair' for s in media))
        self.assertEqual([pid for s in media for pid in (s.get('photo_id'),s.get('second_photo_id')) if pid is not None],list(range(12)))
        self.assertEqual(media[0]['weather'],'Sol · 22 °C')
        self.assertFalse(media[-1]['weather'])
