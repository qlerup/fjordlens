"""Exercise the shared browser monitor with real dialog/fetch behavior."""
import unittest
from pathlib import Path
from playwright.sync_api import sync_playwright


class HubSessionBrowserTests(unittest.TestCase):
    def test_revocation_displays_once_then_returns_to_login_and_outage_does_not_log_out(self):
        root=Path(__file__).resolve().parents[1]
        with sync_playwright() as playwright:
            browser=playwright.chromium.launch()
            try:
                for width in (390,1440):
                    context=browser.new_context(viewport={'width':width,'height':900})
                    page=context.new_page()
                    status={'revoked':False,'outage':False}
                    def route(request):
                        path=request.request.url.split('test')[-1].split('?')[0]
                        if path.endswith('.js'): request.fulfill(path=str(root/'static/hub-session.js'),content_type='text/javascript; charset=utf-8')
                        elif path.endswith('.css'): request.fulfill(path=str(root/'static/hub-session.css'),content_type='text/css; charset=utf-8')
                        elif path.startswith('/api/'):
                            code=503 if status['outage'] else 401 if status['revoked'] else 200
                            request.fulfill(status=code,json={'authenticated':code==200, 'error_code':'access_revoked' if code==401 else 'hub_unavailable' if code==503 else None})
                        else: request.fulfill(content_type='text/html; charset=utf-8',body='<html><head><meta charset="utf-8"><link rel="stylesheet" href="/static/hub-session.css"><script defer src="/static/hub-session.js"></script></head><body><main>Private content</main></body></html>')
                    page.route('**/*',route)
                    page.goto('https://session.test/',wait_until='networkidle')
                    other=page.context.new_page()
                    other.route('**/*',route)
                    other.goto('https://session.test/',wait_until='networkidle')
                    status['outage']=True
                    page.evaluate("fetch('/api/auth/access')")
                    self.assertEqual(page.locator('.hub-access-removed').count(),0)
                    status.update(outage=False,revoked=True)
                    page.evaluate("fetch('/api/private'); fetch('/api/auth/access')")
                    popup=page.locator('.hub-access-removed')
                    popup.wait_for()
                    self.assertEqual(popup.count(),1)
                    self.assertIn('Din adgang er blevet fjernet.',popup.inner_text())
                    box=popup.bounding_box()
                    self.assertGreaterEqual(box['x'],0)
                    self.assertLessEqual(box['x']+box['width'],width)
                    # Revocation propagates to a second open tab even if its cookie was cleared.
                    other.locator('.hub-access-removed').wait_for()
                    popup.get_by_role('button',name='Gå til login').click()
                    page.wait_for_url('**/login')
                    other.wait_for_url('**/login')  # No click: the automatic logout timer redirects.
                    other.close()
                    page.close()
                    context.close()
            finally: browser.close()
