(() => {
  'use strict';

  const API = '/api/cast-airplay';
  const ACTION_ID = 'mapperHeaderCastAirplayAction';
  let lastSession = null;
  let statusCache = null;
  let castSdkPromise = null;
  let castSession = null;
  let observer = null;

  const esc = (value) => String(value == null ? '' : value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const isEnglish = () => String(document.documentElement.lang || 'da').toLowerCase().startsWith('en');
  const tr = (da, en) => isEnglish() ? en : da;

  function appState() {
    try { return state; } catch (_) { return null; }
  }

  function notify(text, type = 'ok') {
    try {
      if (typeof showStatus === 'function') { showStatus(text, type); return; }
    } catch (_) {}
    console[type === 'err' ? 'error' : 'log'](text);
  }

  function isPhone() {
    try {
      return window.matchMedia('(max-width: 760px)').matches && (navigator.maxTouchPoints > 0 || 'ontouchstart' in window);
    } catch (_) {
      return false;
    }
  }

  function platform() {
    const ua = String(navigator.userAgent || '');
    if (/iPhone|iPod/i.test(ua)) return 'ios';
    if (/Android/i.test(ua)) return 'android';
    return 'mobile';
  }

  async function api(path, options = {}) {
    const response = await fetch(`${API}${path}`, {
      credentials: 'same-origin',
      ...options,
      headers: {
        ...(options.body ? {'Content-Type':'application/json'} : {}),
        ...(options.headers || {}),
      },
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
    return data;
  }

  async function loadStatus(force = false) {
    if (statusCache && !force) return statusCache;
    statusCache = await api('/status');
    return statusCache;
  }

  function selection() {
    const s = appState();
    if (!s) return {photo_ids:[], folder_paths:[]};
    const photoIds = Array.from(s.mapperSelectedPhotoIds || [])
      .map(v => Number(v || 0)).filter(v => Number.isFinite(v) && v > 0);
    const folders = Array.from(s.mapperSelectedFolders || [])
      .map(v => String(v || '').trim()).filter(Boolean);
    return {photo_ids: photoIds, folder_paths: folders};
  }

  function selectionTitle(sel) {
    if (sel.folder_paths.length === 1 && !sel.photo_ids.length) {
      const folder = String(sel.folder_paths[0] || '').split('/').filter(Boolean).pop();
      return folder ? `FjordLens · ${folder}` : 'FjordLens';
    }
    const total = sel.photo_ids.length + sel.folder_paths.length;
    return total > 1 ? `FjordLens · ${total} ${tr('valg', 'selections')}` : 'FjordLens';
  }

  function ensureAction() {
    const menu = document.getElementById('mapperHeaderMenu');
    if (!menu) return null;
    let btn = document.getElementById(ACTION_ID);
    if (!btn) {
      btn = document.createElement('button');
      btn.id = ACTION_ID;
      btn.type = 'button';
      btn.className = 'mapper-header-menu-item';
      btn.textContent = 'AirPlay / Cast';
      const share = document.getElementById('mapperHeaderShareAction');
      if (share && share.parentNode === menu) share.insertAdjacentElement('afterend', btn);
      else menu.appendChild(btn);
      btn.addEventListener('click', onActionClick);
    }
    return btn;
  }

  function refreshAction() {
    const btn = ensureAction();
    if (!btn) return;
    const s = appState();
    const sel = selection();
    const count = sel.photo_ids.length + sel.folder_paths.length;
    const visible = !!(isPhone() && s && s.view === 'mapper' && s.mapperEditMode);
    btn.classList.toggle('hidden', !visible);
    btn.disabled = !visible || count === 0;
    btn.textContent = count > 0 ? `AirPlay / Cast (${count})` : 'AirPlay / Cast';
    btn.title = count > 0
      ? tr('Send de valgte billeder, videoer eller mapper til en skærm', 'Send selected photos, videos or folders to a display')
      : tr('Vælg billeder, videoer eller en mappe først', 'Select photos, videos or a folder first');
  }

  function closeMapperMenu() {
    try {
      const menu = document.getElementById('mapperHeaderMenu');
      if (menu) menu.classList.remove('open');
      if (typeof closeMapperHeaderMenu === 'function') closeMapperHeaderMenu();
    } catch (_) {}
  }

  function ensureModal() {
    let modal = document.getElementById('castAirplayModal');
    if (modal) return modal;
    modal = document.createElement('div');
    modal.id = 'castAirplayModal';
    modal.className = 'cast-airplay-modal hidden';
    modal.innerHTML = `
      <div class="cast-airplay-backdrop" data-cast-close></div>
      <div class="cast-airplay-card" role="dialog" aria-modal="true" aria-labelledby="castAirplayTitle">
        <div class="cast-airplay-head">
          <div>
            <h3 id="castAirplayTitle">AirPlay / Cast</h3>
            <div id="castAirplaySub" class="mini-label"></div>
          </div>
          <button type="button" class="btn" data-cast-close>×</button>
        </div>
        <div id="castAirplayError" class="cast-airplay-error hidden"></div>
        <div id="castAirplayBody"></div>
      </div>`;
    document.body.appendChild(modal);
    modal.addEventListener('click', event => {
      if (event.target.closest('[data-cast-close]')) closeModal();
      const castBtn = event.target.closest('[data-cast-start]');
      if (castBtn) startGoogleCast();
      const airplayBtn = event.target.closest('[data-airplay-start]');
      if (airplayBtn) openAirplayPlayer();
      const setupBtn = event.target.closest('[data-cast-setup]');
      if (setupBtn) renderSetup();
      const saveSetup = event.target.closest('[data-cast-setup-save]');
      if (saveSetup) saveCastSetup();
      const prev = event.target.closest('[data-cast-prev]');
      if (prev) sendCastCommand('PREV');
      const next = event.target.closest('[data-cast-next]');
      if (next) sendCastCommand('NEXT');
      const reload = event.target.closest('[data-cast-reload]');
      if (reload) sendCastLoad();
    });
    return modal;
  }

  function openModal() {
    const modal = ensureModal();
    modal.classList.remove('hidden');
    return modal;
  }

  function closeModal() {
    document.getElementById('castAirplayModal')?.classList.add('hidden');
  }

  function setError(message) {
    const el = document.getElementById('castAirplayError');
    if (!el) return;
    const text = String(message || '').trim();
    el.textContent = text;
    el.classList.toggle('hidden', !text);
  }

  function setBody(html) {
    const body = document.getElementById('castAirplayBody');
    if (body) body.innerHTML = html;
  }

  function setSub(text) {
    const el = document.getElementById('castAirplaySub');
    if (el) el.textContent = String(text || '');
  }

  async function onActionClick(event) {
    event.preventDefault();
    event.stopPropagation();
    closeMapperMenu();
    const sel = selection();
    if (!sel.photo_ids.length && !sel.folder_paths.length) {
      notify(tr('Vælg mindst ét billede, én video eller én mappe.', 'Select at least one photo, video or folder.'), 'err');
      return;
    }
    openModal();
    setError('');
    setSub(tr('Klargør valget…', 'Preparing selection…'));
    setBody(`<div class="cast-airplay-loading">${esc(tr('Klargør billeder og videoer til afspilning…', 'Preparing photos and videos for playback…'))}</div>`);
    try {
      lastSession = await api('/session', {
        method: 'POST',
        body: JSON.stringify({...sel, title: selectionTitle(sel)}),
      });
      renderReady();
    } catch (error) {
      setError(error.message || error);
      setBody('');
    }
  }

  function renderReady() {
    if (!lastSession) return;
    const p = platform();
    const count = Number(lastSession.item_count || 0);
    setSub(`${count} ${count === 1 ? tr('medie', 'item') : tr('medier', 'items')}`);
    setError('');

    if (p === 'ios') {
      const mixedNote = lastSession.contains_images
        ? tr('Video kan sendes via Apples AirPlay-vælger. For billeder eller et blandet slideshow åbner FjordLens en fuldskærmsvisning, som kan vises via Skærmdublering i Kontrolcenter.', 'Video can use Apple’s AirPlay picker. For photos or a mixed slideshow FjordLens opens a fullscreen view that can be shown with Screen Mirroring from Control Center.')
        : tr('FjordLens åbner afspilleren, hvor du kan vælge AirPlay-enheden.', 'FjordLens opens the player where you can choose the AirPlay device.');
      setBody(`
        <div class="cast-airplay-choice">
          <div class="cast-airplay-platform-icon"></div>
          <div><strong>AirPlay</strong><p>${esc(mixedNote)}</p></div>
        </div>
        <div class="cast-airplay-actions"><button type="button" class="btn primary" data-airplay-start>${esc(tr('Åbn AirPlay', 'Open AirPlay'))}</button></div>`);
      return;
    }

    if (p === 'android') {
      if (lastSession.cast_configured) {
        setBody(`
          <div class="cast-airplay-choice">
            <div class="cast-airplay-platform-icon">▣</div>
            <div><strong>Google Cast</strong><p>${esc(tr('Vælg Chromecast, Google TV eller Nest-skærm. FjordLens fortsætter selv slideshowet på modtageren.', 'Choose a Chromecast, Google TV or Nest display. FjordLens keeps the slideshow running on the receiver.'))}</p></div>
          </div>
          <div class="cast-airplay-actions"><button type="button" class="btn primary" data-cast-start>${esc(tr('Vælg Cast-enhed', 'Choose Cast device'))}</button></div>`);
      } else if (lastSession.can_admin) {
        setBody(`
          <div class="cast-airplay-choice"><div class="cast-airplay-platform-icon">▣</div><div><strong>${esc(tr('Google Cast skal opsættes én gang', 'Google Cast needs one-time setup'))}</strong><p>${esc(tr('Receiver-siden er allerede klar i FjordLens. Opret en Custom Web Receiver hos Google og indsæt App ID’et her.', 'The receiver page is already ready in FjordLens. Create a Custom Web Receiver with Google and enter its App ID here.'))}</p></div></div>
          <div class="cast-airplay-actions"><button type="button" class="btn primary" data-cast-setup>${esc(tr('Opsæt Google Cast', 'Set up Google Cast'))}</button></div>`);
      } else {
        setBody(`<div class="cast-airplay-note">${esc(tr('Google Cast er ikke konfigureret endnu. En administrator skal indsætte Cast Receiver App ID i FjordLens.', 'Google Cast is not configured yet. An administrator must enter the Cast Receiver App ID in FjordLens.'))}</div>`);
      }
      return;
    }

    setBody(`
      <div class="cast-airplay-note">${esc(tr('Denne funktion er lavet til telefoner. Vælg Cast på Android eller AirPlay på iPhone.', 'This feature is intended for phones. Use Cast on Android or AirPlay on iPhone.'))}</div>
      <div class="cast-airplay-actions">
        ${lastSession.cast_configured ? `<button type="button" class="btn primary" data-cast-start>Google Cast</button>` : ''}
        <button type="button" class="btn" data-airplay-start>AirPlay</button>
      </div>`);
  }

  function renderSetup() {
    if (!lastSession) return;
    setSub(tr('Google Cast · opsætning', 'Google Cast · setup'));
    setError('');
    setBody(`
      <div class="cast-airplay-note">
        <strong>${esc(tr('Receiver URL', 'Receiver URL'))}</strong>
        <code>${esc(lastSession.receiver_url || '')}</code>
        <p>${esc(tr('Brug denne URL som Custom Web Receiver URL i Google Cast SDK Developer Console.', 'Use this URL as the Custom Web Receiver URL in the Google Cast SDK Developer Console.'))}</p>
      </div>
      <label class="cast-airplay-field">
        <span>Cast Receiver App ID</span>
        <input id="castReceiverAppIdInput" type="text" autocomplete="off" autocapitalize="characters" placeholder="XXXXXXXX">
      </label>
      <div class="cast-airplay-actions">
        <button type="button" class="btn" data-cast-close>${esc(tr('Annuller', 'Cancel'))}</button>
        <button type="button" class="btn primary" data-cast-setup-save>${esc(tr('Gem', 'Save'))}</button>
      </div>`);
  }

  async function saveCastSetup() {
    const input = document.getElementById('castReceiverAppIdInput');
    const appId = String(input?.value || '').trim();
    if (!appId) { setError(tr('Indsæt Cast Receiver App ID.', 'Enter the Cast Receiver App ID.')); return; }
    setError('');
    try {
      const status = await api('/config', {method:'POST', body:JSON.stringify({cast_receiver_app_id: appId})});
      statusCache = status;
      if (lastSession) {
        lastSession.cast_receiver_app_id = status.cast_receiver_app_id || appId;
        lastSession.cast_configured = true;
      }
      renderReady();
      notify(tr('Google Cast er gemt.', 'Google Cast setup saved.'), 'ok');
    } catch (error) {
      setError(error.message || error);
    }
  }

  function loadCastSdk() {
    if (window.cast?.framework && window.chrome?.cast) return Promise.resolve(true);
    if (castSdkPromise) return castSdkPromise;
    castSdkPromise = new Promise((resolve, reject) => {
      const previous = window.__onGCastApiAvailable;
      window.__onGCastApiAvailable = (available, errorInfo) => {
        try { if (typeof previous === 'function') previous(available, errorInfo); } catch (_) {}
        if (available) resolve(true);
        else reject(new Error(tr('Google Cast er ikke tilgængelig i denne browser.', 'Google Cast is not available in this browser.')));
      };
      let script = document.querySelector('script[data-fjordlens-cast-sdk]');
      if (!script) {
        script = document.createElement('script');
        script.dataset.fjordlensCastSdk = '1';
        script.src = 'https://www.gstatic.com/cv/js/sender/v1/cast_sender.js?loadCastFramework=1';
        script.async = true;
        script.onerror = () => reject(new Error(tr('Kunne ikke indlæse Google Cast SDK.', 'Could not load Google Cast SDK.')));
        document.head.appendChild(script);
      }
      window.setTimeout(() => {
        if (!(window.cast?.framework && window.chrome?.cast)) reject(new Error(tr('Google Cast blev ikke klar i tide.', 'Google Cast did not become ready in time.')));
      }, 12000);
    });
    return castSdkPromise;
  }

  async function startGoogleCast() {
    if (!lastSession || !lastSession.cast_receiver_app_id) {
      setError(tr('Cast Receiver App ID mangler.', 'Cast Receiver App ID is missing.'));
      return;
    }
    setError('');
    try {
      await loadCastSdk();
      const context = cast.framework.CastContext.getInstance();
      context.setOptions({
        receiverApplicationId: String(lastSession.cast_receiver_app_id),
        autoJoinPolicy: chrome.cast.AutoJoinPolicy.ORIGIN_SCOPED,
      });
      await context.requestSession();
      castSession = context.getCurrentSession();
      if (!castSession) throw new Error(tr('Cast-sessionen kunne ikke startes.', 'Could not start the Cast session.'));
      await new Promise(resolve => setTimeout(resolve, 650));
      await sendCastLoad(true);
      renderCastControls();
    } catch (error) {
      const text = String(error?.message || error || '');
      if (!/cancel/i.test(text)) setError(text);
    }
  }

  async function sendCastMessage(message) {
    if (!castSession) {
      try { castSession = cast.framework.CastContext.getInstance().getCurrentSession(); } catch (_) {}
    }
    if (!castSession) throw new Error(tr('Ingen aktiv Cast-session.', 'No active Cast session.'));
    return castSession.sendMessage(String(lastSession?.namespace || 'urn:x-cast:dk.glerup.fjordlens.gallery'), message);
  }

  async function sendCastLoad(retry = false) {
    if (!lastSession) return;
    const message = {type:'LOAD', session_url:lastSession.session_url};
    try {
      await sendCastMessage(message);
    } catch (error) {
      if (!retry) throw error;
      await new Promise(resolve => setTimeout(resolve, 900));
      await sendCastMessage(message);
    }
  }

  async function sendCastCommand(type) {
    setError('');
    try { await sendCastMessage({type}); }
    catch (error) { setError(error.message || error); }
  }

  function renderCastControls() {
    const count = Number(lastSession?.item_count || 0);
    setSub(tr('Caster nu', 'Casting now'));
    setBody(`
      <div class="cast-airplay-casting">
        <div class="cast-airplay-castmark">▣</div>
        <strong>${esc(tr('FjordLens caster', 'FjordLens is casting'))}</strong>
        <span>${count} ${count === 1 ? tr('medie', 'item') : tr('medier', 'items')}</span>
      </div>
      <div class="cast-airplay-controls">
        <button type="button" class="btn" data-cast-prev>‹ ${esc(tr('Forrige', 'Previous'))}</button>
        <button type="button" class="btn" data-cast-reload>${esc(tr('Start forfra', 'Restart'))}</button>
        <button type="button" class="btn" data-cast-next>${esc(tr('Næste', 'Next'))} ›</button>
      </div>`);
  }

  function openAirplayPlayer() {
    if (!lastSession?.play_url) return;
    // A new top-level Safari page is required for Apple's native playback-target picker.
    window.location.href = String(lastSession.play_url);
  }

  function init() {
    ensureAction();
    refreshAction();
    window.addEventListener('resize', refreshAction, {passive:true});
    document.addEventListener('click', () => setTimeout(refreshAction, 0), true);
    document.addEventListener('touchend', () => setTimeout(refreshAction, 0), true);
    observer = new MutationObserver(() => refreshAction());
    observer.observe(document.body, {subtree:true, childList:true, attributes:true, attributeFilter:['class']});
    loadStatus().catch(() => {});
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init, {once:true});
  else init();
})();
