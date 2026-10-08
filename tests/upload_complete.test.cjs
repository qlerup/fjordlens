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
    isMobileSelectionGestureDevice:()=>true,
    document:{getElementById:id=>elements[id]}, fetch:fetcher,
    Date, AbortSignal, window:{setTimeout:fn=>fn()}, uploadPostprocessPollDelayMs:()=>0,
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

test('desktop uploads never open the completion popup', () => {
  const f = fixture();
  f.context.isMobileSelectionGestureDevice = () => false;
  assert.equal(f.context.showUploadCompleteDialog(), false);
  assert.equal(f.dialog.shows, 0);
});

test('upload processing survives network, HTTP, JSON and incomplete status responses', async () => {
  const replies = [
    response({ok:true,running:true}),
    response({ok:true,running:true,phase:'faces',stage_processed:4,stage_total:20}),
    new Error('offline'),
    {ok:false,status:502,json:async()=>({error:'Bad gateway'})},
    {ok:true,json:async()=>{throw new Error('invalid JSON');}},
    response({ok:true}),
    response({ok:true,running:true,phase:'faces',stage_processed:10,stage_total:20}),
    response({ok:true,running:false,result:{ok:true,faces_done:20}}),
  ];
  const f = fixture(async () => {
    assert.ok(replies.length, 'must not read beyond confirmed completion');
    const next = replies.shift();
    if (next instanceof Error) throw next;
    return next;
  });
  const progress = [];
  const result = await f.context.runUploadPostprocess(s=>progress.push(s.stage_processed));
  assert.deepEqual(progress, [4,10]);
  assert.equal(result.faces_done,20);
});

test('resumed upload retains phase during lost status and clears only on confirmed completion', async () => {
  let calls = 0, finish;
  const f = fixture(async () => {
    calls++;
    if (calls === 1) return response({ok:true,running:true,phase:'faces',stage_processed:4,stage_total:20});
    if (calls === 2) throw new Error('offline');
    return new Promise(resolve=>{finish=resolve;});
  });
  Object.assign(f.context, {
    uploadQueuePumpRunning:false, postprocessPhaseLabel:key=>key, shortRelName:()=>'',
    renderUploadMonitor:()=>{}, maybeRefreshPhotosDuringPostprocess:async()=>{},
  });
  f.context.state.view = 'timeline';
  f.context.uploadUiState.totalFiles = 0;
  f.context.uploadUiState.processedFiles = 0;
  vm.runInContext(source.slice(source.indexOf('let uploadPostprocessResumeActive = false;'),
    source.indexOf('function uploadSingleFileTus(')), f.context);
  const polling = f.context.resumeUploadPostprocessAfterRefresh();
  await new Promise(setImmediate);
  assert.equal(f.context.uploadUiState.currentPhaseLabel,'faces');
  assert.equal(f.context.uploadUiState.currentLoaded,4);
  finish(response({ok:true,running:false}));
  await polling;
  assert.equal(f.context.uploadUiState.currentPhaseLabel,'');
});

test('revoked access is not retried forever', async () => {
  let calls=0;
  const f=fixture(async()=>{calls++;return {status:401,ok:false};});
  await assert.rejects(f.context.readUploadPostprocessStatus('/status',Date.now()+10000), /Adgang/);
  assert.equal(calls,1);
});
