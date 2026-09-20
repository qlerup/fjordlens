const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

function setup({merged = true, ok = true, open = false} = {}) {
  const calls = [], loaded = [], refreshed = [], matches = [], statuses = [];
  const context = vm.createContext({
    state: {view: 'personer', personView: {mode: open ? 'photos' : 'grid', personId: 7}},
    tr: value => value, showStatus: (...args) => statuses.push(args),
    loadPersonPhotos: async (...args) => loaded.push(args),
    reconcilePeopleGrid: items => refreshed.push(items),
    fetch: async (url, options) => {
      calls.push([url, options]);
      if (url === '/api/people/7/rename') return {ok, json: async () => ({ok, merged, to_id: 9, name: 'Anna'})};
      if (url === '/api/people') return {ok: true, json: async () => ({items: [{id: 9, count: 1886}]})};
      if (url === '/api/faces/match-unknown') return new Promise(resolve => matches.push(resolve));
      throw new Error('Unexpected expensive follow-up: ' + url);
    }
  });
  const source = fs.readFileSync('static/app.js', 'utf8');
  vm.runInContext(source.slice(source.indexOf('async function renameOrMergePerson('), source.indexOf('async function matchUnknownFaces(')), context);
  return {context, calls, loaded, refreshed, matches, statuses};
}

test('manual merge completes while automatic matching is still pending, without duplicate training', async () => {
  const {context, calls, refreshed, matches} = setup();
  assert.equal(await context.renameOrMergePerson(7, 'Anna', {action: 'merge', target_id: 9}), true);
  assert.deepEqual(calls.map(c => c[0]), ['/api/people/7/rename', '/api/people', '/api/faces/match-unknown']);
  assert.equal(matches.length, 1, 'matching has started but has not completed');
  assert.equal(JSON.parse(calls[0][1].body).target_id, 9);
  assert.equal(refreshed[0][0].count, 1886);
});

test('several merges during a match coalesce into one follow-up pass', async () => {
  const {context, matches} = setup();
  await context.renameOrMergePerson(7, 'Anna');
  await context.renameOrMergePerson(7, 'Anna');
  await context.renameOrMergePerson(7, 'Anna');
  assert.equal(matches.length, 1);
  matches[0]({ok: true, json: async () => ({ok: true, matched: 0})});
  await new Promise(setImmediate);
  assert.equal(matches.length, 2);
  matches[1]({ok: true, json: async () => ({ok: true, matched: 0})});
  await new Promise(setImmediate);
  assert.equal(matches.length, 2);
});

test('background results update people and failures do not turn a saved merge into failure', async () => {
  const {context, matches, refreshed, statuses} = setup();
  assert.equal(await context.renameOrMergePerson(7, 'Anna'), true);
  matches[0]({ok: true, json: async () => ({ok: true, matched: 3, clusters_promoted: 1})});
  await new Promise(setImmediate);
  assert.equal(refreshed.length, 2);
  assert.equal(await context.renameOrMergePerson(7, 'Anna'), true);
  matches[1]({ok: false, json: async () => ({ok: false})});
  await new Promise(setImmediate);
  assert.match(statuses.at(-1)[0], /Automatisk ansigtsmatch fejlede/);
  assert.equal(await context.renameOrMergePerson(7, 'Anna'), true);
  assert.equal(matches.length, 3, 'a failed pass must release the background runner');
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
