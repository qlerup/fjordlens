// Run with: node --test tests/viewer_paging.test.cjs
const assert = require('node:assert/strict');
const { test } = require('node:test');
const { readFileSync } = require('node:fs');
const { join } = require('node:path');
const vm = require('node:vm');
const context = vm.createContext({ window: {} });
vm.runInContext(readFileSync(join(__dirname, '../static/media_preloader.js'), 'utf8'), context);
const { createViewerPager } = context.window.FjordLensMediaPreloader;

function fixture({ total = 37, loaded = 5, index = 4, pageSize = 5 } = {}) {
  const state = { items: Array.from({ length: loaded }, (_, i) => i), index, open: true, context: 'folder-a', requests: 0, updates: 0 };
  const options = {
    getItems: () => state.items,
    getIndex: () => state.index,
    hasMore: () => state.items.length < total,
    isOpen: () => state.open,
    getContext: () => state.context,
    onUpdate: () => state.updates++,
    loadMore: async () => {
      state.requests++;
      const end = Math.min(total, state.items.length + pageSize);
      while (state.items.length < end) state.items.push(state.items.length);
    },
  };
  return { state, options, pager: createViewerPager(options) };
}

test('forward navigation crosses every page and only wraps at the real folder end', async () => {
  const { state, pager } = fixture();
  assert.equal(pager.peek(1), -1, 'an unloaded next photo must not preview the first photo');
  for (let expected = 5; expected < 37; expected++) {
    const index = await pager.target(1);
    assert.equal(index, expected);
    state.index = index;
  }
  assert.equal(await pager.target(1), 0);
  assert.equal(state.requests, 7);
});

test('prefetch fills ten neighbours without downloading the whole folder listing', async () => {
  const { state, pager } = fixture();
  await pager.prefetch();
  assert.equal(state.items.length, 15);
  assert.equal(state.requests, 2);
  state.index++;
  await pager.prefetch();
  assert.equal(state.items.length, 20);
});

test('backwards wrap reaches the actual last photo', async () => {
  const { state, pager } = fixture({ index: 0 });
  assert.equal(pager.peek(-1), -1);
  assert.equal(await pager.target(-1), 36);
  assert.equal(state.items.length, 37);
});

test('prefetch and boundary navigation share their pending page request', async () => {
  const { state, options } = fixture({ total: 15 });
  let release;
  const gate = new Promise(resolve => { release = resolve; });
  const loadMore = options.loadMore;
  options.loadMore = async () => { await gate; await loadMore(); };
  const pager = createViewerPager(options);
  const prefetch = pager.prefetch();
  const target = pager.target(1);
  release();
  assert.equal(await target, 5);
  await prefetch;
  assert.equal(state.requests, 2);
  assert.equal(new Set(state.items).size, 15);
});

test('failed or empty pages keep the current photo and allow a retry', async () => {
  for (const reject of [false, true]) {
    const { state, options } = fixture();
    const loadMore = options.loadMore;
    let fail = true;
    options.loadMore = async () => {
      if (!fail) return loadMore();
      if (reject) throw Error('offline');
    };
    const pager = createViewerPager(options);
    assert.equal(await pager.target(1), -1);
    assert.equal(state.index, 4);
    fail = false;
    assert.equal(await pager.target(1), 5);
  }
});

test('closing the viewer or changing folders cancels a pending navigation', async () => {
  for (const close of [true, false]) {
    const { state, options } = fixture();
    let release;
    options.loadMore = () => new Promise(resolve => { release = resolve; });
    const pager = createViewerPager(options);
    const result = pager.target(1);
    await Promise.resolve();
    if (close) state.open = false;
    else state.context = 'folder-b';
    release();
    assert.equal(await result, -1);
    assert.equal(state.updates, 0);
  }
});

test('complete albums and explicit item lists wrap without requesting pages', async () => {
  const { state, pager } = fixture({ total: 5 });
  assert.equal(await pager.target(1), 0);
  state.index = 0;
  assert.equal(await pager.target(-1), 4);
  await pager.prefetch();
  assert.equal(state.requests, 0);
});
