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
        if urlsplit(route.request.url).path == '/api/cameras':
            route.fulfill(json={'items': [], 'cameras': [
                {'model': 'Camera A', 'count': self.total, 'thumb_url': '/test/thumb.jpg'},
                {'model': 'Camera B', 'count': self.total, 'thumb_url': None}], 'has_more': False})
            return
        start = int(qs.get('offset', ['0'])[0])
        size = int(qs.get('limit', [str(self.total)])[0])
        view = qs.get('view', ['timeline'])[0]
        base = {'timeline': 10000, 'kameraer': 20000, 'favorites': 30000, 'mapper': 40000}.get(view, 0)
        if view == 'kameraer' and qs.get('camera') == ['Camera B']:
            base = 50000
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
        if url.path in ('/api/photos', '/api/cameras'):
            view = parse_qs(url.query).get('view', [''])[0]
            if view == self.hold_view:
                self.pending.append(route)
            else:
                self.photo_response(route)
        elif url.path.startswith('/api/photos/') and url.path.endswith('/favorite'):
            self.excluded_favorites.add(int(url.path.split('/')[3]) - 30000)
            route.fulfill(json={'ok': True, 'favorite': False})
        elif url.path in ('/api/settings/upload-destination', '/api/folder-index'):
            if self.hold_folders:
                self.pending.append(route)
            else:
                self.folder_response(route)
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

    def folder_response(self, route):
        query = parse_qs(urlsplit(route.request.url).query)
        parent = query.get('parent', [''])[0]
        paths = ['Album', 'Second'] if not parent or query.get('tree') == ['1'] else []
        route.fulfill(json={'ok': True, 'folders': paths, 'parent': parent, 'revision': 1,
                            'items': [{'path': p, 'name': p.split('/')[-1], 'previews': ['/test/thumb.jpg']} for p in paths],
                            'indexing': False, 'pending_previews': False})

    def test_empty_photo_page_does_not_flash_empty_while_folder_index_is_pending(self):
        self.total = 0
        self.hold_folders = True
        self.page.evaluate("void setView('mapper')")
        self.page.wait_for_function('!state.photosLoading && state.mapperFoldersLoading')
        self.assertTrue(self.page.evaluate("els.empty.classList.contains('hidden')"))
        self.assertEqual(self.page.locator('#galleryGrid .mapper-ghost-card').count(), 12)
        route = next(r for r in self.pending if '/folder-index' in r.request.url)
        self.hold_folders = False
        self.folder_response(route)
        self.page.wait_for_function('!state.mapperFoldersLoading')
        self.assertEqual(self.page.locator('#galleryGrid .folder-card').count(), 2)
        self.assertTrue(self.page.evaluate("els.empty.classList.contains('hidden')"))

    def test_folder_lookup_failure_shows_retry_instead_of_empty(self):
        self.total = 0
        self.hold_folders = True
        self.page.evaluate("void setView('mapper')")
        self.page.wait_for_function('!state.photosLoading && state.mapperFoldersLoading')
        route = next(r for r in self.pending if '/folder-index' in r.request.url)
        route.fulfill(status=503, json={'ok': False, 'error': 'Midlertidig fejl'})
        self.page.wait_for_function('!state.mapperFoldersLoading')
        self.assertFalse(self.page.evaluate("els.empty.classList.contains('hidden')"))
        self.assertIn('Midlertidig fejl',self.page.evaluate('els.empty.textContent'))
        self.hold_folders = False
        self.page.evaluate("els.empty.querySelector('button').click()")
        self.page.wait_for_function('state.mapperFolders.length === 2 && !state.mapperFoldersLoading')
        self.assertTrue(self.page.evaluate("els.empty.classList.contains('hidden')"))

    def test_index_covers_need_no_extra_preview_metadata_request_and_survive_photo_arrival(self):
        self.hold_view = 'mapper'
        self.page.evaluate("void setView('mapper')")
        self.page.wait_for_function("document.querySelectorAll('#galleryGrid .folder-grid img').length === 2")
        self.page.evaluate("window.savedFolder = document.querySelector('#galleryGrid .folder-card'); window.savedCover = savedFolder.querySelector('img')")
        self.assertFalse(any('/api/folder-previews?' in r for r in self.requests))
        self.hold_view = None
        photo = next(r for r in self.pending if '/api/photos?' in r.request.url and 'view=mapper' in r.request.url)
        self.photo_response(photo)
        self.page.wait_for_function('!state.photosLoading && state.items.length > 0')
        self.assertTrue(self.page.evaluate('savedFolder.isConnected && savedCover.isConnected'))

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
        self.page.wait_for_function('state.cameras.length === 2 && !state.photosLoading')

    def test_all_photo_grids_append_without_replacing_existing_cards(self):
        for view in ('timeline', 'kameraer', 'favorites'):
            with self.subTest(view=view):
                self.page.evaluate("(view) => setView(view, {cameraModel: view === 'kameraer' ? 'Camera A' : null})", view)
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
                self.page.evaluate("(view) => setView(view, {cameraModel: view === 'kameraer' ? 'Camera A' : null})", view)
                boundary = self.page.evaluate('state.items.length')
                self.page.evaluate('(boundary) => openViewer(boundary - 1)', boundary)
                self.page.evaluate('nextViewer(1)')
                self.assertEqual(self.page.evaluate('state.selectedIndex'), boundary)
                self.assertGreater(self.page.evaluate('state.items.length'), boundary)
                self.page.evaluate('closeViewer()')

    def test_removing_a_favorite_does_not_skip_the_next_page_first_photo(self):
        self.page.evaluate("setView('favorites')")
        # This checks sequential cursor adjustment; scroll paging is tested separately.
        # Settle any viewport-triggered page before mutating its result set.
        self.page.evaluate('async () => { photoLoadMoreObserver?.disconnect(); await photosLoadPromise; photoLoadMoreObserver?.disconnect(); }')
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
        folder = next(r for r in self.pending if '/folder-index' in r.request.url)
        self.hold_folders = False
        self.folder_response(folder)
        self.page.wait_for_function('navigationDone')
        self.assertEqual(self.page.locator('#galleryGrid .folder-card').count(), 2)

    def test_folder_cards_are_usable_while_photos_and_covers_are_pending(self):
        self.hold_view = 'mapper'
        self.page.route('**/api/folder-previews?*', lambda route: self.pending.append(route))
        self.page.evaluate("void setView('mapper')")
        self.page.wait_for_function("document.querySelectorAll('#galleryGrid .folder-card').length === 2")
        self.assertTrue(self.page.evaluate('state.photosLoading'))
        self.assertEqual(self.page.locator('#galleryGrid [data-photo-id]').count(), 0)
        self.page.locator('#galleryGrid .folder-card[data-folder="Album"]').click()
        self.page.wait_for_function("state.mapperPath === 'Album'")
        self.assertTrue(self.page.evaluate('state.photosLoading'))
        self.hold_view = None
        self.page.evaluate("setView('favorites')")
        self.assertEqual(self.page.evaluate('state.items[0].id'), 30000)

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
        self.assertEqual(self.page.locator('#galleryGrid .camera-folder').count(), 2)

    def test_galleries_fetch_five_rows_and_load_more_on_scroll(self):
        for width in (390, 1366):
            self.page.set_viewport_size({'width': width, 'height': 844})
            for view in ('timeline', 'kameraer', 'favorites'):
                with self.subTest(width=width, view=view):
                    self.page.evaluate('galleryDataCache.clear(); window.scrollTo(0, 0)')
                    start = len(self.requests)
                    self.page.evaluate("(view) => setView(view, {cameraModel: view === 'kameraer' ? 'Camera A' : null})", view)
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
            self.page.evaluate("(view) => setView(view, {cameraModel: view === 'kameraer' ? 'Camera A' : null})", view)
            self.page.evaluate('async () => { while (state.photosHasMore) await loadPhotos(true); }')
            self.assertEqual(self.page.locator('#galleryGrid [data-photo-id]').count(), self.total)
            self.assertEqual(self.page.locator('#galleryGrid .mapper-ghost-card').count(), 0)

    def test_camera_overview_opens_filtered_album_and_returns_without_folder_actions(self):
        for width in (390, 1366):
            self.page.set_viewport_size({'width': width, 'height': 844})
            self.page.evaluate("setView('kameraer')")
            self.assertEqual(self.page.locator('.camera-folder').count(), 2)
            self.assertEqual(self.page.locator('#galleryGrid [data-photo-id]').count(), 0)
            self.page.locator('.camera-folder[data-camera="Camera A"]').click()
            self.page.wait_for_function("state.cameraModel === 'Camera A' && state.items.length > 0")
            self.assertEqual(self.page.evaluate('state.items[0].id'), 20000)
            self.assertIn('camera=Camera+A', self.page.url)
            self.page.locator('[data-camera-back]').click()
            self.page.wait_for_function('state.cameraModel === null && !state.photosLoading')
            self.assertNotIn('camera=', self.page.url)
            self.page.locator('.camera-folder[data-camera="Camera B"]').click()
            self.page.wait_for_function("state.cameraModel === 'Camera B' && state.items.length > 0")
            self.assertEqual(self.page.evaluate('state.items[0].id'), 50000)
            self.assertFalse(self.page.evaluate('state.mapperEditMode'))
            self.assertFalse(any('/folder-preview' in r for r in self.requests))

    def test_camera_album_survives_reload_and_ignores_a_late_previous_album(self):
        self.page.goto('https://fjordlens.test/?view=kameraer&camera=Camera+B', wait_until='networkidle')
        self.page.wait_for_function("state.cameraModel === 'Camera B' && state.items.length > 0")
        self.assertEqual(self.page.evaluate('state.items[0].id'), 50000)
        self.hold_view = 'kameraer'
        self.page.evaluate("void setView('kameraer', {cameraModel: 'Camera A'})")
        self.page.wait_for_timeout(50)
        self.hold_view = None
        self.page.evaluate("setView('kameraer', {cameraModel: 'Camera B'})")
        self.assertEqual(self.page.evaluate('state.items[0].id'), 50000)
