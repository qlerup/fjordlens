const {test} = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');

function setup(fetch) {
  const context = {fetch, AbortController, setTimeout, clearTimeout, console};
  context.window = context;
  vm.runInNewContext(fs.readFileSync('static/video_diagnostics.js', 'utf8'), context);
  return context.FjordLensVideoDiagnostics.report;
}
const video = () => ({error: {code: 3, message: 'decode failed'},
  currentSrc: 'https://fjordlens.test/api/viewable/a.mp4', networkState: 3, readyState: 0});

test('snapshots failed media before navigation and probes with HEAD only', async () => {
  const calls = [];
  let finish;
  const report = setup(async (url, options) => {
    calls.push({url, options});
    if (options.method === 'HEAD') return new Promise(resolve => { finish = resolve; });
    return {ok: true};
  });
  const media = video();
  const task = report(media, {id: 12, is_video: true}, '/api/media/playback-error/12');
  media.error = null;
  media.currentSrc = '/different.mp4';
  finish({status: 200, redirected: false, headers: new Headers({'Content-Type': 'video/mp4', 'Accept-Ranges': 'bytes'})});
  await task;
  assert.equal(calls[0].url, 'https://fjordlens.test/api/viewable/a.mp4');
  assert.equal(calls[0].options.method, 'HEAD');
  const body = JSON.parse(calls[1].options.body);
  assert.equal(body.code, 3);
  assert.equal(body.http_status, 200);
  assert.equal(body.content_type, 'video/mp4');
  assert.equal(body.accept_ranges, 'bytes');
  assert.equal(body.message, 'decode failed');
  assert.equal(body.url, undefined);
});

test('network failure still reports the original media error', async () => {
  let body;
  const report = setup(async (url, options) => {
    if (options.method === 'HEAD') throw new TypeError('offline');
    body = JSON.parse(options.body);
  });
  await report(video(), {id: 12, is_video: true}, '/report');
  assert.equal(body.code, 3);
  assert.equal(body.probe_error, 'TypeError');
});

test('clearing the player or displaying a photo does not report an error', async () => {
  const report = setup(() => { throw new Error('unexpected request'); });
  await report({...video(), error: null}, {id: 12, is_video: true}, '/report');
  await report(video(), {id: 12, is_video: false}, '/report');
});
