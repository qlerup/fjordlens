"""Exercise the actual modal and scripts with simulated account/model results."""
import json
from pathlib import Path

from playwright.sync_api import sync_playwright, expect

from chatgpt_analysis_schema import SCHEMA
from test_chatgpt_analysis import sample

ROOT = Path(__file__).resolve().parents[1]


def test_modal_upload_result_error_keyboard_and_mobile(tmp_path):
    template = (ROOT / 'templates/index.html').read_text(encoding='utf-8')
    start = template.index('<div id="chatgptConnectionPanel"')
    panel = template[start:template.index('<div style=', start)]
    analysis = sample(SCHEMA)
    analysis['summary'] = 'Et barn holder en rød bold i en have. <script>alert(1)</script>'
    analysis['objects'] = [dict(type='ball', label='bold', count=1, attributes=['rød'], confidence=.95, uncertainty=None)]
    response = {'ok': True, 'state': 'completed', 'result': analysis,
                'metadata': dict(model='test-vision', analyzed_at=1791633600, prompt_version='fjordlens-photo-1', schema_version='1'),
                'usage': {'windows': []}}
    posts, errors = [], []
    def handle(route):
        url, method = route.request.url, route.request.method
        if url.endswith('/connection'):
            data = dict(ok=True, csrf='csrf-test', connected=True, email='test@example.com', plan='plus')
        elif url.endswith('/test-models'):
            data = dict(ok=True, models=[dict(id='test-vision', label='Test billedmodel', default=True)])
        elif method == 'POST':
            assert route.request.headers['x-chatgpt-csrf'] == 'csrf-test'
            posts.append(route.request.post_data_buffer)
            data = dict(ok=True, id='job-1', state='running')
        elif method == 'DELETE':
            data = dict(ok=True)
        else:
            data = response
        route.fulfill(content_type='application/json', body=json.dumps(data))
    with sync_playwright() as runtime:
        browser = runtime.chromium.launch()
        page = browser.new_page(viewport={'width': 1440, 'height': 1000})
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.route('https://fjordlens.test/', lambda route: route.fulfill(content_type='text/html',
            body='<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
                 '<body class="view-settings">' + panel))
        page.route('**/api/ai/chatgpt/**', handle)
        page.goto('https://fjordlens.test/')
        for css in ['styles.css', 'redesign.css']:
            page.add_style_tag(path=str(ROOT / 'static' / css))
        for js in ['chatgpt-connection.js', 'chatgpt-analysis.js']:
            page.add_script_tag(path=str(ROOT / 'static' / js))
        expect(page.locator('#chatgptTestBtn')).to_be_enabled()
        page.locator('#chatgptTestBtn').click()
        expect(page.locator('#chatgptTestDialog')).to_be_visible()
        expect(page.locator('#chatgptTestModel')).to_have_value('test-vision')
        expect(page.locator('#chatgptTestRun')).to_be_disabled()
        # Invalid file is rejected before any request.
        page.locator('#chatgptTestImage').set_input_files(dict(name='bad.svg', mimeType='image/svg+xml', buffer=b'<svg/>'))
        expect(page.locator('#chatgptTestError')).to_contain_text('JPG')
        for width in [1440, 390, 320]:
            page.set_viewport_size({'width': width, 'height': 950})
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            assert page.locator('#chatgptTestDialog').evaluate('(el) => el.scrollWidth <= el.clientWidth')
        from test_chatgpt_analysis import image_bytes
        page.locator('#chatgptTestImage').set_input_files(dict(name='test.png', mimeType='image/png', buffer=image_bytes()))
        expect(page.locator('#chatgptTestPreview')).to_be_visible()
        page.locator('#chatgptTestRun').click()
        expect(page.locator('#chatgptTestResult')).to_be_visible()
        expect(page.locator('#chatgptTestSummary')).to_contain_text('<script>alert(1)</script>')
        assert page.locator('#chatgptTestSummary script').count() == 0
        expect(page.locator('#chatgptTestSections')).to_contain_text('bold · antal: 1 · rød')
        expect(page.locator('#chatgptTestPreview')).to_be_visible()
        assert len(posts) == 1 and b'test-vision' in posts[0] and b'80' in posts[0]
        for width in [1440, 390]:
            page.set_viewport_size({'width': width, 'height': 950})
            page.screenshot(path=str(tmp_path / f'chatgpt-analysis-{width}.png'))
            assert page.locator('#chatgptTestDialog').evaluate('(el) => el.scrollWidth <= el.clientWidth')
        page.keyboard.press('Escape')
        expect(page.locator('#chatgptTestDialog')).not_to_be_visible()
        expect(page.locator('#chatgptTestBtn')).to_be_focused()
        page.locator('#chatgptTestBtn').click()
        expect(page.locator('#chatgptTestResult')).not_to_be_visible()
        response.clear(); response.update(ok=True, state='failed', error='Forbrugsgrænsen er nået.')
        page.locator('#chatgptTestImage').set_input_files(dict(name='test.png', mimeType='image/png', buffer=image_bytes()))
        page.locator('#chatgptTestRun').click()
        expect(page.locator('#chatgptTestError')).to_contain_text('Forbrugsgrænsen')
        expect(page.locator('#chatgptTestResult')).not_to_be_visible()
        assert errors == []
        browser.close()
