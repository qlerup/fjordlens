const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('static/app.js', 'utf8');
const snippet = source.slice(source.indexOf('function conversionProgressSummary('), source.indexOf('async function startExistingConversion('));

test('progress counts failures as handled and excludes skipped files', () => {
  const ctx = vm.createContext({});
  vm.runInContext(snippet, ctx);
  const result = ctx.conversionProgressSummary({running: true, progress: {total: 10, processed: 3, errors: 2, skipped: 90, current: 'photo.heic'}});
  assert.equal(result.percent, 50);
  assert.match(result.text, /5\/10/);
  assert.match(result.text, /90 allerede/);
  assert.match(result.text, /photo.heic/);
  assert.equal(ctx.conversionProgressSummary({running: true, progress: {phase: 'checking'}}).percent, null);
  const scan = ctx.conversionProgressSummary({running: true, progress: {phase: 'checking', check_stage: 'files', checked: 30, check_total: 60, pending: 8, skipped: 22}});
  assert.equal(scan.percent, 50);
  assert.match(scan.text, /30\/60/);
  assert.match(scan.text, /8 mangler/);
  assert.match(scan.text, /22 allerede/);
  const history = ctx.conversionProgressSummary({running: true, progress: {phase: 'checking', check_stage: 'metadata', checked: 20, check_total: 100}});
  assert.equal(history.percent, 20);
  assert.match(history.text, /konverteringshistorik/);
  const disk = ctx.conversionProgressSummary({running: true, progress: {phase: 'checking', check_stage: 'disk', scanned: 200, found: 30, added: 7}});
  assert.equal(disk.percent, null);
  assert.match(disk.text, /200 filer/);
  assert.match(disk.text, /30 originalfiler/);
  assert.match(disk.text, /7 ikke registreret/);
  assert.equal(ctx.conversionProgressSummary({result: {total: 0, skipped: 90}}).percent, 100);
  assert.equal(ctx.conversionProgressSummary({result: {total: 10, processed: 3, stopped: true}}).percent, 30);
  assert.match(ctx.conversionProgressSummary({result: {ok: false, error: 'database unavailable'}}).text, /database unavailable/);
});

test('three conversion types poll independently and retain their own results', async () => {
  const nodes = new Map(), timers = [];
  const node = id => {
    if (!nodes.has(id)) nodes.set(id, {classList: {toggle() {}}, removeAttribute() {}});
    return nodes.get(id);
  };
  const responses = {heic: {running: true, progress: {total: 10, processed: 2}}, raw: {result: {total: 0, skipped: 7}}, mov: {running: true, progress: {total: 4, processed: 3}}};
  const ctx = vm.createContext({
    document: {getElementById: node}, clearTimeout() {}, setTimeout: fn => timers.push(fn),
    conversionTypeConfig: type => ({statusUrl: type, buttonText: type}),
    fetch: async type => ({ok: true, json: async () => ({ok: true, ...responses[type]})}),
    loadPhotos: async () => {}, state: {view: 'settings'},
  });
  vm.runInContext(snippet, ctx);
  for (const type of ['heic', 'raw', 'mov']) ctx.watchExistingConversion(type);
  await new Promise(setImmediate);
  assert.equal(node('heicBulkProgressBar').value, 20);
  assert.equal(node('rawBulkProgressBar').value, 100);
  assert.equal(node('movBulkProgressBar').value, 75);
  assert.equal(node('rawBulkConvertBtn').disabled, false);
  assert.equal(timers.length, 2);
  responses.heic = {result: {total: 10, processed: 9, errors: 1}};
  await timers[0]();
  assert.equal(node('heicBulkProgressBar').value, 100);
  assert.equal(node('heicBulkConvertBtn').disabled, false);
  assert.equal(node('movBulkConvertBtn').disabled, true);
});
