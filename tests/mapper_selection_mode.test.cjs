const {test} = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const source = fs.readFileSync(require('node:path').join(__dirname, '../static/app.js'), 'utf8');

test('selection mode updates existing cards and overlays without remounting the gallery', () => {
  function card(dataset, folder = false) {
    const classes = new Set(folder ? ['folder-card'] : []);
    let badge = null;
    return {dataset, classes, classList: {contains: c => classes.has(c), toggle(c, on) {if (on) classes.add(c); else classes.delete(c);}},
      querySelector(selector) {
        if (selector === '.folder-select-badge') return badge;
        if (selector === '.card-thumb') return {appendChild(value) {badge = value; value.remove = () => {badge = null;};}};
      }};
  }
  const photo = card({photoId: '7'}), folder = card({folder: 'trip'}, true), overlay = {style: {}};
  const items = [{id: 7}], cards = [photo, folder]; let stopped = 0;
  const state = {view: 'mapper', items, mapperSelectedPhotoIds: new Set([7]), mapperSelectedFolders: new Set(['trip'])};
  const ctx = vm.createContext({state, els: {grid: {querySelectorAll: () => cards}}, mapperCardItemJson: new Map(),
    document: {createElement: () => ({}), querySelectorAll: () => [overlay]},
    _stopMapperDragSelectSession() {stopped++;}, renderMapperContext() {},
    renderGrid() {throw Error('selection must not redraw cards');}});
  vm.runInContext(source.slice(source.indexOf('function setMapperEditMode('), source.indexOf('const MAPPER_DRAG_SELECT_MIN_DISTANCE_PX')), ctx);
  ctx.setMapperEditMode(true);
  assert.equal(photo.classes.has('selected'), true);
  assert.equal(folder.querySelector('.folder-select-badge').textContent, '✓');
  assert.equal(overlay.style.display, 'none');
  ctx.setMapperEditMode(false);
  assert.equal(photo.classes.has('selected'), false);
  assert.equal(folder.classes.has('selected'), false);
  assert.equal(folder.querySelector('.folder-select-badge'), null);
  assert.equal(overlay.style.display, '');
  assert.equal(state.mapperSelectedPhotoIds.size, 0);
  assert.equal(stopped, 1);
  assert.equal(ctx.mapperCardItemJson.get(photo), JSON.stringify([0, '', items[0]]));
});
