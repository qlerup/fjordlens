const els = {
  title: document.getElementById('shareTitle'),
  meta: document.getElementById('shareMeta'),
  status: document.getElementById('shareStatus'),
  blockedTypes: document.getElementById('shareBlockedTypes'),
  blockedTypesList: document.getElementById('shareBlockedTypesList'),
  shareUploadStatus: document.getElementById('shareUploadStatus'),
  shareUploadLabel: document.getElementById('shareUploadLabel'),
  shareUploadPct: document.getElementById('shareUploadPct'),
  shareUploadBar: document.getElementById('shareUploadBar'),
  authBox: document.getElementById('shareAuthBox'),
  authTitle: document.getElementById('authTitle'),
  authNameWrap: document.getElementById('authNameWrap'),
  authNameLabel: document.getElementById('authNameLabel'),
  authName: document.getElementById('authName'),
  authLabel: document.getElementById('authLabel'),
  authPassword: document.getElementById('authPassword'),
  authBtn: document.getElementById('authBtn'),
  uploadWrap: document.getElementById('uploadWrap'),
  pathBackTop: document.getElementById('sharePathBackTop'),
  uploadLabel: document.getElementById('uploadLabel'),
  fileInput: document.getElementById('shareFileInput'),
  uploadBtn: document.getElementById('uploadBtn'),
  downloadBtn: document.getElementById('shareDownloadBtn'),
  deleteBtn: document.getElementById('deleteBtn'),
  moreBtn: document.getElementById('shareMoreBtn'),
  moreMenu: document.getElementById('shareMoreMenu'),
  moreSelectBtn: document.getElementById('shareMenuSelectBtn'),
  moreSelectAllBtn: document.getElementById('shareMenuSelectAllBtn'),
  moreClearBtn: document.getElementById('shareMenuClearBtn'),
  moreDownloadBtn: document.getElementById('shareMenuDownloadBtn'),
  moreDeleteBtn: document.getElementById('shareMenuDeleteBtn'),
  grid: document.getElementById('shareGrid'),
  viewer: document.getElementById('shareViewer'),
  viewerImg: document.getElementById('shareViewerImg'),
  viewerVideo: document.getElementById('shareViewerVideo'),
  viewerVideoPlayBtn: document.getElementById('shareViewerVideoPlayBtn'),
  viewerClose: document.getElementById('shareViewerClose'),
  viewerPrev: document.getElementById('shareViewerPrev'),
  viewerNext: document.getElementById('shareViewerNext'),
  viewerTitle: document.getElementById('shareViewerTitle'),
  viewerMenuBtn: document.getElementById('shareViewerMenuBtn'),
  viewerMenu: document.getElementById('shareViewerMenu'),
  viewerOpenOrig: document.getElementById('shareViewerOpenOrig'),
  viewerDownloadBtn: document.getElementById('shareViewerDownloadBtn'),
  downloadModal: document.getElementById('shareDownloadModal'),
  downloadModalTitle: document.getElementById('shareDownloadModalTitle'),
  downloadModalClose: document.getElementById('shareDownloadModalClose'),
  downloadOptions: document.getElementById('shareDownloadOptions'),
  downloadPrompt: document.getElementById('shareDownloadPrompt'),
  downloadDateLegend: document.getElementById('shareDownloadDateLegend'),
  downloadDateOriginal: document.getElementById('shareDownloadDateOriginal'),
  downloadDateOriginalTitle: document.getElementById('shareDownloadDateOriginalTitle'),
  downloadDateOriginalDesc: document.getElementById('shareDownloadDateOriginalDesc'),
  downloadDateToday: document.getElementById('shareDownloadDateToday'),
  downloadDateTodayTitle: document.getElementById('shareDownloadDateTodayTitle'),
  downloadDateTodayDesc: document.getElementById('shareDownloadDateTodayDesc'),
  downloadConvertedBtn: document.getElementById('shareDownloadConvertedBtn'),
  downloadOriginalBtn: document.getElementById('shareDownloadOriginalBtn'),
  downloadPackagingHint: document.getElementById('shareDownloadPackagingHint'),
  downloadPreparing: document.getElementById('shareDownloadPreparing'),
  downloadPreparingText: document.getElementById('shareDownloadPreparingText'),
  downloadCancelBtn: document.getElementById('shareDownloadCancelBtn'),
  downloadReady: document.getElementById('shareDownloadReady'),
  downloadReadyText: document.getElementById('shareDownloadReadyText'),
  downloadNativeBtn: document.getElementById('shareDownloadNativeBtn'),
  downloadFallbackBtn: document.getElementById('shareDownloadFallbackBtn'),
  downloadReadyClose: document.getElementById('shareDownloadReadyClose'),
  uploadPrepModal: document.getElementById('shareUploadPrepModal'),
  uploadPrepClose: document.getElementById('shareUploadPrepClose'),
  uploadPrepCancel: document.getElementById('shareUploadPrepCancel'),
  uploadPrepContinue: document.getElementById('shareUploadPrepContinue'),
  uploadWarnModal: document.getElementById('shareUploadWarnModal'),
  uploadWarnClose: document.getElementById('shareUploadWarnClose'),
};

const state = {
  token: String(window.SHARE_TOKEN || ''),
  info: null,
  items: [],
  folders: [],
  photosOffset: 0,
  photosTotal: 0,
  photosHasMore: false,
  photosLoading: false,
  ghostCapacity: 0,
  selected: new Set(),
  selectionPulseId: 0,
  auth: { passwordRequired: false, nameRequired: false },
  selectMode: false,
  currentPath: '', // relative to share root (e.g. "sub/child")
  visible: [],    // items filtered to currentPath
  viewerIndex: -1,
  videoAutoplay: false,
  uploadAllowedExtensions: [],
};

let shareLoadObserver = null;
let shareGhostChunkObserver = null;

const uploadProgress = {
  active: false,
  totalFiles: 0,
  totalBytes: 0,
  completedFiles: 0,
  completedBytes: 0,
  failedFiles: 0,
  currentFile: '',
  currentBytes: 0,
};

let uploadProgressHideTimer = null;
let lastResizeIsMobile = isMobileShareView();
let pendingShareFilePicker = null;
let shareUploadTransferHeartbeatTimer = null;
let pendingShareDownloadIds = [];
let preparedShareDownloadFiles = [];
let shareDownloadFallbackIndex = 0;
let shareDownloadController = null;
let shareDownloadBusy = false;

async function setShareUploadTransferState(active) {
  try {
    await fetch(`/api/share/${encodeURIComponent(state.token)}/upload/transfer-state`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ active: !!active }),
    });
  } catch {}
}

function startShareUploadTransferHeartbeat() {
  if (shareUploadTransferHeartbeatTimer) {
    window.clearInterval(shareUploadTransferHeartbeatTimer);
    shareUploadTransferHeartbeatTimer = null;
  }
  setShareUploadTransferState(true).catch(() => {});
  shareUploadTransferHeartbeatTimer = window.setInterval(() => {
    if (!uploadProgress.active) {
      stopShareUploadTransferHeartbeat().catch(() => {});
      return;
    }
    setShareUploadTransferState(true).catch(() => {});
  }, 15000);
}

async function stopShareUploadTransferHeartbeat() {
  if (shareUploadTransferHeartbeatTimer) {
    window.clearInterval(shareUploadTransferHeartbeatTimer);
    shareUploadTransferHeartbeatTimer = null;
  }
  await setShareUploadTransferState(false);
}

function clearUploadProgressHideTimer() {
  if (uploadProgressHideTimer) {
    window.clearTimeout(uploadProgressHideTimer);
    uploadProgressHideTimer = null;
  }
}

function setShareUploadStatusVisible(visible, tone = 'ok') {
  if (!els.shareUploadStatus) return;
  els.shareUploadStatus.classList.remove('err');
  if (tone === 'err') els.shareUploadStatus.classList.add('err');
  els.shareUploadStatus.classList.toggle('hidden', !visible);
}

function renderShareUploadStatus() {
  if (!els.shareUploadLabel || !els.shareUploadPct || !els.shareUploadBar) return;

  const totalFiles = Math.max(0, Number(uploadProgress.totalFiles || 0));
  if (totalFiles <= 0) {
    els.shareUploadLabel.textContent = 'Upload: 0/0';
    els.shareUploadPct.textContent = '0%';
    els.shareUploadBar.style.width = '0%';
    return;
  }

  const totalBytes = Math.max(0, Number(uploadProgress.totalBytes || 0));
  const completedFiles = Math.max(0, Number(uploadProgress.completedFiles || 0));
  const completedBytes = Math.max(0, Number(uploadProgress.completedBytes || 0));
  const currentBytes = Math.max(0, Number(uploadProgress.currentBytes || 0));
  const inProgress = !!uploadProgress.active && completedFiles < totalFiles;
  const currentIndex = inProgress ? Math.min(totalFiles, completedFiles + 1) : Math.min(totalFiles, completedFiles);

  let pct = 0;
  if (totalBytes > 0) {
    const combined = Math.max(0, Math.min(totalBytes, completedBytes + currentBytes));
    pct = Math.round((combined / totalBytes) * 100);
  } else {
    pct = Math.round((Math.max(0, Math.min(totalFiles, completedFiles)) / totalFiles) * 100);
  }
  pct = Math.max(0, Math.min(100, pct));

  let label = `${t('upload_run')}: ${currentIndex}/${totalFiles}`;
  if (inProgress && uploadProgress.currentFile) label += ` - ${uploadProgress.currentFile}`;
  if (!inProgress) {
    label = `Upload: ${Math.min(totalFiles, completedFiles)}/${totalFiles}`;
    if (uploadProgress.failedFiles > 0) label += ` (${uploadProgress.failedFiles} fejl)`;
  }

  els.shareUploadLabel.textContent = label;
  els.shareUploadPct.textContent = `${pct}%`;
  els.shareUploadBar.style.width = `${pct}%`;
}

function startShareUploadProgress(files) {
  const list = Array.isArray(files) ? files : [];
  clearUploadProgressHideTimer();
  uploadProgress.active = true;
  uploadProgress.totalFiles = list.length;
  uploadProgress.totalBytes = list.reduce((sum, f) => sum + Math.max(0, Number((f && f.size) || 0)), 0);
  uploadProgress.completedFiles = 0;
  uploadProgress.completedBytes = 0;
  uploadProgress.failedFiles = 0;
  uploadProgress.currentFile = '';
  uploadProgress.currentBytes = 0;
  setShareUploadStatusVisible(list.length > 0, 'ok');
  renderShareUploadStatus();
}

function markShareUploadCurrentFile(file) {
  uploadProgress.currentFile = String((file && file.name) || '');
  uploadProgress.currentBytes = 0;
  renderShareUploadStatus();
}

function updateShareUploadProgress(bytesUploaded, bytesTotal) {
  const uploaded = Math.max(0, Number(bytesUploaded || 0));
  const total = Math.max(0, Number(bytesTotal || 0));
  uploadProgress.currentBytes = (total > 0) ? Math.min(uploaded, total) : uploaded;
  renderShareUploadStatus();
}

function finishShareUploadFile(file, ok) {
  uploadProgress.completedFiles += 1;
  uploadProgress.completedBytes += Math.max(0, Number((file && file.size) || 0));
  uploadProgress.currentBytes = 0;
  uploadProgress.currentFile = '';
  if (!ok) uploadProgress.failedFiles += 1;
  renderShareUploadStatus();
}

function finishShareUploadProgress() {
  uploadProgress.active = false;
  renderShareUploadStatus();
  const hasErrors = uploadProgress.failedFiles > 0;
  setShareUploadStatusVisible(true, hasErrors ? 'err' : 'ok');
  clearUploadProgressHideTimer();
  uploadProgressHideTimer = window.setTimeout(() => {
    setShareUploadStatusVisible(false, 'ok');
  }, 5000);
}

function isMobileShareView() {
  try {
    return window.matchMedia('(max-width: 760px)').matches;
  } catch {
    return false;
  }
}

function openSharedItem(item) {
  const url = item && (item.original_url || item.view_url || item.thumb_url);
  if (url) window.open(url, '_blank', 'noopener');
}

