from pathlib import Path
import pytest
import os
from playwright.sync_api import sync_playwright, expect


@pytest.mark.parametrize('copying', [False, True])
def test_photo_move_picker_and_context_download(tmp_path, copying):
    source = Path('static/app.js').read_text(encoding='utf-8')
    start = source.index('async function openMapperMoveDialog(')
    move_script = source[start:source.index("document.getElementById('mapperHeaderMoveAction')", start)]
    menu_script = source[source.index('function mapperContextMenuItemsForPhoto('):source.index('let pendingIosUploadPicker')]
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=os.environ.get('CHROMIUM_EXECUTABLE'))
        page = browser.new_page(viewport={'width':1280, 'height':900})
        errors = []
        page.on('pageerror', lambda exc: errors.append(str(exc)))
        page.set_content('<html lang="da"><body></body></html>')
        page.add_style_tag(path='static/styles.css')
        page.add_style_tag(path='static/redesign.css')
        page.evaluate("""() => {
          window.state={view:'mapper',mapperPath:'Old',mapperSelectedPhotoIds:new Set([99]),mapperSelectedFolders:new Set(),mapperEditMode:true};
          window._normalizeMapperPath=p=>p; window.mapperFolderAllows=p=>p!=='Read only';
          window.mapperPhotoCanDelete=()=>true; window.tr=x=>x;
          window.loadMapperTreeIndex=async()=>['Old','New','Read only','Read only/Allowed','Bette','Bette/Nakkefoldscanning','Bette/Videoer'];
          window.setMapperEditMode=value=>{state.mapperEditMode=value};
          window.galleryDataCache=new Map();window.mapperViews=new Map();
          window.loadMapperTools=window.loadPhotos=async()=>{};
          window.openDownloadModal=(folder,ids)=>{window.downloadIds=ids};
          window.showStatus=text=>{window.statusMessage=text};
          window.resumeUploadPostprocessAfterRefresh=async()=>{window.postprocessMonitored=true};
          window.fetch=async(url,opts)=>{
            window.payload={url,...JSON.parse(opts.body)};
            if(window.fail) return {ok:false,json:async()=>({ok:false,error:'Ingen adgang'})};
            if(url==='/api/settings/upload-folder') return {ok:true,json:async()=>({ok:true,created:[payload.parent,payload.path].filter(Boolean).join('/')})};
            return {ok:true,json:async()=>({ok:true,moved:2,copied:2,renamed:1,destination:'New/Holiday'})};
          };
        }""")
        page.add_script_tag(content=move_script + menu_script)
        page.evaluate("mapperContextMenuItemsForPhoto(42).find(item=>item.label==='Download billede').action()")
        assert page.evaluate('downloadIds') == [42]
        assert page.evaluate('[...state.mapperSelectedPhotoIds]') == [99]
        page.evaluate("copying => openMapperMoveDialog('',[1,2],copying)", copying)
        expect(page.locator('dialog')).to_be_visible()
        expect(page.locator('dialog h3')).to_have_text('Kopiér valgte billeder' if copying else 'Flyt valgte billeder')
        if copying:
            expect(page.locator('dialog')).to_contain_text('Original og konverteret fil kopieres sammen.')
        expect(page.locator('[data-save]')).to_be_disabled()
        expect(page.get_by_role('button', name='Opret mappe', exact=True)).to_be_disabled()
        expect(page.get_by_role('button',name='Read only',exact=True)).to_be_disabled()
        expect(page.get_by_role('button',name='Nakkefoldscanning',exact=True)).to_be_hidden()
        page.get_by_role('button',name='Undermapper i Bette',exact=True).click()
        expect(page.get_by_role('button',name='Nakkefoldscanning',exact=True)).to_be_visible()
        page.get_by_role('button',name='Nakkefoldscanning',exact=True).click()
        expect(page.locator('.move-preview')).to_have_text('Ny placering: Bette/Nakkefoldscanning')
        page.locator('.move-search').first.fill('Videoer')
        expect(page.get_by_role('button',name='Videoer',exact=True)).to_be_visible()
        expect(page.get_by_role('button',name='New',exact=True)).to_have_count(0)
        page.locator('.move-search').first.fill('')
        expect(page.locator('dialog')).not_to_contain_text('uploads')
        page.get_by_role('button', name='New', exact=True).click()
        page.get_by_label('Ny undermappe (valgfrit)').fill('Holiday')
        expect(page.locator('.move-preview')).to_contain_text('New/Holiday')
        expect(page.get_by_role('button', name='Opret mappe', exact=True)).to_be_enabled()
        for width in [1280,390,320]:
            page.set_viewport_size({'width':width,'height':850})
            assert page.locator('dialog').evaluate('(el)=>el.scrollWidth<=el.clientWidth')
            page.screenshot(path=str(tmp_path/f'{"copy" if copying else "move"}-photos-{width}.png'))
        page.evaluate('window.fail=true')
        page.get_by_role('button', name='Opret mappe', exact=True).click()
        expect(page.locator('.move-error')).to_contain_text('Ingen adgang')
        expect(page.get_by_label('Ny undermappe (valgfrit)')).to_have_value('Holiday')
        expect(page.get_by_role('button', name='Opret mappe', exact=True)).to_be_enabled()
        page.evaluate('window.fail=false')
        page.get_by_role('button', name='Opret mappe', exact=True).click()
        expect(page.get_by_role('button', name='Holiday', exact=True)).to_have_attribute('aria-pressed', 'true')
        expect(page.get_by_label('Ny undermappe (valgfrit)')).to_have_value('')
        expect(page.locator('.move-preview')).to_have_text('Ny placering: New/Holiday')
        expect(page.get_by_role('button', name='Opret mappe', exact=True)).to_be_disabled()
        assert page.evaluate('window.payload') == dict(url='/api/settings/upload-folder',destination='uploads',parent='New',path='Holiday')
        page.screenshot(path=str(tmp_path/f'{"copy" if copying else "move"}-folder-created.png'))
        page.evaluate('window.fail=true')
        page.locator('[data-save]').click()
        expect(page.locator('.move-error')).to_contain_text('Ingen adgang')
        expect(page.locator('[data-save]')).to_be_enabled()
        assert page.evaluate('state.mapperEditMode') is True
        expect(page.get_by_role('button',name='Read only',exact=True)).to_be_disabled()
        page.evaluate('window.fail=false')
        page.locator('[data-save]').click()
        expect(page.locator('dialog')).to_have_count(0)
        assert page.evaluate('window.payload') == dict(url='/api/photos/copy' if copying else '/api/photos/move',photo_ids=[1,2],parent='New/Holiday',new_name='')
        assert '2 billeder' in page.evaluate('statusMessage') and '1 omdøbt' in page.evaluate('statusMessage')
        assert page.evaluate('state.mapperEditMode') is False
        if copying:
            assert page.evaluate('postprocessMonitored')
            assert 'kopieret' in page.evaluate('statusMessage')
        assert not errors
        browser.close()
