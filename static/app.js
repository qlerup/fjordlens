const els = {
  grid: document.getElementById("galleryGrid"),
  search: document.getElementById("searchInput"),
  sort: document.getElementById("sortSelect"),
  scanBtn: document.getElementById("scanBtn"),
  rescanBtn: document.getElementById("rescanBtn"),
  rethumbBtn: document.getElementById("rethumbBtn"),
  clearIndexBtn: document.getElementById("clearIndexBtn"),
  aiIngestBtn: document.getElementById("aiIngestBtn"),
  aiStopBtn: document.getElementById("aiStopBtn"),
  aiStatus: document.getElementById("aiStatus"),
  facesIndexBtn: document.getElementById("facesIndexBtn"),
  facesStatus: document.getElementById("facesStatus"),
  mapperTools: document.getElementById("mapperTools"),
  mapperCurrentPath: document.getElementById("mapperCurrentPath"),
  mapperUpBtn: document.getElementById("mapperUpBtn"),
  mapperFolderNewInput: document.getElementById("mapperFolderNewInput"),
  mapperFolderCreateBtn: document.getElementById("mapperFolderCreateBtn"),
  mapperEditBtn: document.getElementById("mapperEditBtn"),
  mapperDeleteBtn: document.getElementById("mapperDeleteBtn"),
  mapperNavMenu: document.getElementById("mapperNavMenu"),
  mapperTreeNav: document.getElementById("mapperTreeNav"),
  mapperDropZone: document.getElementById("mapperDropZone"),
  stopScanBtn: null,
  status: document.getElementById("statusBar"),
  empty: document.getElementById("emptyState"),

  photoCount: document.getElementById("photoCount"),
  photoCountLabel: document.getElementById("photoCountLabel"),
  favoriteCount: document.getElementById("favoriteCount"),
  favoriteCountLabel: document.getElementById("favoriteCountLabel"),
  selectedCount: document.getElementById("selectedCount"),
  selectedCountLabel: document.getElementById("selectedCountLabel"),
  statPhotos: document.getElementById("statPhotos"),
  statFavorites: document.getElementById("statFavorites"),
  statSelected: document.getElementById("statSelected"),
  statHiddenToggle: document.getElementById("statHiddenToggle"),
  showHiddenToggle: document.getElementById("showHiddenToggle"),

  viewTitle: document.getElementById("viewTitle"),
  viewSubtitle: document.getElementById("viewSubtitle"),

  detailEmpty: document.getElementById("detailEmpty"),
  detailContent: document.getElementById("detailContent"),
  detailThumb: document.getElementById("detailThumb"),
  detailName: document.getElementById("detailName"),
  detailPath: document.getElementById("detailPath"),
  detailDate: document.getElementById("detailDate"),
  detailSize: document.getElementById("detailSize"),
  detailDims: document.getElementById("detailDims"),
  detailDevice: document.getElementById("detailDevice"),
  detailLens: document.getElementById("detailLens"),
  detailGps: document.getElementById("detailGps"),
  detailCountry: document.getElementById("detailCountry"),
  detailCity: document.getElementById("detailCity"),
  detailAiTags: document.getElementById("detailAiTags"),
  rawMeta: document.getElementById("rawMeta"),
  toggleRawBtn: document.getElementById("toggleRawBtn"),
  favoriteBtn: document.getElementById("favoriteBtn"),
  // logs
  logsBox: document.getElementById("liveLogs"),
  logsStart: document.getElementById("logsStart"),
  logsClear: document.getElementById("logsClear"),
  mainLogsBox: document.getElementById("mainLogs"),
  mainLogsStart: document.getElementById("mainLogsStart"),
  mainLogsClear: document.getElementById("mainLogsClear"),
  logsPanel: document.getElementById("logsPanel"),
  settingsPanel: document.getElementById("settingsPanel"),
  placesMapWrap: document.getElementById("placesMapWrap"),
  placesMapEl: document.getElementById("placesMap"),
  // duplicates
  dupesBtn: document.getElementById("dupesBtn"),
  dupesRun: document.getElementById("dupesRun"),
  dupeDist: document.getElementById("dupeDist"),
  dupeMin: document.getElementById("dupeMin"),
  dupeStatus: document.getElementById("dupeStatus"),
  dupeResults: document.getElementById("dupeResults"),
  // viewer
  viewer: document.getElementById("viewer"),
  viewerImg: document.getElementById("viewerImg"),
  viewerVideo: document.getElementById("viewerVideo"),
  viewerPrev: document.getElementById("viewerPrev"),
  viewerNext: document.getElementById("viewerNext"),
  viewerClose: document.getElementById("viewerClose"),
  viewerOpenOrig: document.getElementById("viewerOpenOrig"),
  menuBtn: document.getElementById("menuBtn"),
  drawerBackdrop: document.getElementById("drawerBackdrop"),
  profileLink: document.getElementById("profileLink"),
  profileModal: document.getElementById("profileModal"),
  profileModalClose: document.getElementById("profileModalClose"),
  scanModal: document.getElementById("scanModal"),
  scanModalClose: document.getElementById("scanModalClose"),
  scanModalCancel: document.getElementById("scanModalCancel"),
  scanModalStart: document.getElementById("scanModalStart"),
  // date edit controls
  editDateBtn: document.getElementById('editDateBtn'),
  dateEditWrap: document.getElementById('dateEditWrap'),
  dateInput: document.getElementById('dateInput'),
  dateSaveBtn: document.getElementById('dateSaveBtn'),
  dateCancelBtn: document.getElementById('dateCancelBtn'),
  // gps edit controls
  editGpsBtn: document.getElementById('editGpsBtn'),
  gpsEditWrap: document.getElementById('gpsEditWrap'),
  gpsMapEl: document.getElementById('gpsMap'),
  gpsCoordText: document.getElementById('gpsCoordText'),
  gpsSaveBtn: document.getElementById('gpsSaveBtn'),
  gpsCancelBtn: document.getElementById('gpsCancelBtn'),
  gpsEarthBtn: document.getElementById('gpsEarthBtn'),
  gpsSearchInput: document.getElementById('gpsSearchInput'),
  gpsSearchList: document.getElementById('gpsSearchList'),
  // upload overlay
  uploadOverlay: document.getElementById("uploadOverlay"),
  uploadProgressBar: document.getElementById("uploadProgressBar"),
  uploadProgressText: document.getElementById("uploadProgressText"),
};

function ensureUploadOverlayRefs() {
  if (!els.uploadOverlay) els.uploadOverlay = document.getElementById("uploadOverlay");
  if (!els.uploadProgressBar) els.uploadProgressBar = document.getElementById("uploadProgressBar");
  if (!els.uploadProgressText) els.uploadProgressText = document.getElementById("uploadProgressText");
}

// Immediate emergency cleanup in case an overlay/backdrop was left in DOM
(function immediateCleanup(){
  try { document.querySelectorAll('.modal-backdrop').forEach(el=>{ el.classList.remove('active'); if (el.parentElement) el.parentElement.removeChild(el); }); } catch{}
  try { document.querySelectorAll('.upload-overlay').forEach(el=> el.classList.add('hidden')); } catch{}
})();
try { window.addEventListener('DOMContentLoaded', ()=>{
  try { document.querySelectorAll('.modal-backdrop').forEach(el=>{ el.classList.remove('active'); if (el.parentElement) el.parentElement.removeChild(el); }); } catch{}
  try { document.querySelectorAll('.upload-overlay').forEach(el=> el.classList.add('hidden')); } catch{}
}); } catch{}

// People: toggle 'Vis skjulte'
try {
  if (els.showHiddenToggle) {
    els.showHiddenToggle.addEventListener('change', ()=>{
      state.showHiddenPeople = !!els.showHiddenToggle.checked;
      if (state.view === 'personer') loadPeople();
    });
  }
} catch {}

const APP_PROFILE = (window.APP_PROFILE && typeof window.APP_PROFILE === 'object') ? window.APP_PROFILE : {};
const UI_LANGUAGES = new Set(['da', 'en']);

const I18N = {
  da: {
    nav_timeline: '📅 Tidlinje',
    nav_favorites: '⭐ Favoritter',
    nav_places: '📍 Steder',
    nav_cameras: '📸 Kameraer',
    nav_folders: '🗂️ Mapper',
    nav_people: '🙂 Personer',
    nav_settings: '⚙️ Indstillinger',
    profile_link: 'Profil',
    logout_link: 'Log ud',
    search_placeholder: 'Søg på dansk: strand, bil, skov, kamera, dato, filnavn...',
    tab_maint: 'Vedligeholdelse',
    tab_ai: 'AI',
    tab_logs: 'Logs',
    tab_users: 'Brugere',
    tab_twofa: 'Min 2FA',
    tab_profile: 'Profil',
    tab_other: 'Andet',
    view_timeline_title: 'Tidlinje',
    view_timeline_sub: 'Dato-grupperet oversigt (år/måned)',
    view_favorites_title: 'Favoritter',
    view_favorites_sub: 'Markerede billeder',
    view_steder_title: 'Steder',
    view_steder_sub: 'Billeder med GPS/placeringsdata',
    view_kameraer_title: 'Kameraer',
    view_kameraer_sub: 'Filtreret på billeder med kameradata',
    view_mapper_title: 'Mapper',
    view_mapper_sub: 'Grupperet efter kilde-mappe',
    view_personer_title: 'Personer',
    view_personer_sub: 'Klar til ansigtsgenkendelse (kommer med ONNX face-service)',
    view_settings_title: 'Indstillinger',
    view_settings_sub: 'Vedligeholdelse, scan og administration',
    sort_date_desc: 'Nyeste først',
    sort_date_asc: 'Ældste først',
    sort_name_asc: 'Navn A-Å',
    sort_name_desc: 'Navn Å-A',
    sort_size_desc: 'Størst først',
    sort_size_asc: 'Mindst først',
    stat_photos: 'Billeder',
    stat_people: 'Personer',
    stat_favorites: 'Favoritter',
    stat_selected: 'Valgt',
    stat_show_hidden: 'Vis skjulte',
    empty_people: 'Ingen personer endnu. Upload billeder med ansigter eller kør ansigtsindeksering.',
    empty_no_photos: 'Ingen billeder endnu. Slip filer for at uploade eller scan biblioteket.',
    empty_no_matches: "Ingen billeder matcher filteret endnu. Prøv 'Scan bibliotek'.",
    empty_mapper_tree: 'Ingen mapper endnu.',
    no_thumb: 'Ingen thumbnail',
    settings_title: 'Indstillinger',
    settings_sub: 'Vedligeholdelse, scan og logs',
    maint_title: 'Vedligeholdelse',
    btn_scan_library: 'Scan bibliotek',
    btn_rescan_metadata: 'Rescan metadata',
    btn_rebuild_thumbs: 'Genbyg thumbnails',
    btn_reset_index: 'Nulstil indeks',
    btn_build_embeddings: 'Byg AI-embeddings',
    btn_start_ai: 'Start AI',
    btn_stop_ai: 'Stop AI',
    btn_index_faces: 'Indekser ansigter',
    status_faces_prefix: 'Ansigter',
    status_ai_prefix: 'AI',
    status_stopped: 'stoppet',
    status_running: 'kører',
    status_dash: '—',
    upload_new_folder_placeholder: 'Ny mappe (fx ferie eller 2026/rejse)',
    upload_create_folder: 'Opret mappe',
    logs_label: 'Logs:',
    btn_stop: 'Stop',
    btn_start: 'Start',
    btn_clear: 'Ryd',
    mapper_current_folder: 'Aktuel mappe',
    mapper_root_folder: 'uploads (rodmappe)',
    mapper_drop_here: 'Slip filer her for at uploade til',
    mapper_up: 'Op',
    mapper_done: 'Færdig',
    mapper_edit: '!edit',
    mapper_delete_selected: 'Slet valgte',
    profile_title: 'Profil',
    profile_close: 'Luk',
    profile_username: 'Brugernavn',
    profile_password_new_optional: 'Nyt password (valgfrit)',
    profile_password_repeat: 'Gentag nyt password',
    profile_password_repeat_placeholder: 'Gentag password',
    profile_password_unchanged_placeholder: 'Tom = uændret',
    profile_ui_lang: 'UI-sprog',
    profile_search_lang: 'Søgesprog',
    profile_save: 'Gem profil',
    profile_saved: 'Profil opdateret',
    status_errors_label: 'fejl',
    status_ready_scan: "Klar. Tryk 'Scan bibliotek' for at indeksere dine billeder.",
    scan_modal_title: 'Scan bibliotek',
    scan_modal_text: 'Vil du starte en fuld scanning af biblioteket nu?',
    scan_modal_close: 'Luk',
    scan_modal_cancel: 'Annuller',
    scan_modal_start: 'Start scan',
  },
  en: {
    nav_timeline: '📅 Timeline',
    nav_favorites: '⭐ Favorites',
    nav_places: '📍 Places',
    nav_cameras: '📸 Cameras',
    nav_folders: '🗂️ Folders',
    nav_people: '🙂 People',
    nav_settings: '⚙️ Settings',
    profile_link: 'Profile',
    logout_link: 'Log out',
    search_placeholder: 'Search in English: beach, car, forest, camera, date, filename...',
    tab_maint: 'Maintenance',
    tab_ai: 'AI',
    tab_logs: 'Logs',
    tab_users: 'Users',
    tab_twofa: 'My 2FA',
    tab_profile: 'Profile',
    tab_other: 'Other',
    view_timeline_title: 'Timeline',
    view_timeline_sub: 'Date grouped overview (year/month)',
    view_favorites_title: 'Favorites',
    view_favorites_sub: 'Starred photos',
    view_steder_title: 'Places',
    view_steder_sub: 'Photos with location metadata',
    view_kameraer_title: 'Cameras',
    view_kameraer_sub: 'Filtered by available camera metadata',
    view_mapper_title: 'Folders',
    view_mapper_sub: 'Grouped by source folder',
    view_personer_title: 'People',
    view_personer_sub: 'Face-recognition ready (ONNX face service)',
    view_settings_title: 'Settings',
    view_settings_sub: 'Maintenance, scan and administration',
    sort_date_desc: 'Newest first',
    sort_date_asc: 'Oldest first',
    sort_name_asc: 'Name A-Z',
    sort_name_desc: 'Name Z-A',
    sort_size_desc: 'Largest first',
    sort_size_asc: 'Smallest first',
    stat_photos: 'Photos',
    stat_people: 'People',
    stat_favorites: 'Favorites',
    stat_selected: 'Selected',
    stat_show_hidden: 'Show hidden',
    empty_people: 'No people yet. Upload photos with faces or run face indexing.',
    empty_no_photos: 'No photos yet. Drop files to upload or scan the library.',
    empty_no_matches: "No photos match the current filters yet. Try 'Scan library'.",
    empty_mapper_tree: 'No folders yet.',
    no_thumb: 'No thumbnail',
    settings_title: 'Settings',
    settings_sub: 'Maintenance, scan and logs',
    maint_title: 'Maintenance',
    btn_scan_library: 'Scan library',
    btn_rescan_metadata: 'Rescan metadata',
    btn_rebuild_thumbs: 'Rebuild thumbnails',
    btn_reset_index: 'Reset index',
    btn_build_embeddings: 'Build AI embeddings',
    btn_start_ai: 'Start AI',
    btn_stop_ai: 'Stop AI',
    btn_index_faces: 'Index faces',
    status_faces_prefix: 'Faces',
    status_ai_prefix: 'AI',
    status_stopped: 'stopped',
    status_running: 'running',
    status_dash: '—',
    upload_new_folder_placeholder: 'New folder (e.g. holiday or 2026/trip)',
    upload_create_folder: 'Create folder',
    logs_label: 'Logs:',
    btn_stop: 'Stop',
    btn_start: 'Start',
    btn_clear: 'Clear',
    mapper_current_folder: 'Current folder',
    mapper_root_folder: 'uploads (root)',
    mapper_drop_here: 'Drop files here to upload to',
    mapper_up: 'Up',
    mapper_done: 'Done',
    mapper_edit: '!edit',
    mapper_delete_selected: 'Delete selected',
    profile_title: 'Profile',
    profile_close: 'Close',
    profile_username: 'Username',
    profile_password_new_optional: 'New password (optional)',
    profile_password_repeat: 'Repeat new password',
    profile_password_repeat_placeholder: 'Repeat password',
    profile_password_unchanged_placeholder: 'Empty = unchanged',
    profile_ui_lang: 'UI language',
    profile_search_lang: 'Search language',
    profile_save: 'Save profile',
    profile_saved: 'Profile updated',
    status_errors_label: 'failures',
    status_ready_scan: "Ready. Press 'Scan library' to index your photos.",
    scan_modal_title: 'Scan library',
    scan_modal_text: 'Do you want to start a full library scan now?',
    scan_modal_close: 'Close',
    scan_modal_cancel: 'Cancel',
    scan_modal_start: 'Start scan',
  },
};

const APP_VIEW_KEYS = new Set(['timeline', 'favorites', 'steder', 'kameraer', 'mapper', 'personer', 'settings']);

function resolveUiLanguage(lang) {
  return UI_LANGUAGES.has(lang) ? lang : 'da';
}

function tr(key) {
  const lang = resolveUiLanguage(state.uiLanguage || 'da');
  const dict = I18N[lang] || I18N.da;
  return (dict[key] || I18N.da[key] || key);
}

function updateAiToggleButton() {
  if (!els.aiStopBtn) return;
  const running = !!state.aiRunning;
  els.aiStopBtn.textContent = running ? tr('btn_stop_ai') : tr('btn_start_ai');
  els.aiStopBtn.classList.toggle('danger', running);
}

function navLabels() {
  return {
    timeline: [tr('view_timeline_title'), tr('view_timeline_sub')],
    favorites: [tr('view_favorites_title'), tr('view_favorites_sub')],
    steder: [tr('view_steder_title'), tr('view_steder_sub')],
    kameraer: [tr('view_kameraer_title'), tr('view_kameraer_sub')],
    mapper: [tr('view_mapper_title'), tr('view_mapper_sub')],
    personer: [tr('view_personer_title'), tr('view_personer_sub')],
    settings: [tr('view_settings_title'), tr('view_settings_sub')],
  };
}

