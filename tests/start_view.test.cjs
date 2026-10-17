const {test} = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const source = fs.readFileSync(require('node:path').join(__dirname, '../static/app.js'), 'utf8');
function setup(success) {
  let handler, payload, navigated = null, error = null;
  const select = {value: 'mapper', disabled: false, addEventListener(name, fn) {handler = fn;}};
  const ctx = vm.createContext({document: {getElementById: () => select},
    APP_PROFILE: {start_view:'timeline'}, state: {view:'timeline',currentUser:{id:7}},
    fetch: async (url, options) => {payload={url,...JSON.parse(options.body)}; return {ok:success,json:async()=>({ok:success,error:'Save failed'})};},
    setView: async view => {navigated=view;}, showStatus: message => {error=message;}});
  vm.runInContext(source.slice(source.indexOf("document.getElementById('galleryViewSelect')?.addEventListener"), source.indexOf('async function setView(')),ctx);
  return {ctx,select,run:()=>handler({target:select}),result:()=>({payload,navigated,error})};
}
test('view choice saves on the user before navigating to the existing menu',async()=>{
  const s=setup(true); await s.run();
  assert.deepEqual(s.result().payload,{url:'/api/me/start-view',start_view:'mapper'});
  assert.equal(s.result().navigated,'mapper');
  assert.equal(s.ctx.APP_PROFILE.start_view,'mapper');
  assert.equal(s.ctx.state.currentUser.start_view,'mapper');
  assert.equal(s.select.disabled,false);
});
test('failed saving restores the selector and leaves the previous preference and menu intact',async()=>{
  const s=setup(false); await s.run();
  assert.equal(s.select.value,'timeline');
  assert.equal(s.result().navigated,null);
  assert.equal(s.ctx.APP_PROFILE.start_view,'timeline');
  assert.equal(s.select.disabled,false);
  assert.equal(s.result().error,'Save failed');
});
