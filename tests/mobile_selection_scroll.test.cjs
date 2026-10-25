const {test} = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const source = fs.readFileSync(require('node:path').join(__dirname, '../static/app.js'), 'utf8');

function setup(edit = true, allowDoubleTap = true) {
  const handlers = new Map(), timers = new Map(); let timerId = 0, selected = 0, opened = 0, doubles = 0;
  const element = {style: {}, addEventListener(name, handler) {
    if (!handlers.has(name)) handlers.set(name, []);
    handlers.get(name).push(handler);
  }};
  const context = vm.createContext({state: {mapperEditMode: edit}, navigator: {maxTouchPoints: 1},
    window: {scrollX: 0, scrollY: 0, matchMedia: () => ({matches: true}),
      setTimeout(fn) {timers.set(++timerId, fn); return timerId;}, clearTimeout(id) {timers.delete(id);}}});
  vm.runInContext(source.slice(source.indexOf('const MOBILE_SELECT_DOUBLE_TAP_MS'), source.indexOf('// --- Desktop right-click context menu')), context);
  context.bindMobileDoubleTapSelection(element, {allowDoubleTap, onSingleTap() {opened++;}, onDoubleTap() {doubles++;}});
  element.addEventListener('click', () => {if (context.state.mapperEditMode) selected++;});
  function fire(name, extra = {}) {
    const event = {detail: 1, preventDefault() {}, stopImmediatePropagation() {this.stopped = true;}, ...extra};
    for (const handler of handlers.get(name) || []) {handler(event); if (event.stopped) break;}
    return event;
  }
  function touch(name, x, y) {fire(name, {touches: name === 'touchend' ? [] : [{clientX: x, clientY: y}], changedTouches: [{clientX: x, clientY: y}]});}
  return {context, fire, touch, timers, counts: () => ({selected, opened, doubles})};
}

test('scrolling never selects, even if the browser emits a click afterwards', () => {
  const s = setup();
  s.touch('touchstart', 20, 100); s.touch('touchmove', 20, 70); s.touch('touchend', 20, 40); s.fire('click');
  assert.equal(s.counts().selected, 0);
  // The next deliberate tap still selects normally.
  s.touch('touchstart', 20, 40); s.touch('touchend', 22, 42); s.fire('click');
  assert.equal(s.counts().selected, 1);
});

test('movement remains a scroll even after the finger returns to its starting point', () => {
  const s = setup();
  s.touch('touchstart', 20, 100); s.touch('touchmove', 20, 70); s.touch('touchend', 20, 100); s.fire('click');
  assert.equal(s.counts().selected, 0);
});

test('native scroll displacement and cancelled touches suppress selection', () => {
  const s = setup();
  s.touch('touchstart', 20, 100); s.context.window.scrollY = 50; s.touch('touchend', 20, 100); s.fire('click');
  s.touch('touchstart', 20, 100); s.fire('touchcancel'); s.fire('click');
  assert.equal(s.counts().selected, 0);
});

test('scrolling cancels a pending single tap and never starts double-tap selection', () => {
  const s = setup(false);
  s.touch('touchstart', 20, 100); s.touch('touchend', 20, 100); s.fire('click');
  assert.equal(s.timers.size, 1);
  s.touch('touchstart', 20, 100); s.touch('touchmove', 20, 60); s.fire('click');
  assert.equal(s.timers.size, 0);
  assert.deepEqual(s.counts(), {selected: 0, opened: 0, doubles: 0});
});

test('stationary double taps still enter selection and mouse/keyboard clicks still work', () => {
  const s = setup(false);
  for (let i = 0; i < 2; i++) {s.touch('touchstart', 20, 100); s.touch('touchend', 20, 100); s.fire('click');}
  assert.equal(s.counts().doubles, 1);
  s.context.state.mapperEditMode = true;
  s.fire('touchcancel'); s.fire('click', {detail: 0});
  s.fire('pointerdown', {pointerType: 'mouse'}); s.fire('click');
  assert.equal(s.counts().selected, 2);
});

test('range dragging starts only with the mouse, never a scrolling touch or pen', () => {
  let starts = 0;
  const ctx = vm.createContext({_isMapperSelectablePhotoCard: () => true, _startMapperDragSelection() {starts++;}});
  vm.runInContext(source.slice(source.indexOf('function _handleMapperDragPointerStart('), source.indexOf('function _finishMapperDragSelectSession(')), ctx);
  ctx._handleMapperDragPointerStart({pointerType: 'touch', button: 0}, {});
  ctx._handleMapperDragPointerStart({pointerType: 'pen', button: 0}, {});
  assert.equal(starts, 0);
  ctx._handleMapperDragPointerStart({pointerType: 'mouse', button: 0, buttons: 1}, {});
  assert.equal(starts, 1);
});

test('a media tap opens synchronously without waiting for a double-tap timer', () => {
  const s = setup(false, false);
  s.touch('touchstart', 20, 100); s.touch('touchend', 20, 100); s.fire('click');
  assert.equal(s.counts().opened, 1);
  assert.equal(s.timers.size, 0);
  assert.equal(s.counts().doubles, 0);
});

test('immediate media opening still ignores scrolls and supports selection mode', () => {
  const s = setup(false, false);
  s.touch('touchstart', 20, 100); s.touch('touchmove', 20, 60); s.touch('touchend', 20, 60); s.fire('click');
  assert.equal(s.counts().opened, 0);
  s.context.state.mapperEditMode = true;
  s.touch('touchstart', 20, 60); s.touch('touchend', 20, 60); s.fire('click');
  assert.equal(s.counts().opened, 0);
  assert.equal(s.counts().selected, 1);
});