let state = {
  items: [],
  selectedId: null,
  view: "timeline",
  sort: "date_desc",
  q: "",
  scanning: false,
  selectedIndex: -1,
  folder: null,
  // logs
  logsRunning: true,
  logsAfter: 0,
  // people view state
  people: [],
  personView: { mode: 'list', personId: null, personName: null },
  showHiddenPeople: false,
  mapperPath: "",
  mapperFolders: [],
  mapperEditMode: false,
  mapperSelectedFolders: new Set(),
  mapperTreeOpen: false,
  mapperTreeExpanded: new Set([""]),
  currentUser: {
    id: APP_PROFILE.id || null,
    username: APP_PROFILE.username || '',
    role: APP_PROFILE.role || 'user',
  },
  uiLanguage: resolveUiLanguage(APP_PROFILE.ui_language || 'da'),
  searchLanguage: resolveUiLanguage(APP_PROFILE.search_language || 'da'),
  aiRunning: false,
};

const MAPPER_TREE_UI_STATE_KEY = 'fjordlens.mapperTreeUi.v1';

function _loadMapperTreeUiState() {
  try {
    const raw = localStorage.getItem(MAPPER_TREE_UI_STATE_KEY);
    if (!raw) return;
    const parsed = JSON.parse(raw);
    if (parsed && typeof parsed === 'object') {
      state.mapperTreeOpen = !!parsed.open;
      const expanded = Array.isArray(parsed.expanded) ? parsed.expanded : [];
      const cleaned = expanded
        .map(v => _normalizeMapperPath(v))
        .filter(v => v === '' || !!v);
      state.mapperTreeExpanded = new Set(['', ...cleaned]);
    }
  } catch {}
}

function _saveMapperTreeUiState() {
  try {
    const expanded = Array.from(state.mapperTreeExpanded || []).map(v => _normalizeMapperPath(v));
    localStorage.setItem(MAPPER_TREE_UI_STATE_KEY, JSON.stringify({
      open: !!state.mapperTreeOpen,
      expanded: Array.from(new Set(['', ...expanded])),
    }));
  } catch {}
}

_loadMapperTreeUiState();

function _expandMapperAncestors(path) {
  const parts = String(path || '').split('/').filter(Boolean);
  let acc = '';
  state.mapperTreeExpanded.add('');
  for (const part of parts) {
    acc = acc ? `${acc}/${part}` : part;
    state.mapperTreeExpanded.add(acc);
  }
  _saveMapperTreeUiState();
}

function _buildMapperTree(paths) {
  const nodes = new Map();
  nodes.set('', { path: '', name: 'uploads', children: new Set() });
  for (const rawPath of (paths || [])) {
    const safePath = _normalizeMapperPath(rawPath);
    if (!safePath) continue;
    const parts = safePath.split('/').filter(Boolean);
    let parent = '';
    let acc = '';
    for (const part of parts) {
      acc = acc ? `${acc}/${part}` : part;
      if (!nodes.has(acc)) nodes.set(acc, { path: acc, name: part, children: new Set() });
      if (!nodes.has(parent)) nodes.set(parent, { path: parent, name: parent || 'uploads', children: new Set() });
      nodes.get(parent).children.add(acc);
      parent = acc;
    }
  }
  return nodes;
}

function renderMapperTree() {
  if (!els.mapperTreeNav) return;
  if (state.view !== 'mapper' || !state.mapperTreeOpen) {
    if (els.mapperNavMenu) els.mapperNavMenu.classList.add('hidden');
    els.mapperTreeNav.classList.add('hidden');
    return;
  }

  if (els.mapperNavMenu) els.mapperNavMenu.classList.remove('hidden');

  const tree = _buildMapperTree(state.mapperFolders || []);
  _expandMapperAncestors(state.mapperPath || '');
  const root = tree.get('');
  const rootChildren = root ? Array.from(root.children) : [];

  els.mapperTreeNav.classList.remove('hidden');
  if (!rootChildren.length) {
    els.mapperTreeNav.innerHTML = `<div class="mini-label">${escapeHtml(tr('empty_mapper_tree'))}</div>`;
    return;
  }
  els.mapperTreeNav.innerHTML = '';

  const renderNode = (path, depth = 0) => {
    const node = tree.get(path);
    if (!node) return;

    const children = Array.from(node.children || []).sort((a, b) => {
      const an = (tree.get(a)?.name || a).toLocaleLowerCase('da-DK');
      const bn = (tree.get(b)?.name || b).toLocaleLowerCase('da-DK');
      return an.localeCompare(bn, 'da-DK');
    });
    const hasChildren = children.length > 0;
    const isExpanded = state.mapperTreeExpanded.has(path) || String(state.mapperPath || '').startsWith(path ? `${path}/` : '');

    const row = document.createElement('div');
    row.className = 'mapper-tree-item';
    row.style.paddingLeft = `${depth * 14}px`;

    const caret = document.createElement('button');
    caret.className = 'mapper-tree-caret';
    caret.type = 'button';
    caret.textContent = hasChildren ? (isExpanded ? '▾' : '▸') : '';
    caret.disabled = !hasChildren;
    if (!hasChildren) caret.style.visibility = 'hidden';
    if (hasChildren) {
      caret.title = isExpanded ? 'Fold mappe sammen' : 'Fold mappe ud';
      caret.setAttribute('aria-label', isExpanded ? 'Fold mappe sammen' : 'Fold mappe ud');
      caret.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        if (state.mapperTreeExpanded.has(path)) state.mapperTreeExpanded.delete(path);
        else state.mapperTreeExpanded.add(path);
        _saveMapperTreeUiState();
        renderMapperTree();
      });
    }
    row.appendChild(caret);

    const link = document.createElement('button');
    link.className = 'mapper-tree-link' + (String(state.mapperPath || '') === path ? ' active' : '');
    link.type = 'button';
    link.textContent = node.name;
    link.addEventListener('click', async () => {
      state.mapperPath = path;
      state.folder = path || null;
      _expandMapperAncestors(path);
      renderMapperContext(path);
      await loadMapperTools(path);
      await loadPhotos();
    });
    row.appendChild(link);
    els.mapperTreeNav.appendChild(row);

    if (hasChildren && isExpanded) {
      for (const ch of children) renderNode(ch, depth + 1);
    }
  };

  for (const ch of rootChildren.sort((a, b) => {
    const an = (tree.get(a)?.name || a).toLocaleLowerCase('da-DK');
    const bn = (tree.get(b)?.name || b).toLocaleLowerCase('da-DK');
    return an.localeCompare(bn, 'da-DK');
  })) {
    renderNode(ch, 0);
  }
}

function _normalizeMapperPath(path) {
  const raw = String(path || '').replace(/\\/g, '/').trim();
  if (!raw) return '';
  return raw
    .split('/')
    .map(s => s.trim())
    .filter(s => s && s !== '.' && s !== '..')
    .join('/');
}

function _readRouteStateFromUrl() {
  try {
    const url = new URL(window.location.href);
    const viewRaw = String(url.searchParams.get('view') || '').trim().toLowerCase();
    const view = APP_VIEW_KEYS.has(viewRaw) ? viewRaw : null;
    const mapperPath = _normalizeMapperPath(url.searchParams.get('mappe') || url.searchParams.get('folder') || '');
    return { view, mapperPath };
  } catch {
    return { view: null, mapperPath: '' };
  }
}

function _syncRouteStateToUrl() {
  try {
    const url = new URL(window.location.href);
    if (state.view && state.view !== 'timeline') {
      url.searchParams.set('view', state.view);
    } else {
      url.searchParams.delete('view');
    }
    if (state.view === 'mapper' && state.mapperPath) {
      url.searchParams.set('mappe', state.mapperPath);
    } else {
      url.searchParams.delete('mappe');
      url.searchParams.delete('folder');
    }
    const next = `${url.pathname}${url.search}${url.hash}`;
    const cur = `${window.location.pathname}${window.location.search}${window.location.hash}`;
    if (next !== cur) {
      window.history.replaceState({ view: state.view, mappe: state.mapperPath || '' }, '', next);
    }
  } catch {}
}

// mark initial view for CSS targeting
document.body.classList.add("view-timeline");

// Map state for "Steder"
let placesMap = null;
let placesSourceReady = false;

function showStatus(text, type = "ok") {
  els.status.textContent = text;
  els.status.classList.remove("hidden", "ok", "err");
  els.status.classList.add(type);
}
function hideStatus() {
  els.status.classList.add("hidden");
}

function fmtBytes(bytes) {
  if (bytes == null) return "-";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let val = Number(bytes);
  let idx = 0;
  while (val >= 1024 && idx < units.length - 1) {
    val /= 1024;
    idx++;
  }
  return `${val.toFixed(val >= 10 || idx === 0 ? 0 : 1)} ${units[idx]}`;
}

function fmtDims(w, h) {
  if (!w || !h) return "-";
  return `${w} × ${h}`;
}

function escapeHtml(s) {
  if (s === null || s === undefined) return '';
  return String(s).replace(/[&<>"'`]/g, (ch) => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;',
    '`': '&#96;'
  })[ch]);
}

function fmtDate(s) {
  if (!s) return "-";
  try {
    const locale = (state.uiLanguage === 'en') ? 'en-GB' : 'da-DK';
    return new Date(s).toLocaleString(locale);
  } catch {
    return s;
  }
}

function renderStats() {
  const inPeople = (state.view === 'personer');
  if (els.photoCountLabel) els.photoCountLabel.textContent = inPeople ? tr('stat_people') : tr('stat_photos');
  if (els.favoriteCountLabel) els.favoriteCountLabel.textContent = tr('stat_favorites');
  if (els.selectedCountLabel) els.selectedCountLabel.textContent = tr('stat_selected');
  const showHiddenLabel = document.querySelector('label[for="showHiddenToggle"]');
  if (showHiddenLabel) showHiddenLabel.textContent = tr('stat_show_hidden');
  if (els.statFavorites) els.statFavorites.style.display = inPeople ? 'none' : '';
  if (els.statSelected) els.statSelected.style.display = inPeople ? 'none' : '';

  if (inPeople) {
    if (els.photoCount) els.photoCount.textContent = Array.isArray(state.people) ? state.people.length : 0;
  } else {
    if (els.photoCount) els.photoCount.textContent = state.items.length;
    if (els.favoriteCount) els.favoriteCount.textContent = state.items.filter(i => i.favorite).length;
    if (els.selectedCount) els.selectedCount.textContent = state.selectedId ? "1" : "0";
  }
}

function renderEmpty(message) {
  els.empty.innerHTML = `<div>${message}</div>`;
  els.empty.classList.remove("hidden");
}

function hideEmpty() {
  els.empty.classList.add("hidden");
}

function setDetail(item) {
  if (!item) {
    els.detailEmpty.classList.remove("hidden");
    els.detailContent.classList.add("hidden");
    return;
  }

  els.detailEmpty.classList.add("hidden");
  els.detailContent.classList.remove("hidden");

  if (item.thumb_url) {
    els.detailThumb.src = item.thumb_url;
    els.detailThumb.style.display = "block";
  } else {
    els.detailThumb.removeAttribute("src");
    els.detailThumb.style.display = "none";
  }

  els.detailName.textContent = item.filename || "-";
  els.detailPath.textContent = item.rel_path || "-";
  els.detailDate.textContent = fmtDate(item.captured_at || item.modified_fs || item.created_fs);
  // Prefill date editor
  try {
    const iso = (item.captured_at || item.modified_fs || item.created_fs || '').toString();
    if (els.dateInput && iso) {
      const d = new Date(iso);
      const y = d.getFullYear();
      const m = String(d.getMonth()+1).padStart(2,'0');
      const da = String(d.getDate()).padStart(2,'0');
      const hh = String(d.getHours()).padStart(2,'0');
      const mm = String(d.getMinutes()).padStart(2,'0');
      els.dateInput.value = `${y}-${m}-${da}T${hh}:${mm}`;
    }
  } catch {}
  els.detailSize.textContent = fmtBytes(item.file_size);
  els.detailDims.textContent = fmtDims(item.width, item.height);
  els.detailDevice.textContent = (item.device_label || [item.camera_make, item.camera_model].filter(Boolean).join(" ") ) || "-";
  els.detailLens.textContent = (item.lens_label || item.lens_model) || "-";
  if (item.gps_lat != null && item.gps_lon != null) {
    els.detailGps.textContent = `${Number(item.gps_lat).toFixed(5)}, ${Number(item.gps_lon).toFixed(5)}`;
  } else {
    els.detailGps.textContent = item.gps_name || "-";
  }
  els.detailAiTags.textContent = (item.ai_tags && item.ai_tags.length) ? item.ai_tags.join(", ") : "-";
  const geo = (item.metadata_json && item.metadata_json.geo) ? item.metadata_json.geo : {};
  els.detailCountry.textContent = geo.country || "-";
  els.detailCity.textContent = geo.city || "-";
  els.rawMeta.textContent = JSON.stringify(item.metadata_json || {}, null, 2);
  els.favoriteBtn.textContent = item.favorite ? "★" : "☆";

  // Click on thumbnail in detail opens viewer
  els.detailThumb.onclick = () => {
    const idx = state.items.findIndex(i => i.id === item.id);
    if (idx >= 0) openViewer(idx);
  };
}

function getSizeLabel(w, h) {
  if (!w || !h) return "";
  const area = w * h;
  if (area >= 2500 * 2500) return "XL";
  if (area >= 1200 * 1200) return "M";
  if (area >= 600 * 600) return "SM";
  return "XS";
}

function cardHTML(item) {
  const thumb = item.thumb_url
    ? `<div class="card-thumb"><img loading="lazy" src="${item.thumb_url}" alt=""></div>`
    : `<div class="card-thumb placeholder">${item.is_video ? '🎬 Video' : escapeHtml(tr('no_thumb'))}</div>`;
  const videoOverlay = item.is_video
    ? `<div class="video-badge" aria-label="Video" title="Video"><span class="video-badge-icon" aria-hidden="true"></span></div>`
    : "";

  // Gridkort uden extra tekst/metadata – kun selve billedet
  return `${thumb}${videoOverlay}`;
}

function renderGrid() {
  // Toggle fixed-width columns for folder view
  if (els.grid) els.grid.classList.toggle("folders-view", state.view === "mapper");
  if (els.mapperTools) els.mapperTools.classList.add("hidden");
  // Always hide special panels first
  if (els.settingsPanel) els.settingsPanel.classList.add("hidden");
  if (els.logsPanel) els.logsPanel.classList.add("hidden");
  if (els.placesMapWrap) els.placesMapWrap.classList.add("hidden");
  // Handle Settings view
  if (state.view === "settings") {
    els.grid.innerHTML = "";
    if (els.settingsPanel) els.settingsPanel.classList.remove("hidden");
    if (els.logsPanel) els.logsPanel.classList.remove("hidden");
    return;
  }
  // Handle Places (Steder) view: show map with clusters
  if (state.view === "steder") {
    if (els.placesMapWrap) els.placesMapWrap.classList.remove("hidden");
    els.grid.innerHTML = ""; // hide gallery
    initOrUpdatePlacesMap();
    return;
  }
  // Handle People (Personer) view
  if (state.view === 'personer') {
    if (els.statHiddenToggle) {
      els.statHiddenToggle.style.display = '';
      if (els.showHiddenToggle) els.showHiddenToggle.checked = !!state.showHiddenPeople;
    }
    els.grid.innerHTML = '';
      els.grid.classList.remove('timeline-wrap');
      els.grid.classList.add('gallery-grid');
    const people = state.personView.mode === 'list' ? (state.people || []) : [];
    if (state.personView.mode === 'list') {
      if (!people.length) {
        renderEmpty(tr('empty_people'));
        renderStats();
        setDetail(null);
        return;
      }
      hideEmpty();
      people.forEach(p => appendPersonCard(p));
      renderStats();
      return;
    } else if (state.personView.mode === 'photos') {
      hideEmpty();
      // Ensure the container is not a gallery grid so inner grid can span full width
      els.grid.classList.remove('gallery-grid');
      const head = document.createElement('div');
      head.className = 'timeline-header';
      head.style.cursor = 'pointer';
      head.textContent = `← ${state.personView.personName || 'Person'}`;
      head.addEventListener('click', ()=>{ state.personView = { mode:'list', personId:null, personName:null }; loadPeople(); });
      els.grid.appendChild(head);
      const wrap = document.createElement('div');
      wrap.className = 'timeline-grid';
      els.grid.appendChild(wrap);
      (state.items||[]).forEach(it => appendCardTo(it, wrap));
      renderStats();
      return;
    }
  }
  // Hide hidden-toggle outside People view
  if (state.view !== 'personer' && els.statHiddenToggle) {
    els.statHiddenToggle.style.display = 'none';
  }
  // Timeline view: group by year-month headers
  if (state.view === "timeline") {
    els.grid.innerHTML = "";
    // Ensure vertical stacking container (not the gallery grid)
    els.grid.classList.remove('gallery-grid');
    els.grid.classList.add('timeline-wrap');
    hideEmpty();
    const items = state.items.slice();
    if (!items.length) {
      renderEmpty(tr('empty_no_photos'));
      renderStats();
      setDetail(null);
      return;
    }
    const groups = new Map(); // key: YYYY-MM label
    for (const it of items) {
      const d = new Date(it.captured_at || it.modified_fs || it.created_fs || Date.now());
      const y = d.getFullYear();
      const m = d.toLocaleString((state.uiLanguage === 'en') ? 'en-GB' : 'da-DK', { month: "long" });
      const key = `${y}-${String(d.getMonth()+1).padStart(2,'0')}`;
      const label = `${m} ${y}`;
      if (!groups.has(key)) groups.set(key, { label, arr: [] });
      groups.get(key).arr.push(it);
    }
    // Sort groups according to selection (date_desc or date_asc)
    const asc = state.sort === 'date_asc';
    const ordered = Array.from(groups.entries()).sort((a,b)=> {
      if (a[0] === b[0]) return 0;
      return asc ? (a[0] > b[0] ? 1 : -1) : (a[0] < b[0] ? 1 : -1);
    });
    for (const [, grp] of ordered) {
      const h = document.createElement('div');
      h.className = 'timeline-header';
      h.textContent = grp.label;
      const wrap = document.createElement('div');
      wrap.className = 'timeline-grid';
      els.grid.appendChild(h);
      els.grid.appendChild(wrap);
      grp.arr.forEach(it => appendCardTo(it, wrap));
    }
    if (!state.items.some(i => i.id === state.selectedId)) {
      state.selectedId = null; setDetail(null);
    }
    renderStats();
    return;
  }

  // Default views (mapper, etc.)
  els.grid.innerHTML = "";
  if (state.view === "mapper" && els.mapperTools) {
    els.mapperTools.classList.remove("hidden");
  }
  // Restore gallery grid layout for non-timeline views
  els.grid.classList.add('gallery-grid');
  els.grid.classList.remove('timeline-wrap');
  if (!state.items.length && state.view !== "mapper") {
    const msg = state.view === "personer"
      ? tr('empty_people')
      : tr('empty_no_matches');
    renderEmpty(msg);
    renderStats();
    setDetail(null);
    return;
  }
  hideEmpty();

  const items = state.items.slice();
  if (state.view === "mapper") {
    const current = String(state.mapperPath || "");
    const groupMap = new Map();
    const includeFolder = (folderPath) => {
      if (!groupMap.has(folderPath)) groupMap.set(folderPath, []);
    };
    const immediateChild = (folderPath, parentPath) => {
      const f = String(folderPath || '');
      const p = String(parentPath || '');
      if (!f) return null;
      if (!p) {
        const seg = f.split('/').filter(Boolean)[0] || null;
        return seg || null;
      }
      if (f === p || !f.startsWith(p + '/')) return null;
      const rest = f.slice(p.length + 1);
      const seg = rest.split('/').filter(Boolean)[0] || null;
      return seg ? `${p}/${seg}` : null;
    };

    for (const it of items) {
      const rel = String(it.rel_path || '');
      const folder = rel.includes('/') ? rel.split('/').slice(0, -1).join('/') : '';
      const child = immediateChild(folder, current);
      if (!child) continue;
      includeFolder(child);
      groupMap.get(child).push(it);
    }

    for (const f of (state.mapperFolders || [])) {
      const child = immediateChild(String(f || ''), current);
      if (child) includeFolder(child);
    }

    const sorted = Array.from(groupMap.keys()).sort((a, b) => a.localeCompare(b, 'da-DK'));
    if (!sorted.length) {
      hideEmpty();
      renderStats();
      setDetail(null);
      return;
    }
    for (const folderPath of sorted) {
      const arr = groupMap.get(folderPath) || [];
      const title = folderPath.split('/').filter(Boolean).pop() || folderPath;
      appendFolderCard(folderPath, arr, {
        title,
        onOpen: () => {
          state.mapperPath = folderPath;
          state.folder = folderPath;
          loadMapperTools(folderPath);
          loadPhotos();
        },
      });
    }
  } else {
    items.forEach(item => appendCard(item));
  }

  if (!state.items.some(i => i.id === state.selectedId)) {
    state.selectedId = null;
    setDetail(null);
  }
  renderStats();
}