function t(key) {
  const da = {
    title: 'Delt mappe',
    loading: 'Indl\u00e6ser...',
    auth_required: 'Adgang kr\u00e6ves',
    auth_title: 'Adgang kr\u00e6ves',
    auth_name_label: 'Dit navn',
    auth_name_placeholder: 'Skriv dit navn',
    auth_password_label: 'Indtast adgangskode',
    auth_password_placeholder: 'Adgangskode',
    auth_name_missing: 'Navn er p\u00e5kr\u00e6vet',
    auth_continue: 'Forts\u00e6t',
    upload_pick: 'Upload',
    perms_label: 'Tilladelser',
    perms_view: 'Se',
    perms_view_upload: 'Se og upload',
    perms_view_upload_delete: 'Se, upload og slette',
    perms_download: 'download',
    perms_upload: 'upload',
    perms_upload_download: 'upload',
    perms_delete: 'slette',
    perms_and: 'og',
    upload_run: 'Upload',
    download: 'Download',
    download_selected: 'Download valgte',
    download_title: 'Download',
    download_prompt: 'V\u00e6lg hvad der skal hentes:',
    download_converted: 'Download konverterede',
    download_original: 'Download originale',
    download_date_legend: 'Dato p\u00e5 gemte billeder',
    download_date_original_title: 'Bevar original optagelsesdato',
    download_date_original_desc: 'Billedet placeres ved den dato, hvor det blev taget.',
    download_date_today_title: 'Brug dags dato',
    download_date_today_desc: 'Billedet placeres blandt de nyeste billeder i fotoappen.',
    download_zip_hint: 'Ved flere valg pakkes de som ZIP.',
    download_mobile_hint: 'P\u00e5 mobil pakkes billederne aldrig som ZIP.',
    download_preparing: 'Forbereder download...',
    download_preparing_item: 'Forbereder {current} af {total}...',
    download_receiving: 'Henter fil... {pct}%',
    download_ready_native: 'Billederne er klar. Tryk p\u00e5 \u201cGem i Fotos\u201d, og v\u00e6lg Fotos eller Gem billeder i telefonens delingsmenu.',
    download_ready_fallback: 'Din browser kan ikke sende filer direkte til fotoappen. Hent dem enkeltvis herfra. Direkte deling til Fotos kr\u00e6ver en underst\u00f8ttet browser og HTTPS.',
    download_native: 'Gem i Fotos',
    download_fallback_next: 'Hent billede {current} af {total}',
    download_done: 'Download klar',
    download_shared: 'Billederne blev sendt til telefonens delingsmenu.',
    download_cancelled: 'Download annulleret',
    download_failed: 'Download fejlede',
    download_not_allowed: 'Download er ikke tilladt for dette link.',
    download_none: 'Ingen billeder valgt',
    download_share_cancelled: 'Deling blev annulleret.',
    close: 'Luk',
    cancel: 'Annuller',
    open_view: '\u00c5bn visning',
    video_play: 'Afspil video',
    select_photos: 'V\u00e6lg billeder',
    select_done: 'Afslut v\u00e6lg',
    select_all: 'V\u00e6lg alle',
    clear_selected: 'Fjern valgte',
    delete_selected: 'Slet valgte',
    no_files: 'Ingen filer valgt',
    upload_done: 'Upload fuldf\u00f8rt',
    upload_failed: 'Upload fejlede',
    postprocess_start_failed: 'Efterbehandling kunne ikke starte',
    blocked_file_types: 'Blokerede filtyper',
    blocked_file_types_none: 'Ingen blokerede filtyper',
    blocked_file_types_status: 'Blokeret filtype: {types}. Kun billeder og videoer uploades.',
    blocked_file_types_selected: 'Valgt og blokeret: {types}',
    blocked_file_types_configured: 'Blokeret fra whitelist: {types}',
    delete_done: 'Sletning fuldf\u00f8rt',
    delete_failed: 'Sletning fejlede',
    password_failed: 'Forkert adgangskode',
    back: 'Tilbage',
    open: '\u00c5bn',
    selected: 'valgt',
  };
  const en = {
    title: 'Shared folder',
    loading: 'Loading...',
    auth_required: 'Access required',
    auth_title: 'Access required',
    auth_name_label: 'Your name',
    auth_name_placeholder: 'Enter your name',
    auth_password_label: 'Enter password',
    auth_password_placeholder: 'Password',
    auth_name_missing: 'Name is required',
    auth_continue: 'Continue',
    upload_pick: 'Upload',
    perms_label: 'Permissions',
    perms_view: 'View',
    perms_view_upload: 'View and upload',
    perms_view_upload_delete: 'View, upload and delete',
    perms_download: 'download',
    perms_upload: 'upload',
    perms_upload_download: 'upload',
    perms_delete: 'delete',
    perms_and: 'and',
    upload_run: 'Upload',
    download: 'Download',
    download_selected: 'Download selected',
    download_title: 'Download',
    download_prompt: 'Choose what to download:',
    download_converted: 'Download converted',
    download_original: 'Download originals',
    download_date_legend: 'Date on saved photos',
    download_date_original_title: 'Keep original capture date',
    download_date_original_desc: 'The photo is placed at the date when it was taken.',
    download_date_today_title: 'Use today\u2019s date',
    download_date_today_desc: 'The photo is placed among the newest photos in the photo app.',
    download_zip_hint: 'Multiple selections are packaged as a ZIP.',
    download_mobile_hint: 'On mobile, photos are never packaged as a ZIP.',
    download_preparing: 'Preparing download...',
    download_preparing_item: 'Preparing {current} of {total}...',
    download_receiving: 'Receiving file... {pct}%',
    download_ready_native: 'The files are ready. Tap \u201cSave to Photos\u201d and choose Photos or Save Images in the phone\u2019s share menu.',
    download_ready_fallback: 'Your browser cannot send files directly to the photo app. Download them individually here. Direct sharing to Photos requires a supported browser and HTTPS.',
    download_native: 'Save to Photos',
    download_fallback_next: 'Download photo {current} of {total}',
    download_done: 'Download ready',
    download_shared: 'The files were sent to the phone\u2019s share menu.',
    download_cancelled: 'Download cancelled',
    download_failed: 'Download failed',
    download_not_allowed: 'Downloads are not allowed for this link.',
    download_none: 'No photos selected',
    download_share_cancelled: 'Sharing was cancelled.',
    close: 'Close',
    cancel: 'Cancel',
    open_view: 'Open view',
    video_play: 'Play video',
    select_photos: 'Select photos',
    select_done: 'Finish selecting',
    select_all: 'Select all',
    clear_selected: 'Clear selection',
    delete_selected: 'Delete selected',
    no_files: 'No files selected',
    upload_done: 'Upload completed',
    upload_failed: 'Upload failed',
    postprocess_start_failed: 'Post-processing could not start',
    blocked_file_types: 'Blocked file types',
    blocked_file_types_none: 'No blocked file types',
    blocked_file_types_status: 'Blocked file type: {types}. Only photos and videos are uploaded.',
    blocked_file_types_selected: 'Selected and blocked: {types}',
    blocked_file_types_configured: 'Blocked from whitelist: {types}',
    delete_done: 'Delete completed',
    delete_failed: 'Delete failed',
    password_failed: 'Wrong password',
    back: 'Back',
    open: 'Open',
    selected: 'selected',
  };
  const lang = (document.documentElement.lang || 'da').toLowerCase().startsWith('en') ? en : da;
  return lang[key] || key;
}

