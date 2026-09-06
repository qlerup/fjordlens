import json
from datetime import datetime, timezone
import unittest
from urllib.parse import urlsplit
import app
import moment_cinema
from tests import test_moments_v2 as legacy


class ShareBrowserTests(unittest.TestCase):
    setUp = legacy.MomentEditingTests.setUp
    tearDown = legacy.MomentEditingTests.tearDown
    _insert_photo = legacy.MomentEditingTests._insert_photo
    make_moment = legacy.MomentEditingTests.make_moment

    def test_settings_buttons_work_in_full_application(self):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            self.skipTest('Playwright is optional for local browser checks')
        moment = self.make_moment()
        with app.closing(app.get_conn()) as conn:
            conn.execute('UPDATE moments SET script_json=? WHERE id=?', (json.dumps([dict(type='text',text='Test',design_version=moment_cinema.VERSION)]),moment['id']))
            conn.commit()
        self.client.post(f"/api/moments/{moment['id']}/share")
        errors = []
        with sync_playwright() as runtime:
            try:
                browser = runtime.chromium.launch(headless=True)
            except Exception as exc:
                self.skipTest(f'Chromium is not installed: {exc}')
            page = browser.new_page(viewport=dict(width=1500,height=950),permissions=['clipboard-read','clipboard-write'])
            page.set_default_timeout(8000)
            page.on('pageerror', lambda error: errors.append(str(error)))
            def route(r):
                url = urlsplit(r.request.url)
                if url.hostname != 'fjordlens.test':
                    r.abort(); return
                if url.path == '/api/health':
                    r.fulfill(json={'ok':True,'ai':{'ok':True}}); return
                response = self.client.open(url.path+('?' + url.query if url.query else ''),method=r.request.method,data=r.request.post_data,content_type=r.request.headers.get('content-type'))
                r.fulfill(status=response.status_code,body=response.get_data(),content_type=response.content_type)
                response.close()
            page.route('**/*',route)
            page.goto('https://fjordlens.test/')
            page.locator('#uiDesignIntroModal').wait_for(state='visible')
            page.locator('#uiDesignIntroModal button').last.click()
            page.locator('[data-view="settings"]').first.click()
            page.locator('[data-tab="shared"]').click()
            page.locator('[data-share-edit]').first.click()
            page.get_by_role('dialog',name='Rediger momentlink').wait_for(timeout=5000)
            page.locator('[data-name]').fill('Delte minder')
            page.locator('[data-days]').fill('14')
            page.get_by_role('button',name='Gem ændringer',exact=True).click()
            page.locator('#sharedLinksList').get_by_text('Delte minder',exact=False).wait_for()
            page.locator('[data-share-copy]').click()
            copied = page.evaluate('navigator.clipboard.readText()')
            self.assertIn('/m/',copied)
            with page.expect_download() as download:
                page.locator('[data-share-qr]').click()
            self.assertTrue(download.value.suggested_filename.endswith('.png'))
            page.on('dialog',lambda dialog: dialog.accept('30') if dialog.type == 'prompt' else dialog.accept())
            with page.expect_response(lambda r: r.url.endswith('/extend')):
                page.locator('[data-share-extend]').click()
            listing = self.client.get('/api/admin/shares?include_inactive=1').get_json()['items']
            self.assertGreater((datetime.fromisoformat(listing[0]['expires_at'].replace('Z','+00:00'))-datetime.now(timezone.utc)).days,28)
            page.locator('[data-share-revoke]').click()
            page.locator('[data-share-activate]').wait_for()
            self.assertEqual(app.app.test_client().get(urlsplit(copied).path).status_code,404)
            page.locator('[data-share-activate]').click()
            page.locator('[data-share-revoke]').wait_for()
            self.assertEqual(app.app.test_client().get(urlsplit(copied).path).status_code,200)
            page.locator('[data-share-delete]').click()
            page.wait_for_function("document.querySelectorAll('[data-share-delete]').length === 0")
            self.assertEqual(app.app.test_client().get(urlsplit(copied).path).status_code,404)
            page.locator('[data-view="momenter"]').first.click()
            page.locator('[data-moment-action="share"]').first.click()
            self.assertEqual(self.client.get('/api/admin/shares?include_inactive=1').get_json()['items'],[])
            page.locator('[data-expire-value]').fill('2')
            page.locator('[data-expire-unit]').select_option('hours')
            page.get_by_role('button',name='Opret delelink',exact=True).click()
            page.get_by_role('textbox',name='Delelink',exact=True).wait_for()
            listing = self.client.get('/api/admin/shares?include_inactive=1').get_json()['items']
            seconds = (datetime.fromisoformat(listing[0]['expires_at'].replace('Z','+00:00'))-datetime.now(timezone.utc)).total_seconds()
            self.assertTrue(7100 < seconds <= 7200)
            page.get_by_role('dialog',name='Del moment').locator('[data-close]').click()
            page.locator('[data-moment-action="share"]').first.click()
            page.locator('[data-never]').check()
            page.get_by_role('button',name='Opret delelink',exact=True).click()
            page.get_by_text('Linket har intet udløb.',exact=True).wait_for()
            self.assertTrue(any(s['expires_at'] is None for s in self.client.get('/api/admin/shares?include_inactive=1').get_json()['items']))
            self.assertFalse(errors,errors)
            browser.close()
