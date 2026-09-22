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
test('sustained speed changes converge without keeping the session average', () => {
  const f = fixture();
  f.state.totalBytes = 100000000;
  for (let t = 0; t <= 20; t++) f.sample(t, t * 10000);
  for (let t = 21; t <= 80; t++) f.sample(t, 200000 + (t - 20) * 1000);
  assert.ok(Math.abs(f.state.transferRateBps - 1000) < 50);
  for (let t = 81; t <= 170; t++) f.sample(t, 260000 + (t - 80) * 20000);
  assert.ok(Math.abs(f.state.transferRateBps - 20000) < 500);
});

test('bursty chunk progress stays stable while retaining realistic throughput', () => {
  const f = fixture();
  const chunk = 2 * 1024 * 1024;
  f.state.totalBytes = 6 * 1024 ** 3;
  const rates = [];
  for (let t = 0; t <= 180; t++) {
    f.sample(t, Math.floor(t / 8) * chunk);
    if (t >= 90) rates.push(f.state.transferRateBps);
  }
  const actualRate = chunk / 8;
  assert.ok((Math.max(...rates) - Math.min(...rates)) / actualRate < 0.12);
  assert.ok(rates.every(rate => Math.abs(rate - actualRate) / actualRate < 0.12));
});

test('subsecond progress callbacks do not change smoothing and warmup lasts ten seconds', () => {
  const sparse = fixture(), frequent = fixture();
  for (let tick = 0; tick <= 600; tick++) {
    const t = tick / 10;
    const bytes = Math.floor(t / 4) * 10000;
    frequent.sample(t, bytes);
    if (tick % 10 === 0) sparse.sample(t, bytes);
    if (tick === 90) assert.match(frequent.ctx.uploadEtaLabel(bytes), /beregner/);
  }
  assert.equal(sparse.state.transferRateBps, frequent.state.transferRateBps);
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
