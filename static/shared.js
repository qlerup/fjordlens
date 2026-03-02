const els = {
  title: document.getElementById('shareTitle'),
  meta: document.getElementById('shareMeta'),
  status: document.getElementById('shareStatus'),
  authBox: document.getElementById('shareAuthBox'),
  authPassword: document.getElementById('authPassword'),
  authBtn: document.getElementById('authBtn'),
  uploadWrap: document.getElementById('uploadWrap'),
  uploadLabel: document.getElementById('uploadLabel'),
  fileInput: document.getElementById('shareFileInput'),
  uploadBtn: document.getElementById('uploadBtn'),
  deleteBtn: document.getElementById('deleteBtn'),
  grid: document.getElementById('shareGrid'),
};

const state = {
  token: String(window.SHARE_TOKEN || ''),
  info: null,
  items: [],
  selected: new Set(),
};

function t(key) {
  const da = {
    title: 'Delt mappe',
    loading: 'Indlæser…',
    auth_required: 'Adgangskode kræves',
    auth_label: 'Indtast adgangskode',
    auth_continue: 'Fortsæt',
    upload_pick: 'Vælg filer',
    upload_run: 'Upload',
    delete_selected: 'Slet valgte',
    no_files: 'Ingen filer valgt',
    upload_done: 'Upload fuldført',
    upload_failed: 'Upload fejlede',
    delete_done: 'Sletning fuldført',
    delete_failed: 'Sletning fejlede',
    password_failed: 'Forkert adgangskode',
    open: 'Åbn',
    selected: 'valgt',
  };
  const en = {
    title: 'Shared folder',
    loading: 'Loading…',
    auth_required: 'Password required',
    auth_label: 'Enter password',
    auth_continue: 'Continue',
    upload_pick: 'Choose files',
    upload_run: 'Upload',
    delete_selected: 'Delete selected',
    no_files: 'No files selected',
    upload_done: 'Upload completed',
    upload_failed: 'Upload failed',
    delete_done: 'Delete completed',
    delete_failed: 'Delete failed',
    password_failed: 'Wrong password',
    open: 'Open',
    selected: 'selected',
  };
  const lang = (document.documentElement.lang || 'da').toLowerCase().startsWith('en') ? en : da;
  return lang[key] || key;
}

function showStatus(text, type = 'ok') {
  if (!els.status) return;
  els.status.textContent = text;
  els.status.classList.remove('hidden', 'ok', 'err');
  els.status.classList.add(type);
}

function hideStatus() {
  if (!els.status) return;
  els.status.classList.add('hidden');
}

function updateDeleteButton() {
  if (!els.deleteBtn) return;
  const count = state.selected.size;
  els.deleteBtn.disabled = count === 0;
  els.deleteBtn.textContent = count > 0 ? `${t('delete_selected')} (${count})` : t('delete_selected');
}

function renderGrid() {
  if (!els.grid) return;
  els.grid.innerHTML = '';
  state.items.forEach((item) => {
    const card = document.createElement('article');
    card.className = 'photo-card' + (state.selected.has(item.id) ? ' selected' : '');
    const thumb = item.thumb_url
      ? `<div class="card-thumb"><img loading="lazy" src="${item.thumb_url}" alt=""></div>`
      : '<div class="card-thumb placeholder">No thumbnail</div>';
    card.innerHTML = `
      ${thumb}
      <div class="card-body">
        <h4 class="card-title">${(item.filename || '').replace(/</g, '&lt;')}</h4>
        <div class="card-meta" style="display:flex;justify-content:space-between;align-items:center;gap:8px;">
          <button class="btn small" data-open="1">${t('open')}</button>
          <label class="mini-label" style="display:flex;align-items:center;gap:6px;">
            <input type="checkbox" data-check="1" ${state.selected.has(item.id) ? 'checked' : ''} />
            <span>${t('selected')}</span>
          </label>
        </div>
      </div>`;

    const openBtn = card.querySelector('[data-open="1"]');
    const check = card.querySelector('[data-check="1"]');
    if (openBtn) {
      openBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        const url = item.original_url || item.download_url;
        if (url) window.open(url, '_blank', 'noopener');
      });
    }
    if (check) {
      check.addEventListener('change', () => {
        if (check.checked) state.selected.add(item.id);
        else state.selected.delete(item.id);
        updateDeleteButton();
      });
    }
    card.addEventListener('click', () => {
      if (state.selected.has(item.id)) state.selected.delete(item.id);
      else state.selected.add(item.id);
      renderGrid();
      updateDeleteButton();
    });
    els.grid.appendChild(card);
  });
  updateDeleteButton();
}

