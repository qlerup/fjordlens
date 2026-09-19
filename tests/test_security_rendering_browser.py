"""Execute the production rendering expressions in Chromium's HTML parser."""
import re
import unittest
from pathlib import Path

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).parents[1]


class SecurityRenderingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch()
        cls.main = (ROOT / 'static/app.js').read_text(encoding='utf-8')
        cls.shared = (ROOT / 'static/shared.js').read_text(encoding='utf-8')

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()

    def setUp(self):
        self.page = self.browser.new_page()
        self.page.set_content('<div id="usersPanelInner"></div><article id="card"></article>')
        self.page.evaluate('window.injected = false')

    def tearDown(self):
        self.page.close()

    def test_admin_table_treats_existing_hostile_and_ordinary_names_as_text(self):
        # Exercise the actual asynchronous data fetch and complete HTML assembly.
        # Stop before unrelated panel event wiring/settings network requests.
        start = self.main.index('async function renderUsersPanel(){')
        sink = self.main.index('    wrap.innerHTML = `\n', start)
        end = self.main.index('\n    `;', sink) + len('\n    `;')
        render = self.main[start:end] + '\n } catch (error) { throw error; }\n}'
        escape = self.main[self.main.index('function escapeHtml('):self.main.index('\nfunction fmtDate(')]
        self.page.add_script_tag(content=escape + '\nconst tr = value => value;\n' + render)
        for name in ['<img src=x onerror="window.injected=true">', '\"><svg onload="window.injected=true">', 'Anne & Søren "Family"']:
            with self.subTest(name=name):
                self.page.evaluate('''async name => {
                    window.fetch = async () => ({ok:true, text:async()=>JSON.stringify({ok:true,
                        items:[{id:3,username:name,role:'user'}], login_audit:[]})});
                    await renderUsersPanel();
                }''', name)
                self.assertEqual(self.page.locator('td.col-user strong').text_content(), name)
                self.assertEqual(self.page.locator('td.col-user img, td.col-user svg').count(), 0)
                self.assertFalse(self.page.evaluate('window.injected'))

    def test_both_share_card_renderers_escape_text_and_attribute_contexts(self):
        # Both initial and incremental gallery rendering have their own sink.
        helper = self.shared[:self.shared.index('\nconst els =')]
        self.page.add_script_tag(content=helper)
        renderers = re.findall(r"const uploader = .*?card\.innerHTML = .*?;", self.shared, re.S)
        self.assertEqual(len(renderers), 2)
        for renderer in renderers:
            for name in ['<img src=x onerror="window.injected=true">', '\" onmouseover=\"window.injected=true', "O'Brian & family"]:
                with self.subTest(renderer=renderer[:80], name=name):
                    self.page.evaluate('''({code,name}) => {
                        const card = document.getElementById('card');
                        const item = {uploaded_by:name};
                        const thumb = '', selectBadge = '', badge = '';
                        eval(code);
                    }''', {'code': renderer, 'name': name})
                    self.assertEqual(self.page.locator('.uploader-badge').text_content(), name)
                    self.assertEqual(self.page.locator('#card img, #card [onmouseover], #card [onerror]').count(), 0)
                    self.assertFalse(self.page.evaluate('window.injected'))


if __name__ == '__main__':
    unittest.main()