function appendCardTo(item, container) {
  const card = document.createElement("article");
  card.className = "photo-card" + (state.selectedId === item.id ? " active" : "");
  card.innerHTML = cardHTML(item);
  // If viewing 'Ukendte' person folder, overlay detected face boxes on the thumbnail
  try {
    if (state.personView && state.personView.personId === 'unknown' && item && Array.isArray(item.faces) && item.faces.length) {
      const thumb = card.querySelector('.card-thumb');
      const img = thumb && thumb.querySelector('img');
      if (thumb && img) {
        thumb.style.position = 'relative';
        img.style.objectFit = 'contain';
        img.style.background = '#0d1016';
        const faces = item.faces.slice(0, 2);
        const draw = () => {
          try {
            const cw = thumb.clientWidth; const ch = thumb.clientHeight;
            const iw = img.naturalWidth || (item.width||1); const ih = img.naturalHeight || (item.height||1);
            const scale = Math.min(cw/iw, ch/ih);
            const dw = iw*scale; const dh = ih*scale;
            const offX = (cw - dw)/2; const offY = (ch - dh)/2;
            faces.forEach(fc => {
              const box = document.createElement('div');
              box.style.position = 'absolute';
              box.style.left = `${offX + (fc.x*dw)}px`;
              box.style.top = `${offY + (fc.y*dh)}px`;
              box.style.width = `${fc.w*dw}px`;
              box.style.height = `${fc.h*dh}px`;
              box.style.border = '2px solid #e33';
              box.style.boxShadow = '0 0 0 1px rgba(0,0,0,0.4) inset';
              box.style.pointerEvents = 'none';
              thumb.appendChild(box);
            });
          } catch {}
        };
        if (img.complete) draw(); else img.addEventListener('load', draw, { once: true });
      }
    }
  } catch {}
  // Single-click opens viewer directly
  card.addEventListener("click", (ev) => {
    state.selectedId = item.id;
    setDetail(item);
    const idx = state.items.findIndex(i => i.id === item.id);
    if (idx >= 0) openViewer(idx);
  });
  (container || els.grid).appendChild(card);
}

function appendCard(item){ return appendCardTo(item, els.grid); }

function appendFolderCard(folder, arr, opts = {}) {
  const previews = arr.slice(0, 4);
  const card = document.createElement("article");
  const isSelected = !!(state.mapperEditMode && state.mapperSelectedFolders && state.mapperSelectedFolders.has(folder));
  card.className = "photo-card folder-card" + (isSelected ? " selected" : "");
  const cells = previews.map(p => p.thumb_url ? `<img src="${p.thumb_url}" alt="">` : "").join("");
  const title = opts.title || folder;
  const selBadge = state.mapperEditMode ? `<span class="folder-select-badge">${isSelected ? '✓' : ''}</span>` : '';
  card.innerHTML = `
    <div class="card-thumb folder-mosaic"><div class="folder-grid">${cells}</div>${selBadge}</div>
    <div class="card-body">
      <h4 class="card-title">${title}</h4>
      <div class="card-meta">
        <span>${arr.length} elementer</span>
        <span>Mapper</span>
      </div>
    </div>`;
  card.addEventListener("click", () => {
    if (state.mapperEditMode) {
      toggleMapperFolderSelection(folder);
      return;
    }
    if (typeof opts.onOpen === 'function') {
      opts.onOpen();
      return;
    }
    state.view = "timeline";
    state.folder = folder === "(root)" ? "" : folder;
    document.querySelectorAll(".nav-item").forEach(btn => btn.classList.remove("active"));
    loadPhotos();
  });
  els.grid.appendChild(card);
}

function appendPersonCard(p) {
  const card = document.createElement('article');
  card.className = 'photo-card';
  const img = p.thumb_url ? `<img src="${p.thumb_url}" alt="${p.name}">` : `<div class="card-thumb placeholder">🙂</div>`;
  card.innerHTML = `
    <div class="card-thumb">${img}</div>
    <div class="card-body">
      <h4 class="card-title">${escapeHtml(p.name || 'Ukendt')}</h4>
      <div class="card-meta"><span>${p.count||0} billede(r)</span></div>
      <div class="pills">${p.hidden ? '<span class="pill">Skjult</span>' : ''}</div>
      <div class="actions" style="margin-top:6px;display:flex;gap:6px;">
        <button class="btn tiny" data-act="rename">Navngiv</button>
        ${p.id==='unknown' ? '' : `<button class="btn tiny ${p.hidden?'':'danger'}" data-act="${p.hidden?'unhide':'hide'}">${p.hidden?'Vis':'Skjul'}</button>`}
      </div>
    </div>
  `;
  // Klik på hele kortet åbner personens billeder (undtagen når man klikker på en knap)
  card.addEventListener('click', (e)=>{
    if (e.target && e.target.closest('[data-act]')) return;
    if (p.id === 'unknown') loadPersonPhotos('unknown', 'Ukendte');
    else loadPersonPhotos(p.id, p.name);
  });
  card.querySelector('[data-act="rename"]').addEventListener('click', async ()=>{
    const nv = prompt('Nyt navn for person:', p.name || '');
    if (!nv) return;
    if (p.id === 'unknown') { showStatus('Ukendte kan ikke omdøbes', 'err'); return; }
    try {
      const r = await fetch(`/api/people/${p.id}/rename`, { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ name: nv })});
      const d = await r.json();
      if (!r.ok || !d.ok) { showStatus(d.error || 'Kunne ikke omdøbe', 'err'); return; }
      showStatus('Navn opdateret', 'ok');
      loadPeople();
    } catch { showStatus('Fejl ved omdøbning', 'err'); }
  });
  const hideBtn = card.querySelector('[data-act="hide"]');
  if (hideBtn) {
    hideBtn.addEventListener('click', async ()=>{
      if (!confirm('Skjul denne person fra listen?')) return;
      try {
        const r = await fetch(`/api/people/${p.id}/hide`, { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ hidden: true })});
        const d = await r.json();
        if (!r.ok || !d.ok) { showStatus(d.error || 'Kunne ikke skjule', 'err'); return; }
        showStatus('Person skjult', 'ok');
        loadPeople();
      } catch { showStatus('Fejl ved skjul', 'err'); }
    });
  }
  const unhideBtn = card.querySelector('[data-act="unhide"]');
  if (unhideBtn) {
    unhideBtn.addEventListener('click', async ()=>{
      try {
        const r = await fetch(`/api/people/${p.id}/hide`, { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ hidden: false })});
        const d = await r.json();
        if (!r.ok || !d.ok) { showStatus(d.error || 'Kunne ikke gendanne', 'err'); return; }
        showStatus('Person vist igen', 'ok');
        loadPeople();
      } catch { showStatus('Fejl ved gendannelse', 'err'); }
    });
  }
  els.grid.appendChild(card);
}

// Viewer controls
function openViewer(index) {
  state.selectedIndex = index;
  const it = state.items[index];
  if (!it || !it.original_url) return;
  if (!els.viewer) return;
  // Toggle media elements
  if (els.viewerImg) {
    els.viewerImg.style.display = it.is_video ? 'none' : 'block';
    if (!it.is_video) {
      // Always use the server-provided original_url (it serves a viewable copy for HEIC/HEIF)
      els.viewerImg.src = it.original_url || it.thumb_url || '';
    }
    if (it.is_video) els.viewerImg.removeAttribute('src');
  }
  if (els.viewerVideo) {
    els.viewerVideo.style.display = it.is_video ? 'block' : 'none';
    try { els.viewerVideo.pause(); } catch(_) {}
    if (it.is_video) {
      els.viewerVideo.src = it.original_url;
      try { els.viewerVideo.play().catch(()=>{}); } catch(_) {}
    } else {
      els.viewerVideo.removeAttribute('src');
    }
  }
  els.viewer.classList.remove("hidden");
  // Populate slide-out info with the current item's metadata
  try {
    const title = (it.filename || it.rel_path || "-");
    const date = fmtDate(it.captured_at || it.modified_fs || it.created_fs);
    const dims = it.width && it.height ? `${it.width} × ${it.height}` : "-";
    const dev = it.device_label || (it.camera_make || "");
    const lens = it.lens_label || it.lens_model || "-";
    const gps = (it.gps_lat!=null && it.gps_lon!=null) ? `${Number(it.gps_lat).toFixed(5)}, ${Number(it.gps_lon).toFixed(5)}` : (it.gps_name || "-");
    const tags = (it.ai_tags && it.ai_tags.length) ? it.ai_tags.join(", ") : "-";
    const dl = (it.download_url || it.original_url || '#');
    const q = (id)=>document.getElementById(id);
    q('viTitle').textContent = title;
    q('viDate').textContent = date;
    q('viSize').textContent = fmtBytes(it.file_size);
    q('viDims').textContent = dims;
    q('viDevice').textContent = dev || '-';
    q('viLens').textContent = lens;
    q('viGps').textContent = gps;
    q('viTags').textContent = tags;
    try {
      const geo = (it.metadata_json && it.metadata_json.geo) ? it.metadata_json.geo : {};
      q('viCountry').textContent = geo.country || '-';
      q('viCity').textContent = geo.city || '-';
    } catch {}
    const viDL = q('viDownload'); if (viDL) viDL.href = dl;
    try { const fbtn = q('viFavoriteBtn'); if (fbtn) fbtn.textContent = it.favorite ? '★' : '☆'; } catch {}
  } catch {}

  // Position the info panel so it appears to slide out from "under" the media
  try {
    const vi = document.getElementById('viewerInfo');
    if (vi) {
      const mediaEl = (it.is_video ? els.viewerVideo : els.viewerImg);
      const r = mediaEl.getBoundingClientRect();
      // Hide panel "under" image: set its left so it sits fully beneath media
      const w = vi.offsetWidth || 360;
      const underOffset = 8; // tuck a bit under the image
      vi.style.left = `${Math.round(r.right - w - underOffset)}px`;
      vi.style.right = 'auto';
      // Size/position vertically to be slightly smaller than image (16px padding on top/bottom)
      const vPad = 16;
      const top = Math.max(0, Math.round(r.top + vPad));
      const bottomGap = Math.max(0, Math.round(window.innerHeight - (r.bottom - vPad)));
      vi.style.top = `${top}px`;
      vi.style.bottom = `${bottomGap}px`;
      vi.style.height = '';
    }
  } catch {}
  if (els.viewerOpenOrig) {
    const dl = (it.download_url || it.original_url || '');
    els.viewerOpenOrig.href = dl;
    els.viewerOpenOrig.download = it.filename || '';
    els.viewerOpenOrig.style.display = 'inline-block';
  }
}
function closeViewer() {
  if (!els.viewer) return;
  els.viewer.classList.add("hidden");
  if (els.viewerImg) els.viewerImg.removeAttribute("src");
  if (els.viewerVideo) { try { els.viewerVideo.pause(); } catch(_) {} els.viewerVideo.removeAttribute('src'); }
}
function nextViewer(step=1) {
  if (state.selectedIndex < 0) return;
  const n = state.items.length;
  state.selectedIndex = (state.selectedIndex + step + n) % n;
  const it = state.items[state.selectedIndex];
  if (!it || !it.original_url) return;
  if (it.is_video) {
    if (els.viewerVideo) {
      try { els.viewerVideo.pause(); } catch(_) {}
      els.viewerVideo.style.display = 'block';
      if (els.viewerImg) els.viewerImg.style.display = 'none';
      els.viewerVideo.src = it.original_url;
      try { els.viewerVideo.play().catch(()=>{}); } catch(_) {}
    }
  } else {
    if (els.viewerImg) {
      els.viewerImg.style.display = 'block';
      // Use original_url for full-resolution viewing (server handles HEIC conversion)
      els.viewerImg.src = it.original_url || it.thumb_url || '';
    }
    if (els.viewerVideo) { try { els.viewerVideo.pause(); } catch(_) {} els.viewerVideo.style.display = 'none'; }
  }
  if (els.viewerOpenOrig) {
    const dl = (it.download_url || it.original_url || '');
    els.viewerOpenOrig.href = dl;
    els.viewerOpenOrig.download = it.filename || '';
  }
}

async function loadPhotos() {
  const qs = new URLSearchParams({
    q: state.q,
    view: state.view,
    sort: state.sort,
    folder: state.folder || "",
    search_lang: state.searchLanguage || 'da',
  });

  const res = await fetch(`/api/photos?${qs.toString()}`);
  const data = await res.json();
  state.items = data.items || [];

  const labels = navLabels();
  const [title, subtitle] = labels[state.view] || ["FjordLens", ""];
  els.viewTitle.textContent = title;
  els.viewSubtitle.textContent = subtitle;

  renderGrid();
}

async function loadPeople() {
  try {
    const url = state.showHiddenPeople ? '/api/people?include_hidden=1' : '/api/people';
    const res = await fetch(url);
    const data = await res.json();
    state.people = data.items || [];
  } catch { state.people = []; }
  // Update headings for People view
  const labels = navLabels();
  const [title, subtitle] = labels['personer'] || ["Personer", ""];
  if (els.viewTitle) els.viewTitle.textContent = title;
  if (els.viewSubtitle) els.viewSubtitle.textContent = subtitle;
  renderGrid();
}

async function loadPersonPhotos(pid, name) {
  try {
    const url = (pid === 'unknown') ? '/api/people/unknown/photos-faces' : `/api/people/${pid}/photos`;
    const res = await fetch(url);
    const data = await res.json();
    state.items = data.items || [];
    state.personView = { mode: 'photos', personId: pid, personName: name };
  } catch { state.items = []; }
  renderGrid();
}

async function fetchUploadDestinationConfig(destination = null) {
  let url = '/api/settings/upload-destination';
  if (destination) url += `?destination=${encodeURIComponent(destination)}`;
  const res = await fetch(url);
  const data = await res.json();
  return { res, data };
}

