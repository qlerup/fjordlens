const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('static/app.js', 'utf8');
const code = source.slice(source.indexOf('const logRetryMonitors ='), source.indexOf('function appendLogItem('));

class Element {
  constructor() { this.children = []; this.classList = {add() {}}; }
  set innerHTML(value) { this.children = []; }
  append(...children) { this.children.push(...children); }
  appendChild(child) { this.children.push(child); }
  setAttribute() {}
  addEventListener(event, fn) { this[event] = fn; }
}

function fixture() {
  const items = [1, 2].map(id => ({id, event: 'error', retry_stage: 'faces', _extra: `file${id}.jpg`}));
  const box = new Element(), timers = [], calls = [];
  const ctx = vm.createContext({
    state: {uiLanguage: 'da', logItems: items, logCategory: 'all', logPage: 1},
    els: {mainLogsBox: box}, LOG_CATEGORIES: ['all'], LOG_PAGE_SIZE: 50,
    logCategoryLabels: () => ({}), classifySeverity: () => 'err', fmtLogTime: () => '20:48',
    document: {createElement: () => new Element()},
    window: {setTimeout(fn) { timers.push(fn); }},
    fetch: async (url, options) => {
      calls.push({url, options});
      if (url.startsWith('/api/logs?')) return {ok: true, json: async () => ({resolved_ids: [2]})};
      return {ok: true, json: async () => ({ok: true, status: options?.method === 'POST' ? 'running' : 'succeeded'})};
    },
  });
  vm.runInContext(code, ctx);
  return {ctx, items, box, timers, calls};
}

test('each failure has its own button and retry targets only the selected log', async () => {
  const f = fixture();
  f.ctx.renderLogList();
  assert.equal(f.box.children.length, 2);
  const buttons = f.box.children.map(row => row.children[2].children[0]);
  assert.equal(buttons[0].textContent, 'Prøv igen');
  await buttons[0].click();
  assert.equal(f.calls[0].url, '/api/logs/2/retry');
  assert.equal(f.calls[0].options.method, 'POST');
  assert.equal(f.items[0].retry, undefined);
  assert.equal(f.box.children[0].children[2].children[0].textContent, 'Prøver igen…');
  f.timers.shift()();
  await new Promise(setImmediate);
  assert.equal(f.box.children.length, 1);
  assert.equal(f.ctx.state.logItems[0].id, 1);
});

test('busy or failed request keeps the row retryable and shows the reason', async () => {
  const f = fixture();
  f.ctx.fetch = async () => ({ok: false, json: async () => ({error: 'Vent til behandlingen er færdig'})});
  await f.ctx.retryLogItem(f.items[0]);
  const actions = f.box.children[1].children[2];
  assert.equal(actions.children[0].disabled, false);
  assert.equal(actions.children[0].textContent, 'Prøv igen');
  assert.equal(actions.children[1].textContent, 'Vent til behandlingen er færdig');
});

test('unsupported log entries have no misleading retry action', () => {
  const f = fixture();
  delete f.items[0].retry_stage;
  f.ctx.renderLogList();
  assert.equal(f.box.children[1].children.length, 2);
});

test('resolution from another retry button removes only the specified log IDs', () => {
  const f = fixture();
  f.ctx.applyLogResolutions({resolved_ids: [1]});
  f.ctx.renderLogList();
  assert.equal(f.ctx.state.logItems.length, 1);
  assert.equal(f.ctx.state.logItems[0].id, 2);
});

test('clear preserves server-confirmed unresolved rows even with log polling stopped', async () => {
  const f = fixture();
  f.ctx.showStatus = () => assert.fail('unexpected error');
  f.ctx.fetch = async () => ({ok: true, json: async () => ({ok: true, items: [f.items[0]]})});
  vm.runInContext(source.slice(source.indexOf('async function clearLogs()'),
    source.indexOf('els.logsStart && els.logsStart.addEventListener')), f.ctx);
  await f.ctx.clearLogs();
  assert.equal(f.ctx.state.logItems.length, 1);
  assert.equal(f.ctx.state.logItems[0].id, 1);
  assert.equal(f.box.children.length, 1);
});

test('failed clear keeps visible logs intact', async () => {
  const f = fixture();
  let message;
  f.ctx.showStatus = error => {message = error;};
  f.ctx.fetch = async () => ({ok: false, json: async () => ({error: 'Disk full'})});
  vm.runInContext(source.slice(source.indexOf('async function clearLogs()'),
    source.indexOf('els.logsStart && els.logsStart.addEventListener')), f.ctx);
  await f.ctx.clearLogs();
  assert.equal(f.ctx.state.logItems.length, 2);
  assert.equal(message, 'Disk full');
});
