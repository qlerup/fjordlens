import unittest
from urllib.parse import urlsplit, parse_qs
import test_gallery_navigation_browser as fixtures


@unittest.skipUnless(fixtures.sync_playwright, 'Requires Playwright')
class PersonSearchBrowserTests(unittest.TestCase):
    setUpClass = classmethod(fixtures.GalleryNavigationBrowserTests.setUpClass.__func__)
    tearDownClass = classmethod(fixtures.GalleryNavigationBrowserTests.tearDownClass.__func__)
    setUp = fixtures.GalleryNavigationBrowserTests.setUp
    tearDown = fixtures.GalleryNavigationBrowserTests.tearDown
    photo_response = fixtures.GalleryNavigationBrowserTests.photo_response
    folder_response = fixtures.GalleryNavigationBrowserTests.folder_response

    def route(self, route):
        url = urlsplit(route.request.url)
        if url.path == '/api/people/suggest':
            prefix = parse_qs(url.query).get('q', [''])[0].lower()
            names = ['Christian Hansen', 'Christina', 'Clara']
            route.fulfill(json={'items': [{'id': i+1, 'name': name} for i, name in enumerate(names)
                                         if name.lower().startswith(prefix)], 'has_more': False})
        else:
            fixtures.GalleryNavigationBrowserTests.route(self, route)

    def test_dropdown_selection_and_filename_only_search_on_enter(self):
        self.page.evaluate('expandSearchField(true)')
        field = self.page.locator('#searchInput')
        initial_requests = len([url for url in self.requests if url.startswith('/api/photos?')])
        field.press_sequentially('@')
        self.page.wait_for_function('document.querySelectorAll(".person-search-option").length === 3')
        field.press('ControlOrMeta+A')
        field.press_sequentially('@Ch')
        self.page.wait_for_function('document.querySelectorAll(".person-search-option").length === 2')
        self.assertEqual(self.page.evaluate('state.q'), '')
        self.page.get_by_role('option', name='Christian Hansen', exact=True).click()
        self.assertEqual(field.input_value(), '@"Christian Hansen" ')
        self.assertEqual(self.page.evaluate('state.q'), '')
        field.press_sequentially('IMG_1')
        self.assertEqual(self.page.evaluate('state.q'), '')
        self.assertEqual(len([url for url in self.requests if url.startswith('/api/photos?')]), initial_requests)
        field.press('Enter')
        self.page.wait_for_function('state.q.includes("IMG_1") && !state.photosLoading')
        requests = [parse_qs(urlsplit(url).query) for url in self.requests if url.startswith('/api/photos?')]
        self.assertTrue(any(q.get('person') == ['1'] and q.get('q') == ['IMG_1'] for q in requests))

    def test_keyboard_selection_escape_and_desktop_layout(self):
        self.page.set_viewport_size({'width': 1280, 'height': 900})
        self.page.evaluate('expandSearchField(true)')
        field = self.page.locator('#searchInput')
        field.press('ControlOrMeta+A')
        field.press_sequentially('@Ch')
        self.page.wait_for_function('document.querySelectorAll(".person-search-option").length === 2')
        field.press('ArrowDown')
        field.press('Enter')
        self.assertEqual(field.input_value(), '@"Christina" ')
        self.assertEqual(self.page.evaluate('state.q'), '')
        field.press_sequentially('@C')
        self.page.wait_for_function('!document.getElementById("person-search-suggestions").hidden')
        field.press('Escape')
        self.assertTrue(self.page.locator('#person-search-suggestions').is_hidden())
        field.fill('filename')
        field.press('Enter')
        self.page.wait_for_function('state.q === "filename" && !state.photosLoading')

    def test_mapper_input_uses_same_mentions_and_keeps_draft(self):
        self.page.evaluate('setView("mapper")')
        self.page.wait_for_function('state.view === "mapper" && !state.photosLoading')
        self.page.evaluate('els.mapperSearchShell.classList.add("expanded"); els.mapperSearchInput.focus()')
        field = self.page.locator('#mapperSearchInput')
        field.press_sequentially('@Cl')
        self.page.get_by_role('option', name='Clara', exact=True).click()
        self.assertEqual(self.page.locator('#searchInput').input_value(), '@"Clara" ')
        self.assertEqual(self.page.evaluate('state.q'), '')
        field.press('Enter')
        self.page.wait_for_function('state.q.includes("Clara") && !state.photosLoading')
        requests = [parse_qs(urlsplit(url).query) for url in self.requests if url.startswith('/api/photos?')]
        self.assertTrue(any(q.get('person') == ['3'] and q.get('view') == ['mapper'] for q in requests))