async function uploadFiles(fileList, options = {}) {
  ensureUploadOverlayRefs();
  const files = Array.from(fileList || []).filter(f => !!f && f.name);
  if (!files.length) return;
  const fd = new FormData();
  const meta = [];
  for (const f of files) { fd.append('files', f, f.name); meta.push({ name: f.name, lastModified: f.lastModified }); }
  fd.append('meta', JSON.stringify(meta));
  const destination = (options && options.destination) ? String(options.destination) : '';
  const subdir = (options && Object.prototype.hasOwnProperty.call(options, 'subdir')) ? String(options.subdir || '') : null;
  if (destination) fd.append('destination', destination);
  if (subdir !== null) fd.append('subdir', subdir);
  const totalSize = files.reduce((s,f)=>s+ (f.size||0), 0);
  // Show overlay
  if (els.uploadOverlay) { els.uploadOverlay.classList.remove('hidden'); els.uploadOverlay.classList.add('active'); }
  if (els.uploadProgressBar) els.uploadProgressBar.style.width = '0%';
  if (els.uploadProgressText) els.uploadProgressText.textContent = `${files.length} fil(er)`;
  try {
    await new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhr.open('POST', '/api/upload');
      xhr.onload = () => {
        try {
          const data = JSON.parse(xhr.responseText || '{}');
          if (xhr.status >= 200 && xhr.status < 300 && data && data.ok !== false) {
            const saved = (data.saved||[]).length;
            const errs = (data.errors||[]).length;
            showStatus(`Upload fuldført: ${saved} fil(er)${errs?`, fejl: ${errs}`:''}`, errs? 'err':'ok');
            resolve();
          } else {
            showStatus((data && data.error) || 'Upload fejlede', 'err');
            reject(new Error('upload failed'));
          }
        } catch (e) { showStatus('Upload fejlede', 'err'); reject(e); }
      };
      xhr.onerror = () => { showStatus('Upload fejlede (netværk)', 'err'); reject(new Error('net')); };
      xhr.upload.onprogress = (e) => {
        if (!e.lengthComputable) return;
        const pct = Math.round((e.loaded / e.total) * 100);
        if (els.uploadProgressBar) els.uploadProgressBar.style.width = pct + '%';
        if (els.uploadProgressText) {
          const mbLoaded = (e.loaded/1024/1024).toFixed(1);
          const mbTotal = (e.total/1024/1024).toFixed(1);
          els.uploadProgressText.textContent = `${pct}% · ${mbLoaded}/${mbTotal} MB`;
        }
      };
      xhr.send(fd);
    });
    await loadPhotos();
    if (state.view === 'mapper') {
      loadMapperTools();
    }
  } catch (e) {
    console.error(e);
  } finally {
    if (els.uploadOverlay) { els.uploadOverlay.classList.remove('active'); els.uploadOverlay.classList.add('hidden'); }
  }
}

function renderMapperContext(path = '') {
  const p = String(path || '');
  if (els.mapperCurrentPath) {
    els.mapperCurrentPath.textContent = `${tr('mapper_current_folder')}: ${p ? `uploads/${p}` : tr('mapper_root_folder')}`;
  }
  if (els.mapperDropZone) {
    els.mapperDropZone.textContent = `${tr('mapper_drop_here')}: ${p || tr('mapper_root_folder')}`;
    els.mapperDropZone.classList.toggle('hidden', !!state.mapperEditMode);
  }
  if (els.mapperUpBtn) {
    els.mapperUpBtn.textContent = tr('mapper_up');
    els.mapperUpBtn.disabled = !p;
  }
  if (els.mapperEditBtn) {
    els.mapperEditBtn.textContent = state.mapperEditMode ? tr('mapper_done') : tr('mapper_edit');
  }
  if (els.mapperDeleteBtn) {
    const count = state.mapperSelectedFolders ? state.mapperSelectedFolders.size : 0;
    els.mapperDeleteBtn.classList.toggle('hidden', !state.mapperEditMode);
    els.mapperDeleteBtn.disabled = count === 0;
    els.mapperDeleteBtn.textContent = count > 0 ? `${tr('mapper_delete_selected')} (${count})` : tr('mapper_delete_selected');
  }
  if (els.mapperFolderNewInput) els.mapperFolderNewInput.disabled = !!state.mapperEditMode;
  if (els.mapperFolderNewInput) els.mapperFolderNewInput.placeholder = tr('upload_new_folder_placeholder');
  if (els.mapperFolderCreateBtn) {
    els.mapperFolderCreateBtn.disabled = !!state.mapperEditMode;
    els.mapperFolderCreateBtn.textContent = tr('upload_create_folder');
  }
  renderMapperTree();
}

async function loadMapperTools(preferred = null) {
  try {
    const { res, data } = await fetchUploadDestinationConfig('uploads');
    if (!res.ok || !data || !data.ok) return;
    const folders = Array.isArray(data.folders) ? data.folders.filter(f => !!f) : [];
    state.mapperFolders = folders;
    if (state.mapperSelectedFolders && state.mapperSelectedFolders.size) {
      state.mapperSelectedFolders = new Set(
        Array.from(state.mapperSelectedFolders).filter(f => folders.includes(f))
      );
    }
    const wantedRaw = (preferred !== null) ? String(preferred || '') : String(state.mapperPath || data.subdir || '');
    const wanted = _normalizeMapperPath(wantedRaw);
    state.mapperPath = wanted;
    state.folder = wanted || null;
    _expandMapperAncestors(wanted);
    renderMapperContext(state.mapperPath);
    if (state.view === 'mapper') _syncRouteStateToUrl();
  } catch {}
}

async function createMapperFolder() {
  if (!els.mapperFolderNewInput) return;
  const parent = String(state.mapperPath || '');
  const path = (els.mapperFolderNewInput.value || '').trim();
  if (!path) {
    showStatus('Skriv mappenavn først.', 'err');
    return;
  }
  const createBtn = els.mapperFolderCreateBtn;
  const originalLabel = createBtn ? createBtn.textContent : 'Opret mappe';
  try {
    if (createBtn) {
      createBtn.disabled = true;
      createBtn.classList.add('loading');
      createBtn.textContent = 'Opretter...';
    }
    const res = await fetch('/api/settings/upload-folder', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ destination: 'uploads', parent, path }),
    });
    const data = await res.json();
    if (!res.ok || !data || !data.ok) {
      showStatus((data && data.error) || 'Kunne ikke oprette mappe', 'err');
      return;
    }
    els.mapperFolderNewInput.value = '';
    state.mapperFolders = Array.isArray(data.folders) ? data.folders.filter(f => !!f) : [];
    state.mapperPath = parent;
    state.folder = parent || null;
    renderMapperContext(parent);
    await loadPhotos();
    const createdPath = String(data.created || path || '');
    showStatus(`Mappe oprettet: ${createdPath}`, 'ok');
  } catch {
    showStatus('Fejl ved oprettelse af mappe.', 'err');
  } finally {
    if (createBtn) {
      createBtn.classList.remove('loading');
      createBtn.textContent = originalLabel || 'Opret mappe';
      createBtn.disabled = !!state.mapperEditMode;
    }
  }
}

function setMapperEditMode(enabled) {
  state.mapperEditMode = !!enabled;
  if (!state.mapperEditMode) {
    state.mapperSelectedFolders = new Set();
  }
  renderMapperContext(state.mapperPath || '');
  if (state.view === 'mapper') renderGrid();
}

function toggleMapperFolderSelection(folderPath) {
  if (!state.mapperSelectedFolders) state.mapperSelectedFolders = new Set();
  if (state.mapperSelectedFolders.has(folderPath)) state.mapperSelectedFolders.delete(folderPath);
  else state.mapperSelectedFolders.add(folderPath);
  renderMapperContext(state.mapperPath || '');
  if (state.view === 'mapper') renderGrid();
}

async function deleteSelectedMapperFolders() {
  const selected = Array.from(state.mapperSelectedFolders || []);
  if (!selected.length) {
    showStatus('Vælg mindst én mappe at slette.', 'err');
    return;
  }
  const ok = confirm(`Slet ${selected.length} mappe(r) inkl. alt indhold? Dette kan ikke fortrydes.`);
  if (!ok) return;
  const deleteBtn = els.mapperDeleteBtn;
  const originalLabel = deleteBtn ? deleteBtn.textContent : 'Slet valgte';
  try {
    if (deleteBtn) {
      deleteBtn.disabled = true;
      deleteBtn.classList.add('loading');
      deleteBtn.textContent = 'Sletter...';
    }
    const res = await fetch('/api/settings/upload-folder-delete', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ destination: 'uploads', paths: selected }),
    });
    const data = await res.json();
    if (!res.ok || !data || !data.ok) {
      showStatus((data && data.error) || 'Kunne ikke slette mapper', 'err');
      return;
    }
    state.mapperFolders = Array.isArray(data.folders) ? data.folders.filter(f => !!f) : [];
    state.mapperSelectedFolders = new Set();
    setMapperEditMode(false);
    await loadMapperTools(state.mapperPath || '');
    await loadPhotos();
    const deletedCount = Array.isArray(data.deleted) ? data.deleted.length : 0;
    const removedPhotos = Number(data.removed_photos || 0);
    showStatus(`Slettet ${deletedCount} mappe(r) og ${removedPhotos} indekserede filer.`, 'ok');
  } catch {
    showStatus('Fejl ved sletning af mapper.', 'err');
  } finally {
    if (deleteBtn) {
      deleteBtn.classList.remove('loading');
      deleteBtn.textContent = originalLabel || 'Slet valgte';
    }
    renderMapperContext(state.mapperPath || '');
  }
}

let _dragDepth = 0;

function _showGlobalDropOverlay() {
  ensureUploadOverlayRefs();
  if (!els.uploadOverlay) return;
  const canUploadHere = (state.view === 'mapper' && !state.mapperEditMode);
  const targetLabel = state.mapperPath ? `uploads/${state.mapperPath}` : 'uploads (rodmappe)';
  const titleEl = document.querySelector('#uploadOverlay .upload-title');
  if (titleEl) {
    titleEl.textContent = canUploadHere
      ? 'Slip filer for at uploade'
      : 'Gå til Mapper for at uploade';
  }
  if (els.uploadProgressText) {
    els.uploadProgressText.textContent = canUploadHere
      ? `Upload destination: ${targetLabel}`
      : 'Upload er kun aktiv i Mapper-sektionen';
  }
  if (els.uploadProgressBar) {
    els.uploadProgressBar.style.width = canUploadHere ? '100%' : '0%';
  }
  els.uploadOverlay.classList.toggle('upload-ready', canUploadHere);
  els.uploadOverlay.classList.toggle('upload-blocked', !canUploadHere);
  els.uploadOverlay.classList.remove('hidden');
  els.uploadOverlay.classList.add('active');
}

function _hideGlobalDropOverlay() {
  ensureUploadOverlayRefs();
  if (!els.uploadOverlay) return;
  els.uploadOverlay.classList.remove('active', 'upload-ready', 'upload-blocked');
  els.uploadOverlay.classList.add('hidden');
}

window.addEventListener('dragenter', (e) => {
  if (!(e.dataTransfer && e.dataTransfer.types && e.dataTransfer.types.includes('Files'))) return;
  _dragDepth += 1;
  _showGlobalDropOverlay();
});

window.addEventListener('dragover', (e) => {
  if (e.dataTransfer && e.dataTransfer.types && e.dataTransfer.types.includes('Files')) {
    e.preventDefault();
    _showGlobalDropOverlay();
  }
});

window.addEventListener('dragleave', () => {
  _dragDepth = Math.max(0, _dragDepth - 1);
  if (_dragDepth === 0) _hideGlobalDropOverlay();
});

window.addEventListener('drop', async (e) => {
  _dragDepth = 0;
  const hasFiles = !!(e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length);
  if (hasFiles) {
    e.preventDefault();
    const droppedInsideMapperZone = !!(els.mapperDropZone && e.target && els.mapperDropZone.contains(e.target));
    if (state.view !== 'mapper' || state.mapperEditMode) {
      showStatus('Upload er kun aktiv i Mapper-sektionen.', 'err');
    } else if (!droppedInsideMapperZone) {
      const targetSubdir = String(state.mapperPath || '');
      await uploadFiles(e.dataTransfer.files, { destination: 'uploads', subdir: targetSubdir });
      await loadMapperTools(targetSubdir);
      await loadPhotos();
    }
  }
  _hideGlobalDropOverlay();
});

function buildPlacesGeoJSON(items) {
  const feats = [];
  for (const it of items) {
    const lat = it.gps_lat != null ? parseFloat(it.gps_lat) : null;
    const lon = it.gps_lon != null ? parseFloat(it.gps_lon) : null;
    if (isFinite(lat) && isFinite(lon)) {
      feats.push({
        type: "Feature",
        geometry: { type: "Point", coordinates: [lon, lat] },
        properties: {
          id: it.id,
          name: it.filename || "(ukendt)",
          thumb: it.thumb_url || null,
          date: it.captured_at || it.modified_fs || "",
        },
      });
    }
  }
  return { type: "FeatureCollection", features: feats };
}

function initOrUpdatePlacesMap() {
  if (!els.placesMapEl) return;
  // Lazy init map
  if (!placesMap) {
    placesMap = new maplibregl.Map({
      container: els.placesMapEl,
      // Street/label style (Carto Positron GL) without API key
      style: "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
      center: [10, 56],
      zoom: 4,
      pitch: 0,
      bearing: 0,
      dragRotate: false,
      pitchWithRotate: false,
      attributionControl: false,
    });
    // Add attribution including MapLibre (plus source attributions from the style)
    placesMap.addControl(new maplibregl.AttributionControl({
      compact: true,
      customAttribution: "MapLibre"
    }));
    placesMap.addControl(new maplibregl.NavigationControl({ showCompass: false }));
    placesMap.on("load", () => {
      // Add clustered source + layers
      const geo0 = buildPlacesGeoJSON(state.items);
      console.log("[Steder] init features:", geo0.features.length);
      addOrUpdatePlacesSource(geo0);
      addPlacesLayers();
      // Cluster click expands
      placesMap.on("click", "clusters", (e) => {
        const features = placesMap.queryRenderedFeatures(e.point, { layers: ["clusters"] });
        const clusterId = features[0].properties.cluster_id;
        const src = placesMap.getSource("places");
        src.getClusterExpansionZoom(clusterId, (err, zoom) => {
          if (err) return;
          placesMap.easeTo({ center: features[0].geometry.coordinates, zoom });
        });
      });
      // Single point click shows popup
      placesMap.on("click", "unclustered-point", (e) => {
        const f = e.features && e.features[0];
        if (!f) return;
        const p = f.properties || {};
        const html = `
          <div class="places-map-popup">
            ${p.thumb ? `<img class="thumb" src="${p.thumb}" alt="">` : ""}
            <div class="meta">${p.name || ""}</div>
            <div class="meta">${p.date ? new Date(p.date).toLocaleString("da-DK") : ""}</div>
          </div>`;
        new maplibregl.Popup({ offset: 12 })
          .setLngLat(f.geometry.coordinates)
          .setHTML(html)
          .addTo(placesMap);
      });
      placesMap.on("mouseenter", "clusters", () => (placesMap.getCanvas().style.cursor = "pointer"));
      placesMap.on("mouseleave", "clusters", () => (placesMap.getCanvas().style.cursor = ""));
      placesMap.on("mouseenter", "unclustered-point", () => (placesMap.getCanvas().style.cursor = "pointer"));
      placesMap.on("mouseleave", "unclustered-point", () => (placesMap.getCanvas().style.cursor = ""));
      placesSourceReady = true;
      // Render initial HTML markers and keep them updated
      renderPlacesMarkers();
      placesMap.on("moveend", renderPlacesMarkers);
      placesMap.on("zoomend", renderPlacesMarkers);
      placesMap.on("data", (e) => { if (e.sourceId === "places" && e.isSourceLoaded) renderPlacesMarkers(); });
    });
  }
  // Update data if map already loaded
  if (placesMap && placesMap.isStyleLoaded()) {
    const geo = buildPlacesGeoJSON(state.items);
    if (!placesMap.getSource("places")) {
      addOrUpdatePlacesSource(geo);
      addPlacesLayers();
    } else {
      placesMap.getSource("places").setData(geo);
    }
    const banner = document.getElementById("placesBanner");
    if (banner) {
      const n = (geo.features && geo.features.length) || 0;
      if (n === 0) {
        banner.style.display = "block";
        banner.textContent = "Ingen GPS-billeder fundet i visningen";
      } else {
        banner.style.display = "block";
        banner.textContent = `GPS-billeder: ${n}`;
      }
    }
    // Fit bounds to data when entering view
    try {
      if (geo.features && geo.features.length) {
        let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
        for (const f of geo.features) {
          const [x, y] = f.geometry.coordinates;
          if (x < minX) minX = x; if (y < minY) minY = y; if (x > maxX) maxX = x; if (y > maxY) maxY = y;
        }
        const b = [[minX, minY], [maxX, maxY]];
        placesMap.fitBounds(b, { padding: 40, duration: 400, maxZoom: 12 });
      }
    } catch {}
    setTimeout(() => { try { placesMap.resize(); renderPlacesMarkers(); } catch {} }, 50);
  }
}

function addOrUpdatePlacesSource(geo) {
  if (placesMap.getSource("places")) {
    placesMap.getSource("places").setData(geo);
    return;
  }
  placesMap.addSource("places", {
    type: "geojson",
    data: geo,
    cluster: true,
      // Klynger bevares ved tæt zoom; større radius gør dem mere stabile
      clusterMaxZoom: 20,
      clusterRadius: 80,
      clusterMinPoints: 2,
  });
}

function addPlacesLayers() {
  if (placesMap.getLayer("clusters")) return;
  placesMap.addLayer({
    id: "clusters",
    type: "circle",
    source: "places",
    filter: ["has", "point_count"],
    paint: {
      "circle-color": [
        "step",
        ["get", "point_count"],
        "#4f6bdc",
        25, "#4279f4",
        100, "#2c8cff"
      ],
      "circle-radius": ["step", ["get", "point_count"], 18, 25, 24, 100, 30],
      "circle-stroke-color": "#0b1020",
      "circle-stroke-width": 2
    }
  });
  placesMap.addLayer({
    id: "cluster-count",
    type: "symbol",
    source: "places",
    filter: ["has", "point_count"],
    layout: {
      "text-field": ["get", "point_count_abbreviated"],
      "text-size": 12
    },
    paint: { "text-color": "#ffffff" }
  });
  placesMap.addLayer({
    id: "unclustered-point",
    type: "circle",
    source: "places",
    filter: ["!has", "point_count"],
    paint: {
      "circle-color": "#7aa2ff",
      "circle-radius": 7,
      "circle-stroke-color": "#0b1020",
      "circle-stroke-width": 2
    }
  });
}

