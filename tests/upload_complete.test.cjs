const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('static/app.js', 'utf8');
const completion = source.slice(source.indexOf('function showUploadCompleteDialog()'),
  source.indexOf('// Read-only background monitoring'));

function fixture(fetcher) {
  const dialog = {open:false, shows:0, showModal(){this.open=true; this.shows++;}};
  const elements = {uploadCompleteDialog:dialog, uploadCompleteTitle:{},
    uploadCompleteMessage:{}, uploadCompleteCloseHint:{}};
  const context = vm.createContext({
    state:{uiLanguage:'da'}, uploadStopRequested:false, uploadQueue:[],
    uploadUiState:{failedFiles:0}, uploadSessionSavedTotal:2, isUploadRunning:()=>false,
    document:{getElementById:id=>elements[id]}, fetch:fetcher,
    Date, window:{setTimeout:fn=>fn()}, uploadPostprocessPollDelayMs:()=>0,
  });
  vm.runInContext(completion, context);
  return {context, dialog, elements};
}
const response = data => ({ok:true, json:async()=>data});

test('completion appears after server accepts postprocessing, before processing finishes', async () => {
  let finish;
  const f = fixture(async url => url === '/api/upload/postprocess'
    ? response({ok:true,running:true})
    : new Promise(resolve=>{finish=resolve;}));
  const processing = f.context.runUploadPostprocess(null, ()=>f.context.showUploadCompleteDialog());
  await new Promise(setImmediate);
  assert.equal(f.dialog.open, true);
  assert.match(f.elements.uploadCompleteCloseHint.textContent, /lukke browseren/);
  finish(response({ok:true,running:false,result:{ok:true}}));
  await processing;
});

test('rejected postprocessing does not show a safe-to-close success message', async () => {
  const f = fixture(async()=>({ok:false,json:async()=>({ok:false,error:'busy'})}));
  await assert.rejects(f.context.runUploadPostprocess(null, ()=>f.context.showUploadCompleteDialog()), /busy/);
  assert.equal(f.dialog.open, false);
});

test('unfinished, failed, stopped, and empty transfers do not show completion', () => {
  for (const change of [c=>c.uploadQueue.push({}), c=>c.uploadUiState.failedFiles=1,
    c=>c.uploadStopRequested=true, c=>c.uploadSessionSavedTotal=0, c=>c.isUploadRunning=()=>true]) {
    const f=fixture(); change(f.context);
    assert.equal(f.context.showUploadCompleteDialog(), false);
    assert.equal(f.dialog.open, false);
  }
});

test('opening an already visible completion dialog is harmless', () => {
  const f=fixture();
  f.context.showUploadCompleteDialog(); f.context.showUploadCompleteDialog();
  assert.equal(f.dialog.shows,1);
});
