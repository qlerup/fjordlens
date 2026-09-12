const {test} = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
function setup() {
  const nodes = [];
  class Media extends EventTarget {
    constructor(video = false) { super(); this.video = video; this.isConnected = false; nodes.push(this); }
    set src(value) { this.url = value; }
    get src() { return this.url; }
    removeAttribute(name) { if (name === 'src') this.url = ''; }
    load() {}
    pause() {}
    done() { this.dispatchEvent(new Event(this.video ? 'loadedmetadata' : 'load')); }
  }
  const context = {Image: Media, document: {createElement: () => new Media(true)}, setTimeout, clearTimeout};
  context.window = context;
  vm.runInNewContext(fs.readFileSync('static/media_preloader.js', 'utf8'), context);
  return {nodes, cache: context.FjordLensMediaPreloader.create({ahead: 2, behind: 1})};
}
const tick = () => new Promise(r => setTimeout(r, 60));
const items = Array.from({length: 6}, (_, id) => ({original_url: `/${id}.jpg`}));
test('waits for current, then downloads forward neighbours one at a time', async () => {
  const {nodes, cache} = setup();
  try {
    cache.getImage(items[2]); cache.update(items, 2); await tick();
    assert.deepEqual(nodes.map(n => n.src), ['/2.jpg']);
    nodes[0].done(); await tick();
    assert.deepEqual(nodes.map(n => n.src), ['/2.jpg', '/3.jpg']);
    nodes[1].done(); await tick();
    assert.equal(nodes[2].src, '/4.jpg');
    nodes[2].done(); await tick();
    assert.equal(nodes[3].src, '/1.jpg');
  } finally { cache.clear(); }
});
test('jump cancels unfinished background request and prioritizes selected photo', async () => {
  const {nodes, cache} = setup();
  try {
    cache.getImage(items[0]); cache.update(items, 0); nodes[0].done(); await tick();
    assert.equal(nodes[1].src, '/1.jpg');
    const selected = cache.getImage(items[4]); cache.update(items, 4); await tick();
    assert.equal(nodes[1].src, ''); assert.equal(selected.src, '/4.jpg');
    assert.equal(nodes.length, 3);
    selected.done(); await tick(); assert.equal(nodes[3].src, '/5.jpg');
  } finally { cache.clear(); }
});
test('errors advance queue; revisiting a failed photo starts a fresh request', async () => {
  const {nodes, cache} = setup();
  try {
    cache.getImage(items[0]); cache.update(items, 0);
    nodes[0].dispatchEvent(new Event('error')); await tick();
    assert.equal(nodes[1].src, '/1.jpg');
    assert.notEqual(cache.getImage(items[0]), nodes[0]);
  } finally { cache.clear(); }
});
test('video metadata preparation is sequential and current video is not fetched twice', async () => {
  const {nodes, cache} = setup();
  try {
    const list = items.map((item, i) => ({...item, is_video: i < 2}));
    cache.update(list, 0); await tick();
    assert.equal(nodes.length, 1); assert.equal(nodes[0].src, '/1.jpg');
    assert.equal(nodes[0].preload, 'metadata');
    nodes[0].done(); await tick(); assert.equal(nodes[1].src, '/2.jpg');
  } finally { cache.clear(); }
});
test('repeated updates do not start concurrent downloads and close stops queue', async () => {
  const {nodes, cache} = setup();
  cache.getImage(items[0]); cache.update(items, 0); nodes[0].done(); await tick();
  cache.update(items, 0); await tick(); assert.equal(nodes.length, 2);
  cache.clear(); nodes[1].done(); await tick(); assert.equal(nodes.length, 2);
});
