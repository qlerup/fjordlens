"""Responsive placement and role visibility of the shared work status."""
import unittest
from pathlib import Path

from jinja2 import Template
from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]


class StatusHeaderTests(unittest.TestCase):
    def test_roles_and_responsive_placement(self):
        template = (ROOT / 'templates/index.html').read_text(encoding='utf-8')
        start = template.index('<main class="main">')
        end = template.index('</section>', start) + len('</section>')
        header = Template(template[start:end] + '</main>')
        source = (ROOT / 'static/app.js').read_text(encoding='utf-8')
        placement = source[source.index('function ensureTimelineHeaderActions()'):source.index('function ensureUploadOverlayRefs()')]
        with sync_playwright() as runtime:
            browser = runtime.chromium.launch()
            page = browser.new_page()
            for role in ['user', 'manager', 'admin']:
                page.set_content('<body class="view-mapper">' + header.render(user_role=role))
                self.assertEqual(page.locator('#uploadTopStatus').count(), 0 if role == 'user' else 1)
                if role == 'user':
                    continue
                for css in ['styles.css', 'redesign.css']:
                    page.add_style_tag(path=str(ROOT / 'static' / css))
                page.evaluate('''() => {
                    window.state = {view: 'mapper'};
                    window.els = Object.fromEntries(['uploadTopStatus', 'mapperHeaderActions', 'mapperSearchShell', 'topbar', 'timelineHeaderActions', 'searchShell'].map(id => [id, document.getElementById(id)]));
                    els.sort = document.getElementById('sortSelect');
                    uploadTopStatus.classList.remove('hidden');
                    uploadTopStatusLabel.textContent = 'Konverterer RAW/HEIC/MOV · 14/38 · 37%';
                    uploadTopStatusBar.style.width = '37%';
                }''')
                page.add_script_tag(content=placement)
                for width in [1440, 390, 320, 760, 1440]:
                    page.set_viewport_size({'width': width, 'height': 900})
                    page.evaluate('placeGlobalSearchSortForView()')
                    status = page.locator('#uploadTopStatus')
                    self.assertTrue(status.is_visible())
                    self.assertIn('14/38 · 37%', status.inner_text())
                    anchor = page.locator('#viewTitle' if width <= 760 else '#mapperSearchShell').bounding_box()
                    box = status.bounding_box()
                    self.assertLess(box['y'], anchor['y'] + anchor['height'])
                    self.assertGreater(box['y'] + box['height'], anchor['y'])
                    self.assertLessEqual(box['x'] + box['width'], width)
                    if width <= 760:
                        self.assertGreaterEqual(box['x'], anchor['x'] + anchor['width'])
                    else:
                        self.assertLessEqual(box['x'] + box['width'], anchor['x'])
                page.set_viewport_size({'width': 390, 'height': 900})
                page.evaluate('''() => {
                    placeGlobalSearchSortForView();
                    uploadTopStatus.classList.add('multi');
                    uploadTopProcessRow.classList.remove('hidden');
                    uploadTopProcessRow.innerHTML = '<div class="upload-top-proc"><div class="upload-top-proc-name">Konverterer 37%</div><div class="upload-top-status-progress"><span class="upload-top-status-bar" style="width:37%"></span></div></div>';
                }''')
                self.assertTrue(page.locator('#uploadTopProcessRow .upload-top-status-progress').is_visible())
            browser.close()


if __name__ == '__main__':
    unittest.main()
