from pathlib import Path
from playwright.sync_api import sync_playwright, expect


def test_photo_move_picker_and_context_download(tmp_path):
    source = Path('static/app.js').read_text(encoding='utf-8')
    start = source.index('async function openMapperMoveDialog(')
    move_script = source[start:source.index("document.getElementById('mapperHeaderMoveAction')", start)]
    menu_script = source[source.index('function mapperContextMenuItemsForPhoto('):source.index('let pendingIosUploadPicker')]
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={'width':1280, 'height':900})
        errors = []
        page.on('pageerror', lambda exc: errors.append(str(exc)))
        page.set_content('<html lang="da"><body></body></html>')
        page.add_style_tag(path='static/styles.css')
        page.add_style_tag(path='static/redesign.css')
        page.evaluate("""() => {
          window.state={view:'mapper',mapperPath:'Old',mapperSelectedPhotoIds:new Set([99]),mapperSelectedFolders:new Set()};
          window._normalizeMapperPath=p=>p; window.mapperFolderAllows=p=>p!=='Read only';
          window.mapperPhotoCanDelete=()=>true; window.tr=x=>x;
          window.loadMapperTreeIndex=async()=>['Old','New','Read only'];
          window.galleryDataCache=new Map();window.mapperViews=new Map();
          window.loadMapperTools=window.loadPhotos=async()=>{};
          window.openDownloadModal=(folder,ids)=>{window.downloadIds=ids};
          window.showStatus=text=>{window.statusMessage=text};
          window.fetch=async(url,opts)=>{
            window.payload={url,...JSON.parse(opts.body)};
            if(window.fail) return {ok:false,json:async()=>({ok:false,error:'Ingen adgang'})};
            return {ok:true,json:async()=>({ok:true,moved:2,renamed:1,destination:'New/Holiday'})};
          };
        }""")
        page.add_script_tag(content=move_script + menu_script)
        page.evaluate("mapperContextMenuItemsForPhoto(42).find(item=>item.label==='Download billede').action()")
        assert page.evaluate('downloadIds') == [42]
        assert page.evaluate('[...state.mapperSelectedPhotoIds]') == [99]
        page.evaluate("openMapperMoveDialog('',[1,2])")
        expect(page.locator('dialog')).to_be_visible()
        expect(page.locator('[data-save]')).to_be_disabled()
        expect(page.locator('.move-destinations')).not_to_contain_text('Read only')
        page.get_by_role('button', name='uploads/New', exact=True).click()
        page.get_by_label('Ny undermappe (valgfrit)').fill('Holiday')
        expect(page.locator('.move-preview')).to_contain_text('uploads/New/Holiday')
        for width in [1280,390,320]:
            page.set_viewport_size({'width':width,'height':850})
            assert page.locator('dialog').evaluate('(el)=>el.scrollWidth<=el.clientWidth')
            page.screenshot(path=str(tmp_path/f'move-photos-{width}.png'))
        page.evaluate('window.fail=true')
        page.locator('[data-save]').click()
        expect(page.locator('.move-error')).to_contain_text('Ingen adgang')
        expect(page.locator('[data-save]')).to_be_enabled()
        page.evaluate('window.fail=false')
        page.locator('[data-save]').click()
        expect(page.locator('dialog')).to_have_count(0)
        assert page.evaluate('window.payload') == dict(url='/api/photos/move',photo_ids=[1,2],parent='New',new_name='Holiday')
        assert '2 billeder' in page.evaluate('statusMessage') and '1 omdøbt' in page.evaluate('statusMessage')
        assert not errors
        browser.close()
