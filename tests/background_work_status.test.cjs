const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('static/app.js', 'utf8');
const code = source.slice(source.indexOf('let backgroundWorkTimer = null;'), source.indexOf('let uploadPostprocessResumeActive = false;'));
function fixture() {
  const responses = new Map();
  const panel = {textContent: '', hidden: true, classList: {toggle(name, on) { panel.hidden = on; }}};
  let calls = 0, tick, timerCount = 0;
  const ctx = vm.createContext({Map, AbortSignal,
    els: {uploadTopProcessRow: null}, tr: key => key,
    localUpload: false, localPostprocess: false,
    isUploadRunning: () => ctx.localUpload,
    isUploadPostprocessPhase: () => ctx.localPostprocess,
    ensureUploadTopStatusRefs: () => {},
    showTopStatusMessage: (text, pct) => {panel.textContent=text;panel.pct=pct;panel.hidden=false;panel.indeterminate=false;},
    hideTopStatusMessage: () => {panel.hidden=true;},
    setTopStatusIndeterminate: on => {panel.indeterminate=on;},
    postprocessPhaseLabel: key => key,
    fetch: async (url, options) => {
      calls++;
      assert.equal(options.method, undefined, 'monitor must never start or stop work');
      const response = await (responses.get(url) || {ok: true, running: false});
      if (response instanceof Error) throw response;
      return {ok: true, json: async () => response};
    }, window: {setInterval(fn) { tick = fn; timerCount++; return 1; }}
  });
  vm.runInContext(code, ctx);
  return {ctx, panel, responses, get calls() {return calls;}, get timerCount() {return timerCount;}, tick: () => tick()};
}
test('discovers a job after idle and keeps monitoring after completion', async () => {
  const f = fixture();
  f.ctx.startBackgroundWorkStatus(); f.ctx.startBackgroundWorkStatus();
  await new Promise(setImmediate);
  assert.equal(f.timerCount, 1);
  assert.equal(f.panel.hidden, true);
  f.responses.set('/api/upload/postprocess/status', {ok: true, running: true, phase: 'faces', stage_total: 156, stage_processed: 19});
  await f.tick();
  assert.equal(f.panel.hidden, false);
  assert.match(f.panel.textContent, /faces.*19\/156.*12%/);
  f.responses.set('/api/upload/postprocess/status', {ok: true, running: false});
  await f.tick();
  assert.equal(f.panel.hidden, true);
  f.responses.set('/api/faces/status', {ok: true, running: true, processed: 4, total: 20});
  await f.tick();
  assert.match(f.panel.textContent, /upload_proc_faces.*4\/20.*20%/);
});
test('failed status request preserves active job with reconnecting label until confirmed finished', async () => {
  const f = fixture();
  const url = '/api/upload/postprocess/status';
  f.responses.set(url, {ok: true, running: true, phase: 'faces', stage_total: 156, stage_processed: 19});
  await f.ctx.pollBackgroundWorkStatus();
  f.responses.set(url, new Error('offline'));
  await f.ctx.pollBackgroundWorkStatus();
  assert.equal(f.panel.hidden, false);
  assert.match(f.panel.textContent, /19\/156.*background_status_reconnecting/);
  f.responses.set(url, {ok: false});
  await f.ctx.pollBackgroundWorkStatus();
  assert.equal(f.panel.hidden, false);
  f.responses.set(url, {ok: true, running: false});
  await f.ctx.pollBackgroundWorkStatus();
  assert.equal(f.panel.hidden, true);
});
test('polling is single flight and independent jobs remain visible', async () => {
  const f = fixture();
  f.responses.set('/api/upload/direct-postprocess/status', {ok: true, running: true, phase: 'metadata'});
  f.responses.set('/api/ai/status', {ok: true, running: true, processed: 3, total: 10});
  await Promise.all([f.ctx.pollBackgroundWorkStatus(), f.ctx.pollBackgroundWorkStatus()]);
  assert.equal(f.calls, 5);
  assert.match(f.panel.textContent, /metadata/);
  assert.equal(f.panel.indeterminate, true);
});

test('face progress renders without waiting for another slow status source', async () => {
  const f = fixture();
  let release;
  f.responses.set('/api/ai/status', new Promise(resolve => { release = resolve; }));
  f.responses.set('/api/faces/status', {ok: true, running: true, processed: 7, total: 20});
  const polling = f.ctx.pollBackgroundWorkStatus();
  await new Promise(setImmediate);
  assert.equal(f.panel.hidden, false);
  assert.match(f.panel.textContent, /upload_proc_faces.*7\/20.*35%/);
  release({ok: true, running: false});
  await polling;
});

test('real page includes the background monitor outside view-specific header controls', () => {
  const html = fs.readFileSync('templates/index.html', 'utf8');
  const main = html.indexOf('<main class="main">');
  const topbar = html.indexOf('<header id="topbar"');
  const monitor = html.slice(main, topbar);
  assert.match(monitor, /id="uploadTopStatus"/);
  assert.match(monitor, /role="status"/);
  assert.match(monitor, /aria-live="polite"/);
  assert.doesNotMatch(html, /id="backgroundWorkStatus"/);
  assert.equal((html.match(/id="uploadTopStatus"/g)||[]).length,1);
});


test('fresh page discovers conversion percentage without a browser upload queue', async () => {
  const f=fixture();
  f.responses.set('/api/upload/postprocess/status',{ok:true,running:true,phase:'converting',stage_total:37,stage_processed:22});
  await f.ctx.pollBackgroundWorkStatus();
  assert.match(f.panel.textContent,/converting.*22\/37.*59%/);
  assert.equal(f.panel.pct,59);
  f.responses.set('/api/upload/postprocess/status',new Error('offline'));
  await f.ctx.pollBackgroundWorkStatus();
  assert.equal(f.panel.pct,59);
  assert.match(f.panel.textContent,/background_status_reconnecting/);
});

test('multiple independent jobs share the same progress component', async () => {
  const f=fixture();
  const row={innerHTML:'',classList:{remove(){}}};
  f.ctx.els.uploadTopProcessRow=row;
  f.ctx.els.uploadTopStatus={classList:{add(){}}};
  f.ctx.escapeHtml=s=>s.replaceAll('<','&lt;');
  f.responses.set('/api/upload/postprocess/status',{ok:true,running:true,phase:'<convert>',stage_total:37,stage_processed:22});
  f.responses.set('/api/ai/status',{ok:true,running:true,processed:3,total:10});
  await f.ctx.pollBackgroundWorkStatus();
  assert.match(row.innerHTML,/59%/);
  assert.match(row.innerHTML,/30%/);
  assert.doesNotMatch(row.innerHTML,/<convert>/);
});

test('background polls never replace active browser upload progress', async () => {
  const f=fixture();f.panel.textContent='Uploader 45%';f.panel.hidden=false;
  f.ctx.localUpload=true;
  f.responses.set('/api/faces/status',{ok:true,running:true,total:20,processed:7});
  await f.ctx.pollBackgroundWorkStatus();
  assert.equal(f.panel.textContent,'Uploader 45%');
  f.ctx.localUpload=false;f.ctx.renderBackgroundWorkStatus();
  assert.match(f.panel.textContent,/35%/);
});
