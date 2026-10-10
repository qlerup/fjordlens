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
    mapper_delete_counting: 'Counting files…',
    mapper_delete_file_progress: 'Deleted {done} of {total} files · {percent} %',
    mapper_delete_cleanup: 'Deleted {done} files · cleaning up index…',
    mapper_delete_file_refreshing: 'Deleted {done} files · refreshing view…',
  };
  const button = {textContent:'Delete', classList:{add(){},remove(){}}, setAttribute(){},removeAttribute(){}};
  const messages = [];
  const ctx = vm.createContext({state:{currentUser:{role:'admin'},mapperSelectedFolders:new Set(),mapperSelectedPhotoIds:new Set()},
    els:{mapperDeleteBtn:button}, TextDecoder, tr:key=>labels[key]||key, showStatus:(...args)=>messages.push(args),
    renderMapperContext(){},confirm:()=>true, invalidateStoredFolderPreviews(){},
    loadMapperTools:async()=>{},loadPhotos:async()=>{},setMapperEditMode(){}});
  vm.runInContext(source.slice(source.indexOf('function mediaPathPermission('), source.indexOf('function mapperContextMenuItemsForFolder(')), ctx);
  vm.runInContext(source.slice(source.indexOf('function renderMapperDeleteProgress()'),source.indexOf('// Select all visible items in Mapper')),ctx);
  return {ctx,button,messages};
}

test('folder progress counts files across the entire selection and stays busy through refresh', async()=>{
  const {ctx,button} = setup(); let resolve, calls=0;
  const send=()=>{calls++;return new Promise(r=>{resolve=r;});};
  const task=ctx.runMapperDeleteBatches(['One','Two'],'folders',send,()=>{});
  assert.match(button.textContent,/Counting files/); assert.equal(button.title,'One');
  assert.equal(await ctx.runMapperDeleteBatches(['Other'],'folders',send,()=>{}),false);
  Object.assign(ctx.state.mapperDeleteProgress,{fileTotal:100,fileDone:37,phase:'deleting'});
  ctx.renderMapperDeleteProgress();assert.match(button.textContent,/37 of 100 files.*37 %/);
  resolve({removed_files:100}); assert.equal(await task,true);assert.equal(calls,1);
  assert.match(button.textContent,/Deleted 100 files.*refreshing/);assert.equal(button.disabled,true);
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

test('folder workflow deduplicates descendants and streams the whole selection once',async()=>{
  const {ctx,messages}=setup();ctx.state.mapperSelectedFolders=new Set(['A','A/Child','B','C']);
  const sent=[];
  ctx.fetch=async(url,opts)=>{
    const body=JSON.parse(opts.body);sent.push(body.paths);
    assert.equal(body.progress,true);
    return {ok:true,json:async()=>({ok:true,deleted:['A','B','C'],folders:[],removed_photos:4,removed_files:8})};
  };
  await ctx.deleteSelectedMapperFolders();
  assert.deepEqual(sent,[['A','B','C']]);
  assert.deepEqual([...ctx.state.mapperSelectedFolders],[]);
  assert.equal(ctx.state.mapperDeleteProgress,null);
});

test('fragmented streamed progress updates file counts before a partial failure',async()=>{
  const {ctx,button,messages}=setup();ctx.state.mapperSelectedFolders=new Set(['A']);
  const events=[{type:'progress',phase:'deleting',done:0,total:100},
    {type:'progress',phase:'deleting',done:37,total:100},
    {type:'result',status:400,data:{ok:false,error:'Disk unavailable'}}];
  const bytes=new TextEncoder().encode(events.map(e=>JSON.stringify(e)+'\n').join(''));
  const split=new TextEncoder().encode(events.slice(0,2).map(e=>JSON.stringify(e)+'\n').join('')).length;
  const chunks=[bytes.slice(0,30),bytes.slice(30,split),bytes.slice(split)];
  let reads=0;
  ctx.fetch=async()=>({ok:true,headers:{get:()=> 'application/x-ndjson'},body:{getReader:()=>({
    read:async()=> {if(reads===2) assert.match(button.textContent,/37 of 100 files.*37 %/);return reads<chunks.length?{value:chunks[reads++],done:false}:{done:true};},
    releaseLock(){}
  })}});
  await ctx.deleteSelectedMapperFolders();
  assert.match(messages[0][0],/37 of 100 processed.*Disk unavailable/);
  assert.deepEqual([...ctx.state.mapperSelectedFolders],['A']);
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
