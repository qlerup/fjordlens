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
    els: {logsError: {textContent: '', hidden: true}}, logViewRevision: 0, AbortController,
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

test('server errors are visible and a successful retry clears the message', async () => {
  let failing = true;
  const f = fixture(async () => failing ? {ok:false, status:500} : response());
  f.ctx.startLogs(); await tick();
  assert.match(f.ctx.els.logsError.textContent, /HTTP 500/);
  assert.equal(f.ctx.els.logsError.hidden, false);
  assert.equal(f.timers.size, 1);
  failing = false;
  const retry = f.timers.values().next().value;
  f.timers.clear();
  await retry();
  assert.equal(f.ctx.els.logsError.hidden, true);
  assert.equal(f.ctx.state.logItems.length, 1);
});

test('expired sessions and forbidden access stop polling with an explanation', async () => {
  for (const status of [401,403]) {
    const f = fixture(async () => ({ok:false, status}));
    f.ctx.startLogs(); await tick();
    assert.equal(f.ctx.state.logsRunning, false);
    assert.equal(f.timers.size, 0);
    assert.equal(f.ctx.els.logsError.hidden, false);
    assert.match(f.ctx.els.logsError.textContent, status === 401 ? /Log ind igen/ : /administrator/);
  }
});

test('invalid log payload is reported without discarding existing rows', async () => {
  const f = fixture(async () => ({ok:true, status:200, json:async () => ({})}));
  f.ctx.state.logItems.push({id:9});
  f.ctx.startLogs(); await tick();
  assert.match(f.ctx.els.logsError.textContent, /ugyldigt logsvar/);
  assert.equal(f.ctx.state.logItems.length, 1);
});

test('admin identity loading automatically starts logs after page reload without a Start button', async () => {
  const f = fixture(async () => response());
  const logFetch = f.ctx.fetch;
  f.ctx.fetch = async (url, options) => url === '/api/me'
    ? {ok:true, json:async () => ({ok:true, item:{id:1,role:'admin'}})}
    : logFetch(url, options);
  f.ctx.document = {querySelector: () => null, querySelectorAll: () => []};
  vm.runInContext(source.slice(source.indexOf('// Resolve user role early'),
    source.indexOf('setView(state.view, { syncUrl: false')), f.ctx);
  await tick();
  assert.equal(f.ctx.state.currentUser.role, 'admin');
  assert.equal(f.ctx.state.logsRunning, true);
  assert.equal(f.calls.length, 1);
  assert.equal(f.ctx.state.logItems.length, 1);
  assert.equal(f.timers.size, 1);
  assert.doesNotMatch(fs.readFileSync('templates/index.html', 'utf8'), /id="(?:logsStart|mainLogsStart)"/);
});

test('non-admin sessions never automatically request administrator logs', async () => {
  for (const role of ['user', 'manager']) {
    const f = fixture(async () => response());
    const logFetch = f.ctx.fetch;
    f.ctx.fetch = async (url, options) => url === '/api/me'
      ? {ok:true, json:async () => ({ok:true, item:{id:2,role}})}
      : logFetch(url, options);
    f.ctx.document = {querySelector: () => null, querySelectorAll: () => []};
    vm.runInContext(source.slice(source.indexOf('// Resolve user role early'),
      source.indexOf('setView(state.view, { syncUrl: false')), f.ctx);
    await tick();
    assert.equal(f.ctx.state.logsRunning, false);
    assert.equal(f.calls.length, 0);
  }
});

test('starting twice schedules one timer, and stopping clears it', async () => {
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