async function startShareUploadPostprocess() {
  const res = await fetch(`/api/share/${encodeURIComponent(state.token)}/upload/postprocess`, {
    method: 'POST',
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok || !data || data.ok === false) {
    throw new Error((data && data.error) || t('postprocess_start_failed'));
  }
  return data;
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

function normalizeUploadFileExtension(value) {
  let raw = String(value || '').trim().toLowerCase();
  if (!raw) return '';
  raw = raw.split('?', 1)[0].split('#', 1)[0].replace(/\\/g, '/').trim();
  if (raw.includes('/')) raw = raw.split('/').pop() || '';
  let ext = raw.startsWith('.') ? raw : '';
  if (!ext) {
    const dot = raw.lastIndexOf('.');
    ext = dot >= 0 ? raw.slice(dot) : `.${raw}`;
  }
  return /^\.[a-z0-9]{1,16}$/.test(ext) ? ext : '';
}

function summarizeFileExtensions(files) {
  const counts = new Map();
  (Array.isArray(files) ? files : []).forEach((file) => {
    const ext = normalizeUploadFileExtension(file && file.name ? file.name : '') || 'uden filtype';
    counts.set(ext, (counts.get(ext) || 0) + 1);
  });
  return Array.from(counts.entries())
    .sort((a, b) => String(a[0]).localeCompare(String(b[0])))
    .map(([ext, count]) => count > 1 ? `${ext} (${count})` : ext)
    .join(', ');
}

function applyShareUploadFileTypes(data = {}) {
  const allowed = Array.isArray(data.upload_allowed_extensions)
    ? data.upload_allowed_extensions.map(normalizeUploadFileExtension).filter(Boolean)
    : [];
  state.uploadAllowedExtensions = Array.from(new Set(allowed)).sort();
  const accept = String(data.upload_accept || state.uploadAllowedExtensions.join(',')).trim();
  if (els.fileInput && accept) els.fileInput.accept = accept;
}

function splitShareFilesByAllowed(files) {
  const allowed = new Set(Array.isArray(state.uploadAllowedExtensions) ? state.uploadAllowedExtensions : []);
  if (!allowed.size) return { allowed: files, blocked: [] };
  const pass = [];
  const blocked = [];
  (Array.isArray(files) ? files : []).forEach((file) => {
    const ext = normalizeUploadFileExtension(file && file.name ? file.name : '');
    if (ext && allowed.has(ext)) pass.push(file);
    else blocked.push(file);
  });
  return { allowed: pass, blocked };
}

function renderShareBlockedTypes(blockedFiles = null) {
  if (!els.blockedTypes || !els.blockedTypesList) return;
  const selectedSummary = Array.isArray(blockedFiles) && blockedFiles.length ? summarizeFileExtensions(blockedFiles) : '';
  const configured = state.info && Array.isArray(state.info.upload_blocked_extensions)
    ? state.info.upload_blocked_extensions.map(normalizeUploadFileExtension).filter(Boolean).sort()
    : [];
  if (selectedSummary) {
    els.blockedTypesList.textContent = t('blocked_file_types_selected').replace('{types}', selectedSummary);
    els.blockedTypes.classList.remove('hidden');
    return;
  }
  if (configured.length) {
    els.blockedTypesList.textContent = t('blocked_file_types_configured').replace('{types}', configured.join(', '));
    els.blockedTypes.classList.remove('hidden');
    return;
  }
  els.blockedTypesList.textContent = t('blocked_file_types_none');
  els.blockedTypes.classList.add('hidden');
}

function canDeleteFromShare() {
  return !!(state.info && state.info.can_delete);
}

function canDownloadFromShare() {
  return !!(state.info && state.info.can_download);
}

function canSelectFromShare() {
  return canDownloadFromShare() || canDeleteFromShare();
}

function closeShareMoreMenu() {
  if (!els.moreMenu) return;
  els.moreMenu.classList.remove('open');
  try {
    els.moreMenu.style.position = '';
    els.moreMenu.style.left = '';
    els.moreMenu.style.right = '';
    els.moreMenu.style.top = '';
    els.moreMenu.style.maxWidth = '';
  } catch {}
}

function openShareMoreMenu() {
  if (!els.moreMenu || !els.moreBtn) return;
  els.moreMenu.classList.add('open');
  try {
    const r = els.moreBtn.getBoundingClientRect();
    const vw = Math.max(window.innerWidth || 0, document.documentElement.clientWidth || 0);
    const width = 220;
    const pad = 8;
    let left = r.right - width;
    left = Math.max(pad, Math.min(left, vw - width - pad));
    const top = Math.max(pad, r.bottom + 8);
    els.moreMenu.style.position = 'fixed';
    els.moreMenu.style.left = `${left}px`;
    els.moreMenu.style.right = 'auto';
    els.moreMenu.style.top = `${top}px`;
    els.moreMenu.style.maxWidth = `${width}px`;
  } catch {}
}

function toggleShareMoreMenu() {
  if (!els.moreMenu) return;
  if (els.moreMenu.classList.contains('open')) closeShareMoreMenu();
  else openShareMoreMenu();
}

function closeShareViewerMenu() {
  if (els.viewerMenu) els.viewerMenu.classList.add('hidden');
}

function toggleShareViewerMenu() {
  if (!els.viewerMenu) return;
  els.viewerMenu.classList.toggle('hidden');
}

function setSelectMode(enabled, opts = {}) {
  const on = !!enabled && canSelectFromShare();
  state.selectMode = on;
  if (!on || opts.clearSelection) {
    state.selected = new Set();
    state.selectionPulseId = 0;
  }
  updateDeleteButton();
  if (!opts.skipRender) renderGrid();
}

function syncSelectionToVisible() {
  if (!state.selected || !state.selected.size) return;
  const visibleIds = new Set((state.visible || []).map((it) => Number(it && it.id || 0)).filter((id) => id > 0));
  const next = new Set();
  state.selected.forEach((id) => { if (visibleIds.has(Number(id))) next.add(Number(id)); });
  state.selected = next;
  if (!state.selected.has(Number(state.selectionPulseId || 0))) state.selectionPulseId = 0;
}

function updateDeleteButton() {
  const canDelete = canDeleteFromShare();
  const canDownload = canDownloadFromShare();
  const canSelect = canSelectFromShare();
  const count = state.selected.size;
  if (els.downloadBtn) {
    const showDownload = canDownload && state.selectMode;
    els.downloadBtn.style.display = showDownload ? '' : 'none';
    els.downloadBtn.disabled = count === 0;
    els.downloadBtn.textContent = count > 0 ? `${t('download')} (${count})` : t('download');
  }
  if (els.deleteBtn) {
    const showDelete = canDelete && state.selectMode;
    els.deleteBtn.style.display = showDelete ? '' : 'none';
    els.deleteBtn.disabled = count === 0;
    els.deleteBtn.textContent = count > 0 ? `${t('delete_selected')} (${count})` : t('delete_selected');
  }
  if (els.moreBtn) {
    els.moreBtn.style.display = canSelect ? '' : 'none';
  }
  if (els.moreSelectBtn) {
    els.moreSelectBtn.textContent = state.selectMode ? t('select_done') : t('select_photos');
  }
  if (els.moreSelectAllBtn) {
    const hasVisible = Array.isArray(state.visible) && state.visible.length > 0;
    els.moreSelectAllBtn.disabled = !(canSelect && state.selectMode && hasVisible);
  }
  if (els.moreClearBtn) {
    els.moreClearBtn.disabled = !(canSelect && state.selectMode && count > 0);
  }
  if (els.moreDownloadBtn) {
    els.moreDownloadBtn.style.display = canDownload ? '' : 'none';
    els.moreDownloadBtn.disabled = !(canDownload && state.selectMode && count > 0);
    els.moreDownloadBtn.textContent = count > 0
      ? `${t('download_selected')} (${count})`
      : t('download_selected');
  }
  if (els.moreDeleteBtn) {
    els.moreDeleteBtn.style.display = canDelete ? '' : 'none';
    els.moreDeleteBtn.disabled = !(canDelete && state.selectMode && count > 0);
    els.moreDeleteBtn.textContent = count > 0 ? `${t('delete_selected')} (${count})` : t('delete_selected');
  }
  if (els.pathBackTop) {
    const showBack = !!String(state.currentPath || '').trim();
    els.pathBackTop.style.display = showBack ? '' : 'none';
    els.pathBackTop.disabled = !!state.selectMode;
    els.pathBackTop.textContent = t('back');
  }
}

function isProbablyIosDevice() {
  try {
    const ua = String(navigator.userAgent || '');
    const platform = String(navigator.platform || '');
    return /iPad|iPhone|iPod/.test(ua) || (platform === 'MacIntel' && Number(navigator.maxTouchPoints || 0) > 1);
  } catch {
    return false;
  }
}

function shouldReplaceNativeMediaContextMenu() {
  if (isProbablyIosDevice()) return true;
  try {
    return !!(window.matchMedia && window.matchMedia('(hover: none) and (pointer: coarse)').matches);
  } catch {
    return false;
  }
}

function isMobileDownloadDevice() {
  try {
    if (navigator.userAgentData && typeof navigator.userAgentData.mobile === 'boolean') {
      if (navigator.userAgentData.mobile) return true;
    }
    const ua = String(navigator.userAgent || '');
    if (/Android|webOS|iPhone|iPad|iPod|IEMobile|Opera Mini|Mobile/i.test(ua)) return true;
    if (isProbablyIosDevice()) return true;
    return isMobileShareView() && Number(navigator.maxTouchPoints || 0) > 0;
  } catch {
    return isMobileShareView();
  }
}

function normalizeShareDownloadIds(values) {
  const ids = [];
  const seen = new Set();
  (Array.isArray(values) ? values : []).forEach((raw) => {
    const id = Number(raw || 0);
    if (!Number.isInteger(id) || id <= 0 || seen.has(id)) return;
    seen.add(id);
    ids.push(id);
  });
  return ids;
}

function selectedShareDownloadDateMode() {
  return (els.downloadDateToday && els.downloadDateToday.checked) ? 'today' : 'original';
}

function setShareDownloadStage(stage) {
  if (els.downloadOptions) els.downloadOptions.classList.toggle('hidden', stage !== 'options');
  if (els.downloadPreparing) els.downloadPreparing.classList.toggle('hidden', stage !== 'preparing');
  if (els.downloadReady) els.downloadReady.classList.toggle('hidden', stage !== 'ready');
}

function setShareDownloadPreparingText(text) {
  if (els.downloadPreparingText) els.downloadPreparingText.textContent = String(text || t('download_preparing'));
}

function updateShareDownloadFallbackButton() {
  if (!els.downloadFallbackBtn) return;
  const total = preparedShareDownloadFiles.length;
  const current = Math.min(total, shareDownloadFallbackIndex + 1);
  if (!total || shareDownloadFallbackIndex >= total) {
    els.downloadFallbackBtn.classList.add('hidden');
    els.downloadFallbackBtn.disabled = true;
    return;
  }
  els.downloadFallbackBtn.disabled = false;
  els.downloadFallbackBtn.textContent = t('download_fallback_next')
    .replace('{current}', String(current))
    .replace('{total}', String(total));
}

function resetShareDownloadModalState() {
  preparedShareDownloadFiles = [];
  shareDownloadFallbackIndex = 0;
  if (els.downloadDateOriginal) els.downloadDateOriginal.checked = true;
  if (els.downloadDateToday) els.downloadDateToday.checked = false;
  if (els.downloadNativeBtn) {
    els.downloadNativeBtn.classList.add('hidden');
    els.downloadNativeBtn.disabled = false;
  }
  if (els.downloadFallbackBtn) {
    els.downloadFallbackBtn.classList.add('hidden');
    els.downloadFallbackBtn.disabled = true;
  }
  if (els.downloadReadyText) els.downloadReadyText.textContent = '';
  setShareDownloadPreparingText(t('download_preparing'));
  setShareDownloadStage('options');
}

function openShareDownloadModal(ids) {
  if (!canDownloadFromShare()) {
    showStatus(t('download_not_allowed'), 'err');
    return;
  }
  const normalized = normalizeShareDownloadIds(ids);
  if (!normalized.length) {
    showStatus(t('download_none'), 'err');
    return;
  }
  if (!els.downloadModal || shareDownloadBusy) return;
  pendingShareDownloadIds = normalized;
  resetShareDownloadModalState();
  if (els.downloadPackagingHint) {
    els.downloadPackagingHint.textContent = t(isMobileDownloadDevice() ? 'download_mobile_hint' : 'download_zip_hint');
  }
  els.downloadModal.classList.remove('hidden');
  try { els.downloadConvertedBtn && els.downloadConvertedBtn.focus({ preventScroll: true }); } catch {}
}

function closeShareDownloadModal(options = {}) {
  const shouldAbort = options.abort !== false;
  if (shouldAbort && shareDownloadController) {
    try { shareDownloadController.abort(); } catch {}
  }
  if (els.downloadModal) els.downloadModal.classList.add('hidden');
  pendingShareDownloadIds = [];
  preparedShareDownloadFiles = [];
  shareDownloadFallbackIndex = 0;
  if (!shareDownloadBusy) shareDownloadController = null;
}

function extractShareDownloadFilename(disposition, fallbackName) {
  const raw = String(disposition || '').trim();
  if (!raw) return String(fallbackName || 'download.bin');
  const encoded = raw.match(/filename\*=([^;]+)/i);
  if (encoded && encoded[1]) {
    let value = String(encoded[1]).trim().replace(/^UTF-8''/i, '').replace(/^"(.*)"$/, '$1');
    try { value = decodeURIComponent(value); } catch {}
    if (value) return value;
  }
  const plain = raw.match(/filename="?([^";]+)"?/i);
  return (plain && plain[1]) ? String(plain[1]).trim() : String(fallbackName || 'download.bin');
}

function uniqueShareDownloadFilename(filename, usedNames) {
  const cleaned = String(filename || 'download.bin').replace(/\\/g, '/').split('/').pop() || 'download.bin';
  const dot = cleaned.lastIndexOf('.');
  const stem = dot > 0 ? cleaned.slice(0, dot) : cleaned;
  const suffix = dot > 0 ? cleaned.slice(dot) : '';
  let candidate = cleaned;
  let index = 2;
  while (usedNames.has(candidate.toLowerCase())) {
    candidate = `${stem}_${index}${suffix}`;
    index += 1;
  }
  usedNames.add(candidate.toLowerCase());
  return candidate;
}

function shareDownloadLastModified(res, dateMode) {
  try {
    const values = [
      res.headers.get('X-FjordLens-Captured-At'),
      res.headers.get('last-modified'),
    ];
    for (const value of values) {
      const parsed = Date.parse(String(value || ''));
      if (Number.isFinite(parsed) && parsed > 0) return parsed;
    }
  } catch {}
  return Date.now();
}

function makePreparedShareDownloadFile(blob, filename, type, lastModified) {
  if (typeof File === 'function') {
    return new File([blob], filename, { type, lastModified });
  }
  const fallback = new Blob([blob], { type });
  try { Object.defineProperty(fallback, 'name', { value: filename, configurable: true }); } catch {}
  try { Object.defineProperty(fallback, 'lastModified', { value: lastModified, configurable: true }); } catch {}
  return fallback;
}

function downloadShareBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = String(filename || 'download.bin');
  document.body.appendChild(anchor);
  anchor.click();
  window.setTimeout(() => {
    URL.revokeObjectURL(url);
    anchor.remove();
  }, 1500);
}

async function extractShareDownloadError(res) {
  const fallback = `${t('download_failed')} (HTTP ${Number(res && res.status || 0) || '?'})`;
  if (!res) return fallback;
  try {
    const contentType = String(res.headers.get('content-type') || '').toLowerCase();
    if (contentType.includes('application/json')) {
      const payload = await res.json().catch(() => null);
      return String((payload && (payload.error || payload.message)) || fallback);
    }
    return String((await res.text().catch(() => '')) || '').trim() || fallback;
  } catch {
    return fallback;
  }
}

async function fetchShareDownloadBlob(url, options, onProgress) {
  const res = await fetch(url, options);
  if (!res.ok) return { ok: false, res };
  const totalRaw = Number(res.headers.get('content-length') || 0);
  const total = Number.isFinite(totalRaw) && totalRaw > 0 ? totalRaw : 0;
  if (!res.body || typeof res.body.getReader !== 'function') {
    const blob = await res.blob();
    if (typeof onProgress === 'function') onProgress(blob.size, total || blob.size, 100);
    return { ok: true, res, blob };
  }
  const reader = res.body.getReader();
  const chunks = [];
  let received = 0;
  while (true) {
    const chunk = await reader.read();
    if (chunk.done) break;
    if (!chunk.value || !chunk.value.byteLength) continue;
    chunks.push(chunk.value);
    received += chunk.value.byteLength;
    const pct = total > 0 ? Math.max(0, Math.min(100, Math.round((received / total) * 100))) : null;
    if (typeof onProgress === 'function') onProgress(received, total, pct);
  }
  const blob = new Blob(chunks, { type: res.headers.get('content-type') || 'application/octet-stream' });
  if (typeof onProgress === 'function') onProgress(received, total || received, 100);
  return { ok: true, res, blob };
}

function shareSingleDownloadUrl(photoId, mode, dateMode) {
  const token = encodeURIComponent(state.token);
  const id = encodeURIComponent(String(photoId));
  const params = new URLSearchParams({ mode, date_mode: dateMode });
  return `/api/share/${token}/download/${id}?${params.toString()}`;
}

function canNativeSharePreparedFiles(files) {
  if (!Array.isArray(files) || !files.length) return false;
  if (window.isSecureContext !== true) return false;
  if (!navigator || typeof navigator.share !== 'function' || typeof navigator.canShare !== 'function') return false;
  try { return !!navigator.canShare({ files }); } catch { return false; }
}

function showPreparedShareDownloads() {
  const nativeReady = canNativeSharePreparedFiles(preparedShareDownloadFiles);
  setShareDownloadStage('ready');
  if (els.downloadReadyText) {
    els.downloadReadyText.textContent = t(nativeReady ? 'download_ready_native' : 'download_ready_fallback');
  }
  if (els.downloadNativeBtn) {
    els.downloadNativeBtn.classList.toggle('hidden', !nativeReady);
    els.downloadNativeBtn.disabled = !nativeReady;
  }
  if (els.downloadFallbackBtn) {
    els.downloadFallbackBtn.classList.toggle('hidden', nativeReady);
  }
  updateShareDownloadFallbackButton();
  if (!nativeReady && els.downloadFallbackBtn) els.downloadFallbackBtn.classList.remove('hidden');
}