// HTML-baserede markører (små thumbs + tæller) – deaktiveret for stabilitet.
// Vi bruger i stedet MapLibres egne cluster/point-lag ovenfor.
let placesHtmlMarkers = [];
function clearPlacesMarkers() {
  for (const m of placesHtmlMarkers) {
    try { m.remove(); } catch {}
  }
  placesHtmlMarkers = [];
}

function renderPlacesMarkers() {
  if (!placesMap || !placesMap.isStyleLoaded()) return;
  const src = placesMap.getSource("places");
  if (!src) return;
  clearPlacesMarkers();

  try {
    const clusterFeats = placesMap.queryRenderedFeatures({ layers: ["clusters"] }) || [];
    for (const f of clusterFeats) {
      const cid = f && f.properties ? f.properties.cluster_id : null;
      const coords = f && f.geometry && f.geometry.coordinates ? f.geometry.coordinates : null;
      if (cid == null || !coords) continue;
      try {
        src.getClusterLeaves(cid, 1, 0, (err, leaves) => {
          const el = document.createElement("div");
          el.className = "cluster-marker";
          if (!err && leaves && leaves[0] && leaves[0].properties) {
            const thumb = leaves[0].properties.thumb || null;
            if (thumb) el.style.backgroundImage = `url(${thumb})`;
          }
          const badge = document.createElement("span");
          badge.className = "cluster-badge";
          badge.textContent = String(f.properties.point_count_abbreviated || f.properties.point_count || "");
          el.appendChild(badge);
          el.addEventListener("click", () => openClusterSheet(cid));
          const m = new maplibregl.Marker({ element: el, anchor: "center" })
            .setLngLat(coords)
            .addTo(placesMap);
          placesHtmlMarkers.push(m);
        });
      } catch {}
    }

    // Unclustered points: show small photo markers using thumbs
    const pointFeats = placesMap.queryRenderedFeatures({ layers: ["unclustered-point"] }) || [];
    for (const f of pointFeats) {
      const p = f.properties || {};
      const coords = f && f.geometry && f.geometry.coordinates ? f.geometry.coordinates : null;
      if (!coords) continue;
      const el = document.createElement("div");
      el.className = "photo-marker";
      if (p.thumb) el.style.backgroundImage = `url(${p.thumb})`;
      el.title = p.name || "";
      el.addEventListener("click", () => {
        const pid = typeof p.id === "string" ? parseInt(p.id, 10) : p.id;
        const idx = state.items.findIndex(i => i.id === pid);
        if (idx >= 0) openViewer(idx);
      });
      const m = new maplibregl.Marker({ element: el, anchor: "center" })
        .setLngLat(coords)
        .addTo(placesMap);
      placesHtmlMarkers.push(m);
    }
  } catch {}
}
function updateScanButton() {
  if (state.scanning) {
    els.scanBtn.textContent = "Stop scan";
  } else {
    els.scanBtn.textContent = "Scan bibliotek";
  }
}

function openClusterSheet(clusterId) {
  const src = placesMap.getSource("places");
  if (!src) return;
  try {
    src.getClusterLeaves(clusterId, 100, 0, (err, leaves) => {
      const sheet = document.getElementById("clusterSheet");
      const grid = document.getElementById("clusterGrid");
      if (!sheet || !grid) return;
      grid.innerHTML = "";
      if (!err && leaves && leaves.length) {
        for (const lf of leaves) {
          const p = lf.properties || {};
          const img = document.createElement("img");
          if (p.thumb) img.src = p.thumb;
          img.title = p.name || "";
          img.addEventListener("click", () => {
            // Åbn viewer på dette billede hvis muligt
            const idx = state.items.findIndex(i => i.id === p.id);
            if (idx >= 0) openViewer(idx);
          });
          grid.appendChild(img);
        }
      }
      sheet.classList.remove("hidden");
    });
  } catch {}
}

// Luk sheet når man klikker på baggrund eller trykker Escape
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") {
    const sheet = document.getElementById("clusterSheet");
    if (sheet) sheet.classList.add("hidden");
  }
});

// Luk sheet ved klik udenfor panelet
document.addEventListener("click", (e) => {
  const sheet = document.getElementById("clusterSheet");
  if (!sheet || sheet.classList.contains("hidden")) return;
  if (!sheet.contains(e.target)) {
    sheet.classList.add("hidden");
  }
});

async function pollScanStatus() {
  try {
    const res = await fetch("/api/scan/status");
    const data = await res.json();
    const running = !!(data && data.running);
    state.scanning = running;
    updateScanButton();
    if (!running) {
      showStatus("Scan færdig eller stoppet.", "ok");
      await loadPhotos();
      return; // stop polling
    }
  } catch (_) {
    // ignore polling errors
  }
  // continue polling while scanning
  if (state.scanning) {
    setTimeout(pollScanStatus, 2000);
  }
}

async function scanLibrary() {
  if (state.scanning) {
    // act as stop
    try {
      const res = await fetch("/api/scan/stop", { method: "POST" });
      const data = await res.json();
      if (!res.ok || !data.ok) {
        showStatus("Kunne ikke stoppe scan.", "err");
        return;
      }
      showStatus("Stopper scan...", "ok");
    } catch (_) {
      showStatus("Fejl ved stop scan.", "err");
    }
    return;
  }

  // Start scan
  try {
    const res = await fetch("/api/scan", { method: "POST" });
    const data = await res.json();
    if (!res.ok || !data.ok) {
      showStatus(`Fejl: ${data && data.error ? data.error : "Scan fejlede"}`, "err");
      return;
    }
    state.scanning = true;
    updateScanButton();
    showStatus("Scan startet... klik 'Stop scan' for at afbryde.", "ok");
    pollScanStatus();
  } catch (err) {
    showStatus(`Fejl under scan: ${err}`, "err");
  }
}

// Rescan metadata
async function pollRescanStatus() {
  try {
    const res = await fetch("/api/rescan/status");
    const data = await res.json();
    if (!data || !data.ok) return;
    if (!data.running) {
      if (data.result) {
        const r = data.result;
        showStatus(`Rescan færdig. Gennemgået: ${r.scanned}, opdateret: ${r.updated}, mangler: ${r.missing}, fejl: ${r.errors}.`, "ok");
      }
      await loadPhotos();
      return;
    }
  } catch {}
  setTimeout(pollRescanStatus, 2000);
}

async function rescanMetadata() {
  try {
    els.rescanBtn.disabled = true;
    showStatus("Rescanner metadata for eksisterende billeder...", "ok");
    const res = await fetch("/api/rescan", { method: "POST" });
    const data = await res.json();
    if (!res.ok || !data.ok) {
      showStatus(`Fejl: ${data && data.error ? data.error : "Rescan fejlede"}`, "err");
      els.rescanBtn.disabled = false;
      return;
    }
    pollRescanStatus();
  } catch (e) {
    showStatus("Fejl ved rescan.", "err");
    els.rescanBtn.disabled = false;
  }
}

// Rethumb (rebuild thumbnails)
async function pollRethumbStatus() {
  try {
    const res = await fetch("/api/rethumb/status");
    const data = await res.json();
    if (!data || !data.ok) return;
    if (!data.running) {
      if (data.result) {
        const r = data.result;
        showStatus(`Genbyg thumbnails færdig. Behandlet: ${r.processed}, fejl: ${r.errors}.`, "ok");
      }
      await loadPhotos();
      return;
    }
  } catch {}
  setTimeout(pollRethumbStatus, 2000);
}

async function rethumbAll() {
  try {
    if (els.rethumbBtn) els.rethumbBtn.disabled = true;
    showStatus("Genbygger thumbnails (kan tage lidt tid)...", "ok");
    const res = await fetch("/api/rethumb", { method: "POST" });
    const data = await res.json();
    if (!res.ok || !data.ok) {
      showStatus(`Fejl: ${data && data.error ? data.error : "Genbyg thumbnails fejlede"}`, "err");
      if (els.rethumbBtn) els.rethumbBtn.disabled = false;
      return;
    }
    pollRethumbStatus();
  } catch (e) {
    showStatus("Fejl ved genbyg thumbnails.", "err");
    if (els.rethumbBtn) els.rethumbBtn.disabled = false;
  }
}

// Clear index (DB + thumbnails, not originals)
async function clearIndex() {
  const ok = confirm("Nulstil indeks? Dette sletter kun data og thumbnails i FjordLens (ikke dine originale billeder). Fortsæt?");
  if (!ok) return;
  try {
    if (els.clearIndexBtn) els.clearIndexBtn.disabled = true;
    showStatus("Sletter indeks og thumbnails...", "ok");
    const res = await fetch("/api/clear", { method: "POST" });
    const data = await res.json();
    if (!res.ok || !data.ok) {
      showStatus(`Fejl ved nulstilling: ${data && data.error ? data.error : "ukendt"}`, "err");
      if (els.clearIndexBtn) els.clearIndexBtn.disabled = false;
      return;
    }
    const r = data.removed || {};
    showStatus(`Indeks nulstillet. Slettet: ${r.photos || 0} poster, ${r.faces || 0} ansigter, ${r.people || 0} personer, ${r.thumbs || 0} thumbs.`, "ok");
    // Tøm UI og hent frisk
    state.items = [];
    await loadPhotos();
  } catch (e) {
    showStatus("Fejl ved nulstilling.", "err");
  } finally {
    if (els.clearIndexBtn) els.clearIndexBtn.disabled = false;
  }
}

async function toggleFavorite() {
  if (!state.selectedId) return;
  const selected = state.items.find(i => i.id === state.selectedId);
  if (!selected) return;

  const res = await fetch(`/api/photos/${state.selectedId}/favorite`, { method: "POST" });
  const data = await res.json();
  if (!res.ok || !data.ok) return;

  selected.favorite = !!data.favorite;
  renderGrid();
  setDetail(selected);
}

async function setView(view, opts = {}) {
  const { syncUrl = true } = opts || {};
  const nextView = APP_VIEW_KEYS.has(view) ? view : 'timeline';
  state.view = nextView;
  if (nextView !== 'mapper') state.mapperPath = _normalizeMapperPath(state.mapperPath);
  state.folder = (nextView === 'mapper' ? (_normalizeMapperPath(state.mapperPath) || null) : null);
  state.selectedId = null;
  document.querySelectorAll(".nav-item").forEach(btn => {
    btn.classList.toggle("active", btn.dataset.view === nextView);
  });
  // Toggle body class to drive CSS for Settings view
  document.body.classList.toggle("view-settings", nextView === "settings");
  document.body.classList.toggle("view-timeline", nextView === "timeline");
  document.body.classList.toggle("view-mapper", nextView === "mapper");
  if (nextView !== 'mapper' && els.mapperTreeNav) {
    if (els.mapperNavMenu) els.mapperNavMenu.classList.add('hidden');
    els.mapperTreeNav.classList.add('hidden');
  }
  if (syncUrl) _syncRouteStateToUrl();

  if (nextView === "settings") {
    // show logs panel, do not load photos
    renderGrid();
  } else if (nextView === 'personer') {
    state.personView = { mode: 'list', personId: null, personName: null };
    await loadPeople();
  } else {
    if (nextView === 'mapper') await loadMapperTools();
    await loadPhotos();
  }
}

function applyUiLanguage() {
  try { document.documentElement.lang = state.uiLanguage || 'da'; } catch {}
  if (els.search) els.search.placeholder = tr('search_placeholder');

  if (els.sort) {
    const sortTexts = {
      date_desc: tr('sort_date_desc'),
      date_asc: tr('sort_date_asc'),
      name_asc: tr('sort_name_asc'),
      name_desc: tr('sort_name_desc'),
      size_desc: tr('sort_size_desc'),
      size_asc: tr('sort_size_asc'),
    };
    Object.entries(sortTexts).forEach(([val, text]) => {
      const opt = els.sort.querySelector(`option[value="${val}"]`);
      if (opt) opt.textContent = text;
    });
  }

  const navMap = {
    timeline: tr('nav_timeline'),
    favorites: tr('nav_favorites'),
    steder: tr('nav_places'),
    kameraer: tr('nav_cameras'),
    mapper: tr('nav_folders'),
    personer: tr('nav_people'),
    settings: tr('nav_settings'),
  };
  Object.entries(navMap).forEach(([view, text]) => {
    const el = document.querySelector(`.nav-item[data-view="${view}"]`);
    if (el) el.textContent = text;
  });

  if (els.profileLink) els.profileLink.textContent = tr('profile_link');
  const logoutLink = document.querySelector('.sidebar-footer a[href="/logout"]');
  if (logoutLink) logoutLink.textContent = tr('logout_link');

  const tabText = {
    maint: tr('tab_maint'),
    ai: tr('tab_ai'),
    logs: tr('tab_logs'),
    users: tr('tab_users'),
    twofa: tr('tab_twofa'),
    profile: tr('tab_profile'),
    other: tr('tab_other'),
  };
  Object.entries(tabText).forEach(([tab, text]) => {
    const btn = document.querySelector(`#settingsPanel .tab-btn[data-tab="${tab}"]`);
    if (btn) btn.textContent = text;
  });

  const settingsHeaderTitle = document.querySelector('#settingsPanel .settings-header h1');
  const settingsHeaderSub = document.querySelector('#settingsPanel .settings-header p');
  if (settingsHeaderTitle) settingsHeaderTitle.textContent = tr('settings_title');
  if (settingsHeaderSub) settingsHeaderSub.textContent = tr('settings_sub');

  const maintTitle = document.querySelector('#settingsPanel .tab-panel[data-tabpanel="maint"] .sidebar-card-title');
  if (maintTitle) maintTitle.textContent = tr('maint_title');

  if (els.scanBtn) els.scanBtn.textContent = tr('btn_scan_library');
  if (els.rescanBtn) els.rescanBtn.textContent = tr('btn_rescan_metadata');
  if (els.rethumbBtn) els.rethumbBtn.textContent = tr('btn_rebuild_thumbs');
  if (els.clearIndexBtn) els.clearIndexBtn.textContent = tr('btn_reset_index');
  if (els.aiIngestBtn) els.aiIngestBtn.textContent = tr('btn_build_embeddings');
  updateAiToggleButton();
  if (els.facesIndexBtn) els.facesIndexBtn.textContent = tr('btn_index_faces');

  const logsLabel = document.querySelector('#logsPanel strong');
  if (logsLabel) logsLabel.textContent = tr('logs_label');
  if (els.logsStart) els.logsStart.textContent = state.logsRunning ? tr('btn_stop') : tr('btn_start');
  if (els.mainLogsClear) els.mainLogsClear.textContent = tr('btn_clear');

  const profileModalTitle = document.querySelector('#profileModal h3');
  if (profileModalTitle) profileModalTitle.textContent = tr('profile_title');
  if (els.profileModalClose) els.profileModalClose.textContent = tr('profile_close');

  const scanModalTitle = document.getElementById('scanModalTitle');
  const scanModalText = document.getElementById('scanModalText');
  if (scanModalTitle) scanModalTitle.textContent = tr('scan_modal_title');
  if (scanModalText) scanModalText.textContent = tr('scan_modal_text');
  if (els.scanModalClose) els.scanModalClose.textContent = tr('scan_modal_close');
  if (els.scanModalCancel) els.scanModalCancel.textContent = tr('scan_modal_cancel');
  if (els.scanModalStart) els.scanModalStart.textContent = tr('scan_modal_start');

  const labels = navLabels();
  const [title, subtitle] = labels[state.view] || ['FjordLens', ''];
  if (els.viewTitle) els.viewTitle.textContent = title;
  if (els.viewSubtitle) els.viewSubtitle.textContent = subtitle;
}

function activateSettingsTab(tab) {
  const btn = document.querySelector(`#settingsPanel .tab-btn[data-tab="${tab}"]`);
  if (btn) btn.click();
}

function openProfileModal() {
  if (!els.profileModal) return;
  els.profileModal.classList.remove('hidden');
}

function closeProfileModal() {
  if (!els.profileModal) return;
  els.profileModal.classList.add('hidden');
}

function openScanModal() {
  if (!els.scanModal) return;
  els.scanModal.classList.remove('hidden');
}

function closeScanModal() {
  if (!els.scanModal) return;
  els.scanModal.classList.add('hidden');
}

// Events
els.search.addEventListener("input", () => {
  state.q = els.search.value.trim();
  loadPhotos();
});
els.sort.addEventListener("change", () => {
  state.sort = els.sort.value;
  loadPhotos();
});
els.scanBtn.addEventListener("click", () => {
  if (state.scanning) {
    scanLibrary();
    return;
  }
  openScanModal();
});
els.rescanBtn && els.rescanBtn.addEventListener("click", rescanMetadata);
els.rethumbBtn && els.rethumbBtn.addEventListener("click", rethumbAll);
els.clearIndexBtn && els.clearIndexBtn.addEventListener("click", clearIndex);
async function startAiIngest() {
  try {
    showStatus("Starter AI‑indeksering (embeddings)...", "ok");
    const res = await fetch('/api/ai/ingest', { method: 'POST' });
    const data = await res.json();
    if (!res.ok || !data.ok) {
      showStatus("Kunne ikke starte AI‑indeksering.", "err");
      return;
    }
    showStatus("AI‑indeksering er startet i baggrunden.", "ok");
    state.aiRunning = true;
    updateAiToggleButton();
    pollAiStatus();
  } catch { showStatus("Fejl ved start af AI‑indeksering.", "err"); }
}

async function stopAiIngest() {
  try {
    const res = await fetch('/api/ai/stop', { method: 'POST' });
    const data = await res.json().catch(() => ({}));
    if (!res.ok || (data && data.ok === false)) {
      showStatus('Kunne ikke stoppe AI‑indeksering.', 'err');
      return;
    }
    showStatus('AI‑indeksering stoppet.', 'ok');
    state.aiRunning = false;
    updateAiToggleButton();
    pollAiStatus();
  } catch {
    showStatus('Fejl ved stop af AI‑indeksering.', 'err');
  }
}

els.aiIngestBtn && els.aiIngestBtn.addEventListener("click", startAiIngest);

