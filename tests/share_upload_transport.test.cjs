const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('static/shared.js', 'utf8');

function setup(Upload) {
  const messages = [];
  const ctx = vm.createContext({
    window:{tus:{Upload}}, state:{token:'private-link'}, els:{},
    fetch:async()=>({ok:true,status:200,json:async()=>({ok:true,can_upload:true,show_others_uploads:false})}),
    showStatus:(text,tone)=>messages.push({text,tone}),t:key=>key,
    applyShareUploadFileTypes(){},renderShareBlockedTypes(){},
    splitShareFilesByAllowed:files=>({allowed:files,blocked:[]}),
    showUploadWarningModal(){},startShareUploadProgress(){},startShareUploadTransferHeartbeat(){},
    setShareUploadTransferState:async()=>{},markShareUploadCurrentFile(){},
    updateShareUploadProgress(){},finishShareUploadFile(){},stopShareUploadTransferHeartbeat:async()=>{},
    finishShareUploadProgress(){},closeUploadWarningModal(){},startShareUploadPostprocess:async()=>{},loadPhotos:async()=>{},
  });
  vm.runInContext(source.slice(source.indexOf('function configureShareUploadRequest('),source.indexOf('async function runDelete(')),ctx);
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