async function startShareDownload(modeValue) {
  if (!canDownloadFromShare()) {
    showStatus(t('download_not_allowed'), 'err');
    closeShareDownloadModal();
    return;
  }
  const ids = normalizeShareDownloadIds(pendingShareDownloadIds);
  if (!ids.length) {
    showStatus(t('download_none'), 'err');
    return;
  }
  if (shareDownloadBusy) return;
  const mode = String(modeValue || '').toLowerCase() === 'original' ? 'original' : 'converted';
  const dateMode = selectedShareDownloadDateMode();
  const mobile = isMobileDownloadDevice();
  shareDownloadBusy = true;
  shareDownloadController = new AbortController();
  setShareDownloadStage('preparing');
  setShareDownloadPreparingText(t('download_preparing'));

  try {
    if (mobile) {
      const files = [];
      const usedNames = new Set();
      for (let index = 0; index < ids.length; index += 1) {
        const current = index + 1;
        const prefix = t('download_preparing_item')
          .replace('{current}', String(current))
          .replace('{total}', String(ids.length));
        setShareDownloadPreparingText(prefix);
        const result = await fetchShareDownloadBlob(
          shareSingleDownloadUrl(ids[index], mode, dateMode),
          { method: 'GET', cache: 'no-store', signal: shareDownloadController.signal },
          (_received, _total, pct) => {
            if (pct == null) return;
            setShareDownloadPreparingText(`${prefix} ${pct}%`);
          },
        );
        if (!result.ok) throw new Error(await extractShareDownloadError(result.res));
        const fallbackName = `photo_${ids[index]}`;
        const rawName = extractShareDownloadFilename(result.res.headers.get('content-disposition'), fallbackName);
        const filename = uniqueShareDownloadFilename(rawName, usedNames);
        const type = result.blob.type || result.res.headers.get('content-type') || 'application/octet-stream';
        files.push(makePreparedShareDownloadFile(
          result.blob,
          filename,
          type,
          shareDownloadLastModified(result.res, dateMode),
        ));
      }
      preparedShareDownloadFiles = files;
      shareDownloadFallbackIndex = 0;
      showPreparedShareDownloads();
      return;
    }

    const isSingle = ids.length === 1;
    const url = isSingle
      ? shareSingleDownloadUrl(ids[0], mode, dateMode)
      : `/api/share/${encodeURIComponent(state.token)}/download-zip`;
    const options = isSingle
      ? { method: 'GET', cache: 'no-store', signal: shareDownloadController.signal }
      : {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ photo_ids: ids, mode, date_mode: dateMode }),
          signal: shareDownloadController.signal,
        };
    const result = await fetchShareDownloadBlob(url, options, (_received, _total, pct) => {
      if (pct == null) return;
      setShareDownloadPreparingText(t('download_receiving').replace('{pct}', String(pct)));
    });
    if (!result.ok) throw new Error(await extractShareDownloadError(result.res));
    const fallbackName = isSingle ? `photo_${ids[0]}` : `fjordlens_download_${ids.length}.zip`;
    const filename = extractShareDownloadFilename(result.res.headers.get('content-disposition'), fallbackName);
    downloadShareBlob(result.blob, filename);
    closeShareDownloadModal({ abort: false });
    showStatus(`${t('download_done')}: ${filename}`, 'ok');
  } catch (err) {
    const aborted = !!(err && (err.name === 'AbortError' || String(err.message || '').toLowerCase().includes('aborted')));
    if (aborted) {
      showStatus(t('download_cancelled'), 'ok');
    } else {
      setShareDownloadStage('options');
      showStatus(`${t('download_failed')}${err && err.message ? `: ${String(err.message)}` : ''}`, 'err');
    }
  } finally {
    shareDownloadBusy = false;
    shareDownloadController = null;
  }
}

async function sharePreparedDownloadsNatively() {
  const files = preparedShareDownloadFiles.slice();
  if (!canNativeSharePreparedFiles(files)) {
    showPreparedShareDownloads();
    return;
  }
  if (els.downloadNativeBtn) els.downloadNativeBtn.disabled = true;
  try {
    // Keep this call before the first await: Web Share requires fresh user activation.
    const shareResult = navigator.share({ files });
    await shareResult;
    closeShareDownloadModal({ abort: false });
    showStatus(t('download_shared'), 'ok');
  } catch (err) {
    const cancelled = !!(err && err.name === 'AbortError');
    if (cancelled) {
      if (els.downloadReadyText) els.downloadReadyText.textContent = t('download_share_cancelled');
    } else {
      if (els.downloadReadyText) els.downloadReadyText.textContent = t('download_ready_fallback');
      if (els.downloadNativeBtn) els.downloadNativeBtn.classList.add('hidden');
      if (els.downloadFallbackBtn) els.downloadFallbackBtn.classList.remove('hidden');
      updateShareDownloadFallbackButton();
    }
  } finally {
    if (els.downloadNativeBtn) els.downloadNativeBtn.disabled = false;
  }
}

function downloadNextPreparedShareFile() {
  const index = shareDownloadFallbackIndex;
  const file = preparedShareDownloadFiles[index];
  if (!file) {
    updateShareDownloadFallbackButton();
    return;
  }
  downloadShareBlob(file, file.name || `photo_${index + 1}`);
  shareDownloadFallbackIndex += 1;
  updateShareDownloadFallbackButton();
  if (shareDownloadFallbackIndex >= preparedShareDownloadFiles.length) {
    if (els.downloadReadyText) els.downloadReadyText.textContent = t('download_done');
    showStatus(t('download_done'), 'ok');
  }
}

function shouldShowUploadPrepNotice() {
  return isMobileShareView() || isProbablyIosDevice();
}

function closeUploadPrepModal() {
  pendingShareFilePicker = null;
  if (els.uploadPrepModal) els.uploadPrepModal.classList.add('hidden');
}

function showUploadPrepModal(onContinue) {
  if (!els.uploadPrepModal) {
    if (typeof onContinue === 'function') onContinue();
    return;
  }
  pendingShareFilePicker = (typeof onContinue === 'function') ? onContinue : null;
  els.uploadPrepModal.classList.remove('hidden');
  try { els.uploadPrepContinue && els.uploadPrepContinue.focus({ preventScroll: true }); } catch {}
}

function continueUploadPrepModal() {
  const fn = pendingShareFilePicker;
  pendingShareFilePicker = null;
  if (els.uploadPrepModal) els.uploadPrepModal.classList.add('hidden');
  if (typeof fn === 'function') fn();
}

function openShareFilePicker(skipPrepNotice = false) {
  if (!els.fileInput) return;
  if (!skipPrepNotice && shouldShowUploadPrepNotice()) {
    showUploadPrepModal(() => openShareFilePicker(true));
    return;
  }
  els.fileInput.value = '';
  try {
    if (typeof els.fileInput.showPicker === 'function') {
      els.fileInput.showPicker();
      return;
    }
    els.fileInput.click();
  } catch {
    showStatus('Kunne ikke åbne filvælger.', 'err');
  }
}

function showUploadWarningModal() {
  if (!els.uploadWarnModal) return;
  els.uploadWarnModal.classList.remove('hidden');
}

function closeUploadWarningModal() {
  if (!els.uploadWarnModal) return;
  els.uploadWarnModal.classList.add('hidden');
}

function renderGrid() {
  if (!els.grid) return;
  // Build folder cards and photo cards based on currentPath
  // If multiple folders are shared, treat a virtual root so we only show folders at top-level
  let root = '';
  try {
    const fps = (state.info && Array.isArray(state.info.folder_paths)) ? state.info.folder_paths : [];
    const count = Number((state.info && (state.info.folder_count != null ? state.info.folder_count : fps.length)) || 0);
    root = (count <= 1 && fps.length) ? String(fps[0] || '') : '';
  } catch { root = ''; }
  const norm = (rel) => {
    // Map uploads/originals|converted/<path>/<file> -> <path>
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
        const url = String(it.thumb_url || it.view_url || it.original_url || '');
        if (url && prev.length < 4) prev.push(url);
      } catch {}
    }
  }
  for (const folder of (state.folders || [])) {
    const path = String(folder && folder.path || '');
    if (!path) continue;
    byFolder.set(path, Array.isArray(folder.previews) ? folder.previews.slice(0, 4) : []);
    folderCounts.set(path, Number(folder.count || 0));
  }

  // Render
  els.grid.innerHTML = '';
  // Upload tile (always visible when share allows upload)
  try {
    if (state.info && state.info.can_upload && !state.selectMode) {
      const up = document.createElement('article');
      up.className = 'photo-card upload-card';
      up.innerHTML = `<div class="card-thumb"><div class="upload-plus" aria-label="${t('upload_pick')}">+</div></div>`;
      up.addEventListener('click', () => openShareFilePicker());
      els.grid.appendChild(up);
    }
  } catch {}

  // Folder cards
  const folderKeys = Array.from(byFolder.keys()).sort((a,b)=>a.localeCompare(b,'da-DK'));
  for (const fk of folderKeys) {
    const card = document.createElement('article');
    card.className = 'photo-card folder-card';
    const prev = byFolder.get(fk) || [];
    const shuffled = (a) => { const b = a.slice(); for (let i=b.length-1;i>0;i--){const j=Math.floor(Math.random()*(i+1)); [b[i],b[j]]=[b[j],b[i]];} return b; };
    const uniq = []; const seen = new Set(); for (const u of shuffled(prev)) { if (u && !seen.has(u)) { seen.add(u); uniq.push(u); } }
    const STORE_KEY = 'fl_folder_previews_v1';
    const loadStore = () => { try { return JSON.parse(localStorage.getItem(STORE_KEY) || '{}') || {}; } catch { return {}; } };
    const saveStore = (obj) => { try { localStorage.setItem(STORE_KEY, JSON.stringify(obj)); } catch {} };
    const store = loadStore();
    const stored = Array.isArray(store[fk]) ? store[fk] : null;
    const intersect = (want, avail) => want.filter(u => avail.includes(u));
    const desired = () => (uniq.length === 1 ? 1 : ((uniq.length === 2 || uniq.length === 3) ? 2 : 4));
    let variant = 'v4';
    let useUrls = [];
    const pickFresh = () => {
      if (uniq.length <= 0) return [];
      if (uniq.length === 1) { variant='v1'; return [uniq[0]]; }
      if (uniq.length === 2 || uniq.length === 3) { variant='v2'; return uniq.slice(0,2); }
      variant='v4'; return uniq.slice(0,4);
    };
    if (stored && stored.length) {
      const cand = intersect(stored, uniq);
      if (cand.length >= desired()) {
        useUrls = cand.slice(0, desired());
        variant = (useUrls.length === 1 ? 'v1' : (useUrls.length === 2 ? 'v2' : 'v4'));
      } else {
        useUrls = pickFresh();
        store[fk] = useUrls; saveStore(store);
      }
    } else {
      useUrls = pickFresh();
      store[fk] = useUrls; saveStore(store);
    }
    const thumbs = useUrls.map(u => `<img src="${u}" alt="">`).join("");
    const count = Number(folderCounts.get(fk) || 0);
    const title = (fk.split('/').pop() || fk);
    card.innerHTML = `
      <div class="card-thumb folder-mosaic"><div class="folder-grid ${variant}">${thumbs}</div></div>
      <div class="folder-name-overlay"><span class="folder-name"><span class="scroll">${title}</span></span><span class="folder-count">${count ? `${count} elementer` : ''}</span></div>
    `;
    // Hover marquee for long folder names (same logic as app.js)
    try {
      const nameEl = card.querySelector('.folder-name');
      const inner = nameEl ? nameEl.querySelector('.scroll') : null;
      if (nameEl && inner) {
        nameEl.setAttribute('title', String(title||''));
        const startMarquee = () => {
          try {
            const prev = inner.style.display;
            inner.style.display = 'inline-block';
            const delta = Math.max(0, inner.scrollWidth - nameEl.clientWidth);
            if (delta <= 4) return;
            nameEl.classList.add('marquee');
            let x = 0; let lastTs = 0; const speed = 60;
            const step = (ts) => {
              if (!nameEl.classList.contains('marquee')) return;
              if (!lastTs) { lastTs = ts; }
              const dt = Math.max(0, (ts - lastTs)/1000); lastTs = ts;
              x -= speed * dt; if (-x >= delta) x = 0;
              inner.style.transform = `translateX(${x}px)`;
              nameEl.__raf = window.requestAnimationFrame(step);
            };
            cancelMarquee();
            nameEl.__raf = window.requestAnimationFrame(step);
          } catch {}
        };
        const cancelMarquee = () => {
          try { if (nameEl.__raf) { window.cancelAnimationFrame(nameEl.__raf); nameEl.__raf = null; } } catch {}
          try { inner.style.transform = ''; } catch {}
          try { inner.style.display = ''; } catch {}
          nameEl.classList.remove('marquee');
        };
        const onEnter = () => startMarquee();
        const onLeave = () => cancelMarquee();
        card.addEventListener('mouseenter', onEnter);
        card.addEventListener('mouseleave', onLeave);
        card.addEventListener('mouseover', onEnter, { passive: true });
      }
    } catch {}
    card.addEventListener('click', async () => {
      if (state.selectMode) return;
      state.currentPath = fk;
      await loadPhotos(false);
    });
    els.grid.appendChild(card);
  }

  // Photo cards
  state.visible = directItems.slice();
  syncSelectionToVisible();
  state.visible.forEach((item, idx) => {
    const photoId = Number(item && item.id ? item.id : 0);
    const isSelected = !!(state.selectMode && photoId > 0 && state.selected.has(photoId));
    const shouldAnimateSelection = !!(isSelected && photoId > 0 && Number(state.selectionPulseId || 0) === photoId);
    const card = document.createElement('article');
    card.className = `photo-card${isSelected ? ' selected' : ''}${shouldAnimateSelection ? ' just-selected' : ''}`;
    if (photoId > 0) card.setAttribute('data-photo-id', String(photoId));
    const thumb = item.thumb_url
      ? `<div class="card-thumb"><img loading="auto" decoding="async" src="${item.thumb_url}" alt=""></div>`
      : '<div class="card-thumb placeholder">No thumbnail</div>';
    const selectBadge = canSelectFromShare() ? `<span class="photo-select-badge">${isSelected ? '&#10003;' : ''}</span>` : '';
    const uploader = String(item && item.uploaded_by ? item.uploaded_by : '').trim();
    const uploaderTag = uploader ? `<div class="uploader-badge" title="Uploadet af ${uploader}">${uploader}</div>` : '';
    card.innerHTML = `${thumb}${selectBadge}${uploaderTag}`;
    let longPressTimer = null;
    let longPressActivated = false;
    let longPressStartX = null;
    let longPressStartY = null;
    const activateLongPressSelection = () => {
      if (!canSelectFromShare() || state.selectMode || photoId <= 0) return;
      longPressTimer = null;
      longPressActivated = true;
      setSelectMode(true, { skipRender: true });
      state.selectionPulseId = photoId;
      state.selected.add(photoId);
      renderGrid();
    };
    const startLongPress = (ev) => {
      if (!canSelectFromShare() || state.selectMode || photoId <= 0) return;
      if (ev && ev.type === 'mousedown' && Number(ev.button) !== 0) return;
      const touch = ev && ev.touches && ev.touches[0];
      longPressStartX = touch ? touch.clientX : Number(ev && ev.clientX || 0);
      longPressStartY = touch ? touch.clientY : Number(ev && ev.clientY || 0);
      longPressActivated = false;
      longPressTimer = window.setTimeout(() => {
        activateLongPressSelection();
      }, 550);
    };
    const cancelLongPress = () => {
      if (longPressTimer) window.clearTimeout(longPressTimer);
      longPressTimer = null;
      longPressStartX = null;
      longPressStartY = null;
    };
    const cancelLongPressOnMove = (ev) => {
      if (!longPressTimer || longPressStartX === null || longPressStartY === null) return;
      const touch = ev && ev.touches && ev.touches[0];
      if (!touch) return;
      if (Math.abs(touch.clientX - longPressStartX) > 10 || Math.abs(touch.clientY - longPressStartY) > 10) {
        cancelLongPress();
      }
    };
    card.addEventListener('mousedown', startLongPress);
    card.addEventListener('touchstart', startLongPress, { passive: true });
    card.addEventListener('touchmove', cancelLongPressOnMove, { passive: true });
    ['mouseup', 'mouseleave', 'touchend', 'touchcancel'].forEach((ev) => card.addEventListener(ev, cancelLongPress));
    card.addEventListener('contextmenu', (ev) => {
      // iOS viser ellers sin egen menu med bl.a. "Kopiér link" og "Gem".
      if (!shouldReplaceNativeMediaContextMenu()) return;
      ev.preventDefault();
      ev.stopPropagation();
      cancelLongPress();
      activateLongPressSelection();
    });
    card.addEventListener('dragstart', (ev) => ev.preventDefault());
    const cardImage = card.querySelector('img');
    if (cardImage) cardImage.setAttribute('draggable', 'false');

    card.addEventListener('click', (ev) => {
      if (longPressActivated) {
        longPressActivated = false;
        ev.preventDefault();
        ev.stopPropagation();
        return;
      }
      if (state.selectMode && canSelectFromShare()) {
        if (photoId > 0) {
          if (state.selected.has(photoId)) {
            state.selected.delete(photoId);
            if (Number(state.selectionPulseId || 0) === photoId) state.selectionPulseId = 0;
          } else {
            state.selected.add(photoId);
            state.selectionPulseId = photoId;
          }
        }
        updateDeleteButton();
        renderGrid();
        ev.preventDefault();
        ev.stopPropagation();
        return;
      }
      openShareViewer(idx);
    });
    els.grid.appendChild(card);
  });
  appendShareGhostSlots(state.items.length, state.ghostCapacity);
  setupShareGhostLoading();
  updateDeleteButton();
  state.selectionPulseId = 0;
}

