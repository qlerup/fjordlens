import unittest
from urllib.parse import urlsplit
import test_gallery_navigation_browser as fixtures

@unittest.skipUnless(fixtures.sync_playwright, 'Requires Playwright')
class VideoIntervalBrowserTests(unittest.TestCase):
    setUpClass = classmethod(fixtures.GalleryNavigationBrowserTests.setUpClass.__func__)
    tearDownClass = classmethod(fixtures.GalleryNavigationBrowserTests.tearDownClass.__func__)
    setUp = fixtures.GalleryNavigationBrowserTests.setUp
    tearDown = fixtures.GalleryNavigationBrowserTests.tearDown
    photo_response = fixtures.GalleryNavigationBrowserTests.photo_response
    folder_response = fixtures.GalleryNavigationBrowserTests.folder_response

    def route(self, route):
        path = urlsplit(route.request.url).path
        if path == '/api/faces/status':
            route.fulfill(json={'ok': True, 'video_index': True, 'video_interval_seconds': getattr(self, 'interval', 3), 'video_max_frames': 24})
        elif path == '/api/settings/faces-video':
            if getattr(self, 'fail_save', False):
                route.fulfill(status=500, json={'ok': False})
            else:
                self.interval = route.request.post_data_json['interval_seconds']
                route.fulfill(json={'ok': True, 'interval_seconds': self.interval})
        else:
            fixtures.GalleryNavigationBrowserTests.route(self, route)

    def test_interval_edit_save_error_and_polling(self):
        self.page.evaluate('setView("settings")')
        self.page.locator('.tab-btn[data-tab="ai"]').click()
        self.page.evaluate('pollFacesStatus()')
        field = self.page.locator('#facesVideoInterval')
        self.page.wait_for_function('els.facesVideoInterval.value === "3"')
        for width in (390, 1280):
            self.page.set_viewport_size({'width': width, 'height': 900})
            field.fill('10')
            self.page.evaluate('pollFacesStatus()')
            self.assertEqual(field.input_value(), '10')
            self.page.locator('#facesVideoIntervalSave').click()
            self.page.wait_for_function('!state.facesVideoIntervalSaving && !state.facesVideoIntervalDirty')
            self.assertEqual(self.interval, 10)
        self.fail_save = True
        field.fill('12')
        self.page.locator('#facesVideoIntervalSave').click()
        self.page.wait_for_function('!state.facesVideoIntervalSaving')
        self.assertEqual(field.input_value(), '12')
        self.assertTrue(self.page.evaluate('state.facesVideoIntervalDirty'))
        self.assertTrue(self.page.locator('#facesVideoIntervalFeedback').inner_text())
