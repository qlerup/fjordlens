// Run with: node --test tests/test_login_appearance.js
// Execute the real bootstrap scripts, rather than only checking for key names.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const root = path.resolve(__dirname, '..');
const template = fs.readFileSync(path.join(root, 'templates/base.html'), 'utf8');
const scripts = [...template.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(match => match[1]);
const designScript = fs.readFileSync(path.join(root, 'static/theme-design.js'), 'utf8');

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
  };
}

function browser(options = {}) {
  const values = { ...options.storage };
  const cookies = { ...options.cookies };
  const cookieWrites = [];
  const document = element();
  const window = element();
  const html = element(options.attributes);
  const stylesheet = { disabled: false, media: 'not all' };
  const metas = [
    element({ media: '(prefers-color-scheme: light)' }),
    element({ media: '(prefers-color-scheme: dark)' }),
    element({ id: 'theme-color-override' }),
  ];
  const mediaQuery = element();
  mediaQuery.matches = options.dark !== false;
  if (options.legacyMedia) {
    mediaQuery.addListener = callback => { mediaQuery.onChange = callback; };
    delete mediaQuery.addEventListener;
  }
  const nodes = {};
  const observers = [];
  const storage = {
    getItem(key) {
      if (options.blockStorage || options.blockKey === key) throw Error('storage blocked');
      return values[key] ?? null;
    },
    setItem(key, value) {
      if (options.blockStorage) throw Error('storage blocked');
      values[key] = value;
    },
  };
  Object.assign(document, {
    documentElement: html,
    visibilityState: 'visible',
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
      cookieWrites.push(value);
      const pair = value.split(';')[0];
      const split = pair.indexOf('=');
      cookies[pair.slice(0, split)] = pair.slice(split + 1);
    },
  });
  Object.assign(window, {
    location: { protocol: options.protocol || 'https:', reload() {} },
    setTimeout() {},
    matchMedia() {
      if (options.noMedia) throw Error('matchMedia unavailable');
      return mediaQuery;
    },
  });
  const context = vm.createContext({
    document, window, localStorage: storage,
    MutationObserver: class {
      constructor(callback) { this.callback = callback; observers.push(this); }
      observe(target, config) { this.target = target; this.config = config; }
    },
    fetch: async () => ({ ok: true, json: async () => ({ ok: true }) }),
  });
  return {
    values, cookies, cookieWrites, document, window, html, stylesheet, metas,
    mediaQuery, nodes, observers,
    login() {
      // Match parser order: bootstrap runs before the stylesheet link exists.
      vm.runInContext(scripts[0], context);
      nodes.fjordDesignStylesheet = stylesheet;
      for (const script of scripts.slice(1)) vm.runInContext(script, context);
    },
    app(profile) {
      nodes.bootstrapData = { dataset: { profile: JSON.stringify(profile) } };
      nodes.fjordDesignStylesheet = stylesheet;
      nodes.uiDesignSelect = element();
      vm.runInContext(designScript, context);
    },
  };
}

for (const design of ['classic', 'fjord']) {
  for (const theme of ['system', 'light', 'dark']) {
    test(`login restores ${design}/${theme} before pageshow`, () => {
      const b = browser({ storage: { fl_ui_design: design, fl_theme_mode: theme } });
      b.login();
      assert.equal(b.html.getAttribute('data-ui-design'), design);
      assert.equal(b.html.getAttribute('data-theme'), theme === 'system' ? null : theme);
      assert.equal(b.stylesheet.media, design === 'fjord' ? 'all' : 'not all');
      assert.equal(b.stylesheet.disabled, false);
      const color = design === 'fjord'
        ? (theme === 'light' ? '#edf3f4' : '#08141a')
        : (theme === 'light' ? '#f5f6f8' : '#0f1115');
      assert.equal(b.metas[2].getAttribute('content'), color);
      if (theme !== 'system') b.metas.forEach(meta => assert.equal(meta.getAttribute('content'), color));
    });
  }
}

for (const event of ['pageshow', 'focus', 'storage', 'visibilitychange']) {
  test(`login refreshes both directions on ${event}`, async () => {
    const b = browser({ storage: { fl_ui_design: 'classic', fl_theme_mode: 'dark' } });
    b.login();
    b.values.fl_ui_design = 'fjord';
    b.values.fl_theme_mode = 'light';
    const target = event === 'visibilitychange' ? b.document : b.window;
    await target.fire(event, { key: 'fl_ui_design', persisted: true });
    assert.equal(b.html.getAttribute('data-ui-design'), 'fjord');
    assert.equal(b.html.getAttribute('data-theme'), 'light');
    assert.equal(b.stylesheet.media, 'all');
    assert.equal(b.metas[2].getAttribute('content'), '#edf3f4');
    b.values.fl_ui_design = 'classic';
    b.values.fl_theme_mode = 'system';
    await target.fire(event, { key: 'fl_theme_mode', persisted: true });
    assert.equal(b.html.getAttribute('data-theme'), null);
    assert.equal(b.stylesheet.media, 'not all');
    assert.equal(b.metas[2].getAttribute('content'), '#0f1115');
  });
}

test('system theme tracks OS changes, but explicit mode remains fixed', async () => {
  const b = browser({ storage: { fl_ui_design: 'fjord', fl_theme_mode: 'system' } });
  b.login();
  b.mediaQuery.matches = false;
  await b.mediaQuery.fire('change');
  assert.equal(b.metas[2].getAttribute('content'), '#edf3f4');
  b.values.fl_theme_mode = 'dark';
  await b.mediaQuery.fire('change');
  assert.equal(b.html.getAttribute('data-theme'), 'dark');
  b.metas.forEach(meta => assert.equal(meta.getAttribute('content'), '#08141a'));
});

