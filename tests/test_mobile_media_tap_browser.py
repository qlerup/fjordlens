"""A single touch opens gallery media without a hover step or selection delay."""
import unittest

import test_gallery_navigation_browser as fixtures


@unittest.skipUnless(fixtures.sync_playwright, 'Requires Playwright')
class MobileMediaTapBrowserTests(unittest.TestCase):
    setUpClass = classmethod(fixtures.GalleryNavigationBrowserTests.setUpClass.__func__)
    tearDownClass = classmethod(fixtures.GalleryNavigationBrowserTests.tearDownClass.__func__)
    tearDown = fixtures.GalleryNavigationBrowserTests.tearDown
    route = fixtures.GalleryNavigationBrowserTests.route
    photo_response = fixtures.GalleryNavigationBrowserTests.photo_response
    folder_response = fixtures.GalleryNavigationBrowserTests.folder_response

    def setUp(self):
        fixtures.GalleryNavigationBrowserTests.setUp(self)
        self.context.close()
        self.context = self.browser.new_context(viewport={'width': 390, 'height': 844}, is_mobile=True, has_touch=True)
        self.page = self.context.new_page()
        self.page.on('pageerror', lambda error: self.errors.append(str(error)))
        self.page.route('**/*', self.route)
        self.page.goto('https://fjordlens.test/', wait_until='networkidle')
        if self.page.locator('#uiDesignIntroModal').is_visible():
            self.page.locator('#uiDesignIntroLater').click()
        self.page.wait_for_function('state.items.length > 0 && !state.photosLoading')

    def setup_cards(self, view='mapper'):
        self.page.evaluate("""view => {
            state.view = view;
            state.mapperEditMode = false;
            state.mapperPath = 'Album';
            state.photosHasMore = false;
            state.viewerItems = null;
            state.items = [false, true].map((is_video, index) => ({
                id: index + 1, filename: is_video ? 'video.mp4' : 'photo.jpg',
                original_url: '/test/thumb.jpg', thumb_url: '/test/thumb.jpg', is_video,
            }));
            els.grid.innerHTML = '';
            state.items.forEach(appendCard);
            window.openedItems = [];
            window.originalOpenViewer ||= openViewer;
            openViewer = (...args) => { openedItems.push(args[0]); originalOpenViewer(...args); };
        }""", view)

    def test_one_tap_opens_each_photo_and_video_in_folders_and_timeline(self):
        for view in ('mapper', 'timeline'):
            self.setup_cards(view)
            for index in (0, 1):
                card = self.page.locator(f'#galleryGrid [data-photo-id="{index + 1}"]')
                icon = card.locator('.info-icon-overlay')
                self.assertEqual(icon.evaluate('el => el.style.opacity'), '1')
                card.tap()
                self.assertTrue(self.page.locator('#viewer').is_visible())
                self.assertEqual(self.page.evaluate('state.selectedIndex'), index)
                self.page.evaluate('closeViewer()')
            self.assertEqual(self.page.evaluate('openedItems'), [0, 1])

    def test_selection_mode_keeps_taps_for_selection(self):
        self.setup_cards()
        self.page.evaluate('setMapperEditMode(true)')
        self.page.locator('#galleryGrid [data-photo-id="1"]').tap()
        self.assertFalse(self.page.locator('#viewer').is_visible())
        self.assertTrue(self.page.evaluate('state.mapperSelectedPhotoIds.has(1)'))

    def test_desktop_still_reveals_info_on_mouse_hover(self):
        self.context.close()
        self.context = self.browser.new_context(viewport={'width': 1280, 'height': 900})
        self.page = self.context.new_page()
        self.page.on('pageerror', lambda error: self.errors.append(str(error)))
        self.page.route('**/*', self.route)
        self.page.goto('https://fjordlens.test/', wait_until='networkidle')
        if self.page.locator('#uiDesignIntroModal').is_visible():
            self.page.locator('#uiDesignIntroLater').click()
        self.page.mouse.move(0, 0)
        self.setup_cards('timeline')
        self.page.mouse.move(0, 0)
        card = self.page.locator('#galleryGrid [data-photo-id="1"]')
        self.assertEqual(card.locator('.info-icon-overlay').evaluate('el => el.style.opacity'), '0')
        card.hover()
        self.assertEqual(card.locator('.info-icon-overlay').evaluate('el => el.style.opacity'), '1')
        card.click()
        self.assertTrue(self.page.locator('#viewer').is_visible())
