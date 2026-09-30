const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

test('bulk retry mounts beside the actual log clear button and sends POST', async () => {
  const root = path.join(__dirname, '..');
  const html = fs.readFileSync(path.join(root, 'templates/index.html'), 'utf8');
  assert.match(html, /id="mainLogsClear"/);
  const source = fs.readFileSync(path.join(root, 'static/app.js'), 'utf8');
  const script = source.slice(source.indexOf('// Bulk retries use'));
  const mounted = [];
  const calls = [];
  const element = () => ({listeners:{},setAttribute(){},addEventListener(name, fn){this.listeners[name]=fn;}});
  const context = {
    els:{logsClear:null,mainLogsClear:{after(...nodes){mounted.push(...nodes);}}},
    document:{createElement:element},state:{logItems:[]},
    fetch:async (url,options) => {calls.push([url,options.method]);return {ok:true,json:async()=>({ok:true,running:false,total:0})};},
    renderLogList(){},refreshResolvedLogs:async()=>{},clearTimeout(){},setTimeout(){},
  };
  vm.runInNewContext(script,context);
  await new Promise(setImmediate);
  assert.equal(mounted[0].id,'logsRetryAll');
  assert.equal(mounted[0].textContent,'Prøv alle igen');
  await mounted[0].listeners.click();
  assert.deepEqual(calls,[['/api/logs/retry-all','GET'],['/api/logs/retry-all','POST']]);
});
