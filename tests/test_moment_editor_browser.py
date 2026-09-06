"""Isolated browser integration: real editor/player and Flask endpoints, temporary media."""
import json
import os
import unittest
from pathlib import Path
from urllib.parse import urlsplit
from PIL import Image, ImageDraw
import app
import moment_cinema
from tests import test_moments_v2 as legacy


class EditorBrowserTests(unittest.TestCase):
    setUp = legacy.MomentEditingTests.setUp
    tearDown = legacy.MomentEditingTests.tearDown
    _insert_photo = legacy.MomentEditingTests._insert_photo
    make_moment = legacy.MomentEditingTests.make_moment

    def test_edit_reorder_pair_save_and_playback(self):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            self.skipTest('Playwright is optional for local browser checks')
        moment = self.make_moment()
        ids = json.loads(moment['photo_ids_json'])
        with app.closing(app.get_conn()) as conn:
            for index,pid in enumerate(ids):
                rel = conn.execute('SELECT rel_path FROM photos WHERE id=?',(pid,)).fetchone()[0]
                path = app.UPLOAD_DIR / rel.split('/',1)[1]
                path.parent.mkdir(parents=True,exist_ok=True)
                image = Image.new('RGB',(500,800),['#8cafa1','#d6aa73','#64899a','#b89a91'][index])
                draw = ImageDraw.Draw(image)
                draw.ellipse((120,90,380,350),fill='#edceb0')
                draw.rounded_rectangle((80,360,420,780),radius=100,fill='#334f54')
                image.save(path)
                image.resize((125,200)).save(self.thumbs / f'{pid}.jpg')
                conn.execute("UPDATE photos SET ext='.jpg',width=500,height=800,thumb_name=? WHERE id=?",(f'{pid}.jpg',pid))
            script = [dict(type='photo',photo_id=pid,duration=5.2,fit='contain',layout='right',label='Sommer',detail='12. juli 2024',design_version=moment_cinema.VERSION) for pid in ids]
            conn.execute('UPDATE moments SET script_json=? WHERE id=?',(json.dumps(script),moment['id']))
            conn.commit()
        harness = '''<!doctype html><meta charset="utf-8"><link rel="stylesheet" href="/static/styles.css">
        <button onclick="editMomentSlideshow(MOMENT_ID)">Test editor</button>
        <div id="momentPlayerOverlay" class="moment-player hidden"><div id="momentPlayerProgress" class="moment-player-progress"></div><button id="momentPlayerCloseBtn" class="moment-player-close">Luk afspilning</button><div id="momentPlayerStage" class="moment-player-stage"></div><div class="moment-player-footer"><span id="momentPlayerFooterTitle"></span><button id="momentPlayerVideoBtn">Video</button><button id="momentPlayerEditBtn">Rediger diasshow</button></div></div>
        <script>const state={currentUser:{role:'admin'},momentPlayer:null}; const els=Object.fromEntries([...document.querySelectorAll('[id]')].map(e=>[e.id,e])); function tr(s){return s} function escapeHtml(s){const e=document.createElement('span');e.textContent=String(s);return e.innerHTML.replaceAll('"','&quot;')}</script>
        <script src="/static/moments.js"></script><script src="/static/moment_player.js"></script><script src="/static/moment_editor.js"></script>'''.replace('MOMENT_ID',str(moment['id']))
        errors = []
        with sync_playwright() as runtime:
            try:
                browser = runtime.chromium.launch(headless=True)
            except Exception as exc:
                self.skipTest(f'Chromium is not installed: {exc}')
            page = browser.new_page(viewport=dict(width=1440,height=1050))
            page.on('pageerror',lambda error: errors.append(str(error)))
            def route(request_route):
                request = request_route.request
                path = urlsplit(request.url).path
                if path == '/':
                    request_route.fulfill(body=harness,content_type='text/html'); return
                response = self.client.open(path,method=request.method,data=request.post_data,content_type=request.headers.get('content-type'))
                request_route.fulfill(status=response.status_code,body=response.get_data(),content_type=response.content_type)
                response.close()
            page.route('**/*',route)
            page.goto('http://fjordlens.test/')
            page.get_by_role('button',name='Test editor',exact=True).click()
            page.locator('[data-field="heading"]').fill('K\u00f8benhavn og \u00c6r\u00f8')
            page.locator('[data-field="duration"]').fill('14')
            page.locator('[data-second]').select_option(str(ids[1]))
            self.assertEqual(page.locator('.slideshow-preview .cinema-media').count(),2)
            page.locator('.slideshow-clip').nth(0).drag_to(page.locator('.slideshow-clip').nth(2))
            page.get_by_role('button',name='+ Tekst',exact=True).click()
            page.locator('[data-field="heading"]').fill('Vores sommerminder')
            page.get_by_role('button',name='Gem diasshow',exact=True).click()
            page.get_by_text('Diasshow gemt.',exact=False).wait_for()
            saved = self.client.get(f"/api/moments/{moment['id']}").get_json()['item']['script']
            self.assertEqual(saved[2]['type'],'pair')
            self.assertEqual(saved[2]['label'],'K\u00f8benhavn og \u00c6r\u00f8')
            self.assertEqual(saved[2]['duration'],14)
            self.assertEqual(saved[3]['text'],'Vores sommerminder')
            page.locator('.slideshow-clip').nth(2).click()
            screenshot = os.environ.get('FJORDLENS_EDITOR_SCREENSHOT')
            if screenshot:
                page.screenshot(path=screenshot,full_page=True,animations='disabled')
            page.get_by_role('button',name='Afspil udkast',exact=True).click()
            page.locator('#momentPlayerStage .cinema-media').wait_for()
            self.assertFalse(page.locator('#momentPlayerVideoBtn').is_visible())
            page.get_by_role('button',name='Luk afspilning',exact=True).click()
            self.assertTrue(page.locator('.slideshow-editor').is_visible())
            self.assertFalse(errors,errors)
            browser.close()
