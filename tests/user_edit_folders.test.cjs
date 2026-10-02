const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const path = require('node:path');
const { chromium } = require('playwright');

test('edit user opens and saves folder permissions without losing profile edits', async () => {
  const source = readFileSync(path.join(__dirname, '../static/app.js'), 'utf8');
  const panel = source.slice(source.indexOf('async function renderUsersPanel(){'), source.indexOf('async function renderTwofaPanel(){'));
  const browser = await chromium.launch();
  try {
    for (const width of [1280, 390]) {
      const page = await browser.newPage({ viewport: { width, height: 850 } });
      const errors = [];
      page.on('pageerror', e => errors.push(e.message));
      await page.setContent('<div id="usersPanelInner"></div>');
      await page.addStyleTag({ path: path.join(__dirname, '../static/styles.css') });
      await page.addStyleTag({ path: path.join(__dirname, '../static/redesign.css') });
      await page.evaluate(() => {
        window.tr = key => key;
        window.escapeHtml = value => String(value).replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('"', '&quot;');
        window.renderMailSettingsPanel = window.initForgotPasswordToggle = () => {};
        window.showStatus = () => {};
        window.saved = [];
        window.failSave = false;
        window.fetch = async (url, options) => {
          if (options) {
            const body = JSON.parse(options.body);
            if (window.failSave) return { ok: false, json: async () => ({ ok: false, error: 'test failure' }) };
            window.saved.push({ url, body });
            return { ok: true, json: async () => ({ ok: true, ...body }) };
          }
          return { ok: true, text: async () => JSON.stringify({ ok: true, items: [
            { id: 7, username: 'Test', role: 'user', allowed_folders: [{ folder_path: 'Family', permission: 'view' }] }
          ], available_folders: ['Family', 'Holiday'] }) };
        };
      });
      await page.addScriptTag({ content: panel });
      await page.evaluate(() => renderUsersPanel());
      await page.locator('[data-edit="7"]').click();
      await page.locator('#eu_username').fill('Unsaved name');
      await page.locator('#eu_acl').click();
      assert.equal(await page.locator('input[name="perm:Family"][value="view"]').isChecked(), true);
      await page.locator('.ua-row[data-folder="Holiday"] label[data-level="upload"]').click();
      await page.locator('#ua_cancel').click();
      await page.locator('#eu_acl').click();
      assert.equal(await page.locator('input[name="perm:Holiday"][value="upload"]').isChecked(), false);
      await page.locator('.ua-row[data-folder="Holiday"] label[data-level="upload"]').click();
      await page.evaluate(() => { window.failSave = true; });
      await page.locator('#ua_save').click();
      assert.equal(await page.locator('#ua_modal').isVisible(), true);
      await page.evaluate(() => { window.failSave = false; });
      await page.locator('#ua_save').click();
      await page.waitForFunction(() => document.getElementById('ua_modal').classList.contains('hidden'));
      assert.equal(await page.locator('#eu_username').inputValue(), 'Unsaved name');
      const saved = await page.evaluate(() => window.saved);
      assert.equal(saved[0].url, '/api/admin/users/7/folders');
      assert.deepEqual(saved[0].body.allowed_folders, [
        { folder_path: 'Family', permission: 'view' }, { folder_path: 'Holiday', permission: 'upload' }
      ]);
      await page.locator('#eu_acl').click();
      assert.equal(await page.locator('input[name="perm:Holiday"][value="upload"]').isChecked(), true);
      assert.deepEqual(errors, []);
      await page.close();
    }
  } finally { await browser.close(); }
});
