const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('static/app.js', 'utf8');
const polling = source.slice(source.indexOf('let logsPollTimer ='), source.indexOf('async function clearLogs()'));

function fixture(fetcher) {
  const calls = [], timers = new Map();
  let id = 0;
  const ctx = vm.createContext({
    state: {logsRunning: false, logsAfter: 0, logItems: []},
    els: {logsStart: {textContent: 'Start'}}, logViewRevision: 0, AbortController,
    fetch: (url, options) => { calls.push({url, options}); return fetcher(url, options); },
    setTimeout: fn => { timers.set(++id, fn); return id; },
    clearTimeout: id => timers.delete(id),
    applyLogResolutions() {}, appendLogItem: item => ctx.state.logItems.push(item),
    renderLogList() {}, classifySeverity: () => 'info',
  });
  vm.runInContext(polling, ctx);
  return {ctx, calls, timers};
}
const response = (id=1) => ({ok: true, status:200, json: async () => ({items:[{id,event:'upload_start'}], next:id})});
const tick = () => new Promise(setImmediate);

test('admin identity loading leaves logs stopped after page reload', async () => {
  const f = fixture(async () => response());
  f.ctx.fetch = async () => ({ok:true, json:async () => ({ok:true, item:{id:1,role:'admin'}})});
  f.ctx.document = {querySelector: () => null, querySelectorAll: () => []};
  vm.runInContext(source.slice(source.indexOf('// Resolve user role early'),
    source.indexOf('setView(state.view, { syncUrl: false')), f.ctx);
  await tick();
  assert.equal(f.ctx.state.currentUser.role, 'admin');
  assert.equal(f.ctx.state.logsRunning, false);
  assert.equal(f.calls.length, 0);
  assert.equal(f.timers.size, 0);
  assert.match(fs.readFileSync('templates/index.html', 'utf8'), /id="logsStart" class="btn">Start</);
});

test('manual Start polls once, schedules one timer, and Stop clears it', async () => {
  const f = fixture(async () => response());
  await f.ctx.pollLogs();
  assert.equal(f.calls.length, 0);
  f.ctx.startLogs(); f.ctx.startLogs();
  await tick();
  assert.equal(f.calls.length, 1);
  assert.equal(f.ctx.state.logItems.length, 1);
  assert.equal(f.timers.size, 1);
  f.ctx.stopLogs();
  assert.equal(f.timers.size, 0);
  assert.equal(f.ctx.els.logsStart.textContent, 'Start');
});

test('Stop aborts an in-flight request and ignores its late response', async () => {
  let resolve;
  const f = fixture(() => new Promise(r => {resolve=r;}));
  f.ctx.startLogs();
  f.ctx.stopLogs();
  assert.equal(f.calls[0].options.signal.aborted, true);
  resolve(response());
  await tick();
  assert.equal(f.ctx.state.logItems.length, 0);
  assert.equal(f.timers.size, 0);
});

test('rapid Stop and Start keeps old replies out of the new polling loop', async () => {
  const pending = [];
  const f = fixture(() => new Promise(resolve => pending.push(resolve)));
  f.ctx.startLogs(); f.ctx.stopLogs(); f.ctx.startLogs();
  pending[1](response(2)); await tick();
  pending[0](response(1)); await tick();
  assert.deepEqual(Array.from(f.ctx.state.logItems, item => item.id), [2]);
  assert.equal(f.ctx.state.logsAfter, 2);
  assert.equal(f.timers.size, 1);
});
