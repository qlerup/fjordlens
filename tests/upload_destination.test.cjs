const {test} = require('node:test');
const assert = require('node:assert/strict');
const {readFileSync} = require('node:fs');
const vm = require('node:vm');

test('upload refresh keeps root selected regardless of saved upload destination', async () => {
  const source = readFileSync('static/app.js','utf8');
  let savedFolder = 'Christmas';
  const requests = [];
  const state = {view:'mapper',mapperPath:'',mapperSelectedFolders:new Set(),items:[],currentUser:{id:1}};
  const context = vm.createContext({state,URLSearchParams,document:{hidden:false},mapperViews:new Map(),
    galleryDataCache:{clear(){},generation:()=>0},galleryCacheKey:x=>x,
    fetch:async(url)=>{requests.push(url);return {ok:true,status:200,json:async()=>({ok:true,subdir:savedFolder,folders:['Christmas','Birthday'],items:[],revision:1})};},
    _normalizeMapperPath:x=>x,_expandMapperAncestors(){},renderMapperContext(){},_syncRouteStateToUrl(){},showStatus(){},renderGrid(){},
    setTimeout:()=>1,clearTimeout(){},rememberMapperView(){},photosRequestSequence:0,photosAbortController:null,photosLoadPromise:null});
  vm.runInContext(source.slice(source.indexOf('let mapperToolsRequestSequence ='),source.indexOf('async function createMapperFolder(')),context);
  await context.loadMapperTools();
  assert.equal(state.mapperPath,'');
  savedFolder = 'Birthday';
  await context.loadMapperTools();
  assert.equal(state.mapperPath,'');
  assert.equal(state.folder,null);
  state.mapperPath = 'Chosen parent';
  await context.loadMapperTools();
  assert.equal(state.mapperPath,'Chosen parent');
  context.beginMapperPathNavigation('');
  await context.loadMapperTools('');
  assert.equal(state.mapperPath,'');
  context.beginMapperPathNavigation('Explicit target');
  await context.loadMapperTools('Explicit target');
  assert.equal(state.mapperPath,'Explicit target');
  assert.ok(requests.every(url=>url.startsWith('/api/folder-index?')));
});
