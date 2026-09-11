(function () {
  'use strict';

  const INTRO_KEY = 'fjordlens.uiDesignIntro.v1';
  const DESIGN_KEY = 'fl_ui_design';
  const bootstrap = document.getElementById('bootstrapData');
  let profile = {};
  try { profile = JSON.parse((bootstrap && bootstrap.dataset.profile) || '{}') || {}; } catch {}
  let current = document.documentElement.getAttribute('data-ui-design') === 'fjord' ? 'fjord' : 'classic';
  let saving = false;

  const stylesheet = document.getElementById('fjordDesignStylesheet');
  const settingsSelect = document.getElementById('uiDesignSelect');
  const introModal = document.getElementById('uiDesignIntroModal');
  const introSelect = document.getElementById('uiDesignIntroSelect');
  const introApply = document.getElementById('uiDesignIntroApply');
  const introLater = document.getElementById('uiDesignIntroLater');
  const status = document.getElementById('uiDesignStatus');

  const LENS_SVG =
    '<svg class="fl-lens-icon" viewBox="0 0 20 20" aria-hidden="true"><circle cx="9" cy="9" r="5.6" fill="none" stroke="currentColor" stroke-width="1.6"/><path d="m13.5 13.5 3.3 3.3" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/><path d="M6.3 8.3a3.2 3.2 0 0 1 2.1-2.1" fill="none" stroke="currentColor" stroke-width="1.1" stroke-linecap="round" opacity="0.65"/></svg>';

  function prepareNavigation() {
    document.querySelectorAll('.nav-item[data-view]').forEach((button) => {
      if (button.querySelector('.nav-label')) return;
      const text = String(button.textContent || '').trim();
      const match = text.match(/^(\S+)\s+(.*)$/);
      if (!match) return;
      button.textContent = '';
      const icon = document.createElement('span');
      icon.className = 'nav-icon';
      icon.textContent = match[1];
      const label = document.createElement('span');
      label.className = 'nav-label';
      label.textContent = match[2];
      button.append(icon, label);
    });
  }

  function prepareSearchIcons() {
    ['searchToggleBtn', 'mapperSearchToggleBtn'].forEach((id) => {
      const btn = document.getElementById(id);
      if (btn && !btn.querySelector('.fl-lens-icon')) btn.innerHTML = LENS_SVG;
    });
  }

  function rememberCookie(key, value) {
    // Appearance-only compatibility hints. The server owns the global design.
    try {
      const secure = window.location.protocol === 'https:' ? '; Secure' : '';
      document.cookie = key + '=' + encodeURIComponent(value) + '; Path=/; Max-Age=31536000; SameSite=Lax' + secure;
    } catch (_) {}
  }

  function rememberTheme() {
    const mode = document.documentElement.getAttribute('data-theme');
    rememberCookie('fl_theme_mode', mode === 'light' || mode === 'dark' ? mode : 'system');
  }

  function applyLocally(value) {
    current = value === 'fjord' ? 'fjord' : 'classic';
    try { localStorage.setItem(DESIGN_KEY, current); } catch {}
    rememberCookie(DESIGN_KEY, current);
    if (stylesheet) {
      stylesheet.disabled = false;
      stylesheet.media = current === 'fjord' ? 'all' : 'not all';
    }
    document.documentElement.dataset.uiDesign = current;
    if (settingsSelect) settingsSelect.value = current;
    if (introSelect) introSelect.value = current;
    if (current === 'fjord') {
      prepareNavigation();
      prepareSearchIcons();
    } else {
      document.querySelectorAll('.nav-item[data-view]').forEach(button => {
        const icon = button.querySelector('.nav-icon');
        const label = button.querySelector('.nav-label');
        if (icon && label) button.textContent = icon.textContent + ' ' + label.textContent;
      });
      ['searchToggleBtn', 'mapperSearchToggleBtn'].forEach(id => {
        const button = document.getElementById(id);
        if (button && button.querySelector('.fl-lens-icon')) button.textContent = '🔍';
      });
    }
  }

  async function save(value) {
    if (saving) return false;
    saving = true;
    const requested = value === 'fjord' ? 'fjord' : 'classic';
    [settingsSelect, introSelect, introApply, introLater].forEach(el => { if (el) el.disabled = true; });
    if (status) {
      status.textContent = 'Gemmer design…';
      status.className = 'status';
    }
    try {
      const response = await fetch('/api/settings/ui-design', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ui_design: requested }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok || !data.ok) throw new Error(data.error || 'save_failed');
      if (window.FjordLensDesign) window.FjordLensDesign.apply(data.ui_design);
      applyLocally(data.ui_design);
      if (status) {
        status.textContent = 'Designet er gemt for alle brugere.';
        status.className = 'status ok';
      }
      return true;
    } catch (error) {
      applyLocally(current);
      if (status) {
        status.textContent = 'Designet kunne ikke gemmes.';
        status.className = 'status err';
      }
      return false;
    } finally {
      saving = false;
      [settingsSelect, introSelect, introApply, introLater].forEach(el => { if (el) el.disabled = false; });
    }
  }

  function closeIntro() {
    if (introModal) introModal.classList.remove('active');
    try { localStorage.setItem(INTRO_KEY, 'seen'); } catch {}
    // Source of truth is server-side and global: once anyone dismisses this,
    // nobody should see it again on any account or device.
    try { fetch('/api/ui-design-intro-seen', { method: 'POST' }); } catch {}
  }

  applyLocally(current);
  window.addEventListener('fjordlens:ui-design', event => applyLocally(event.detail));
  rememberTheme();
  // app.js owns the light/dark/system control. Mirror its applied preference,
  // including a switch back to system, without changing the user's selection.
  const themeObserver = new MutationObserver(rememberTheme);
  themeObserver.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
  if (settingsSelect) settingsSelect.addEventListener('change', () => save(settingsSelect.value));
  if (introApply) introApply.addEventListener('click', async () => {
    if (await save((introSelect && introSelect.value) || 'fjord')) closeIntro();
  });
  if (introLater) introLater.addEventListener('click', async () => {
    if (await save('classic')) closeIntro();
  });

  let introSeen = !!profile.ui_design_intro_seen;
  if (!introSeen) {
    try { introSeen = localStorage.getItem(INTRO_KEY) === 'seen'; } catch {}
  }
  if (!introSeen && introModal) {
    if (introSelect) introSelect.value = current === 'fjord' ? 'fjord' : 'classic';
    window.setTimeout(() => introModal.classList.add('active'), 350);
  }
})();