function estimateShareColumns() {
  try {
    const style = getComputedStyle(els.grid);
    const tracks = String(style.gridTemplateColumns || '').split(/\s+/).filter((value) => parseFloat(value) > 0);
    return Math.max(1, tracks.length || (window.innerWidth <= 760 ? 2 : 6));
  } catch {
    return window.innerWidth <= 760 ? 2 : 6;
  }
}

function appendShareGhostSlots(fromIndex, toIndex) {
  if (!els.grid) return;
  const fragment = document.createDocumentFragment();
  for (let index = fromIndex; index < toIndex; index += 1) {
    const ghost = document.createElement('article');
    ghost.className = 'photo-card mapper-ghost-card share-ghost-card';
    ghost.setAttribute('aria-hidden', 'true');
    ghost.dataset.shareIndex = String(index);
    ghost.innerHTML = '<div class="card-thumb mapper-ghost-thumb"></div>';
    fragment.appendChild(ghost);
  }
  els.grid.appendChild(fragment);
}

function syncShareCardSelection(card, photoId) {
  const selected = state.selectMode && state.selected.has(photoId);
  card.classList.toggle('selected', selected);
  const badge = card.querySelector('.photo-select-badge');
  if (badge) badge.innerHTML = selected ? '&#10003;' : '';
  updateDeleteButton();
}

function createHydratedShareCard(item, index) {
  const photoId = Number(item && item.id || 0);
  const card = document.createElement('article');
  card.className = `photo-card${state.selectMode && state.selected.has(photoId) ? ' selected' : ''}`;
  card.dataset.shareIndex = String(index);
  if (photoId > 0) card.dataset.photoId = String(photoId);
  const thumb = item.thumb_url
    ? `<div class="card-thumb"><img loading="lazy" decoding="async" src="${item.thumb_url}" alt=""></div>`
    : '<div class="card-thumb placeholder">No thumbnail</div>';
  const badge = canSelectFromShare() ? '<span class="photo-select-badge"></span>' : '';
  const uploader = String(item && item.uploaded_by || '').trim();
  const uploaderTag = uploader ? `<div class="uploader-badge">${uploader}</div>` : '';
  card.innerHTML = `${thumb}${badge}${uploaderTag}`;
  syncShareCardSelection(card, photoId);

  let longPress = null;
  let longPressActivated = false;
  const cancelLongPress = () => { if (longPress) clearTimeout(longPress); longPress = null; };
  const startLongPress = () => {
    if (!canSelectFromShare() || state.selectMode || photoId <= 0) return;
    cancelLongPress();
    longPressActivated = false;
    longPress = window.setTimeout(() => {
      longPressActivated = true;
      state.selectMode = true;
      state.selected.add(photoId);
      syncShareCardSelection(card, photoId);
    }, 550);
  };
  card.addEventListener('touchstart', startLongPress, { passive: true });
  card.addEventListener('mousedown', startLongPress);
  ['touchmove', 'touchend', 'touchcancel', 'mouseup', 'mouseleave'].forEach((name) => card.addEventListener(name, cancelLongPress, { passive: true }));
  card.addEventListener('click', (event) => {
    if (longPressActivated) {
      longPressActivated = false;
      event.preventDefault();
      return;
    }
    if (state.selectMode && canSelectFromShare()) {
      if (state.selected.has(photoId)) state.selected.delete(photoId); else state.selected.add(photoId);
      syncShareCardSelection(card, photoId);
      event.preventDefault();
      return;
    }
    openShareViewer(index);
  });
  return card;
}

function hydrateShareItems(startIndex, items) {
  if (!els.grid) return;
  items.forEach((item, offset) => {
    const index = startIndex + offset;
    const ghost = els.grid.querySelector(`.share-ghost-card[data-share-index="${index}"]`);
    if (ghost) ghost.replaceWith(createHydratedShareCard(item, index));
  });
  state.visible = state.items.slice();
}

function expandShareGhostChunk() {
  const cols = estimateShareColumns();
  const next = Math.min(state.photosTotal, state.ghostCapacity + (cols * 50));
  if (next <= state.ghostCapacity) return;
  const startIndex = state.ghostCapacity;
  appendShareGhostSlots(startIndex, next);
  state.ghostCapacity = next;
  hydrateShareItems(startIndex, state.items.slice(startIndex, next));
  setupShareGhostLoading();
}

function setupShareGhostLoading() {
  try { if (shareLoadObserver) shareLoadObserver.disconnect(); } catch {}
  try { if (shareGhostChunkObserver) shareGhostChunkObserver.disconnect(); } catch {}
  if (!els.grid) return;
  const cols = estimateShareColumns();
  const firstGhost = els.grid.querySelector(`.share-ghost-card[data-share-index="${state.items.length}"]`);
  if (firstGhost && state.photosHasMore && 'IntersectionObserver' in window) {
    const cardWidth = firstGhost.getBoundingClientRect().width || 180;
    shareLoadObserver = new IntersectionObserver((entries) => {
      if (entries.some((entry) => entry.isIntersecting) && !state.photosLoading) loadPhotos(false, true);
    }, { rootMargin: `${Math.ceil(cardWidth * 5)}px 0px` });
    shareLoadObserver.observe(firstGhost);
  }
  if (state.ghostCapacity < state.photosTotal && 'IntersectionObserver' in window) {
    const triggerIndex = Math.max(0, state.ghostCapacity - (cols * 40));
    const trigger = els.grid.querySelector(`[data-share-index="${triggerIndex}"]`);
    if (trigger) {
      shareGhostChunkObserver = new IntersectionObserver((entries) => {
        if (entries.some((entry) => entry.isIntersecting)) expandShareGhostChunk();
      });
      shareGhostChunkObserver.observe(trigger);
    }
  }
}

function navigateShareBackPath() {
  if (state.selectMode) return;
  const current = String(state.currentPath || '').trim();
  if (!current) return;
  const parts = current.split('/').filter(Boolean);
  parts.pop();
  state.currentPath = parts.join('/');
  loadPhotos(false);
}

// --- Simple viewer (popup) ---
let shareViewerVideoManualPlayRequired = false;
let shareViewerVideoSourceGeneration = 0;
const shareViewerMediaPreloader = (window.FjordLensMediaPreloader && typeof window.FjordLensMediaPreloader.create === 'function')
  ? window.FjordLensMediaPreloader.create({ ahead: 10, behind: 10 })
  : { update() {}, clear() {} };
const shareViewerImagePresenter = window.FjordLensMediaPreloader.createImagePresenter({
  getNode: () => els.viewerImg,
  setNode: (node) => { els.viewerImg = node; },
  preloader: shareViewerMediaPreloader,
});
const shareViewerPager = window.FjordLensMediaPreloader.createViewerPager({
  getItems: () => state.visible,
  getIndex: () => state.viewerIndex,
  hasMore: () => state.photosHasMore,
  loadMore: () => loadPhotos(false, true),
  getContext: () => JSON.stringify([state.token, state.currentPath, shareViewerVideoSourceGeneration]),
  isOpen: () => !!els.viewer && !els.viewer.classList.contains('hidden'),
  onUpdate: () => shareViewerMediaPreloader.update(state.visible, state.viewerIndex),
});

function isShareViewerVideoActive() {
  if (!els.viewer || !els.viewerVideo || els.viewer.classList.contains('hidden')) return false;
  if (els.viewerVideo.style.display === 'none') return false;
  const item = state.visible[state.viewerIndex];
  return !!(item && item.is_video);
}

function setShareViewerVideoPlayOverlayVisible(visible) {
  if (!els.viewerVideoPlayBtn) return;
  els.viewerVideoPlayBtn.classList.toggle('hidden', !visible);
}

function syncShareViewerVideoPlayOverlay() {
  const paused = !!(els.viewerVideo && (els.viewerVideo.paused || els.viewerVideo.ended));
  const needsButton = !state.videoAutoplay || shareViewerVideoManualPlayRequired;
  setShareViewerVideoPlayOverlayVisible(isShareViewerVideoActive() && paused && needsButton);
}

async function playActiveShareViewerVideo(generation = shareViewerVideoSourceGeneration) {
  if (!isShareViewerVideoActive() || !els.viewerVideo) return false;
  try {
    const result = els.viewerVideo.play();
    if (result && typeof result.then === 'function') await result;
    if (generation !== shareViewerVideoSourceGeneration) return false;
    shareViewerVideoManualPlayRequired = false;
    syncShareViewerVideoPlayOverlay();
    return true;
  } catch (_) {
    if (generation !== shareViewerVideoSourceGeneration) return false;
    shareViewerVideoManualPlayRequired = true;
    syncShareViewerVideoPlayOverlay();
    return false;
  }
}

