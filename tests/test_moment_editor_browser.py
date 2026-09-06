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
            script = [dict(type='photo',photo_id=pid,duration=5.2,fit='contain',layout='right',label='Sommer',eyebrow='DANMARK',weather='Sol · 22 °C',detail='12. juli 2024',design_version=moment_cinema.VERSION) for pid in ids]
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
            # Drag the actual heading and retain the resulting position through
            # undo, redo, reset, saving, reopening, and anonymous playback.
            heading = page.locator('.slideshow-preview .cinema-heading')
            before = heading.bounding_box()
            page.mouse.move(before['x']+before['width']/2, before['y']+before['height']/2)
            page.mouse.down()
            page.mouse.move(before['x']+before['width']/2-170, before['y']+before['height']/2-110, steps=12)
            page.mouse.up()
            moved = heading.bounding_box()
            moved_stage = page.locator('.slideshow-preview').bounding_box()
            self.assertLess(moved['x'],before['x']-100)
            self.assertLess(moved['y'],before['y']-70)
            self.assertEqual(page.locator('.slideshow-preview .cinema-positioned').count(),1)
            page.get_by_role('button',name='Fortryd',exact=True).click()
            self.assertEqual(page.locator('.slideshow-preview .cinema-positioned').count(),0)
            page.get_by_role('button',name='Gentag',exact=True).click()
            self.assertEqual(page.locator('.slideshow-preview .cinema-positioned').count(),1)
            page.get_by_role('button',name='Nulstil placering',exact=True).click()
            self.assertEqual(page.locator('.slideshow-preview .cinema-positioned').count(),0)
            page.get_by_role('button',name='Fortryd',exact=True).click()
            page.get_by_role('button',name='Gem diasshow',exact=True).click()
            page.get_by_text('Diasshow gemt.',exact=False).wait_for()
            saved = self.client.get(f"/api/moments/{moment['id']}").get_json()['item']['script']
            self.assertEqual(saved[2]['type'],'pair')
            self.assertEqual(saved[2]['label'],'K\u00f8benhavn og \u00c6r\u00f8')
            self.assertEqual(saved[2]['duration'],14)
            self.assertEqual(saved[3]['text'],'Vores sommerminder')
            self.assertLess(saved[3]['text_position']['x'], .5)
            self.assertLess(saved[3]['text_position']['y'], .5)
            page.get_by_role('button',name='Luk',exact=True).click()
            page.get_by_role('button',name='Test editor',exact=True).click()
            page.locator('.slideshow-clip').nth(3).click()
            restored = page.locator('.slideshow-preview .cinema-heading').bounding_box()
            restored_stage = page.locator('.slideshow-preview').bounding_box()
            self.assertAlmostEqual(restored['x']-restored_stage['x'],moved['x']-moved_stage['x'],delta=2)
            self.assertAlmostEqual(restored['y']-restored_stage['y'],moved['y']-moved_stage['y'],delta=2)
            positioned = page.locator('.slideshow-preview .cinema-positioned')
            old_x = float(positioned.evaluate("e => e.style.getPropertyValue('--text-x')"))
            positioned.focus()
            page.keyboard.press('ArrowRight')
            self.assertGreater(float(positioned.evaluate("e => e.style.getPropertyValue('--text-x')")),old_x)
            page.get_by_role('button',name='Fortryd',exact=True).click()
            if os.environ.get('FJORDLENS_EDITOR_SCREENSHOT'):
                page.screenshot(path=str(Path(os.environ['FJORDLENS_EDITOR_SCREENSHOT']).with_name('fjordlens-moved-text.png')),animations='disabled')
            page.locator('.slideshow-clip').nth(2).click()
            screenshot = os.environ.get('FJORDLENS_EDITOR_SCREENSHOT')
            if screenshot:
                page.screenshot(path=screenshot,full_page=True,animations='disabled')
            page.get_by_role('button',name='Afspil udkast',exact=True).click()
            page.locator('#momentPlayerStage .cinema-media').wait_for()
            self.assertFalse(page.locator('#momentPlayerVideoBtn').is_visible())
            page.get_by_role('button',name='Luk afspilning',exact=True).click()
            self.assertTrue(page.locator('.slideshow-editor').is_visible())
            # Use the real anonymous share page, with the phone held upright.
            link = self.client.post(f"/api/moments/{moment['id']}/share").get_json()['url']
            public_client = app.app.test_client()
            self.client = public_client
            for width,height in ((390,844),(320,568)):
                page.set_viewport_size(dict(width=width,height=height))
                page.goto('http://fjordlens.test'+link)
                if width == 390:
                    page.get_by_role('button',name='Fuld skærm',exact=True).click()
                    page.wait_for_function("document.fullscreenElement?.id === 'momentPlayerOverlay'")
                    page.get_by_role('button',name='Afslut fuld skærm',exact=True).click()
                    page.wait_for_function('!document.fullscreenElement')
                heading = page.locator('#momentPlayerStage .cinema-heading').last
                heading.wait_for()
                page.emulate_media(reduced_motion='reduce')
                text = page.locator('#momentPlayerStage .cinema-type').last.bounding_box()
                self.assertGreater(text['width'],width*.9)
                self.assertGreater(text['y'],height*.4)
                self.assertGreaterEqual(heading.evaluate('e => parseFloat(getComputedStyle(e).fontSize)'),22)
                weather = page.locator('#momentPlayerStage .cinema-weather').last.bounding_box()
                footer = page.locator('.moment-player-footer').bounding_box()
                self.assertLess(weather['y']+weather['height'],footer['y'])
                if screenshot and width == 390:
                    page.screenshot(path=str(Path(screenshot).with_name('fjordlens-mobile-share.png')),animations='disabled')
            page.set_viewport_size(dict(width=844,height=390))
            self.assertLess(page.locator('#momentPlayerStage .cinema-type').last.bounding_box()['width'],844*.4)
            # Advance the real public player to the moved text slide.
            for _ in range(3):
                page.keyboard.press('ArrowRight')
            page.locator('#momentPlayerStage .cinema-positioned').last.wait_for()
            page.set_viewport_size(dict(width=390,height=844))
            box = page.locator('#momentPlayerStage .cinema-positioned').last.bounding_box()
            self.assertGreaterEqual(box['x'], -1)
            self.assertGreaterEqual(box['y'], -1)
            self.assertLessEqual(box['x']+box['width'],391)
            self.assertLessEqual(box['y']+box['height'],845)
            self.assertFalse(errors,errors)
            browser.close()
