const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const {JSDOM} = require('jsdom');

test('selection hides only marked faces, stays in review mode and can process the remainder', async () => {
  const dom = new JSDOM('<header></header><main></main>', {runScripts:'outside-only'});
  const w = dom.window;
  w.state = {currentUser:{role:'admin'},view:'personer',personView:{mode:'photos',personId:7},
    items:[{id:1,faces:[{id:11}]},{id:2,faces:[{id:22}]}], people:[]};
  w.showStatus = () => {};
  w.loadPeople = async () => {};
  w.personHasName = () => true;
  let failed = true;
  const calls = [];
  w.fetch = async (url, options) => {
    calls.push(JSON.parse(options.body));
    return {ok:!failed, json:async () => failed ? {ok:false,error:'Try again'} : {ok:true,name:'Hidden'}};
  };
  w.eval(fs.readFileSync('static/person_faces.js','utf8'));
  w.renderGrid = () => {
    const head = w.document.querySelector('header'), grid = w.document.querySelector('main');
    head.replaceChildren(); grid.replaceChildren();
    w.state.items.forEach(item => {
      const card = w.document.createElement('article'); card.className = 'photo-card'; card.dataset.photoId = item.id; grid.append(card);
    });
    w.setupPersonFaceSelection(head, grid);
  };
  const button = label => [...w.document.querySelectorAll('button')].find(button => button.textContent === label);
  const settle = () => new Promise(resolve => setImmediate(resolve));
  w.renderGrid(); button('Vælg').click();
  w.document.querySelector('[data-photo-id="1"]').click();
  button('Skjul valgte').click(); await settle();
  assert.equal(w.state.items.length,2);
  assert.equal(button('Skjul valgte').disabled,false);
  assert.deepEqual(calls[0].face_ids,[11]);
  failed = false;
  button('Skjul valgte').click(); await settle();
  assert.equal(w.state.items.length,1);
  assert.equal(w.state.items[0].id,2);
  assert.ok(button('Færdig'));
  assert.equal(button('Skjul valgte').disabled,true);
  button('Vælg alle').click(); button('Skjul valgte').click(); await settle();
  assert.equal(w.state.items.length,0);
  assert.match(w.document.querySelector('main').textContent,/ikke flere/);
  dom.window.close();
});
