const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

test('clearing a failed file refreshes both views, including while a list request is in flight', async () => {
  const listeners = {}, nodes = {}, calls = [];
  const element = () => ({children:[], style:{}, append(...x){this.children.push(...x)}, replaceChildren(){this.children=[]}});
  const root = {querySelector: key => nodes[key] ||= element()};
  let cleared = false, logsReloaded = 0, resolvePending;
  const ctx = {
    document:{getElementById:()=>root, createElement:element,
      addEventListener:(name,fn)=>listeners[name]=fn,
      dispatchEvent:event=>listeners[event.type]?.()},
    Event:class {constructor(type){this.type=type}}, clearTimeout(){}, setTimeout(){}, queueMicrotask,
    refreshResolvedLogs:async()=>logsReloaded++,
    fetch:async(url,options)=>{
      calls.push([url,options?.method || 'GET']);
      if (options?.method==='POST') {cleared=true;return {ok:true,json:async()=>({ok:true})};}
      return {ok:true,json:async()=>({items:cleared?[]:[{id:4,rel_path:'missing.jpg',stage:'metadata',error:'missing'}]})};
    }
  };
  vm.runInNewContext(fs.readFileSync('static/processing_failures.js','utf8'),ctx);
  listeners.DOMContentLoaded();
  await nodes['[data-refresh]'].onclick();
  assert.equal(nodes['[data-list]'].children.length,1,nodes['[data-status]'].textContent);
  const clear = nodes['[data-list]'].children[0].children[3];
  assert.equal(clear.textContent,'Ryd');
  await clear.onclick();
  await new Promise(setImmediate);
  assert.equal(nodes['[data-list]'].children.length,0);
  assert.equal(logsReloaded,1);
  assert.ok(calls.some(([url,method])=>url==='/api/processing-failures/4/clear' && method==='POST'));
  ctx.fetch=async()=>new Promise(resolve=>{resolvePending=resolve});
  const loading=nodes['[data-refresh]'].onclick();
  listeners['fjordlens:errors-cleared']();
  let reloads=0;
  ctx.fetch=async()=>{reloads++;return {ok:true,json:async()=>({items:[]})}};
  resolvePending({ok:true,json:async()=>({items:[{id:4,stage:'metadata'}]})});
  await loading;
  await new Promise(setImmediate);
  assert.equal(reloads,1);
  assert.equal(nodes['[data-list]'].children.length,0);
});
