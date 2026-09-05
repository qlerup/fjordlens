(() => {
  'use strict';

  const API = '/api/google-photo-frame';
  let folders = [];
  let activeFolder = '';
  let photos = [];
  let selected = new Set();
  let searchText = '';
  let loading = false;

  const isEnglish = () => String(document.documentElement.lang || 'da').toLowerCase().startsWith('en');
  const t = () => isEnglish() ? {
    title: 'Choose photos for Google Photo Frame',
    hint: 'Choose a folder on the left and select the photos that should appear on the Nest Hub.',
    folders: 'Folders',
    all: 'All photos',
    search: 'Search photos…',
    searchBtn: 'Search',
    selectVisible: 'Select visible',
    clear: 'Clear selection',
    selected: n => `${n} selected`,
    close: 'Close',
    add: 'Add selected',
    remove: 'Remove selected',
    loadingFolders: 'Loading folders…',
    loadingPhotos: 'Loading photos…',
    noPhotos: 'No photos found.',
    noFolders: 'No folders found.',
    loadFailed: 'Could not load photos or folders.',
    noneSelected: 'Select at least one photo first.',
    sending: 'Updating Google Photo Frame…',
    done: 'Google Photo Frame updated.',
    failed: 'Some photos could not be updated.',
    limit: 'Up to 220 photos are shown at a time. Use folders or search to narrow the list.'
  } : {
    title: 'Vælg billeder til Google Photo Frame',
    hint: 'Vælg en mappe til venstre og marker de billeder, der skal vises på Nest Hub.',
    folders: 'Mapper',
    all: 'Alle billeder',
    search: 'Søg i billeder…',
    searchBtn: 'Søg',
    selectVisible: 'Vælg viste',
    clear: 'Ryd valg',
    selected: n => `${n} valgt`,
    close: 'Luk',
    add: 'Tilføj valgte',
    remove: 'Fjern valgte',
    loadingFolders: 'Henter mapper…',
    loadingPhotos: 'Henter billeder…',
    noPhotos: 'Ingen billeder fundet.',
    noFolders: 'Ingen mapper fundet.',
    loadFailed: 'Kunne ikke hente billeder eller mapper.',
    noneSelected: 'Vælg mindst ét billede først.',
    sending: 'Opdaterer Google Photo Frame…',
    done: 'Google Photo Frame er opdateret.',
    failed: 'Nogle billeder kunne ikke opdateres.',
    limit: 'Der vises op til 220 billeder ad gangen. Brug mapper eller søgning til at indsnævre listen.'
  };

  const esc = value => String(value == null ? '' : value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

  function modal() {
    let el = document.getElementById('gpfPickerModal');
    if (el) return el;
    el = document.createElement('div');
    el.id = 'gpfPickerModal';
    el.className = 'hidden';
    el.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,.62);display:flex;align-items:center;justify-content:center;z-index:13000;padding:14px;';
    el.innerHTML = `
      <div class="photoframe-modal-card" style="width:980px;max-width:96vw;background:var(--panel);border:1px solid var(--border);border-radius:12px;padding:16px;max-height:92vh;overflow:auto;box-shadow:0 24px 70px rgba(0,0,0,.35);">
        <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:12px;margin-bottom:8px;">
          <div>
            <h3 id="gpfPickerTitle" style="margin:0;"></h3>
            <div id="gpfPickerHint" class="mini-label" style="margin-top:5px;"></div>
          </div>
          <button id="gpfPickerClose" class="btn"></button>
        </div>
        <div class="photoframe-scope-toolbar-row" style="margin:12px 0 8px;">
          <button id="gpfPickerSelectVisible" class="btn small" type="button"></button>
          <button id="gpfPickerClear" class="btn small" type="button"></button>
          <div id="gpfPickerSelectedCount" class="mini-label" style="margin-left:auto;"></div>
        </div>
        <div class="mini-label" id="gpfPickerLimit" style="margin-bottom:8px;"></div>
        <div class="photoframe-scope-browser">
          <aside class="photoframe-scope-folders-pane">
            <div id="gpfPickerFoldersLabel" class="mini-label" style="margin-bottom:6px;"></div>
            <div id="gpfPickerFolderNav" class="photoframe-scope-folder-nav"></div>
          </aside>
          <section class="photoframe-scope-photos-pane">
            <div class="toolbar" style="gap:8px;align-items:stretch;margin-bottom:8px;">
              <input id="gpfPickerSearch" class="mapper-input" type="text" style="min-width:0;width:100%;">
              <button id="gpfPickerSearchBtn" class="btn small" type="button"></button>
            </div>
            <div id="gpfPickerPhotos" class="photoframe-scope-thumb-grid"></div>
          </section>
        </div>
        <div id="gpfPickerError" class="mini-label hidden" style="color:#ff6b6b;margin-top:10px;"></div>
        <div style="display:flex;justify-content:flex-end;gap:8px;flex-wrap:wrap;margin-top:14px;">
          <button id="gpfPickerRemove" class="btn" type="button"></button>
          <button id="gpfPickerAdd" class="btn primary" type="button"></button>
        </div>
      </div>`;
    document.body.appendChild(el);

    el.addEventListener('click', event => {
      if (event.target === el || event.target.closest('#gpfPickerClose')) closePicker();
      const folderBtn = event.target.closest('[data-gpf-picker-folder]');
      if (folderBtn) {
        activeFolder = String(folderBtn.dataset.gpfPickerFolder || '');
        renderFolders();
        loadPhotos();
      }
      const photoCard = event.target.closest('[data-gpf-picker-photo]');
      if (photoCard) {
        const id = Number(photoCard.dataset.gpfPickerPhoto || 0);
        if (!id) return;
        if (selected.has(id)) selected.delete(id); else selected.add(id);
        photoCard.classList.toggle('selected', selected.has(id));
        updateSelectedCount();
      }
    });

    document.getElementById('gpfPickerSearchBtn').addEventListener('click', () => {
      searchText = String(document.getElementById('gpfPickerSearch').value || '').trim();
      loadPhotos();
    });
    document.getElementById('gpfPickerSearch').addEventListener('keydown', event => {
      if (event.key === 'Enter') {
        event.preventDefault();
        searchText = String(event.currentTarget.value || '').trim();
        loadPhotos();
      }
    });
    document.getElementById('gpfPickerSelectVisible').addEventListener('click', () => {
      photos.forEach(item => {
        const id = Number(item?.id || 0);
        if (id) selected.add(id);
      });
      renderPhotos();
    });
    document.getElementById('gpfPickerClear').addEventListener('click', () => {
      selected.clear();
      renderPhotos();
    });
    document.getElementById('gpfPickerAdd').addEventListener('click', () => syncSelected('add'));
    document.getElementById('gpfPickerRemove').addEventListener('click', () => syncSelected('remove'));
    return el;
  }

  function setError(message = '') {
    const el = document.getElementById('gpfPickerError');
    if (!el) return;
    el.textContent = String(message || '');
    el.classList.toggle('hidden', !message);
  }

  function updateLabels() {
    const tr = t();
    document.getElementById('gpfPickerTitle').textContent = tr.title;
    document.getElementById('gpfPickerHint').textContent = tr.hint;
    document.getElementById('gpfPickerClose').textContent = tr.close;
    document.getElementById('gpfPickerFoldersLabel').textContent = tr.folders;
    document.getElementById('gpfPickerSearch').placeholder = tr.search;
    document.getElementById('gpfPickerSearchBtn').textContent = tr.searchBtn;
    document.getElementById('gpfPickerSelectVisible').textContent = tr.selectVisible;
    document.getElementById('gpfPickerClear').textContent = tr.clear;
    document.getElementById('gpfPickerAdd').textContent = tr.add;
    document.getElementById('gpfPickerRemove').textContent = tr.remove;
    document.getElementById('gpfPickerLimit').textContent = tr.limit;
    updateSelectedCount();
  }

  function updateSelectedCount() {
    const el = document.getElementById('gpfPickerSelectedCount');
    if (el) el.textContent = t().selected(selected.size);
  }

  async function fetchJson(url, options = {}) {
    const response = await fetch(url, {credentials:'same-origin', ...options});
    const data = await response.json().catch(() => ({}));
    if (!response.ok || data?.ok === false) throw new Error(data?.error || `HTTP ${response.status}`);
    return data;
  }

  async function openPicker() {
    const el = modal();
    folders = [];
    activeFolder = '';
    photos = [];
    selected = new Set();
    searchText = '';
    document.getElementById('gpfPickerSearch').value = '';
    setError('');
    updateLabels();
    el.classList.remove('hidden');
    await loadFolders();
    await loadPhotos();
  }

  function closePicker() {
    document.getElementById('gpfPickerModal')?.classList.add('hidden');
  }

  async function loadFolders() {
    const nav = document.getElementById('gpfPickerFolderNav');
    if (!nav) return;
    nav.innerHTML = `<div class="mini-label">${esc(t().loadingFolders)}</div>`;
    try {
      const data = await fetchJson('/api/photoframes/available-folders');
      folders = Array.isArray(data.items) ? data.items.map(v => String(v || '').trim()).filter(Boolean) : [];
      renderFolders();
    } catch (err) {
      folders = [];
      renderFolders();
      setError(`${t().loadFailed} ${err.message || err}`);
    }
  }

  function folderLabel(path) {
    const clean = String(path || '').replace(/\\/g, '/').replace(/\/$/, '');
    return clean.split('/').filter(Boolean).pop() || clean || t().all;
  }

  function renderFolders() {
    const nav = document.getElementById('gpfPickerFolderNav');
    if (!nav) return;
    const allBtn = `<button type="button" class="photoframe-scope-folder-item${activeFolder === '' ? ' active' : ''}" data-gpf-picker-folder="">
      <div class="photoframe-scope-folder-line is-title"><span class="photoframe-scope-folder-marquee-text">${esc(t().all)}</span></div>
    </button>`;
    const items = folders.map(path => {
      const active = activeFolder === path ? ' active' : '';
      return `<button type="button" class="photoframe-scope-folder-item${active}" data-gpf-picker-folder="${esc(path)}">
        <div class="photoframe-scope-folder-line is-title" title="${esc(folderLabel(path))}"><span class="photoframe-scope-folder-marquee-text">${esc(folderLabel(path))}</span></div>
        <div class="photoframe-scope-folder-line is-sub mini-label" title="${esc(path)}"><span class="photoframe-scope-folder-marquee-text">${esc(path)}</span></div>
      </button>`;
    }).join('');
    nav.innerHTML = allBtn + (items || `<div class="mini-label" style="padding:8px 0;">${esc(t().noFolders)}</div>`);
  }

  async function loadPhotos() {
    if (loading) return;
    loading = true;
    const list = document.getElementById('gpfPickerPhotos');
    if (list) list.innerHTML = `<div class="mini-label">${esc(t().loadingPhotos)}</div>`;
    setError('');
    try {
      const qs = new URLSearchParams({limit:'220'});
      if (activeFolder) qs.set('folder', activeFolder);
      if (searchText) qs.set('q', searchText);
      const data = await fetchJson(`/api/photoframes/available-photos?${qs.toString()}`);
      const raw = Array.isArray(data.items) ? data.items : [];
      photos = raw.filter(item => {
        const rel = String(item?.rel_path || '').toLowerCase();
        const ext = String(item?.ext || rel || '').toLowerCase();
        return !item?.is_video && !['.mp4','.m4v','.mov','.avi','.mkv','.webm','.3gp'].some(s => ext.endsWith(s));
      });
      renderPhotos();
    } catch (err) {
      photos = [];
      renderPhotos();
      setError(`${t().loadFailed} ${err.message || err}`);
    } finally {
      loading = false;
    }
  }

  function renderPhotos() {
    const list = document.getElementById('gpfPickerPhotos');
    if (!list) return;
    if (!photos.length) {
      list.innerHTML = `<div class="mini-label" style="padding:10px 0;">${esc(t().noPhotos)}</div>`;
      updateSelectedCount();
      return;
    }
    list.innerHTML = photos.map(item => {
      const id = Number(item?.id || 0);
      const thumb = String(item?.thumb_url || item?.view_url || '');
      const label = String(item?.filename || item?.name || item?.rel_path || `#${id}`);
      return `<article class="photoframe-scope-photo-card${selected.has(id) ? ' selected' : ''}" data-gpf-picker-photo="${id}" title="${esc(label)}">
        <div class="photoframe-scope-photo-thumb">
          ${thumb ? `<img class="photoframe-scope-photo-img" loading="lazy" decoding="async" src="${esc(thumb)}" alt="">` : `<div class="photoframe-scope-photo-placeholder">—</div>`}
          <span class="photoframe-scope-select-badge">&#10003;</span>
        </div>
        <div class="mini-label" style="padding:5px 2px 0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${esc(label)}</div>
      </article>`;
    }).join('');
    updateSelectedCount();
  }

  async function syncSelected(mode) {
    const ids = Array.from(selected).map(Number).filter(id => Number.isFinite(id) && id > 0);
    if (!ids.length) {
      setError(t().noneSelected);
      return;
    }
    const addBtn = document.getElementById('gpfPickerAdd');
    const removeBtn = document.getElementById('gpfPickerRemove');
    if (addBtn) addBtn.disabled = true;
    if (removeBtn) removeBtn.disabled = true;
    setError('');
    try {
      let failures = 0;
      for (let i = 0; i < ids.length; i += 20) {
        const chunk = ids.slice(i, i + 20);
        const data = await fetchJson(`${API}/photos/${mode}`, {
          method:'POST',
          headers:{'Content-Type':'application/json'},
          body:JSON.stringify({photo_ids:chunk})
        });
        failures += Array.isArray(data.failed) ? data.failed.length : 0;
      }
      if (failures) setError(`${t().failed} (${failures})`);
      else {
        try {
          if (typeof showStatus === 'function') showStatus(t().done, 'ok');
        } catch (_) {}
        closePicker();
      }
      setTimeout(() => document.querySelector('#gpfSection [data-gpf-action="refresh"]')?.click(), 50);
    } catch (err) {
      setError(`${t().failed} ${err.message || err}`);
    } finally {
      if (addBtn) addBtn.disabled = false;
      if (removeBtn) removeBtn.disabled = false;
    }
  }

  // Capture the Google card's choose action before google_photo_frame.js redirects to Mapper.
  document.addEventListener('click', event => {
    const button = event.target.closest('#gpfSection [data-gpf-action="choose"]');
    if (!button) return;
    event.preventDefault();
    event.stopPropagation();
    event.stopImmediatePropagation();
    openPicker();
  }, true);
})();
