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
        script = [dict(type='text',text='Ærø og København',duration=4.5,text_position=dict(x=.2,y=.7)),
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
        self.assertEqual(item['script'][0]['text_position'],dict(x=.2,y=.7))
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

    def test_invalid_text_positions_rejected(self):
        import moments_service
        for position in ({'x':-1,'y':.5},{'x':.5,'y':1.1},{'x':True,'y':.5},
                         {'x':float('nan'),'y':.5},{'x':.5},{'x':.5,'y':'20%'},[]):
            with self.subTest(position=position), self.assertRaises(moments_service.EditError):
                moment_slideshow.validate([dict(type='text',text='Hej',text_position=position)],{},set())

    def test_export_format_validation_and_persistence(self):
        moment = self.make_moment()
        url = f"/api/moments/{moment['id']}/render-video"
        self.assertEqual(self.client.post(url,json={'format':'square'}).status_code,400)
        self.assertEqual(self.client.post(url,json={'format':'portrait'}).status_code,400)
        self.assertEqual(self.client.post(url,json=['portrait']).status_code,400)
        with patch.object(app.threading, 'Thread') as thread:
            thread.return_value.is_alive.return_value = False
            for format in ('landscape',):
                response = self.client.post(url,json={'format':format})
                self.assertEqual(response.status_code,200,response.get_json())
                self.assertEqual(self.client.get(url+'/status').get_json()['video_format'],format)
                thread.return_value.start.assert_called()
        app.moment_video_threads.pop(moment['id'],None)

    def test_mp4_text_overlay_moves_to_selected_corner(self):
        from PIL import Image
        def bounds(position):
            overlay = moment_cinema.overlay(dict(type='text',text='Bryllup',text_position=position),(640,360))
            bright = Image.new('1',overlay.size)
            bright.putdata([int(max(pixel[:3])>150) for pixel in overlay.getdata()])
            return bright.getbbox()
        left, right = bounds(dict(x=0,y=0)), bounds(dict(x=1,y=1))
        self.assertLess(left[0],10)
        self.assertLess(left[1],60)
        self.assertGreater(right[0],400)
        self.assertGreater(right[1],250)
        self.assertLessEqual(right[2],640)
        self.assertLessEqual(right[3],360)

    def test_old_portrait_export_is_retired_without_changing_the_timeline(self):
        import moments_service
        moment = self.make_moment()
        script = [dict(type='text',text='Vores dag',duration=6,script_edited=True,
                       music=dict(track_id='wedding-1',volume=.3))]
        with app.closing(app.get_conn()) as conn:
            conn.execute("UPDATE moments SET user_edited=1,script_json=?,video_status='done',video_format='portrait',video_rel_path='old_portrait.mp4' WHERE id=?",
                         (json.dumps(script),moment['id']))
            moments_service.migrate(conn)
            row=conn.execute('SELECT * FROM moments WHERE id=?',(moment['id'],)).fetchone()
        self.assertEqual(json.loads(row['script_json']),script)
        self.assertEqual(row['video_format'],'landscape')
        self.assertEqual(row['video_status'],'none')
        self.assertIsNone(row['video_rel_path'])

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
