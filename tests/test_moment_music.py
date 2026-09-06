import json
import subprocess
import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import patch
import numpy as np
import app
import moment_music as music
import moment_slideshow
from tests import test_moments_v2 as legacy


class MusicTests(unittest.TestCase):
    def test_catalog_and_invalid_choices(self):
        tracks = music.catalog()
        self.assertEqual(len(tracks), 16)
        self.assertEqual(len({t['id'] for t in tracks}), 16)
        for track in tracks:
            self.assertTrue((music.ROOT / track['file']).is_file())
            self.assertLess(track['trim_start'], track['trim_end'])
        for value in ({'track_id':'../README.md'}, {'track_id':[]}, {'volume':True},
                      {'volume':float('nan')}, {'volume':2}, {'url':'https://example.com/a.mp3'}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                music.validate(value)
        self.assertIsNone(music.descriptor([{'music':{'track_id':None,'volume':.3}}], 'Bryllup'))
        self.assertTrue(music.choice([], 'Bryllup · 26.06.2026')['track_id'].startswith('wedding-'))

    def test_removing_first_slide_keeps_soundtrack(self):
        soundtrack = dict(track_id='summer-1', volume=.4)
        script = [dict(type='photo',photo_id=1,script_edited=True,music=soundtrack),
                  dict(type='photo',photo_id=2)]
        kept = json.loads(moment_slideshow.retain_edited_script(json.dumps(script), {2}))
        self.assertEqual(kept[0]['music'], soundtrack)

    def test_crossfade_has_no_gap_at_repeated_boundaries_and_exports_audio(self):
        import imageio_ffmpeg
        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        rate = 44100
        sine = .2 * np.sin(2 * np.pi * 220 * np.arange(rate * 3) / rate)
        samples = np.column_stack([sine, sine])
        intro, cycle = music.loop_parts(samples, rate)
        repeated = np.concatenate([intro,cycle,cycle,cycle])
        for boundary in (rate*2, rate*4, rate*6):
            self.assertLess(abs(repeated[boundary,0]-repeated[boundary-1,0]), .02)
            self.assertGreater(np.sqrt(np.mean(repeated[boundary-1000:boundary+1000]**2)), .1)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with wave.open(str(root/'tone.wav'),'wb') as out:
                out.setnchannels(2); out.setsampwidth(2); out.setframerate(rate)
                out.writeframes((samples * 32767).astype('<i2').tobytes())
            subprocess.run([ffmpeg,'-v','error','-f','lavfi','-i','color=c=blue:s=90x160:r=10',
                            '-t','8','-c:v','libx264','-pix_fmt','yuv420p',str(root/'silent.mp4')],check=True)
            track = dict(file='tone.wav',trim_start=0,trim_end=3,crossfade=1,volume=.4)
            with patch.object(music,'ROOT',root):
                music.add_to_video(ffmpeg, root/'silent.mp4', root/'result.mp4',root,track)
            raw = subprocess.run([ffmpeg,'-v','error','-i',str(root/'result.mp4'),'-vn','-f','f32le',
                                  '-ar','44100','-ac','1','-'],capture_output=True,check=True).stdout
            audio = np.frombuffer(raw,dtype='<f4')
            self.assertAlmostEqual(len(audio)/rate,8,delta=.06)
            for second in (2,4,6):
                window = audio[int((second-.05)*rate):int((second+.05)*rate)]
                self.assertGreater(np.sqrt(np.mean(window**2)),.045)
            self.assertLess(np.sqrt(np.mean(audio[-1000:]**2)), .01)


class MusicIntegrationTests(unittest.TestCase):
    setUp = legacy.MomentEditingTests.setUp
    tearDown = legacy.MomentEditingTests.tearDown
    _insert_photo = legacy.MomentEditingTests._insert_photo
    make_moment = legacy.MomentEditingTests.make_moment

    def test_share_snapshots_music_and_revocation_blocks_audio(self):
        row = self.make_moment()
        url = f"/api/moments/{row['id']}"
        selected = dict(track_id='wedding-1',volume=.3)
        script = [dict(type='text',text='Bryllup',duration=5,music=selected)]
        saved = self.client.put(url+'/slideshow',json=dict(script=script,revision=row['revision']))
        self.assertEqual(saved.status_code,200)
        token = self.client.post(url+'/share').get_json()['url'].split('/')[-1]
        guest = app.app.test_client()
        public = guest.get('/api/moment-share/'+token).get_json()['item']
        self.assertEqual(public['music']['id'],'wedding-1')
        self.assertEqual(public['music']['volume'],.3)
        with guest.get(public['music']['url'],headers={'Range':'bytes=0-31'}) as response:
            self.assertEqual(response.status_code,206)
            self.assertEqual(len(response.data),32)
        self.assertNotEqual(guest.get('/api/moments/music').status_code,200)
        script[0]['music'] = dict(track_id=None,volume=.3)
        self.assertEqual(self.client.put(url+'/slideshow',json=dict(script=script,revision=saved.get_json()['revision'])).status_code,200)
        self.assertIsNone(self.client.get(url).get_json()['item']['music'])
        self.assertEqual(guest.get('/api/moment-share/'+token).get_json()['item']['music']['id'],'wedding-1')
        self.client.delete(url+'/share')
        self.assertEqual(guest.get(public['music']['url']).status_code,404)

    def test_upgrade_preserves_manual_edits_and_is_idempotent(self):
        row = self.make_moment()
        script = [dict(type='text',text='Bevar mig',script_edited=True,duration=8)]
        with app.closing(app.get_conn()) as conn:
            conn.execute("UPDATE moments SET script_json=?,video_status='done',video_rel_path='old.mp4' WHERE id=?",(json.dumps(script),row['id']))
            music.upgrade(conn); music.upgrade(conn)
            result = conn.execute('SELECT * FROM moments WHERE id=?',(row['id'],)).fetchone()
        self.assertEqual(result['revision'],row['revision']+1)
        self.assertEqual(json.loads(result['script_json'])[0]['text'],'Bevar mig')
        self.assertEqual(result['video_status'],'none')
        self.assertIsNone(result['video_rel_path'])
