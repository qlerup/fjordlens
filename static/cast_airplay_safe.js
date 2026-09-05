(() => {
  'use strict';

  const API = '/api/cast-airplay';
  const ACTION_ID = 'mapperHeaderCastAirplayAction';
  const DEFAULT_NS = 'urn:x-cast:dk.glerup.fjordlens.gallery';
  let lastSession = null;
  let castSdkPromise = null;
  let castSession = null;
  let preparingSession = false;
  let refreshTimer = null;

  const esc = value => String(value == null ? '' : value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const isEnglish = () => String(document.documentElement.lang || 'da').toLowerCase().startsWith('en');
  const tr = (da, en) => isEnglish() ? en : da;

  function appState() { try { return state; } catch (_) { return null; } }
  function notify(text, type = 'ok') {
    try { if (typeof showStatus === 'function') { showStatus(text, type); return; } } catch (_) {}
    console[type === 'err' ? 'error' : 'log'](text);
  }
  function isPhone() {
    const ua = String(navigator.userAgent || '');
    if (/iPhone|iPad|iPod/i.test(ua)) return true;
    if (/Android.*Mobile/i.test(ua)) return true;
    try { return window.matchMedia('(max-width:760px)').matches && (navigator.maxTouchPoints > 0 || 'ontouchstart' in window); }
    catch (_) { return false; }
  }
  function platform() {
    const ua = String(navigator.userAgent || '');
    if (/iPhone|iPad|iPod/i.test(ua)) return 'ios';
    if (/Android/i.test(ua)) return 'android';
    return 'mobile';
  }
  async function api(path, options = {}, timeoutMs = 15000) {
    const controller = typeof AbortController !== 'undefined' ? new AbortController() : null;
    const timer = controller ? setTimeout(() => controller.abort(), timeoutMs) : null;
    try {
      const response = await window.fetch(`${API}${path}`, {
        credentials: 'same-origin',
        ...options,
        ...(controller ? {signal: controller.signal} : {}),
        headers: {...(options.body ? {'Content-Type':'application/json'} : {}), ...(options.headers || {})},
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
      return data;
    } catch (error) {
      if (error?.name === 'AbortError') throw new Error(tr('FjordLens-serveren svarede ikke inden for 15 sekunder.', 'The FjordLens server did not respond within 15 seconds.'));
      throw error;
    } finally {
      if (timer) clearTimeout(timer);
    }
  }

  function selection() {
    const s = appState();
    if (!s) return {photo_ids:[], folder_paths:[]};
    return {
      photo_ids: Array.from(s.mapperSelectedPhotoIds || []).map(v => Number(v || 0)).filter(v => Number.isFinite(v) && v > 0),
      folder_paths: Array.from(s.mapperSelectedFolders || []).map(v => String(v || '').trim()).filter(Boolean),
    };
  }
  function selectionTitle(sel) {
    if (sel.folder_paths.length === 1 && !sel.photo_ids.length) {
      const name = String(sel.folder_paths[0] || '').split('/').filter(Boolean).pop();
      return name ? `FjordLens · ${name}` : 'FjordLens';
    }
    const count = sel.photo_ids.length + sel.folder_paths.length;
    return count > 1 ? `FjordLens · ${count} ${tr('valg', 'selections')}` : 'FjordLens';
  }

  function ensureAction() {
    const menu = document.getElementById('mapperHeaderMenu');
    if (!menu) return null;
    let btn = document.getElementById(ACTION_ID);
    if (btn) return btn;
    btn = document.createElement('button');
    btn.id = ACTION_ID;
    btn.type = 'button';
    btn.className = 'mapper-header-menu-item hidden';
    btn.textContent = 'AirPlay / Cast';
    const share = document.getElementById('mapperHeaderShareAction');
    if (share && share.parentNode === menu) share.insertAdjacentElement('afterend', btn); else menu.appendChild(btn);
    btn.addEventListener('click', onActionClick);
    return btn;
  }
  function refreshAction() {
    refreshTimer = null;
    const btn = ensureAction();
    if (!btn) return;
    const s = appState();
    const sel = selection();
    const count = sel.photo_ids.length + sel.folder_paths.length;
    const visible = !!(isPhone() && s && s.view === 'mapper' && s.mapperEditMode);
    const disabled = !visible || count === 0 || preparingSession;
    const text = count > 0 ? `AirPlay / Cast (${count})` : 'AirPlay / Cast';
    const title = count > 0
      ? tr('Send de valgte billeder, videoer eller mapper til en skærm', 'Send selected photos, videos or folders to a display')
      : tr('Vælg billeder, videoer eller en mappe først', 'Select photos, videos or a folder first');
    if (visible && btn.classList.contains('hidden')) btn.classList.remove('hidden');
    if (!visible && !btn.classList.contains('hidden')) btn.classList.add('hidden');
    if (btn.disabled !== disabled) btn.disabled = disabled;
    if (btn.textContent !== text) btn.textContent = text;
    if (btn.title !== title) btn.title = title;
  }
  function queueRefresh() {
    if (refreshTimer !== null) return;
    refreshTimer = window.setTimeout(refreshAction, 40);
  }
  function closeMapperMenu() {
    try { if (typeof closeMapperHeaderMenu === 'function') closeMapperHeaderMenu(); }
    catch (_) { document.getElementById('mapperHeaderMenu')?.classList.remove('open'); }
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
        <div class="cast-airplay-head"><div><h3 id="castAirplayTitle">AirPlay / Cast</h3><div id="castAirplaySub" class="mini-label"></div></div><button type="button" class="btn" data-cast-close>×</button></div>
        <div id="castAirplayError" class="cast-airplay-error hidden"></div><div id="castAirplayBody"></div>
      </div>`;
    document.body.appendChild(modal);
    modal.addEventListener('click', event => {
      if (event.target.closest('[data-cast-close]')) return closeModal();
      if (event.target.closest('[data-cast-start]')) return startGoogleCast();
      if (event.target.closest('[data-cast-setup]')) return renderSetup();
      if (event.target.closest('[data-cast-setup-save]')) return saveCastSetup();
      if (event.target.closest('[data-cast-prev]')) return sendCastCommand('PREV');
      if (event.target.closest('[data-cast-next]')) return sendCastCommand('NEXT');
      if (event.target.closest('[data-cast-reload]')) return sendCastLoad();
    });
    return modal;
  }
  function openModal() { const m = ensureModal(); m.classList.remove('hidden'); return m; }
  function closeModal() { document.getElementById('castAirplayModal')?.classList.add('hidden'); }
  function setSub(text) { const el = document.getElementById('castAirplaySub'); if (el && el.textContent !== String(text || '')) el.textContent = String(text || ''); }
  function setBody(html) { const el = document.getElementById('castAirplayBody'); if (el && el.innerHTML !== html) el.innerHTML = html; }
  function setError(message) {
    const el = document.getElementById('castAirplayError');
    if (!el) return;
    const text = String(message || '').trim();
    if (el.textContent !== text) el.textContent = text;
    if (text && el.classList.contains('hidden')) el.classList.remove('hidden');
    if (!text && !el.classList.contains('hidden')) el.classList.add('hidden');
  }

  async function onActionClick(event) {
    event.preventDefault();
    event.stopPropagation();
    if (preparingSession) return;
    closeMapperMenu();
    const sel = selection();
    if (!sel.photo_ids.length && !sel.folder_paths.length) return notify(tr('Vælg mindst ét billede, én video eller én mappe.', 'Select at least one photo, video or folder.'), 'err');
    preparingSession = true;
    queueRefresh();
    openModal();
    setError('');
    setSub(tr('Klargør valget…', 'Preparing selection…'));
    setBody(`<div class="cast-airplay-loading">${esc(tr('Opretter afspilningssession…', 'Creating playback session…'))}</div>`);
    try {
      lastSession = await api('/session', {method:'POST', body:JSON.stringify({...sel, title:selectionTitle(sel)})});
      window.__fjordlensCastSession = lastSession;
      window.dispatchEvent(new CustomEvent('fjordlens:cast-session', {detail:lastSession}));
      renderReady();
    } catch (error) {
      setError(error?.message || error);
      setBody(`<div class="cast-airplay-note">${esc(tr('Sessionen kunne ikke oprettes.', 'The session could not be created.'))}</div>`);
    } finally {
      preparingSession = false;
      queueRefresh();
    }
  }

  function renderReady() {
    if (!lastSession) return;
    const count = Number(lastSession.item_count || 0);
    setSub(`${count} ${count === 1 ? tr('medie', 'item') : tr('medier', 'items')}`);
    setError('');
    if (platform() === 'ios') {
      const note = tr(
        'FjordLens streamer de valgte billeder og videoer løbende til AirPlay. Afspilningen kan starte, så snart de første HLS-segmenter er klar.',
        'FjordLens streams the selected photos and videos progressively to AirPlay. Playback can start as soon as the first HLS segments are ready.'
      );
      return setBody(`<div class="cast-airplay-choice"><div class="cast-airplay-platform-icon"></div><div><strong>AirPlay</strong><p>${esc(note)}</p></div></div><div class="cast-airplay-actions"><button type="button" class="btn primary" data-airplay-start>${esc(tr('AirPlay', 'AirPlay'))}</button></div>`);
    }
    if (platform() === 'android') {
      if (lastSession.cast_configured) return setBody(`<div class="cast-airplay-choice"><div class="cast-airplay-platform-icon">▣</div><div><strong>Google Cast</strong><p>${esc(tr('Vælg Chromecast, Google TV eller Nest-skærm.', 'Choose a Chromecast, Google TV or Nest display.'))}</p></div></div><div class="cast-airplay-actions"><button type="button" class="btn primary" data-cast-start>${esc(tr('Vælg Cast-enhed', 'Choose Cast device'))}</button></div>`);
      if (lastSession.can_admin) return setBody(`<div class="cast-airplay-choice"><div class="cast-airplay-platform-icon">▣</div><div><strong>${esc(tr('Google Cast skal opsættes én gang', 'Google Cast needs one-time setup'))}</strong><p>${esc(tr('Receiver-siden er klar. Opret en Custom Web Receiver hos Google og indsæt App ID’et.', 'The receiver page is ready. Create a Custom Web Receiver with Google and enter its App ID.'))}</p></div></div><div class="cast-airplay-actions"><button type="button" class="btn primary" data-cast-setup>${esc(tr('Opsæt Google Cast', 'Set up Google Cast'))}</button></div>`);
      return setBody(`<div class="cast-airplay-note">${esc(tr('Google Cast er ikke konfigureret endnu.', 'Google Cast is not configured yet.'))}</div>`);
    }
    setBody(`<div class="cast-airplay-note">${esc(tr('Denne funktion er lavet til telefoner.', 'This feature is intended for phones.'))}</div>`);
  }

  function renderSetup() {
    setSub(tr('Google Cast · opsætning', 'Google Cast · setup'));
    setError('');
    setBody(`<div class="cast-airplay-note"><strong>Receiver URL</strong><code>${esc(lastSession?.receiver_url || '')}</code></div><label class="cast-airplay-field"><span>Cast Receiver App ID</span><input id="castReceiverAppIdInput" type="text" autocomplete="off" autocapitalize="characters" placeholder="XXXXXXXX"></label><div class="cast-airplay-actions"><button type="button" class="btn" data-cast-close>${esc(tr('Annuller', 'Cancel'))}</button><button type="button" class="btn primary" data-cast-setup-save>${esc(tr('Gem', 'Save'))}</button></div>`);
  }
  async function saveCastSetup() {
    const appId = String(document.getElementById('castReceiverAppIdInput')?.value || '').trim();
    if (!appId) return setError(tr('Indsæt Cast Receiver App ID.', 'Enter the Cast Receiver App ID.'));
    setError('');
    try {
      const status = await api('/config', {method:'POST', body:JSON.stringify({cast_receiver_app_id:appId})});
      lastSession.cast_receiver_app_id = status.cast_receiver_app_id || appId;
      lastSession.cast_configured = true;
      renderReady();
    } catch (error) { setError(error?.message || error); }
  }

  function loadCastSdk() {
    if (window.cast?.framework && window.chrome?.cast) return Promise.resolve(true);
    if (castSdkPromise) return castSdkPromise;
    castSdkPromise = new Promise((resolve, reject) => {
      const previous = window.__onGCastApiAvailable;
      window.__onGCastApiAvailable = (available, info) => {
        try { if (typeof previous === 'function') previous(available, info); } catch (_) {}
        if (available) resolve(true); else reject(new Error(tr('Google Cast er ikke tilgængelig i denne browser.', 'Google Cast is not available in this browser.')));
      };
      if (!document.querySelector('script[data-fjordlens-cast-sdk]')) {
        const script = document.createElement('script');
        script.dataset.fjordlensCastSdk = '1';
        script.async = true;
        script.src = 'https://www.gstatic.com/cv/js/sender/v1/cast_sender.js?loadCastFramework=1';
        script.onerror = () => reject(new Error(tr('Kunne ikke indlæse Google Cast SDK.', 'Could not load Google Cast SDK.')));
        document.head.appendChild(script);
      }
      setTimeout(() => { if (!(window.cast?.framework && window.chrome?.cast)) reject(new Error(tr('Google Cast blev ikke klar i tide.', 'Google Cast did not become ready in time.'))); }, 12000);
    });
    return castSdkPromise;
  }
  async function startGoogleCast() {
    if (!lastSession?.cast_receiver_app_id) return setError(tr('Cast Receiver App ID mangler.', 'Cast Receiver App ID is missing.'));
    setError('');
    try {
      await loadCastSdk();
      const context = cast.framework.CastContext.getInstance();
      context.setOptions({receiverApplicationId:String(lastSession.cast_receiver_app_id), autoJoinPolicy:chrome.cast.AutoJoinPolicy.ORIGIN_SCOPED});
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
    if (!castSession) { try { castSession = cast.framework.CastContext.getInstance().getCurrentSession(); } catch (_) {} }
    if (!castSession) throw new Error(tr('Ingen aktiv Cast-session.', 'No active Cast session.'));
    return castSession.sendMessage(String(lastSession?.namespace || DEFAULT_NS), message);
  }
  async function sendCastLoad(retry = false) {
    if (!lastSession) return;
    try { await sendCastMessage({type:'LOAD', session_url:lastSession.session_url}); }
    catch (error) {
      if (!retry) throw error;
      await new Promise(resolve => setTimeout(resolve, 900));
      await sendCastMessage({type:'LOAD', session_url:lastSession.session_url});
    }
  }
  async function sendCastCommand(type) {
    setError('');
    try { await sendCastMessage({type}); } catch (error) { setError(error?.message || error); }
  }
  function renderCastControls() {
    const count = Number(lastSession?.item_count || 0);
    setSub(tr('Caster nu', 'Casting now'));
    setBody(`<div class="cast-airplay-casting"><div class="cast-airplay-castmark">▣</div><strong>${esc(tr('FjordLens caster', 'FjordLens is casting'))}</strong><span>${count} ${count === 1 ? tr('medie', 'item') : tr('medier', 'items')}</span></div><div class="cast-airplay-controls"><button type="button" class="btn" data-cast-prev>‹ ${esc(tr('Forrige', 'Previous'))}</button><button type="button" class="btn" data-cast-reload>${esc(tr('Start forfra', 'Restart'))}</button><button type="button" class="btn" data-cast-next>${esc(tr('Næste', 'Next'))} ›</button></div>`);
  }

  function init() {
    ensureAction();
    refreshAction();
    window.addEventListener('resize', queueRefresh, {passive:true});
    document.addEventListener('click', queueRefresh, true);
    document.addEventListener('touchend', queueRefresh, {capture:true, passive:true});
    document.addEventListener('visibilitychange', () => { if (!document.hidden) queueRefresh(); });
    window.setInterval(() => { if (!document.hidden) queueRefresh(); }, 1200);
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init, {once:true}); else init();
})();