function prepareShareViewerVideoPlayback() {
  const generation = ++shareViewerVideoSourceGeneration;
  if (!isShareViewerVideoActive()) {
    shareViewerVideoManualPlayRequired = false;
    setShareViewerVideoPlayOverlayVisible(false);
    return;
  }
  shareViewerVideoManualPlayRequired = !state.videoAutoplay;
  syncShareViewerVideoPlayOverlay();
  if (state.videoAutoplay) {
    // Invoke play while the opening click still carries user activation on mobile.
    playActiveShareViewerVideo(generation);
  }
}

function openShareViewer(index) {
  if (!els.viewer || !state.visible.length) return;
  const clamp = (i) => (i + state.visible.length) % state.visible.length;
  state.viewerIndex = clamp(index);
  const it = state.visible[state.viewerIndex];
  const mediaUrl = it && (it.original_url || it.view_url || it.thumb_url) || '';
  const isVideo = !!(it && it.is_video);

  if (els.viewerImg) {
    els.viewerImg.setAttribute('draggable', 'false');
    els.viewerImg.style.display = isVideo ? 'none' : 'block';
    if (!isVideo) {
      shareViewerImagePresenter.show(it);
    } else {
      shareViewerImagePresenter.clear();
    }
  }
  if (els.viewerVideo) {
    els.viewerVideo.setAttribute('draggable', 'false');
    els.viewerVideo.style.display = isVideo ? 'block' : 'none';
    try { els.viewerVideo.pause(); } catch {}
    if (isVideo) {
      if (it && it.thumb_url) els.viewerVideo.setAttribute('poster', it.thumb_url);
      else els.viewerVideo.removeAttribute('poster');
      els.viewerVideo.src = mediaUrl;
      try { els.viewerVideo.load(); } catch {}
    } else {
      els.viewerVideo.removeAttribute('src');
      els.viewerVideo.removeAttribute('poster');
      try { els.viewerVideo.load(); } catch {}
    }
  }
  if (els.viewerTitle) els.viewerTitle.textContent = String(it && it.filename || '');
  if (els.viewerOpenOrig) {
    if (mediaUrl) els.viewerOpenOrig.href = mediaUrl;
    else els.viewerOpenOrig.removeAttribute('href');
    els.viewerOpenOrig.textContent = t('open_view');
  }
  if (els.viewerDownloadBtn) {
    const canDownload = canDownloadFromShare() && Number(it && it.id || 0) > 0;
    els.viewerDownloadBtn.classList.toggle('hidden', !canDownload);
    els.viewerDownloadBtn.disabled = !canDownload;
    els.viewerDownloadBtn.textContent = t('download');
  }
  closeShareMoreMenu();
  closeShareViewerMenu();
  const viewerWasHidden = els.viewer.classList.contains('hidden');
  els.viewer.classList.remove('hidden');
  if (viewerWasHidden) els.viewer.classList.remove('viewer-controls-visible');
  document.body.classList.add('viewer-scroll-lock');
  prepareShareViewerVideoPlayback();

  // Hold de næste 10 og forrige 10 billeder/videoer klar i browserens cache.
  shareViewerMediaPreloader.update(state.visible, state.viewerIndex);
  shareViewerPager.prefetch();
}
function closeShareViewer() {
  if (!els.viewer) return;
  els.viewer.classList.add('hidden');
  els.viewer.classList.remove('viewer-controls-visible');
  document.body.classList.remove('viewer-scroll-lock');
  closeShareViewerMenu();
  cleanupShareViewerDrag();
  shareViewerVideoSourceGeneration += 1;
  shareViewerVideoManualPlayRequired = false;
  shareViewerMediaPreloader.clear();
  shareViewerImagePresenter.clear();
  setShareViewerVideoPlayOverlayVisible(false);
  if (els.viewerImg) els.viewerImg.removeAttribute('src');
  if (els.viewerVideo) {
    try { els.viewerVideo.pause(); } catch {}
    els.viewerVideo.removeAttribute('src');
    els.viewerVideo.removeAttribute('poster');
    try { els.viewerVideo.load(); } catch {}
  }
}
async function navShareViewer(step) {
  if (!state.visible.length) return;
  const targetIndex = await shareViewerPager.target(step);
  if (targetIndex >= 0) openShareViewer(targetIndex);
}

if (els.viewerClose) els.viewerClose.addEventListener('click', closeShareViewer);
if (els.viewerPrev) els.viewerPrev.addEventListener('click', () => navShareViewer(-1));
if (els.viewerNext) els.viewerNext.addEventListener('click', () => navShareViewer(1));
if (els.viewerVideoPlayBtn) {
  els.viewerVideoPlayBtn.addEventListener('click', (event) => {
    event.preventDefault();
    event.stopPropagation();
    playActiveShareViewerVideo();
  });
}
if (els.viewerVideo) {
  els.viewerVideo.addEventListener('play', () => {
    if (isShareViewerVideoActive() && !els.viewerVideo.paused) setShareViewerVideoPlayOverlayVisible(false);
    else syncShareViewerVideoPlayOverlay();
  });
  els.viewerVideo.addEventListener('pause', syncShareViewerVideoPlayOverlay);
  els.viewerVideo.addEventListener('ended', syncShareViewerVideoPlayOverlay);
  els.viewerVideo.addEventListener('loadedmetadata', syncShareViewerVideoPlayOverlay);
  els.viewerVideo.addEventListener('error', () => setShareViewerVideoPlayOverlayVisible(false));
}
if (els.viewerMenuBtn) {
  els.viewerMenuBtn.addEventListener('click', (e) => {
    e.preventDefault();
    e.stopPropagation();
    toggleShareViewerMenu();
  });
}
if (els.viewerDownloadBtn) {
  els.viewerDownloadBtn.addEventListener('click', (e) => {
    e.preventDefault();
    e.stopPropagation();
    closeShareViewerMenu();
    const item = state.visible[state.viewerIndex] || null;
    openShareDownloadModal([Number(item && item.id || 0)]);
  });
}
if (els.viewer) {
  els.viewer.addEventListener('click', (e) => {
    const target = e.target;
    if (target === els.viewer) {
      closeShareViewer();
      return;
    }
    if (target && target.closest && (target.closest('#shareViewerMenu') || target.closest('#shareViewerMenuBtn'))) return;
    if (target === els.viewerImg || target === els.viewerVideo) {
      if (window.matchMedia && window.matchMedia('(max-width: 760px)').matches) {
        els.viewer.classList.toggle('viewer-controls-visible');
      }
      closeShareViewerMenu();
      return;
    }
    closeShareViewerMenu();
  });
}
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape' && els.downloadModal && !els.downloadModal.classList.contains('hidden')) {
    closeShareDownloadModal();
    return;
  }
  const viewerOpen = !!(els.viewer && !els.viewer.classList.contains('hidden'));
  if (!viewerOpen) {
    if (e.key === 'Escape') {
      closeShareMoreMenu();
      if (state.selectMode) setSelectMode(false, { clearSelection: true });
    }
    return;
  }
  if (e.key === 'Escape') closeShareViewer();
  if (e.key === 'ArrowLeft') navShareViewer(-1);
  if (e.key === 'ArrowRight') navShareViewer(1);
});

// --- Touch-gestures i viewer (mobil): swipe venstre/højre = bladre, swipe ned = luk ---
const SHARE_VIEWER_BG = 'rgba(0,0,0,0.88)';
let shareTouchStartX = null;
let shareTouchStartY = null;
let shareTouchStartTime = 0;
let shareDragAxis = null; // 'x' = bladre, 'y' = træk ned for at lukke
let shareDragDx = 0;
let shareDragDy = 0;
let shareViewerLongPressTimer = null;
let shareViewerLongPressActivated = false;
let shareViewerLongPressMouseX = null;
let shareViewerLongPressMouseY = null;

function cancelShareViewerLongPress() {
  if (shareViewerLongPressTimer) window.clearTimeout(shareViewerLongPressTimer);
  shareViewerLongPressTimer = null;
  shareViewerLongPressMouseX = null;
  shareViewerLongPressMouseY = null;
}

function scheduleShareViewerLongPressSelection() {
  if (!canSelectFromShare()) return;
  cancelShareViewerLongPress();
  shareViewerLongPressTimer = window.setTimeout(activateShareViewerLongPressSelection, 550);
}

function activateShareViewerLongPressSelection() {
  const item = state.visible[state.viewerIndex] || null;
  const photoId = Number(item && item.id || 0);
  if (!canSelectFromShare() || photoId <= 0) return false;
  cancelShareViewerLongPress();
  shareViewerLongPressActivated = true;
  closeShareViewer();
  setSelectMode(true, { skipRender: true });
  state.selectionPulseId = photoId;
  state.selected.add(photoId);
  renderGrid();
  return true;
}

function getActiveShareViewerMedia() {
  if (els.viewerVideo && els.viewerVideo.style.display !== 'none') return els.viewerVideo;
  if (els.viewerImg && els.viewerImg.style.display !== 'none') return els.viewerImg;
  return els.viewerImg || els.viewerVideo || null;
}

function resetShareViewerTouch() {
  cancelShareViewerLongPress();
  shareTouchStartX = null;
  shareTouchStartY = null;
  shareTouchStartTime = 0;
  shareDragAxis = null;
  shareDragDx = 0;
  shareDragDy = 0;
}

function cleanupShareViewerDrag() {
  [els.viewerImg, els.viewerVideo].forEach((node) => {
    if (!node) return;
    node.style.transition = '';
    node.style.transform = '';
    node.style.opacity = '';
    node.style.willChange = '';
  });
  if (els.viewer) {
    els.viewer.style.transition = '';
    els.viewer.style.background = SHARE_VIEWER_BG;
  }
}

function applyShareViewerDrag(dx, dy) {
  const active = getActiveShareViewerMedia();
  if (!active) return;
  setShareViewerVideoPlayOverlayVisible(false);
  active.style.willChange = 'transform, opacity';
  active.style.transition = 'none';
  if (shareDragAxis === 'y') {
    const h = Math.max(1, window.innerHeight || 1);
    const ratio = Math.min(1, dy / h);
    const scale = Math.max(0.82, 1 - ratio * 0.18);
    active.style.transform = `translateY(${Math.round(dy)}px) scale(${scale.toFixed(3)})`;
    if (els.viewer) {
      els.viewer.style.transition = 'none';
      els.viewer.style.background = `rgba(0,0,0,${(0.88 * (1 - ratio * 0.75)).toFixed(3)})`;
    }
  } else {
    const w = Math.max(1, window.innerWidth || 1);
    const ratio = Math.min(1, Math.abs(dx) / w);
    active.style.transform = `translateX(${Math.round(dx)}px)`;
    active.style.opacity = String(Math.max(0.72, 1 - ratio * 0.38));
  }
}

function animateShareViewerReset() {
  const active = getActiveShareViewerMedia();
  if (active) {
    active.style.transition = 'transform 190ms ease, opacity 190ms ease';
    active.style.transform = 'translate(0, 0) scale(1)';
    active.style.opacity = '1';
  }
  if (els.viewer) {
    els.viewer.style.transition = 'background 190ms ease';
    els.viewer.style.background = SHARE_VIEWER_BG;
  }
  window.setTimeout(() => {
    cleanupShareViewerDrag();
    syncShareViewerVideoPlayOverlay();
  }, 210);
}

function commitShareViewerDismiss() {
  const active = getActiveShareViewerMedia();
  const h = Math.max(1, window.innerHeight || 1);
  if (active) {
    active.style.transition = 'transform 200ms ease, opacity 200ms ease';
    active.style.transform = `translateY(${h}px) scale(0.82)`;
    active.style.opacity = '0.3';
  }
  if (els.viewer) {
    els.viewer.style.transition = 'background 200ms ease';
    els.viewer.style.background = 'rgba(0,0,0,0)';
  }
  window.setTimeout(closeShareViewer, 210);
}

async function commitShareViewerNav(step) {
  const sourceGeneration = shareViewerVideoSourceGeneration;
  const targetIndex = await shareViewerPager.target(step);
  if (sourceGeneration !== shareViewerVideoSourceGeneration) return;
  if (targetIndex < 0) { animateShareViewerReset(); return; }
  const active = getActiveShareViewerMedia();
  const w = Math.max(1, window.innerWidth || 1);
  if (!active) {
    openShareViewer(targetIndex);
    return;
  }
  active.style.transition = 'transform 170ms ease, opacity 170ms ease';
  active.style.transform = `translateX(${step > 0 ? -w : w}px)`;
  active.style.opacity = '0.25';
  window.setTimeout(() => {
    if (sourceGeneration !== shareViewerVideoSourceGeneration || els.viewer.classList.contains('hidden')) return;
    openShareViewer(targetIndex);
    cleanupShareViewerDrag();
  }, 180);
}

