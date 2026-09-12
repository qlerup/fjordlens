const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const {JSDOM} = require('jsdom');

test('restores original cards, pagination and scroll; invalidated or edited views are not reused', () => {
  const dom = new JSDOM('<div id="grid" class="folders-view"><article id="original"></article></div><div id="empty" class="hidden"></div>');
  const grid = dom.window.document.getElementById('grid'), original = grid.firstChild;
  let generation = 0, refreshes = 0, scroll;
  const state = {view:'mapper',mapperPath:'A',items:[{id:1}],mapperFolders:['A'],photosPageOffset:50,photosHasMore:true,mapperTotalItems:100,mapperGhostCapacity:100};
  const context = vm.createContext({state,els:{grid,empty:dom.window.document.getElementById('empty')},
    galleryDataCache:{generation:()=>generation},galleryCacheKey:JSON.stringify,photosRequestSequence:0,
    captureGalleryScrollAnchor:()=>({scrollY:700}), renderMapperContext:()=>{}});
  const source = fs.readFileSync('static/app.js','utf8');
  vm.runInContext(source.slice(source.indexOf('const mapperViews ='),source.indexOf('async function refreshMapperViewInBackground')),context);
  context.refreshMapperViewInBackground = async () => {refreshes++;};
  context.renderGrid = () => {
    const entry = vm.runInContext('pendingMapperView',context);
    grid.replaceChildren(...entry.nodes); scroll = entry.scroll.scrollY;
    vm.runInContext('pendingMapperView = null',context);
  };
  context.rememberMapperView();
  grid.replaceChildren(dom.window.document.createElement('p'));
  state.items = [];
  assert.equal(context.restoreMapperView(),true);
  assert.equal(grid.firstChild,original);
  assert.equal(state.photosPageOffset,50);
  assert.equal(state.photosHasMore,true);
  assert.equal(scroll,700);
  assert.equal(refreshes,1);
  context.restoreMapperView();
  assert.equal(refreshes,1, 'sequential navigation hooks must not duplicate refresh requests');
  state.mapperEditMode = true;
  assert.equal(context.restoreMapperView(),false);
  state.mapperEditMode = false; generation++;
  assert.equal(context.restoreMapperView(),false);
  dom.window.close();
});

test('background refresh ignores replies after leaving a folder and skips unchanged rendering', async () => {
  const source = fs.readFileSync('static/app.js','utf8');
  const state = {view:'mapper',mapperPath:'A',mapperSort:'date_desc',items:[{id:1}],mapperFolders:['A'],mapperTotalItems:1};
  let resolve, renders = 0, remembered = 0;
  const context = vm.createContext({state,photosRequestSequence:1,URLSearchParams,
    mapperViewKey:()=>state.mapperPath,galleryDataCache:{generation:()=>0},
    _normalizeMapperSort:x=>x,estimateMapperPageLimit:()=>50,
    fetch:()=>new Promise(r=>resolve=r),fetchUploadDestinationConfig:async()=>({res:{ok:true},data:{ok:true,folders:['A']}}),
    rememberMapperView:()=>remembered++,renderGrid:()=>renders++});
  vm.runInContext(source.slice(source.indexOf('async function refreshMapperViewInBackground'),source.indexOf('function galleryCacheKey')),context);
  const run = context.refreshMapperViewInBackground();
  state.mapperPath = 'B';
  resolve({ok:true,json:async()=>({items:[{id:2}],total:1})}); await run;
  assert.equal(state.items[0].id,1);
  assert.equal(remembered,0);
  state.mapperPath = 'A';
  const unchanged = context.refreshMapperViewInBackground();
  resolve({ok:true,json:async()=>({items:[{id:1}],total:1})}); await unchanged;
  assert.equal(renders,0);
  assert.equal(remembered,1);
});
