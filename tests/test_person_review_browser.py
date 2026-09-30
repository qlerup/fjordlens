"""Browser regressions for reviewing proposals, without a live face database."""
import json
import unittest
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


class FaceReviewBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch()
        cls.root = Path(__file__).resolve().parents[1]

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()

    def setUp(self):
        self.context = self.browser.new_context(viewport={'width':1200,'height':900})
        self.page = self.context.new_page()
        self.errors = []
        self.page.on('pageerror', lambda error: self.errors.append(str(error)))
        self.page.route('https://review.test/**', lambda route: route.fulfill(content_type='text/html',body='<html><head></head><body></body></html>'))
        self.page.goto('https://review.test/')
        self.page.add_style_tag(content=(self.root/'static/styles.css').read_text(encoding='utf-8'))
        self.page.evaluate('''() => {
          window.state = {view:'personer',personView:{personId:7},people:[{id:9,name:'Other person'}]};
          window.personHasName = () => true;
          window.refreshed = 0;
          window.loadPersonPhotos = () => { refreshed++; };
          window.calls = []; window.failSave = false;
          const image = 'data:image/svg+xml,' + encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="80" height="80"><rect width="80" height="80" fill="#537c8c"/></svg>');
          const face = id => ({face_id:id,photo_id:id,face_url:image,image_url:image,box:{x:.25,y:.25,w:.5,h:.5},
                              reason:id<=62?'better_match':'ambiguous'});
          window.groups = [
            {target_id:9,target_name:'Other person',count:62,face_ids:Array.from({length:62},(_,i)=>i+1),faces:Array.from({length:62},(_,i)=>face(i+1)),previews:[face(1)]},
            {target_id:null,target_name:'Kræver manuel gennemgang',count:3,face_ids:[63,64,65],faces:[face(63),face(64),face(65)],previews:[face(63)]}
          ];
          window.fetch = async (url, options) => {
            if (url.endsWith('/faces/selection')) {
              calls.push(JSON.parse(options.body));
              return {ok:!failSave,json:async()=>failSave?{ok:false,error:'Try again'}:{ok:true}};
            }
            if(options?.method==='POST')return {ok:true,json:async()=>({ok:true,job_id:'test'})};
            return {ok:true,json:async()=>({ok:true,status:'done',total:100,scanned:100,skipped:2,results:groups})};
          };
        }''')
        self.page.add_script_tag(content=(self.root/'static/person_faces.js').read_text(encoding='utf-8'))
        self.page.evaluate("openPersonFaceReview({sourceId:7,sourceName:'Source'})")
        expect(self.page.locator('.face-review-group')).to_have_count(2)

    def tearDown(self):
        self.assertEqual(self.errors, [])
        self.context.close()

    def test_summary_counts_faces_and_does_not_call_manual_group_a_match(self):
        status = self.page.locator('[data-status]')
        expect(status).to_contain_text('62 med forslag til en anden person')
        expect(status).to_contain_text('3 kræver manuel gennemgang')
        expect(status).to_contain_text('2 kunne ikke sammenlignes')
        expect(self.page.locator('.face-review-group').nth(1)).to_contain_text('uden entydigt match')
        self.assertEqual(self.page.evaluate('calls'), [])

    def test_selects_subset_across_pages_and_keeps_remainder(self):
        self.page.locator('.face-review-group').first.click()
        expect(self.page.locator('.face-review-card')).to_have_count(60)
        move = self.page.get_by_role('button', name='Flyt valgte til Other person',exact=True)
        expect(move).to_be_disabled()
        self.page.get_by_label('Vælg ansigt 1',exact=True).check()
        self.page.get_by_role('button',name='Næste',exact=True).click()
        expect(self.page.locator('.face-review-card')).to_have_count(2)
        self.page.get_by_label('Vælg ansigt 61',exact=True).check()
        move.click()
        expect(self.page.locator('.face-review-group').first).to_contain_text('60 ansigt(er)')
        self.assertEqual(self.page.evaluate('calls[0].face_ids'), [1,61])
        self.assertEqual(self.page.evaluate('calls[0].target_id'),9)
        self.page.get_by_role('button',name='Luk',exact=True).click()
        self.page.wait_for_function('refreshed === 1')

    def test_failed_save_preserves_selection_and_allows_retry(self):
        self.page.locator('.face-review-group').first.click()
        self.page.get_by_label('Vælg ansigt 1',exact=True).check()
        self.page.evaluate('failSave=true')
        self.page.get_by_role('button',name='Flyt valgte til Other person',exact=True).click()
        expect(self.page.locator('[data-status]')).to_have_text('Try again')
        expect(self.page.get_by_label('Vælg ansigt 1',exact=True)).to_be_checked()
        expect(self.page.get_by_role('button',name='Flyt valgte til Other person',exact=True)).to_be_enabled()
        self.page.evaluate('failSave=false')
        self.page.get_by_role('button',name='Flyt valgte til Other person',exact=True).click()
        expect(self.page.locator('.face-review-group').first).to_contain_text('61 ansigt(er)')

    def test_mobile_manual_review_requires_selection_and_target(self):
        self.page.set_viewport_size({'width':390,'height':844})
        self.page.locator('.face-review-group').nth(1).click()
        expect(self.page.locator('.face-review-explanation').last).to_contain_text('ikke nødvendigvis')
        assign = self.page.get_by_role('button',name='Flyt valgte til valgt person',exact=True)
        expect(assign).to_be_disabled()
        self.page.get_by_role('button',name='Vælg denne side',exact=True).click()
        expect(assign).to_be_disabled()
        self.page.get_by_label('Flyt til person',exact=True).select_option('9')
        expect(assign).to_be_enabled()
        dialog=self.page.locator('#face-review-dialog')
        self.assertLessEqual(dialog.bounding_box()['width'],390)
        self.assertFalse(dialog.evaluate('(node)=>node.scrollWidth>node.clientWidth'))
        self.assertEqual(self.page.evaluate('calls'),[])

    def test_box_tracks_contained_photo_and_resize(self):
        self.page.get_by_role('button',name='Luk',exact=True).click()
        self.page.evaluate('''() => {
            const face = groups[0].faces[0];
            face.image_url = 'data:image/svg+xml,' + encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="400" height="200"><rect width="400" height="200" fill="#537c8c"/></svg>');
            face.pixel_box = [100,50,200,100]; face.source_size = [400,200];
            openPersonFaceReview({sourceId:7});
        }''')
        self.page.locator('.face-review-group').first.click()
        media = self.page.locator('.face-review-media').first
        box = media.locator('.face-review-box')
        expect(box).to_be_visible()
        for width in (1200,390):
            self.page.set_viewport_size({'width':width,'height':900})
            self.page.wait_for_function('''() => {
                const media=document.querySelector('.face-review-media');
                const box=media.querySelector('.face-review-box');
                return Math.abs(parseFloat(box.style.top)-media.clientHeight*.375)<1;
            }''')
            m,b=media.bounding_box(),box.bounding_box()
            self.assertAlmostEqual(b['x']-m['x'],m['width']*.25,delta=1)
            self.assertAlmostEqual(b['y']-m['y'],m['height']*.375,delta=1)
            self.assertAlmostEqual(b['width'],m['width']*.5,delta=1)
            self.assertAlmostEqual(b['height'],m['height']*.25,delta=1)

    def test_person_name_is_text_not_html(self):
        self.page.get_by_role('button',name='Luk',exact=True).click()
        self.page.evaluate("groups[0].target_name='<img src=x onerror=alert(1)>'; openPersonFaceReview({sourceId:7})")
        expect(self.page.locator('.face-review-group').first).to_contain_text('<img src=x onerror=alert(1)>')
        expect(self.page.locator('.face-review-group strong img')).to_have_count(0)

    def test_portrait_rotation_and_exact_video_frame_coordinates(self):
        for exact_frame in (False, True):
            self.page.get_by_role('button',name='Luk',exact=True).click()
            self.page.evaluate('''exact => {
                const face=groups[0].faces[0];
                face.image_url='data:image/svg+xml,'+encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="200" height="400"/>');
                face.pixel_box=[50,100,100,200]; face.source_size=exact?[1920,1080]:[400,200];
                face.exact_frame=exact; openPersonFaceReview({sourceId:7});
            }''', exact_frame)
            self.page.locator('.face-review-group').first.click()
            media=self.page.locator('.face-review-media').first
            expect(media.locator('.face-review-box')).to_be_visible()
            m,b=media.bounding_box(),media.locator('.face-review-box').bounding_box()
            self.assertAlmostEqual(b['x']-m['x'],m['width']*.375,delta=1)
            self.assertAlmostEqual(b['y']-m['y'],m['height']*.25,delta=1)
            self.assertAlmostEqual(b['width'],m['width']*.25,delta=1)
            self.assertAlmostEqual(b['height'],m['height']*.5,delta=1)


if __name__ == '__main__':
    unittest.main()