function shareTouchStartsInNativeVideoControls(target, touch) {
  if (!els.viewerVideo || !target || !touch) return false;
  if (target !== els.viewerVideo && !(target.closest && target.closest('#shareViewerVideo'))) return false;
  try {
    const rect = els.viewerVideo.getBoundingClientRect();
    const controlBand = Math.min(96, Math.max(58, rect.height * 0.18));
    return touch.clientY >= (rect.bottom - controlBand);
  } catch (_) {
    return false;
  }
}

if (els.viewer) {
  els.viewer.addEventListener('touchstart', (e) => {
    if (!e.touches || e.touches.length !== 1) return;
    const target = e.target;
    if (target && target.closest && target.closest('#shareViewerClose, #shareViewerMenuBtn, #shareViewerMenu, #shareViewerPrev, #shareViewerNext, #shareViewerVideoPlayBtn, .btn, a')) return;
    const t = e.touches[0];
    if (shareTouchStartsInNativeVideoControls(target, t)) return;
    shareTouchStartX = t.clientX;
    shareTouchStartY = t.clientY;
    shareTouchStartTime = Date.now();
    shareDragAxis = null;
    shareDragDx = 0;
    shareDragDy = 0;
    shareViewerLongPressActivated = false;
    scheduleShareViewerLongPressSelection();
  }, { passive: true });

  els.viewer.addEventListener('touchmove', (e) => {
    if (shareTouchStartX === null || shareTouchStartY === null) return;
    if (els.viewer.classList.contains('hidden')) return;
    const t = e.touches && e.touches[0];
    if (!t) return;
    const dx = t.clientX - shareTouchStartX;
    const dy = t.clientY - shareTouchStartY;
    const absX = Math.abs(dx);
    const absY = Math.abs(dy);
    if (absX > 10 || absY > 10) cancelShareViewerLongPress();
    if (!shareDragAxis) {
      if (absX >= 8 && absX > absY * 1.1) shareDragAxis = 'x';
      else if (dy >= 8 && absY > absX * 1.1) shareDragAxis = 'y';
      else return;
    }
    shareDragDx = dx;
    shareDragDy = Math.max(0, dy);
    applyShareViewerDrag(dx, shareDragDy);
    e.preventDefault();
  }, { passive: false });

  els.viewer.addEventListener('touchend', (e) => {
    cancelShareViewerLongPress();
    if (shareViewerLongPressActivated) {
      shareViewerLongPressActivated = false;
      resetShareViewerTouch();
      return;
    }
    if (shareTouchStartX === null || shareTouchStartY === null) return;
    if (els.viewer.classList.contains('hidden')) {
      resetShareViewerTouch();
      return;
    }
    const changed = e.changedTouches && e.changedTouches[0];
    if (!changed) {
      resetShareViewerTouch();
      return;
    }
    const dt = Date.now() - shareTouchStartTime;
    if (shareDragAxis === 'y') {
      const velocity = shareDragDy / Math.max(1, dt);
      const minDismiss = Math.max(90, Math.round((window.innerHeight || 640) * 0.12));
      if (shareDragDy >= minDismiss || velocity > 0.42) commitShareViewerDismiss();
      else animateShareViewerReset();
      resetShareViewerTouch();
      return;
    }
    const dx = shareDragAxis === 'x' ? shareDragDx : (changed.clientX - shareTouchStartX);
    const dy = changed.clientY - shareTouchStartY;
    const absX = Math.abs(dx);
    const absY = Math.abs(dy);
    const minSwipe = Math.max(52, Math.round((window.innerWidth || 320) * 0.16));
    if (absX >= minSwipe && absX > absY * 1.12 && dt <= 900) {
      commitShareViewerNav(dx < 0 ? 1 : -1);
    } else if (shareDragAxis === 'x') {
      animateShareViewerReset();
    }
    resetShareViewerTouch();
  }, { passive: true });

  els.viewer.addEventListener('touchcancel', () => {
    if (shareDragAxis) animateShareViewerReset();
    resetShareViewerTouch();
  }, { passive: true });

  els.viewer.addEventListener('contextmenu', (e) => {
    const target = e.target;
    if ((target !== els.viewerImg && target !== els.viewerVideo) || !shouldReplaceNativeMediaContextMenu()) return;
    e.preventDefault();
    e.stopPropagation();
    activateShareViewerLongPressSelection();
  });
  els.viewer.addEventListener('mousedown', (e) => {
    if (Number(e.button) !== 0 || (e.target !== els.viewerImg && e.target !== els.viewerVideo)) return;
    shareViewerLongPressActivated = false;
    scheduleShareViewerLongPressSelection();
    shareViewerLongPressMouseX = Number(e.clientX || 0);
    shareViewerLongPressMouseY = Number(e.clientY || 0);
  });
  els.viewer.addEventListener('mousemove', (e) => {
    if (!shareViewerLongPressTimer || shareViewerLongPressMouseX === null || shareViewerLongPressMouseY === null) return;
    if (Math.abs(Number(e.clientX || 0) - shareViewerLongPressMouseX) > 14 || Math.abs(Number(e.clientY || 0) - shareViewerLongPressMouseY) > 14) {
      cancelShareViewerLongPress();
    }
  }, { passive: true });
  ['mouseup', 'mouseleave'].forEach((eventName) => els.viewer.addEventListener(eventName, cancelShareViewerLongPress));
  els.viewer.addEventListener('click', (e) => {
    if (!shareViewerLongPressActivated) return;
    shareViewerLongPressActivated = false;
    e.preventDefault();
    e.stopImmediatePropagation();
  }, true);
}

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
  const res = await fetch(`/api/share/${encodeURIComponent(state.token)}/info`, { cache: 'no-store' });
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
  state.videoAutoplay = data.video_autoplay === true;
  applyShareUploadFileTypes(data);
  renderShareBlockedTypes();
  if (els.authBox) els.authBox.classList.add('hidden');
  if (els.meta) {
    const permissionParts = [t('perms_view')];
    if (data.can_upload) permissionParts.push(t('perms_upload'));
    if (data.can_delete) permissionParts.push(t('perms_delete'));
    // "Se, upload og slette" - sidste led bindes med "og"
    const permsText = permissionParts.length > 1
      ? `${permissionParts.slice(0, -1).join(', ')} ${t('perms_and')} ${permissionParts[permissionParts.length - 1]}`
      : permissionParts[0];
    const folderNames = Array.isArray(data.folder_paths) ? data.folder_paths.map(p => String(p||'').split('/').filter(Boolean).pop() || '').filter(Boolean) : [];
    const baseTitle = (folderNames.length === 1)
      ? folderNames[0]
      : (String(data.share_name || '').trim() || String(data.folder_label || '').replace(/^uploads\//,'').trim());
    els.meta.innerHTML = `<div class="meta-folder">${baseTitle}</div><div class="meta-perms">${t('perms_label')}: ${permsText}</div>`;
  }
  if (els.uploadWrap) els.uploadWrap.style.display = data.can_upload ? '' : 'none';
  if (els.uploadBtn) els.uploadBtn.style.display = data.can_upload ? '' : 'none';
  if (!canSelectFromShare()) {
    state.selectMode = false;
    state.selected = new Set();
    state.selectionPulseId = 0;
  }
  if (!canDownloadFromShare()) {
    if (els.viewerDownloadBtn) els.viewerDownloadBtn.classList.add('hidden');
    if (els.downloadModal && !els.downloadModal.classList.contains('hidden')) closeShareDownloadModal();
  }
  updateDeleteButton();
  return true;
}

function captureShareGridScrollAnchor() {
  if (!els.grid) return null;
  const cards = Array.from(els.grid.querySelectorAll('.photo-card[data-photo-id]'));
  const visibleCard = cards.find((card) => {
    const rect = card.getBoundingClientRect();
    return rect.bottom > 0 && rect.top < window.innerHeight;
  });
  if (!visibleCard) return { scrollY: window.scrollY, photoId: 0, top: 0 };
  return {
    scrollY: window.scrollY,
    photoId: Number(visibleCard.getAttribute('data-photo-id') || 0),
    top: visibleCard.getBoundingClientRect().top,
  };
}

function restoreShareGridScrollAnchor(anchor) {
  if (!anchor) return;
  const restore = () => {
    const photoId = Number(anchor.photoId || 0);
    const card = photoId > 0 && els.grid
      ? els.grid.querySelector(`.photo-card[data-photo-id="${photoId}"]`)
      : null;
    const targetY = card
      ? Math.max(0, window.scrollY + card.getBoundingClientRect().top - Number(anchor.top || 0))
      : Math.max(0, Number(anchor.scrollY || 0));
    window.scrollTo(0, targetY);
  };
  restore();
  requestAnimationFrame(() => {
    restore();
    requestAnimationFrame(restore);
  });
}

let sharePhotosLoadPromise = null;
let sharePhotosRequestSequence = 0;

async function loadPhotos(preserveScroll = false, append = false) {
  if (append && sharePhotosLoadPromise) return sharePhotosLoadPromise.catch(() => false);
  const request = loadSharePhotosPage(preserveScroll, append);
  sharePhotosLoadPromise = request;
  try {
    return await request;
  } catch (error) {
    showStatus('Kunne ikke hente billeder. Prøv igen.', 'err');
    return false;
  } finally {
    if (sharePhotosLoadPromise === request) {
      sharePhotosLoadPromise = null;
      state.photosLoading = false;
    }
  }
}

async function loadSharePhotosPage(preserveScroll = false, append = false) {
  const sequence = ++sharePhotosRequestSequence;
  const path = state.currentPath;
  state.photosLoading = true;
  const cols = estimateShareColumns();
  const params = new URLSearchParams({
    path: state.currentPath || '',
    offset: String(append ? state.photosOffset : 0),
    limit: String(cols * 5),
  });
  const startIndex = append ? state.items.length : 0;
  const res = await fetch(`/api/share/${encodeURIComponent(state.token)}/photos?${params.toString()}`);
  const data = await res.json().catch(() => ({}));
  if (sequence !== sharePhotosRequestSequence || path !== state.currentPath) return false;
  if (res.status === 401 && data && (data.password_required || data.name_required)) {
    applyAuthRequirements(data);
    state.photosLoading = false;
    return false;
  }
  if (!res.ok || !data || !data.ok) {
    showStatus((data && data.error) || 'Share error', 'err');
    state.photosLoading = false;
    return false;
  }
  const incoming = Array.isArray(data.items) ? data.items : [];
  state.items = append ? state.items.concat(incoming) : incoming;
  state.folders = Array.isArray(data.folders) ? data.folders : state.folders;
  state.photosOffset = Number(data.next_offset || state.items.length);
  state.photosTotal = Math.max(state.items.length, Number(data.total || 0));
  state.photosHasMore = !!data.has_more;
  state.photosLoading = false;
  if (!state.selectMode) {
    state.selected = new Set();
    state.selectionPulseId = 0;
  }
  if (append) {
    hydrateShareItems(startIndex, incoming);
    setupShareGhostLoading();
    return true;
  }
  state.ghostCapacity = Math.min(state.photosTotal, cols * 50);
  const scrollAnchor = preserveScroll ? captureShareGridScrollAnchor() : null;
  renderGrid();
  restoreShareGridScrollAnchor(scrollAnchor);
  return true;
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

async function runUpload(preselectedFiles = null) {
  const files = Array.isArray(preselectedFiles)
    ? preselectedFiles
    : ((els.fileInput && els.fileInput.files) ? Array.from(els.fileInput.files) : []);
  if (!files.length) { showStatus(t('no_files'), 'err'); return; }
  // Ensure we are authorized just before starting (handles expired session)
  try {
    const res = await fetch(`/api/share/${encodeURIComponent(state.token)}/info`, { cache: 'no-store' });
    const data = await res.json().catch(() => ({}));
    if (res.status === 401) {
      applyAuthRequirements(data || {});
      showStatus(t('auth_required'), 'err');
      return; // Wait for user to authorize
    }
    if (!res.ok || !data || !data.ok || !data.can_upload) {
      showStatus((data && data.error) || 'Upload ikke tilladt', 'err');
      return;
    }
    state.info = data;
    applyShareUploadFileTypes(data);
    renderShareBlockedTypes();
  } catch {}
  const split = splitShareFilesByAllowed(files);
  if (split.blocked.length) {
    const summary = summarizeFileExtensions(split.blocked);
    renderShareBlockedTypes(split.blocked);
    showStatus(t('blocked_file_types_status').replace('{types}', summary), 'err');
  }
  const uploadFiles = split.allowed;
  if (!uploadFiles.length) {
    if (els.fileInput) els.fileInput.value = '';
    return;
  }

  function hasTusClient(){ return !!(window.tus && typeof window.tus.Upload === 'function'); }
  async function uploadTus(file){
    return new Promise((resolve)=>{
      if (!hasTusClient()) { resolve({ ok:false, error:'TUS client unavailable' }); return; }
      const meta = {
        filename: String(file && file.name || 'file'),
        lastModified: String(Number(file && file.lastModified ? file.lastModified : 0)),
      };
      const upload = new window.tus.Upload(file, {
        endpoint: `/api/share/${encodeURIComponent(state.token)}/upload/tus`,
        metadata: meta,
        uploadDataDuringCreation: false,
        withCredentials: true,
        overridePatchMethod: true,
        chunkSize: 2 * 1024 * 1024,
        parallelUploads: 1,
        retryDelays: [0, 1000, 2500, 5000],
        removeFingerprintOnSuccess: true,
        onProgress(bytesUploaded, bytesTotal){
          const pct = bytesTotal > 0 ? Math.round((bytesUploaded/bytesTotal)*100) : 0;
          updateShareUploadProgress(bytesUploaded, bytesTotal);
          showStatus(`${t('upload_run')}: ${file.name} - ${pct}%`, 'ok');
        },
        onError(err){
          try {
            const resp = err && err.originalResponse;
            const status = resp && typeof resp.getStatus === 'function' ? Number(resp.getStatus()) : 0;
            if (status === 401) {
              showStatus(t('auth_required'), 'err');
              // Refresh share info to reveal auth box (password/name)
              loadInfo();
            }
          } catch {}
          resolve({ ok:false, error: (err && err.message) || 'Upload failed' });
        },
        onSuccess(){ resolve({ ok:true }); },
      });
      upload.findPreviousUploads().then((prev)=>{ if (Array.isArray(prev) && prev.length) upload.resumeFromPreviousUpload(prev[0]); upload.start(); }).catch(()=> upload.start());
    });
  }

  let saved=0, failed=0;
  if (!hasTusClient()) { showStatus('TUS klient mangler. Genindl\u00e6s siden.', 'err'); return; }
  showUploadWarningModal();
  startShareUploadProgress(uploadFiles);
  startShareUploadTransferHeartbeat();
  await setShareUploadTransferState(true);
  try {
    for (const f of uploadFiles){
      markShareUploadCurrentFile(f);
      const r = await uploadTus(f);
      const ok = !!(r && r.ok);
      finishShareUploadFile(f, ok);
      if (ok) saved+=1; else failed+=1;
    }
  } finally {
    await stopShareUploadTransferHeartbeat();
    finishShareUploadProgress();
    closeUploadWarningModal();
    if (els.fileInput) els.fileInput.value = '';
  }
  let postprocessError = '';
  if (saved > 0) {
    try {
      await startShareUploadPostprocess();
    } catch (err) {
      postprocessError = err && err.message ? String(err.message) : t('postprocess_start_failed');
    }
  }
  if (postprocessError) {
    showStatus(`${t('upload_done')} - ${t('postprocess_start_failed')}: ${postprocessError}`, 'err');
  } else if (failed>0){ showStatus(`${t('upload_done')} - ${saved} ok - ${failed} fejl`, 'err'); }
  else { showStatus(t('upload_done'), 'ok'); }
  await loadPhotos(true);
}

async function runDelete() {
  if (!canDeleteFromShare()) {
    showStatus('Sletning ikke tilladt', 'err');
    return;
  }
  const ids = Array.from(state.selected || []);
  if (!ids.length) {
    showStatus('Ingen billeder valgt', 'err');
    return;
  }
  if (!window.confirm(`Slet ${ids.length} billede(r)?`)) return;
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
  state.selected = new Set();
  state.selectionPulseId = 0;
  if (state.selectMode) setSelectMode(false, { skipRender: true, clearSelection: true });
  await loadPhotos(true);
}

async function boot() {
  hideStatus();
  state.selectMode = false;
  state.selected = new Set();
  state.selectionPulseId = 0;
  closeShareMoreMenu();
  closeShareViewerMenu();
  closeShareDownloadModal();
  closeUploadWarningModal();
  clearUploadProgressHideTimer();
  setShareUploadStatusVisible(false, 'ok');
  renderShareUploadStatus();
  if (els.title) els.title.textContent = t('title');
  if (els.meta) els.meta.textContent = t('loading');
  if (els.authTitle) els.authTitle.textContent = t('auth_title');
  if (els.authNameLabel) els.authNameLabel.textContent = t('auth_name_label');
  if (els.authName) els.authName.placeholder = t('auth_name_placeholder');
  if (els.authLabel) els.authLabel.textContent = t('auth_password_label');
  if (els.authPassword) els.authPassword.placeholder = t('auth_password_placeholder');
  if (els.authBtn) els.authBtn.textContent = t('auth_continue');
  if (els.uploadLabel) els.uploadLabel.textContent = t('upload_pick');
  // No separate upload button; auto-start on file pick
  if (els.downloadBtn) els.downloadBtn.textContent = t('download');
  if (els.deleteBtn) els.deleteBtn.textContent = t('delete_selected');
  if (els.moreSelectBtn) els.moreSelectBtn.textContent = t('select_photos');
  if (els.moreSelectAllBtn) els.moreSelectAllBtn.textContent = t('select_all');
  if (els.moreClearBtn) els.moreClearBtn.textContent = t('clear_selected');
  if (els.moreDownloadBtn) els.moreDownloadBtn.textContent = t('download_selected');
  if (els.moreDeleteBtn) els.moreDeleteBtn.textContent = t('delete_selected');
  if (els.viewerOpenOrig) els.viewerOpenOrig.textContent = t('open_view');
  if (els.viewerDownloadBtn) els.viewerDownloadBtn.textContent = t('download');
  if (els.viewerVideoPlayBtn) {
    els.viewerVideoPlayBtn.setAttribute('aria-label', t('video_play'));
    els.viewerVideoPlayBtn.setAttribute('title', t('video_play'));
  }
  if (els.downloadModalTitle) els.downloadModalTitle.textContent = t('download_title');
  if (els.downloadModalClose) els.downloadModalClose.setAttribute('aria-label', t('close'));
  if (els.downloadPrompt) els.downloadPrompt.textContent = t('download_prompt');
  if (els.downloadDateLegend) els.downloadDateLegend.textContent = t('download_date_legend');
  if (els.downloadDateOriginalTitle) els.downloadDateOriginalTitle.textContent = t('download_date_original_title');
  if (els.downloadDateOriginalDesc) els.downloadDateOriginalDesc.textContent = t('download_date_original_desc');
  if (els.downloadDateTodayTitle) els.downloadDateTodayTitle.textContent = t('download_date_today_title');
  if (els.downloadDateTodayDesc) els.downloadDateTodayDesc.textContent = t('download_date_today_desc');
  if (els.downloadConvertedBtn) els.downloadConvertedBtn.textContent = t('download_converted');
  if (els.downloadOriginalBtn) els.downloadOriginalBtn.textContent = t('download_original');
  if (els.downloadCancelBtn) els.downloadCancelBtn.textContent = t('cancel');
  if (els.downloadNativeBtn) els.downloadNativeBtn.textContent = t('download_native');
  if (els.downloadReadyClose) els.downloadReadyClose.textContent = t('close');

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
if (els.uploadWrap) {
  els.uploadWrap.addEventListener('click', (e) => {
    e.preventDefault();
    openShareFilePicker();
  });
}
if (els.fileInput) {
  els.fileInput.addEventListener('change', () => {
    const list = (els.fileInput && els.fileInput.files) ? els.fileInput.files : null;
    if (!list || !list.length) return;
    // Clone FileList immediately; iOS Safari can keep picker UI blocked while
    // the change handler runs. Defer heavy work one tick for smoother UX.
    const files = Array.from(list);
    showStatus(`${t('upload_run')}: forbereder ${files.length} filer...`, 'ok');
    window.setTimeout(() => {
      try {
        runUpload(files);
      } catch (e) {
        console.error(e);
      }
    }, 50);
    // Clear value so the same files can be picked again later
    els.fileInput.value = '';
  });
}
if (els.deleteBtn) els.deleteBtn.addEventListener('click', runDelete);
if (els.downloadBtn) {
  els.downloadBtn.addEventListener('click', () => {
    openShareDownloadModal(Array.from(state.selected || []));
  });
}
if (els.pathBackTop) {
  els.pathBackTop.addEventListener('click', (e) => {
    e.preventDefault();
    navigateShareBackPath();
  });
}
if (els.moreBtn) {
  ['pointerdown', 'touchstart'].forEach((ev) => {
    els.moreBtn.addEventListener(ev, (e) => { e.stopPropagation(); }, { passive: true });
  });
  els.moreBtn.addEventListener('click', (e) => {
    e.preventDefault();
    e.stopPropagation();
    toggleShareMoreMenu();
  });
}
if (els.moreMenu) {
  ['pointerdown', 'touchstart', 'click'].forEach((ev) => {
    els.moreMenu.addEventListener(ev, (e) => { e.stopPropagation(); }, { passive: true });
  });
}
if (els.moreSelectBtn) {
  els.moreSelectBtn.addEventListener('click', () => {
    setSelectMode(!state.selectMode, { clearSelection: !state.selectMode ? false : true });
    closeShareMoreMenu();
  });
}
if (els.moreSelectAllBtn) {
  els.moreSelectAllBtn.addEventListener('click', async () => {
    if (!state.selectMode || !canSelectFromShare()) return;
    while (state.photosHasMore) {
      const loaded = await loadPhotos(false, true);
      if (!loaded) break;
    }
    state.selected = new Set((state.visible || []).map((it) => Number(it && it.id || 0)).filter((id) => id > 0));
    state.selectionPulseId = 0;
    renderGrid();
    closeShareMoreMenu();
  });
}
if (els.moreClearBtn) {
  els.moreClearBtn.addEventListener('click', () => {
    state.selected = new Set();
    state.selectionPulseId = 0;
    renderGrid();
    closeShareMoreMenu();
  });
}
if (els.moreDownloadBtn) {
  els.moreDownloadBtn.addEventListener('click', () => {
    closeShareMoreMenu();
    openShareDownloadModal(Array.from(state.selected || []));
  });
}
if (els.moreDeleteBtn) {
  els.moreDeleteBtn.addEventListener('click', async () => {
    closeShareMoreMenu();
    await runDelete();
  });
}
if (els.downloadModalClose) {
  els.downloadModalClose.addEventListener('click', () => closeShareDownloadModal());
}
if (els.downloadCancelBtn) {
  els.downloadCancelBtn.addEventListener('click', () => closeShareDownloadModal());
}
if (els.downloadReadyClose) {
  els.downloadReadyClose.addEventListener('click', () => closeShareDownloadModal());
}
if (els.downloadConvertedBtn) {
  els.downloadConvertedBtn.addEventListener('click', () => startShareDownload('converted'));
}
if (els.downloadOriginalBtn) {
  els.downloadOriginalBtn.addEventListener('click', () => startShareDownload('original'));
}
if (els.downloadNativeBtn) {
  els.downloadNativeBtn.addEventListener('click', sharePreparedDownloadsNatively);
}
if (els.downloadFallbackBtn) {
  els.downloadFallbackBtn.addEventListener('click', downloadNextPreparedShareFile);
}
if (els.downloadModal) {
  els.downloadModal.addEventListener('click', (e) => {
    const target = e.target;
    if (target === els.downloadModal || (target && target.classList && target.classList.contains('modal-backdrop'))) {
      closeShareDownloadModal();
    }
  });
}
if (els.uploadPrepClose) {
  els.uploadPrepClose.addEventListener('click', closeUploadPrepModal);
}
if (els.uploadPrepCancel) {
  els.uploadPrepCancel.addEventListener('click', closeUploadPrepModal);
}
if (els.uploadPrepContinue) {
  els.uploadPrepContinue.addEventListener('click', continueUploadPrepModal);
}
if (els.uploadPrepModal) {
  els.uploadPrepModal.addEventListener('click', (e) => {
    if (e.target === els.uploadPrepModal || (e.target && e.target.classList && e.target.classList.contains('modal-backdrop'))) {
      closeUploadPrepModal();
    }
  });
}
if (els.uploadWarnClose) {
  els.uploadWarnClose.addEventListener('click', closeUploadWarningModal);
}
if (els.uploadWarnModal) {
  els.uploadWarnModal.addEventListener('click', (e) => {
    if (e.target === els.uploadWarnModal) closeUploadWarningModal();
  });
}

document.addEventListener('pointerdown', (e) => {
  const t = e.target;
  if (!(t instanceof Node)) return;
  if (els.moreMenu && els.moreMenu.contains(t)) return;
  if (els.moreBtn && els.moreBtn.contains(t)) return;
  closeShareMoreMenu();
});

window.addEventListener('resize', () => {
  const mobileNow = isMobileShareView();
  if (mobileNow === lastResizeIsMobile) return;
  lastResizeIsMobile = mobileNow;
  updateDeleteButton();
});

boot();
