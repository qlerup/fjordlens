"""Exercise the real context-menu/dialog code with controlled API responses."""
import unittest
from pathlib import Path
from playwright.sync_api import sync_playwright, expect


class FolderPrivacyBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pw=sync_playwright().start()
        cls.browser=cls.pw.chromium.launch()
        source=Path('static/app.js').read_text(encoding='utf-8')
        cls.script=source[source.index('function mapperContextMenuItemsForFolder('):source.index('async function openMapperMoveDialog(')]

    @classmethod
    def tearDownClass(cls):
        cls.browser.close();cls.pw.stop()

    def setUp(self):
        self.page=self.browser.new_page(viewport={'width':1280,'height':900})
        self.page.set_content('<html lang="da"><body></body></html>')
        self.page.add_style_tag(path='static/styles.css')
        self.page.evaluate("""() => {
          window.state={currentUser:{role:'manager'}};
          window.tr=x=>x;window.showStatus=(text)=>{window.error=text};
          window.info={private:false,inherited:false};window.saved=null;
          window.fetch=async(url,options)=>{
            if(options?.method==='POST'){window.saved=JSON.parse(options.body);return new Promise(()=>{});}
            return {ok:true,json:async()=>window.info};
          };
        }""")
        self.page.add_script_tag(content=self.script)

    def tearDown(self):
        self.page.close()

    def test_manager_menu_create_and_restore_labels(self):
        self.assertTrue(self.page.evaluate("mapperContextMenuItemsForFolder('Family').some(x=>x.label==='Privat mappe …')"))
        self.page.evaluate("state.currentUser.role='user'")
        self.assertFalse(self.page.evaluate("mapperContextMenuItemsForFolder('Family').some(x=>x.label==='Privat mappe …')"))
        self.page.evaluate("state.currentUser.role='admin';openMapperPrivacyDialog('Family')")
        expect(self.page.locator('.privacy-save')).to_have_text('Gør mappen privat')
        self.page.locator('.privacy-save').click()
        self.page.wait_for_function('window.saved!==null')
        self.assertEqual(self.page.evaluate('window.saved'),{'folder':'Family','private':True})

    def test_restore_and_inherited_state(self):
        self.page.evaluate("info={private:true,inherited:false};openMapperPrivacyDialog('Family')")
        expect(self.page.locator('.privacy-save')).to_have_text('Fjern privatmarkering')
        self.page.locator('.privacy-save').click()
        self.page.wait_for_function('window.saved!==null')
        self.assertEqual(self.page.evaluate('window.saved.private'),False)
        self.page.locator('.privacy-cancel').click()
        expect(self.page.locator('dialog')).to_have_count(0)
        self.page.evaluate("info={private:true,inherited:true,private_parent:'Family'};openMapperPrivacyDialog('Family/Child')")
        expect(self.page.locator('.privacy-save')).to_be_disabled()
        expect(self.page.locator('.privacy-inherited')).to_contain_text('Family')
        self.page.set_viewport_size({'width':390,'height':844})
        self.assertTrue(self.page.locator('dialog').evaluate('(el)=>el.scrollWidth<=el.clientWidth'))
