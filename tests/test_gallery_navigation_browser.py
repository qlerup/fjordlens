"""Real-browser checks for responsive gallery navigation and incremental pages."""
import io
import json
import os
import unittest
from urllib.parse import urlsplit, parse_qs

from PIL import Image
import test_video_autoplay_settings as fixtures

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None


@unittest.skipUnless(sync_playwright, 'Requires Playwright and Chromium')
class GalleryNavigationBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.playwright = sync_playwright().start()
        options = {'headless': True}
        if os.environ.get('FJORDLENS_TEST_CHROMIUM'):
            options['executable_path'] = os.environ['FJORDLENS_TEST_CHROMIUM']
            options['args'] = ['--no-sandbox', '--disable-dev-shm-usage']
        cls.browser = cls.playwright.chromium.launch(**options)
        image = io.BytesIO()
        Image.new('RGB', (32, 24), 'steelblue').save(image, 'JPEG')
        cls.jpeg = image.getvalue()

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()

    def setUp(self):
        self.fixture = fixtures.VideoAutoplaySettingsTests()
        self.fixture.setUp()
        self.client = self.fixture._authenticated_client()
        self.context = self.browser.new_context(viewport={'width': 390, 'height': 844}, is_mobile=True)
        self.page = self.context.new_page()
        self.pending, self.requests, self.errors = [], [], []
        self.hold_view, self.hold_folders, self.hold_sync = None, False, False
        self.total = 600
        self.excluded_favorites = set()
        self.page.on('pageerror', lambda error: self.errors.append(str(error)))
        self.page.route('**/*', self.route)
        self.page.goto('https://fjordlens.test/', wait_until='networkidle')
        if self.page.locator('#uiDesignIntroModal').is_visible():
            self.page.locator('#uiDesignIntroLater').click()
        self.page.wait_for_function('state.items.length > 0 && !state.photosLoading')

    def tearDown(self):
        for route in self.pending:
            try:
                route.abort()
            except Exception:
                pass  # Already fulfilled or cancelled by navigation.
        self.page.wait_for_timeout(50)
        self.page.unroute_all(behavior='ignoreErrors')
        self.context.close()
        self.fixture.tearDown()
        self.assertEqual(self.errors, [])

    def photo_response(self, route):
        qs = parse_qs(urlsplit(route.request.url).query)
        start = int(qs.get('offset', ['0'])[0])
        size = int(qs.get('limit', [str(self.total)])[0])
        view = qs.get('view', ['timeline'])[0]
        base = {'timeline': 10000, 'kameraer': 20000, 'favorites': 30000, 'mapper': 40000}.get(view, 0)
        indices = [i for i in range(self.total) if view != 'favorites' or i not in self.excluded_favorites]
        if qs.get('sort') == ['date_asc']:
            indices.reverse()
        end = min(len(indices), start + size)
        items = [{'id': base+i, 'filename': f'image-{i}.jpg', 'ext': '.jpg',
                  'favorite': view == 'favorites',
                  'captured_at': f'2026-{9-i//200:02}-15T12:00:00',
                  'thumb_url': '/test/thumb.jpg', 'original_url': '/test/thumb.jpg'} for i in indices[start:end]]
        route.fulfill(content_type='application/json', body=json.dumps({'ok': True, 'items': items,
                      'has_more': end < len(indices), 'next_offset': end, 'total': None}))

    def route(self, route):
        url = urlsplit(route.request.url)
        if url.hostname != 'fjordlens.test':
            route.abort(); return
        self.requests.append(url.path + '?' + url.query)
        if url.path == '/api/photos':
            view = parse_qs(url.query).get('view', [''])[0]
            if view == self.hold_view:
                self.pending.append(route)
            else:
                self.photo_response(route)
        elif url.path.startswith('/api/photos/') and url.path.endswith('/favorite'):
            self.excluded_favorites.add(int(url.path.split('/')[3]) - 30000)
            route.fulfill(json={'ok': True, 'favorite': False})
        elif url.path == '/api/settings/upload-destination':
            if self.hold_folders:
                self.pending.append(route)
            else:
                route.fulfill(json={'ok': True, 'folders': ['Album', 'Second'], 'subdir': ''})
        elif url.path == '/api/upload/folder-sync/status' and self.hold_sync:
            self.pending.append(route)
        elif url.path.startswith('/api/'):
            route.fulfill(json={'ok': True, 'items': [], 'folders': [], 'running': False})
        elif url.path == '/test/thumb.jpg':
            route.fulfill(content_type='image/jpeg', body=self.jpeg)
        else:
            response = self.client.get(url.path + ('?' + url.query if url.query else ''))
            route.fulfill(status=response.status_code, headers=dict(response.headers), body=response.data)
            response.close()

    def test_menu_closes_and_skeleton_is_visible_while_photos_are_pending(self):
        self.hold_view = 'kameraer'
        self.page.evaluate("openDrawer(); document.querySelector('[data-view=kameraer]').click()")
        self.page.wait_for_function("state.view === 'kameraer' && state.photosLoading")
        self.assertFalse(self.page.evaluate("document.body.classList.contains('drawer-open')"))
        self.assertEqual(self.page.locator('#galleryGrid [data-photo-id]').count(), 0)
        self.assertEqual(self.page.locator('#galleryGrid .mapper-ghost-card').count(), 12)
        self.page.wait_for_timeout(50)
        self.hold_view = None
        self.photo_response(self.pending.pop())
        self.page.wait_for_function('state.items.length > 0 && !state.photosLoading')

    def test_all_photo_grids_append_without_replacing_existing_cards(self):
        for view in ('timeline', 'kameraer', 'favorites'):
            with self.subTest(view=view):
                self.page.evaluate('(view) => setView(view)', view)
                initial_count = self.page.evaluate('state.items.length')
                self.page.evaluate("window.originalCard = document.querySelector('#galleryGrid [data-photo-id]')")
                self.page.evaluate('loadPhotos(true)')
                self.assertTrue(self.page.evaluate("originalCard.isConnected && originalCard === document.querySelector('#galleryGrid [data-photo-id]')"))
                self.assertGreater(self.page.locator('#galleryGrid [data-photo-id]').count(), initial_count)
        photo_requests = [parse_qs(urlsplit(r).query) for r in self.requests if r.startswith('/api/photos?')]
        self.assertTrue(all(int(q['limit'][0]) <= 60 and q['browse'] == ['1'] for q in photo_requests))

    def test_gallery_controls_return_immediately_when_leaving_people(self):
        self.page.evaluate("setView('personer')")
        self.assertEqual(self.page.evaluate('els.searchShell.style.display'), 'none')
        self.hold_view = 'kameraer'
        self.page.evaluate("void setView('kameraer')")
        self.assertNotEqual(self.page.evaluate('els.searchShell.style.display'), 'none')
        self.assertFalse(self.page.locator('#peopleMatchScanBtn').is_visible())

    def test_viewer_continues_across_gallery_page_boundaries(self):
        for view in ('timeline', 'kameraer', 'favorites'):
            with self.subTest(view=view):
                self.page.evaluate('(view) => setView(view)', view)
                boundary = self.page.evaluate('state.items.length')
                self.page.evaluate('(boundary) => openViewer(boundary - 1)', boundary)
                self.page.evaluate('nextViewer(1)')
                self.assertEqual(self.page.evaluate('state.selectedIndex'), boundary)
                self.assertGreater(self.page.evaluate('state.items.length'), boundary)
                self.page.evaluate('closeViewer()')

    def test_removing_a_favorite_does_not_skip_the_next_page_first_photo(self):
        self.page.evaluate("setView('favorites')")
        self.page.evaluate('state.selectedId = state.items[0].id; toggleFavorite()')
        self.page.evaluate('loadPhotos(true)')
        ids = self.page.evaluate('state.items.map(item => item.id)')
        self.assertEqual(ids, list(range(30000, 30000 + len(ids))))

    def test_timeline_merges_months_and_keeps_sorted_headers_across_pages(self):
        self.total = 300
        for sort, months in [('date_desc', ['2026-09', '2026-08']), ('date_asc', ['2026-08', '2026-09'])]:
            with self.subTest(sort=sort):
                self.page.evaluate('(sort) => { galleryDataCache.clear(); state.sort = sort; return setView("timeline"); }', sort)
                self.page.evaluate('async () => { while (state.photosHasMore) await loadPhotos(true); }')
                groups = self.page.locator('#galleryGrid .timeline-grid[data-month]')
                self.assertEqual(groups.count(), 2)
                self.assertEqual(groups.evaluate_all('(nodes) => nodes.map(node => node.dataset.month)'), months)
                self.assertEqual(self.page.locator('[data-month="2026-09"] [data-photo-id]').count(), 200)
                self.assertEqual(self.page.locator('[data-month="2026-08"] [data-photo-id]').count(), 100)

    def test_fast_navigation_cancels_the_previous_photo_request(self):
        self.hold_view = 'kameraer'
        self.page.evaluate("void setView('kameraer')")
        self.page.wait_for_timeout(50)
        self.page.evaluate("setView('favorites')")
        self.assertEqual(self.page.evaluate('state.view'), 'favorites')
        self.assertEqual(self.page.evaluate('state.items[0].id'), 30000)
        self.assertFalse(self.page.evaluate('state.photosLoading'))
        self.assertTrue(any('view=kameraer' in r for r in self.requests))

    def test_folder_photos_do_not_wait_for_folder_index_or_disk_sync(self):
        self.hold_folders = self.hold_sync = True
        self.page.evaluate("window.navigationDone = false; void setView('mapper').then(() => navigationDone = true)")
        self.page.wait_for_function('state.items.length > 0 && !state.photosLoading')
        self.assertTrue(self.page.locator('#galleryGrid [data-photo-id]').count() > 0)
        self.assertFalse(self.page.evaluate("document.body.classList.contains('drawer-open')"))
        folder = next(r for r in self.pending if '/upload-destination' in r.request.url)
        self.hold_folders = False
        folder.fulfill(json={'ok': True, 'folders': ['Album', 'Second'], 'subdir': ''})
        self.page.wait_for_function('navigationDone')
        self.assertEqual(self.page.locator('#galleryGrid .folder-card').count(), 2)

    def test_exhausted_mapper_pages_remove_placeholder_cards(self):
        self.total = 27
        self.page.evaluate("setView('mapper')")
        self.page.evaluate('''async () => { while (state.photosHasMore) await loadPhotos(true); }''')
        self.assertEqual(self.page.locator('#galleryGrid [data-photo-id]').count(), 27)
        self.assertEqual(self.page.locator('#galleryGrid .mapper-ghost-card').count(), 0)

    def test_failed_load_removes_loading_placeholders_and_can_be_retried(self):
        self.hold_view = 'kameraer'
        self.page.evaluate("void setView('kameraer')")
        self.page.wait_for_timeout(50)
        self.pending.pop().fulfill(status=503, json={'error': 'temporary'})
        self.page.wait_for_function('!state.photosLoading')
        self.assertEqual(self.page.locator('#galleryGrid .mapper-ghost-card').count(), 0)
        self.hold_view = None
        self.page.evaluate("setView('kameraer')")
        self.assertGreater(self.page.locator('#galleryGrid [data-photo-id]').count(), 0)

    def test_galleries_fetch_five_rows_and_load_more_on_scroll(self):
        for width in (390, 1366):
            self.page.set_viewport_size({'width': width, 'height': 844})
            for view in ('timeline', 'kameraer', 'favorites'):
                with self.subTest(width=width, view=view):
                    self.page.evaluate('galleryDataCache.clear(); window.scrollTo(0, 0)')
                    start = len(self.requests)
                    self.page.evaluate('(view) => setView(view)', view)
                    self.page.wait_for_timeout(200)
                    self.page.wait_for_function('!state.photosLoading')
                    count = self.page.evaluate('state.items.length')
                    self.assertLess(count, self.total)
                    limit = self.page.evaluate("estimateMapperGridMetrics(state.view === 'timeline' ? els.grid.querySelector('.timeline-grid') : null).cols * 5")
                    self.assertLess(limit, 60)
                    requests = [parse_qs(urlsplit(r).query) for r in self.requests[start:] if r.startswith('/api/photos?')]
                    self.assertTrue(requests)
                    self.assertTrue(all(int(q['limit'][0]) == limit for q in requests))
                    self.assertEqual(self.page.locator('#galleryGrid button[data-gallery-sentinel]').count(), 0)
                    self.page.evaluate("window.originalCard = document.querySelector('#galleryGrid [data-photo-id]'); document.querySelector('#galleryGrid [data-gallery-sentinel]').firstElementChild.scrollIntoView()")
                    self.page.wait_for_function('(count) => state.items.length > count', arg=count)
                    self.assertTrue(self.page.evaluate('originalCard.isConnected'))

    def test_gallery_scroll_placeholders_disappear_at_end(self):
        self.total = 53
        for view in ('timeline', 'kameraer', 'favorites'):
            self.page.evaluate('galleryDataCache.clear()')
            self.page.evaluate('(view) => setView(view)', view)
            self.page.evaluate('async () => { while (state.photosHasMore) await loadPhotos(true); }')
            self.assertEqual(self.page.locator('#galleryGrid [data-photo-id]').count(), self.total)
            self.assertEqual(self.page.locator('#galleryGrid .mapper-ghost-card').count(), 0)
