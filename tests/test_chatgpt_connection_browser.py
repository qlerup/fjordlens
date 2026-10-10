"""Actual login panel with device-code and account responses simulated."""
import json
import unittest
from pathlib import Path

from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]


class ChatGPTConnectionBrowserTests(unittest.TestCase):
    def test_device_login_auto_completion_cancel_retry_and_mobile(self):
        template = (ROOT / 'templates/index.html').read_text(encoding='utf-8')
        start = template.index('<div id="chatgptConnectionPanel"')
        panel = template[start:template.index('<div style=', start)]
        data = {'ok': True, 'connected': False, 'csrf': 'csrf-test'}
        errors = []
        started = []

        def route_request(route):
            method = route.request.method
            login = route.request.url.endswith('/login')
            if method in {'POST', 'DELETE'}:
                assert route.request.headers['x-chatgpt-csrf'] == 'csrf-test'
            if login and method == 'POST':
                started.append(True)
                data['login'] = {'state': 'waiting', 'user_code': 'ABCD-1234',
                                 'verification_url': 'https://auth.openai.com/codex/device'}
            if method == 'DELETE':
                data.pop('login', None)
                if not login:
                    data.update(connected=False)
            route.fulfill(content_type='application/json', body=json.dumps(data))

        with sync_playwright() as runtime:
            browser = runtime.chromium.launch()
            page = browser.new_page()
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.route('https://fjordlens.test/', lambda route: route.fulfill(
                content_type='text/html', body='<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
                '<body class="view-settings" style="padding:16px;margin:0"><div class="mini-label">AI beskrivelser</div>' + panel))
            page.route('**/api/ai/chatgpt/*', route_request)
            page.goto('https://fjordlens.test/')
            for css in ['styles.css', 'redesign.css']:
                page.add_style_tag(path=str(ROOT / 'static' / css))
            page.add_script_tag(path=str(ROOT / 'static/chatgpt-connection.js'))
            expect(page.locator('#chatgptConnectionStatus')).to_contain_text('ikke tilsluttet')
            page.locator('#chatgptConnectBtn').click()
            expect(page.locator('#chatgptDeviceCode')).to_have_value('ABCD-1234')
            expect(page.locator('#chatgptVerifyLink')).to_have_attribute('href', 'https://auth.openai.com/codex/device')
            expect(page.locator('#chatgptConnectBtn')).to_be_disabled()
            for width in [1440, 390, 320]:
                page.set_viewport_size({'width': width, 'height': 900})
                expect(page.locator('#chatgptLoginSteps')).to_be_visible()
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            # No file inputs, download helpers, or desktop installs.
            assert page.locator('input[type="file"]').count() == 0
            page.locator('#chatgptCancelBtn').click()
            expect(page.locator('#chatgptLoginSteps')).not_to_be_visible()
            expect(page.locator('#chatgptConnectBtn')).to_be_enabled()
            page.locator('#chatgptConnectBtn').click()
            expect(page.locator('#chatgptDeviceCode')).to_have_value('ABCD-1234')
            data.update(connected=True, email='my-account@example.com', plan='plus', login={'state': 'completed'})
            expect(page.locator('#chatgptConnectionStatus')).to_contain_text('my-account@example.com')
            expect(page.locator('#chatgptLoginSteps')).not_to_be_visible()
            expect(page.locator('#chatgptDeviceCode')).to_have_value('')
            page.locator('#chatgptDisconnectBtn').click()
            expect(page.locator('#chatgptConnectionStatus')).to_contain_text('ikke tilsluttet')
            expect(page.locator('#chatgptDisconnectBtn')).not_to_be_visible()
            data.update(ok=False, error='Test af midlertidig fejl')
            page.evaluate("document.body.classList.remove('view-settings')")
            page.evaluate("document.body.classList.add('view-settings')")
            expect(page.locator('#chatgptConnectionError')).to_contain_text('midlertidig fejl')
            data.update(ok=True)
            page.locator('#chatgptRetryBtn').click()
            expect(page.locator('#chatgptConnectionError')).not_to_be_visible()
            expect(page.locator('#chatgptConnectBtn')).to_be_enabled()
            assert errors == [] and len(started) == 2
            browser.close()


if __name__ == '__main__':
    unittest.main()
