(() => {
  'use strict';

  const selected = new Set();
  let folders = [];
  let currentFolder = '';
  let currentItems = [];
  let searchTimer = null;

  const esc = (value) => String(value == null ? '' : value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const isEnglish = () => String(document.documentElement.lang || 'da').toLowerCase().startsWith('en');
  const tr = (da, en) => isEnglish() ? en : da;

  function notify(text, type = 'ok') {
    try {
      if (typeof showStatus === 'function') { showStatus(text, type); return; }
    } catch (_) {}
    console[type === 'err' ? 'error' : 'log'](text);
  }

  function ensureModal() {
    let modal = document.getElementById('gpfPickerModal');
    if (modal) return modal;
    modal = document.createElement('div');
    modal.id = 'gpfPickerModal';
    modal.className = 'gpf-picker hidden';
    modal.innerHTML = `
      <div class="gpf-picker-backdrop" data-gpf-picker-close></div>
      <div class="gpf-picker-card" role="dialog" aria-modal="true" aria-labelledby="gpfPickerTitle">
        <div class="gpf-picker-head">
          <div>
            <h3 id="gpfPickerTitle">${esc(tr('Vælg billeder til Google Photo Frame', 'Choose photos for Google Photo Frame'))}</h3>
            <div class="mini-label">${esc(tr('Vælg en mappe og markér de billeder, der skal vises på Nest Hub.', 'Choose a folder and select the photos to show on Nest Hub.'))}</div>
          </div>
          <button type="button" class="btn" data-gpf-picker-close>×</button>
        </div>
        <div class="gpf-picker-toolbar">
          <div class="gpf-picker-search-wrap">
            <input id="gpfPickerSearch" type="search" placeholder="${esc(tr('Søg i valgt mappe…', 'Search selected folder…'))}" autocomplete="off">
          </div>
          <div id="gpfPickerCount" class="mini-label"></div>
        </div>
        <div id="gpfPickerError" class="gpf-picker-error hidden"></div>
        <div class="gpf-picker-body">
          <aside class="gpf-picker-sidebar">
            <div class="gpf-picker-sidebar-title">${esc(tr('Mapper', 'Folders'))}</div>
            <div id="gpfPickerFolders" class="gpf-picker-folders"></div>
          </aside>
          <main class="gpf-picker-main">
            <div id="gpfPickerLoading" class="mini-label hidden">${esc(tr('Henter billeder…', 'Loading photos…'))}</div>
            <div id="gpfPickerEmpty" class="mini-label hidden">${esc(tr('Ingen billeder i denne mappe.', 'No photos in this folder.'))}</div>
            <div id="gpfPickerPhotos" class="gpf-picker-grid"></div>
          </main>
        </div>
        <div class="gpf-picker-actions">
          <button type="button" class="btn" data-gpf-picker-close>${esc(tr('Annuller', 'Cancel'))}</button>
          <button type="button" class="btn" id="gpfPickerRemove">${esc(tr('Fjern valgte', 'Remove selected'))}</button>
          <button type="button" class="btn primary" id="gpfPickerAdd">${esc(tr('Tilføj valgte', 'Add selected'))}</button>
        </div>
      </div>`;
    document.body.appendChild(modal);
    bindModal(modal);
    return modal;
  }

  function setError(message) {
    const el = document.getElementById('gpfPickerError');
    if (!el) return;
    const text = String(message || '').trim();
    el.textContent = text;
    el.classList.toggle('hidden', !text);
  }

  function updateCount() {
    const count = selected.size;
    const el = document.getElementById('gpfPickerCount');
    if (el) el.textContent = `${count} ${tr('valgt', 'selected')}`;
    const add = document.getElementById('gpfPickerAdd');
    const remove = document.getElementById('gpfPickerRemove');
    if (add) add.disabled = !count;
    if (remove) remove.disabled = !count;
  }

  function closePicker() {
    document.getElementById('gpfPickerModal')?.classList.add('hidden');
  }

  function bindModal(modal) {
    modal.addEventListener('click', (event) => {
      if (event.target.closest('[data-gpf-picker-close]')) {
        closePicker();
        return;
      }
      const folderBtn = event.target.closest('[data-gpf-folder]');
      if (folderBtn) {
        currentFolder = folderBtn.dataset.gpfFolder || '';
        renderFolders();
        loadPhotos();
        return;
      }
      const photoCard = event.target.closest('[data-gpf-photo-id]');
      if (photoCard) {
        const id = Number(photoCard.dataset.gpfPhotoId || 0);
        if (!id) return;
        if (selected.has(id)) selected.delete(id); else selected.add(id);
        photoCard.classList.toggle('selected', selected.has(id));
        updateCount();
        return;
      }
      if (event.target.closest('#gpfPickerAdd')) syncSelected('add');
      if (event.target.closest('#gpfPickerRemove')) syncSelected('remove');
    });

    modal.querySelector('#gpfPickerSearch')?.addEventListener('input', () => {
      clearTimeout(searchTimer);
      searchTimer = setTimeout(() => loadPhotos(), 260);
    });
  }

  function renderFolders() {
    const wrap = document.getElementById('gpfPickerFolders');
    if (!wrap) return;
    if (!folders.length) {
      wrap.innerHTML = `<div class="mini-label">${esc(tr('Ingen mapper fundet.', 'No folders found.'))}</div>`;
      return;
    }
    wrap.innerHTML = folders.map(path => {
      const label = String(path || '').split('/').filter(Boolean).pop() || path;
      const active = path === currentFolder ? ' active' : '';
      return `<button type="button" class="gpf-picker-folder${active}" data-gpf-folder="${esc(path)}" title="${esc(path)}"><span class="gpf-picker-folder-icon">📁</span><span>${esc(label)}</span></button>`;
    }).join('');
  }

  function renderPhotos() {
    const wrap = document.getElementById('gpfPickerPhotos');
    const empty = document.getElementById('gpfPickerEmpty');
    if (!wrap || !empty) return;
    empty.classList.toggle('hidden', currentItems.length > 0);
    wrap.innerHTML = currentItems.map(item => {
      const id = Number(item?.id || 0);
      if (!id) return '';
      const rel = String(item?.rel_path || '');
      const label = String(item?.filename || rel.split('/').pop() || `#${id}`);
      const thumb = String(item?.thumb_url || '');
      const isSelected = selected.has(id);
      return `<article class="photoframe-scope-photo-card gpf-picker-photo${isSelected ? ' selected' : ''}" data-gpf-photo-id="${id}" tabindex="0">
        <div class="photoframe-scope-photo-thumb gpf-picker-thumb">
          ${thumb ? `<img class="photoframe-scope-photo-img" loading="lazy" decoding="async" src="${esc(thumb)}" alt="">` : `<div class="photoframe-scope-photo-placeholder">${esc(tr('Ingen miniature', 'No thumbnail'))}</div>`}
          <span class="photoframe-scope-select-badge">✓</span>
        </div>
        <div class="gpf-picker-photo-label" title="${esc(label)}">${esc(label)}</div>
      </article>`;
    }).join('');
  }

  async function loadFolders() {
    setError('');
    const response = await fetch('/api/photoframes/available-folders', {credentials:'same-origin'});
    const data = await response.json().catch(() => ({}));
    if (!response.ok || !data.ok) throw new Error(data.error || `HTTP ${response.status}`);
    folders = Array.isArray(data.items) ? data.items.map(v => String(v || '').trim()).filter(Boolean) : [];
    if (!currentFolder || !folders.includes(currentFolder)) currentFolder = folders[0] || '';
    renderFolders();
  }

  async function loadPhotos() {
    const loading = document.getElementById('gpfPickerLoading');
    const wrap = document.getElementById('gpfPickerPhotos');
    if (loading) loading.classList.remove('hidden');
    if (wrap) wrap.classList.add('is-loading');
    setError('');
    try {
      const qs = new URLSearchParams();
      qs.set('limit', '220');
      if (currentFolder) qs.set('folder', currentFolder);
      const q = String(document.getElementById('gpfPickerSearch')?.value || '').trim();
      if (q) qs.set('q', q);
      const response = await fetch(`/api/photoframes/available-photos?${qs.toString()}`, {credentials:'same-origin'});
      const data = await response.json().catch(() => ({}));
      if (!response.ok || !data.ok) throw new Error(data.error || `HTTP ${response.status}`);
      const raw = Array.isArray(data.items) ? data.items : [];
      currentItems = raw.filter(item => {
        const rel = String(item?.rel_path || '').toLowerCase();
        const ext = String(item?.ext || rel).toLowerCase();
        return !item?.is_video && !['.mp4','.m4v','.mov','.avi','.mkv','.webm','.3gp'].some(x => ext.endsWith(x));
      });
      renderPhotos();
    } catch (error) {
      currentItems = [];
      renderPhotos();
      setError(error.message || error);
    } finally {
      if (loading) loading.classList.add('hidden');
      if (wrap) wrap.classList.remove('is-loading');
    }
  }

  async function openPicker() {
    const modal = ensureModal();
    selected.clear();
    currentFolder = '';
    currentItems = [];
    const search = modal.querySelector('#gpfPickerSearch');
    if (search) search.value = '';
    updateCount();
    modal.classList.remove('hidden');
    try {
      await loadFolders();
      await loadPhotos();
    } catch (error) {
      setError(error.message || error);
    }
  }

  async function syncSelected(mode) {
    const ids = Array.from(selected);
    if (!ids.length) return;
    const addBtn = document.getElementById('gpfPickerAdd');
    const removeBtn = document.getElementById('gpfPickerRemove');
    if (addBtn) addBtn.disabled = true;
    if (removeBtn) removeBtn.disabled = true;
    setError('');
    let changed = 0;
    let failed = 0;
    try {
      for (let i = 0; i < ids.length; i += 20) {
        const chunk = ids.slice(i, i + 20);
        const response = await fetch(`/api/google-photo-frame/photos/${mode === 'add' ? 'add' : 'remove'}`, {
          method: 'POST',
          credentials: 'same-origin',
          headers: {'Content-Type':'application/json'},
          body: JSON.stringify({photo_ids: chunk}),
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok && response.status !== 207) throw new Error(data.error || `HTTP ${response.status}`);
        changed += Number(mode === 'add' ? data.added || 0 : data.removed || 0);
        failed += Array.isArray(data.failed) ? data.failed.length : 0;
      }
      notify(`${mode === 'add' ? tr('Google Photo Frame opdateret', 'Google Photo Frame updated') : tr('Billeder fjernet fra Google Photo Frame', 'Photos removed from Google Photo Frame')}: ${changed}${failed ? ` · ${failed} ${tr('fejl', 'failed')}` : ''}`, failed ? 'err' : 'ok');
      window.postMessage({type:'fjordlens-google-photo-frame'}, window.location.origin);
      closePicker();
    } catch (error) {
      setError(error.message || error);
      notify(`${tr('Google Photo Frame-fejl', 'Google Photo Frame error')}: ${error.message || error}`, 'err');
    } finally {
      updateCount();
    }
  }

  document.addEventListener('click', (event) => {
    const choose = event.target.closest('#gpfSection [data-gpf-action="choose"]');
    if (!choose) return;
    event.preventDefault();
    event.stopPropagation();
    event.stopImmediatePropagation();
    openPicker();
  }, true);
})();
