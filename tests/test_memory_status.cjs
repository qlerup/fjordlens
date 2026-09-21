const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '../static/app.js'), 'utf8');
const code = source.slice(source.indexOf('let memoryStatusPending = false;'), source.indexOf('async function pollFacesStatus()'));

test('RAM keeps updating independently of a stopped face queue and clears stale values on failure', async () => {
  const label = {};
  let used = 1.7, failed = false, tick;
  const context = vm.createContext({
    document: {getElementById: () => label}, AbortSignal,
    fetch: async () => {
      if (failed) throw new Error('offline');
      return {ok: true, json: async () => ({ok: true, enabled: true, mode: 'host_global',
        used_bytes: used * 1073741824, total_bytes: 10 * 1073741824})};
    },
    setInterval: (callback, ms) => { assert.equal(ms, 5000); tick = callback; }
  });
  vm.runInContext(code, context);
  const startup = source.match(/pollMemoryStatus\(\);\s*setInterval\(pollMemoryStatus, 5000\);/)[0];
  vm.runInContext(startup, context);
  await new Promise(resolve => setImmediate(resolve));
  assert.match(label.textContent, /1\.70 \/ 10\.00/);
  used = 2.38;
  await tick();
  assert.match(label.textContent, /2\.38 \/ 10\.00/);
  failed = true;
  await tick();
  assert.match(label.textContent, /kunne ikke hente/);
  assert.doesNotMatch(label.textContent, /2\.38/);
});
