"""Browser regressions; requires Playwright and Chromium."""
import io
import unittest
from pathlib import Path

from PIL import Image

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None


@unittest.skipUnless(sync_playwright, 'Install playwright to run browser regressions')
class FolderPreviewBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch()
        cls.script = (Path(__file__).resolve().parents[1] / 'static/folder_previews.js').read_text(encoding='utf-8')
        data = io.BytesIO()
        Image.new('RGB', (32, 24), 'blue').save(data, 'JPEG', progressive=True)
        cls.jpeg = data.getvalue()

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()

    def setUp(self):
        self.context = self.browser.new_context(viewport={'width': 390, 'height': 844}, is_mobile=True)
        self.page = self.context.new_page()
        self.requests = []
        self.page.route('**/thumb/**', lambda route: self.requests.append(route))
        self.page.set_content('<style>article{height:220px}</style><article id="card"><div class="folder-grid"></div></article>')
        self.page.add_script_tag(content=self.script)

    def tearDown(self):
        for route in self.requests:
            try:
                route.abort()
            except Exception:
                pass  # Already fulfilled or aborted by the test.
        self.page.unroute_all(behavior='ignoreErrors')
        self.context.close()

    def wait_requests(self, count):
        for _ in range(100):
            if len(self.requests) >= count:
                return
            self.page.wait_for_timeout(20)
        self.fail(f'Expected {count} requests, got {len(self.requests)}')

    def finish(self, route):
        route.fulfill(content_type='image/jpeg', body=self.jpeg)

    def test_mosaic_appears_only_when_all_four_thumbnails_are_decoded(self):
        self.page.evaluate("FjordLensFolderPreviews.watch(card, () => [1,2,3,4].map(n => `https://test/thumb/${n}`))")
        self.wait_requests(4)
        for request in self.requests[:3]:
            self.finish(request)
        self.page.wait_for_timeout(100)
        self.assertEqual(self.page.locator('.folder-grid img').count(), 0)
        self.finish(self.requests[3])
        self.page.wait_for_function("document.querySelectorAll('.folder-grid img').length === 4")
        self.assertTrue(self.page.evaluate("Array.from(document.querySelectorAll('.folder-grid img')).every(i => i.complete && i.naturalWidth === 32)"))

    def test_failed_thumbnail_does_not_block_the_cover(self):
        self.page.evaluate("FjordLensFolderPreviews.watch(card, () => [1,2].map(n => `https://test/thumb/${n}`))")
        self.wait_requests(2)
        self.requests[0].abort()
        self.finish(self.requests[1])
        self.page.wait_for_function("document.querySelectorAll('.folder-grid.v1 img').length === 1")

    def test_offscreen_folders_wait_until_the_user_scrolls(self):
        self.page.evaluate('''() => {
          card.style.marginTop = '4000px';
          window.loads = 0;
          FjordLensFolderPreviews.watch(card, () => { loads++; return ['https://test/thumb/1']; });
        }''')
        self.page.wait_for_timeout(100)
        self.assertEqual(self.page.evaluate('loads'), 0)
        self.page.locator('#card').scroll_into_view_if_needed()
        self.wait_requests(1)
        self.assertEqual(self.page.evaluate('loads'), 1)

    def test_transfer_limit_and_navigation_cancel_obsolete_covers(self):
        self.page.evaluate('''() => {
          for (let i=0;i<3;i++) {
            const next = card.cloneNode(true); next.removeAttribute('id'); document.body.append(next);
            FjordLensFolderPreviews.render(next, [0,1,2,3].map(n => `https://test/thumb/${i}-${n}`));
          }
        }''')
        self.wait_requests(6)
        self.page.wait_for_timeout(100)
        self.assertEqual(len(self.requests), 6)
        self.page.evaluate('''() => {
          FjordLensFolderPreviews.reset();
          document.body.replaceChildren(card);
          FjordLensFolderPreviews.render(card, ['https://test/thumb/new']);
        }''')
        self.wait_requests(7)
        self.assertTrue(self.requests[-1].request.url.endswith('/new'))
        self.finish(self.requests[-1])
        self.page.wait_for_function("document.querySelectorAll('.folder-grid img').length === 1")

    def test_metadata_is_batched_deduplicated_and_retries_after_failure(self):
        result = self.page.evaluate('''async () => {
          let calls = [];
          const load = FjordLensFolderPreviews.createBatchLoader(async keys => {
            calls.push(keys); return Object.fromEntries(keys.map(key => [key, [key + '.jpg']]));
          });
          const results = await Promise.all([...Array.from({length: 40}, (_, i) => load(String(i))), load('0')]);
          let failures = 0;
          const retry = FjordLensFolderPreviews.createBatchLoader(async () => {
            if (++failures === 1) throw Error('offline'); return {test: ['ok']};
          });
          await retry('test').catch(() => {});
          await new Promise(resolve => setTimeout(resolve, 0));
          return {calls, results, retried: await retry('test')};
        }''')
        self.assertEqual([len(batch) for batch in result['calls']], [16, 16, 8])
        self.assertEqual(result['results'][0], result['results'][-1])
        self.assertEqual(result['retried'], ['ok'])

    def test_real_pages_render_folders_before_previews_and_use_the_shared_loader(self):
        import json
        from urllib.parse import urlsplit, parse_qs
        from test_video_autoplay_settings import VideoAutoplaySettingsTests

        fixture = VideoAutoplaySettingsTests()
        fixture.setUp()
        fixture._add_share()
        client = fixture._authenticated_client()
        try:
            for shared in (False, True):
                with self.subTest(shared=shared):
                    context = self.browser.new_context(viewport={'width': 390, 'height': 844}, is_mobile=True)
                    page = context.new_page()
                    pending, batches, errors = [], [], []
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    def route_request(route):
                        url = urlsplit(route.request.url)
                        if url.hostname != 'fjordlens.test':
                            route.abort()
                        elif url.path == '/api/folder-previews':
                            pending.append(route)
                            batches.append(parse_qs(url.query)['folders'])
                        elif url.path.startswith('/test/thumb/'):
                            route.fulfill(content_type='image/jpeg', body=self.jpeg)
                        elif url.path == '/api/photos' or url.path.endswith('/photos') and url.path.startswith('/api/share/'):
                            route.fulfill(content_type='application/json', body=json.dumps(dict(ok=True, items=[], folders=[], total=0, has_more=False, next_offset=0)))
                        else:
                            response = client.open(url.path + ('?' + url.query if url.query else ''), method=route.request.method,
                                                   data=route.request.post_data, content_type=route.request.headers.get('content-type'))
                            route.fulfill(status=response.status_code, headers=dict(response.headers), body=response.data)
                            response.close()
                    page.route('**/*', route_request)
                    page.goto('https://fjordlens.test/' + ('s/video-share' if shared else ''), wait_until='networkidle')
                    if not shared and page.locator('#uiDesignIntroModal').is_visible():
                        page.locator('#uiDesignIntroLater').click()
                    page.evaluate('''async shared => {
                      const folders = Array.from({length: 60}, (_, i) => `Folder${String(i).padStart(2, '0')}`);
                      state.items = [];
                      if (shared) {
                        state.folders = folders.map(path => ({path, count: 4, previews: [1,2,3,4].map(i => `/test/thumb/${path}-${i}`)}));
                        renderGrid();
                      } else {
                        state.view = 'mapper'; state.mapperPath = ''; state.mapperFolders = folders;
                        await loadPhotos(false);
                      }
                    }''', shared)
                    # loadPhotos must resolve and all names must be present while
                    # folder metadata is deliberately still blocked on the network.
                    self.assertEqual(page.locator('.folder-card').count(), 60)
                    if not shared:
                        for _ in range(100):
                            if pending:
                                break
                            page.wait_for_timeout(20)
                        self.assertTrue(pending)
                        self.assertEqual(page.locator('.folder-grid img').count(), 0)
                        for route in pending[:]:
                            folders = parse_qs(urlsplit(route.request.url).query)['folders']
                            route.fulfill(content_type='application/json', body=json.dumps({'items': {
                                folder: [f'/test/thumb/{folder}-{i}' for i in range(4)] for folder in folders}}))
                        self.assertLess(len(batches), 4)
                        self.assertLess(sum(map(len, batches)), 60)
                    page.wait_for_function("document.querySelector('.folder-grid img')?.naturalWidth > 0")
                    self.assertEqual(page.locator('.folder-grid').first.locator('img').count(), 4)
                    self.assertEqual(errors, [])
                    for route in pending:
                        try:
                            route.abort()
                        except Exception:
                            pass
                    page.unroute_all(behavior='ignoreErrors')
                    context.close()
        finally:
            fixture.tearDown()


if __name__ == '__main__':
    unittest.main()
