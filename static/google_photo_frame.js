(() => {
  'use strict';

  const API = '/api/google-photo-frame';
  let gpfStatus = null;
  let statusLoading = null;
  let observer = null;

  const DA = {
    sectionTitle: 'Google Photo Frame',
    sectionSub: 'Google Photos-album til Nest Hub\'ens normale pauseskærm/slideshow.',
    nativeSectionTitle: 'FjordLens fotorammer',
    nativeSectionSub: 'Raspberry Pi-rammer med direkte status, synk, version og fjernstyring.',
    cardTitle: 'Google Nest Photo Frame',
    notConfigured: 'Mangler opsætning',
    disconnected: 'Ikke forbundet',
    connected: 'Forbundet',
    type: 'Type',
    typeValue: 'Google Photos Photo Frame',
    album: 'Album',
    photos: 'Billeder i frame',
    uploaded: 'Uploadet af FjordLens',
    lastSync: 'Sidste synk',
    devices: 'Nest-skærme',
    devicesValue: 'Styres i Google Home',
    noDeviceInfo: 'Google giver ikke FjordLens IP, online-status eller enhedsliste. Derfor viser dette kort album- og synkstatus i stedet.',
    setupHint: 'Vælg dette album én gang i Google Home under din Nest Hub → Photo Frame → Google Photos. Derefter kan FjordLens styre billederne herfra.',
    configure: 'Opsæt Google',
    connect: 'Forbind Google',
    settings: 'Indstillinger',
    choose: 'Vælg billeder',
    openAlbum: 'Åbn album',
    refresh: 'Opdater',
    disconnect: 'Afbryd',
    configTitle: 'Google Photo Frame – opsætning',
    clientId: 'OAuth Client ID',
    clientSecret: 'OAuth Client Secret',
    secretHelp: 'Lad feltet være tomt senere for at beholde den gemte secret.',
    redirect: 'Authorized redirect URI',
    redirectHelp: 'Denne adresse skal indsættes præcist i Google Cloud OAuth-klienten.',
    albumTitle: 'Album-navn',
    cancel: 'Annuller',
    save: 'Gem',
    googleCloudHelp: 'I Google Cloud: aktivér Google Photos Library API, opret en OAuth 2.0 Web application og tilføj redirect-adressen ovenfor.',
    configureFirst: 'Gem OAuth-oplysningerne først.',
    saved: 'Google-indstillinger gemt.',
    connectPopup: 'Google-login er åbnet i et nyt vindue.',
    disconnectedOk: 'Google Photo Frame er afbrudt.',
    disconnectConfirm: 'Afbryd Google Photos fra FjordLens? Albummet og de uploadede billeder slettes ikke.',
    selectHint: 'Hold på et billede for at starte valg. Når billeder er markeret, vises knappen “Google Frame”.',
    mapperButton: 'Google Frame',
    actionTitle: 'Google Photo Frame',
    selected: 'valgt',
    add: 'Tilføj valgte',
    remove: 'Fjern valgte',
    removeHelp: 'Fjern betyder kun fra Photo Frame-albummet. Google API’et kan ikke slette den uploadede kopi fra Google Photos-biblioteket.',
    sending: 'Sender billeder til Google Photo Frame',
    removing: 'Fjerner billeder fra Google Photo Frame',
    doneAdd: 'Google Photo Frame opdateret',
    doneRemove: 'Billeder fjernet fra Google Photo Frame',
    error: 'Google Photo Frame-fejl',
    noSelection: 'Vælg mindst ét billede først.',
    loading: 'Henter Google-status…',
    never: 'Aldrig',
    localCountSuffix: 'lokalt registreret',
  };

  const EN = {
    ...DA,
    sectionTitle: 'Google Photo Frame',
    sectionSub: 'Google Photos album for the Nest Hub normal ambient slideshow.',
    nativeSectionTitle: 'FjordLens photo frames',
    nativeSectionSub: 'Raspberry Pi frames with direct status, sync, version and remote control.',
    cardTitle: 'Google Nest Photo Frame',
    notConfigured: 'Setup needed',
    disconnected: 'Not connected',
    connected: 'Connected',
    type: 'Type', typeValue: 'Google Photos Photo Frame', album: 'Album', photos: 'Photos in frame', uploaded: 'Uploaded by FjordLens', lastSync: 'Last sync',
    devices: 'Nest displays', devicesValue: 'Managed in Google Home',
    noDeviceInfo: 'Google does not expose device IP, online status or the Nest device list to FjordLens. This card therefore shows album and sync status instead.',
    setupHint: 'Choose this album once in Google Home under your Nest Hub → Photo Frame → Google Photos. FjordLens can then manage the photos here.',
    configure: 'Set up Google', connect: 'Connect Google', settings: 'Settings', choose: 'Choose photos', openAlbum: 'Open album', refresh: 'Refresh', disconnect: 'Disconnect',
    configTitle: 'Google Photo Frame – setup', clientId: 'OAuth Client ID', clientSecret: 'OAuth Client Secret', secretHelp: 'Leave blank later to keep the stored secret.',
    redirect: 'Authorized redirect URI', redirectHelp: 'Add this exact address to the Google Cloud OAuth client.', albumTitle: 'Album name', cancel: 'Cancel', save: 'Save',
    googleCloudHelp: 'In Google Cloud: enable Google Photos Library API, create an OAuth 2.0 Web application and add the redirect URI above.',
    configureFirst: 'Save the OAuth settings first.', saved: 'Google settings saved.', connectPopup: 'Google sign-in opened in a new window.', disconnectedOk: 'Google Photo Frame disconnected.',
    disconnectConfirm: 'Disconnect Google Photos from FjordLens? The album and uploaded photos will not be deleted.', selectHint: 'Long-press a photo to start selecting. Once photos are selected, the “Google Frame” button appears.',
    mapperButton: 'Google Frame', actionTitle: 'Google Photo Frame', selected: 'selected', add: 'Add selected', remove: 'Remove selected',
    removeHelp: 'Remove only removes items from the Photo Frame album. The Google API cannot delete the uploaded copy from the Google Photos library.',
    sending: 'Sending photos to Google Photo Frame', removing: 'Removing photos from Google Photo Frame', doneAdd: 'Google Photo Frame updated', doneRemove: 'Photos removed from Google Photo Frame',
    error: 'Google Photo Frame error', noSelection: 'Select at least one photo first.', loading: 'Loading Google status…', never: 'Never', localCountSuffix: 'tracked locally',
  };

  const T = () => String(document.documentElement.lang || 'da').toLowerCase().startsWith('en') ? EN : DA;
  const esc = (value) => String(value == null ? '' : value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

  function appState() {
    try { return state; } catch (_) { return null; }
  }

  function notify(text, type = 'ok') {
    try {
      if (typeof showStatus === 'function') { showStatus(text, type); return; }
    } catch (_) {}
    console[type === 'err' ? 'error' : 'log'](text);
  }

  function fmtDate(value) {
    if (!value) return T().never;
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return String(value);
    try { return date.toLocaleString(String(document.documentElement.lang || 'da-DK')); } catch (_) { return date.toLocaleString(); }
  }

  async function api(path, options = {}) {
    const response = await fetch(`${API}${path}`, {
      credentials: 'same-origin',
      ...options,
      headers: {
        ...(options.body ? {'Content-Type': 'application/json'} : {}),
        ...(options.headers || {}),
      },
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok && response.status !== 207) throw new Error(data.error || `HTTP ${response.status}`);
    return data;
  }

  async function loadStatus(refresh = false) {
    if (statusLoading && !refresh) return statusLoading;
    statusLoading = api(`/status${refresh ? '?refresh=1' : ''}`)
      .then(data => {
        gpfStatus = data.item || null;
        renderSection();
        mountMapperButton();
        return gpfStatus;
      })
      .catch(err => {
        gpfStatus = {configured:false, connected:false, can_admin:false, last_error:String(err.message || err)};
        renderSection();
        return gpfStatus;
      })
      .finally(() => { statusLoading = null; });
    return statusLoading;
  }

  function currentViewIsPhotoframe() {
    const s = appState();
    if (s && s.view) return s.view === 'photoframe';
    return !!document.querySelector('.nav-item.active[data-view="photoframe"]');
  }

  function ensureSection() {
    if (!currentViewIsPhotoframe()) return null;
    const wrap = document.querySelector('#galleryGrid .photoframe-wrap');
    if (!wrap) return null;
    let section = document.getElementById('gpfSection');
    if (!section) {
      section = document.createElement('section');
      section.id = 'gpfSection';
      section.className = 'gpf-section';
      wrap.prepend(section);
    }
    ensureNativeHeading(wrap);
    return section;
  }

  function ensureNativeHeading(wrap) {
    let heading = document.getElementById('gpfNativeHeading');
    if (!heading) {
      heading = document.createElement('div');
      heading.id = 'gpfNativeHeading';
      heading.className = 'gpf-native-section-head';
      const googleSection = document.getElementById('gpfSection');
      if (googleSection && googleSection.parentNode === wrap) googleSection.insertAdjacentElement('afterend', heading);
      else wrap.prepend(heading);
    }
    const t = T();
    const markup = `<div><h2>${esc(t.nativeSectionTitle)}</h2><p>${esc(t.nativeSectionSub)}</p></div>`;
    if (heading.innerHTML !== markup) heading.innerHTML = markup;
  }

  function statusBadge(status) {
    const t = T();
    if (!status || !status.configured) return `<span class="gpf-badge is-warn"><span class="dot"></span>${esc(t.notConfigured)}</span>`;
    if (!status.connected) return `<span class="gpf-badge is-off"><span class="dot"></span>${esc(t.disconnected)}</span>`;
    return `<span class="gpf-badge is-on"><span class="dot"></span>${esc(t.connected)}</span>`;
  }

  function renderSection() {
    const section = ensureSection();
    if (!section) return;
    const t = T();
    const s = gpfStatus;
    if (!s) {
      const markup = `<div class="gpf-section-head"><div><h2>${esc(t.sectionTitle)}</h2><p>${esc(t.sectionSub)}</p></div></div><div class="gpf-card"><div class="mini-label">${esc(t.loading)}</div></div>`;
      if (section.dataset.gpfSignature !== 'loading') {
        section.dataset.gpfSignature = 'loading';
        section.innerHTML = markup;
      }
      return;
    }
    const albumLabel = s.album_title || 'FjordLens Photo Frame';
    const countText = s.remote_count != null ? String(s.remote_count) : String(s.synced_count || 0);
    const actions = [];
    if (s.can_admin) {
      if (!s.configured) actions.push(`<button class="btn small primary" data-gpf-action="config">${esc(t.configure)}</button>`);
      else if (!s.connected) {
        actions.push(`<button class="btn small primary" data-gpf-action="connect">${esc(t.connect)}</button>`);
        actions.push(`<button class="btn small" data-gpf-action="config">${esc(t.settings)}</button>`);
      } else {
        actions.push(`<button class="btn small primary" data-gpf-action="choose">${esc(t.choose)}</button>`);
        if (s.album_url) actions.push(`<button class="btn small" data-gpf-action="open-album">${esc(t.openAlbum)}</button>`);
        actions.push(`<button class="btn small" data-gpf-action="refresh">${esc(t.refresh)}</button>`);
        actions.push(`<button class="btn small" data-gpf-action="config">${esc(t.settings)}</button>`);
      }
    } else if (s.album_url) {
      actions.push(`<button class="btn small" data-gpf-action="open-album">${esc(t.openAlbum)}</button>`);
    }

    const markup = `
      <div class="gpf-section-head">
        <div><h2>${esc(t.sectionTitle)}</h2><p>${esc(t.sectionSub)}</p></div>
      </div>
      <article class="gpf-card">
        <div class="gpf-card-head"><h3>${esc(t.cardTitle)}</h3>${statusBadge(s)}</div>
        <div class="gpf-meta">
          <div class="gpf-row"><span>${esc(t.type)}</span><strong>${esc(t.typeValue)}</strong></div>
          <div class="gpf-row"><span>${esc(t.album)}</span><strong>${esc(albumLabel)}</strong></div>
          <div class="gpf-row"><span>${esc(t.photos)}</span><strong>${esc(countText)}</strong></div>
          <div class="gpf-row"><span>${esc(t.uploaded)}</span><strong>${esc(String(s.uploaded_count || 0))} ${esc(t.localCountSuffix)}</strong></div>
          <div class="gpf-row"><span>${esc(t.lastSync)}</span><strong>${esc(fmtDate(s.last_sync_at))}</strong></div>
          <div class="gpf-row"><span>${esc(t.devices)}</span><strong>${esc(t.devicesValue)}</strong></div>
        </div>
        <div class="gpf-note">${esc(t.noDeviceInfo)}</div>
        ${s.connected ? `<div class="gpf-hint">${esc(t.setupHint)}</div>` : ''}
        ${s.last_error ? `<div class="gpf-error">${esc(s.last_error)}</div>` : ''}
        <div class="gpf-actions">${actions.join('')}</div>
        ${s.can_admin && s.connected ? `<div class="gpf-subactions"><button class="gpf-link-danger" data-gpf-action="disconnect">${esc(t.disconnect)}</button></div>` : ''}
      </article>`;
    const signature = JSON.stringify([
      document.documentElement.lang || 'da',
      s.configured, s.connected, s.can_admin, s.client_id, s.redirect_uri,
      s.album_title, s.album_id, s.album_url, s.synced_count, s.uploaded_count,
      s.remote_count, s.last_sync_at, s.last_error,
    ]);
    if (section.dataset.gpfSignature !== signature) {
      section.dataset.gpfSignature = signature;
      section.innerHTML = markup;
    }
  }

  function ensureConfigModal() {
    let modal = document.getElementById('gpfConfigModal');
    if (modal) return modal;
    modal = document.createElement('div');
    modal.id = 'gpfConfigModal';
    modal.className = 'gpf-modal hidden';
    document.body.appendChild(modal);
    return modal;
  }

  function openConfig() {
    const t = T();
    const s = gpfStatus || {};
    const modal = ensureConfigModal();
    modal.innerHTML = `
      <div class="gpf-modal-backdrop" data-gpf-close></div>
      <div class="gpf-modal-card" role="dialog" aria-modal="true">
        <div class="gpf-modal-head"><h3>${esc(t.configTitle)}</h3><button class="btn ghost small" data-gpf-close>×</button></div>
        <p class="gpf-help">${esc(t.googleCloudHelp)}</p>
        <label class="gpf-field"><span>${esc(t.clientId)}</span><input id="gpfClientId" type="text" autocomplete="off" value="${esc(s.client_id || '')}"></label>
        <label class="gpf-field"><span>${esc(t.clientSecret)}</span><input id="gpfClientSecret" type="password" autocomplete="new-password" placeholder="••••••••••••"></label>
        <div class="gpf-help">${esc(t.secretHelp)}</div>
        <label class="gpf-field"><span>${esc(t.redirect)}</span><input id="gpfRedirectUri" type="url" value="${esc(s.redirect_uri || '')}"></label>
        <div class="gpf-help">${esc(t.redirectHelp)}</div>
        <label class="gpf-field"><span>${esc(t.albumTitle)}</span><input id="gpfAlbumTitle" type="text" value="${esc(s.album_title || 'FjordLens Photo Frame')}"></label>
        <div class="gpf-modal-actions"><button class="btn" data-gpf-close>${esc(t.cancel)}</button><button class="btn primary" data-gpf-save>${esc(t.save)}</button></div>
      </div>`;
    modal.classList.remove('hidden');
  }

  function closeConfig() {
    const modal = document.getElementById('gpfConfigModal');
    if (modal) modal.classList.add('hidden');
  }

  async function saveConfig() {
    const t = T();
    const button = document.querySelector('[data-gpf-save]');
    if (button) button.disabled = true;
    try {
      const data = await api('/config', {
        method: 'POST',
        body: JSON.stringify({
          client_id: document.getElementById('gpfClientId')?.value || '',
          client_secret: document.getElementById('gpfClientSecret')?.value || '',
          redirect_uri: document.getElementById('gpfRedirectUri')?.value || '',
          album_title: document.getElementById('gpfAlbumTitle')?.value || 'FjordLens Photo Frame',
        }),
      });
      gpfStatus = data.item || gpfStatus;
      closeConfig();
      renderSection();
      notify(t.saved, 'ok');
    } catch (err) {
      notify(`${t.error}: ${err.message || err}`, 'err');
    } finally {
      if (button) button.disabled = false;
    }
  }

  function connectGoogle() {
    const t = T();
    if (!gpfStatus?.configured) { openConfig(); notify(t.configureFirst, 'err'); return; }
    const popup = window.open(`${API}/oauth/start`, 'fjordlensGooglePhotoFrame', 'width=720,height=780,resizable=yes,scrollbars=yes');
    if (!popup) window.location.href = `${API}/oauth/start`;
    else notify(t.connectPopup, 'ok');
  }

  async function disconnectGoogle() {
    const t = T();
    if (!window.confirm(t.disconnectConfirm)) return;
    try {
      const data = await api('/disconnect', {method:'POST', body:'{}'});
      gpfStatus = data.item || gpfStatus;
      renderSection();
      mountMapperButton();
      notify(t.disconnectedOk, 'ok');
    } catch (err) { notify(`${t.error}: ${err.message || err}`, 'err'); }
  }

  function choosePhotos() {
    const t = T();
    const mapper = document.querySelector('.nav-item[data-view="mapper"]');
    if (mapper) mapper.click();
    setTimeout(() => notify(t.selectHint, 'ok'), 200);
  }

  function selectedPhotoIds() {
    const s = appState();
    if (!s || !s.mapperSelectedPhotoIds) return [];
    try { return Array.from(s.mapperSelectedPhotoIds).map(Number).filter(id => Number.isFinite(id) && id > 0); } catch (_) { return []; }
  }

  function mountMapperButton() {
    const existing = document.getElementById('gpfMapperButton');
    const s = appState();
    const ids = selectedPhotoIds();
    const shouldShow = !!(gpfStatus?.connected && gpfStatus?.can_admin && s && s.view === 'mapper' && s.mapperEditMode && ids.length);
    if (!shouldShow) { if (existing) existing.remove(); return; }
    const row = document.querySelector('#mapperTools .mapper-tools-row');
    if (!row) return;
    let button = existing;
    if (!button) {
      button = document.createElement('button');
      button.id = 'gpfMapperButton';
      button.className = 'btn gpf-mapper-btn';
      button.type = 'button';
      button.addEventListener('click', openSelectionActions);
      row.appendChild(button);
    }
    const nextText = `${T().mapperButton} (${ids.length})`;
    if (button.textContent !== nextText) button.textContent = nextText;
  }

  function openSelectionActions() {
    const ids = selectedPhotoIds();
    const t = T();
    if (!ids.length) { notify(t.noSelection, 'err'); return; }
    let modal = document.getElementById('gpfActionModal');
    if (!modal) {
      modal = document.createElement('div');
      modal.id = 'gpfActionModal';
      modal.className = 'gpf-modal hidden';
      document.body.appendChild(modal);
    }
    modal.innerHTML = `
      <div class="gpf-modal-backdrop" data-gpf-action-close></div>
      <div class="gpf-modal-card gpf-action-card" role="dialog" aria-modal="true">
        <div class="gpf-modal-head"><h3>${esc(t.actionTitle)}</h3><button class="btn ghost small" data-gpf-action-close>×</button></div>
        <p><strong>${ids.length}</strong> ${esc(t.selected)}</p>
        <div class="gpf-big-actions"><button class="btn primary" data-gpf-sync="add">${esc(t.add)}</button><button class="btn" data-gpf-sync="remove">${esc(t.remove)}</button></div>
        <p class="gpf-help">${esc(t.removeHelp)}</p>
      </div>`;
    modal.classList.remove('hidden');
  }

  function closeActionModal() {
    document.getElementById('gpfActionModal')?.classList.add('hidden');
  }

  async function syncSelection(mode) {
    const ids = selectedPhotoIds();
    const t = T();
    if (!ids.length) { notify(t.noSelection, 'err'); return; }
    closeActionModal();
    const chunks = [];
    for (let i = 0; i < ids.length; i += 20) chunks.push(ids.slice(i, i + 20));
    let completed = 0;
    let changed = 0;
    let failed = 0;
    for (const chunk of chunks) {
      notify(`${mode === 'add' ? t.sending : t.removing}… ${completed}/${ids.length}`, 'ok');
      try {
        const data = await api(`/photos/${mode === 'add' ? 'add' : 'remove'}`, {method:'POST', body:JSON.stringify({photo_ids: chunk})});
        changed += Number(mode === 'add' ? data.added || 0 : data.removed || 0);
        failed += Array.isArray(data.failed) ? data.failed.length : 0;
      } catch (err) {
        failed += chunk.length;
        notify(`${t.error}: ${err.message || err}`, 'err');
      }
      completed += chunk.length;
    }
    await loadStatus(true);
    const base = mode === 'add' ? t.doneAdd : t.doneRemove;
    notify(`${base}: ${changed}${failed ? ` · ${failed} fejl` : ''}`, failed ? 'err' : 'ok');
  }

  function handleSectionClick(event) {
    const button = event.target.closest('[data-gpf-action]');
    if (!button) return;
    const action = button.dataset.gpfAction;
    if (action === 'config') openConfig();
    else if (action === 'connect') connectGoogle();
    else if (action === 'choose') choosePhotos();
    else if (action === 'open-album' && gpfStatus?.album_url) window.open(gpfStatus.album_url, '_blank', 'noopener');
    else if (action === 'refresh') loadStatus(true);
    else if (action === 'disconnect') disconnectGoogle();
  }

  function installEvents() {
    document.addEventListener('click', event => {
      if (event.target.closest('#gpfSection [data-gpf-action]')) handleSectionClick(event);
      if (event.target.closest('[data-gpf-close]')) closeConfig();
      if (event.target.closest('[data-gpf-save]')) saveConfig();
      if (event.target.closest('[data-gpf-action-close]')) closeActionModal();
      const syncBtn = event.target.closest('[data-gpf-sync]');
      if (syncBtn) syncSelection(syncBtn.dataset.gpfSync);
    });
    window.addEventListener('message', event => {
      if (event.origin !== window.location.origin) return;
      if (event.data?.type !== 'fjordlens-google-photo-frame') return;
      loadStatus(true);
    });
  }

  function installObserver() {
    if (observer) return;
    observer = new MutationObserver(() => {
      renderSection();
      mountMapperButton();
    });
    observer.observe(document.body, {childList:true, subtree:true});
  }

  function init() {
    installEvents();
    installObserver();
    renderSection();
    loadStatus(false);
    // Core changes views without always replacing the full page, so keep a tiny fallback tick.
    setInterval(() => { renderSection(); mountMapperButton(); }, 1200);
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init, {once:true});
  else init();
})();