els.aiStopBtn && els.aiStopBtn.addEventListener('click', async () => {
  if (state.aiRunning) {
    await stopAiIngest();
    return;
  }
  await startAiIngest();
});

// Faces indexing controls
async function pollFacesStatus() {
  try {
    const r = await fetch('/api/faces/status');
    const s = await r.json();
    if (els.facesStatus) {
      const run = s && s.running ? tr('status_running') : tr('status_stopped');
      els.facesStatus.textContent = `${tr('status_faces_prefix')}: ${run}`;
    }
    if (s && s.running) {
      setTimeout(pollFacesStatus, 1500);
    } else {
      // refresh lists when done
      if (state.view === 'personer') loadPeople();
      else loadPhotos();
      if (els.facesIndexBtn) els.facesIndexBtn.disabled = false;
    }
  } catch {
    if (els.facesStatus) els.facesStatus.textContent = `${tr('status_faces_prefix')}: ${tr('status_dash')}`;
    if (els.facesIndexBtn) els.facesIndexBtn.disabled = false;
  }
}

async function startFacesIndex(all=true) {
  try {
    if (els.facesIndexBtn) els.facesIndexBtn.disabled = true;
    showStatus('Starter ansigtsindeksering…', 'ok');
    const url = all ? '/api/faces/index?all=1' : '/api/faces/index';
    const res = await fetch(url, { method: 'POST' });
    const data = await res.json();
    if (!res.ok || !data.ok) {
      showStatus(data && data.error ? data.error : 'Kunne ikke starte ansigtsindeksering', 'err');
      if (els.facesIndexBtn) els.facesIndexBtn.disabled = false;
      return;
    }
    pollFacesStatus();
  } catch (e) {
    showStatus('Fejl ved start af ansigtsindeksering', 'err');
    if (els.facesIndexBtn) els.facesIndexBtn.disabled = false;
  }
}

if (els.facesIndexBtn) {
  els.facesIndexBtn.addEventListener('click', () => startFacesIndex(true));
}

async function pollAiStatus() {
  try {
    const r = await fetch('/api/ai/status');
    const s = await r.json();
    state.aiRunning = !!(s && s.ok && s.running);
    updateAiToggleButton();
    if (els.aiStatus) {
      if (!s || !s.ok) { els.aiStatus.textContent = `${tr('status_ai_prefix')}: ${tr('status_dash')}`; }
      else {
        const run = s.running ? tr('status_running') : tr('status_stopped');
        els.aiStatus.textContent = `${tr('status_ai_prefix')}: ${run} · embedded ${s.embedded||0}/${s.total||0} · ${tr('status_errors_label')} ${s.failed||0}`;
      }
    }
  } catch {
    state.aiRunning = false;
    updateAiToggleButton();
    if (els.aiStatus) els.aiStatus.textContent = `${tr('status_ai_prefix')}: ${tr('status_dash')}`;
  }
  // Poll mens der kører noget
  try {
    const r2 = await fetch('/api/ai/status');
    const s2 = await r2.json();
    if (s2 && s2.running) setTimeout(pollAiStatus, 1200);
  } catch {}
}

// Start med at vise status hvis noget kører allerede
pollAiStatus();
updateScanButton();
els.toggleRawBtn.addEventListener("click", () => {
  const hidden = els.rawMeta.classList.toggle("hidden");
  els.toggleRawBtn.textContent = hidden ? "Vis rå metadata (JSON)" : "Skjul rå metadata (JSON)";
});
els.favoriteBtn.addEventListener("click", toggleFavorite);

// Date edit interactions
if (els.editDateBtn) {
  els.editDateBtn.addEventListener('click', () => {
    if (els.dateEditWrap) {
      els.dateEditWrap.classList.remove('hidden');
      els.dateEditWrap.classList.add('floating');
      // Position under the pencil button (viewport coordinates)
      try {
        const r = els.editDateBtn.getBoundingClientRect();
        const w = Math.min(420, Math.max(300, window.innerWidth - 24));
        let left = r.right - w;
        const margin = 12;
        if (left < margin) left = margin;
        if (left + w > window.innerWidth - margin) left = window.innerWidth - margin - w;
        els.dateEditWrap.style.width = w + 'px';
        els.dateEditWrap.style.left = left + 'px';
        els.dateEditWrap.style.top = (r.bottom + 8) + 'px';
        els.dateEditWrap.style.zIndex = '100000';
      } catch {}
    }
    try {
      const row = els.editDateBtn.closest('.detail-row');
      if (row) row.classList.add('popover-open');
    } catch {}
  });
}
if (els.dateCancelBtn) {
  els.dateCancelBtn.addEventListener('click', () => {
    if (els.dateEditWrap) { els.dateEditWrap.classList.add('hidden'); els.dateEditWrap.classList.remove('floating'); els.dateEditWrap.style.left=''; els.dateEditWrap.style.top=''; }
    try {
      const row = els.editDateBtn.closest('.detail-row');
      if (row) row.classList.remove('popover-open');
    } catch {}
  });
}
if (els.dateSaveBtn) {
  els.dateSaveBtn.addEventListener('click', async () => {
    if (!state.selectedId || !els.dateInput) return;
    const v = els.dateInput.value;
    if (!v) return;
    try {
      const res = await fetch(`/api/photos/${state.selectedId}/captured-at`, { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ captured_at: v })});
      const data = await res.json();
      if (!res.ok || !data.ok) { showStatus(data.error || 'Kunne ikke opdatere dato', 'err'); return; }
      const item = data.item;
      const idx = state.items.findIndex(i => i.id === item.id);
      if (idx >= 0) state.items[idx] = item;
      showStatus('Dato opdateret', 'ok');
      renderGrid();
      setDetail(item);
      if (els.dateEditWrap) { els.dateEditWrap.classList.add('hidden'); els.dateEditWrap.classList.remove('floating'); els.dateEditWrap.style.left=''; els.dateEditWrap.style.top=''; }
      try {
        const row = els.editDateBtn.closest('.detail-row');
        if (row) row.classList.remove('popover-open');
      } catch {}
    } catch (e) {
      showStatus('Fejl ved opdatering', 'err');
    }
  });
}

// --- GPS editor (MapLibre) ---
let gpsMap = null;
let gpsMarker = null;
let gpsLat = null;
let gpsLon = null;
let gpsPrevParent = null;
let gpsPrevNext = null;
let gpsBackdrop = null;
let gpsEarthOn = true;
let gpsSearchTimer = null;

function initGpsMap(item) {
  if (!els.gpsMapEl) return;
  if (!gpsMap) {
    gpsMap = new maplibregl.Map({
      container: els.gpsMapEl,
      style: 'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json',
      center: [10,56], zoom: 4, attributionControl: false,
    });
    gpsMap.addControl(new maplibregl.NavigationControl({ showCompass:false }), 'top-right');
    gpsMap.on('click', (e)=> setGpsPoint(e.lngLat.lng, e.lngLat.lat));
    try { gpsMap.on('load', ()=> { gpsMap.getCanvas().style.cursor='crosshair'; }); } catch{}
  }
  ensureEarthLayer();
  try { if (gpsMap.getLayer('esri')) gpsMap.setLayoutProperty('esri','visibility', gpsEarthOn ? 'visible' : 'none'); } catch{}
  applySatelliteLabelMode();
  if (item && item.gps_lon != null && item.gps_lat != null) {
    setGpsPoint(Number(item.gps_lon), Number(item.gps_lat), { fly:true });
  } else {
    if (gpsMarker) { gpsMarker.remove(); gpsMarker=null; }
    gpsLat=gpsLon=null;
    if (els.gpsCoordText) els.gpsCoordText.textContent = 'Klik på kortet for at vælge';
    try { gpsMap.jumpTo({ center:[10,56], zoom:4 }); } catch {}
  }
}
function ensureEarthLayer(){
  if (!gpsMap) return;
  const add = ()=>{
    try {
      if (!gpsMap.getSource('esri')) {
        gpsMap.addSource('esri', { type:'raster', tiles:['https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}'], tileSize:256, attribution:'Esri' });
      }
      if (!gpsMap.getLayer('esri')) {
        // Insert raster below first symbol (labels) layer so labels stay on top
        let beforeId = null;
        try {
          const layers = gpsMap.getStyle().layers || [];
          for (const lyr of layers) { if (lyr.type === 'symbol') { beforeId = lyr.id; break; } }
        } catch {}
        gpsMap.addLayer({ id:'esri', type:'raster', source:'esri', layout:{ visibility: gpsEarthOn ? 'visible' : 'none' } }, beforeId || undefined);
      } else {
        gpsMap.setLayoutProperty('esri','visibility', gpsEarthOn ? 'visible' : 'none');
      }
      applySatelliteLabelMode();
    } catch(e){}
  };
  try { if (gpsMap.isStyleLoaded()) add(); else gpsMap.once('load', add); } catch { add(); }
}

// Keep only labels (symbol layers) above satellite and make text black
function applySatelliteLabelMode(){
  if (!gpsMap) return;
  try {
    const style = gpsMap.getStyle(); if (!style || !style.layers) return;
    for (const lyr of style.layers) {
      const id = lyr.id; const tp = lyr.type;
      if (id === 'esri') continue; // keep satellite
      if (tp && tp !== 'symbol') {
        if (id !== 'esri' && id !== 'pickCircle') {
          try { gpsMap.setLayoutProperty(id, 'visibility', 'none'); } catch {}
        }
      } else if (tp === 'symbol') {
        try { gpsMap.setLayoutProperty(id, 'visibility', 'visible'); } catch {}
        try { gpsMap.setPaintProperty(id, 'text-color', '#000000'); } catch {}
        try { gpsMap.setPaintProperty(id, 'text-halo-color', '#ffffff'); } catch {}
        try { gpsMap.setPaintProperty(id, 'text-halo-width', 0.8); } catch {}
      }
    }
  } catch {}
}
function setGpsPoint(lon, lat, opts={}){
  gpsLat=lat; gpsLon=lon;
  if (els.gpsCoordText) els.gpsCoordText.textContent = `${lat.toFixed(6)}, ${lon.toFixed(6)}`;
  // Update circle layer data for precise rendering (no DOM transform issues)
  try {
    const src = gpsMap.getSource('pick');
    if (src) {
      src.setData({ type:'FeatureCollection', features:[{ type:'Feature', geometry:{ type:'Point', coordinates:[lon,lat] } }] });
    }
  } catch {}
  // Tilføj eller flyt markør på kortet
  try {
    if (gpsMarker) { gpsMarker.remove(); gpsMarker = null; }
    gpsMarker = new maplibregl.Marker({ color: '#d00', draggable: false })
      .setLngLat([lon, lat])
      .addTo(gpsMap);
  } catch {}
  if (opts.fly) { try { gpsMap.jumpTo({ center:[lon,lat], zoom:11 }); } catch {} }
}
if (els.editGpsBtn) {
  els.editGpsBtn.addEventListener('click', () => {
    // Safety: remove any stray backdrops before opening
    try { document.querySelectorAll('.modal-backdrop').forEach(el=>{ if(el.parentElement) el.parentElement.removeChild(el); }); } catch{}
    if (els.gpsEditWrap) {
      // Reparent to body and show centered modal with backdrop
      try { gpsPrevParent = els.gpsEditWrap.parentElement; gpsPrevNext = els.gpsEditWrap.nextElementSibling; document.body.appendChild(els.gpsEditWrap); } catch {}
      if (!gpsBackdrop) { gpsBackdrop = document.createElement('div'); gpsBackdrop.className='modal-backdrop'; gpsBackdrop.addEventListener('click', (e)=> { if (e.target === gpsBackdrop && els.gpsCancelBtn) els.gpsCancelBtn.click(); }); }
      document.body.appendChild(gpsBackdrop);
      // place modal inside backdrop (centered via flex)
      gpsBackdrop.appendChild(els.gpsEditWrap);
      els.gpsEditWrap.classList.remove('hidden');
      els.gpsEditWrap.classList.add('gps-modal');
      gpsBackdrop.classList.add('active');
      const item = state.items.find(i => i.id === state.selectedId);
      initGpsMap(item);
      // Ensure correct size/transform after showing modal (fixes wrong click coords)
      try {
        if (gpsMap) {
          // resize now and on next frame
          gpsMap.resize();
          requestAnimationFrame(()=>{ try { gpsMap.resize(); } catch{} });
        }
      } catch {}
    }
  });
}
if (els.gpsCancelBtn) {
  els.gpsCancelBtn.addEventListener('click', ()=>{
    if (els.gpsEditWrap) { els.gpsEditWrap.classList.add('hidden'); els.gpsEditWrap.classList.remove('floating'); els.gpsEditWrap.classList.remove('gps-modal');
      try { if (gpsPrevParent) { if (gpsPrevNext) gpsPrevParent.insertBefore(els.gpsEditWrap, gpsPrevNext); else gpsPrevParent.appendChild(els.gpsEditWrap); } } catch {}
      try { if (gpsBackdrop) gpsBackdrop.classList.remove('active'); } catch{}
      try { if (gpsBackdrop && gpsBackdrop.parentElement) gpsBackdrop.parentElement.removeChild(gpsBackdrop); } catch{}
      gpsBackdrop = null;
    }
  });
}
if (els.gpsSaveBtn) {
  els.gpsSaveBtn.addEventListener('click', async ()=>{
    if (!state.selectedId || gpsLat==null || gpsLon==null) return;
    try {
      const res = await fetch(`/api/photos/${state.selectedId}/gps`, { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ lat: gpsLat, lon: gpsLon })});
      const data = await res.json();
      if (!res.ok || !data.ok) { showStatus(data.error || 'Kunne ikke opdatere GPS', 'err'); return; }
      const item = data.item; const idx = state.items.findIndex(i => i.id === item.id); if (idx>=0) state.items[idx]=item;
      showStatus('GPS opdateret', 'ok'); renderGrid(); setDetail(item);
      if (els.gpsEditWrap) { els.gpsEditWrap.classList.add('hidden'); els.gpsEditWrap.classList.remove('floating'); els.gpsEditWrap.classList.remove('gps-modal');
        try { if (gpsPrevParent) { if (gpsPrevNext) gpsPrevParent.insertBefore(els.gpsEditWrap, gpsPrevNext); else gpsPrevParent.appendChild(els.gpsEditWrap); } } catch {}
        try { if (gpsBackdrop) gpsBackdrop.classList.remove('active'); } catch{}
        try { if (gpsBackdrop && gpsBackdrop.parentElement) gpsBackdrop.parentElement.removeChild(gpsBackdrop); } catch{}
        gpsBackdrop = null;
      }
    } catch(e){ showStatus('Fejl ved opdatering', 'err'); }
  });
}

function ensurePickLayer(){
  if (!gpsMap) return;
  const add = ()=>{
    try {
      if (!gpsMap.getSource('pick')) {
        gpsMap.addSource('pick', { type:'geojson', data:{ type:'FeatureCollection', features:[] } });
      }
      if (!gpsMap.getLayer('pickCircle')) {
        gpsMap.addLayer({ id:'pickCircle', type:'circle', source:'pick', paint: { 'circle-radius': 6, 'circle-color':'#5b8cff', 'circle-stroke-color':'#ffffff', 'circle-stroke-width': 2 } });
      }
    } catch(e){}
  };
  try { if (gpsMap.isStyleLoaded()) add(); else gpsMap.once('load', add); } catch { add(); }
}

// --- Address search (Nominatim) ---
async function searchAddress(q){
  q = (q || '').trim();
  if (!els.gpsSearchList) return;
  if (!q) { els.gpsSearchList.classList.add('hidden'); els.gpsSearchList.innerHTML=''; return; }
  try{
    const url = `https://nominatim.openstreetmap.org/search?format=jsonv2&limit=5&accept-language=da&q=${encodeURIComponent(q)}`;
    const res = await fetch(url, { headers: { 'Accept': 'application/json' } });
    const data = await res.json();
    if (!Array.isArray(data)) { els.gpsSearchList.classList.add('hidden'); return; }
    const html = data.map(r=>`<div class="gps-result-item" data-lat="${r.lat}" data-lon="${r.lon}">${(r.display_name||'').replaceAll('<','&lt;')}</div>`).join('');
    els.gpsSearchList.innerHTML = html || '<div class="gps-result-item">Ingen resultater</div>';
    els.gpsSearchList.classList.remove('hidden');
    els.gpsSearchList.querySelectorAll('.gps-result-item').forEach(it=>{
      it.addEventListener('click', ()=>{
        const lat = parseFloat(it.getAttribute('data-lat'));
        const lon = parseFloat(it.getAttribute('data-lon'));
        setGpsPoint(lon, lat, { fly:true });
        els.gpsSearchList.classList.add('hidden');
      });
    });
  } catch{
    els.gpsSearchList.classList.add('hidden');
  }
}

if (els.gpsSearchInput){
  els.gpsSearchInput.addEventListener('input', ()=>{
    const q = els.gpsSearchInput.value;
    if (gpsSearchTimer) clearTimeout(gpsSearchTimer);
    gpsSearchTimer = setTimeout(()=> searchAddress(q), 350);
  });
}
// Earth overlay toggle
if (els.gpsEarthBtn) {
  els.gpsEarthBtn.addEventListener('click', ()=>{
    gpsEarthOn = !gpsEarthOn;
    if (els.gpsEarthBtn) els.gpsEarthBtn.classList.toggle('toggled', gpsEarthOn);
    ensureEarthLayer();
    try { if (gpsMap && gpsMap.getLayer('esri')) gpsMap.setLayoutProperty('esri','visibility', gpsEarthOn?'visible':'none'); } catch{}
  });
}

document.querySelectorAll(".nav-item").forEach(btn => {
  btn.addEventListener("click", () => {
    if (btn.dataset.view === 'mapper' && state.view === 'mapper') {
      state.mapperTreeOpen = !state.mapperTreeOpen;
      _saveMapperTreeUiState();
      renderMapperTree();
      document.body.classList.remove("drawer-open");
      return;
    }
    setView(btn.dataset.view);
    // Close drawer on mobile nav selection
    document.body.classList.remove("drawer-open");
  });
});

