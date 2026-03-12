const els = {
  title: document.getElementById('shareTitle'),
  meta: document.getElementById('shareMeta'),
  status: document.getElementById('shareStatus'),
  authBox: document.getElementById('shareAuthBox'),
  authTitle: document.getElementById('authTitle'),
  authNameWrap: document.getElementById('authNameWrap'),
  authNameLabel: document.getElementById('authNameLabel'),
  authName: document.getElementById('authName'),
  authLabel: document.getElementById('authLabel'),
  authPassword: document.getElementById('authPassword'),
  authBtn: document.getElementById('authBtn'),
  uploadWrap: document.getElementById('uploadWrap'),
  uploadLabel: document.getElementById('uploadLabel'),
  fileInput: document.getElementById('shareFileInput'),
  uploadBtn: document.getElementById('uploadBtn'),
  deleteBtn: document.getElementById('deleteBtn'),
  grid: document.getElementById('shareGrid'),
  viewer: document.getElementById('shareViewer'),
  viewerImg: document.getElementById('shareViewerImg'),
  viewerClose: document.getElementById('shareViewerClose'),
  viewerPrev: document.getElementById('shareViewerPrev'),
  viewerNext: document.getElementById('shareViewerNext'),
  viewerTitle: document.getElementById('shareViewerTitle'),
};

const state = {
  token: String(window.SHARE_TOKEN || ''),
  info: null,
  items: [],
  selected: new Set(),
  auth: { passwordRequired: false, nameRequired: false },
  currentPath: '', // relative to share root (e.g. "sub/child")
  visible: [],    // items filtered to currentPath
  viewerIndex: -1,
};

function isMobileShareView() {
  try {
    return window.matchMedia('(max-width: 760px)').matches;
  } catch {
    return false;
  }
}

function openSharedItem(item) {
  const url = item && (item.original_url || item.download_url);
  if (url) window.open(url, '_blank', 'noopener');
}

