const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { join } = require('node:path');
const vm = require('node:vm');
const source = readFileSync(join(__dirname, '../static/app.js'), 'utf8');

function fixture(active = false, queue = [], pump = false) {
  let listener;
  const draft = { pending: ['old-upload.jpg'] };
  const context = vm.createContext({
    isUploadRunning: () => active,
    uploadQueue: queue,
    uploadQueuePumpRunning: pump,
    _readUploadResumeDraft: () => draft,
    window: { addEventListener: (name, callback) => {
      assert.equal(name, 'beforeunload'); listener = callback;
    } },
  });
  vm.runInContext(source.slice(source.indexOf('function shouldWarnOnPageLeaveDuringUpload()'),
    source.indexOf('async function maybeRefreshPhotosDuringPostprocess(')), context);
  const event = { prevented: false, preventDefault() { this.prevented = true; } };
  listener(event);
  assert.deepEqual(draft.pending, ['old-upload.jpg'], 'resume information is preserved');
  return event;
}

test('saved resume draft alone does not block reload', () => {
  const event = fixture();
  assert.equal(event.prevented, false);
  assert.equal(event.returnValue, undefined);
});
test('active file transfer blocks reload', () => {
  const event = fixture(true);
  assert.equal(event.prevented, true);
  assert.equal(event.returnValue, '');
});
test('queued browser files block reload before transfer starts', () => {
  assert.equal(fixture(false, [{ files: ['new.jpg'] }]).prevented, true);
});
test('server postprocessing alone does not block reload', () => {
  assert.equal(fixture(false, [], true).prevented, false);
});
