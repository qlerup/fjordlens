// Run with: node --test tests/test_login_appearance.js
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');
const root = path.resolve(__dirname, '..');
const template = fs.readFileSync(path.join(root, 'templates/base.html'), 'utf8');
const scripts = [...template.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(match => match[1]);
const designScript = fs.readFileSync(path.join(root, 'static/theme-design.js'), 'utf8');
const syncScript = fs.readFileSync(path.join(root, 'static/ui-design-sync.js'), 'utf8');

function element(initial = {}) {
  const attributes = { ...initial };
  const listeners = {};
  return {
    dataset: {},
    getAttribute: key => attributes[key] ?? null,
    setAttribute: (key, value) => { attributes[key] = String(value); },
    removeAttribute: key => { delete attributes[key]; },
    addEventListener: (name, callback) => { (listeners[name] ||= []).push(callback); },
    fire: (name, event = {}) => Promise.all((listeners[name] || []).map(callback => callback(event))),
    dispatchEvent(event) { (listeners[event.type] || []).forEach(callback => callback(event)); },
  };
}

function browser(options = {}) {
  const values = { ...options.storage };
  const cookies = { ...options.cookies };
  const document = element();
  const window = element();
  const html = element({ 'data-ui-design': options.design || 'classic', ...options.attributes });
  const stylesheet = { disabled: false, media: 'not all' };
  const metas = [element({ media: '(prefers-color-scheme: light)' }), element({ media: '(prefers-color-scheme: dark)' }), element()];
  const mediaQuery = element();
  mediaQuery.matches = options.dark !== false;
  if (options.legacyMedia) {
    mediaQuery.addListener = callback => { mediaQuery.onChange = callback; };
    delete mediaQuery.addEventListener;
  }
  const nodes = {};
  const observers = [];
  const intervals = [];
  const requests = [];
  const server = { design: options.design || 'classic', failure: false, saveFailure: false, pending: null };
  const storage = {
    getItem(key) {
      if (options.blockStorage) throw Error('storage blocked');
      return values[key] ?? null;
    },
    setItem(key, value) {
      if (options.blockStorage) throw Error('storage blocked');
      values[key] = value;
    },
  };
  Object.assign(document, {
    documentElement: html, visibilityState: 'visible',
    getElementById: id => nodes[id] || null,
    querySelectorAll: selector => selector === 'meta[name="theme-color"]' ? metas : [],
  });
  Object.defineProperty(document, 'cookie', {
    get() {
      if (options.blockCookies) throw Error('cookies blocked');
      return Object.entries(cookies).map(([key, value]) => `${key}=${value}`).join('; ');
    },
    set(value) {
      if (options.blockCookies) throw Error('cookies blocked');
      const pair = value.split(';')[0];
      const split = pair.indexOf('=');
      cookies[pair.slice(0, split)] = pair.slice(split + 1);
    },
  });
  Object.assign(window, {
    location: { protocol: 'https:', reload() { throw Error('must not reload active pages'); } },
    setTimeout() { return 1; }, clearTimeout() {},
    setInterval(fn, ms) { intervals.push({ fn, ms }); },
    matchMedia() {
      if (options.noMedia) throw Error('matchMedia unavailable');
      return mediaQuery;
    },
  });
  const context = vm.createContext({
    document, window, localStorage: storage, AbortController,
    CustomEvent: class { constructor(type, init) { this.type = type; this.detail = init.detail; } },
    MutationObserver: class {
      constructor(callback) { this.callback = callback; observers.push(this); }
      observe(target, config) { this.target = target; this.config = config; }
    },
    fetch: async (url, init = {}) => {
      requests.push({ url, init });
      if (init.method === 'POST') {
        if (server.saveFailure) return { ok: false, json: async () => ({ ok: false }) };
        server.design = JSON.parse(init.body).ui_design;
      } else {
        if (server.failure) throw Error('offline');
        if (server.pending) return server.pending;
      }
      const design = server.design;
      return { ok: true, json: async () => ({ ok: true, ui_design: design }) };
    },
  });
  return {
    values, cookies, document, window, html, stylesheet, metas, mediaQuery, nodes, observers, intervals, requests, server,
    login() {
      vm.runInContext(scripts[0], context);
      nodes.fjordDesignStylesheet = stylesheet;
      scripts.slice(1).forEach(script => vm.runInContext(script, context));
    },
    async sync() {
      nodes.fjordDesignStylesheet = stylesheet;
      vm.runInContext(syncScript, context);
      await window.FjordLensDesign.refresh();
    },
    app() {
      nodes.bootstrapData = { dataset: { profile: JSON.stringify({ ui_design: 'classic', ui_design_intro_seen: true }) } };
      nodes.fjordDesignStylesheet = stylesheet;
      nodes.uiDesignSelect = element();
      nodes.uiDesignStatus = element();
      vm.runInContext(designScript, context);
    },
  };
}

for (const design of ['classic', 'fjord']) {
  for (const theme of ['system', 'light', 'dark']) {
    test(`server design ${design}/${theme} wins over stale storage before pageshow`, () => {
      const b = browser({ design, storage: { fl_ui_design: design === 'fjord' ? 'classic' : 'fjord', fl_theme_mode: theme } });
      b.login();
      assert.equal(b.html.getAttribute('data-ui-design'), design);
      assert.equal(b.html.getAttribute('data-theme'), theme === 'system' ? null : theme);
      assert.equal(b.stylesheet.media, design === 'fjord' ? 'all' : 'not all');
      assert.equal(b.stylesheet.disabled, false);
      const color = design === 'fjord' ? (theme === 'light' ? '#edf3f4' : '#08141a') : (theme === 'light' ? '#f5f6f8' : '#0f1115');
      assert.equal(b.metas[2].getAttribute('content'), color);
    });
  }
}

for (const event of ['pageshow', 'focus', 'storage', 'visibilitychange', 'online']) {
  test(`open login follows server in both directions on ${event}`, async () => {
    const b = browser();
    b.login();
    await b.sync();
    const target = event === 'visibilitychange' ? b.document : b.window;
    for (const design of ['fjord', 'classic']) {
      b.server.design = design;
      await target.fire(event, { key: 'fl_ui_design', persisted: true });
      assert.equal(b.html.getAttribute('data-ui-design'), design);
      assert.equal(b.stylesheet.media, design === 'fjord' ? 'all' : 'not all');
    }
    assert.ok(b.requests.every(r => r.init.cache === 'no-store'));
  });
}

test('active pages poll changes from another device within five seconds', async () => {
  const b = browser(); b.login(); await b.sync();
  assert.equal(b.intervals[0].ms, 5000);
  b.server.design = 'fjord'; await b.intervals[0].fn();
  assert.equal(b.stylesheet.media, 'all');
  b.document.visibilityState = 'hidden';
  const count = b.requests.length;
  await b.intervals[0].fn();
  assert.equal(b.requests.length, count);
});

test('failed synchronization keeps the last confirmed design', async () => {
  const b = browser({ design: 'fjord' }); b.login(); await b.sync();
  b.server.failure = true;
  b.values.fl_ui_design = 'classic';
  await b.window.fire('focus');
  assert.equal(b.stylesheet.media, 'all');
});

test('cleared local storage cannot reset the administrator design', async () => {
  const b = browser({ design: 'fjord' }); b.login(); await b.sync();
  delete b.values.fl_ui_design;
  await b.window.fire('storage', { key: null });
  assert.equal(b.stylesheet.media, 'all');
});

test('system theme follows OS changes with the global design', async () => {
  const b = browser({ design: 'fjord', storage: { fl_theme_mode: 'system' } }); b.login();
  b.mediaQuery.matches = false; await b.mediaQuery.fire('change');
  assert.equal(b.metas[2].getAttribute('content'), '#edf3f4');
  b.values.fl_theme_mode = 'dark'; await b.mediaQuery.fire('change');
  b.metas.forEach(meta => assert.equal(meta.getAttribute('content'), '#08141a'));
});

test('blocked local storage still uses server design and theme cookie', () => {
  const b = browser({ design: 'fjord', blockStorage: true, cookies: { fl_ui_design: 'classic', fl_theme_mode: 'light' } });
  b.login(); assert.equal(b.stylesheet.media, 'all'); assert.equal(b.html.getAttribute('data-theme'), 'light');
});

test('legacy matchMedia listeners work', () => {
  const b = browser({ design: 'fjord', legacyMedia: true }); b.login();
  b.mediaQuery.matches = false; b.mediaQuery.onChange();
  assert.equal(b.metas[2].getAttribute('content'), '#edf3f4');
});

test('blocked browser persistence never breaks startup', async () => {
  const b = browser({ design: 'fjord', blockStorage: true, blockCookies: true, noMedia: true });
  b.login(); await b.sync(); b.app(); assert.equal(b.stylesheet.media, 'all');
});

test('authenticated pages use global design over stale user profile', async () => {
  const b = browser({ design: 'fjord' }); await b.sync(); b.app();
  assert.equal(b.nodes.uiDesignSelect.value, 'fjord'); assert.equal(b.stylesheet.media, 'all');
  b.server.design = 'classic'; await b.window.FjordLensDesign.refresh();
  assert.equal(b.nodes.uiDesignSelect.value, 'classic'); assert.equal(b.stylesheet.media, 'not all');
});

test('admin save applies the confirmed global design without reloading', async () => {
  const b = browser(); await b.sync(); b.app();
  b.nodes.uiDesignSelect.value = 'fjord'; await b.nodes.uiDesignSelect.fire('change');
  assert.equal(b.server.design, 'fjord'); assert.equal(b.stylesheet.media, 'all');
  assert.ok(b.requests.some(r => r.url === '/api/settings/ui-design' && r.init.method === 'POST'));
});

test('rejected admin save restores selection and retains confirmed design', async () => {
  const b = browser({ design: 'fjord' }); await b.sync(); b.app();
  b.server.saveFailure = true;
  b.nodes.uiDesignSelect.value = 'classic'; await b.nodes.uiDesignSelect.fire('change');
  assert.equal(b.stylesheet.media, 'all'); assert.equal(b.nodes.uiDesignSelect.value, 'fjord');
  assert.equal(b.nodes.uiDesignSelect.disabled, false); assert.equal(b.nodes.uiDesignStatus.className, 'status err');
});

test('a slow poll cannot overwrite a newer successful administrator save', async () => {
  const b = browser(); await b.sync(); b.app();
  let release;
  b.server.pending = new Promise(resolve => { release = resolve; });
  const poll = b.window.FjordLensDesign.refresh();
  b.nodes.uiDesignSelect.value = 'fjord'; await b.nodes.uiDesignSelect.fire('change');
  release({ ok: true, json: async () => ({ ok: true, ui_design: 'classic' }) });
  await poll;
  assert.equal(b.stylesheet.media, 'all'); assert.equal(b.html.getAttribute('data-ui-design'), 'fjord');
});
