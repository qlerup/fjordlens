const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

async function setup(confirmed, count = 3) {
  const calls = [], prompts = [], scan = {}, status = {}, bar = {removeAttribute() {}};
  const root = {querySelector: key => ({'[data-scan]': scan, '[data-status]': status, '[data-progress]': bar})[key]};
  const ctx = vm.createContext({
    document: {getElementById: () => root, addEventListener: (_, fn) => fn()},
    window: {confirm: text => {prompts.push(text); return confirmed;}},
    clearTimeout() {}, setTimeout() {},
    fetch: async (_, options) => {
      const body = options.body ? JSON.parse(options.body) : null;
      calls.push(body);
      const data = body?.action === 'scan' ? {ok: true, count, token: 'reviewed-selection'}
        : body?.action === 'start' ? {ok: true} : {ok: true, running: false};
      return {ok: true, json: async () => data};
    },
  });
  vm.runInContext(fs.readFileSync('static/pending_uploads.js', 'utf8'), ctx);
  await new Promise(setImmediate);
  return {calls, prompts, scan, status};
}

test('scanning and cancelling never starts processing', async () => {
  const ui = await setup(false);
  await ui.scan.onclick();
  assert.match(ui.status.textContent, /3 filer/);
  assert.equal(ui.prompts.length, 1);
  assert.equal(ui.calls.filter(call => call?.action === 'start').length, 0);
});

test('confirming starts exactly the reviewed selection', async () => {
  const ui = await setup(true);
  await ui.scan.onclick();
  assert.match(ui.prompts[0], /Ønsker du at færdigbehandle filerne/);
  assert.deepEqual(ui.calls.filter(call => call?.action === 'start'), [{action: 'start', token: 'reviewed-selection'}]);
});

test('empty search neither prompts nor starts processing', async () => {
  const ui = await setup(true, 0);
  await ui.scan.onclick();
  assert.equal(ui.prompts.length, 0);
  assert.equal(ui.calls.filter(call => call?.action === 'start').length, 0);
});