async function loadInfo() {
  const res = await fetch(`/api/share/${encodeURIComponent(state.token)}/info`);
  const data = await res.json().catch(() => ({}));
  if (res.status === 401 && data && data.password_required) {
    if (els.authBox) els.authBox.classList.remove('hidden');
    if (els.meta) els.meta.textContent = t('auth_required');
    return false;
  }
  if (!res.ok || !data || !data.ok) {
    showStatus((data && data.error) || 'Share error', 'err');
    return false;
  }
  state.info = data;
  if (els.authBox) els.authBox.classList.add('hidden');
  if (els.meta) {
    const perms = data.can_delete ? 'view+upload+delete' : (data.can_upload ? 'view+upload' : 'view');
    els.meta.textContent = `${data.folder_label} · ${perms}`;
  }
  if (els.uploadWrap) els.uploadWrap.style.display = data.can_upload ? '' : 'none';
  if (els.uploadBtn) els.uploadBtn.style.display = data.can_upload ? '' : 'none';
  if (els.deleteBtn) els.deleteBtn.style.display = data.can_delete ? '' : 'none';
  return true;
}

async function loadPhotos() {
  const res = await fetch(`/api/share/${encodeURIComponent(state.token)}/photos`);
  const data = await res.json().catch(() => ({}));
  if (res.status === 401 && data && data.password_required) {
    if (els.authBox) els.authBox.classList.remove('hidden');
    return;
  }
  if (!res.ok || !data || !data.ok) {
    showStatus((data && data.error) || 'Share error', 'err');
    return;
  }
  state.items = data.items || [];
  state.selected = new Set();
  renderGrid();
}

async function runAuth() {
  const password = String((els.authPassword && els.authPassword.value) || '');
  const res = await fetch(`/api/share/${encodeURIComponent(state.token)}/auth`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ password }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok || !data || !data.ok) {
    showStatus((data && data.error) || t('password_failed'), 'err');
    return;
  }
  hideStatus();
  if (els.authPassword) els.authPassword.value = '';
  await boot();
}

async function runUpload() {
  const files = (els.fileInput && els.fileInput.files) ? Array.from(els.fileInput.files) : [];
  if (!files.length) {
    showStatus(t('no_files'), 'err');
    return;
  }
  const fd = new FormData();
  files.forEach((f) => fd.append('files', f));
  const res = await fetch(`/api/share/${encodeURIComponent(state.token)}/upload`, { method: 'POST', body: fd });
  const data = await res.json().catch(() => ({}));
  if (!res.ok || !data || data.ok === false) {
    showStatus((data && data.error) || t('upload_failed'), 'err');
    return;
  }
  showStatus(t('upload_done'), 'ok');
  if (els.fileInput) els.fileInput.value = '';
  await loadPhotos();
}

async function runDelete() {
  const ids = Array.from(state.selected || []);
  if (!ids.length) return;
  const res = await fetch(`/api/share/${encodeURIComponent(state.token)}/delete`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ photo_ids: ids }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok || !data || !data.ok) {
    showStatus((data && data.error) || t('delete_failed'), 'err');
    return;
  }
  showStatus(t('delete_done'), 'ok');
  await loadPhotos();
}

async function boot() {
  hideStatus();
  if (els.title) els.title.textContent = t('title');
  if (els.meta) els.meta.textContent = t('loading');
  if (els.authBtn) els.authBtn.textContent = t('auth_continue');
  if (els.uploadLabel) els.uploadLabel.textContent = t('upload_pick');
  if (els.uploadBtn) els.uploadBtn.textContent = t('upload_run');
  if (els.deleteBtn) els.deleteBtn.textContent = t('delete_selected');

  const ok = await loadInfo();
  if (!ok) return;
  await loadPhotos();
}

if (els.authBtn) els.authBtn.addEventListener('click', runAuth);
if (els.authPassword) {
  els.authPassword.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      runAuth();
    }
  });
}
if (els.uploadBtn) els.uploadBtn.addEventListener('click', runUpload);
if (els.deleteBtn) els.deleteBtn.addEventListener('click', runDelete);

boot();