if (els.profileLink) {
  els.profileLink.addEventListener('click', async (e) => {
    e.preventDefault();
    await renderProfilePanel();
    openProfileModal();
    document.body.classList.remove('drawer-open');
  });
}

if (els.profileModalClose) {
  els.profileModalClose.addEventListener('click', closeProfileModal);
}
if (els.profileModal) {
  els.profileModal.addEventListener('click', (e) => {
    if (e.target === els.profileModal) closeProfileModal();
  });
}

if (els.scanModalClose) {
  els.scanModalClose.addEventListener('click', closeScanModal);
}
if (els.scanModalCancel) {
  els.scanModalCancel.addEventListener('click', closeScanModal);
}
if (els.scanModalStart) {
  els.scanModalStart.addEventListener('click', async () => {
    closeScanModal();
    await scanLibrary();
  });
}
if (els.scanModal) {
  els.scanModal.addEventListener('click', (e) => {
    if (e.target === els.scanModal) closeScanModal();
  });
}

// Settings tabs switching
document.querySelectorAll('#settingsPanel .tab-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    const tab = btn.dataset.tab;
    // activate button
    document.querySelectorAll('#settingsPanel .tab-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    // show panel
    document.querySelectorAll('#settingsPanel .tab-panel').forEach(p => {
      p.classList.toggle('hidden', p.dataset.tabpanel !== tab);
    });
    // lazy-load embedded admin panels
    if (tab === 'users') renderUsersPanel();
    if (tab === 'twofa') renderTwofaPanel();
  });
});

els.mapperFolderCreateBtn && els.mapperFolderCreateBtn.addEventListener('click', createMapperFolder);
els.mapperEditBtn && els.mapperEditBtn.addEventListener('click', () => setMapperEditMode(!state.mapperEditMode));
els.mapperDeleteBtn && els.mapperDeleteBtn.addEventListener('click', deleteSelectedMapperFolders);
els.mapperUpBtn && els.mapperUpBtn.addEventListener('click', async () => {
  const cur = String(state.mapperPath || '');
  if (!cur) return;
  const parts = cur.split('/').filter(Boolean);
  parts.pop();
  const parent = parts.join('/');
  state.mapperPath = parent;
  state.folder = parent || null;
  renderMapperContext(parent);
  await loadMapperTools(parent);
  await loadPhotos();
});
if (els.mapperDropZone) {
  els.mapperDropZone.addEventListener('dragover', (e) => {
    if (state.view !== 'mapper') return;
    if (e.dataTransfer && e.dataTransfer.types && e.dataTransfer.types.includes('Files')) {
      e.preventDefault();
      els.mapperDropZone.classList.add('dragover');
    }
  });
  els.mapperDropZone.addEventListener('dragleave', () => {
    els.mapperDropZone.classList.remove('dragover');
  });
  els.mapperDropZone.addEventListener('drop', async (e) => {
    els.mapperDropZone.classList.remove('dragover');
    if (state.view !== 'mapper') return;
    if (!(e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length)) return;
    e.preventDefault();
    const targetSubdir = String(state.mapperPath || '');
    await uploadFiles(e.dataTransfer.files, { destination: 'uploads', subdir: targetSubdir });
    await loadMapperTools(targetSubdir);
    await loadPhotos();
  });
}

// viewer events
els.viewerClose && els.viewerClose.addEventListener("click", closeViewer);
els.viewerPrev && els.viewerPrev.addEventListener("click", () => nextViewer(-1));
els.viewerNext && els.viewerNext.addEventListener("click", () => nextViewer(1));
window.addEventListener("keydown", (e) => {
  if (!els.viewer || els.viewer.classList.contains("hidden")) return;
  if (e.key === "Escape") closeViewer();
  if (e.key === "ArrowLeft") nextViewer(-1);
  if (e.key === "ArrowRight") nextViewer(1);
});

// Close viewer when clicking the dark backdrop (outside media/content)
if (els.viewer) {
  els.viewer.addEventListener('click', (e) => {
    if (e.target === els.viewer) closeViewer();
  });
}

// Viewer Info toggle
const viPanel = document.getElementById('viewerInfo');
const viBtn = document.getElementById('viewerInfoBtn');
if (viBtn && viPanel) {
  viBtn.addEventListener('click', ()=>{
    if (viPanel.classList.contains('open')) {
      viPanel.classList.remove('open'); // slide back under image (still present but under)
    } else {
      // Ensure visible, start from under state, then slide out
      viPanel.classList.remove('hidden');
      // Recompute anchor to media edge before opening (in case window resized)
      try {
        const it = state.items[state.selectedIndex] || {};
        const mediaEl = (it.is_video ? els.viewerVideo : els.viewerImg);
        const r = mediaEl.getBoundingClientRect();
        const w = viPanel.offsetWidth || 360;
        const underOffset = 8;
        viPanel.style.left = `${Math.round(r.right - w - underOffset)}px`;
        viPanel.style.right = 'auto';
        const vPad = 16;
        const top = Math.max(0, Math.round(r.top + vPad));
        const bottomGap = Math.max(0, Math.round(window.innerHeight - (r.bottom - vPad)));
        viPanel.style.top = `${top}px`;
        viPanel.style.bottom = `${bottomGap}px`;
        viPanel.style.height = '';
      } catch {}
      // force reflow so transition starts from transform:0 (under)
      void viPanel.offsetWidth;
      viPanel.classList.add('open');
    }
  });
}
// Hide panel on close
const _origCloseViewer = closeViewer;
closeViewer = function(){
  try { if (viPanel) { viPanel.classList.remove('open'); /* keep under image, no hidden */ } } catch {}
  _origCloseViewer();
}

// Keep the slide-out anchored to the media edge on resize
window.addEventListener('resize', ()=>{
  try {
    const vi = document.getElementById('viewerInfo');
    if (!vi) return;
    const it = state.items[state.selectedIndex] || {};
    const mediaEl = (it.is_video ? els.viewerVideo : els.viewerImg);
    const r = mediaEl.getBoundingClientRect();
    const w = vi.offsetWidth || 360;
    const underOffset = 8;
    vi.style.left = `${Math.round(r.right - w - underOffset)}px`;
    vi.style.right = 'auto';
    const vPad = 16;
    const top = Math.max(0, Math.round(r.top + vPad));
    const bottomGap = Math.max(0, Math.round(window.innerHeight - (r.bottom - vPad)));
    vi.style.top = `${top}px`;
    vi.style.bottom = `${bottomGap}px`;
    vi.style.height = '';
  } catch {}
});

// Proxy edit buttons inside viewer to open the main editors
const viEditDateBtn = document.getElementById('viEditDateBtn');
if (viEditDateBtn) {
  viEditDateBtn.addEventListener('click', ()=>{ try { closeViewer(); } catch{}; try { els.editDateBtn && els.editDateBtn.click(); } catch{} });
}
const viEditGpsBtn = document.getElementById('viEditGpsBtn');
if (viEditGpsBtn) {
  viEditGpsBtn.addEventListener('click', ()=>{ try { closeViewer(); } catch{}; try { els.editGpsBtn && els.editGpsBtn.click(); } catch{} });
}

// Viewer actions: favorite + similar
const viFavoriteBtn = document.getElementById('viFavoriteBtn');
if (viFavoriteBtn) {
  viFavoriteBtn.addEventListener('click', async ()=>{
    await toggleFavorite();
    try { const selected = state.items.find(i=>i.id===state.selectedId); viFavoriteBtn.textContent = selected && selected.favorite ? '★' : '☆'; } catch {}
  });
}

async function openSimilarForSelected(){
  if (!state.selectedId) return;
  try {
    const res = await fetch(`/api/photos/${state.selectedId}/similar?limit=60`);
    const data = await res.json();
    if (!res.ok) { showStatus(data && data.error ? data.error : 'Kunne ikke hente lignende', 'err'); return; }
    state.view = 'timeline';
    state.items = Array.isArray(data.items) ? data.items : [];
    state.selectedId = null;
    if (els.viewTitle) els.viewTitle.textContent = 'Lignende billeder';
    if (els.viewSubtitle) els.viewSubtitle.textContent = 'Fundet via billed‑embedding';
    closeViewer();
    renderGrid();
  } catch { showStatus('Fejl ved hentning af lignende', 'err'); }
}
const viSimilarBtn = document.getElementById('viSimilarBtn');
if (viSimilarBtn) viSimilarBtn.addEventListener('click', openSimilarForSelected);

// Mobile drawer toggle
function openDrawer(){ document.body.classList.add("drawer-open"); }
function closeDrawer(){ document.body.classList.remove("drawer-open"); }
els.menuBtn && els.menuBtn.addEventListener("click", () => {
  if (document.body.classList.contains("drawer-open")) closeDrawer(); else openDrawer();
});
els.drawerBackdrop && els.drawerBackdrop.addEventListener("click", closeDrawer);
window.addEventListener("keydown", (e) => { if (e.key === "Escape") closeDrawer(); });

// Initial load
const _initialRoute = _readRouteStateFromUrl();
if (_initialRoute.view) {
  state.view = _initialRoute.view;
}
if (state.view === 'mapper') {
  state.mapperPath = _initialRoute.mapperPath || '';
  state.folder = state.mapperPath || null;
}

applyUiLanguage();

setView(state.view, { syncUrl: false }).then(() => {
  showStatus(tr('status_ready_scan'), "ok");
  // Start with a quick status check in case scan was running
  fetch("/api/scan/status").then(r => r.json()).then(d => {
    if (d && d.running) {
      state.scanning = true;
      updateScanButton();
      pollScanStatus();
    }
  }).catch(() => {});
  // logs always running
  startLogs();
  // Safety: remove any stray backdrops/overlays that might block UI after reload
  try { document.querySelectorAll('.modal-backdrop').forEach(el=>{ if(el.parentElement) el.parentElement.removeChild(el); }); } catch{}
  try { document.querySelectorAll('.upload-overlay').forEach(el=> el.classList.remove('active')); } catch{}
  // Watchdog: every 5s remove any backdrop with no visible modal child
  setInterval(()=>{
    try {
      document.querySelectorAll('.modal-backdrop').forEach(el=>{
        const hasModal = !!el.querySelector('.gps-modal:not(.hidden)');
        if (!hasModal) { if (el.parentElement) el.parentElement.removeChild(el); }
      });
      document.querySelectorAll('.upload-overlay').forEach(el=>{ if (!el.classList.contains('active')) el.classList.remove('active'); });
    } catch{}
  }, 1000);
});

// --- Embedded Admin Panels ---
async function renderUsersPanel(){
  const wrap = document.getElementById('usersPanelInner');
  if (!wrap) return;
  wrap.textContent = 'Indlæser…';
  try{
    const r = await fetch('/api/admin/users');
    const js = await r.json();
    if (!r.ok || !js.ok){
      wrap.innerHTML = `<div class="empty">Kan ikke hente brugere. ${js && js.error ? js.error : ''}</div>`;
      return;
    }
    const items = js.items || [];
    const rows = items.map(u => `
      <tr>
        <td class="muted">#${u.id}</td>
        <td><strong>${u.username}</strong></td>
        <td>${u.role}</td>
        <td>${(u.ui_language || 'da').toUpperCase()} / ${(u.search_language || 'da').toUpperCase()}</td>
        <td>${u.totp_enabled ? '<span class="badge twofa">2FA</span>' : '<span class="badge muted">—</span>'}</td>
        <td style="text-align:right;display:flex;gap:6px;justify-content:flex-end;">
          <button data-edit="${u.id}" class="btn small">Rediger</button>
          <button data-del="${u.id}" class="btn danger small">Slet</button>
        </td>
      </tr>`).join('');
    wrap.innerHTML = `
      <div class="panel" style="margin-bottom:12px;">
        <div class="toolbar">
          <strong>Brugere</strong>
          <button id="nu_open" class="btn primary" style="margin-left:auto;">Tilføj bruger</button>
        </div>
      </div>
      <div class="data-table" style="margin-bottom:12px;">
        <table>
          <thead><tr><th>ID</th><th>Brugernavn</th><th>Rolle</th><th>Sprog (UI/Søgning)</th><th>2FA</th><th></th></tr></thead>
          <tbody>${rows || '<tr><td colspan=6 class="muted">Ingen brugere</td></tr>'}</tbody>
        </table>
      </div>
      <!-- Create user modal -->
      <div id="nu_modal" class="hidden" style="position:fixed;inset:0;background:rgba(0,0,0,0.6);display:flex;align-items:center;justify-content:center;z-index:9999;">
        <div style="width:520px;max-width:92vw;background:var(--panel);border:1px solid var(--border);border-radius:12px;padding:16px;">
          <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px;">
            <h3 style="margin:0;">Tilføj bruger</h3>
            <button id="nu_close" class="btn">Luk</button>
          </div>
          <div class="form-row"><label for="nu_username">Brugernavn</label><input id="nu_username" placeholder="Brugernavn"></div>
          <div class="form-row"><label for="nu_password">Adgangskode</label><input id="nu_password" placeholder="Adgangskode" type="password"></div>
          <div class="form-row"><label for="nu_role">Rolle</label>
            <select id="nu_role" class="select">
              <option value="user">Bruger</option>
              <option value="manager">Manager</option>
              <option value="admin">Admin</option>
            </select>
          </div>
          <div class="form-row"><label for="nu_ui_language">UI-sprog</label>
            <select id="nu_ui_language" class="select">
              <option value="da">Dansk</option>
              <option value="en">English</option>
            </select>
          </div>
          <div class="form-row"><label for="nu_search_language">Søgesprog</label>
            <select id="nu_search_language" class="select">
              <option value="da">Dansk</option>
              <option value="en">English</option>
            </select>
          </div>
          <label style="display:flex;align-items:center;gap:8px;margin:6px 0 2px;">
            <input type="checkbox" id="nu_2fa" />
            <span>Aktivér 2FA fra start</span>
          </label>
          <div class="actions" style="justify-content:flex-end;">
            <button id="nu_cancel" class="btn">Annuller</button>
            <button id="nu_save" class="btn primary">Opret</button>
          </div>
        </div>
      </div>

      <!-- Edit user modal -->
      <div id="eu_modal" class="hidden" style="position:fixed;inset:0;background:rgba(0,0,0,0.6);display:flex;align-items:center;justify-content:center;z-index:9999;">
        <div style="width:520px;max-width:92vw;background:var(--panel);border:1px solid var(--border);border-radius:12px;padding:16px;">
          <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px;">
            <h3 style="margin:0;">Rediger bruger</h3>
            <button id="eu_close" class="btn">Luk</button>
          </div>
          <div class="form-row"><label for="eu_username">Brugernavn</label><input id="eu_username" placeholder="Brugernavn"></div>
          <div class="form-row"><label for="eu_password">Nyt password (valgfrit)</label><input id="eu_password" placeholder="Tom = uændret" type="password"></div>
          <div class="form-row"><label for="eu_role">Rolle</label>
            <select id="eu_role" class="select">
              <option value="user">Bruger</option>
              <option value="manager">Manager</option>
              <option value="admin">Admin</option>
            </select>
          </div>
          <div class="form-row"><label for="eu_ui_language">UI-sprog</label>
            <select id="eu_ui_language" class="select">
              <option value="da">Dansk</option>
              <option value="en">English</option>
            </select>
          </div>
          <div class="form-row"><label for="eu_search_language">Søgesprog</label>
            <select id="eu_search_language" class="select">
              <option value="da">Dansk</option>
              <option value="en">English</option>
            </select>
          </div>
          <div class="actions" style="justify-content:flex-end;">
            <button id="eu_cancel" class="btn">Annuller</button>
            <button id="eu_save" class="btn primary">Gem</button>
          </div>
        </div>
      </div>
    `;

    const byId = new Map(items.map(u => [String(u.id), u]));

    // bind delete
    wrap.querySelectorAll('button[data-del]').forEach(btn=>{
      btn.addEventListener('click', async ()=>{
        const id = btn.getAttribute('data-del');
        if (!confirm('Slet bruger #' + id + '?')) return;
        const rr = await fetch('/api/admin/users/'+id, {method:'DELETE'});
        const jj = await rr.json();
        if (!rr.ok || !jj.ok){ showStatus('Kunne ikke slette: ' + (jj && jj.error || ''), 'err'); return; }
        showStatus('Bruger slettet', 'ok');
        renderUsersPanel();
      });
    });

    // edit modal wiring
    const editModal = document.getElementById('eu_modal');
    const editCloseBtn = document.getElementById('eu_close');
    const editCancelBtn = document.getElementById('eu_cancel');
    let editingUserId = null;

    function closeEdit(){
      if (!editModal) return;
      editModal.classList.add('hidden');
      editingUserId = null;
      const ep = document.getElementById('eu_password');
      if (ep) ep.value = '';
    }

    wrap.querySelectorAll('button[data-edit]').forEach(btn => {
      btn.addEventListener('click', () => {
        const id = String(btn.getAttribute('data-edit') || '');
        const user = byId.get(id);
        if (!user) return;
        editingUserId = user.id;
        const eu = document.getElementById('eu_username');
        const ep = document.getElementById('eu_password');
        const er = document.getElementById('eu_role');
        const eul = document.getElementById('eu_ui_language');
        const esl = document.getElementById('eu_search_language');
        if (eu) eu.value = user.username || '';
        if (ep) ep.value = '';
        if (er) er.value = user.role || 'user';
        if (eul) eul.value = user.ui_language || 'da';
        if (esl) esl.value = user.search_language || 'da';
        if (editModal) editModal.classList.remove('hidden');
      });
    });

    editCloseBtn && editCloseBtn.addEventListener('click', closeEdit);
    editCancelBtn && editCancelBtn.addEventListener('click', closeEdit);
    editModal && editModal.addEventListener('click', (e)=>{ if(e.target === editModal) closeEdit(); });

    const editSaveBtn = document.getElementById('eu_save');
    if (editSaveBtn) {
      editSaveBtn.addEventListener('click', async () => {
        if (!editingUserId) return;
        const username = (document.getElementById('eu_username').value || '').trim();
        const password = document.getElementById('eu_password').value || '';
        const role = document.getElementById('eu_role').value || 'user';
        const ui_language = document.getElementById('eu_ui_language').value || 'da';
        const search_language = document.getElementById('eu_search_language').value || 'da';
        if (!username) { showStatus('Brugernavn må ikke være tomt.', 'err'); return; }
        const payload = { username, role, ui_language, search_language };
        if (password) payload.password = password;
        const rr = await fetch('/api/admin/users/' + editingUserId, { method:'PUT', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload) });
        const jj = await rr.json();
        if (!rr.ok || !jj.ok) { showStatus('Kunne ikke gemme bruger: ' + ((jj && jj.error) || ''), 'err'); return; }
        showStatus('Bruger opdateret', 'ok');
        closeEdit();
        renderUsersPanel();
      });
    }

    // modal wiring
    const modal = document.getElementById('nu_modal');
    const openBtn = document.getElementById('nu_open');
    const closeBtn = document.getElementById('nu_close');
    const cancelBtn = document.getElementById('nu_cancel');
    function open(){ if(modal) modal.classList.remove('hidden'); }
    function clear(){
      const u = document.getElementById('nu_username');
      const p = document.getElementById('nu_password');
      const r = document.getElementById('nu_role');
      const f = document.getElementById('nu_2fa');
      const ul = document.getElementById('nu_ui_language');
      const sl = document.getElementById('nu_search_language');
      if (u) u.value = '';
      if (p) p.value = '';
      if (r) r.value = 'user';
      if (f) f.checked = false;
      if (ul) ul.value = 'da';
      if (sl) sl.value = 'da';
    }
    function close(){ if(modal) { modal.classList.add('hidden'); clear(); } }
    openBtn && openBtn.addEventListener('click', open);
    closeBtn && closeBtn.addEventListener('click', close);
    cancelBtn && cancelBtn.addEventListener('click', close);
    modal && modal.addEventListener('click', (e)=>{ if(e.target === modal) close(); });

    // bind create (modal)
    const saveBtn = document.getElementById('nu_save');
    if (saveBtn){
      saveBtn.addEventListener('click', async ()=>{
        const username = (document.getElementById('nu_username').value || '').trim();
        const password = document.getElementById('nu_password').value || '';
        const role = document.getElementById('nu_role').value || 'user';
        const ui_language = document.getElementById('nu_ui_language').value || 'da';
        const search_language = document.getElementById('nu_search_language').value || 'da';
        const enforce_2fa = !!(document.getElementById('nu_2fa') && document.getElementById('nu_2fa').checked);
        if (!username || !password){ showStatus('Udfyld brugernavn og adgangskode.', 'err'); return; }
        const payload = { username, password, role, enforce_2fa, ui_language, search_language };
        const rr = await fetch('/api/admin/users', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload)});
        const jj = await rr.json();
        if (!rr.ok || !jj.ok){ showStatus('Kunne ikke oprette: ' + (jj && jj.error || ''), 'err'); return; }
        showStatus('Bruger oprettet', 'ok');
        close();
        renderUsersPanel();
      });
    }
  }catch(e){ wrap.innerHTML = `<div class="empty">Fejl: ${e}</div>`; }
}