function t(key) {
  const da = {
    title: 'Delt mappe',
    loading: 'Indlæser…',
    auth_required: 'Adgang kræves',
    auth_title: 'Adgang kræves',
    auth_name_label: 'Dit navn',
    auth_name_placeholder: 'Skriv dit navn',
    auth_password_label: 'Indtast adgangskode',
    auth_password_placeholder: 'Adgangskode',
    auth_name_missing: 'Navn er påkrævet',
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
    auth_required: 'Access required',
    auth_title: 'Access required',
    auth_name_label: 'Your name',
    auth_name_placeholder: 'Enter your name',
    auth_password_label: 'Enter password',
    auth_password_placeholder: 'Password',
    auth_name_missing: 'Name is required',
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
  // Build folder cards and photo cards based on currentPath
  const root = (Array.isArray(state.info && state.info.folder_paths) && state.info.folder_paths[0]) ? String(state.info.folder_paths[0] || '') : '';
  const norm = (rel) => {
    // Map uploads/originals|converted/<path>/<file> → <path>
    let p = String(rel || '').replace(/\\/g, '/');
    if (p.startsWith('uploads/originals/')) p = p.slice('uploads/originals/'.length);
    else if (p.startsWith('uploads/converted/')) p = p.slice('uploads/converted/'.length);
    else if (p.startsWith('uploads/')) p = p.slice('uploads/'.length);
    const parts = p.split('/');
    parts.pop();
    return parts.join('/');
  };
  const relFromRoot = (folder) => {
    const f = String(folder || '').replace(/\\/g, '/');
    return f.startsWith(root + '/') ? f.slice((root + '/').length) : (f === root ? '' : f);
  };

  const items = Array.isArray(state.items) ? state.items : [];
  const byFolder = new Map(); // folderKey -> preview urls (max 4)
  const folderCounts = new Map(); // folderKey -> total items count
  const current = String(state.currentPath || '');
  const includeFolder = (f) => { if (!byFolder.has(f)) byFolder.set(f, []); };
  const incCount = (f) => { folderCounts.set(f, (folderCounts.get(f) || 0) + 1); };
  const immediateChild = (folder) => {
    const base = current ? `${root}/${current}` : root;
    const rel = relFromRoot(folder);
    if (!rel.startsWith(current ? current + '/' : '')) return null;
    const rest = current ? rel.slice(current.length + 1) : rel;
    if (!rest) return null;
    const seg = rest.split('/').filter(Boolean)[0] || null;
    return seg ? (current ? `${current}/${seg}` : seg) : null;
  };

  const directItems = [];
  for (const it of items) {
    const folder = norm(it.rel_path || '');
    const rel = relFromRoot(folder);
    if (rel === current) directItems.push(it);
    const child = immediateChild(folder);
    if (child) {
      includeFolder(child);
      incCount(child);
      try {
        const prev = byFolder.get(child);
        const url = String(it.thumb_url || it.view_url || it.original_url || it.download_url || '');
        if (url && prev.length < 4) prev.push(url);
      } catch {}
    }
  }

  // Render
  els.grid.innerHTML = '';
  // Back button + path label (simple)
  if (current) {
    const back = document.createElement('div');
    back.className = 'mini-label';
    back.style.margin = '4px 0 6px 2px';
    back.innerHTML = `<button class="btn small" id="sharePathBack">Tilbage</button> <span style="opacity:.8">${root}/${current}</span>`;
    els.grid.appendChild(back);
    const btn = back.querySelector('#sharePathBack');
    if (btn) btn.addEventListener('click', () => {
      const parts = current.split('/').filter(Boolean); parts.pop();
      state.currentPath = parts.join('/');
      renderGrid();
    });
  }

  // Folder cards
  const folderKeys = Array.from(byFolder.keys()).sort((a,b)=>a.localeCompare(b,'da-DK'));
  for (const fk of folderKeys) {
    const card = document.createElement('article');
    card.className = 'photo-card folder-card';
    const prev = byFolder.get(fk) || [];
    const thumbs = prev.map(u => `<img src="${u}" alt="">`).join("");
    const count = Number(folderCounts.get(fk) || 0);
    card.innerHTML = `
      <div class="card-thumb folder-mosaic"><div class="folder-grid">${thumbs}</div></div>
      <div class="folder-name-overlay"><span class="folder-name">${(fk.split('/').pop() || fk)}</span><span class="folder-count">${count ? `${count} elementer` : ''}</span></div>
    `;
    card.addEventListener('click', () => { state.currentPath = fk; renderGrid(); });
    els.grid.appendChild(card);
  }

  // Photo cards
  state.visible = directItems.slice();
  state.visible.forEach((item, idx) => {
    const card = document.createElement('article');
    card.className = 'photo-card';
    const thumb = item.thumb_url
      ? `<div class="card-thumb"><img loading="lazy" src="${item.thumb_url}" alt=""></div>`
      : '<div class="card-thumb placeholder">No thumbnail</div>';
    card.innerHTML = `${thumb}`;
    card.addEventListener('click', () => openShareViewer(idx));
    els.grid.appendChild(card);
  });
}

// --- Simple viewer (popup) ---
function openShareViewer(index) {
  if (!els.viewer || !state.visible.length) return;
  const clamp = (i)=> (i+state.visible.length)%state.visible.length;
  state.viewerIndex = clamp(index);
  const it = state.visible[state.viewerIndex];
  els.viewerImg.src = it && (it.original_url || it.view_url || it.download_url || it.thumb_url) || '';
  els.viewerTitle.textContent = String(it && it.filename || '');
  els.viewer.classList.remove('hidden');
}
function closeShareViewer(){ if (els.viewer) els.viewer.classList.add('hidden'); }
function navShareViewer(step){ if (!state.visible.length) return; openShareViewer(state.viewerIndex + step); }

if (els.viewerClose) els.viewerClose.addEventListener('click', closeShareViewer);
if (els.viewerPrev) els.viewerPrev.addEventListener('click', ()=>navShareViewer(-1));
if (els.viewerNext) els.viewerNext.addEventListener('click', ()=>navShareViewer(1));
document.addEventListener('keydown',(e)=>{
  if (els.viewer && els.viewer.classList.contains('hidden')) return;
  if (e.key==='Escape') closeShareViewer();
  if (e.key==='ArrowLeft') navShareViewer(-1);
  if (e.key==='ArrowRight') navShareViewer(1);
});

function applyAuthRequirements(data = {}) {
  const passwordRequired = !!data.password_required;
  const nameRequired = !!data.name_required;
  state.auth = { passwordRequired, nameRequired };
  if (els.authBox) els.authBox.classList.remove('hidden');
  if (els.authTitle) els.authTitle.textContent = t('auth_title');
  if (els.authNameLabel) els.authNameLabel.textContent = t('auth_name_label');
  if (els.authName) els.authName.placeholder = t('auth_name_placeholder');
  if (els.authLabel) els.authLabel.textContent = t('auth_password_label');
  if (els.authPassword) els.authPassword.placeholder = t('auth_password_placeholder');
  if (els.authNameWrap) els.authNameWrap.classList.toggle('hidden', !nameRequired);
  if (els.authPassword && els.authPassword.parentElement) {
    els.authPassword.parentElement.classList.toggle('hidden', !passwordRequired);
  }
}

async function loadInfo() {
  const res = await fetch(`/api/share/${encodeURIComponent(state.token)}/info`);
  const data = await res.json().catch(() => ({}));
  if (res.status === 401 && data && (data.password_required || data.name_required)) {
    applyAuthRequirements(data);
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
    const title = String(data.share_name || data.folder_label || '');
    els.meta.textContent = `${title} · ${perms}`;
  }
  if (els.uploadWrap) els.uploadWrap.style.display = data.can_upload ? '' : 'none';
  if (els.uploadBtn) els.uploadBtn.style.display = data.can_upload ? '' : 'none';
  if (els.deleteBtn) els.deleteBtn.style.display = (data.can_delete && !isMobileShareView()) ? '' : 'none';
  return true;
}

async function loadPhotos() {
  const res = await fetch(`/api/share/${encodeURIComponent(state.token)}/photos`);
  const data = await res.json().catch(() => ({}));
  if (res.status === 401 && data && (data.password_required || data.name_required)) {
    applyAuthRequirements(data);
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
  const visitorName = String((els.authName && els.authName.value) || '').trim();
  const password = String((els.authPassword && els.authPassword.value) || '');
  if (state.auth.nameRequired && !visitorName) {
    showStatus(t('auth_name_missing'), 'err');
    return;
  }
  const res = await fetch(`/api/share/${encodeURIComponent(state.token)}/auth`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ password, visitor_name: visitorName }),
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
  if (els.authTitle) els.authTitle.textContent = t('auth_title');
  if (els.authNameLabel) els.authNameLabel.textContent = t('auth_name_label');
  if (els.authName) els.authName.placeholder = t('auth_name_placeholder');
  if (els.authLabel) els.authLabel.textContent = t('auth_password_label');
  if (els.authPassword) els.authPassword.placeholder = t('auth_password_placeholder');
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
if (els.authName) {
  els.authName.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      runAuth();
    }
  });
}
if (els.uploadBtn) els.uploadBtn.addEventListener('click', runUpload);
if (els.deleteBtn) els.deleteBtn.addEventListener('click', runDelete);

window.addEventListener('resize', () => {
  if (state.info && els.deleteBtn) {
    els.deleteBtn.style.display = (state.info.can_delete && !isMobileShareView()) ? '' : 'none';
  }
  renderGrid();
});

boot();
