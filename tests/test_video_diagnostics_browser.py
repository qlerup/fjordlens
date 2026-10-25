"""Verify a real media loading failure reaches the diagnostic endpoint."""
import unittest
from pathlib import Path
from urllib.parse import urlsplit

import test_gallery_navigation_browser as fixtures


@unittest.skipUnless(fixtures.sync_playwright, 'Requires Playwright')
class VideoDiagnosticsBrowserTests(unittest.TestCase):
    setUpClass = classmethod(fixtures.GalleryNavigationBrowserTests.setUpClass.__func__)
    tearDownClass = classmethod(fixtures.GalleryNavigationBrowserTests.tearDownClass.__func__)
    setUp = fixtures.GalleryNavigationBrowserTests.setUp
    tearDown = fixtures.GalleryNavigationBrowserTests.tearDown
    photo_response = fixtures.GalleryNavigationBrowserTests.photo_response
    folder_response = fixtures.GalleryNavigationBrowserTests.folder_response

    def route(self, route):
        path = urlsplit(route.request.url).path
        if path == '/test/broken.mp4':
            route.fulfill(status=404, content_type='text/plain', body='Not found')
        elif path == '/test/recoverable.mp4':
            if getattr(self, 'video_available', False):
                route.fulfill(content_type='video/mp4', body=(Path(__file__).parent / 'fixtures/playback.mp4').read_bytes())
            else:
                route.fulfill(status=503, content_type='text/plain', body='Unavailable')
        elif path == '/api/media/playback-error/1':
            self.diagnostic = route.request.post_data_json
            self.report_count += 1
            route.fulfill(json={'ok': True})
        else:
            fixtures.GalleryNavigationBrowserTests.route(self, route)

    def test_failed_video_reports_media_and_http_errors_without_retry_loop(self):
        self.diagnostic = None
        self.report_count = 0
        with self.page.expect_response('**/api/media/playback-error/1'):
            self.page.evaluate("""() => {
                state.items = [{id: 1, filename: 'broken.mp4', is_video: true,
                    original_url: '/test/broken.mp4'}];
                openViewer(0);
            }""")
        self.assertIsNotNone(self.diagnostic)
        self.assertEqual(self.diagnostic['code'], 4)
        self.assertEqual(self.diagnostic['http_status'], 404)
        self.assertEqual(self.diagnostic['content_type'], 'text/plain')
        self.page.evaluate('closeViewer()')
        self.page.wait_for_timeout(100)
        self.assertEqual(self.report_count, 1)

    def test_user_can_reload_a_failed_video_and_continue_to_the_next_video(self):
        self.diagnostic = None
        self.report_count = 0
        with self.page.expect_response('**/api/media/playback-error/1'):
            self.page.evaluate("""() => {
                state.videoAutoplay = true;
                state.items = [1, 2].map(id => ({id, filename: id + '.mp4', is_video: true,
                    original_url: '/test/recoverable.mp4'}));
                openViewer(0);
            }""")
        retry = self.page.locator('#viewerVideoPlayBtn')
        self.assertTrue(retry.is_visible())
        self.assertEqual(retry.get_attribute('data-error-label'), 'Prøv igen')
        self.video_available = True
        retry.click()
        self.page.wait_for_function('!els.viewerVideo.error && els.viewerVideo.currentTime > 0')
        self.assertFalse(retry.is_visible())
        self.page.evaluate('nextViewer(1)')
        self.page.wait_for_function('state.selectedIndex === 1 && !viewerTransitionRunning && !els.viewerVideo.error && els.viewerVideo.currentTime > 0')
        self.assertEqual(self.report_count, 1)
