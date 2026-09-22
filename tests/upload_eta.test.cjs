const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('static/app.js', 'utf8');
function fixture() {
  let now = 0, active = true;
  const timers = new Map();
  const state = { totalBytes: 1000000, transferSamples: [], transferLastSampleBytes: 0 };
  const ctx = vm.createContext({ uploadUiState: state, performance: { now: () => now },
    isUploadRunning: () => active, isUploadPostprocessPhase: () => false, uploadStopRequested: false,
    renderUploadMonitor() {}, window: { setInterval(fn) { timers.set(1, fn); return 1; }, clearInterval(id) { timers.delete(id); } } });
  vm.runInContext(source.slice(source.indexOf('function formatUploadEta('), source.indexOf('function setUploadStopButtonState(')), ctx);
  return { ctx, state, timers, sample(t, bytes) { now = t * 1000; ctx.updateUploadTransferEstimate(bytes); }, stop() { active = false; } };
}
test('constant speed predicts remaining transfer time after warmup', () => {
  const f = fixture();
  f.sample(0, 0);
  assert.match(f.ctx.uploadEtaLabel(0), /beregner/);
  for (let t = 1; t <= 20; t++) f.sample(t, t * 10000);
  assert.equal(f.state.transferRateBps, 10000);
  assert.match(f.ctx.uploadEtaLabel(200000), /00:01:20/);
});
test('old speed is forgotten within the rolling window in both directions', () => {
  const f = fixture();
  for (let t = 0; t <= 20; t++) f.sample(t, t * 10000);
  for (let t = 21; t <= 35; t++) f.sample(t, 200000 + (t - 20) * 1000);
  assert.equal(f.state.transferRateBps, 1000);
  for (let t = 36; t <= 50; t++) f.sample(t, 215000 + (t - 35) * 20000);
  assert.equal(f.state.transferRateBps, 20000);
});
test('pauses lower throughput, report stalled progress and recover', () => {
  const f = fixture();
  for (let t = 0; t <= 10; t++) f.sample(t, t * 10000);
  f.sample(15, 100000);
  assert.ok(f.state.transferRateBps < 10000);
  f.sample(20, 100000);
  assert.match(f.ctx.uploadEtaLabel(100000), /afventer fremgang/);
  f.sample(21, 110000);
  assert.match(f.ctx.uploadEtaLabel(110000), /ca\./);
  assert.equal(f.ctx.uploadEtaLabel(1000000), '');
});
test('rollback restarts warmup and repeated renders do not change estimate', () => {
  const f = fixture();
  for (let t = 0; t <= 10; t++) f.sample(t, t * 10000);
  const label = f.ctx.uploadEtaLabel(100000);
  for (let i = 0; i < 100; i++) assert.equal(f.ctx.uploadEtaLabel(100000), label);
  f.sample(11, 50000);
  assert.match(f.ctx.uploadEtaLabel(50000), /beregner/);
});
test('heartbeat is unique and stops when uploading stops', () => {
  const f = fixture();
  f.ctx.syncUploadEstimateTimer(); f.ctx.syncUploadEstimateTimer();
  assert.equal(f.timers.size, 1);
  f.stop(); f.ctx.syncUploadEstimateTimer();
  assert.equal(f.timers.size, 0);
});

test('monitor renders the complete ETA together on its own line', () => {
  const ctx = vm.createContext({ els: { uploadMonitorSummary: {} },
    uploadUiState: { failedFiles: 0, processedFiles: 8, totalFiles: 79, totalBytes: 3900 },
    isPostprocess: false, postprocessLabel: '', processedVisualBytes: 824, overallPct: 21,
    etaTxt: 'Tid tilbage: ca. 00:07:01', fmtBytes: n => String(n) });
  const start = source.indexOf('  if (els.uploadMonitorSummary) {', source.indexOf('function renderUploadMonitor()'));
  vm.runInContext(source.slice(start, source.indexOf('  if (els.uploadMonitorCurrent)', start)), ctx);
  const lines = ctx.els.uploadMonitorSummary.textContent.split('\n');
  assert.equal(lines.length, 2);
  assert.equal(lines[1], 'Tid\u00a0tilbage:\u00a0ca.\u00a000:07:01');
  assert.match(fs.readFileSync('static/styles.css', 'utf8'), /\.upload-monitor-summary\s*\{\s*white-space: pre-line;/);
});