async function renderTwofaPanel(){
  const wrap = document.getElementById('twofaPanelInner');
  if (!wrap) return;
  wrap.textContent = 'Indlæser…';
  try{
    const r = await fetch('/api/me/2fa');
    const js = await r.json();
    if (!r.ok || !js.ok){ wrap.innerHTML = `<div class="empty">Kan ikke hente 2FA-status.</div>`; return; }
    const enabled = !!js.enabled;
    const daysVal = (js.remember_days||0);
    // Build UI depending on state
    let leftCol = '';
    if (!enabled && js.qr) {
      leftCol = `<img src="${js.qr}" alt="QR" style="width:140px;height:140px;border:1px solid var(--border);border-radius:8px;background:#fff;"/>`;
    }
    let secretRow = '';
    const toggleLabel = enabled ? 'Deaktivér' : 'Aktivér';
    const toggleClass = enabled ? 'btn danger' : 'btn primary';
    const regenBtnHtml = enabled ? '<button id="tf_regen" class="btn">Forny QR / nøgle</button>' : '';
    wrap.innerHTML = `
      <div class="panel" style="display:flex;gap:16px;align-items:flex-start;flex-wrap:wrap;">
        ${leftCol}
        <div style="flex:1;min-width:260px;">
          <div class="form-row"><label>Husk dage</label><input id="tf_days" class="input-number" type="number" min="0" max="30" value="${daysVal}"></div>
          ${secretRow}
          <div class="form-row"><label>Engangskode</label><input id="tf_code" class="input-number" placeholder="6-cifret kode" autocomplete="one-time-code"></div>
          <div class="actions" style="flex-wrap:wrap;gap:8px;justify-content:flex-start;">
            <button id="tf_toggle" class="${toggleClass}">${toggleLabel}</button>
            <button id="tf_save" class="btn">Gem</button>
            ${regenBtnHtml}
          </div>
          <div class="mini-label" style="margin-top:6px;">Status: <strong>${enabled ? 'Aktiveret' : 'Deaktiveret'}</strong></div>
        </div>
      </div>
    `;
    async function post(action){
      const payload = { action, code: (document.getElementById('tf_code').value||'').trim(), days: parseInt(document.getElementById('tf_days').value || '0',10) };
      const rr = await fetch('/api/me/2fa', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload)});
      const jj = await rr.json();
      if (!rr.ok || !jj.ok){ showStatus('2FA-fejl: ' + (jj && jj.error || ''), 'err'); return; }
      showStatus('2FA opdateret', 'ok');
      renderTwofaPanel();
    }
    document.getElementById('tf_toggle').addEventListener('click', ()=>post(enabled ? 'disable' : 'enable'));
    document.getElementById('tf_save').addEventListener('click', ()=>post('save'));
    const regenBtn = document.getElementById('tf_regen');
    regenBtn && regenBtn.addEventListener('click', ()=>post('regen'));
  }catch(e){ wrap.innerHTML = `<div class="empty">Fejl: ${e}</div>`; }
}

async function renderProfilePanel() {
  const wrap = document.getElementById('profilePanelInner');
  if (!wrap) return;
  wrap.textContent = '...';

  const setProfileInlineStatus = (text, type = 'ok') => {
    const box = document.getElementById('pf_status');
    if (!box) return;
    if (!text) {
      box.textContent = '';
      box.className = 'mini-label hidden';
      return;
    }
    box.textContent = text;
    box.className = `status ${type}`;
    box.classList.remove('hidden');
  };

  try {
    const r = await fetch('/api/me');
    const js = await r.json();
    if (!r.ok || !js.ok || !js.item) {
      wrap.innerHTML = `<div class="empty">${state.uiLanguage === 'en' ? 'Could not load profile.' : 'Kan ikke hente profil.'} ${js && js.error ? js.error : ''}</div>`;
      return;
    }
    const me = js.item;
    state.currentUser = { id: me.id, username: me.username, role: me.role || 'user' };
    wrap.innerHTML = `
      <div class="panel" style="max-width:700px;">
        <div class="form-row"><label for="pf_username">${tr('profile_username')}</label><input id="pf_username" value="${escapeHtml(me.username || '')}" /></div>
        <div class="form-row"><label for="pf_password">${tr('profile_password_new_optional')}</label><input id="pf_password" type="password" placeholder="${tr('profile_password_unchanged_placeholder')}" /></div>
        <div class="form-row"><label for="pf_password2">${tr('profile_password_repeat')}</label><input id="pf_password2" type="password" placeholder="${tr('profile_password_repeat_placeholder')}" /></div>
        <div class="form-row"><label for="pf_ui_language">${tr('profile_ui_lang')}</label>
          <select id="pf_ui_language" class="select">
            <option value="da">Dansk</option>
            <option value="en">English</option>
          </select>
        </div>
        <div class="form-row"><label for="pf_search_language">${tr('profile_search_lang')}</label>
          <select id="pf_search_language" class="select">
            <option value="da">Dansk</option>
            <option value="en">English</option>
          </select>
        </div>
        <div class="actions" style="justify-content:flex-end;">
          <button id="pf_save" class="btn primary">${tr('profile_save')}</button>
        </div>
        <div id="pf_status" class="mini-label hidden" style="margin-top:8px;"></div>
      </div>
    `;

    const uiSelect = document.getElementById('pf_ui_language');
    const searchSelect = document.getElementById('pf_search_language');
    if (uiSelect) uiSelect.value = me.ui_language || state.uiLanguage || 'da';
    if (searchSelect) searchSelect.value = me.search_language || state.searchLanguage || 'da';

    const saveBtn = document.getElementById('pf_save');
    if (saveBtn) {
      saveBtn.addEventListener('click', async () => {
        const username = (document.getElementById('pf_username').value || '').trim();
        const password = document.getElementById('pf_password').value || '';
        const password2 = document.getElementById('pf_password2').value || '';
        const ui_language = document.getElementById('pf_ui_language').value || 'da';
        const search_language = document.getElementById('pf_search_language').value || 'da';
        if (!username) { setProfileInlineStatus(state.uiLanguage === 'en' ? 'Username cannot be empty.' : 'Brugernavn må ikke være tomt.', 'err'); return; }
        if (password && password !== password2) { setProfileInlineStatus(state.uiLanguage === 'en' ? 'Passwords do not match.' : 'Password matcher ikke.', 'err'); return; }

        setProfileInlineStatus('', 'ok');

        const payload = { username, ui_language, search_language };
        if (password) payload.password = password;

        const rr = await fetch('/api/me/profile', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });
        const jj = await rr.json();
        if (!rr.ok || !jj.ok) {
          setProfileInlineStatus((state.uiLanguage === 'en' ? 'Could not save profile: ' : 'Kunne ikke gemme profil: ') + ((jj && jj.error) || ''), 'err');
          return;
        }

        state.currentUser.username = username;
        state.uiLanguage = resolveUiLanguage(ui_language);
        state.searchLanguage = resolveUiLanguage(search_language);
        applyUiLanguage();
        await loadPhotos();
        setProfileInlineStatus(tr('profile_saved'), 'ok');
        const p1 = document.getElementById('pf_password');
        const p2 = document.getElementById('pf_password2');
        if (p1) p1.value = '';
        if (p2) p2.value = '';
      });
    }
  } catch (e) {
    wrap.innerHTML = `<div class="empty">${state.uiLanguage === 'en' ? 'Error' : 'Fejl'}: ${e}</div>`;
  }
}

// Duplicates UI
async function fetchDuplicates() {
  const dist = parseInt(els.dupeDist ? els.dupeDist.value : 5, 10) || 5;
  const min = parseInt(els.dupeMin ? els.dupeMin.value : 2, 10) || 2;
  try {
    if (els.dupeStatus) { els.dupeStatus.textContent = `Søger efter dupletter (afstand=${dist}, min=${min})...`; els.dupeStatus.classList.remove("hidden", "err"); els.dupeStatus.classList.add("ok"); }
    if (els.dupeResults) els.dupeResults.innerHTML = "";
    const res = await fetch(`/api/duplicates?distance=${encodeURIComponent(dist)}&min=${encodeURIComponent(min)}`);
    const data = await res.json();
    renderDuplicates(data);
    if (els.dupeStatus) { els.dupeStatus.textContent = `Færdig. Checksum-grupper: ${data?.counts?.checksum || 0}, pHash-lige: ${data?.counts?.phash_equal || 0}, pHash-nære: ${data?.counts?.phash_near || 0}`; }
  } catch (e) {
    if (els.dupeStatus) { els.dupeStatus.textContent = `Fejl ved duplet-søgning.`; els.dupeStatus.classList.remove("ok"); els.dupeStatus.classList.add("err"); }
  }
}

function renderDuplicates(data) {
  if (!els.dupeResults) return;
  const wrap = els.dupeResults;
  wrap.innerHTML = "";
  if (!data || !data.groups) {
    wrap.innerHTML = "<div class='empty'>Ingen resultater.</div>";
    return;
  }
  for (const grp of data.groups) {
    const sets = grp.items || [];
    if (!sets.length) continue;
    const sec = document.createElement("section");
    sec.className = "dupe-group";
    const titleMap = { checksum: "Checksum", phash_equal: "pHash (ens)", phash_near: `pHash (nær)` };
    const name = titleMap[grp.reason] || grp.reason;
    sec.innerHTML = `<h4>${name} · ${sets.length} grupper</h4>`;
    for (const arr of sets) {
      const strip = document.createElement("div");
      strip.className = "dupe-strip";
      for (const it of arr) {
        const a = document.createElement("a");
        a.className = "dupe-item";
        a.href = it.rel_path ? `/api/original/${encodeURIComponent(it.rel_path)}` : "#";
        a.target = "_blank";
        a.rel = "noopener";
        a.innerHTML = `${it.thumb_url ? `<img class='dupe-thumb' src='${it.thumb_url}' alt=''>` : `<div class='dupe-thumb' style='display:grid;place-items:center;background:#1b1f29;'>Ingen</div>`}<small>${it.filename || ''}</small>`;
        strip.appendChild(a);
      }
      sec.appendChild(strip);
    }
    wrap.appendChild(sec);
  }
  if (!wrap.children.length) {
    wrap.innerHTML = "<div class='empty'>Ingen dupletter fundet med de aktuelle kriterier.</div>";
  }
}

// Buttons for duplicates (both buttons do the same action)
els.dupesBtn && els.dupesBtn.addEventListener('click', fetchDuplicates);
els.dupesRun && els.dupesRun.addEventListener('click', fetchDuplicates);

// Live logs
// Determine severity for a log event -> one of: 'ok' | 'warn' | 'err' | 'info'
function classifySeverity(eventName) {
  const ev = String(eventName || '').toLowerCase();
  // Errors: hard failures
  if (ev === 'error' || ev.endsWith('_error') || ev.endsWith('_fail') || ev === 'ai_http_error') return 'err';
  // Warnings: skipped or not critical changes
  if (ev === 'skip_unchanged' || ev === 'no_new' || ev === 'upload_skip_unsupported' || ev === 'missing' || ev.endsWith('_check')) return 'warn';
  // Success/info: the rest of positive events
  if (ev.endsWith('_done') || ev.endsWith('_saved') || ev.endsWith('_ok') || ev === 'indexed' || ev === 'faces_detect' || ev === 'faces_index_done' || ev === 'face_saved' || ev === 'upload_indexed' || ev === 'rethumb_ok') return 'ok';
  return 'info';
}

function appendLogLine(text, level = 'info') {
  const makeLineEl = (container) => {
    if (!container) return;
    const line = document.createElement('span');
    line.className = `log-line log-${level}`;
    line.textContent = text;
    container.appendChild(line);
    // Trim to keep DOM light
    const maxLines = (container.id === 'mainLogs') ? 1200 : 400;
    while (container.childElementCount > maxLines) {
      container.removeChild(container.firstElementChild);
    }
    container.scrollTop = container.scrollHeight;
  };
  makeLineEl(els.logsBox);
  makeLineEl(els.mainLogsBox);
}

function fmtLogTime(ts) {
  const raw = (ts == null) ? '' : String(ts).trim();
  if (!raw) return '-';
  try {
    const d = new Date(raw);
    if (!Number.isFinite(d.getTime())) return raw;
    const dd = String(d.getDate()).padStart(2, '0');
    const mm = String(d.getMonth() + 1).padStart(2, '0');
    const yyyy = d.getFullYear();
    const hh = String(d.getHours()).padStart(2, '0');
    const mi = String(d.getMinutes()).padStart(2, '0');
    const ss = String(d.getSeconds()).padStart(2, '0');
    return `${dd}-${mm}-${yyyy} ${hh}:${mi}:${ss}`;
  } catch {
    return raw;
  }
}

async function pollLogs() {
  if (!state.logsRunning) return;
  try {
    const res = await fetch(`/api/logs?after=${state.logsAfter}`);
    const data = await res.json();
    if (data && data.items) {
      for (const it of data.items) {
        let extra = "";
        if (it.rel_path) extra += ` :: ${it.rel_path}`;
        if (it.from_path) extra += ` ← ${it.from_path}`;
        if (typeof it.distance !== "undefined") extra += ` [d=${it.distance}]`;
        if (typeof it.scanned !== "undefined") extra += ` scanned=${it.scanned}`;
        if (typeof it.updated !== "undefined") extra += ` updated=${it.updated}`;
        if (typeof it.errors !== "undefined") extra += ` errors=${it.errors}`;
        if (typeof it.missing !== "undefined") extra += ` missing=${it.missing}`;
        if (it.error) extra += ` :: ${it.error}`;
        const label = (it.event === 'skip_unchanged' || it.event === 'no_new') ? 'no new' : it.event;
        const msg = `[${fmtLogTime(it.t)}] ${label}${extra}`;
        const lvl = classifySeverity(it.event);
        appendLogLine(msg, lvl);
        state.logsAfter = it.id;
      }
    }
  } catch {}
  setTimeout(pollLogs, 1000);
}

function startLogs() {
  state.logsRunning = true;
  if (els.logsStart) els.logsStart.textContent = "Stop";
  pollLogs();
}
function stopLogs() {
  state.logsRunning = false;
  if (els.logsStart) els.logsStart.textContent = "Start";
}

async function clearLogs() {
  try { await fetch('/api/logs/clear', { method: 'POST' }); } catch {}
  state.logsAfter = 0;
  if (els.logsBox) els.logsBox.innerHTML = "";
  if (els.mainLogsBox) els.mainLogsBox.innerHTML = "";
}

els.logsStart && els.logsStart.addEventListener('click', () => {
  if (state.logsRunning) stopLogs(); else startLogs();
});
els.logsClear && els.logsClear.addEventListener('click', clearLogs);
els.mainLogsClear && els.mainLogsClear.addEventListener('click', clearLogs);
