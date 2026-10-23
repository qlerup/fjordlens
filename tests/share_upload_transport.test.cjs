const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('static/shared.js', 'utf8');

function setup(Upload) {
  const messages = [];
  const ctx = vm.createContext({
    Blob, window:{tus:{Upload}}, state:{token:'private-link'}, els:{},
    fetch:async()=>({ok:true,status:200,json:async()=>({ok:true,can_upload:true,show_others_uploads:false})}),
    showStatus:(text,tone)=>messages.push({text,tone}),t:key=>key,
    applyShareUploadFileTypes(){},renderShareBlockedTypes(){},
    splitShareFilesByAllowed:files=>({allowed:files,blocked:[]}),
    showUploadWarningModal(){},startShareUploadProgress(){},startShareUploadTransferHeartbeat(){},
    setShareUploadTransferState:async()=>{},markShareUploadCurrentFile(){},
    updateShareUploadProgress(){},finishShareUploadFile(){},stopShareUploadTransferHeartbeat:async()=>{},
    finishShareUploadProgress(){},closeUploadWarningModal(){},startShareUploadPostprocess:async()=>{},loadPhotos:async()=>{},
  });
  vm.runInContext(source.slice(source.indexOf('const shareUploadFileReader ='),source.indexOf('async function runDelete(')),ctx);
  return {ctx,messages};
}

test('stalled share request reaches the TUS error handler instead of waiting forever',()=>{
  const {ctx}=setup();
  const xhr={};
  ctx.configureShareUploadRequest({getUnderlyingObject:()=>xhr});
  assert.equal(xhr.timeout,120000);
  let error;
  // tus assigns this when send() runs, after onBeforeRequest.
  xhr.onerror=value=>{error=value;};
  xhr.ontimeout();
  assert.match(error.message,/timed out/);
});

test('share reader sends memory-backed chunks, preserves bytes and supports resume offsets',async()=>{
  const {ctx}=setup();
  const bytes=Uint8Array.from({length:19},(_,i)=>i);
  const ranges=[];
  const file={size:bytes.length,slice(start,end){
    ranges.push([start,end]);
    return {arrayBuffer:async()=>bytes.slice(start,end).buffer};
  }};
  ctx.file=file;
  const reader=await vm.runInContext('shareUploadFileReader.openFile(file, 8)',ctx);
  const first=await reader.slice(0,8);
  const resumed=await reader.slice(5,13);
  const last=await reader.slice(13,Infinity);
  assert.deepEqual(Array.from(new Uint8Array(await first.value.arrayBuffer())),[0,1,2,3,4,5,6,7]);
  assert.deepEqual(Array.from(new Uint8Array(await resumed.value.arrayBuffer())),[5,6,7,8,9,10,11,12]);
  assert.deepEqual(Array.from(new Uint8Array(await last.value.arrayBuffer())),[13,14,15,16,17,18]);
  assert.equal(first.done,false);
  assert.equal(last.done,true);
  assert.deepEqual(ranges,[[0,8],[5,13],[13,19]]);
});

test('file read failures and incomplete reads fail instead of sending an empty chunk',async()=>{
  const {ctx}=setup();
  ctx.file={size:8,slice(){return {arrayBuffer:async()=>new ArrayBuffer(0)};}};
  const reader=await vm.runInContext('shareUploadFileReader.openFile(file, 8)',ctx);
  await assert.rejects(reader.slice(0,8),/Could not read upload chunk/);
  ctx.file.slice=()=>({arrayBuffer:async()=>{throw new Error('File inaccessible');}});
  await assert.rejects(reader.slice(0,8),/File inaccessible/);
});

test('share uploads configure timeout on requests and surface the failed filename and reason',async()=>{
  let configured=false;
  class Upload {
    constructor(file,options) {this.options=options;}
    findPreviousUploads() {return Promise.resolve([]);}
    start() {
      const xhr={onerror:err=>this.options.onError(err)};
      this.options.onBeforeRequest({getUnderlyingObject:()=>xhr});
      configured=xhr.timeout===120000;
      xhr.ontimeout();
    }
  }
  const {ctx,messages}=setup(Upload);
  await ctx.runUpload([{name:'video.mov',size:71000000}]);
  assert.ok(configured);
  assert.ok(messages.some(m=>m.tone==='err' && /video.mov.*timed out/.test(m.text)));
});

test('successful resumed upload still starts postprocessing',async()=>{
  let resumed=false,processed=false;
  class Upload {
    constructor(file,options) {this.options=options;}
    findPreviousUploads() {return Promise.resolve([{uploadUrl:'/existing-upload'}]);}
    resumeFromPreviousUpload(previous) {resumed=previous.uploadUrl==='/existing-upload';}
    start() {this.options.onSuccess();}
  }
  const {ctx,messages}=setup(Upload);
  ctx.startShareUploadPostprocess=async()=>{processed=true;};
  await ctx.runUpload([{name:'video.mov',size:71000000}]);
  assert.ok(resumed && processed);
  assert.equal(messages.at(-1).tone,'ok');
});
