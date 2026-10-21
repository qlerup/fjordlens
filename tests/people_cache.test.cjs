const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

function setup() {
  let warm, resolveFetch, requests = 0, skeletons = 0, updates = 0;
  const grid = {appendChild() { skeletons += 6; }, innerHTML: ''};
  const context = vm.createContext({
    state: {view: 'photos', personView: {mode: 'list'}, people: [], currentUser: {id: 1}},
    els: {grid},
    loadPeople() {}, renderGrid() {},
    reconcilePeopleGrid(items) { updates++; },
    window: {requestIdleCallback(fn) { warm = fn; }},
    document: {
      querySelectorAll() { return Array.from({length: skeletons}, () => ({remove() { skeletons--; }})); },
      getElementById() { return true; },
      createDocumentFragment() { return {appendChild() {}}; },
      createElement() { return {}; },
    },
    sessionStorage: {getItem() { return null; }, setItem() {}},
    fetch() { requests++; return new Promise(resolve => { resolveFetch = resolve; }); },
    Date, performance, console,
  });
  vm.runInContext(fs.readFileSync('static/people_cache.js', 'utf8'), context);
  return {
    context, warm: () => warm(),
    finish: async () => {
      resolveFetch({ok: true, json: async () => ({ok: true, items: [{id: 7, name: 'Anna'}]})});
      await new Promise(resolve => setImmediate(resolve));
    },
    counts: () => ({requests, skeletons, updates}),
  };
}

test('opening People during prefetch renders its result and removes skeletons', async () => {
  const h = setup();
  h.warm();
  h.context.state.view = 'personer';
  await h.context.loadPeople();
  assert.deepEqual(h.counts(), {requests: 1, skeletons: 6, updates: 0});
  await h.finish();
  assert.deepEqual(h.counts(), {requests: 1, skeletons: 0, updates: 1});
  assert.equal(h.context.state.people[0].id, 7);
});

test('prefetch without navigation updates cache without rendering another view', async () => {
  const h = setup();
  h.warm();
  await h.finish();
  assert.equal(h.counts().updates, 0);
  assert.equal(h.context.state._peopleCache.items[0].id, 7);
});

for (const destination of ['photos', 'person-detail', 'hidden-list']) {
  test(`joined prefetch does not overwrite ${destination} after navigation`, async () => {
    const h = setup();
    h.warm();
    h.context.state.view = 'personer';
    await h.context.loadPeople();
    if (destination === 'photos') h.context.state.view = 'photos';
    if (destination === 'person-detail') h.context.state.personView.mode = 'photos';
    if (destination === 'hidden-list') h.context.state.showHiddenPeople = true;
    await h.finish();
    assert.equal(h.counts().updates, 0);
    assert.equal(h.context.state._peopleCache.items[0].id, 7);
  });
}
