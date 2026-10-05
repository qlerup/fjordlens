const {test} = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../static/app.js'), 'utf8');

function setup() {
  const labels = {
    mapper_delete_progress: 'Deleting {kind}: {done} of {total} · {remaining} remaining',
    mapper_delete_refreshing: 'Deleted {total} of {total} · refreshing',
    mapper_delete_partial: '{done} of {total} processed. {error}',
    mapper_delete_folders: 'folders', mapper_delete_photos: 'photos',
  };
  const button = {textContent:'Delete', classList:{add(){},remove(){}}, setAttribute(){},removeAttribute(){}};
  const messages = [];
  const ctx = vm.createContext({state:{mapperSelectedFolders:new Set(),mapperSelectedPhotoIds:new Set()},
    els:{mapperDeleteBtn:button}, tr:key=>labels[key]||key, showStatus:(...args)=>messages.push(args),
    renderMapperContext(){},confirm:()=>true, invalidateStoredFolderPreviews(){},
    loadMapperTools:async()=>{},loadPhotos:async()=>{},setMapperEditMode(){}});
  vm.runInContext(source.slice(source.indexOf('function renderMapperDeleteProgress()'),source.indexOf('// Select all visible items in Mapper')),ctx);
  return {ctx,button,messages};
}

test('folder progress advances only after completed responses and stays busy through refresh', async()=>{
  const {ctx,button} = setup(); let resolve, calls=0;
  const send=()=>{calls++;return new Promise(r=>{resolve=r;});};
  const task=ctx.runMapperDeleteBatches(['One','Two'],'folders',send,()=>{});
  assert.match(button.textContent,/0 of 2/); assert.equal(button.title,'One');
  assert.equal(await ctx.runMapperDeleteBatches(['Other'],'folders',send,()=>{}),false);
  resolve({}); await new Promise(r=>setImmediate(r));
  assert.match(button.textContent,/1 of 2/);assert.match(button.textContent,/1 remaining/);assert.equal(button.title,'Two');
  resolve({}); assert.equal(await task,true);assert.equal(calls,2);
  assert.match(button.textContent,/Deleted 2 of 2/);assert.equal(button.disabled,true);
  ctx.finishMapperDeleteProgress(); assert.equal(ctx.state.mapperDeleteProgress,null);
});

test('photo batches are bounded and a failure stops later deletes with truthful partial progress',async()=>{
  const {ctx,messages} = setup();const batches=[];
  const result=await ctx.runMapperDeleteBatches(Array.from({length:70},(_,i)=>i),'photos',async batch=>{
    batches.push(batch.length);if(batches.length===2)throw Error('NAS unavailable');return {};
  },()=>{});
  assert.equal(result,false);assert.deepEqual(batches,[25,25]);
  assert.equal(ctx.state.mapperDeleteProgress.done,25);
  assert.match(messages[0][0],/25 of 70 processed.*NAS unavailable/);
});

test('folder workflow deduplicates descendants and retains failed and unsent selection',async()=>{
  const {ctx,messages}=setup();ctx.state.mapperSelectedFolders=new Set(['A','A/Child','B','C']);
  const sent=[];
  ctx.fetch=async(url,opts)=>{
    const body=JSON.parse(opts.body);sent.push(body.paths);
    return {ok:sent.length===1,json:async()=>sent.length===1?{ok:true,deleted:['A'],folders:['B','C'],removed_photos:4}:{ok:false,error:'Permission denied'}};
  };
  await ctx.deleteSelectedMapperFolders();
  assert.deepEqual(sent,[['A'],['B']]);
  assert.deepEqual([...ctx.state.mapperSelectedFolders],['B','C']);
  assert.equal(ctx.state.mapperDeleteProgress,null);
  assert.match(messages[0][0],/1 of 3 processed.*Permission denied/);
});

test('declining confirmation does not send deletion or enter busy state',async()=>{
  const {ctx}=setup();ctx.state.mapperSelectedFolders=new Set(['A']);ctx.confirm=()=>false;
  ctx.fetch=()=>{throw Error('must not delete');};
  await ctx.deleteSelectedMapperFolders();assert.equal(ctx.state.mapperDeleteProgress,undefined);
});

test('partially authorized photo response counts only confirmed IDs and retains the rest',async()=>{
  const {ctx,messages}=setup();ctx.state.mapperSelectedPhotoIds=new Set([1,2,3]);
  ctx.fetch=async()=>({ok:true,json:async()=>({ok:true,deleted_ids:[1],removed:{photos:1}})});
  await ctx.deleteSelectedMapperPhotos();
  assert.deepEqual([...ctx.state.mapperSelectedPhotoIds],[2,3]);
  assert.match(messages[0][0],/1 of 3 processed/);
});
