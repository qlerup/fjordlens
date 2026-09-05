"""Run with python -m unittest discover -s tests -p test_viewer_zoom.py.

Requires playwright and its Chromium browser, like test_viewer_images.py.
"""
import base64
import io
import unittest
from pathlib import Path

from PIL import Image

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None


@unittest.skipUnless(sync_playwright, "Install playwright to run browser regressions")
class ViewerZoomTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch()
        cls.script = (Path(__file__).resolve().parents[1] / "static/viewer_zoom.js").read_text(encoding="utf-8")

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()

    def setUp(self):
        self.context = self.browser.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
        self.page = self.context.new_page()
        data = io.BytesIO()
        Image.new("RGB", (600, 400), "green").save(data, "PNG")
        source = base64.b64encode(data.getvalue()).decode()
        self.page.set_content(f'''<meta name="viewport" content="width=device-width,initial-scale=1">
          <style>body{{margin:0}} #viewer{{position:fixed;inset:0;display:flex;align-items:center;justify-content:center;overflow:hidden;touch-action:none}}
          img{{width:100vw;height:100vh;object-fit:contain}} button{{position:absolute;top:0;z-index:5}}</style>
          <div id="viewer"><img id="viewerImg" src="data:image/png;base64,{source}"><button>Close</button></div>''')
        self.page.add_script_tag(content=self.script)
        self.page.evaluate('''() => {
          window.viewer = document.querySelector('#viewer');
          window.current = document.querySelector('img');
          window.enabled = true;
          window.swipes = 0;
          window.cancelled = 0;
          window.clicks = 0;
          window.started = false;
          window.zoom = FjordLensViewerZoom.create({viewer, getImage: () => current,
            isEnabled: () => enabled, onGestureStart: () => { cancelled++; started = false; }});
          viewer.addEventListener('touchstart', () => { started = true; });
          viewer.addEventListener('touchend', () => { if (started) swipes++; started = false; });
          viewer.querySelector('button').onclick = () => { clicks++; };
          window.touch = (type, points) => {
            const touches = points.map(([identifier, clientX, clientY]) => new Touch({identifier, target: current, clientX, clientY}));
            current.dispatchEvent(new TouchEvent(type, {touches, targetTouches: touches, changedTouches: touches, bubbles:true, cancelable:true}));
          };
        }''')
        self.page.wait_for_function("current.complete && current.naturalWidth > 0")

    def tearDown(self):
        self.context.close()

    def touch(self, event, points):
        self.page.evaluate("([event, points]) => touch(event, points)", [event, points])

    def pinch(self, scale=2):
        self.touch("touchstart", [[1, 175, 422]])
        self.touch("touchstart", [[1, 175, 422], [2, 215, 422]])
        self.touch("touchmove", [[1, 195 - 20 * scale, 422], [2, 195 + 20 * scale, 422]])

    def transform(self):
        return self.page.evaluate("(() => { const m = new DOMMatrix(getComputedStyle(current).transform); return {scale:m.a, x:m.e, y:m.f}; })()")

    def test_pinch_and_pan_are_identical_for_both_viewer_ids(self):
        for image_id in ("viewerImg", "shareViewerImg"):
            with self.subTest(image_id=image_id):
                self.page.evaluate("id => { zoom.reset(); current.id = id; }", image_id)
                self.pinch()
                self.assertAlmostEqual(self.transform()["scale"], 2)
                self.touch("touchend", [[1, 155, 422]])
                self.touch("touchmove", [[1, 350, 800]])
                self.assertEqual(self.transform(), {"scale": 2, "x": 195, "y": 0})
                self.touch("touchend", [])
                self.assertEqual(self.page.evaluate("swipes"), 0)

    def test_zoom_out_does_not_swipe_until_all_fingers_are_released(self):
        self.pinch()
        self.touch("touchmove", [[1, 185, 422], [2, 205, 422]])
        self.touch("touchend", [[1, 185, 422]])
        self.touch("touchmove", [[1, 10, 422]])
        self.touch("touchend", [])
        self.assertFalse(self.page.evaluate("zoom.isActive()"))
        self.assertEqual(self.page.evaluate("swipes"), 0)
        self.touch("touchstart", [[1, 300, 422]])
        self.touch("touchmove", [[1, 50, 422]])
        self.touch("touchend", [])
        self.assertEqual(self.page.evaluate("swipes"), 1)

    def test_scale_limit_and_pan_bounds(self):
        self.pinch(8)
        self.assertEqual(self.transform()["scale"], 5)
        self.touch("touchend", [])
        self.touch("touchstart", [[1, 195, 422]])
        self.touch("touchmove", [[1, 2000, 2000]])
        self.assertEqual(self.transform(), {"scale": 5, "x": 780, "y": 228})

    def test_reset_for_new_photo_close_or_rotation_restores_normal_view(self):
        self.pinch()
        self.page.evaluate("zoom.reset()")
        self.assertEqual(self.transform(), {"scale": 1, "x": 0, "y": 0})
        self.assertFalse(self.page.evaluate("viewer.classList.contains('viewer-zoomed')"))
        self.pinch()
        self.page.evaluate("window.dispatchEvent(new Event('resize'))")
        self.assertFalse(self.page.evaluate("zoom.isActive()"))

    def test_cancelled_touch_and_controls_do_not_navigate(self):
        self.pinch()
        self.touch("touchcancel", [])
        self.assertFalse(self.page.evaluate("zoom.isActive()"))
        self.assertEqual(self.page.evaluate("swipes"), 0)
        self.pinch()
        self.touch("touchend", [])
        self.page.locator("button").click()
        self.assertEqual(self.page.evaluate("clicks"), 1)

    def test_disabled_zoom_leaves_video_and_desktop_gestures_alone(self):
        self.page.evaluate("enabled = false")
        self.pinch()
        self.assertFalse(self.page.evaluate("zoom.isActive()"))
        self.assertEqual(self.transform()["scale"], 1)


if __name__ == "__main__":
    unittest.main()
