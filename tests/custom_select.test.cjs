const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const { chromium } = require('playwright');

test('dynamic user dialogs use custom selects and respect theme changes', async () => {
  const browser = await chromium.launch({ headless: true });
  try {
    for (const width of [1280, 390]) {
      const page = await browser.newPage({ viewport: { width, height: 700 } });
      const errors = [];
      page.on('pageerror', error => errors.push(error.message));
      await page.setContent('<html data-theme="dark"><head><link id="fjordDesignStylesheet"></head><body><main id="settings"></main></body></html>');
      await page.addStyleTag({ path: path.join(__dirname, '../static/styles.css') });
      await page.addStyleTag({ path: path.join(__dirname, '../static/redesign.css') });
      await page.addScriptTag({ path: path.join(__dirname, '../static/fl-select.js') });
      const insert = () => page.evaluate(() => {
        document.getElementById('settings').innerHTML = '<div style="padding:16px"><label for="eu_role">Rolle</label><select id="eu_role" class="select"><option value="user">Bruger</option><option value="manager">Manager</option><option value="admin">Admin</option></select><select id="eu_search_language" class="select"><option value="da">Dansk</option><option value="en">English</option></select></div>';
        document.getElementById('eu_role').value = 'manager';
        window.changes = 0;
        document.getElementById('eu_role').addEventListener('change', () => window.changes++);
      });
      await insert();
      await page.waitForSelector('#eu_role[data-fl-select="1"]', { state: 'attached' });
      assert.equal(await page.locator('.fl-select').count(), 2);
      assert.equal(await page.locator('.fl-select-label').first().textContent(), 'Manager');
      await page.locator('.fl-select-btn').first().click();
      await page.locator('.fl-select-item[data-value="admin"]').click();
      assert.equal(await page.locator('#eu_role').inputValue(), 'admin');
      assert.equal(await page.evaluate(() => window.changes), 1);
      await page.locator('.fl-select-btn').first().focus();
      await page.keyboard.press('ArrowDown');
      await page.keyboard.press('Home');
      await page.keyboard.press('ArrowDown');
      await page.keyboard.press('Enter');
      assert.equal(await page.locator('#eu_role').inputValue(), 'manager');
      assert.equal(await page.evaluate(() => window.changes), 2);
      await page.locator('.fl-select-btn').first().click();
      await page.keyboard.press('Escape');
      assert.equal(await page.locator('.fl-select-btn').first().getAttribute('aria-expanded'), 'false');
      await page.evaluate(() => { document.getElementById('eu_role').value = 'user'; });
      await page.waitForFunction(() => document.querySelector('.fl-select-label').textContent === 'Bruger');
      await page.evaluate(() => { document.getElementById('eu_role').disabled = true; });
      await page.waitForFunction(() => document.querySelector('.fl-select-btn').disabled);
      await insert();
      await page.waitForSelector('#eu_role[data-fl-select="1"]', { state: 'attached' });
      assert.equal(await page.locator('.fl-select').count(), 2);
      await page.evaluate(() => {
        document.getElementById('fjordDesignStylesheet').media = 'not all';
        window.dispatchEvent(new Event('fjordlens:ui-design'));
      });
      assert.equal(await page.locator('.fl-select').count(), 0);
      await insert();
      await page.evaluate(() => new Promise(requestAnimationFrame));
      assert.equal(await page.locator('.fl-select').count(), 0);
      await page.evaluate(() => {
        document.getElementById('fjordDesignStylesheet').media = '';
        window.dispatchEvent(new Event('fjordlens:ui-design'));
      });
      assert.equal(await page.locator('.fl-select').count(), 2);
      assert.deepEqual(errors, []);
      await page.close();
    }
  } finally {
    await browser.close();
  }
});
