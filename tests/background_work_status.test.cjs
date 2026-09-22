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
    document: {getElementById: () => panel}, tr: key => key,
    postprocessPhaseLabel: key => key,
    fetch: async (url, options) => {
      calls++;
      assert.equal(options.method, undefined, 'monitor must never start or stop work');
      const response = responses.get(url) || {ok: true, running: false};
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
  assert.match(f.panel.textContent, /faces 19\/156/);
  f.responses.set('/api/upload/postprocess/status', {ok: true, running: false});
  await f.tick();
  assert.equal(f.panel.hidden, true);
  f.responses.set('/api/faces/status', {ok: true, running: true, processed: 4, total: 20});
  await f.tick();
  assert.match(f.panel.textContent, /upload_proc_faces 4\/20/);
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
  assert.match(f.panel.textContent, /upload_proc_embeddings 3\/10/);
});
