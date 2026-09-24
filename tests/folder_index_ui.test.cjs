const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('static/app.js','utf8');
function fixture() {
  const requests=[], renders=[], timers=[];
  const state={view:'mapper',mapperPath:'A',items:[],mapperFolders:[],mapperFolderPreviews:{},currentUser:{id:1},photosLoading:false};
  const context=vm.createContext({state,URLSearchParams,document:{hidden:false},mapperViews:new Map(),
    galleryDataCache:{clear(){},generation:()=>0},galleryCacheKey:value=>JSON.stringify([state.currentUser.id,value]),
    _normalizeMapperPath:value=>String(value||''),_expandMapperAncestors(){},renderMapperContext(){},_syncRouteStateToUrl(){},
    renderGrid(){renders.push({folders:[...state.mapperFolders],loading:state.mapperFoldersLoading,error:state.mapperFoldersError});},
    showStatus(){},setTimeout:fn=>{timers.push(fn);return timers.length;},clearTimeout(){},
    rememberMapperView(){},restoreMapperView:()=>false,photosRequestSequence:0,photosAbortController:null,photosLoadPromise:null,
    fetch:(url)=>new Promise(resolve=>requests.push({url,resolve})),
  });
  vm.runInContext(source.slice(source.indexOf('let mapperToolsRequestSequence ='),source.indexOf('async function createMapperFolder(')),context);
  const reply=(n,parent,paths,status=200)=>requests[n].resolve({ok:status===200,status,json:async()=>({ok:status===200,parent,folders:paths,
    items:paths.map(path=>({path,name:path.split('/').pop(),previews:[]})),revision:1,indexing:false})});
  return {context,state,requests,renders,timers,reply};
}

test('folder and photo requests start together; folders render while photos are pending', async()=>{
  const f=fixture(); let finishPhotos, started=false;
  f.context.loadPhotos=()=>{started=true;return new Promise(resolve=>finishPhotos=resolve);};
  const loading=f.context.navigateMapperPath('A');
  assert.equal(started,true); assert.equal(f.requests.length,1);
  assert.equal(f.state.mapperFoldersLoading,true); assert.equal(f.state.photosLoading,true);
  f.reply(0,'A',['A/Child']); await new Promise(resolve=>setImmediate(resolve));
  assert.deepEqual([...f.state.mapperFolders],['A/Child']);
  assert.equal(f.state.mapperFoldersLoading,false); assert.equal(f.state.photosLoading,true);
  assert.ok(f.renders.some(r=>r.folders.includes('A/Child')));
  finishPhotos(); await loading;
});

test('a late folder response cannot overwrite a newer navigation', async()=>{
  const f=fixture(); const old=f.context.loadMapperTools('A',true);
  f.state.mapperPath='B'; const next=f.context.loadMapperTools('B',true);
  f.reply(1,'B',['B/New']); await next;
  f.reply(0,'A',['A/Old']); await old;
  assert.deepEqual([...f.state.mapperFolders],['B/New']); assert.equal(f.state.mapperFoldersLoading,false);
});

test('responses from another account are discarded, not put into a shared browser cache', async()=>{
  const f=fixture(); const old=f.context.loadMapperTools('A',true);
  f.state.currentUser.id=2; const next=f.context.loadMapperTools('A',true);
  f.reply(1,'A',[]); await next;
  f.reply(0,'A',['A/Private']); await old;
  assert.deepEqual([...f.state.mapperFolders],[]);
});

test('failed folder lookup is an error, not a successfully empty folder; retry succeeds', async()=>{
  const f=fixture(); const first=f.context.loadMapperTools('A',true);
  f.reply(0,'A',[],503); assert.equal(await first,false);
  assert.ok(f.state.mapperFoldersError); assert.equal(f.state.mapperFoldersLoading,false);
  const retry=f.context.loadMapperTools('A',true); f.reply(1,'A',['A/Child']); assert.equal(await retry,true);
  assert.equal(f.state.mapperFoldersError,'');
});

test('revoked folder access clears cached photos and covers immediately', async()=>{
  const f=fixture(); f.state.items=[{id:1}]; f.state.mapperFolderPreviews={'A/Private':['secret.jpg']};
  const request=f.context.loadMapperTools('A',true); f.reply(0,'A',[],403); await request;
  assert.deepEqual([...f.state.items],[]); assert.deepEqual(Object.keys(f.state.mapperFolderPreviews),[]);
  assert.ok(f.state.mapperFoldersError);
});

test('later reads pick up another user’s folder edits even with useCache=true', async()=>{
  const f=fixture(); const first=f.context.loadMapperTools('A',true); f.reply(0,'A',['A/Old']); await first;
  const next=f.context.loadMapperTools('A',true); f.reply(1,'A',['A/New']); await next;
  assert.equal(f.requests.length,2); assert.deepEqual([...f.state.mapperFolders],['A/New']);
  assert.ok(f.requests.every(r=>r.url.startsWith('/api/folder-index?')));
});

test('unchanged folder-index polls do not rebuild the mapper grid', async()=>{
  const f=fixture(); f.state.items=[{id:1}];
  const first=f.context.loadMapperTools('A',true); f.reply(0,'A',['A/Child']); await first;
  const rendersAfterFirst=f.renders.length;
  const next=f.context.loadMapperTools('A',true); f.reply(1,'A',['A/Child']); await next;
  assert.equal(f.renders.length,rendersAfterFirst);
});
