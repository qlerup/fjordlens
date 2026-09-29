const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { join } = require('node:path');
const vm = require('node:vm');
const source = readFileSync(join(__dirname, '../static/app.js'), 'utf8');
function fixture() {
  let clock = 0, requests = 0;
  const context = vm.createContext({ window: {}, URLSearchParams, console, AbortController,
    state: { view: 'timeline', q: '', sort: 'date', items: [], currentUser: { id: 1 }, photosPageLimit: 300 },
    els: { viewTitle: {}, viewSubtitle: {} }, renderGrid() {}, renderStats() {}, showStatus() {},
    navLabels: () => ({}), restoreGalleryScrollAnchor() {}, restoreMapperView: () => false,
    _normalizeMapperPath: s => s, _normalizeMapperSort: s => s || 'date', estimateMapperPageLimit: () => 100,
    appendPersonSearchParams() {}, appendGalleryPage() {},
    handleMapperDiskSyncStatus() {}, hydrateMapperItems() {}, setupMapperGhostLoading() {},
    isPagedGalleryView: view => ['timeline', 'mapper', 'kameraer', 'favorites'].includes(view),
    fetch: async () => { requests++; return { ok: true, headers: { get: () => 'application/json' },
      json: async () => ({ items: [{ id: requests }], has_more: false, next_offset: 1, total: 1 }) }; },
  });
  vm.runInContext(readFileSync(join(__dirname, '../static/gallery_cache.js'), 'utf8'), context);
  context.galleryDataCache = context.window.FjordLensGalleryCache.createCache({ now: () => clock });
  vm.runInContext(`let photosLoadPromise = null; let photosRequestSequence = 0; let photosAbortController = null;
    function galleryCacheKey(query) { return JSON.stringify([state.currentUser.id, query]); }
    ${source.slice(source.indexOf('async function loadPhotos('), source.indexOf('async function loadPeople('))}`, context);
  return { context, cache: context.galleryDataCache, requests: () => requests, advance: n => clock += n,
    load: (append=false, cached=true) => context.loadPhotos(append, false, cached) };
}
for (const view of ['timeline', 'mapper', 'kameraer', 'favorites']) {
  test(`${view}: repeat navigation avoids fetch, edits and expiry refresh`, async () => {
    const f = fixture(); f.context.state.view = view;
    await f.load(); await f.load();
    assert.equal(f.requests(), 1);
    f.context.state.items[0].id = 999;
    await f.load(); assert.equal(f.context.state.items[0].id, 1, 'rendered objects do not mutate the cache');
    await f.load(false, false); assert.equal(f.requests(), 2, 'edit refresh bypasses old data');
    await f.load(); assert.equal(f.requests(), 2);
    f.advance(60000); await f.load(); assert.equal(f.requests(), 3);
  });
}
test('folders, filters and accounts never reuse each other’s pages', async () => {
  const f = fixture(); f.context.state.view = 'mapper';
  f.context.state.mapperPath = 'a'; await f.load();
  f.context.state.mapperPath = 'b'; await f.load();
  f.context.state.mapperPath = 'a'; await f.load(); assert.equal(f.requests(), 2);
  f.context.state.q = 'jul'; await f.load();
  f.context.state.currentUser.id = 2; await f.load(); assert.equal(f.requests(), 4);
});
test('invalidation rejects an older request completing after an edit', () => {
  const f = fixture(), generation = f.cache.generation();
  f.cache.clear(); f.cache.set('page', { items: ['deleted'] }, generation);
  assert.equal(f.cache.get('page'), null);
});
test('cache is bounded and evicts least recently visited pages', () => {
  const f = fixture(); const c = f.context.window.FjordLensGalleryCache.createCache({ maxEntries: 2 });
  c.set('a', {}); c.set('b', {}); c.get('a'); c.set('c', {});
  assert.equal(c.get('b'), null); assert.notEqual(c.get('a'), null);
});

for (const view of ['timeline', 'favorites', 'kameraer', 'mapper']) {
  test(`${view}: total stays stable when another page loads`, async () => {
    const f = fixture();
    f.context.state.view = view;
    f.context.state.cameraModel = 'Test camera';
    let request = 0;
    f.context.fetch = async url => {
      const first = request++ === 0;
      assert.equal(new URLSearchParams(url.split('?')[1]).get('include_total'), first ? '1' : null);
      return { ok: true, headers: { get: () => 'application/json' },
        json: async () => ({ items: [{ id: request }], total: first ? 350 : null,
          has_more: true, next_offset: request * 90 }) };
    };
    f.context.els.grid = { querySelectorAll: () => [] };
    f.context.expandMapperGhostChunk = () => {};
    await f.load();
    assert.equal(f.context.state.photosTotalItems, 350);
    await f.load(true);
    assert.equal(f.context.state.photosTotalItems, 350);
    if (view === 'mapper') assert.equal(f.context.state.mapperTotalItems, 350);
    assert.equal(f.context.state.photosHasMore, true);
    f.context.document = { querySelector: () => null };
    f.context.tr = key => key;
    f.context.els.photoCount = {};
    vm.runInContext(source.slice(source.indexOf('function renderStats()'), source.indexOf('function photoframeSourceLabel(')), f.context);
    f.context.renderStats();
    assert.equal(f.context.els.photoCount.textContent, 350);
  });
}
