const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { join } = require('node:path');
const vm = require('node:vm');
const source = readFileSync(join(__dirname, '../static/app.js'), 'utf8');
const code = source.slice(source.indexOf('function photoThumbnailUrl('), source.indexOf('function cardHTML('));

test('private photo thumbnails carry explicit folder context only when browsing folders', () => {
  const context = vm.createContext({ state: { view: 'mapper', mapperPath: 'Private / Family' } });
  vm.runInContext(code, context);
  const photo = { private: true, thumb_url: '/api/thumbs/photo.jpg?v=42' };
  assert.equal(context.photoThumbnailUrl(photo), '/api/thumbs/photo.jpg?v=42&folder=Private%20%2F%20Family');
  assert.equal(photo.thumb_url, '/api/thumbs/photo.jpg?v=42'); // Covers still use the default blurred URL.
  assert.equal(context.photoThumbnailUrl({ ...photo, private: false }), photo.thumb_url);
  assert.equal(context.photoThumbnailUrl({ ...photo, thumb_url: '/api/share/token/thumb/1' }), '/api/share/token/thumb/1');
  context.state.mapperPath = '';
  assert.equal(context.photoThumbnailUrl(photo), photo.thumb_url);
  context.state.mapperPath = 'Private';
  context.state.view = 'timeline';
  assert.equal(context.photoThumbnailUrl(photo), photo.thumb_url);
});
