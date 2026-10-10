"""Exercise the actual settings panel with mocked account responses."""
import json
import unittest
from pathlib import Path

from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]


class ChatGPTConnectionBrowserTests(unittest.TestCase):
    def test_connect_disconnect_error_and_mobile_layout(self):
        template = (ROOT / 'templates/index.html').read_text(encoding='utf-8')
        start = template.index('<div id="chatgptConnectionPanel"')
        end = template.index('<div style=', start)
        panel = template[start:end]
        data = {'ok': True, 'connected': False, 'csrf': 'csrf-test'}
        imports = []
        errors = []

        def route_request(route):
            method = route.request.method
            if method in {'POST', 'DELETE'}:
                assert route.request.headers['x-chatgpt-csrf'] == 'csrf-test'
            if method == 'POST':
                imports.append(route.request.post_data_buffer)
                data.update(connected=True, email='my-account@example.com')
            if method == 'DELETE':
                data.update(connected=False)
            route.fulfill(content_type='application/json', body=json.dumps(data))

        with sync_playwright() as runtime:
            browser = runtime.chromium.launch()
            page = browser.new_page()
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.route('https://fjordlens.test/', lambda route: route.fulfill(
                content_type='text/html', body='<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
                '<body class="view-settings" style="padding:16px;margin:0"><div class="mini-label">AI beskrivelser</div>' + panel))
            page.route('**/api/ai/chatgpt/connection', route_request)
            page.goto('https://fjordlens.test/')
            for css in ['styles.css', 'redesign.css']:
                page.add_style_tag(path=str(ROOT / 'static' / css))
            page.add_script_tag(path=str(ROOT / 'static/chatgpt-connection.js'))
            expect(page.locator('#chatgptConnectionStatus')).to_contain_text('ikke tilsluttet')
            for width in [1440, 390, 320]:
                page.set_viewport_size({'width': width, 'height': 900})
                page.locator('#chatgptConnectBtn').click()
                expect(page.locator('#chatgptLoginSteps')).to_be_visible()
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                box = page.locator('#chatgptConnectBtn').bounding_box()
                assert box['width'] > 100 and box['height'] > 20
            page.locator('#chatgptConnectionFile').set_input_files({
                'name': 'connection.json', 'mimeType': 'application/json', 'buffer': b'{"fixture":true}'})
            expect(page.locator('#chatgptConnectionStatus')).to_contain_text('my-account@example.com')
            expect(page.locator('#chatgptLoginSteps')).not_to_be_visible()
            assert imports and page.locator('#chatgptConnectionFile').input_value() == ''
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
            assert errors == []
            browser.close()


if __name__ == '__main__':
    unittest.main()
