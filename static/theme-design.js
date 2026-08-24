(function () {
  'use strict';

  const INTRO_KEY = 'fjordlens.uiDesignIntro.v1';
  const bootstrap = document.getElementById('bootstrapData');
  let profile = {};
  try { profile = JSON.parse((bootstrap && bootstrap.dataset.profile) || '{}') || {}; } catch {}
  let current = profile.ui_design === 'fjord' ? 'fjord' : 'classic';

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

  function applyLocally(value) {
    current = value === 'fjord' ? 'fjord' : 'classic';
    if (stylesheet) stylesheet.disabled = current !== 'fjord';
    document.documentElement.dataset.uiDesign = current;
    if (settingsSelect) settingsSelect.value = current;
    if (introSelect) introSelect.value = current;
    if (current === 'fjord') {
      prepareNavigation();
      prepareSearchIcons();
    }
  }

  async function save(value) {
    const changed = (value === 'fjord' ? 'fjord' : 'classic') !== current;
    applyLocally(value);
    if (status) {
      status.textContent = 'Gemmer design…';
      status.className = 'status';
    }
    try {
      const response = await fetch('/api/me/ui-design', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ui_design: current }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok || !data.ok) throw new Error(data.error || 'save_failed');
      if (status) {
        status.textContent = 'Designet er gemt.';
        status.className = 'status ok';
      }
      // Genindlæs så hele siden (dropdowns, navigation, viewer m.m.) starter
      // rent op i det valgte design, i stedet for at forsøge at leve-skifte DOM'en.
      if (changed) window.setTimeout(() => window.location.reload(), 400);
      return true;
    } catch (error) {
      if (status) {
        status.textContent = 'Designet kunne ikke gemmes.';
        status.className = 'status err';
      }
      return false;
    }
  }

  function closeIntro() {
    if (introModal) introModal.classList.remove('active');
    try { localStorage.setItem(INTRO_KEY, 'seen'); } catch {}
  }

  applyLocally(current);
  if (settingsSelect) settingsSelect.addEventListener('change', () => save(settingsSelect.value));
  if (introApply) introApply.addEventListener('click', async () => {
    await save((introSelect && introSelect.value) || 'fjord');
    closeIntro();
  });
  if (introLater) introLater.addEventListener('click', async () => {
    await save('classic');
    closeIntro();
  });

  let introSeen = false;
  try { introSeen = localStorage.getItem(INTRO_KEY) === 'seen'; } catch {}
  if (!introSeen && introModal) {
    if (introSelect) introSelect.value = current === 'fjord' ? 'fjord' : 'classic';
    window.setTimeout(() => introModal.classList.add('active'), 350);
  }
})();