test('legacy matchMedia listeners work', () => {
  const b = browser({ legacyMedia: true });
  b.login();
  b.mediaQuery.matches = false;
  b.mediaQuery.onChange();
  assert.equal(b.metas[2].getAttribute('content'), '#f5f6f8');
});

test('cookies restore appearance when localStorage is unavailable', () => {
  const b = browser({ blockStorage: true, cookies: { fl_ui_design: 'fjord', fl_theme_mode: 'light' } });
  b.login();
  assert.equal(b.stylesheet.media, 'all');
  assert.equal(b.html.getAttribute('data-theme'), 'light');
});

test('legacy localStorage preferences win over stale cookies', () => {
  const b = browser({
    storage: { fl_ui_design: 'classic', fl_theme_mode: 'system' },
    cookies: { fl_ui_design: 'fjord', fl_theme_mode: 'light' },
  });
  b.login();
  assert.equal(b.stylesheet.media, 'not all');
  assert.equal(b.html.getAttribute('data-theme'), null);
});

test('one unreadable storage key does not prevent restoring the other', () => {
  const b = browser({ blockKey: 'fl_theme_mode', storage: { fl_ui_design: 'fjord' } });
  b.login();
  assert.equal(b.stylesheet.media, 'all');
});

test('missing or invalid preferences and malformed cookies safely use defaults', () => {
  const b = browser({
    storage: { fl_ui_design: 'invalid', fl_theme_mode: 'invalid' },
    cookies: { fl_ui_design: '%E0%A4%A', fl_theme_mode: 'invalid' },
  });
  b.login();
  assert.equal(b.html.getAttribute('data-ui-design'), 'classic');
  assert.equal(b.html.getAttribute('data-theme'), null);
  assert.equal(b.stylesheet.media, 'not all');
});

test('login remains usable when all persistence and matchMedia are unavailable', () => {
  const b = browser({ blockStorage: true, blockCookies: true, noMedia: true });
  assert.doesNotThrow(() => b.login());
  assert.equal(b.stylesheet.media, 'not all');
});

test('clearing preferences in another tab resets a previously active theme', async () => {
  const b = browser({ storage: { fl_ui_design: 'fjord', fl_theme_mode: 'light' } });
  b.login();
  delete b.values.fl_ui_design;
  delete b.values.fl_theme_mode;
  await b.window.fire('storage', { key: null });
  assert.equal(b.stylesheet.media, 'not all');
  assert.equal(b.html.getAttribute('data-theme'), null);
});

test('authenticated profile is still authoritative and mirrors appearance cookies', () => {
  const b = browser({
    storage: { fl_ui_design: 'classic' }, attributes: { 'data-theme': 'light' },
  });
  b.app({ ui_design: 'fjord', ui_design_intro_seen: true });
  assert.equal(b.values.fl_ui_design, 'fjord');
  assert.equal(b.cookies.fl_ui_design, 'fjord');
  assert.equal(b.cookies.fl_theme_mode, 'light');
  assert.ok(b.cookieWrites.every(value => value.endsWith('; SameSite=Lax; Secure')));
  assert.ok(b.cookieWrites.every(value => value.includes('; Path=/; Max-Age=31536000;')));
});

test('appearance cookies can still be written when localStorage is blocked', () => {
  const b = browser({ blockStorage: true });
  assert.doesNotThrow(() => b.app({ ui_design: 'fjord', ui_design_intro_seen: true }));
  assert.equal(b.cookies.fl_ui_design, 'fjord');
  assert.equal(b.cookies.fl_theme_mode, 'system');
});

test('theme cookie follows data-theme mutations, including return to system', () => {
  const b = browser();
  b.app({ ui_design: 'fjord', ui_design_intro_seen: true });
  const observer = b.observers[0];
  assert.equal(observer.target, b.html);
  assert.deepEqual(Array.from(observer.config.attributeFilter), ['data-theme']);
  b.html.setAttribute('data-theme', 'dark');
  observer.callback();
  assert.equal(b.cookies.fl_theme_mode, 'dark');
  b.html.removeAttribute('data-theme');
  observer.callback();
  assert.equal(b.cookies.fl_theme_mode, 'system');
});

test('switching back to classic updates the persisted login design', async () => {
  const b = browser();
  b.app({ ui_design: 'fjord', ui_design_intro_seen: true });
  b.nodes.uiDesignSelect.value = 'classic';
  await b.nodes.uiDesignSelect.fire('change');
  assert.equal(b.values.fl_ui_design, 'classic');
  assert.equal(b.cookies.fl_ui_design, 'classic');
  assert.equal(b.stylesheet.disabled, true);
});

test('plain HTTP development installs do not receive Secure-only cookies', () => {
  const b = browser({ protocol: 'http:' });
  b.app({ ui_design: 'classic', ui_design_intro_seen: true });
  assert.ok(b.cookieWrites.every(value => !value.includes('; Secure')));
});

test('blocked cookies do not break the existing app controls', () => {
  const b = browser({ blockCookies: true });
  assert.doesNotThrow(() => b.app({ ui_design: 'fjord', ui_design_intro_seen: true }));
  assert.equal(b.values.fl_ui_design, 'fjord');
  assert.equal(b.stylesheet.disabled, false);
});
