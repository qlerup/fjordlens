const {test} = require('node:test');
const assert = require('node:assert/strict');
const {readFileSync} = require('node:fs');
const vm = require('node:vm');

test('upload refresh keeps root selected even when server remembers the previous uploaded folder', async () => {
  const source = readFileSync('static/app.js','utf8');
  let savedFolder = 'Christmas';
  const state = {view:'mapper',mapperPath:'',mapperSelectedFolders:new Set()};
  const context = vm.createContext({state,mapperToolsRequestSequence:0,
    galleryDataCache:{clear(){},generation:()=>0,set(){}},galleryCacheKey:x=>x,
    fetchUploadDestinationConfig:async()=>({res:{ok:true},data:{ok:true,subdir:savedFolder,folders:['Christmas','Birthday']}}),
    _normalizeMapperPath:x=>x,_expandMapperAncestors(){},renderMapperContext(){},_syncRouteStateToUrl(){},showStatus(){}});
  vm.runInContext(source.slice(source.indexOf('async function loadMapperTools('),source.indexOf('function beginMapperPathNavigation(')),context);
  await context.loadMapperTools();
  assert.equal(state.mapperPath,'');
  savedFolder = 'Birthday';
  await context.loadMapperTools();
  assert.equal(state.mapperPath,'');
  assert.equal(state.folder,null);
  state.mapperPath = 'Chosen parent';
  await context.loadMapperTools();
  assert.equal(state.mapperPath,'Chosen parent');
  await context.loadMapperTools('');
  assert.equal(state.mapperPath,'');
  await context.loadMapperTools('Explicit target');
  assert.equal(state.mapperPath,'Explicit target');
});
