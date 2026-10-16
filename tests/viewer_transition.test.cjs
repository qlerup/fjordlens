// Run with: node --test tests/viewer_transition.test.cjs
const assert = require('node:assert/strict');
const { test } = require('node:test');
const { readFileSync } = require('node:fs');
const { join } = require('node:path');
const vm = require('node:vm');
const source = readFileSync(join(__dirname, '../static/app.js'), 'utf8');
function extract(name) {
  const start = source.indexOf('function ' + name + '(');
  const end = source.indexOf('\nfunction ', start + 1);
  return source.slice(start, end);
}
function fixture() {
  const timers = [], frames = [];
  const media = { style: {} };
  const context = vm.createContext({
    Math, window: { innerWidth: 1000, setTimeout: callback => timers.push(callback) },
    requestAnimationFrame: callback => frames.push(callback),
    els: { viewer: { classList: { contains: () => false } }, viewerImg: media },
    viewerZoom: { isActive: () => false }, viewerVideoSourceGeneration: 1,
    viewerInfoPositionLocked: false, viewerTransitionRunning: true, viewerPendingStep: 0,
    getActiveViewerMediaElement: () => media,
    beginViewerInfoSlideOut: () => true, beginViewerInfoButtonSlideOut: () => true,
    prepareViewerInfoSlideIn: () => true, prepareViewerInfoButtonSlideIn: () => true,
    runViewerInfoSlideIn() {}, runViewerInfoButtonSlideIn() {},
    finishViewerInfoSlideAnimation() {}, finishViewerInfoButtonSlideAnimation() {},
    scheduleViewerInfoPosition() {}, nextViewer() {},
  });
  vm.runInContext(extract('cleanupViewerMediaAnimation') + '\n' + extract('animateViewerSlideTransition'), context);
  return { context, timers, frames, media };
}
test('a delayed incoming animation frame keeps anchors locked until the slide finishes', () => {
  const { context, timers, frames, media } = fixture();
  context.animateViewerSlideTransition(1, () => {});
  assert.equal(context.viewerInfoPositionLocked, true);
  timers.shift()();
  assert.equal(frames.length, 1);
  assert.equal(timers.length, 0, 'cleanup must not race a delayed animation frame');
  assert.equal(media.style.opacity, '0');
  frames.shift()();
  assert.equal(context.viewerTransitionRunning, true);
  assert.equal(timers.length, 1);
  timers.shift()();
  assert.equal(context.viewerInfoPositionLocked, false);
  assert.equal(context.viewerTransitionRunning, false);
  assert.equal(media.style.opacity, '');
});
test('a superseded incoming frame does not animate or clean up the new media', () => {
  const { context, timers, frames, media } = fixture();
  context.animateViewerSlideTransition(1, () => {});
  timers.shift()();
  context.viewerVideoSourceGeneration++;
  frames.shift()();
  assert.equal(timers.length, 0);
  assert.equal(media.style.opacity, '0');
});
test('cancelling media animation releases overlay positioning even while zoomed', () => {
  const { context } = fixture();
  context.viewerInfoPositionLocked = true;
  context.viewerZoom.isActive = () => true;
  context.cleanupViewerMediaAnimation();
  assert.equal(context.viewerInfoPositionLocked, false);
});
