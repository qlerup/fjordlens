"""Browser regressions: pip install playwright && playwright install chromium.

Run with: python -m unittest discover -s tests -p test_viewer_images.py
"""

import io
import unittest
from pathlib import Path

from PIL import Image

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None


@unittest.skipUnless(sync_playwright, "Install playwright to run browser regressions")
class ViewerImageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch()
        cls.script = (Path(__file__).resolve().parents[1] / "static" / "media_preloader.js").read_text(
            encoding="utf-8"
        )

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()

    def setUp(self):
        self.context = self.browser.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
        self.page = self.context.new_page()
        self.pending = {}
        self.page.route("https://viewer.test/**", self.route)
        self.page.goto("https://viewer.test/")
        self.page.add_script_tag(content=self.script)
        self.page.evaluate("""() => {
          window.current = document.querySelector('img');
          window.ready = [];
          window.preloader = FjordLensMediaPreloader.create({ahead: 1, behind: 1});
          window.presenter = FjordLensMediaPreloader.createImagePresenter({
            getNode: () => current,
            setNode: node => { current = node; },
            preloader,
            onReady: item => ready.push(item.id),
          });
          window.items = ['a', 'b', 'c'].map(id => ({
            id, original_url: '/' + id + '.jpg', thumb_url: '/' + id + '-thumb.jpg',
          }));
        }""")

    def tearDown(self):
        self.page.evaluate("preloader.clear(); presenter.clear()")
        self.page.wait_for_timeout(30)
        for routes in list(self.pending.values()):
            for route in routes:
                route.abort()
        self.pending.clear()
        self.page.unroute_all(behavior="ignoreErrors")
        self.context.close()

    def route(self, route):
        path = route.request.url.rsplit("/", 1)[-1]
        if not path:
            route.fulfill(content_type="text/html", body='<img id="photo" alt="" style="width:300px">')
        elif "-thumb" in path:
            self.fulfill_image(route, path, size=(12, 8))
        else:
            self.pending.setdefault(path, []).append(route)

    def fulfill_image(self, route, path, size=(600, 400)):
        colors = {"a": "red", "b": "green", "c": "blue"}
        data = io.BytesIO()
        Image.new("RGB", size, colors[path[0]]).save(data, "JPEG")
        route.fulfill(content_type="image/jpeg", body=data.getvalue())

    def release(self, path):
        for _ in range(100):
            if self.pending.get(path):
                break
            self.page.wait_for_timeout(10)
        self.assertTrue(self.pending.get(path), f"No request for {path}")
        for route in self.pending.pop(path):
            self.fulfill_image(route, path)

    def show(self, index):
        self.page.evaluate("index => presenter.show(items[index])", index)

    def wait_image(self, path, width):
        self.page.wait_for_function(
            "([path, width]) => current.getAttribute('src') === path && current.complete && current.naturalWidth === width",
            arg=[path, width],
        )

    def test_new_photo_uses_its_thumbnail_without_reusing_previous_pixels(self):
        self.show(0)
        self.release("a.jpg")
        self.wait_image("/a.jpg", 600)
        self.page.evaluate("window.old = current")
        self.show(1)
        self.assertTrue(self.page.evaluate("current !== old && !old.isConnected"))
        self.wait_image("/b-thumb.jpg", 12)
        self.release("b.jpg")
        self.wait_image("/b.jpg", 600)

    def test_late_decode_cannot_replace_a_newer_photo_or_a_reopened_viewer(self):
        self.page.evaluate("""() => {
          const decode = HTMLImageElement.prototype.decode;
          HTMLImageElement.prototype.decode = function() {
            if (this.getAttribute('src') === '/a.jpg') {
              return new Promise(resolve => { window.finishOldDecode = resolve; });
            }
            return decode.call(this);
          };
        }""")
        self.show(0)
        self.release("a.jpg")
        self.page.wait_for_function("typeof finishOldDecode === 'function'")
        self.show(1)
        self.release("b.jpg")
        self.wait_image("/b.jpg", 600)
        self.page.evaluate("presenter.clear(); presenter.show(items[2]); finishOldDecode()")
        self.wait_image("/c-thumb.jpg", 12)
        self.release("c.jpg")
        self.wait_image("/c.jpg", 600)

    def test_closing_or_switching_to_video_invalidates_pending_photo(self):
        self.show(0)
        self.wait_image("/a-thumb.jpg", 12)
        self.page.evaluate("presenter.clear(); ready.length = 0")
        self.release("a.jpg")
        self.page.wait_for_timeout(100)
        self.assertTrue(self.page.evaluate("!current.hasAttribute('src') && ready.length === 0"))

    def test_loaded_swipe_preview_is_promoted_without_thumbnail_downgrade(self):
        self.show(0)
        self.page.evaluate("""() => {
          window.preview = new Image();
          preview.src = '/b.jpg';
          preview.style.cssText = 'position:absolute;z-index:1;width:100%';
          document.body.append(preview);
        }""")
        self.release("b.jpg")
        self.page.wait_for_function("preview.complete && preview.naturalWidth > 0")
        self.page.evaluate("presenter.show(items[1], preview)")
        self.assertTrue(self.page.evaluate("current === preview && current.id === 'photo' && current.style.width === '300px'"))
        self.wait_image("/b.jpg", 600)
        self.release("a.jpg")
        self.page.wait_for_timeout(100)
        self.wait_image("/b.jpg", 600)

    def test_preloaded_image_survives_cache_eviction_and_viewer_close(self):
        self.page.evaluate("preloader.update(items, 0)")
        self.release("b.jpg")
        self.page.wait_for_timeout(100)
        self.show(1)
        self.wait_image("/b.jpg", 600)
        self.page.evaluate("preloader.update(items, 1); preloader.clear()")
        self.wait_image("/b.jpg", 600)

    def test_failed_full_image_keeps_the_new_thumbnail(self):
        self.show(1)
        self.wait_image("/b-thumb.jpg", 12)
        for route in self.pending.pop("b.jpg"):
            route.abort()
        self.page.wait_for_timeout(100)
        self.wait_image("/b-thumb.jpg", 12)

    def test_cached_navigation_does_not_restart_the_design_entrance_animation(self):
        root = Path(__file__).resolve().parents[1]
        for name in ("styles.css", "redesign.css"):
            self.page.add_style_tag(content=(root / "static" / name).read_text(encoding="utf-8"))
        self.page.evaluate("current.id = 'viewerImg'")
        self.show(0)
        self.release("a.jpg")
        self.wait_image("/a.jpg", 600)
        self.page.wait_for_timeout(550)
        self.page.evaluate("preloader.getImage(items[1])")
        self.release("b.jpg")
        self.page.wait_for_timeout(50)
        self.show(1)
        frames = self.page.evaluate("""async () => {
          const frames = [];
          for (let i = 0; i < 8; i++) {
            await new Promise(requestAnimationFrame);
            const style = getComputedStyle(current);
            frames.push({opacity: Number(style.opacity), transform: style.transform});
          }
          return frames;
        }""")
        self.assertTrue(all(frame["opacity"] == 1 for frame in frames), frames)
        self.assertTrue(all(frame["transform"] in ("none", "matrix(1, 0, 0, 1, 0, 0)") for frame in frames), frames)

    def test_switching_to_video_preserves_the_cached_photo(self):
        self.show(0)
        self.release("a.jpg")
        self.wait_image("/a.jpg", 600)
        self.show(0)
        self.page.evaluate("window.cached = current; presenter.clear()")
        self.show(0)
        self.assertTrue(self.page.evaluate("current === cached"))
        self.wait_image("/a.jpg", 600)

    def test_ten_each_way_window_only_loads_one_new_photo_per_step(self):
        result = self.page.evaluate("""async () => {
          // Track cache ownership and decode requests without issuing 30 downloads.
          window.preloader.clear();
          const NativeImage = window.Image;
          const created = [];
          window.Image = function() {
            const node = document.createElement('img');
            let source = '';
            Object.defineProperty(node, 'src', {
              get: () => source,
              set: value => { source = value; },
            });
            const removeAttribute = node.removeAttribute.bind(node);
            node.removeAttribute = name => {
              if (name === 'src') source = '';
              removeAttribute(name);
            };
            node.decode = () => { node.decoded = true; return Promise.resolve(); };
            created.push(node);
            return node;
          };
          const list = Array.from({length: 40}, (_, i) => ({original_url: `/photo-${i}.jpg`}));
          const cache = FjordLensMediaPreloader.create();
          const settle = () => new Promise(resolve => setTimeout(resolve, 400));
          cache.update(list, 15);
          await settle();
          const first = created.map(node => node.src).sort();
          const initialCount = created.length;
          const selected = cache.getImage(list[16]);
          cache.update(list, 16);
          await settle();
          const afterForward = created.filter(node => node.src).map(node => node.src).sort();
          const forwardCount = created.length;
          const sameSelected = cache.getImage(list[16]) === selected;
          cache.update(list, 15);
          await settle();
          const afterBack = created.filter(node => node.src).map(node => node.src).sort();
          const backCount = created.length;
          const decoded = created.every(node => node.decoded);
          cache.clear();
          const released = created.every(node => !node.src);
          window.Image = NativeImage;
          return {first, initialCount, afterForward, forwardCount, sameSelected, afterBack, backCount, decoded, released};
        }""")
        self.assertEqual(result["first"], sorted(f"/photo-{i}.jpg" for i in range(5, 26)))
        self.assertEqual(result["afterForward"], sorted(f"/photo-{i}.jpg" for i in range(6, 27)))
        self.assertEqual(result["afterBack"], result["first"])
        self.assertEqual((result["initialCount"], result["forwardCount"], result["backCount"]), (21, 22, 23))
        self.assertTrue(result["sameSelected"] and result["decoded"] and result["released"])


if __name__ == "__main__":
    unittest.main()
