const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

function setup({merged = true, ok = true, open = false} = {}) {
  const calls = [], loaded = [], refreshed = [], statuses = [];
  const context = vm.createContext({
    state: {view: 'personer', personView: {mode: open ? 'photos' : 'grid', personId: 7}},
    tr: value => value, showStatus: (...args) => statuses.push(args),
    loadPersonPhotos: async (...args) => loaded.push(args),
    reconcilePeopleGrid: items => refreshed.push(items),
    fetch: async (url, options) => {
      calls.push([url, options]);
      if (url === '/api/people/7/rename') return {ok, json: async () => ({ok, merged, to_id: 9, name: 'Anna'})};
      if (url === '/api/people') return {ok: true, json: async () => ({items: [{id: 9, count: 1886}]})};
      throw new Error('Unexpected expensive follow-up: ' + url);
    }
  });
  const source = fs.readFileSync('static/app.js', 'utf8');
  vm.runInContext(source.slice(source.indexOf('async function renameOrMergePerson('), source.indexOf('async function matchUnknownFaces(')), context);
  return {context, calls, loaded, refreshed, statuses};
}

test('manual merge does not start an automatic unknown-face scan', async () => {
  const {context, calls, refreshed} = setup();
  assert.equal(await context.renameOrMergePerson(7, 'Anna', {action: 'merge', target_id: 9}), true);
  assert.deepEqual(calls.map(c => c[0]), ['/api/people/7/rename', '/api/people']);
  assert.equal(JSON.parse(calls[0][1].body).target_id, 9);
  assert.equal(refreshed[0][0].count, 1886);
});

test('open source person switches to merged target', async () => {
  const {context, loaded} = setup({open: true});
  assert.equal(await context.renameOrMergePerson(7, 'Anna', {action: 'merge', target_id: 9}), true);
  assert.deepEqual(loaded, [[9, 'Anna']]);
});

test('failed merge does not refresh or start other processing', async () => {
  const {context, calls, loaded, refreshed} = setup({ok: false, open: true});
  assert.equal(await context.renameOrMergePerson(7, 'Anna'), false);
  assert.equal(calls.length, 1);
  assert.equal(loaded.length, 0);
  assert.equal(refreshed.length, 0);
});
