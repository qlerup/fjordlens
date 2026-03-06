const els = {
  grid: document.getElementById("galleryGrid"),
  searchShell: document.getElementById("searchShell"),
  searchToggleBtn: document.getElementById("searchToggleBtn"),
  search: document.getElementById("searchInput"),
  sort: document.getElementById("sortSelect"),
  scanBtn: document.getElementById("scanBtn"),
  rescanBtn: document.getElementById("rescanBtn"),
  rethumbBtn: document.getElementById("rethumbBtn"),
  clearIndexBtn: document.getElementById("clearIndexBtn"),
  aiIngestToggle: document.getElementById("aiIngestToggle"),
  aiIngestToggleText: document.getElementById("aiIngestToggleText"),
  aiPanelTitle: document.getElementById("aiPanelTitle"),
  aiEmbedTitle: document.getElementById("aiEmbedTitle"),
  aiEmbedDesc: document.getElementById("aiEmbedDesc"),
  aiDescTitle: document.getElementById("aiDescTitle"),
  aiDescDesc: document.getElementById("aiDescDesc"),
  aiDescribeToggle: document.getElementById("aiDescribeToggle"),
  aiDescribeToggleText: document.getElementById("aiDescribeToggleText"),
  aiDescribeStatus: document.getElementById("aiDescribeStatus"),
  aiFacesTitle: document.getElementById("aiFacesTitle"),
  aiFacesDesc: document.getElementById("aiFacesDesc"),
  aiStatus: document.getElementById("aiStatus"),
  facesToggle: document.getElementById("facesToggle"),
  facesToggleText: document.getElementById("facesToggleText"),
  facesStatus: document.getElementById("facesStatus"),
  aiIngestThrottleInput: document.getElementById("aiIngestThrottleInput"),
  facesThrottleInput: document.getElementById("facesThrottleInput"),
  aiPerfPresetLow: document.getElementById("aiPerfPresetLow"),
  aiPerfPresetNormal: document.getElementById("aiPerfPresetNormal"),
  aiPerfPresetFast: document.getElementById("aiPerfPresetFast"),
  aiPerfSaveBtn: document.getElementById("aiPerfSaveBtn"),
  aiPerfStatus: document.getElementById("aiPerfStatus"),
  mapperTools: document.getElementById("mapperTools"),
  mapperHeaderActions: document.getElementById("mapperHeaderActions"),
  mapperCurrentPath: document.getElementById("mapperCurrentPath"),
  mapperUpBtn: document.getElementById("mapperUpBtn"),
  mapperSearchShell: document.getElementById("mapperSearchShell"),
  mapperSearchToggleBtn: document.getElementById("mapperSearchToggleBtn"),
  mapperSearchInput: document.getElementById("mapperSearchInput"),
  mapperHeaderMenu: document.getElementById("mapperHeaderMenu"),
  mapperHeaderEditAction: document.getElementById("mapperHeaderEditAction"),
  mapperHeaderShareAction: document.getElementById("mapperHeaderShareAction"),
  mapperHeaderUploadAction: document.getElementById("mapperHeaderUploadAction"),
  mapperHeaderCreateAction: document.getElementById("mapperHeaderCreateAction"),
  mapperEditBtn: document.getElementById("mapperEditBtn"),
  mapperDeleteBtn: document.getElementById("mapperDeleteBtn"),
  mapperNavMenu: document.getElementById("mapperNavMenu"),
  mapperTreeNav: document.getElementById("mapperTreeNav"),
  mapperDropZone: document.getElementById("mapperDropZone"),
  mapperUploadInput: document.getElementById("mapperUploadInput"),
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
  dnsPanelTitle: document.getElementById("dnsPanelTitle"),
  dnsPanelDesc: document.getElementById("dnsPanelDesc"),
  dnsDuckdnsBaseUrlLabel: document.getElementById("dnsDuckdnsBaseUrlLabel"),
  dnsDuckdnsBaseUrlInput: document.getElementById("dnsDuckdnsBaseUrlInput"),
  dnsSaveBtn: document.getElementById("dnsSaveBtn"),
  dnsStatus: document.getElementById("dnsStatus"),
  sharedLinksTitle: document.getElementById("sharedLinksTitle"),
  sharedLinksDesc: document.getElementById("sharedLinksDesc"),
  sharedLinksStatus: document.getElementById("sharedLinksStatus"),
  sharedLinksList: document.getElementById("sharedLinksList"),
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
  viewerMenuBtn: document.getElementById("viewerMenuBtn"),
  viewerMenu: document.getElementById("viewerMenu"),
  viewerMenuInfoBtn: document.getElementById("viewerMenuInfoBtn"),
  viewerOpenOrig: document.getElementById("viewerOpenOrig"),
  menuBtn: document.getElementById("menuBtn"),
  drawerBackdrop: document.getElementById("drawerBackdrop"),
  mobileBottomNav: document.getElementById("mobileBottomNav"),
  mobileNavItems: document.querySelectorAll(".mobile-nav-item"),
  profileLink: document.getElementById("profileLink"),
  profileModal: document.getElementById("profileModal"),
  profileModalClose: document.getElementById("profileModalClose"),
  twofaModal: document.getElementById("twofaModal"),
  twofaModalClose: document.getElementById("twofaModalClose"),
  mapperCreateModal: document.getElementById("mapperCreateModal"),
  mapperCreateModalTitle: document.getElementById("mapperCreateModalTitle"),
  mapperCreateModalClose: document.getElementById("mapperCreateModalClose"),
  mapperCreateModalInput: document.getElementById("mapperCreateModalInput"),
  mapperCreateModalCancel: document.getElementById("mapperCreateModalCancel"),
  mapperCreateModalConfirm: document.getElementById("mapperCreateModalConfirm"),
  mapperShareModal: document.getElementById("mapperShareModal"),
  mapperShareModalTitle: document.getElementById("mapperShareModalTitle"),
  mapperShareModalClose: document.getElementById("mapperShareModalClose"),
  mapperShareModalCancel: document.getElementById("mapperShareModalCancel"),
  mapperShareModalConfirm: document.getElementById("mapperShareModalConfirm"),
  mapperShareNameLabel: document.getElementById("mapperShareNameLabel"),
  mapperShareNameInput: document.getElementById("mapperShareNameInput"),
  mapperShareFolderLabel: document.getElementById("mapperShareFolderLabel"),
  mapperShareFolderInput: document.getElementById("mapperShareFolderInput"),
  mapperShareExpireLabel: document.getElementById("mapperShareExpireLabel"),
  mapperShareExpireValue: document.getElementById("mapperShareExpireValue"),
  mapperShareExpireUnitLabel: document.getElementById("mapperShareExpireUnitLabel"),
  mapperShareExpireUnit: document.getElementById("mapperShareExpireUnit"),
  mapperSharePermissionLabel: document.getElementById("mapperSharePermissionLabel"),
  mapperSharePermission: document.getElementById("mapperSharePermission"),
  mapperShareDuckdnsToggle: document.getElementById("mapperShareDuckdnsToggle"),
  mapperShareDuckdnsToggleText: document.getElementById("mapperShareDuckdnsToggleText"),
  mapperSharePasswordToggle: document.getElementById("mapperSharePasswordToggle"),
  mapperSharePasswordToggleText: document.getElementById("mapperSharePasswordToggleText"),
  mapperShareRequireNameToggle: document.getElementById("mapperShareRequireNameToggle"),
  mapperShareRequireNameToggleText: document.getElementById("mapperShareRequireNameToggleText"),
  mapperSharePasswordWrap: document.getElementById("mapperSharePasswordWrap"),
  mapperSharePasswordLabel: document.getElementById("mapperSharePasswordLabel"),
  mapperSharePasswordInput: document.getElementById("mapperSharePasswordInput"),
  mapperShareResultWrap: document.getElementById("mapperShareResultWrap"),
  mapperShareResultLabel: document.getElementById("mapperShareResultLabel"),
  mapperShareResultInput: document.getElementById("mapperShareResultInput"),
  mapperShareCopyBtn: document.getElementById("mapperShareCopyBtn"),
  scanModal: document.getElementById("scanModal"),
  scanModalClose: document.getElementById("scanModalClose"),
  scanModalCancel: document.getElementById("scanModalCancel"),
  scanModalStart: document.getElementById("scanModalStart"),
  aiScopeModal: document.getElementById("aiScopeModal"),
  aiScopeModalTitle: document.getElementById("aiScopeModalTitle"),
  aiScopeModalText: document.getElementById("aiScopeModalText"),
  aiScopeModalClose: document.getElementById("aiScopeModalClose"),
  aiScopeModalCancel: document.getElementById("aiScopeModalCancel"),
  aiScopeModalNew: document.getElementById("aiScopeModalNew"),
  aiScopeModalAll: document.getElementById("aiScopeModalAll"),
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
  uploadMonitor: document.getElementById("uploadMonitor"),
  uploadMonitorToggle: document.getElementById("uploadMonitorToggle"),
  uploadMonitorStop: document.getElementById("uploadMonitorStop"),
  uploadMonitorBar: document.getElementById("uploadMonitorBar"),
  uploadMonitorSummary: document.getElementById("uploadMonitorSummary"),
  uploadMonitorCurrent: document.getElementById("uploadMonitorCurrent"),
  uploadMonitorList: document.getElementById("uploadMonitorList"),
  uploadTopStatus: document.getElementById("uploadTopStatus"),
  uploadTopStatusLabel: document.getElementById("uploadTopStatusLabel"),
  uploadTopStatusBar: document.getElementById("uploadTopStatusBar"),
};

function ensureUploadOverlayRefs() {
  if (!els.uploadOverlay) els.uploadOverlay = document.getElementById("uploadOverlay");
  if (!els.uploadProgressBar) els.uploadProgressBar = document.getElementById("uploadProgressBar");
  if (!els.uploadProgressText) els.uploadProgressText = document.getElementById("uploadProgressText");
}

function ensureUploadMonitorRefs() {
  if (!els.uploadMonitor) els.uploadMonitor = document.getElementById("uploadMonitor");
  if (!els.uploadMonitorToggle) els.uploadMonitorToggle = document.getElementById("uploadMonitorToggle");
  if (!els.uploadMonitorStop) els.uploadMonitorStop = document.getElementById("uploadMonitorStop");
  if (!els.uploadMonitorBar) els.uploadMonitorBar = document.getElementById("uploadMonitorBar");
  if (!els.uploadMonitorSummary) els.uploadMonitorSummary = document.getElementById("uploadMonitorSummary");
  if (!els.uploadMonitorCurrent) els.uploadMonitorCurrent = document.getElementById("uploadMonitorCurrent");
  if (!els.uploadMonitorList) els.uploadMonitorList = document.getElementById("uploadMonitorList");
}

function ensureUploadTopStatusRefs() {
  if (!els.uploadTopStatus) els.uploadTopStatus = document.getElementById("uploadTopStatus");
  if (!els.uploadTopStatusLabel) els.uploadTopStatusLabel = document.getElementById("uploadTopStatusLabel");
  if (!els.uploadTopStatusBar) els.uploadTopStatusBar = document.getElementById("uploadTopStatusBar");
}

let uploadMonitorDomEventsBound = false;
function bindUploadMonitorDomEvents() {
  if (uploadMonitorDomEventsBound) return;
  document.addEventListener('click', (event) => {
    const toggleBtn = event && event.target && event.target.closest ? event.target.closest('#uploadMonitorToggle') : null;
    if (toggleBtn) {
      uploadUiState.collapsed = !uploadUiState.collapsed;
      showUploadMonitor();
      return;
    }

    const stopBtn = event && event.target && event.target.closest ? event.target.closest('#uploadMonitorStop') : null;
    if (stopBtn) {
      if (stopBtn.disabled) return;
      requestStopUpload();
    }
  });
  uploadMonitorDomEventsBound = true;
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
    tab_dns: 'DNS',
    tab_shared: 'Delte',
    tab_logs: 'Logs',
    tab_users: 'Brugere',
    tab_twofa: 'Min 2FA',
    profile_open_twofa: 'Administrer 2FA',
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
    ai_panel_title: 'AI',
    ai_embed_title: 'AI-embeddings',
    ai_embed_desc: 'Starter eller stopper embedding-jobbet for billeder uden embedding.',
    ai_desc_title: 'AI beskrivelser',
    ai_desc_desc: 'Finder handlinger/scener (fx personer der svømmer) til bedre søgning.',
    ai_faces_title: 'Ansigtsindeksering',
    ai_faces_desc: 'Scanner billeder for ansigter og opdaterer persondata.',
    dns_title: 'DNS',
    dns_desc: 'Opsæt DuckDNS-base URL til delte links.',
    dns_duckdns_base_url: 'DuckDNS base URL',
    dns_duckdns_placeholder: 'https://mitnavn.duckdns.org',
    dns_save: 'Gem DNS',
    dns_saved: 'DNS-indstillinger gemt.',
    dns_load_failed: 'Kunne ikke hente DNS-indstillinger.',
    dns_save_failed: 'Kunne ikke gemme DNS-indstillinger.',
    dns_shares_title: 'Aktive delinger',
    dns_shares_desc: 'Se aktive share-links, kopiér linket igen, tilbagekald dem eller forlæng udløb.',
    dns_shares_loading: 'Indlæser delinger…',
    dns_shares_empty: 'Ingen aktive delinger.',
    dns_shares_load_failed: 'Kunne ikke hente delinger.',
    dns_shares_col_folder: 'Navn',
    dns_shares_col_access: 'Adgang',
    dns_shares_col_expires: 'Udløber',
    dns_shares_col_last_used: 'Sidst brugt',
    dns_shares_col_link: 'Link',
    dns_shares_col_actions: 'Handlinger',
    dns_shares_never: 'Aldrig',
    dns_shares_revoke: 'Tilbagekald',
    dns_shares_deactivate: 'Deaktiver',
    dns_shares_activate: 'Aktiver',
    dns_shares_extend: 'Forlæng',
    dns_shares_copy: 'Kopiér',
    dns_shares_copy_ok: 'Share-link kopieret.',
    dns_shares_copy_failed: 'Kunne ikke kopiere share-link.',
    dns_shares_link_unavailable: 'Link ikke tilgængeligt (opret nyt for gammel deling).',
    dns_shares_revoke_confirm: 'Tilbagekald dette share-link?',
    dns_shares_revoke_ok: 'Share-link tilbagekaldt.',
    dns_shares_revoke_failed: 'Kunne ikke tilbagekalde share-link.',
    dns_shares_deactivate_confirm: 'Deaktiver dette share-link?',
    dns_shares_deactivate_ok: 'Share-link deaktiveret.',
    dns_shares_activate_prompt: 'Aktivér link i antal dage:',
    dns_shares_activate_ok: 'Share-link aktiveret.',
    dns_shares_activate_failed: 'Kunne ikke aktivere share-link.',
    dns_shares_delete: 'Slet',
    dns_shares_delete_confirm: 'Slet dette share-link permanent?',
    dns_shares_delete_ok: 'Share-link slettet.',
    dns_shares_delete_failed: 'Kunne ikke slette share-link.',
    dns_shares_extend_prompt: 'Forlæng med antal dage:',
    dns_shares_extend_ok: 'Share-link forlænget.',
    dns_shares_extend_failed: 'Kunne ikke forlænge share-link.',
    btn_scan_library: 'Scan bibliotek',
    btn_stop_scan: 'Stop scan',
    btn_rescan_metadata: 'Rescan metadata',
    btn_rebuild_thumbs: 'Genbyg thumbnails',
    btn_reset_index: 'Nulstil indeks',
    btn_start_ai: 'Start AI',
    btn_stop_ai: 'Stop AI',
    btn_start_ai_desc: 'Start beskrivelser',
    btn_stop_ai_desc: 'Stop beskrivelser',
    btn_start_faces: 'Start ansigter',
    btn_stop_faces: 'Stop ansigter',
    btn_index_faces: 'Indekser ansigter',
    status_faces_prefix: 'Ansigter',
    status_ai_prefix: 'AI',
    status_ai_desc_prefix: 'Beskrivelser',
    status_embedded_label: 'embedded',
    status_described_label: 'beskrevet',
    status_processed_label: 'behandlet',
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
    mapper_up: 'Tilbage',
    mapper_done: 'Færdig',
    mapper_edit: '⋮',
    mapper_edit_title: 'Flere indstillinger',
    mapper_done_title: 'Luk flere indstillinger',
    mapper_menu_edit: 'Vælg',
    mapper_menu_done: 'Luk redigering',
    mapper_menu_share: 'Del',
    mapper_menu_upload: 'Upload',
    mapper_menu_create: 'Opret mappe',
    mapper_create_modal_title: 'Opret mappe',
    mapper_create_pending: 'Opretter...',
    mapper_delete_selected: 'Slet valgte',
    mapper_create_name_required: 'Skriv mappenavn først.',
    mapper_create_failed: 'Kunne ikke oprette mappe',
    mapper_create_error: 'Fejl ved oprettelse af mappe.',
    mapper_created_status: 'Mappe oprettet',
    mapper_select_delete_none: 'Vælg mindst én mappe at slette.',
    mapper_delete_confirm: 'Slet {count} mappe(r) inkl. alt indhold? Dette kan ikke fortrydes.',
    mapper_delete_pending: 'Sletter...',
    mapper_delete_failed: 'Kunne ikke slette mapper',
    mapper_delete_error: 'Fejl ved sletning af mapper.',
    mapper_delete_success: 'Slettet {count} mappe(r) og {removed} indekserede filer.',
    mapper_share_title: 'Del mapper',
    mapper_share_generate: 'Generer link',
    mapper_share_generating: 'Genererer...',
    mapper_share_name_label: 'Navn',
    mapper_share_name_placeholder: 'F.eks. Familie sommer 2026',
    mapper_share_folder_label: 'Valgte mapper',
    mapper_share_expire_label: 'Gyldig i',
    mapper_share_expire_unit_label: 'Enhed',
    mapper_share_expire_days: 'Dage',
    mapper_share_expire_hours: 'Timer',
    mapper_share_permission_label: 'Adgang',
    mapper_share_perm_view: 'Se',
    mapper_share_perm_upload: 'Se og uploade',
    mapper_share_perm_manage: 'Se, uploade og slette',
    mapper_share_duckdns_toggle: 'Brug DuckDNS-link',
    mapper_share_duckdns_not_configured: 'DuckDNS er ikke konfigureret i DNS-tabben.',
    mapper_share_password_toggle: 'Kodebeskyt link',
    mapper_share_require_name_toggle: 'Kræv navn ved åbning',
    mapper_share_password_label: 'Adgangskode',
    mapper_share_password_placeholder: 'Mindst 4 tegn',
    mapper_share_result_label: 'Share-link',
    mapper_share_copy: 'Kopiér',
    mapper_share_select_one: 'Vælg mindst én mappe først.',
    mapper_share_create_failed: 'Kunne ikke oprette share-link',
    mapper_share_created: 'Share-link oprettet.',
    mapper_share_copy_ok: 'Share-link kopieret.',
    mapper_share_copy_fail: 'Kunne ikke kopiere link automatisk.',
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
    status_error_prefix: 'Fejl:',
    status_ready_scan: "Klar. Tryk 'Scan bibliotek' for at indeksere dine billeder.",
    scan_modal_title: 'Scan bibliotek',
    scan_modal_text: 'Vil du starte en fuld scanning af biblioteket nu?',
    scan_modal_close: 'Luk',
    scan_modal_cancel: 'Annuller',
    scan_modal_start: 'Start scan',
    ai_scope_title_ai: 'Start AI-embeddings',
    ai_scope_title_desc: 'Start AI beskrivelser',
    ai_scope_title_faces: 'Start ansigtsindeksering',
    ai_scope_text: 'Vil du køre på alle eksisterende filer, eller kun på nye uploads fremover?',
    ai_scope_all: 'Alle eksisterende',
    ai_scope_new: 'Kun nye uploads fremover',
    ai_scope_cancel: 'Annuller',
    users_loading: 'Indlæser…',
    users_load_error: 'Kan ikke hente brugere.',
    users_panel_title: 'Brugere',
    users_add_user: 'Tilføj bruger',
    users_no_users: 'Ingen brugere',
    users_col_id: 'ID',
    users_col_username: 'Brugernavn',
    users_col_role: 'Rolle',
    users_col_language: 'Sprog (UI/Søgning)',
    users_col_2fa: '2FA',
    users_btn_folders: 'Mapper',
    users_btn_edit: 'Rediger',
    users_btn_delete: 'Slet',
    users_create_title: 'Tilføj bruger',
    users_edit_title: 'Rediger bruger',
    users_folders_title: 'Mappeadgang',
    users_folders_hint: 'Vælg mapper brugeren må se. Hvis du vælger en undermappe, vises overmapper automatisk kun som sti.',
    users_save_access: 'Gem adgang',
    users_label_username: 'Brugernavn',
    users_label_password: 'Adgangskode',
    users_label_new_password_optional: 'Nyt password (valgfrit)',
    users_label_role: 'Rolle',
    users_label_ui_language: 'UI-sprog',
    users_label_search_language: 'Søgesprog',
    users_role_user: 'Bruger',
    users_role_manager: 'Manager',
    users_role_admin: 'Admin',
    users_enable_2fa_start: 'Aktivér 2FA fra start',
    users_close: 'Luk',
    users_cancel: 'Annuller',
    users_create: 'Opret',
    users_save: 'Gem',
    users_acl_none_found: 'Ingen mapper fundet endnu.',
    users_acl_all_folders: 'Alle mapper (ingen begrænsning)',
    users_acl_selected_suffix: 'valgte mapper',
    users_acl_user_prefix: 'Bruger',
    users_status_acl_save_failed: 'Kunne ikke gemme mappeadgang:',
    users_status_acl_saved: 'Mappeadgang gemt',
    users_confirm_delete: 'Slet bruger',
    users_status_delete_failed: 'Kunne ikke slette:',
    users_status_deleted: 'Bruger slettet',
    users_status_username_required: 'Brugernavn må ikke være tomt.',
    users_status_update_failed: 'Kunne ikke gemme bruger:',
    users_status_updated: 'Bruger opdateret',
    users_status_username_password_required: 'Udfyld brugernavn og adgangskode.',
    users_status_create_failed: 'Kunne ikke oprette:',
    users_status_created: 'Bruger oprettet',
    users_login_log_title: 'Login-log',
    users_login_log_empty: 'Ingen login-forsøg endnu.',
    users_login_col_time: 'Tidspunkt',
    users_login_col_user: 'Bruger',
    users_login_col_status: 'Status',
    users_login_col_reason: 'Hændelse',
    users_login_col_ip: 'IP',
    users_login_col_country: 'Land',
    users_login_col_device: 'Enhed',
    users_login_status_ok: 'OK',
    users_login_status_fail: 'Fejl',
    users_login_unknown: 'Ukendt',
    users_select_all: 'Markér alle',
    users_clear_all: 'Fjern alle markeringer',
    mapper_tree_expand: 'Fold mappe ud',
    mapper_tree_collapse: 'Fold mappe sammen',
    upload_failed_generic: 'Upload fejlede',
    upload_mapper_only: 'Upload er kun aktiv i Mapper-sektionen.',
    person_rename_save_failed: 'Kunne ikke gemme navn',
    person_rename_merged: 'Person flettet til',
    person_name_updated: 'Navn opdateret',
    person_rename_merge_error: 'Fejl ved navngivning/merge',
    person_unknown_cannot_rename: 'Ukendte kan ikke omdøbes',
    person_rename_title: 'Navngiv / merge person',
    person_rename_new_placeholder: 'Opret ny person',
    person_rename_save: 'Gem',
    person_rename_none: 'Ingen eksisterende navne endnu',
    person_unknown: 'Ukendt',
    person_count_suffix: 'billede(r)',
    person_hidden_badge: 'Skjult',
    person_btn_rename: 'Navngiv',
    person_btn_hide: 'Skjul',
    person_btn_unhide: 'Vis',
    person_hide_confirm: 'Skjul denne person fra listen?',
    person_hide_failed: 'Kunne ikke skjule',
    person_hidden_ok: 'Person skjult',
    person_hide_error: 'Fejl ved skjul',
    person_unhide_failed: 'Kunne ikke gendanne',
    person_unhidden_ok: 'Person vist igen',
    person_unhide_error: 'Fejl ved gendannelse',
    users_panel_render_error: 'Fejl',
    twofa_loading: 'Indlæser…',
    twofa_load_failed: 'Kan ikke hente 2FA-status.',
    twofa_remember_days: 'Husk dage',
    twofa_onetime_code: 'Engangskode',
    twofa_code_placeholder: '6-cifret kode',
    twofa_disable: 'Deaktivér',
    twofa_enable: 'Aktivér',
    twofa_regen: 'Forny QR / nøgle',
    twofa_save_btn: 'Gem',
    twofa_status_label: 'Status',
    twofa_status_enabled: 'Aktiveret',
    twofa_status_disabled: 'Deaktiveret',
    twofa_error_prefix: '2FA-fejl:',
    twofa_updated: '2FA opdateret',
    scan_done_or_stopped: 'Scan færdig eller stoppet.',
    scan_stop_failed: 'Kunne ikke stoppe scan.',
    scan_stopping: 'Stopper scan...',
    scan_stop_error: 'Fejl ved stop scan.',
    scan_failed: 'Scan fejlede',
    scan_started_hint: "Scan startet... klik 'Stop scan' for at afbryde.",
    scan_error_prefix: 'Fejl under scan:',
    rescan_starting: 'Rescanner metadata for eksisterende billeder...',
    rescan_failed: 'Rescan fejlede',
    rescan_error: 'Fejl ved rescan.',
    rescan_done_prefix: 'Rescan færdig. Gennemgået',
    rethumb_starting: 'Genbygger thumbnails (kan tage lidt tid)...',
    rethumb_failed: 'Genbyg thumbnails fejlede',
    rethumb_error: 'Fejl ved genbyg thumbnails.',
    rethumb_done_prefix: 'Genbyg thumbnails færdig. Behandlet',
    clear_confirm: 'Nulstil indeks? Dette sletter kun data og thumbnails i FjordLens (ikke dine originale billeder). Fortsæt?',
    clear_starting: 'Sletter indeks og thumbnails...',
    clear_failed: 'Fejl ved nulstilling:',
    clear_unknown: 'ukendt',
    clear_error: 'Fejl ved nulstilling.',
    clear_done_prefix: 'Indeks nulstillet. Slettet',
    file_picker_open_failed: 'Kunne ikke åbne filvælger.',
    ai_starting: 'Starter AI-indeksering (embeddings)...',
    ai_start_failed: 'Kunne ikke starte AI-indeksering.',
    ai_enabled_new_uploads: 'AI aktiveret for nye uploads fremover.',
    ai_started_bg: 'AI-indeksering er startet i baggrunden.',
    ai_start_error: 'Fejl ved start af AI-indeksering.',
    ai_stop_failed: 'Kunne ikke stoppe AI-indeksering.',
    ai_stopped: 'AI-indeksering stoppet.',
    ai_stop_error: 'Fejl ved stop af AI-indeksering.',
    ai_desc_starting: 'Starter AI-beskrivelser…',
    ai_desc_start_failed: 'Kunne ikke starte AI-beskrivelser.',
    ai_desc_enabled_new_uploads: 'AI-beskrivelser aktiveret for nye uploads fremover.',
    ai_desc_started_bg: 'AI-beskrivelser er startet i baggrunden.',
    ai_desc_start_error: 'Fejl ved start af AI-beskrivelser.',
    ai_desc_stop_failed: 'Kunne ikke stoppe AI-beskrivelser.',
    ai_desc_stopped: 'AI-beskrivelser stoppet.',
    ai_desc_stop_error: 'Fejl ved stop af AI-beskrivelser.',
    faces_starting: 'Starter ansigtsindeksering…',
    faces_start_failed: 'Kunne ikke starte ansigtsindeksering',
    faces_enabled_new_uploads: 'Ansigtsindeksering aktiveret for nye uploads fremover.',
    faces_started_bg: 'Ansigtsindeksering kører i baggrunden.',
    faces_start_error: 'Fejl ved start af ansigtsindeksering',
    faces_stop_failed: 'Kunne ikke stoppe ansigtsindeksering.',
    faces_stopped: 'Ansigtsindeksering stoppet.',
    faces_stop_error: 'Fejl ved stop af ansigtsindeksering.',
    date_update_failed: 'Kunne ikke opdatere dato',
    date_updated: 'Dato opdateret',
    update_error: 'Fejl ved opdatering',
    gps_update_failed: 'Kunne ikke opdatere GPS',
    gps_updated: 'GPS opdateret',
    similar_fetch_failed: 'Kunne ikke hente lignende',
    similar_fetch_error: 'Fejl ved hentning af lignende',
    similar_view_title: 'Lignende billeder',
    similar_view_subtitle: 'Fundet via billed-embedding',
    raw_meta_show: 'Vis rå metadata (JSON)',
    raw_meta_hide: 'Skjul rå metadata (JSON)',
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
    tab_dns: 'DNS',
    tab_shared: 'Shared',
    tab_logs: 'Logs',
    tab_users: 'Users',
    tab_twofa: 'My 2FA',
    profile_open_twofa: 'Manage 2FA',
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
    ai_panel_title: 'AI',
    ai_embed_title: 'AI embeddings',
    ai_embed_desc: 'Starts or stops the embeddings job for photos without embeddings.',
    ai_desc_title: 'AI descriptions',
    ai_desc_desc: 'Finds actions/scenes (for example people swimming) for better search.',
    ai_faces_title: 'Face indexing',
    ai_faces_desc: 'Scans photos for faces and updates people data.',
    dns_title: 'DNS',
    dns_desc: 'Configure the DuckDNS base URL used for shared links.',
    dns_duckdns_base_url: 'DuckDNS base URL',
    dns_duckdns_placeholder: 'https://myname.duckdns.org',
    dns_save: 'Save DNS',
    dns_saved: 'DNS settings saved.',
    dns_load_failed: 'Could not load DNS settings.',
    dns_save_failed: 'Could not save DNS settings.',
    dns_shares_title: 'Active shares',
    dns_shares_desc: 'View active share links, copy links again, revoke them, or extend expiry.',
    dns_shares_loading: 'Loading shares…',
    dns_shares_empty: 'No active shares.',
    dns_shares_load_failed: 'Could not load shares.',
    dns_shares_col_folder: 'Name',
    dns_shares_col_access: 'Access',
    dns_shares_col_expires: 'Expires',
    dns_shares_col_last_used: 'Last used',
    dns_shares_col_link: 'Link',
    dns_shares_col_actions: 'Actions',
    dns_shares_never: 'Never',
    dns_shares_revoke: 'Revoke',
    dns_shares_deactivate: 'Deactivate',
    dns_shares_activate: 'Activate',
    dns_shares_extend: 'Extend',
    dns_shares_copy: 'Copy',
    dns_shares_copy_ok: 'Share link copied.',
    dns_shares_copy_failed: 'Could not copy share link.',
    dns_shares_link_unavailable: 'Link unavailable (recreate share for older entry).',
    dns_shares_revoke_confirm: 'Revoke this share link?',
    dns_shares_revoke_ok: 'Share link revoked.',
    dns_shares_revoke_failed: 'Could not revoke share link.',
    dns_shares_deactivate_confirm: 'Deactivate this share link?',
    dns_shares_deactivate_ok: 'Share link deactivated.',
    dns_shares_activate_prompt: 'Activate link for number of days:',
    dns_shares_activate_ok: 'Share link activated.',
    dns_shares_activate_failed: 'Could not activate share link.',
    dns_shares_delete: 'Delete',
    dns_shares_delete_confirm: 'Delete this share link permanently?',
    dns_shares_delete_ok: 'Share link deleted.',
    dns_shares_delete_failed: 'Could not delete share link.',
    dns_shares_extend_prompt: 'Extend by number of days:',
    dns_shares_extend_ok: 'Share link extended.',
    dns_shares_extend_failed: 'Could not extend share link.',
    btn_scan_library: 'Scan library',
    btn_stop_scan: 'Stop scan',
    btn_rescan_metadata: 'Rescan metadata',
    btn_rebuild_thumbs: 'Rebuild thumbnails',
    btn_reset_index: 'Reset index',
    btn_start_ai: 'Start AI',
    btn_stop_ai: 'Stop AI',
    btn_start_ai_desc: 'Start descriptions',
    btn_stop_ai_desc: 'Stop descriptions',
    btn_start_faces: 'Start faces',
    btn_stop_faces: 'Stop faces',
    btn_index_faces: 'Index faces',
    status_faces_prefix: 'Faces',
    status_ai_prefix: 'AI',
    status_ai_desc_prefix: 'Descriptions',
    status_embedded_label: 'embedded',
    status_described_label: 'described',
    status_processed_label: 'processed',
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
    mapper_up: 'Back',
    mapper_done: 'Done',
    mapper_edit: '⋮',
    mapper_edit_title: 'More options',
    mapper_done_title: 'Close more options',
    mapper_menu_edit: 'Select',
    mapper_menu_done: 'Close editing',
    mapper_menu_share: 'Share',
    mapper_menu_upload: 'Upload',
    mapper_menu_create: 'Create folder',
    mapper_create_modal_title: 'Create folder',
    mapper_create_pending: 'Creating...',
    mapper_delete_selected: 'Delete selected',
    mapper_create_name_required: 'Enter a folder name first.',
    mapper_create_failed: 'Could not create folder',
    mapper_create_error: 'Error while creating folder.',
    mapper_created_status: 'Folder created',
    mapper_select_delete_none: 'Select at least one folder to delete.',
    mapper_delete_confirm: 'Delete {count} folder(s) including all content? This cannot be undone.',
    mapper_delete_pending: 'Deleting...',
    mapper_delete_failed: 'Could not delete folders',
    mapper_delete_error: 'Error while deleting folders.',
    mapper_delete_success: 'Deleted {count} folder(s) and {removed} indexed files.',
    mapper_share_title: 'Share folders',
    mapper_share_generate: 'Generate link',
    mapper_share_generating: 'Generating...',
    mapper_share_name_label: 'Name',
    mapper_share_name_placeholder: 'For example Family Summer 2026',
    mapper_share_folder_label: 'Selected folders',
    mapper_share_expire_label: 'Valid for',
    mapper_share_expire_unit_label: 'Unit',
    mapper_share_expire_days: 'Days',
    mapper_share_expire_hours: 'Hours',
    mapper_share_permission_label: 'Access',
    mapper_share_perm_view: 'View',
    mapper_share_perm_upload: 'View and upload',
    mapper_share_perm_manage: 'View, upload and delete',
    mapper_share_duckdns_toggle: 'Use DuckDNS link',
    mapper_share_duckdns_not_configured: 'DuckDNS is not configured in the DNS tab.',
    mapper_share_password_toggle: 'Protect link with password',
    mapper_share_require_name_toggle: 'Require visitor name',
    mapper_share_password_label: 'Password',
    mapper_share_password_placeholder: 'At least 4 characters',
    mapper_share_result_label: 'Share link',
    mapper_share_copy: 'Copy',
    mapper_share_select_one: 'Select at least one folder first.',
    mapper_share_create_failed: 'Could not create share link',
    mapper_share_created: 'Share link created.',
    mapper_share_copy_ok: 'Share link copied.',
    mapper_share_copy_fail: 'Could not copy link automatically.',
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
    status_error_prefix: 'Error:',
    status_ready_scan: "Ready. Press 'Scan library' to index your photos.",
    scan_modal_title: 'Scan library',
    scan_modal_text: 'Do you want to start a full library scan now?',
    scan_modal_close: 'Close',
    scan_modal_cancel: 'Cancel',
    scan_modal_start: 'Start scan',
    ai_scope_title_ai: 'Start AI embeddings',
    ai_scope_title_desc: 'Start AI descriptions',
    ai_scope_title_faces: 'Start face indexing',
    ai_scope_text: 'Do you want to run on all existing files, or only on new uploads from now on?',
    ai_scope_all: 'All existing',
    ai_scope_new: 'Only new uploads from now on',
    ai_scope_cancel: 'Cancel',
    users_loading: 'Loading…',
    users_load_error: 'Could not load users.',
    users_panel_title: 'Users',
    users_add_user: 'Add user',
    users_no_users: 'No users',
    users_col_id: 'ID',
    users_col_username: 'Username',
    users_col_role: 'Role',
    users_col_language: 'Language (UI/Search)',
    users_col_2fa: '2FA',
    users_btn_folders: 'Folders',
    users_btn_edit: 'Edit',
    users_btn_delete: 'Delete',
    users_create_title: 'Add user',
    users_edit_title: 'Edit user',
    users_folders_title: 'Folder access',
    users_folders_hint: 'Select folders the user can access. If you select a subfolder, parent folders are shown only as path containers.',
    users_save_access: 'Save access',
    users_label_username: 'Username',
    users_label_password: 'Password',
    users_label_new_password_optional: 'New password (optional)',
    users_label_role: 'Role',
    users_label_ui_language: 'UI language',
    users_label_search_language: 'Search language',
    users_role_user: 'User',
    users_role_manager: 'Manager',
    users_role_admin: 'Admin',
    users_enable_2fa_start: 'Enable 2FA on creation',
    users_close: 'Close',
    users_cancel: 'Cancel',
    users_create: 'Create',
    users_save: 'Save',
    users_acl_none_found: 'No folders found yet.',
    users_acl_all_folders: 'All folders (no restriction)',
    users_acl_selected_suffix: 'selected folders',
    users_acl_user_prefix: 'User',
    users_status_acl_save_failed: 'Could not save folder access:',
    users_status_acl_saved: 'Folder access saved',
    users_confirm_delete: 'Delete user',
    users_status_delete_failed: 'Could not delete:',
    users_status_deleted: 'User deleted',
    users_status_username_required: 'Username cannot be empty.',
    users_status_update_failed: 'Could not save user:',
    users_status_updated: 'User updated',
    users_status_username_password_required: 'Fill in username and password.',
    users_status_create_failed: 'Could not create:',
    users_status_created: 'User created',
    users_login_log_title: 'Login log',
    users_login_log_empty: 'No login attempts yet.',
    users_login_col_time: 'Time',
    users_login_col_user: 'User',
    users_login_col_status: 'Status',
    users_login_col_reason: 'Event',
    users_login_col_ip: 'IP',
    users_login_col_country: 'Country',
    users_login_col_device: 'Device',
    users_login_status_ok: 'OK',
    users_login_status_fail: 'Failed',
    users_login_unknown: 'Unknown',
    users_select_all: 'Select all',
    users_clear_all: 'Clear all selections',
    mapper_tree_expand: 'Expand folder',
    mapper_tree_collapse: 'Collapse folder',
    upload_failed_generic: 'Upload failed',
    upload_mapper_only: 'Upload is only active in the Folders section.',
    person_rename_save_failed: 'Could not save name',
    person_rename_merged: 'Person merged to',
    person_name_updated: 'Name updated',
    person_rename_merge_error: 'Error while renaming/merging',
    person_unknown_cannot_rename: 'Unknown people cannot be renamed',
    person_rename_title: 'Rename / merge person',
    person_rename_new_placeholder: 'Create new person',
    person_rename_save: 'Save',
    person_rename_none: 'No existing names yet',
    person_unknown: 'Unknown',
    person_count_suffix: 'photo(s)',
    person_hidden_badge: 'Hidden',
    person_btn_rename: 'Rename',
    person_btn_hide: 'Hide',
    person_btn_unhide: 'Show',
    person_hide_confirm: 'Hide this person from the list?',
    person_hide_failed: 'Could not hide',
    person_hidden_ok: 'Person hidden',
    person_hide_error: 'Error while hiding',
    person_unhide_failed: 'Could not restore',
    person_unhidden_ok: 'Person shown again',
    person_unhide_error: 'Error while restoring',
    users_panel_render_error: 'Error',
    twofa_loading: 'Loading…',
    twofa_load_failed: 'Could not load 2FA status.',
    twofa_remember_days: 'Remember days',
    twofa_onetime_code: 'One-time code',
    twofa_code_placeholder: '6-digit code',
    twofa_disable: 'Disable',
    twofa_enable: 'Enable',
    twofa_regen: 'Renew QR / key',
    twofa_save_btn: 'Save',
    twofa_status_label: 'Status',
    twofa_status_enabled: 'Enabled',
    twofa_status_disabled: 'Disabled',
    twofa_error_prefix: '2FA error:',
    twofa_updated: '2FA updated',
    scan_done_or_stopped: 'Scan finished or stopped.',
    scan_stop_failed: 'Could not stop scan.',
    scan_stopping: 'Stopping scan...',
    scan_stop_error: 'Error while stopping scan.',
    scan_failed: 'Scan failed',
    scan_started_hint: "Scan started... click 'Stop scan' to cancel.",
    scan_error_prefix: 'Scan error:',
    rescan_starting: 'Rescanning metadata for existing photos...',
    rescan_failed: 'Rescan failed',
    rescan_error: 'Error while rescanning.',
    rescan_done_prefix: 'Rescan completed. Scanned',
    rethumb_starting: 'Rebuilding thumbnails (may take a while)...',
    rethumb_failed: 'Rebuild thumbnails failed',
    rethumb_error: 'Error while rebuilding thumbnails.',
    rethumb_done_prefix: 'Thumbnail rebuild completed. Processed',
    clear_confirm: 'Reset index? This only deletes FjordLens data and thumbnails (not your original photos). Continue?',
    clear_starting: 'Deleting index and thumbnails...',
    clear_failed: 'Reset failed:',
    clear_unknown: 'unknown',
    clear_error: 'Error while resetting index.',
    clear_done_prefix: 'Index reset. Removed',
    file_picker_open_failed: 'Could not open file picker.',
    ai_starting: 'Starting AI indexing (embeddings)...',
    ai_start_failed: 'Could not start AI indexing.',
    ai_enabled_new_uploads: 'AI enabled for new uploads from now on.',
    ai_started_bg: 'AI indexing started in the background.',
    ai_start_error: 'Error while starting AI indexing.',
    ai_stop_failed: 'Could not stop AI indexing.',
    ai_stopped: 'AI indexing stopped.',
    ai_stop_error: 'Error while stopping AI indexing.',
    ai_desc_starting: 'Starting AI descriptions…',
    ai_desc_start_failed: 'Could not start AI descriptions.',
    ai_desc_enabled_new_uploads: 'AI descriptions enabled for new uploads from now on.',
    ai_desc_started_bg: 'AI descriptions started in the background.',
    ai_desc_start_error: 'Error while starting AI descriptions.',
    ai_desc_stop_failed: 'Could not stop AI descriptions.',
    ai_desc_stopped: 'AI descriptions stopped.',
    ai_desc_stop_error: 'Error while stopping AI descriptions.',
    faces_starting: 'Starting face indexing…',
    faces_start_failed: 'Could not start face indexing',
    faces_enabled_new_uploads: 'Face indexing enabled for new uploads from now on.',
    faces_started_bg: 'Face indexing is running in the background.',
    faces_start_error: 'Error while starting face indexing',
    faces_stop_failed: 'Could not stop face indexing.',
    faces_stopped: 'Face indexing stopped.',
    faces_stop_error: 'Error while stopping face indexing.',
    date_update_failed: 'Could not update date',
    date_updated: 'Date updated',
    update_error: 'Update error',
    gps_update_failed: 'Could not update GPS',
    gps_updated: 'GPS updated',
    similar_fetch_failed: 'Could not load similar photos',
    similar_fetch_error: 'Error while loading similar photos',
    similar_view_title: 'Similar photos',
    similar_view_subtitle: 'Found via image embedding',
    raw_meta_show: 'Show raw metadata (JSON)',
    raw_meta_hide: 'Hide raw metadata (JSON)',
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
  if (!els.aiIngestToggle) return;
  const enabled = !!state.aiAutoEnabled || !!state.aiRunning;
  els.aiIngestToggle.checked = enabled;
  if (els.aiIngestToggleText) {
    els.aiIngestToggleText.textContent = enabled ? tr('btn_stop_ai') : tr('btn_start_ai');
  }
}

function updateAiDescribeToggleButton() {
  if (!els.aiDescribeToggle) return;
  const enabled = !!state.aiDescribeAutoEnabled || !!state.aiDescribeRunning;
  els.aiDescribeToggle.checked = enabled;
  if (els.aiDescribeToggleText) {
    els.aiDescribeToggleText.textContent = enabled ? tr('btn_stop_ai_desc') : tr('btn_start_ai_desc');
  }
}

function updateFacesToggleButton() {
  if (!els.facesToggle) return;
  const enabled = !!state.facesAutoEnabled || !!state.facesRunning;
  els.facesToggle.checked = enabled;
  if (els.facesToggleText) {
    els.facesToggleText.textContent = enabled ? tr('btn_stop_faces') : tr('btn_start_faces');
  }
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
  aiAutoEnabled: false,
  aiDescribeRunning: false,
  aiDescribeAutoEnabled: false,
  facesRunning: false,
  facesAutoEnabled: false,
  aiScopePendingFeature: null,
  shareDuckdnsConfigured: false,
  shareDuckdnsEffectiveBaseUrl: '',
  sharedLinks: [],
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
      caret.title = isExpanded ? tr('mapper_tree_collapse') : tr('mapper_tree_expand');
      caret.setAttribute('aria-label', isExpanded ? tr('mapper_tree_collapse') : tr('mapper_tree_expand'));
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
  const cleaned = raw
    .split('/')
    .map(s => s.trim())
    .filter(s => s && s !== '.' && s !== '..')
    .join('/');
  if (!cleaned) return '';
  if (cleaned === 'uploads') return '';
  if (cleaned.startsWith('uploads/')) return cleaned.slice('uploads/'.length);
  return cleaned;
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
  const allAiTags = [
    ...((item.ai_tags && item.ai_tags.length) ? item.ai_tags : []),
    ...((item.ai_desc_tags && item.ai_desc_tags.length) ? item.ai_desc_tags : []),
  ];
  const dedupAiTags = Array.from(new Set(allAiTags.map((t) => String(t || '').trim()).filter(Boolean)));
  els.detailAiTags.textContent = dedupAiTags.length ? dedupAiTags.join(", ") : "-";
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
  const extRaw = String((item && (item.ext || item.filename || item.rel_path)) || '').toLowerCase();
  const isGif = extRaw.endsWith('.gif');
  const thumb = item.thumb_url
    ? `<div class="card-thumb"><img loading="lazy" decoding="async" src="${item.thumb_url}" alt=""></div>`
    : `<div class="card-thumb placeholder">${item.is_video ? '🎬 Video' : (isGif ? 'GIF' : escapeHtml(tr('no_thumb')))}</div>`;
  const videoOverlay = item.is_video
    ? `<div class="video-badge" aria-label="Video" title="Video"><span class="video-badge-icon" aria-hidden="true"></span></div>`
    : "";
  const gifOverlay = (!item.is_video && isGif)
    ? `<div class="gif-badge" aria-label="GIF" title="GIF">GIF</div>`
    : "";
  const uploadedByRaw = String(item && item.uploaded_by ? item.uploaded_by : '').trim();
  const uploadedBy = uploadedByRaw ? escapeHtml(uploadedByRaw) : '';
  const uploaderTag = uploadedBy
    ? `<div class="uploader-badge" title="Uploadet af ${uploadedBy}">👤 ${uploadedBy}</div>`
    : "";

  // Gridkort uden extra tekst/metadata – kun selve billedet
  return `${thumb}${videoOverlay}${gifOverlay}${uploaderTag}`;
}

// Render a large People list in small chunks to avoid UI jank/crashes
function appendPeopleInChunks(people, chunkSize = 48) {
  if (!els.grid) return;
  let index = 0;
  // Queue for sequential image loading (1 at a time)
  const pendingImgs = [];
  let imgLoading = false;

  function _ensureImgStyles(img) {
    try {
      if (!img) return;
      // Guarantee correct cover/crop immediately
      img.style.width = '100%';
      img.style.height = '100%';
      img.style.objectFit = 'cover';
      img.style.objectPosition = 'center center';
      img.style.display = 'block';
    } catch {}
  }

  function loadNextImg() {
    if (!pendingImgs.length) { imgLoading = false; return; }
    imgLoading = true;
    const img = pendingImgs.shift();
    if (!img) { loadNextImg(); return; }
    const src = img.getAttribute('data-src');
    if (!src) { loadNextImg(); return; }
    const cleanup = () => {
      img.removeEventListener('load', onload);
      img.removeEventListener('error', onerror);
      img.removeEventListener('abort', onerror);
    };
    const onload = () => { cleanup(); loadNextImg(); };
    const onerror = () => { cleanup(); loadNextImg(); };
    img.addEventListener('load', onload, { once: true });
    img.addEventListener('error', onerror, { once: true });
    img.addEventListener('abort', onerror, { once: true });
    // Defer a tiny bit to allow layout to settle
    (window.requestIdleCallback || window.requestAnimationFrame)(() => {
      _ensureImgStyles(img);
      // Force a reflow so object-fit takes effect immediately on some browsers
      try { void img.offsetWidth; } catch {}
      img.setAttribute('src', src);
      img.removeAttribute('data-src');
    });
  }

  function enqueueImgsFrom(node) {
    // Find any newly added images with data-src
    const imgs = node.querySelectorAll('img[data-src]');
    imgs.forEach((im) => pendingImgs.push(im));
    if (!imgLoading) loadNextImg();
  }
  function step() {
    const end = Math.min(index + chunkSize, people.length);
    const frag = document.createDocumentFragment();
    for (; index < end; index += 1) {
      const p = people[index];
      const card = document.createElement('article');
      card.className = 'photo-card';
      const imgHtml = p.thumb_url
        ? `<img data-src="${p.thumb_url}" alt="${escapeHtml(p.name || '')}" loading="lazy" decoding="async" style="width:100%;height:100%;object-fit:cover;object-position:center center;display:block;">`
        : `<div class="card-thumb placeholder">🙂</div>`;
      card.innerHTML = `
        <div class="card-thumb">${imgHtml}</div>
        <div class="card-body">
          <h4 class="card-title">${escapeHtml(p.name || tr('person_unknown'))}</h4>
          <div class="card-meta"><span>${p.count||0} ${escapeHtml(tr('person_count_suffix'))}</span></div>
          <div class="pills">${p.hidden ? `<span class="pill">${escapeHtml(tr('person_hidden_badge'))}</span>` : ''}</div>
          <div class="actions" style="margin-top:6px;display:flex;gap:6px;">
            <button class="btn tiny" data-act="rename">${escapeHtml(tr('person_btn_rename'))}</button>
            ${p.id==='unknown' ? '' : `<button class="btn tiny ${p.hidden?'':'danger'}" data-act="${p.hidden?'unhide':'hide'}">${escapeHtml(p.hidden ? tr('person_btn_unhide') : tr('person_btn_hide'))}</button>`}
          </div>
        </div>
      `;
      card.querySelectorAll('img').forEach((el) => { el.setAttribute('draggable', 'false'); });
      card.addEventListener('click', (e)=>{
        if (e.target && e.target.closest('[data-act]')) return;
        if (p.id === 'unknown') loadPersonPhotos('unknown', tr('person_unknown'));
        else loadPersonPhotos(p.id, p.name);
      });
      const renBtn = card.querySelector('[data-act="rename"]');
      if (renBtn) renBtn.addEventListener('click', async (e)=>{ e.preventDefault(); e.stopPropagation(); openPersonRenameMenu(e.currentTarget, p); });
      const hideBtn = card.querySelector('[data-act="hide"]');
      if (hideBtn) hideBtn.addEventListener('click', async (e)=>{ e.preventDefault(); e.stopPropagation(); if (!confirm(tr('person_hide_confirm'))) return; try { const r = await fetch(`/api/people/${p.id}/hide`, { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ hidden: true })}); const d = await r.json(); if (!r.ok || !d.ok) { showStatus(d.error || tr('person_hide_failed'), 'err'); return; } showStatus(tr('person_hidden_ok'), 'ok'); loadPeople(); } catch { showStatus(tr('person_hide_error'), 'err'); } });
      const unhideBtn = card.querySelector('[data-act="unhide"]');
      if (unhideBtn) unhideBtn.addEventListener('click', async (e)=>{ e.preventDefault(); e.stopPropagation(); try { const r = await fetch(`/api/people/${p.id}/hide`, { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ hidden: false })}); const d = await r.json(); if (!r.ok || !d.ok) { showStatus(d.error || tr('person_unhide_failed'), 'err'); return; } showStatus(tr('person_unhidden_ok'), 'ok'); loadPeople(); } catch { showStatus(tr('person_unhide_error'), 'err'); } });
      frag.appendChild(card);
    }
    els.grid.appendChild(frag);
    enqueueImgsFrom(els.grid);
    if (index < people.length) {
      // Yield to browser to paint and handle input, then continue
      (window.requestIdleCallback || window.requestAnimationFrame)(step);
    }
  }
  step();
}

function renderGrid() {
  // Toggle fixed-width columns for folder view
  if (els.grid) els.grid.classList.toggle("folders-view", state.view === "mapper");
  if (els.mapperTools) els.mapperTools.classList.add("hidden");
  // Always hide special panels first
  if (els.settingsPanel) els.settingsPanel.classList.add("hidden");
  if (els.placesMapWrap) els.placesMapWrap.classList.add("hidden");
  // Handle Settings view
  if (state.view === "settings") {
    els.grid.innerHTML = "";
    if (els.settingsPanel) els.settingsPanel.classList.remove("hidden");
    const activeBtn = document.querySelector('#settingsPanel .tab-btn.active');
    const activeTab = activeBtn ? activeBtn.getAttribute('data-tab') : null;
    if (activeTab) {
      document.querySelectorAll('#settingsPanel .tab-panel').forEach(p => {
        p.classList.toggle('hidden', p.dataset.tabpanel !== activeTab);
      });
    }
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
      // Render in chunks to avoid main-thread spikes when many people exist
      appendPeopleInChunks(people);
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
    const directItems = [];
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
      let folder = rel.includes('/') ? rel.split('/').slice(0, -1).join('/') : '';
      if (folder === 'uploads') folder = '';
      else if (folder.startsWith('uploads/')) folder = folder.slice('uploads/'.length);
      if (folder === current) {
        directItems.push(it);
      }
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
    if (!sorted.length && !directItems.length) {
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
    directItems.forEach((it) => appendCard(it));
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
  card.querySelectorAll('img').forEach((img) => {
    img.setAttribute('draggable', 'false');
  });
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
  card.querySelectorAll('img').forEach((img) => {
    img.setAttribute('draggable', 'false');
  });
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

let personRenameMenuEl = null;

function closePersonRenameMenu() {
  if (personRenameMenuEl && personRenameMenuEl.parentElement) {
    personRenameMenuEl.parentElement.removeChild(personRenameMenuEl);
  }
  personRenameMenuEl = null;
}

async function renameOrMergePerson(pid, name) {
  const nv = String(name || '').trim();
  if (!nv) return;
  try {
    const r = await fetch(`/api/people/${pid}/rename`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: nv }),
    });
    const d = await r.json().catch(() => ({}));
    if (!r.ok || !d.ok) {
      showStatus(d.error || tr('person_rename_save_failed'), 'err');
      return;
    }
    if (d.merged) showStatus(`${tr('person_rename_merged')} '${d.name || nv}'`, 'ok');
    else showStatus(tr('person_name_updated'), 'ok');
    closePersonRenameMenu();
    loadPeople();
  } catch {
    showStatus(tr('person_rename_merge_error'), 'err');
  }
}

function openPersonRenameMenu(anchorBtn, person) {
  closePersonRenameMenu();
  if (!anchorBtn || !person || person.id === 'unknown') {
    if (person && person.id === 'unknown') showStatus(tr('person_unknown_cannot_rename'), 'err');
    return;
  }

  const menu = document.createElement('div');
  menu.className = 'person-rename-menu';
  menu.innerHTML = `
    <div class="person-rename-head">${escapeHtml(tr('person_rename_title'))}</div>
    <div class="person-rename-create-row">
      <input type="text" class="person-rename-input" placeholder="${escapeHtml(tr('person_rename_new_placeholder'))}" value="" />
      <button type="button" class="btn tiny primary" data-act="create">${escapeHtml(tr('person_rename_save'))}</button>
    </div>
    <div class="person-rename-divider"></div>
    <div class="person-rename-list"></div>
  `;

  const listEl = menu.querySelector('.person-rename-list');
  const existing = (Array.isArray(state.people) ? state.people : [])
    .filter((it) => it && it.id !== 'unknown' && Number(it.id) !== Number(person.id) && String(it.name || '').trim())
    .sort((a, b) => String(a.name || '').localeCompare(String(b.name || ''), 'da-DK'));

  if (!existing.length) {
    listEl.innerHTML = `<div class="person-rename-empty">${escapeHtml(tr('person_rename_none'))}</div>`;
  } else {
    existing.forEach((it) => {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'person-rename-option';
      btn.textContent = String(it.name || tr('person_unknown'));
      btn.addEventListener('click', async () => {
        await renameOrMergePerson(person.id, String(it.name || ''));
      });
      listEl.appendChild(btn);
    });
  }

  const input = menu.querySelector('.person-rename-input');
  const createBtn = menu.querySelector('[data-act="create"]');
  const createNow = async () => {
    const val = String(input && input.value ? input.value : '').trim();
    if (!val) {
      input && input.focus();
      return;
    }
    await renameOrMergePerson(person.id, val);
  };
  createBtn && createBtn.addEventListener('click', createNow);
  input && input.addEventListener('keydown', async (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      await createNow();
    }
    if (e.key === 'Escape') {
      e.preventDefault();
      closePersonRenameMenu();
    }
  });

  document.body.appendChild(menu);
  const rect = anchorBtn.getBoundingClientRect();
  const top = Math.min(window.innerHeight - 12, rect.bottom + 6 + window.scrollY);
  const left = Math.min(window.innerWidth - 12, rect.left + window.scrollX);
  menu.style.top = `${top}px`;
  menu.style.left = `${left}px`;
  personRenameMenuEl = menu;
  if (input) {
    try { input.focus(); } catch {}
  }

  window.setTimeout(() => {
    const onDocClick = (ev) => {
      const target = ev.target;
      if (!personRenameMenuEl) {
        document.removeEventListener('click', onDocClick, true);
        return;
      }
      if (target && (personRenameMenuEl.contains(target) || anchorBtn.contains(target))) return;
      closePersonRenameMenu();
      document.removeEventListener('click', onDocClick, true);
    };
    document.addEventListener('click', onDocClick, true);
  }, 0);
}

function appendPersonCard(p) {
  const card = document.createElement('article');
  card.className = 'photo-card';
  const img = p.thumb_url ? `<img src="${p.thumb_url}" alt="${p.name}" loading="lazy" decoding="async">` : `<div class="card-thumb placeholder">🙂</div>`;
  card.innerHTML = `
    <div class="card-thumb">${img}</div>
    <div class="card-body">
      <h4 class="card-title">${escapeHtml(p.name || tr('person_unknown'))}</h4>
      <div class="card-meta"><span>${p.count||0} ${escapeHtml(tr('person_count_suffix'))}</span></div>
      <div class="pills">${p.hidden ? `<span class="pill">${escapeHtml(tr('person_hidden_badge'))}</span>` : ''}</div>
      <div class="actions" style="margin-top:6px;display:flex;gap:6px;">
        <button class="btn tiny" data-act="rename">${escapeHtml(tr('person_btn_rename'))}</button>
        ${p.id==='unknown' ? '' : `<button class="btn tiny ${p.hidden?'':'danger'}" data-act="${p.hidden?'unhide':'hide'}">${escapeHtml(p.hidden ? tr('person_btn_unhide') : tr('person_btn_hide'))}</button>`}
      </div>
    </div>
  `;
  card.querySelectorAll('img').forEach((el) => {
    el.setAttribute('draggable', 'false');
  });
  // Klik på hele kortet åbner personens billeder (undtagen når man klikker på en knap)
  card.addEventListener('click', (e)=>{
    if (e.target && e.target.closest('[data-act]')) return;
    if (p.id === 'unknown') loadPersonPhotos('unknown', tr('person_unknown'));
    else loadPersonPhotos(p.id, p.name);
  });
  card.querySelector('[data-act="rename"]').addEventListener('click', async (e)=>{
    e.preventDefault();
    e.stopPropagation();
    openPersonRenameMenu(e.currentTarget, p);
  });
  const hideBtn = card.querySelector('[data-act="hide"]');
  if (hideBtn) {
    hideBtn.addEventListener('click', async ()=>{
      if (!confirm(tr('person_hide_confirm'))) return;
      try {
        const r = await fetch(`/api/people/${p.id}/hide`, { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ hidden: true })});
        const d = await r.json();
        if (!r.ok || !d.ok) { showStatus(d.error || tr('person_hide_failed'), 'err'); return; }
        showStatus(tr('person_hidden_ok'), 'ok');
        loadPeople();
      } catch { showStatus(tr('person_hide_error'), 'err'); }
    });
  }
  const unhideBtn = card.querySelector('[data-act="unhide"]');
  if (unhideBtn) {
    unhideBtn.addEventListener('click', async ()=>{
      try {
        const r = await fetch(`/api/people/${p.id}/hide`, { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ hidden: false })});
        const d = await r.json();
        if (!r.ok || !d.ok) { showStatus(d.error || tr('person_unhide_failed'), 'err'); return; }
        showStatus(tr('person_unhidden_ok'), 'ok');
        loadPeople();
      } catch { showStatus(tr('person_unhide_error'), 'err'); }
    });
  }
  els.grid.appendChild(card);
}

// Viewer controls
let viewerTransitionRunning = false;
let viewerPendingStep = 0;

function cleanupViewerMediaAnimation() {
  [els.viewerImg, els.viewerVideo].forEach((node) => {
    if (!node) return;
    node.style.transition = '';
    node.style.transform = '';
    node.style.opacity = '';
    node.style.willChange = '';
  });
}

function getActiveViewerMediaElement() {
  if (els.viewerVideo && els.viewerVideo.style.display !== 'none') return els.viewerVideo;
  if (els.viewerImg && els.viewerImg.style.display !== 'none') return els.viewerImg;
  return els.viewerImg || els.viewerVideo || null;
}

function animateViewerSlideTransition(step, applyUpdate) {
  if (!els.viewer || els.viewer.classList.contains('hidden')) {
    applyUpdate();
    return;
  }
  const fromEl = getActiveViewerMediaElement();
  if (!fromEl) {
    applyUpdate();
    return;
  }

  const duration = 180;
  const distance = Math.min(Math.round(window.innerWidth * 0.22), 160);
  const outX = step > 0 ? -distance : distance;
  const inStartX = step > 0 ? distance : -distance;

  fromEl.style.willChange = 'transform, opacity';
  fromEl.style.transition = `transform ${duration}ms ease, opacity ${duration}ms ease`;
  fromEl.style.transform = `translateX(${outX}px)`;
  fromEl.style.opacity = '0';

  window.setTimeout(() => {
    applyUpdate();
    const toEl = getActiveViewerMediaElement();
    if (!toEl) {
      cleanupViewerMediaAnimation();
      return;
    }

    toEl.style.willChange = 'transform, opacity';
    toEl.style.transition = 'none';
    toEl.style.transform = `translateX(${inStartX}px)`;
    toEl.style.opacity = '0';

    requestAnimationFrame(() => {
      toEl.style.transition = `transform ${duration}ms ease, opacity ${duration}ms ease`;
      toEl.style.transform = 'translateX(0)';
      toEl.style.opacity = '1';
    });

    window.setTimeout(() => {
      cleanupViewerMediaAnimation();
      viewerTransitionRunning = false;
      if (viewerPendingStep !== 0) {
        const pending = viewerPendingStep;
        viewerPendingStep = 0;
        nextViewer(pending);
      }
    }, duration + 30);
  }, duration);
}

function openViewer(index) {
  state.selectedIndex = index;
  const it = state.items[index];
  if (!it || !it.original_url) return;
  if (!els.viewer) return;
  // Toggle media elements
  if (els.viewerImg) {
    els.viewerImg.setAttribute('draggable', 'false');
    els.viewerImg.style.display = it.is_video ? 'none' : 'block';
    if (!it.is_video) {
      // Always use the server-provided original_url (it serves a viewable copy for HEIC/HEIF)
      els.viewerImg.src = it.original_url || it.thumb_url || '';
    }
    if (it.is_video) els.viewerImg.removeAttribute('src');
  }
  if (els.viewerVideo) {
    els.viewerVideo.setAttribute('draggable', 'false');
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
  if (viewerTransitionRunning) {
    viewerPendingStep = step;
    return;
  }
  const n = state.items.length;
  const targetIndex = (state.selectedIndex + step + n) % n;
  const it = state.items[targetIndex];
  if (!it || !it.original_url) return;
  viewerTransitionRunning = true;
  state.selectedIndex = targetIndex;
  animateViewerSlideTransition(step, () => openViewer(state.selectedIndex));
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
  closePersonRenameMenu();
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

const uploadUiState = {
  totalFiles: 0,
  totalBytes: 0,
  processedFiles: 0,
  processedBytes: 0,
  failedFiles: 0,
  currentFileName: '',
  currentPhaseLabel: '',
  currentLoaded: 0,
  currentTotal: 0,
  collapsed: false,
};

let uploadOverlayHideTimer = null;
let activeTusUpload = null;
let uploadStopRequested = false;
let uploadWasStopped = false;
let uploadTransferActive = false;
let uploadLiveRefreshBusy = false;
let uploadLiveRefreshAt = 0;
let uploadImmediateRevealDone = false;
let uploadQueuePumpRunning = false;
let uploadBatchSeq = 0;
let uploadSessionSavedTotal = 0;
const uploadQueue = [];
const uploadMonitorItemsByKey = new Map();
const UPLOAD_RESUME_DRAFT_KEY = 'fjordlens.upload.resumeDraft.v1';
const UPLOAD_RESUME_DRAFT_TTL_MS = 12 * 60 * 60 * 1000;

function _uploadFileSignature(file) {
  return [
    String(file && file.name ? file.name : ''),
    String(Number(file && file.size ? file.size : 0)),
    String(Number(file && file.lastModified ? file.lastModified : 0)),
  ].join('|');
}

function _normalizeUploadDraft(raw) {
  if (!raw || typeof raw !== 'object') return null;
  const now = Date.now();
  const createdAt = Number(raw.createdAt || 0);
  const updatedAt = Number(raw.updatedAt || createdAt || now);
  if (!createdAt || (now - updatedAt) > UPLOAD_RESUME_DRAFT_TTL_MS) return null;
  const pending = Array.isArray(raw.pending)
    ? raw.pending.map((v) => String(v || '').trim()).filter(Boolean)
    : [];
  if (!pending.length) return null;
  return {
    destination: String(raw.destination || ''),
    subdir: String(raw.subdir || ''),
    pending,
    createdAt,
    updatedAt,
  };
}

function _readUploadResumeDraft() {
  try {
    const raw = window.localStorage.getItem(UPLOAD_RESUME_DRAFT_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    const normalized = _normalizeUploadDraft(parsed);
    if (!normalized) {
      window.localStorage.removeItem(UPLOAD_RESUME_DRAFT_KEY);
      return null;
    }
    return normalized;
  } catch {
    return null;
  }
}

function _writeUploadResumeDraft(draft) {
  const normalized = _normalizeUploadDraft(draft);
  if (!normalized) {
    try { window.localStorage.removeItem(UPLOAD_RESUME_DRAFT_KEY); } catch {}
    return;
  }
  try {
    window.localStorage.setItem(UPLOAD_RESUME_DRAFT_KEY, JSON.stringify(normalized));
  } catch {}
}

function _clearUploadResumeDraft() {
  try { window.localStorage.removeItem(UPLOAD_RESUME_DRAFT_KEY); } catch {}
}

function _queueUploadDraftFiles(files, destination = '', subdir = '') {
  const existing = _readUploadResumeDraft();
  const sameTarget = !!existing
    && String(existing.destination || '') === String(destination || '')
    && String(existing.subdir || '') === String(subdir || '');
  const pending = sameTarget ? Array.from(existing.pending || []) : [];
  const set = new Set(pending);
  for (const file of (files || [])) {
    set.add(_uploadFileSignature(file));
  }
  _writeUploadResumeDraft({
    destination: String(destination || ''),
    subdir: String(subdir || ''),
    pending: Array.from(set),
    createdAt: sameTarget && existing ? Number(existing.createdAt || Date.now()) : Date.now(),
    updatedAt: Date.now(),
  });
}

function _markUploadDraftFileDone(file) {
  const draft = _readUploadResumeDraft();
  if (!draft) return;
  const sig = _uploadFileSignature(file);
  const pending = (draft.pending || []).filter((v) => v !== sig);
  if (!pending.length) {
    _clearUploadResumeDraft();
    return;
  }
  _writeUploadResumeDraft({
    destination: draft.destination,
    subdir: draft.subdir,
    pending,
    createdAt: Number(draft.createdAt || Date.now()),
    updatedAt: Date.now(),
  });
}

function _announceUploadResumeDraftIfNeeded() {
  const draft = _readUploadResumeDraft();
  if (!draft || !(draft.pending || []).length) return;
  const pathTxt = String(draft.subdir || '').trim() || 'root';
  showStatus(
    `Upload kan genoptages: vælg de samme ${draft.pending.length} fil(er) igen (${pathTxt}) for at fortsætte via TUS.`,
    'ok'
  );
}

function _maybeAnnounceAutoResumeForBatch(files, destination = '', subdir = '') {
  const draft = _readUploadResumeDraft();
  if (!draft) return;
  if (String(draft.destination || '') !== String(destination || '')) return;
  if (String(draft.subdir || '') !== String(subdir || '')) return;
  const pending = new Set((draft.pending || []).map((v) => String(v || '').trim()).filter(Boolean));
  if (!pending.size) return;
  let matched = 0;
  for (const file of (files || [])) {
    if (pending.has(_uploadFileSignature(file))) matched += 1;
  }
  if (matched > 0) {
    showStatus(`Genoptager upload via TUS for ${matched} fil(er)…`, 'ok');
  }
}

function shouldWarnOnPageLeaveDuringUpload() {
  if (isUploadRunning() || uploadQueuePumpRunning) return true;
  const draft = _readUploadResumeDraft();
  return !!(draft && Array.isArray(draft.pending) && draft.pending.length > 0);
}

window.addEventListener('beforeunload', (event) => {
  if (!shouldWarnOnPageLeaveDuringUpload()) return;
  // Browsers ignore custom text, but setting returnValue triggers a confirmation dialog.
  event.preventDefault();
  event.returnValue = '';
});

async function maybeRefreshPhotosDuringPostprocess(force = false) {
  if (!(state.view === 'mapper' || state.view === 'timeline')) return;
  if (uploadLiveRefreshBusy) return;
  const now = Date.now();
  if (!force && (now - uploadLiveRefreshAt) < 2500) return;
  uploadLiveRefreshBusy = true;
  uploadLiveRefreshAt = now;
  try {
    await loadPhotos();
  } catch {}
  uploadLiveRefreshBusy = false;
}

function hideUploadOverlay() {
  ensureUploadOverlayRefs();
  if (!els.uploadOverlay) return;
  els.uploadOverlay.classList.remove('active', 'upload-ready', 'upload-blocked');
  els.uploadOverlay.classList.add('hidden');
}

function isUploadRunning() {
  return !!uploadTransferActive;
}

function resetUploadUiState() {
  uploadUiState.totalFiles = 0;
  uploadUiState.totalBytes = 0;
  uploadUiState.processedFiles = 0;
  uploadUiState.processedBytes = 0;
  uploadUiState.failedFiles = 0;
  uploadUiState.currentFileName = '';
  uploadUiState.currentPhaseLabel = '';
  uploadUiState.currentLoaded = 0;
  uploadUiState.currentTotal = 0;
  uploadMonitorItemsByKey.clear();
}

function setUploadStopButtonState() {
  ensureUploadMonitorRefs();
  if (!els.uploadMonitorStop) return;
  const running = isUploadRunning();
  els.uploadMonitorStop.disabled = !running || uploadStopRequested;
  els.uploadMonitorStop.textContent = uploadStopRequested ? 'Stopper…' : 'Stop upload';
}

function _uploadItemKey(name, index = null) {
  const safeName = String(name || '').trim() || '(ukendt fil)';
  return index === null || index === undefined
    ? safeName
    : `${safeName}::${String(index)}`;
}

function _setUploadMonitorItemProgress(key, pct) {
  const ref = uploadMonitorItemsByKey.get(String(key || ''));
  if (!ref || !ref.progressBar) return;
  const value = Math.max(0, Math.min(100, Number(pct || 0)));
  ref.progressBar.style.width = `${value}%`;
}

function updateUploadMonitorItem(key, ok, detail = '', progressPct = null) {
  const ref = uploadMonitorItemsByKey.get(String(key || ''));
  if (!ref || !ref.statusEl) return;
  ref.statusEl.classList.remove('ok', 'err', 'work');
  ref.statusEl.classList.add(ok === null ? 'work' : (ok ? 'ok' : 'err'));
  ref.statusEl.textContent = String(detail || (ok === null ? 'Arbejder…' : (ok ? 'OK' : 'Fejl')));
  if (progressPct !== null && progressPct !== undefined) {
    _setUploadMonitorItemProgress(key, progressPct);
  }
}

function requestStopUpload() {
  if (!isUploadRunning() || uploadStopRequested) return;
  uploadStopRequested = true;
  uploadWasStopped = true;
  uploadUiState.currentFileName = 'Stopper upload…';
  try {
    if (activeTusUpload && typeof activeTusUpload.abort === 'function') {
      activeTusUpload.abort();
    }
  } catch {}
  setUploadStopButtonState();
  renderUploadMonitor();
}

function renderUploadMonitor() {
  ensureUploadTopStatusRefs();
  ensureUploadMonitorRefs();
  const transferLoaded = uploadTransferActive ? uploadUiState.currentLoaded : 0;
  const processedVisualBytes = Math.min(uploadUiState.totalBytes, uploadUiState.processedBytes + transferLoaded);
  const overallPct = uploadUiState.totalBytes > 0
    ? Math.max(0, Math.min(100, Math.round((processedVisualBytes / uploadUiState.totalBytes) * 100)))
    : 0;
  const phaseKey = String(uploadUiState.currentPhaseLabel || '').toLowerCase();
  const isPostprocess = !!phaseKey && phaseKey !== 'uploader';
  const stagePct = uploadUiState.currentTotal > 0
    ? Math.max(0, Math.min(100, Math.round((uploadUiState.currentLoaded / uploadUiState.currentTotal) * 100)))
    : 0;
  const stageTxt = uploadUiState.currentTotal > 0
    ? `${uploadUiState.currentLoaded}/${uploadUiState.currentTotal}`
    : 'venter…';

  if (els.uploadTopStatus) {
    const hasTopStatus = isUploadRunning() || isPostprocess || !!String(uploadUiState.currentFileName || '').trim();
    if (hasTopStatus) {
      const activePct = isPostprocess ? stagePct : overallPct;
      const topLabel = isPostprocess
        ? `${uploadUiState.currentPhaseLabel} · ${stageTxt} · ${activePct}%`
        : `Uploader · ${Math.max(0, Math.min(uploadUiState.totalFiles, uploadUiState.processedFiles + (uploadUiState.currentFileName ? 1 : 0)))}/${uploadUiState.totalFiles} · ${activePct}%`;
      els.uploadTopStatus.classList.remove('hidden');
      if (els.uploadTopStatusLabel) els.uploadTopStatusLabel.textContent = topLabel;
      if (els.uploadTopStatusBar) els.uploadTopStatusBar.style.width = `${activePct}%`;
    } else {
      els.uploadTopStatus.classList.add('hidden');
      if (els.uploadTopStatusBar) els.uploadTopStatusBar.style.width = '0%';
      if (els.uploadTopStatusLabel) els.uploadTopStatusLabel.textContent = 'Upload: Klar';
    }
  }

  if (!els.uploadMonitor) return;
  setUploadStopButtonState();

  if (els.uploadMonitorBar) els.uploadMonitorBar.style.width = `${overallPct}%`;
  if (els.uploadMonitorSummary) {
    const failedTxt = uploadUiState.failedFiles ? ` · fejl: ${uploadUiState.failedFiles}` : '';
    els.uploadMonitorSummary.textContent = `${uploadUiState.processedFiles}/${uploadUiState.totalFiles} filer · ${fmtBytes(processedVisualBytes)}/${fmtBytes(uploadUiState.totalBytes)} · ${overallPct}%${failedTxt}`;
  }
  if (els.uploadMonitorCurrent) {
    if (isPostprocess) {
      els.uploadMonitorCurrent.textContent = 'Upload fuldført';
    } else if (uploadUiState.currentFileName) {
      const filePct = uploadUiState.currentTotal > 0
        ? Math.max(0, Math.min(100, Math.round((uploadUiState.currentLoaded / uploadUiState.currentTotal) * 100)))
        : 0;
      const phasePrefix = String(uploadUiState.currentPhaseLabel || '').trim() || 'Uploader';
      els.uploadMonitorCurrent.textContent = `${phasePrefix}: ${uploadUiState.currentFileName} (${filePct}%)`;
    } else {
      els.uploadMonitorCurrent.textContent = uploadUiState.totalFiles
        ? 'Upload fuldført'
        : 'Ingen aktiv upload';
    }
  }
}

function showUploadMonitor() {
  ensureUploadMonitorRefs();
  bindUploadMonitorDomEvents();
  if (els.uploadMonitor) els.uploadMonitor.classList.remove('hidden');
  const collapsed = !!uploadUiState.collapsed;
  if (els.uploadMonitor) els.uploadMonitor.classList.toggle('collapsed', collapsed);
  if (els.uploadMonitorToggle) {
    els.uploadMonitorToggle.textContent = collapsed ? 'Vis detaljer' : 'Minimer';
  }
  setUploadStopButtonState();
}

function addUploadMonitorItem(name, ok, detail = '', key = null, progressPct = null) {
  ensureUploadMonitorRefs();
  if (!els.uploadMonitorList) return;
  const li = document.createElement('li');
  li.className = 'upload-monitor-item';
  const safeName = String(name || '').trim() || '(ukendt fil)';
  const itemKey = String(key || _uploadItemKey(safeName));
  const statusClass = ok ? 'ok' : 'err';
  const statusText = ok ? 'OK' : 'Fejl';
  li.innerHTML = `
    <div class="upload-monitor-item-top">
      <span class="upload-monitor-item-name" title="${escapeHtml(safeName)}">${escapeHtml(safeName)}</span>
      <span class="upload-monitor-item-status ${statusClass}">${escapeHtml(detail || statusText)}</span>
    </div>
    <div class="upload-monitor-item-progress"><span class="upload-monitor-item-progress-bar" style="width:${Math.max(0, Math.min(100, Number(progressPct || 0)))}%"></span></div>
  `;
  els.uploadMonitorList.insertBefore(li, els.uploadMonitorList.firstChild || null);
  uploadMonitorItemsByKey.set(itemKey, {
    el: li,
    statusEl: li.querySelector('.upload-monitor-item-status'),
    progressBar: li.querySelector('.upload-monitor-item-progress-bar'),
  });
  while (els.uploadMonitorList.children.length > 8) {
    const last = els.uploadMonitorList.lastChild;
    if (!last) break;
    uploadMonitorItemsByKey.forEach((value, k) => {
      if (value && value.el === last) uploadMonitorItemsByKey.delete(k);
    });
    els.uploadMonitorList.removeChild(last);
  }
}

function uploadSingleFile(file, options = {}, onProgress = null) {
  return new Promise((resolve) => {
    const fd = new FormData();
    const safeName = String(file && file.name ? file.name : 'fil');
    fd.append('files', file, safeName);
    fd.append('meta', JSON.stringify([{ name: safeName, lastModified: Number(file && file.lastModified ? file.lastModified : 0) }]));
    const destination = (options && options.destination) ? String(options.destination) : '';
    const subdir = (options && Object.prototype.hasOwnProperty.call(options, 'subdir')) ? String(options.subdir || '') : null;
    if (destination) fd.append('destination', destination);
    if (subdir !== null) fd.append('subdir', subdir);

    const xhr = new XMLHttpRequest();
    xhr.open('POST', '/api/upload');
    xhr.onload = () => {
      let payload = {};
      try { payload = JSON.parse(xhr.responseText || '{}'); } catch {}
      const ok = xhr.status >= 200 && xhr.status < 300 && payload && payload.ok !== false;
      const saved = Array.isArray(payload.saved) ? payload.saved.length : 0;
      const errors = Array.isArray(payload.errors) ? payload.errors : [];
      const errorMsg = (payload && payload.error) || (errors[0] && (errors[0].error || errors[0].name)) || '';
      resolve({ ok, saved, errorMsg });
    };
    xhr.onerror = () => resolve({ ok: false, saved: 0, errorMsg: 'Netværksfejl' });
    xhr.upload.onprogress = (evt) => {
      if (typeof onProgress === 'function') {
        onProgress(Number(evt && evt.loaded ? evt.loaded : 0), Number(evt && evt.total ? evt.total : 0));
      }
    };
    xhr.send(fd);
  });
}

function hasTusClient() {
  return !!(window.tus && typeof window.tus.Upload === 'function');
}

function postprocessPhaseLabel(phase) {
  const key = String(phase || '').toLowerCase();
  if (key === 'metadata') return 'Metadata';
  if (key === 'thumbnails') return 'Thumbnails';
  if (key === 'faces') return 'Ansigtsgenkendelse';
  if (key === 'embeddings') return 'AI embeddings';
  if (key === 'descriptions') return 'AI beskrivelser';
  if (key === 'starting') return 'Starter efterbehandling';
  if (key === 'done') return 'Efterbehandling færdig';
  if (key === 'error') return 'Efterbehandling fejl';
  return 'Efterbehandler';
}

function shortRelName(relPath) {
  const rel = String(relPath || '').trim();
  if (!rel) return '';
  const parts = rel.split('/').filter(Boolean);
  return parts.length ? parts[parts.length - 1] : rel;
}

async function runUploadPostprocess(onProgress = null) {
  const startRes = await fetch('/api/upload/postprocess', { method: 'POST' });
  let startData = {};
  try { startData = await startRes.json(); } catch {}
  if (!startRes.ok || !startData.ok) {
    const msg = (startData && startData.error) ? String(startData.error) : 'Efterbehandling fejlede';
    throw new Error(msg);
  }

  if (!startData.running) {
    return startData.result || {
      ok: true,
      received: 0,
      indexed: 0,
      index_errors: 0,
      faces_enabled: false,
      faces_done: 0,
      faces_errors: 0,
      ai_enabled: false,
      ai_done: 0,
      ai_errors: 0,
      ai_desc_enabled: false,
      ai_desc_done: 0,
      ai_desc_errors: 0,
    };
  }

  const deadline = Date.now() + (30 * 60 * 1000);
  while (Date.now() < deadline) {
    await new Promise((resolve) => window.setTimeout(resolve, 1200));
    const statusRes = await fetch('/api/upload/postprocess/status');
    let statusData = {};
    try { statusData = await statusRes.json(); } catch {}
    if (!statusRes.ok || !statusData.ok) {
      const msg = (statusData && statusData.error) ? String(statusData.error) : 'Efterbehandling status fejlede';
      throw new Error(msg);
    }
    if (statusData.running && typeof onProgress === 'function') {
      onProgress(statusData);
    }
    if (!statusData.running) {
      if (statusData.error) throw new Error(String(statusData.error));
      return statusData.result || {
        ok: true,
        received: 0,
        indexed: 0,
        index_errors: 0,
        faces_enabled: false,
        faces_done: 0,
        faces_errors: 0,
        ai_enabled: false,
        ai_done: 0,
        ai_errors: 0,
        ai_desc_enabled: false,
        ai_desc_done: 0,
        ai_desc_errors: 0,
      };
    }
  }

  throw new Error('Efterbehandling timeout');
}

let uploadPostprocessResumeActive = false;
async function resumeUploadPostprocessAfterRefresh() {
  if (uploadPostprocessResumeActive) return;
  if (uploadQueuePumpRunning || isUploadRunning()) return;
  uploadPostprocessResumeActive = true;
  try {
    const readStatus = async () => {
      const res = await fetch('/api/upload/postprocess/status');
      let data = {};
      try { data = await res.json(); } catch {}
      if (!res.ok || !data || !data.ok) return null;
      return data;
    };

    let status = await readStatus();
    if (!status) return;

    // If a refresh happened before postprocess started, kick it off automatically.
    if (!status.running && Number(status.pending || 0) > 0) {
      try {
        const startRes = await fetch('/api/upload/postprocess', { method: 'POST' });
        let startData = {};
        try { startData = await startRes.json(); } catch {}
        if (!startRes.ok || !startData || !startData.ok) return;
      } catch {
        return;
      }
      status = await readStatus();
      if (!status) return;
    }

    if (!status.running) return;

    uploadUiState.collapsed = false;
    showUploadMonitor();

    while (status && status.running && !uploadQueuePumpRunning && !isUploadRunning()) {
      const stageTotal = Number(status.stage_total || 0);
      const stageProcessed = Number(status.stage_processed || 0);
      if (stageTotal > 0) uploadUiState.totalFiles = Math.max(uploadUiState.totalFiles, stageTotal);
      if (stageProcessed > 0) uploadUiState.processedFiles = Math.max(uploadUiState.processedFiles, stageProcessed);

      uploadUiState.currentPhaseLabel = postprocessPhaseLabel(status.phase);
      uploadUiState.currentFileName = shortRelName(status.current_rel) || 'Arbejder…';
      uploadUiState.currentLoaded = stageProcessed;
      uploadUiState.currentTotal = stageTotal;
      renderUploadMonitor();

      const phase = String(status.phase || '').toLowerCase();
      if (phase === 'metadata' || phase === 'thumbnails' || phase === 'faces') {
        // Refresh during 'faces' too to reveal any thumbnails that finished
        // right at the phase boundary.
        maybeRefreshPhotosDuringPostprocess(false);
      }

      await new Promise((resolve) => window.setTimeout(resolve, 1200));
      status = await readStatus();
    }

    uploadUiState.currentFileName = '';
    uploadUiState.currentPhaseLabel = '';
    uploadUiState.currentLoaded = 0;
    uploadUiState.currentTotal = 0;
    renderUploadMonitor();

    await maybeRefreshPhotosDuringPostprocess(true);
    if (state.view === 'mapper') loadMapperTools();
  } finally {
    uploadPostprocessResumeActive = false;
  }
}

function uploadSingleFileTus(file, options = {}, onProgress = null) {
  return new Promise((resolve) => {
    let settled = false;
    const done = (payload) => {
      if (settled) return;
      settled = true;
      if (activeTusUpload && activeTusUpload.__fjordlens_file === file) {
        activeTusUpload = null;
      }
      resolve(payload);
    };

    if (uploadStopRequested) {
      done({ ok: false, aborted: true, saved: 0, errorMsg: 'Stoppet af bruger' });
      return;
    }

    if (!hasTusClient()) {
      done({ ok: false, saved: 0, errorMsg: 'TUS client unavailable' });
      return;
    }
    const safeName = String(file && file.name ? file.name : 'fil');
    const destination = (options && options.destination) ? String(options.destination) : '';
    const subdir = (options && Object.prototype.hasOwnProperty.call(options, 'subdir')) ? String(options.subdir || '') : '';
    const metadata = {
      filename: safeName,
      destination,
      subdir,
      lastModified: String(Number(file && file.lastModified ? file.lastModified : 0)),
    };

    const upload = new window.tus.Upload(file, {
      endpoint: '/api/upload/tus',
      metadata,
      uploadDataDuringCreation: false,
      chunkSize: 2 * 1024 * 1024,
      parallelUploads: 1,
      retryDelays: [0, 1000, 2500, 5000],
      removeFingerprintOnSuccess: true,
      onShouldRetry(error, retryAttempt, options) {
        try {
          const status = Number(error && error.originalResponse && error.originalResponse.getStatus && error.originalResponse.getStatus());
          if ([502, 503, 504].includes(status)) return true;
        } catch {}
        return window.tus.defaultOptions.onShouldRetry(error, retryAttempt, options);
      },
      onProgress(bytesUploaded, bytesTotal) {
        if (typeof onProgress === 'function') onProgress(Number(bytesUploaded || 0), Number(bytesTotal || 0));
      },
      onError(error) {
        if (uploadStopRequested) {
          done({ ok: false, aborted: true, saved: 0, errorMsg: 'Stoppet af bruger' });
          return;
        }
        const message = (error && error.message) ? String(error.message) : 'Upload fejl';
        done({ ok: false, saved: 0, errorMsg: message });
      },
      onSuccess() {
        done({ ok: true, saved: 1, errorMsg: '' });
      },
    });

    upload.__fjordlens_file = file;
    activeTusUpload = upload;
    setUploadStopButtonState();

    upload.findPreviousUploads().then((previousUploads) => {
      if (uploadStopRequested) {
        done({ ok: false, aborted: true, saved: 0, errorMsg: 'Stoppet af bruger' });
        return;
      }
      if (Array.isArray(previousUploads) && previousUploads.length > 0) {
        upload.resumeFromPreviousUpload(previousUploads[0]);
      }
      upload.start();
    }).catch(() => {
      if (uploadStopRequested) {
        done({ ok: false, aborted: true, saved: 0, errorMsg: 'Stoppet af bruger' });
        return;
      }
      upload.start();
    });
  });
}

async function uploadSingleFileTusWithAutoResume(file, options = {}, onProgress = null, onAttempt = null) {
  const maxAttempts = 3;
  let last = null;
  for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
    if (typeof onAttempt === 'function') {
      try { onAttempt(attempt, maxAttempts); } catch {}
    }
    const result = await uploadSingleFileTus(file, options, onProgress);
    last = result;
    if (!result || result.ok || result.aborted) return result;
    if (attempt >= maxAttempts) break;
    await new Promise((resolve) => window.setTimeout(resolve, 900 * attempt));
  }
  return last || { ok: false, saved: 0, errorMsg: 'Upload fejl' };
}

async function uploadFiles(fileList, options = {}) {
  ensureUploadOverlayRefs();
  ensureUploadMonitorRefs();
  const files = Array.from(fileList || []).filter(f => !!f && f.name);
  if (!files.length) return { ok: false, queued: 0 };
  const destination = (options && options.destination) ? String(options.destination) : '';
  const subdir = (options && Object.prototype.hasOwnProperty.call(options, 'subdir')) ? String(options.subdir || '') : null;
  const totalSize = files.reduce((s,f)=>s+ (f.size||0), 0);

  _maybeAnnounceAutoResumeForBatch(files, destination, subdir || '');
  _queueUploadDraftFiles(files, destination, subdir || '');

  if (!uploadQueuePumpRunning && !isUploadRunning()) {
    resetUploadUiState();
    uploadStopRequested = false;
    uploadWasStopped = false;
    activeTusUpload = null;
    uploadSessionSavedTotal = 0;
    uploadImmediateRevealDone = false;
    uploadUiState.collapsed = false;
    if (els.uploadMonitorList) els.uploadMonitorList.innerHTML = '';

    if (els.uploadOverlay) {
      const titleEl = document.querySelector('#uploadOverlay .upload-title');
      if (titleEl) titleEl.textContent = 'Starter upload…';
      els.uploadOverlay.classList.remove('hidden');
      els.uploadOverlay.classList.add('active', 'upload-ready');
      if (uploadOverlayHideTimer) {
        window.clearTimeout(uploadOverlayHideTimer);
        uploadOverlayHideTimer = null;
      }
      uploadOverlayHideTimer = window.setTimeout(() => {
        hideUploadOverlay();
        uploadOverlayHideTimer = null;
      }, 900);
    }
    if (els.uploadProgressBar) els.uploadProgressBar.style.width = '100%';
  }

  uploadUiState.totalFiles += files.length;
  uploadUiState.totalBytes += totalSize;
  if (els.uploadProgressText) {
    const queuedCount = Math.max(0, uploadUiState.totalFiles - uploadUiState.processedFiles);
    els.uploadProgressText.textContent = `${queuedCount} filer i kø · ${fmtBytes(uploadUiState.totalBytes)}`;
  }
  renderUploadMonitor();
  showUploadMonitor();

  const batchId = ++uploadBatchSeq;
  const batchPromise = new Promise((resolve) => {
    uploadQueue.push({ batchId, files, destination, subdir, resolve });
  });

  if (!uploadQueuePumpRunning) {
    const runQueue = async () => {
      let post = null;
      try {
        uploadQueuePumpRunning = true;
        let finished = false;
        while (!finished) {
          uploadTransferActive = true;
          setUploadStopButtonState();

          while (uploadQueue.length && !uploadStopRequested) {
            const batch = uploadQueue.shift();
            if (!batch) continue;
            let batchSaved = 0;
            let batchFailed = 0;

            for (let fileIndex = 0; fileIndex < batch.files.length; fileIndex += 1) {
              const file = batch.files[fileIndex];
              const itemKey = _uploadItemKey(file.name, `${batch.batchId}-${fileIndex}`);
              if (uploadStopRequested) break;

              uploadUiState.currentPhaseLabel = 'Uploader';
              uploadUiState.currentFileName = file.name || 'fil';
              uploadUiState.currentLoaded = 0;
              uploadUiState.currentTotal = Number(file.size || 0);
              addUploadMonitorItem(file.name, null, 'Uploader… 0%', itemKey, 0);
              renderUploadMonitor();

              if (!hasTusClient()) {
                throw new Error('TUS client mangler i browseren');
              }
              const result = await uploadSingleFileTusWithAutoResume(
                file,
                { destination: batch.destination, subdir: batch.subdir },
                (loaded, total) => {
                uploadUiState.currentLoaded = Number(loaded || 0);
                uploadUiState.currentTotal = Number(total || file.size || 0);
                const pct = Number(total || file.size || 0) > 0
                  ? Math.max(0, Math.min(100, Math.round((Number(loaded || 0) / Number(total || file.size || 0)) * 100)))
                  : 0;
                updateUploadMonitorItem(itemKey, null, `Uploader… ${pct}%`, pct);
                renderUploadMonitor();
                },
                (attempt, maxAttempts) => {
                  if (attempt <= 1) return;
                  updateUploadMonitorItem(itemKey, null, `Genoptager upload… (${attempt}/${maxAttempts})`, null);
                  renderUploadMonitor();
                }
              );

              if (result && result.aborted) {
                updateUploadMonitorItem(itemKey, false, 'Stoppet', 0);
                renderUploadMonitor();
                break;
              }

              uploadUiState.processedFiles += 1;
              uploadUiState.processedBytes += Number(file.size || uploadUiState.currentTotal || 0);
              uploadUiState.currentLoaded = 0;
              uploadUiState.currentTotal = 0;

              if (result.ok) {
                const saved = Number(result.saved || 0) || 1;
                batchSaved += saved;
                uploadSessionSavedTotal += saved;
                _markUploadDraftFileDone(file);
                updateUploadMonitorItem(itemKey, true, `Uploadet · ${fmtBytes(file.size || 0)}`, 100);
                // Do not refresh grid during raw upload; wait until metadata/thumbnails phase
                // so the flow is strictly: upload -> metadata -> thumbnails -> faces/AI.
                // Refreshes now happen from the postprocess progress callback below.
              } else {
                batchFailed += 1;
                uploadUiState.failedFiles += 1;
                updateUploadMonitorItem(itemKey, false, result.errorMsg || 'Fejl', 0);
              }

              renderUploadMonitor();
            }

            try { batch.resolve({ ok: !uploadStopRequested, saved: batchSaved, failed: batchFailed, stopped: !!uploadStopRequested }); } catch {}
          }

          uploadTransferActive = false;
          setUploadStopButtonState();

          if (uploadStopRequested) {
            while (uploadQueue.length) {
              const skipped = uploadQueue.shift();
              if (!skipped) continue;
              try { skipped.resolve({ ok: false, saved: 0, failed: skipped.files.length, stopped: true }); } catch {}
            }
            finished = true;
            break;
          }

          if (uploadUiState.processedFiles <= 0) {
            finished = true;
            break;
          }

          uploadUiState.currentPhaseLabel = 'Efterbehandler';
          uploadUiState.currentFileName = 'Klargør…';
          uploadUiState.currentLoaded = 0;
          uploadUiState.currentTotal = 0;
          renderUploadMonitor();

          try {
            post = await runUploadPostprocess((status) => {
              uploadUiState.currentPhaseLabel = postprocessPhaseLabel(status.phase);
              const n = shortRelName(status.current_rel);
              uploadUiState.currentFileName = n || 'Arbejder…';
              uploadUiState.currentLoaded = Number(status.stage_processed || 0);
              uploadUiState.currentTotal = Number(status.stage_total || 0);
              if (['metadata','thumbnails','faces'].includes(String(status.phase || '').toLowerCase())) {
                maybeRefreshPhotosDuringPostprocess(false);
              }
              renderUploadMonitor();
            });
          } catch (postErr) {
            console.error(postErr);
            showStatus(`Upload færdig, men efterbehandling fejlede: ${postErr && postErr.message ? postErr.message : 'ukendt fejl'}`, 'err');
          }

          if (uploadQueue.length) {
            post = null;
            continue;
          }

          finished = true;
        }

        uploadUiState.currentFileName = '';
        uploadUiState.currentPhaseLabel = '';
        uploadUiState.currentLoaded = 0;
        uploadUiState.currentTotal = 0;
        renderUploadMonitor();

        if (post) {
          const thumbsDone = Math.max(0, Number(post.indexed || 0) - Number(post.thumb_errors || 0));
          const postParts = [
            `thumbs: ${thumbsDone}${Number(post.thumb_errors || 0) ? ` (fejl: ${Number(post.thumb_errors || 0)})` : ''}`,
            `ansigter: ${Number(post.faces_done || 0)}${Number(post.faces_errors || 0) ? ` (fejl: ${Number(post.faces_errors || 0)})` : ''}`,
            `embeddings: ${Number(post.ai_done || 0)}${Number(post.ai_errors || 0) ? ` (fejl: ${Number(post.ai_errors || 0)})` : ''}`,
            `beskrivelser: ${Number(post.ai_desc_done || 0)}${Number(post.ai_desc_errors || 0) ? ` (fejl: ${Number(post.ai_desc_errors || 0)})` : ''}`,
          ];
          showStatus(
            `${uploadWasStopped ? 'Upload stoppet' : 'Upload færdig'}: ${uploadSessionSavedTotal} fil(er)${uploadUiState.failedFiles ? `, fejl: ${uploadUiState.failedFiles}` : ''} · ${postParts.join(' · ')}`,
            (uploadUiState.failedFiles || Number(post.index_errors || 0) || Number(post.faces_errors || 0) || Number(post.ai_errors || 0) || Number(post.ai_desc_errors || 0)) ? 'err' : 'ok'
          );
        } else {
          showStatus(
            `${uploadWasStopped ? 'Upload stoppet' : 'Upload færdig'}: ${uploadSessionSavedTotal} fil(er)${uploadUiState.failedFiles ? `, fejl: ${uploadUiState.failedFiles}` : ''}`,
            uploadUiState.failedFiles ? 'err' : 'ok'
          );
        }

        await maybeRefreshPhotosDuringPostprocess(true);
        if (state.view === 'mapper') {
          loadMapperTools();
        }
      } catch (e) {
        console.error(e);
        showStatus(tr('upload_failed_generic'), 'err');
      } finally {
        activeTusUpload = null;
        uploadStopRequested = false;
        uploadTransferActive = false;
        uploadQueuePumpRunning = false;
        const draft = _readUploadResumeDraft();
        if (draft && !(draft.pending || []).length) {
          _clearUploadResumeDraft();
        }
        if (uploadOverlayHideTimer) {
          window.clearTimeout(uploadOverlayHideTimer);
          uploadOverlayHideTimer = null;
        }
        hideUploadOverlay();
        showUploadMonitor();
      }
    };
    runQueue();
  }

  return batchPromise;
}

function renderMapperContext(path = '') {
  const p = String(path || '');
  const selectedCount = state.mapperSelectedFolders ? state.mapperSelectedFolders.size : 0;
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
    els.mapperEditBtn.textContent = tr('mapper_edit');
    const mapperEditTitle = tr('mapper_edit_title');
    els.mapperEditBtn.title = mapperEditTitle;
    els.mapperEditBtn.setAttribute('aria-label', mapperEditTitle);
  }
  if (els.mapperHeaderEditAction) {
    els.mapperHeaderEditAction.textContent = state.mapperEditMode
      ? (selectedCount > 0 ? `${tr('mapper_delete_selected')} (${selectedCount})` : tr('mapper_menu_done'))
      : tr('mapper_menu_edit');
  }
  if (els.mapperHeaderShareAction) {
    els.mapperHeaderShareAction.textContent = tr('mapper_menu_share');
    const canShare = !!state.mapperEditMode && selectedCount >= 1;
    els.mapperHeaderShareAction.disabled = !canShare;
    els.mapperHeaderShareAction.title = canShare ? tr('mapper_menu_share') : tr('mapper_share_select_one');
  }
  if (els.mapperHeaderCreateAction) {
    els.mapperHeaderCreateAction.textContent = tr('mapper_menu_create');
    els.mapperHeaderCreateAction.disabled = !!state.mapperEditMode;
    els.mapperHeaderCreateAction.title = state.mapperEditMode ? tr('mapper_done_title') : tr('mapper_menu_create');
  }
  if (els.mapperHeaderUploadAction) {
    els.mapperHeaderUploadAction.textContent = tr('mapper_menu_upload');
    els.mapperHeaderUploadAction.disabled = !!state.mapperEditMode;
    els.mapperHeaderUploadAction.title = state.mapperEditMode ? tr('mapper_done_title') : tr('mapper_menu_upload');
  }
  if (els.mapperDeleteBtn) {
    els.mapperDeleteBtn.classList.add('hidden');
    els.mapperDeleteBtn.disabled = true;
    els.mapperDeleteBtn.textContent = tr('mapper_delete_selected');
  }
  renderMapperTree();
}

function showDnsStatus(message, kind = 'ok') {
  if (!els.dnsStatus) return;
  const msg = String(message || '').trim();
  if (!msg) {
    els.dnsStatus.classList.add('hidden');
    els.dnsStatus.textContent = '';
    els.dnsStatus.classList.remove('ok', 'err');
    return;
  }
  els.dnsStatus.textContent = msg;
  els.dnsStatus.classList.remove('hidden');
  els.dnsStatus.classList.toggle('ok', kind === 'ok');
  els.dnsStatus.classList.toggle('err', kind !== 'ok');
}

function showSharedStatus(message, kind = 'ok') {
  if (!els.sharedLinksStatus) return;
  const msg = String(message || '').trim();
  if (!msg) {
    els.sharedLinksStatus.classList.add('hidden');
    els.sharedLinksStatus.textContent = '';
    els.sharedLinksStatus.classList.remove('ok', 'err');
    return;
  }
  els.sharedLinksStatus.textContent = msg;
  els.sharedLinksStatus.classList.remove('hidden');
  els.sharedLinksStatus.classList.toggle('ok', kind === 'ok');
  els.sharedLinksStatus.classList.toggle('err', kind !== 'ok');
}

function _fmtDnsShareTime(isoValue) {
  const raw = String(isoValue || '').trim();
  if (!raw) return tr('dns_shares_never');
  const dt = new Date(raw);
  if (!Number.isFinite(dt.getTime())) return raw;
  try {
    return dt.toLocaleString();
  } catch {
    return raw;
  }
}

async function _copySharedLink(link) {
  const value = String(link || '').trim();
  if (!value) {
    showSharedStatus(tr('dns_shares_link_unavailable'), 'err');
    return;
  }
  try {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      await navigator.clipboard.writeText(value);
    } else {
      const temp = document.createElement('textarea');
      temp.value = value;
      document.body.appendChild(temp);
      temp.select();
      document.execCommand('copy');
      document.body.removeChild(temp);
    }
    showSharedStatus(tr('dns_shares_copy_ok'), 'ok');
  } catch {
    showSharedStatus(tr('dns_shares_copy_failed'), 'err');
  }
}

function renderDnsSharesList() {
  if (!els.sharedLinksList) return;
  const items = Array.isArray(state.sharedLinks) ? state.sharedLinks : [];
  if (!items.length) {
    els.sharedLinksList.innerHTML = `<div class="mini-label">${escapeHtml(tr('dns_shares_empty'))}</div>`;
    return;
  }
  const rows = items.map((item) => {
    const permission = String(item.permission || 'view');
    const permissionLabel = permission === 'manage'
      ? tr('mapper_share_perm_manage')
      : (permission === 'upload' ? tr('mapper_share_perm_upload') : tr('mapper_share_perm_view'));
    const folder = String(item.share_name || '').trim() || `uploads/${String(item.folder_path || '')}`;
    const link = String(item.link || '');
    const linkCell = link
      ? `<div class="mini-label" style="max-width:420px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;" title="${escapeHtml(link)}">${escapeHtml(link)}</div>`
      : `<span class="mini-label">${escapeHtml(tr('dns_shares_link_unavailable'))}</span>`;
    const isActive = !!item.active;
    const actionBtn = isActive
      ? `<button class="btn danger small" data-share-revoke="${Number(item.id || 0)}">${escapeHtml(tr('dns_shares_deactivate'))}</button>`
      : `<button class="btn small" data-share-activate="${Number(item.id || 0)}">${escapeHtml(tr('dns_shares_activate'))}</button>`;
    const deleteBtn = `<button class="btn danger small" data-share-delete="${Number(item.id || 0)}">${escapeHtml(tr('dns_shares_delete'))}</button>`;
    const extendBtn = isActive
      ? `<button class="btn small" data-share-extend="${Number(item.id || 0)}">${escapeHtml(tr('dns_shares_extend'))}</button>`
      : '';
    return `
      <tr>
        <td>${escapeHtml(folder)}</td>
        <td>${escapeHtml(permissionLabel)}</td>
        <td>${escapeHtml(_fmtDnsShareTime(item.expires_at))}</td>
        <td>${escapeHtml(_fmtDnsShareTime(item.last_used_at))}</td>
        <td>${linkCell}</td>
        <td style="text-align:right;">
          <div class="dns-share-actions">
            <button class="btn small" data-share-copy="${Number(item.id || 0)}">${escapeHtml(tr('dns_shares_copy'))}</button>
            ${extendBtn}
            ${actionBtn}
            ${deleteBtn}
          </div>
        </td>
      </tr>
    `;
  }).join('');

  els.sharedLinksList.innerHTML = `
    <div class="data-table">
      <table>
        <thead>
          <tr>
            <th>${escapeHtml(tr('dns_shares_col_folder'))}</th>
            <th>${escapeHtml(tr('dns_shares_col_access'))}</th>
            <th>${escapeHtml(tr('dns_shares_col_expires'))}</th>
            <th>${escapeHtml(tr('dns_shares_col_last_used'))}</th>
            <th>${escapeHtml(tr('dns_shares_col_link'))}</th>
            <th style="text-align:right;">${escapeHtml(tr('dns_shares_col_actions'))}</th>
          </tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
    </div>
  `;
}

async function loadDnsShares() {
  if (!els.sharedLinksList) return;
  showSharedStatus('');
  els.sharedLinksList.innerHTML = `<div class="mini-label">${escapeHtml(tr('dns_shares_loading'))}</div>`;
  try {
    const res = await fetch('/api/admin/shares?include_inactive=1');
    const data = await res.json().catch(() => ({}));
    if (!res.ok || !data || !data.ok) {
      state.sharedLinks = [];
      els.sharedLinksList.innerHTML = `<div class="mini-label">${escapeHtml((data && data.error) || tr('dns_shares_load_failed'))}</div>`;
      return;
    }
    state.sharedLinks = Array.isArray(data.items) ? data.items : [];
    renderDnsSharesList();
  } catch {
    state.sharedLinks = [];
    els.sharedLinksList.innerHTML = `<div class="mini-label">${escapeHtml(tr('dns_shares_load_failed'))}</div>`;
  }
}

async function revokeDnsShare(shareId) {
  if (!shareId) return;
  if (!window.confirm(tr('dns_shares_deactivate_confirm'))) return;
  try {
    const res = await fetch(`/api/admin/shares/${encodeURIComponent(String(shareId))}/revoke`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok || !data || !data.ok) {
      showSharedStatus((data && data.error) || tr('dns_shares_revoke_failed'), 'err');
      return;
    }
    showSharedStatus(tr('dns_shares_deactivate_ok'), 'ok');
    await loadDnsShares();
  } catch {
    showSharedStatus(tr('dns_shares_revoke_failed'), 'err');
  }
}

async function activateDnsShare(shareId) {
  if (!shareId) return;
  const raw = window.prompt(tr('dns_shares_activate_prompt'), '7');
  if (raw === null) return;
  const days = Number(raw);
  if (!Number.isFinite(days) || days < 1) {
    showSharedStatus(tr('dns_shares_activate_failed'), 'err');
    return;
  }
  try {
    const res = await fetch(`/api/admin/shares/${encodeURIComponent(String(shareId))}/activate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ expires_value: Math.floor(days), expires_unit: 'days' }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok || !data || !data.ok) {
      showSharedStatus((data && data.error) || tr('dns_shares_activate_failed'), 'err');
      return;
    }
    showSharedStatus(tr('dns_shares_activate_ok'), 'ok');
    await loadDnsShares();
  } catch {
    showSharedStatus(tr('dns_shares_activate_failed'), 'err');
  }
}

async function deleteDnsShare(shareId) {
  if (!shareId) return;
  if (!window.confirm(tr('dns_shares_delete_confirm'))) return;
  try {
    const res = await fetch(`/api/admin/shares/${encodeURIComponent(String(shareId))}`, {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json' },
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok || !data || !data.ok) {
      showSharedStatus((data && data.error) || tr('dns_shares_delete_failed'), 'err');
      return;
    }
    showSharedStatus(tr('dns_shares_delete_ok'), 'ok');
    await loadDnsShares();
  } catch {
    showSharedStatus(tr('dns_shares_delete_failed'), 'err');
  }
}

async function extendDnsShare(shareId) {
  if (!shareId) return;
  const raw = window.prompt(tr('dns_shares_extend_prompt'), '7');
  if (raw === null) return;
  const days = Number(raw);
  if (!Number.isFinite(days) || days < 1) {
    showSharedStatus(tr('dns_shares_extend_failed'), 'err');
    return;
  }
  try {
    const res = await fetch(`/api/admin/shares/${encodeURIComponent(String(shareId))}/extend`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ expires_value: Math.floor(days), expires_unit: 'days' }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok || !data || !data.ok) {
      showSharedStatus((data && data.error) || tr('dns_shares_extend_failed'), 'err');
      return;
    }
    showSharedStatus(tr('dns_shares_extend_ok'), 'ok');
    await loadDnsShares();
  } catch {
    showSharedStatus(tr('dns_shares_extend_failed'), 'err');
  }
}

async function loadDnsSettings() {
  if (!els.dnsDuckdnsBaseUrlInput) return;
  showDnsStatus('');
  try {
    const res = await fetch('/api/settings/dns');
    const data = await res.json().catch(() => ({}));
    if (!res.ok || !data || !data.ok) {
      showDnsStatus((data && data.error) || tr('dns_load_failed'), 'err');
      return;
    }
    els.dnsDuckdnsBaseUrlInput.value = String(data.duckdns_base_url || '');
  } catch {
    showDnsStatus(tr('dns_load_failed'), 'err');
  }
}

async function saveDnsSettings() {
  if (!els.dnsDuckdnsBaseUrlInput) return;
  const saveBtn = els.dnsSaveBtn;
  const original = saveBtn ? saveBtn.textContent : tr('dns_save');
  showDnsStatus('');
  try {
    if (saveBtn) {
      saveBtn.disabled = true;
      saveBtn.classList.add('loading');
    }
    const res = await fetch('/api/settings/dns', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        duckdns_base_url: String((els.dnsDuckdnsBaseUrlInput.value || '')).trim(),
      }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok || !data || !data.ok) {
      showDnsStatus((data && data.error) || tr('dns_save_failed'), 'err');
      return;
    }
    els.dnsDuckdnsBaseUrlInput.value = String(data.duckdns_base_url || '');
    showDnsStatus(tr('dns_saved'), 'ok');
  } catch {
    showDnsStatus(tr('dns_save_failed'), 'err');
  } finally {
    if (saveBtn) {
      saveBtn.disabled = false;
      saveBtn.classList.remove('loading');
      saveBtn.textContent = original || tr('dns_save');
    }
  }
}

function showAiPerfStatus(message, kind = 'ok') {
  if (!els.aiPerfStatus) return;
  const msg = String(message || '').trim();
  if (!msg) {
    els.aiPerfStatus.classList.add('hidden');
    els.aiPerfStatus.textContent = '';
    els.aiPerfStatus.classList.remove('ok', 'err');
    return;
  }
  els.aiPerfStatus.textContent = msg;
  els.aiPerfStatus.classList.remove('hidden');
  els.aiPerfStatus.classList.toggle('ok', kind === 'ok');
  els.aiPerfStatus.classList.toggle('err', kind !== 'ok');
}

async function loadAiPerformanceSettings() {
  if (!els.aiIngestThrottleInput || !els.facesThrottleInput) return;
  showAiPerfStatus('');
  try {
    const res = await fetch('/api/settings/ai-performance');
    const data = await res.json().catch(() => ({}));
    if (!res.ok || !data || !data.ok) {
      showAiPerfStatus((data && data.error) || 'Kunne ikke hente AI-ydelse.', 'err');
      return;
    }
    els.aiIngestThrottleInput.value = String(data.ai_ingest_throttle_sec ?? '0.04');
    els.facesThrottleInput.value = String(data.faces_index_throttle_sec ?? '0.06');
  } catch {
    showAiPerfStatus('Kunne ikke hente AI-ydelse.', 'err');
  }
}

async function saveAiPerformanceSettings() {
  if (!els.aiIngestThrottleInput || !els.facesThrottleInput) return;
  const saveBtn = els.aiPerfSaveBtn;
  const original = saveBtn ? saveBtn.textContent : 'Gem ydelse';
  showAiPerfStatus('');
  try {
    if (saveBtn) {
      saveBtn.disabled = true;
      saveBtn.classList.add('loading');
    }
    const aiValue = Number(els.aiIngestThrottleInput.value);
    const facesValue = Number(els.facesThrottleInput.value);
    const res = await fetch('/api/settings/ai-performance', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        ai_ingest_throttle_sec: Number.isFinite(aiValue) ? aiValue : 0,
        faces_index_throttle_sec: Number.isFinite(facesValue) ? facesValue : 0,
      }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok || !data || !data.ok) {
      showAiPerfStatus((data && data.error) || 'Kunne ikke gemme AI-ydelse.', 'err');
      return;
    }
    els.aiIngestThrottleInput.value = String(data.ai_ingest_throttle_sec ?? els.aiIngestThrottleInput.value);
    els.facesThrottleInput.value = String(data.faces_index_throttle_sec ?? els.facesThrottleInput.value);
    showAiPerfStatus('AI-ydelse gemt (gælder med det samme).', 'ok');
  } catch {
    showAiPerfStatus('Kunne ikke gemme AI-ydelse.', 'err');
  } finally {
    if (saveBtn) {
      saveBtn.disabled = false;
      saveBtn.classList.remove('loading');
      saveBtn.textContent = original || 'Gem ydelse';
    }
  }
}

function applyAiPerfPreset(kind) {
  if (!els.aiIngestThrottleInput || !els.facesThrottleInput) return;
  const presets = {
    low: { ai: 0.12, faces: 0.16 },
    normal: { ai: 0.04, faces: 0.06 },
    fast: { ai: 0.00, faces: 0.00 },
  };
  const p = presets[kind] || presets.normal;
  els.aiIngestThrottleInput.value = p.ai.toFixed(2);
  els.facesThrottleInput.value = p.faces.toFixed(2);
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
  if (!els.mapperCreateModalInput) return;
  const parent = String(state.mapperPath || '');
  const path = (els.mapperCreateModalInput.value || '').trim();
  if (!path) {
    showStatus(tr('mapper_create_name_required'), 'err');
    try { els.mapperCreateModalInput.focus(); } catch {}
    return;
  }
  const createBtn = els.mapperCreateModalConfirm;
  const originalLabel = createBtn ? createBtn.textContent : tr('upload_create_folder');
  try {
    if (createBtn) {
      createBtn.disabled = true;
      createBtn.classList.add('loading');
      createBtn.textContent = tr('mapper_create_pending');
    }
    const res = await fetch('/api/settings/upload-folder', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ destination: 'uploads', parent, path }),
    });
    const data = await res.json();
    if (!res.ok || !data || !data.ok) {
      showStatus((data && data.error) || tr('mapper_create_failed'), 'err');
      return;
    }
    els.mapperCreateModalInput.value = '';
    state.mapperFolders = Array.isArray(data.folders) ? data.folders.filter(f => !!f) : [];
    state.mapperPath = parent;
    state.folder = parent || null;
    renderMapperContext(parent);
    await loadPhotos();
    closeMapperCreateModal(false);
    const createdPath = String(data.created || path || '');
    showStatus(`${tr('mapper_created_status')}: ${createdPath}`, 'ok');
  } catch {
    showStatus(tr('mapper_create_error'), 'err');
  } finally {
    if (createBtn) {
      createBtn.classList.remove('loading');
      createBtn.textContent = originalLabel || tr('upload_create_folder');
      createBtn.disabled = false;
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
    showStatus(tr('mapper_select_delete_none'), 'err');
    return;
  }
  const confirmMsg = tr('mapper_delete_confirm').replace('{count}', String(selected.length));
  const ok = confirm(confirmMsg);
  if (!ok) return;
  const deleteBtn = els.mapperDeleteBtn;
  const originalLabel = deleteBtn ? deleteBtn.textContent : 'Slet valgte';
  try {
    if (deleteBtn) {
      deleteBtn.disabled = true;
      deleteBtn.classList.add('loading');
      deleteBtn.textContent = tr('mapper_delete_pending');
    }
    const res = await fetch('/api/settings/upload-folder-delete', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ destination: 'uploads', paths: selected }),
    });
    const data = await res.json();
    if (!res.ok || !data || !data.ok) {
      showStatus((data && data.error) || tr('mapper_delete_failed'), 'err');
      return;
    }
    state.mapperFolders = Array.isArray(data.folders) ? data.folders.filter(f => !!f) : [];
    state.mapperSelectedFolders = new Set();
    setMapperEditMode(false);
    await loadMapperTools(state.mapperPath || '');
    await loadPhotos();
    const deletedCount = Array.isArray(data.deleted) ? data.deleted.length : 0;
    const removedPhotos = Number(data.removed_photos || 0);
    const successMsg = tr('mapper_delete_success')
      .replace('{count}', String(deletedCount))
      .replace('{removed}', String(removedPhotos));
    showStatus(successMsg, 'ok');
  } catch {
    showStatus(tr('mapper_delete_error'), 'err');
  } finally {
    if (deleteBtn) {
      deleteBtn.classList.remove('loading');
      deleteBtn.textContent = originalLabel || 'Slet valgte';
    }
    renderMapperContext(state.mapperPath || '');
  }
}

let _dragDepth = 0;
let _internalImageDrag = false;

document.addEventListener('dragstart', (e) => {
  const target = e.target;
  if (!(target instanceof HTMLElement)) return;
  if (!target.closest('.photo-card') && !target.closest('#viewer')) return;
  _internalImageDrag = true;
  if (target instanceof HTMLImageElement) {
    e.preventDefault();
  }
});

document.addEventListener('dragend', () => {
  _internalImageDrag = false;
  _dragDepth = 0;
  _hideGlobalDropOverlay();
});

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
  if (_internalImageDrag) return;
  if (!(e.dataTransfer && e.dataTransfer.types && e.dataTransfer.types.includes('Files'))) return;
  _dragDepth += 1;
  _showGlobalDropOverlay();
});

window.addEventListener('dragover', (e) => {
  if (_internalImageDrag) return;
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
  if (_internalImageDrag) {
    _internalImageDrag = false;
    _hideGlobalDropOverlay();
    return;
  }
  const hasFiles = !!(e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length);
  if (hasFiles) {
    e.preventDefault();
    const droppedInsideMapperZone = !!(els.mapperDropZone && e.target && els.mapperDropZone.contains(e.target));
    if (state.view !== 'mapper' || state.mapperEditMode) {
      showStatus(tr('upload_mapper_only'), 'err');
    } else if (!droppedInsideMapperZone) {
      const targetSubdir = String(state.mapperPath || '');
      await uploadFiles(e.dataTransfer.files, { destination: 'uploads', subdir: targetSubdir });
      await loadMapperTools(targetSubdir);
      await loadPhotos();
    }
  }
  _internalImageDrag = false;
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
    els.scanBtn.textContent = tr('btn_stop_scan');
  } else {
    els.scanBtn.textContent = tr('btn_scan_library');
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
      showStatus(tr('scan_done_or_stopped'), "ok");
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
        showStatus(tr('scan_stop_failed'), "err");
        return;
      }
      showStatus(tr('scan_stopping'), "ok");
    } catch (_) {
      showStatus(tr('scan_stop_error'), "err");
    }
    return;
  }

  // Start scan
  try {
    const res = await fetch("/api/scan", { method: "POST" });
    const data = await res.json();
    if (!res.ok || !data.ok) {
      showStatus(`${tr('status_error_prefix')} ${data && data.error ? data.error : tr('scan_failed')}`, "err");
      return;
    }
    state.scanning = true;
    updateScanButton();
    showStatus(tr('scan_started_hint'), "ok");
    pollScanStatus();
  } catch (err) {
    showStatus(`${tr('scan_error_prefix')} ${err}`, "err");
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
        showStatus(`${tr('rescan_done_prefix')}: ${r.scanned}, updated: ${r.updated}, missing: ${r.missing}, errors: ${r.errors}.`, "ok");
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
    showStatus(tr('rescan_starting'), "ok");
    const res = await fetch("/api/rescan", { method: "POST" });
    const data = await res.json();
    if (!res.ok || !data.ok) {
      showStatus(`${tr('status_error_prefix')} ${data && data.error ? data.error : tr('rescan_failed')}`, "err");
      els.rescanBtn.disabled = false;
      return;
    }
    pollRescanStatus();
  } catch (e) {
    showStatus(tr('rescan_error'), "err");
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
        showStatus(`${tr('rethumb_done_prefix')}: ${r.processed}, errors: ${r.errors}.`, "ok");
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
    showStatus(tr('rethumb_starting'), "ok");
    const res = await fetch("/api/rethumb", { method: "POST" });
    const data = await res.json();
    if (!res.ok || !data.ok) {
      showStatus(`${tr('status_error_prefix')} ${data && data.error ? data.error : tr('rethumb_failed')}`, "err");
      if (els.rethumbBtn) els.rethumbBtn.disabled = false;
      return;
    }
    pollRethumbStatus();
  } catch (e) {
    showStatus(tr('rethumb_error'), "err");
    if (els.rethumbBtn) els.rethumbBtn.disabled = false;
  }
}

// Clear index (DB + thumbnails, not originals)
async function clearIndex() {
  const ok = confirm(tr('clear_confirm'));
  if (!ok) return;
  try {
    if (els.clearIndexBtn) els.clearIndexBtn.disabled = true;
    showStatus(tr('clear_starting'), "ok");
    const res = await fetch("/api/clear", { method: "POST" });
    const data = await res.json();
    if (!res.ok || !data.ok) {
      showStatus(`${tr('clear_failed')} ${data && data.error ? data.error : tr('clear_unknown')}`, "err");
      if (els.clearIndexBtn) els.clearIndexBtn.disabled = false;
      return;
    }
    const r = data.removed || {};
    showStatus(`${tr('clear_done_prefix')}: ${r.photos || 0} photos, ${r.faces || 0} faces, ${r.people || 0} people, ${r.thumbs || 0} thumbs.`, "ok");
    // Tøm UI og hent frisk
    state.items = [];
    await loadPhotos();
  } catch (e) {
    showStatus(tr('clear_error'), "err");
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
  updateMobileBottomNavActive(nextView);
  // Toggle body class to drive CSS for Settings view
  document.body.classList.toggle("view-settings", nextView === "settings");
  document.body.classList.toggle("view-timeline", nextView === "timeline");
  document.body.classList.toggle("view-mapper", nextView === "mapper");
  if (nextView !== 'mapper') closeMapperHeaderMenu();
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
    if (nextView === 'mapper') await loadMapperTools(String(state.mapperPath || ''));
    await loadPhotos();
  }
}

function updateMobileBottomNavActive(view) {
  document.querySelectorAll('.mobile-nav-item[data-view]').forEach((btn) => {
    btn.classList.toggle('active', btn.dataset.view === view);
  });
}

function applyUiLanguage() {
  try { document.documentElement.lang = state.uiLanguage || 'da'; } catch {}
  if (els.search) els.search.placeholder = tr('search_placeholder');
  if (els.mapperSearchInput) els.mapperSearchInput.placeholder = tr('search_placeholder');

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
    dns: tr('tab_dns'),
    shared: tr('tab_shared'),
    logs: tr('tab_logs'),
    users: tr('tab_users'),
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
  if (els.aiPanelTitle) els.aiPanelTitle.textContent = tr('ai_panel_title');
  if (els.aiEmbedTitle) els.aiEmbedTitle.textContent = tr('ai_embed_title');
  if (els.aiEmbedDesc) els.aiEmbedDesc.textContent = tr('ai_embed_desc');
  if (els.aiDescTitle) els.aiDescTitle.textContent = tr('ai_desc_title');
  if (els.aiDescDesc) els.aiDescDesc.textContent = tr('ai_desc_desc');
  if (els.aiFacesTitle) els.aiFacesTitle.textContent = tr('ai_faces_title');
  if (els.aiFacesDesc) els.aiFacesDesc.textContent = tr('ai_faces_desc');
  if (els.dnsPanelTitle) els.dnsPanelTitle.textContent = tr('dns_title');
  if (els.dnsPanelDesc) els.dnsPanelDesc.textContent = tr('dns_desc');
  if (els.dnsDuckdnsBaseUrlLabel) els.dnsDuckdnsBaseUrlLabel.textContent = tr('dns_duckdns_base_url');
  if (els.dnsDuckdnsBaseUrlInput) els.dnsDuckdnsBaseUrlInput.placeholder = tr('dns_duckdns_placeholder');
  if (els.dnsSaveBtn) els.dnsSaveBtn.textContent = tr('dns_save');
  if (els.sharedLinksTitle) els.sharedLinksTitle.textContent = tr('dns_shares_title');
  if (els.sharedLinksDesc) els.sharedLinksDesc.textContent = tr('dns_shares_desc');
  if (els.sharedLinksList && Array.isArray(state.sharedLinks) && state.sharedLinks.length) renderDnsSharesList();

  if (els.scanBtn) els.scanBtn.textContent = tr('btn_scan_library');
  if (els.rescanBtn) els.rescanBtn.textContent = tr('btn_rescan_metadata');
  if (els.rethumbBtn) els.rethumbBtn.textContent = tr('btn_rebuild_thumbs');
  if (els.clearIndexBtn) els.clearIndexBtn.textContent = tr('btn_reset_index');
  updateAiToggleButton();
  updateAiDescribeToggleButton();
  updateFacesToggleButton();

  const logsLabel = document.querySelector('#logsPanel strong');
  if (logsLabel) logsLabel.textContent = tr('logs_label');
  if (els.logsStart) els.logsStart.textContent = state.logsRunning ? tr('btn_stop') : tr('btn_start');
  if (els.mainLogsClear) els.mainLogsClear.textContent = tr('btn_clear');

  const profileModalTitle = document.querySelector('#profileModal h3');
  if (profileModalTitle) profileModalTitle.textContent = tr('profile_title');
  if (els.profileModalClose) els.profileModalClose.textContent = tr('profile_close');
  const twofaModalTitle = document.getElementById('twofaModalTitle');
  if (twofaModalTitle) twofaModalTitle.textContent = tr('tab_twofa');
  if (els.twofaModalClose) els.twofaModalClose.textContent = tr('profile_close');

  const scanModalTitle = document.getElementById('scanModalTitle');
  const scanModalText = document.getElementById('scanModalText');
  if (scanModalTitle) scanModalTitle.textContent = tr('scan_modal_title');
  if (scanModalText) scanModalText.textContent = tr('scan_modal_text');
  if (els.scanModalClose) els.scanModalClose.textContent = tr('scan_modal_close');
  if (els.scanModalCancel) els.scanModalCancel.textContent = tr('scan_modal_cancel');
  if (els.scanModalStart) els.scanModalStart.textContent = tr('scan_modal_start');
  if (els.mapperCreateModalTitle) els.mapperCreateModalTitle.textContent = tr('mapper_create_modal_title');
  if (els.mapperCreateModalClose) els.mapperCreateModalClose.textContent = tr('scan_modal_close');
  if (els.mapperCreateModalCancel) els.mapperCreateModalCancel.textContent = tr('scan_modal_cancel');
  if (els.mapperCreateModalConfirm) els.mapperCreateModalConfirm.textContent = tr('upload_create_folder');
  if (els.mapperCreateModalInput) els.mapperCreateModalInput.placeholder = tr('upload_new_folder_placeholder');
  if (els.mapperShareModalTitle) els.mapperShareModalTitle.textContent = tr('mapper_share_title');
  if (els.mapperShareModalClose) els.mapperShareModalClose.textContent = tr('scan_modal_close');
  if (els.mapperShareModalCancel) els.mapperShareModalCancel.textContent = tr('scan_modal_cancel');
  if (els.mapperShareModalConfirm) els.mapperShareModalConfirm.textContent = tr('mapper_share_generate');
  if (els.mapperShareNameLabel) els.mapperShareNameLabel.textContent = tr('mapper_share_name_label');
  if (els.mapperShareNameInput) els.mapperShareNameInput.placeholder = tr('mapper_share_name_placeholder');
  if (els.mapperShareFolderLabel) els.mapperShareFolderLabel.textContent = tr('mapper_share_folder_label');
  if (els.mapperShareExpireLabel) els.mapperShareExpireLabel.textContent = tr('mapper_share_expire_label');
  if (els.mapperShareExpireUnitLabel) els.mapperShareExpireUnitLabel.textContent = tr('mapper_share_expire_unit_label');
  if (els.mapperSharePermissionLabel) els.mapperSharePermissionLabel.textContent = tr('mapper_share_permission_label');
  if (els.mapperShareDuckdnsToggleText) els.mapperShareDuckdnsToggleText.textContent = tr('mapper_share_duckdns_toggle');
  if (els.mapperSharePasswordToggleText) els.mapperSharePasswordToggleText.textContent = tr('mapper_share_password_toggle');
  if (els.mapperShareRequireNameToggleText) els.mapperShareRequireNameToggleText.textContent = tr('mapper_share_require_name_toggle');
  if (els.mapperSharePasswordLabel) els.mapperSharePasswordLabel.textContent = tr('mapper_share_password_label');
  if (els.mapperSharePasswordInput) els.mapperSharePasswordInput.placeholder = tr('mapper_share_password_placeholder');
  if (els.mapperShareResultLabel) els.mapperShareResultLabel.textContent = tr('mapper_share_result_label');
  if (els.mapperShareCopyBtn) els.mapperShareCopyBtn.textContent = tr('mapper_share_copy');
  if (els.mapperShareExpireUnit) {
    const dayOpt = els.mapperShareExpireUnit.querySelector('option[value="days"]');
    const hourOpt = els.mapperShareExpireUnit.querySelector('option[value="hours"]');
    if (dayOpt) dayOpt.textContent = tr('mapper_share_expire_days');
    if (hourOpt) hourOpt.textContent = tr('mapper_share_expire_hours');
  }
  if (els.mapperSharePermission) {
    const viewOpt = els.mapperSharePermission.querySelector('option[value="view"]');
    const uploadOpt = els.mapperSharePermission.querySelector('option[value="upload"]');
    const manageOpt = els.mapperSharePermission.querySelector('option[value="manage"]');
    if (viewOpt) viewOpt.textContent = tr('mapper_share_perm_view');
    if (uploadOpt) uploadOpt.textContent = tr('mapper_share_perm_upload');
    if (manageOpt) manageOpt.textContent = tr('mapper_share_perm_manage');
  }
  if (els.aiScopeModalText) els.aiScopeModalText.textContent = tr('ai_scope_text');
  if (els.aiScopeModalCancel) els.aiScopeModalCancel.textContent = tr('ai_scope_cancel');
  if (els.aiScopeModalClose) els.aiScopeModalClose.textContent = tr('scan_modal_close');
  if (els.aiScopeModalNew) els.aiScopeModalNew.textContent = tr('ai_scope_new');
  if (els.aiScopeModalAll) els.aiScopeModalAll.textContent = tr('ai_scope_all');
  if (els.aiScopeModalTitle) {
    const feature = state.aiScopePendingFeature;
    if (feature === 'faces') els.aiScopeModalTitle.textContent = tr('ai_scope_title_faces');
    else if (feature === 'describe') els.aiScopeModalTitle.textContent = tr('ai_scope_title_desc');
    else els.aiScopeModalTitle.textContent = tr('ai_scope_title_ai');
  }

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

function openTwofaModal() {
  if (!els.twofaModal) return;
  els.twofaModal.classList.remove('hidden');
}

function closeTwofaModal() {
  if (!els.twofaModal) return;
  els.twofaModal.classList.add('hidden');
}

function openMapperCreateModal() {
  if (!els.mapperCreateModal) return;
  if (els.mapperCreateModalTitle) els.mapperCreateModalTitle.textContent = tr('mapper_create_modal_title');
  if (els.mapperCreateModalClose) els.mapperCreateModalClose.textContent = tr('scan_modal_close');
  if (els.mapperCreateModalCancel) els.mapperCreateModalCancel.textContent = tr('scan_modal_cancel');
  if (els.mapperCreateModalConfirm) {
    els.mapperCreateModalConfirm.disabled = false;
    els.mapperCreateModalConfirm.classList.remove('loading');
    els.mapperCreateModalConfirm.textContent = tr('upload_create_folder');
  }
  if (els.mapperCreateModalInput) {
    els.mapperCreateModalInput.placeholder = tr('upload_new_folder_placeholder');
  }
  els.mapperCreateModal.classList.remove('hidden');
  if (els.mapperCreateModalInput) {
    requestAnimationFrame(() => {
      try {
        els.mapperCreateModalInput.focus();
        const len = String(els.mapperCreateModalInput.value || '').length;
        els.mapperCreateModalInput.setSelectionRange(len, len);
      } catch {}
    });
  }
}

function closeMapperCreateModal(clearInput = true) {
  if (!els.mapperCreateModal) return;
  els.mapperCreateModal.classList.add('hidden');
  if (clearInput && els.mapperCreateModalInput) {
    els.mapperCreateModalInput.value = '';
  }
}

function _getSelectedMapperFolders() {
  return Array.from(state.mapperSelectedFolders || [])
    .map((v) => String(v || '').trim())
    .filter((v) => !!v);
}

function _defaultMapperShareName(folders) {
  const list = Array.isArray(folders) ? folders.filter(Boolean) : [];
  if (!list.length) return '';
  if (list.length === 1) return `uploads/${list[0]}`;
  return `${list.length} mapper`;
}

function _selectedMapperFoldersText(folders) {
  const list = Array.isArray(folders) ? folders.filter(Boolean) : [];
  if (!list.length) return '';
  const labels = list.map((f) => `uploads/${f}`);
  if (labels.length <= 3) return labels.join(', ');
  return `${labels.slice(0, 3).join(', ')} (+${labels.length - 3})`;
}

function _syncMapperSharePasswordVisibility() {
  const enabled = !!(els.mapperSharePasswordToggle && els.mapperSharePasswordToggle.checked);
  if (els.mapperSharePasswordWrap) els.mapperSharePasswordWrap.classList.toggle('hidden', !enabled);
  if (!enabled && els.mapperSharePasswordInput) els.mapperSharePasswordInput.value = '';
}

async function refreshShareDuckdnsConfig() {
  try {
    const res = await fetch('/api/settings/dns/effective');
    const data = await res.json().catch(() => ({}));
    if (!res.ok || !data || !data.ok) {
      state.shareDuckdnsConfigured = false;
      state.shareDuckdnsEffectiveBaseUrl = '';
      return;
    }
    state.shareDuckdnsConfigured = !!data.duckdns_configured;
    state.shareDuckdnsEffectiveBaseUrl = String(data.effective_duckdns_base_url || '');
  } catch {
    state.shareDuckdnsConfigured = false;
    state.shareDuckdnsEffectiveBaseUrl = '';
  }
}

async function openMapperShareModal() {
  if (!els.mapperShareModal) return;
  const folders = _getSelectedMapperFolders();
  if (!folders.length) {
    showStatus(tr('mapper_share_select_one'), 'err');
    return;
  }
  await refreshShareDuckdnsConfig();
  applyUiLanguage();
  if (els.mapperShareNameInput) els.mapperShareNameInput.value = _defaultMapperShareName(folders);
  if (els.mapperShareFolderInput) els.mapperShareFolderInput.value = _selectedMapperFoldersText(folders);
  if (els.mapperShareExpireValue) els.mapperShareExpireValue.value = '7';
  if (els.mapperShareExpireUnit) els.mapperShareExpireUnit.value = 'days';
  if (els.mapperSharePermission) els.mapperSharePermission.value = 'view';
  if (els.mapperShareDuckdnsToggle) {
    const enabled = !!state.shareDuckdnsConfigured;
    els.mapperShareDuckdnsToggle.checked = enabled;
    els.mapperShareDuckdnsToggle.disabled = !enabled;
    els.mapperShareDuckdnsToggle.title = enabled ? '' : tr('mapper_share_duckdns_not_configured');
  }
  if (els.mapperSharePasswordToggle) els.mapperSharePasswordToggle.checked = false;
  if (els.mapperShareRequireNameToggle) els.mapperShareRequireNameToggle.checked = false;
  _syncMapperSharePasswordVisibility();
  if (els.mapperShareResultWrap) els.mapperShareResultWrap.classList.add('hidden');
  if (els.mapperShareResultInput) els.mapperShareResultInput.value = '';
  if (els.mapperShareModalConfirm) {
    els.mapperShareModalConfirm.disabled = false;
    els.mapperShareModalConfirm.classList.remove('loading');
    els.mapperShareModalConfirm.textContent = tr('mapper_share_generate');
  }
  els.mapperShareModal.classList.remove('hidden');
}

function closeMapperShareModal(clearOutput = true) {
  if (!els.mapperShareModal) return;
  els.mapperShareModal.classList.add('hidden');
  if (clearOutput) {
    if (els.mapperShareResultWrap) els.mapperShareResultWrap.classList.add('hidden');
    if (els.mapperShareResultInput) els.mapperShareResultInput.value = '';
  }
}

async function createMapperShareLink() {
  const folders = _getSelectedMapperFolders();
  if (!folders.length) {
    showStatus(tr('mapper_share_select_one'), 'err');
    return;
  }
  const confirmBtn = els.mapperShareModalConfirm;
  const original = confirmBtn ? confirmBtn.textContent : tr('mapper_share_generate');
  const useDuckdns = !!(els.mapperShareDuckdnsToggle && els.mapperShareDuckdnsToggle.checked);
  const passwordEnabled = !!(els.mapperSharePasswordToggle && els.mapperSharePasswordToggle.checked);
  const requireVisitorName = !!(els.mapperShareRequireNameToggle && els.mapperShareRequireNameToggle.checked);
  const password = String((els.mapperSharePasswordInput && els.mapperSharePasswordInput.value) || '');
  if (passwordEnabled && password.length < 4) {
    showStatus(tr('mapper_share_password_placeholder'), 'err');
    return;
  }
  try {
    if (confirmBtn) {
      confirmBtn.disabled = true;
      confirmBtn.classList.add('loading');
      confirmBtn.textContent = tr('mapper_share_generating');
    }
    const expiresValue = Number((els.mapperShareExpireValue && els.mapperShareExpireValue.value) || 7) || 7;
    const expiresUnit = String((els.mapperShareExpireUnit && els.mapperShareExpireUnit.value) || 'days');
    const permission = String((els.mapperSharePermission && els.mapperSharePermission.value) || 'view');
    const shareNameRaw = String((els.mapperShareNameInput && els.mapperShareNameInput.value) || '').trim();
    const shareName = shareNameRaw || _defaultMapperShareName(folders);
    const res = await fetch('/api/shares', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        folder_paths: folders,
        share_name: shareName,
        permission,
        expires_value: expiresValue,
        expires_unit: expiresUnit,
        use_duckdns: useDuckdns,
        require_visitor_name: requireVisitorName,
        password_enabled: passwordEnabled,
        password,
      }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok || !data || !data.ok) {
      showStatus((data && data.error) || tr('mapper_share_create_failed'), 'err');
      return;
    }
    if (els.mapperShareResultInput) els.mapperShareResultInput.value = String(data.link || '');
    if (els.mapperShareResultWrap) els.mapperShareResultWrap.classList.remove('hidden');
    showStatus(tr('mapper_share_created'), 'ok');
  } catch {
    showStatus(tr('mapper_share_create_failed'), 'err');
  } finally {
    if (confirmBtn) {
      confirmBtn.classList.remove('loading');
      confirmBtn.disabled = false;
      confirmBtn.textContent = original || tr('mapper_share_generate');
    }
  }
}

async function copyMapperShareLink() {
  const link = String((els.mapperShareResultInput && els.mapperShareResultInput.value) || '').trim();
  if (!link) return;
  try {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      await navigator.clipboard.writeText(link);
    } else {
      if (els.mapperShareResultInput) {
        els.mapperShareResultInput.focus();
        els.mapperShareResultInput.select();
      }
      document.execCommand('copy');
    }
    showStatus(tr('mapper_share_copy_ok'), 'ok');
  } catch {
    showStatus(tr('mapper_share_copy_fail'), 'err');
  }
}

function openScanModal() {
  if (!els.scanModal) return;
  els.scanModal.classList.remove('hidden');
}

function closeScanModal() {
  if (!els.scanModal) return;
  els.scanModal.classList.add('hidden');
}

function openAiScopeModal(feature) {
  state.aiScopePendingFeature = feature === 'faces' ? 'faces' : (feature === 'describe' ? 'describe' : 'ai');
  if (els.aiScopeModalTitle) {
    if (state.aiScopePendingFeature === 'faces') els.aiScopeModalTitle.textContent = tr('ai_scope_title_faces');
    else if (state.aiScopePendingFeature === 'describe') els.aiScopeModalTitle.textContent = tr('ai_scope_title_desc');
    else els.aiScopeModalTitle.textContent = tr('ai_scope_title_ai');
  }
  if (els.aiScopeModalText) els.aiScopeModalText.textContent = tr('ai_scope_text');
  if (els.aiScopeModalNew) els.aiScopeModalNew.textContent = tr('ai_scope_new');
  if (els.aiScopeModalAll) els.aiScopeModalAll.textContent = tr('ai_scope_all');
  if (els.aiScopeModalCancel) els.aiScopeModalCancel.textContent = tr('ai_scope_cancel');
  if (els.aiScopeModalClose) els.aiScopeModalClose.textContent = tr('scan_modal_close');
  if (els.aiScopeModal) els.aiScopeModal.classList.remove('hidden');
}

function closeAiScopeModal() {
  if (els.aiScopeModal) els.aiScopeModal.classList.add('hidden');
  state.aiScopePendingFeature = null;
  updateAiToggleButton();
  updateAiDescribeToggleButton();
  updateFacesToggleButton();
}

function openMapperHeaderMenu() {
  if (!els.mapperHeaderMenu) return;
  els.mapperHeaderMenu.classList.add('open');
}

function closeMapperHeaderMenu() {
  if (!els.mapperHeaderMenu) return;
  els.mapperHeaderMenu.classList.remove('open');
}

function toggleMapperHeaderMenu() {
  if (!els.mapperHeaderMenu) return;
  if (els.mapperHeaderMenu.classList.contains('open')) closeMapperHeaderMenu();
  else openMapperHeaderMenu();
}

function openMapperUploadPicker() {
  if (!els.mapperUploadInput) return;
  els.mapperUploadInput.value = '';
  try {
    if (typeof els.mapperUploadInput.showPicker === 'function') {
      els.mapperUploadInput.showPicker();
      return;
    }
    els.mapperUploadInput.click();
  } catch {
    showStatus(tr('file_picker_open_failed'), 'err');
  }
}

function _syncSearchInputs(value, source = null) {
  const v = String(value || '');
  if (els.search && source !== 'top') els.search.value = v;
  if (els.mapperSearchInput && source !== 'mapper') els.mapperSearchInput.value = v;
}

function expandSearchField(focusInput = true) {
  if (!els.searchShell) return;
  els.searchShell.classList.add('expanded');
  if (focusInput && els.search) {
    try {
      els.search.focus();
      const len = String(els.search.value || '').length;
      els.search.setSelectionRange(len, len);
    } catch {}
  }
}

function collapseSearchField() {
  if (!els.searchShell) return;
  els.searchShell.classList.remove('expanded');
}

// Events
if (els.searchToggleBtn) {
  els.searchToggleBtn.addEventListener('click', (e) => {
    e.preventDefault();
    const expanded = !!(els.searchShell && els.searchShell.classList.contains('expanded'));
    if (expanded) {
      if (els.search) els.search.focus();
      return;
    }
    expandSearchField(true);
  });
}

if (els.search) {
  els.search.addEventListener('focus', () => expandSearchField(false));
  els.search.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      collapseSearchField();
      try { els.search.blur(); } catch {}
    }
  });
}

document.addEventListener('pointerdown', (e) => {
  const target = e.target;
  if (!(target instanceof Node)) return;
  if (els.searchShell && els.searchShell.contains(target)) return;
  if (els.mapperSearchShell && els.mapperSearchShell.contains(target)) return;
  if (els.mapperHeaderActions && els.mapperHeaderActions.contains(target)) return;
  collapseSearchField();
  if (els.mapperSearchShell) els.mapperSearchShell.classList.remove('expanded');
  closeMapperHeaderMenu();
});

if (els.mapperSearchToggleBtn) {
  els.mapperSearchToggleBtn.addEventListener('click', (e) => {
    e.preventDefault();
    if (!els.mapperSearchShell) return;
    const expanded = els.mapperSearchShell.classList.contains('expanded');
    if (!expanded) {
      els.mapperSearchShell.classList.add('expanded');
      if (els.mapperSearchInput) {
        try {
          els.mapperSearchInput.focus();
          const len = String(els.mapperSearchInput.value || '').length;
          els.mapperSearchInput.setSelectionRange(len, len);
        } catch {}
      }
      return;
    }
    if (els.mapperSearchInput) els.mapperSearchInput.focus();
  });
}
if (els.mapperSearchInput) {
  els.mapperSearchInput.addEventListener('focus', () => {
    if (els.mapperSearchShell) els.mapperSearchShell.classList.add('expanded');
  });
  els.mapperSearchInput.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      if (els.mapperSearchShell) els.mapperSearchShell.classList.remove('expanded');
      try { els.mapperSearchInput.blur(); } catch {}
    }
  });
  els.mapperSearchInput.addEventListener('input', () => {
    state.q = els.mapperSearchInput.value.trim();
    _syncSearchInputs(els.mapperSearchInput.value, 'mapper');
    loadPhotos();
  });
}
if (els.mapperEditBtn) {
  els.mapperEditBtn.addEventListener('click', (e) => {
    e.preventDefault();
    toggleMapperHeaderMenu();
  });
}
if (els.mapperHeaderEditAction) {
  els.mapperHeaderEditAction.addEventListener('click', async () => {
    const selectedCount = state.mapperSelectedFolders ? state.mapperSelectedFolders.size : 0;
    if (!state.mapperEditMode) {
      setMapperEditMode(true);
      closeMapperHeaderMenu();
      return;
    }
    if (selectedCount > 0) {
      await deleteSelectedMapperFolders();
      closeMapperHeaderMenu();
      return;
    }
    setMapperEditMode(false);
    closeMapperHeaderMenu();
  });
}
if (els.mapperHeaderCreateAction) {
  els.mapperHeaderCreateAction.addEventListener('click', () => {
    openMapperCreateModal();
    closeMapperHeaderMenu();
  });
}
if (els.mapperHeaderUploadAction) {
  els.mapperHeaderUploadAction.addEventListener('click', () => {
    closeMapperHeaderMenu();
    openMapperUploadPicker();
  });
}
if (els.mapperHeaderShareAction) {
  els.mapperHeaderShareAction.addEventListener('click', async () => {
    await openMapperShareModal();
    closeMapperHeaderMenu();
  });
}
if (els.search) {
  _syncSearchInputs(els.search.value || '', 'top');
}
els.search.addEventListener("input", () => {
  state.q = els.search.value.trim();
  _syncSearchInputs(els.search.value, 'top');
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
async function startAiIngest(scope = 'all') {
  try {
    showStatus(tr('ai_starting'), "ok");
    const qs = (scope === 'new') ? '?scope=new' : '?scope=all';
    const res = await fetch(`/api/ai/ingest${qs}`, { method: 'POST' });
    const data = await res.json();
    if (!res.ok || !data.ok) {
      showStatus(tr('ai_start_failed'), "err");
      return;
    }
    if (scope === 'new') {
      showStatus(tr('ai_enabled_new_uploads'), 'ok');
    } else {
      showStatus(tr('ai_started_bg'), "ok");
    }
    state.aiAutoEnabled = true;
    state.aiRunning = !!(data && data.running);
    updateAiToggleButton();
    pollAiStatus();
  } catch { showStatus(tr('ai_start_error'), "err"); }
}

async function stopAiIngest() {
  try {
    const res = await fetch('/api/ai/stop', { method: 'POST' });
    const data = await res.json().catch(() => ({}));
    if (!res.ok || (data && data.ok === false)) {
      showStatus(tr('ai_stop_failed'), 'err');
      return;
    }
    showStatus(tr('ai_stopped'), 'ok');
    state.aiRunning = false;
    state.aiAutoEnabled = false;
    updateAiToggleButton();
    pollAiStatus();
  } catch {
    showStatus(tr('ai_stop_error'), 'err');
  }
}

async function startAiDescribeIngest(scope = 'all') {
  try {
    showStatus(tr('ai_desc_starting'), 'ok');
    const qs = (scope === 'new') ? '?scope=new' : '?scope=all';
    const res = await fetch(`/api/ai/describe/ingest${qs}`, { method: 'POST' });
    const data = await res.json();
    if (!res.ok || !data.ok) {
      showStatus(tr('ai_desc_start_failed'), 'err');
      return;
    }
    if (scope === 'new') {
      showStatus(tr('ai_desc_enabled_new_uploads'), 'ok');
    } else {
      showStatus(tr('ai_desc_started_bg'), 'ok');
    }
    state.aiDescribeAutoEnabled = true;
    state.aiDescribeRunning = !!(data && data.running);
    updateAiDescribeToggleButton();
    pollAiDescribeStatus();
  } catch {
    showStatus(tr('ai_desc_start_error'), 'err');
  }
}

async function stopAiDescribeIngest() {
  try {
    const res = await fetch('/api/ai/describe/stop', { method: 'POST' });
    const data = await res.json().catch(() => ({}));
    if (!res.ok || (data && data.ok === false)) {
      showStatus(tr('ai_desc_stop_failed'), 'err');
      return;
    }
    showStatus(tr('ai_desc_stopped'), 'ok');
    state.aiDescribeRunning = false;
    state.aiDescribeAutoEnabled = false;
    updateAiDescribeToggleButton();
    pollAiDescribeStatus();
  } catch {
    showStatus(tr('ai_desc_stop_error'), 'err');
  }
}

els.aiIngestToggle && els.aiIngestToggle.addEventListener('change', async () => {
  if (els.aiIngestToggle.checked) {
    openAiScopeModal('ai');
    return;
  }
  await stopAiIngest();
});

els.aiDescribeToggle && els.aiDescribeToggle.addEventListener('change', async () => {
  if (els.aiDescribeToggle.checked) {
    openAiScopeModal('describe');
    return;
  }
  await stopAiDescribeIngest();
});

// Faces indexing controls
async function pollFacesStatus() {
  try {
    const r = await fetch('/api/faces/status');
    const s = await r.json();
    state.facesRunning = !!(s && s.ok && s.running);
    state.facesAutoEnabled = !!(s && s.ok && s.auto_index);
    updateFacesToggleButton();
    if (els.facesStatus) {
      const run = s && s.running ? tr('status_running') : tr('status_stopped');
      const source = (!s.running && s.last) ? s.last : s;
      const processed = Number(source && source.processed) || 0;
      const total = Number(source && source.total) || 0;
      els.facesStatus.textContent = `${tr('status_faces_prefix')}: ${run} · ${tr('status_processed_label')} ${processed}/${total}`;
    }
    if (s && s.running) {
      // While faces are indexing, refresh People view incrementally when progress increases
      try {
        const source = (!s.running && s.last) ? s.last : s;
        const processed = Number(source && source.processed) || 0;
        const now = Date.now();
        if (!Number.isNaN(processed)) {
          const lastProc = Number(state._facesProcessed || 0);
          const lastAt = Number(state._facesAutoRefreshAt || 0);
          if (processed > lastProc && (now - lastAt) > 1200) {
            state._facesProcessed = processed;
            state._facesAutoRefreshAt = now;
            if (state.view === 'personer') {
              if (state.personView && state.personView.mode === 'photos' && state.personView.personId) {
                // Refresh current person's photos if viewing a person
                loadPersonPhotos(state.personView.personId, state.personView.personName);
              } else {
                // Refresh the People list so new thumbs appear without manual reload
                loadPeople();
              }
            }
          }
        }
      } catch {}
      setTimeout(pollFacesStatus, 1500);
    } else {
      // refresh lists when done
      if (state.view === 'personer') loadPeople();
      else loadPhotos();
    }
  } catch {
    state.facesRunning = false;
    state.facesAutoEnabled = false;
    updateFacesToggleButton();
    if (els.facesStatus) els.facesStatus.textContent = `${tr('status_faces_prefix')}: ${tr('status_dash')}`;
  }
}

async function startFacesIndex(scope = 'all') {
  try {
    showStatus(tr('faces_starting'), 'ok');
    const url = (scope === 'new') ? '/api/faces/index?scope=new' : '/api/faces/index?scope=all';
    const res = await fetch(url, { method: 'POST' });
    const data = await res.json();
    if (!res.ok || !data.ok) {
      showStatus(data && data.error ? data.error : tr('faces_start_failed'), 'err');
      return;
    }
    state.facesAutoEnabled = true;
    state.facesRunning = !!(data && data.running);
    updateFacesToggleButton();
    if (scope === 'new') {
      showStatus(tr('faces_enabled_new_uploads'), 'ok');
    } else {
      showStatus(tr('faces_started_bg'), 'ok');
    }
    pollFacesStatus();
  } catch (e) {
    showStatus(tr('faces_start_error'), 'err');
  }
}

async function stopFacesIndex() {
  try {
    const res = await fetch('/api/faces/stop', { method: 'POST' });
    const data = await res.json().catch(() => ({}));
    if (!res.ok || !data || data.ok === false) {
      showStatus(tr('faces_stop_failed'), 'err');
      return;
    }
    showStatus(tr('faces_stopped'), 'ok');
    state.facesAutoEnabled = false;
    state.facesRunning = false;
    updateFacesToggleButton();
    pollFacesStatus();
  } catch {
    showStatus(tr('faces_stop_error'), 'err');
  }
}

if (els.facesToggle) {
  els.facesToggle.addEventListener('change', async () => {
    if (els.facesToggle.checked) {
      openAiScopeModal('faces');
      return;
    }
    await stopFacesIndex();
  });
}

async function pollAiStatus() {
  try {
    const r = await fetch('/api/ai/status');
    const s = await r.json();
    state.aiRunning = !!(s && s.ok && s.running);
    state.aiAutoEnabled = !!(s && s.ok && s.auto_ingest);
    updateAiToggleButton();
    if (els.aiStatus) {
      if (!s || !s.ok) { els.aiStatus.textContent = `${tr('status_ai_prefix')}: ${tr('status_dash')}`; }
      else {
        const run = s.running ? tr('status_running') : tr('status_stopped');
        const source = (!s.running && s.last) ? s.last : s;
        const embedded = Number(source && source.embedded) || 0;
        const total = Number(source && source.total) || 0;
        const failed = Number(source && source.failed) || 0;
        els.aiStatus.textContent = `${tr('status_ai_prefix')}: ${run} · ${tr('status_embedded_label')} ${embedded}/${total} · ${tr('status_errors_label')} ${failed}`;
      }
    }
  } catch {
    state.aiRunning = false;
    state.aiAutoEnabled = false;
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

async function pollAiDescribeStatus() {
  try {
    const r = await fetch('/api/ai/describe/status');
    const s = await r.json();
    state.aiDescribeRunning = !!(s && s.ok && s.running);
    state.aiDescribeAutoEnabled = !!(s && s.ok && s.auto_ingest);
    updateAiDescribeToggleButton();
    if (els.aiDescribeStatus) {
      if (!s || !s.ok) {
        els.aiDescribeStatus.textContent = `${tr('status_ai_desc_prefix')}: ${tr('status_dash')}`;
      } else {
        const run = s.running ? tr('status_running') : tr('status_stopped');
        const source = (!s.running && s.last) ? s.last : s;
        const described = Number(source && source.described) || 0;
        const total = Number(source && source.total) || 0;
        const failed = Number(source && source.failed) || 0;
        els.aiDescribeStatus.textContent = `${tr('status_ai_desc_prefix')}: ${run} · ${tr('status_described_label')} ${described}/${total} · ${tr('status_errors_label')} ${failed}`;
      }
    }
  } catch {
    state.aiDescribeRunning = false;
    state.aiDescribeAutoEnabled = false;
    updateAiDescribeToggleButton();
    if (els.aiDescribeStatus) els.aiDescribeStatus.textContent = `${tr('status_ai_desc_prefix')}: ${tr('status_dash')}`;
  }
  try {
    const r2 = await fetch('/api/ai/describe/status');
    const s2 = await r2.json();
    if (s2 && s2.running) setTimeout(pollAiDescribeStatus, 1200);
  } catch {}
}

// Start med at vise status hvis noget kører allerede
pollAiStatus();
pollAiDescribeStatus();
pollFacesStatus();
updateScanButton();
els.toggleRawBtn.addEventListener("click", () => {
  const hidden = els.rawMeta.classList.toggle("hidden");
  els.toggleRawBtn.textContent = hidden ? tr('raw_meta_show') : tr('raw_meta_hide');
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
      if (!res.ok || !data.ok) { showStatus(data.error || tr('date_update_failed'), 'err'); return; }
      const item = data.item;
      const idx = state.items.findIndex(i => i.id === item.id);
      if (idx >= 0) state.items[idx] = item;
      showStatus(tr('date_updated'), 'ok');
      renderGrid();
      setDetail(item);
      if (els.dateEditWrap) { els.dateEditWrap.classList.add('hidden'); els.dateEditWrap.classList.remove('floating'); els.dateEditWrap.style.left=''; els.dateEditWrap.style.top=''; }
      try {
        const row = els.editDateBtn.closest('.detail-row');
        if (row) row.classList.remove('popover-open');
      } catch {}
    } catch (e) {
      showStatus(tr('update_error'), 'err');
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
      if (!res.ok || !data.ok) { showStatus(data.error || tr('gps_update_failed'), 'err'); return; }
      const item = data.item; const idx = state.items.findIndex(i => i.id === item.id); if (idx>=0) state.items[idx]=item;
      showStatus(tr('gps_updated'), 'ok'); renderGrid(); setDetail(item);
      if (els.gpsEditWrap) { els.gpsEditWrap.classList.add('hidden'); els.gpsEditWrap.classList.remove('floating'); els.gpsEditWrap.classList.remove('gps-modal');
        try { if (gpsPrevParent) { if (gpsPrevNext) gpsPrevParent.insertBefore(els.gpsEditWrap, gpsPrevNext); else gpsPrevParent.appendChild(els.gpsEditWrap); } } catch {}
        try { if (gpsBackdrop) gpsBackdrop.classList.remove('active'); } catch{}
        try { if (gpsBackdrop && gpsBackdrop.parentElement) gpsBackdrop.parentElement.removeChild(gpsBackdrop); } catch{}
        gpsBackdrop = null;
      }
    } catch(e){ showStatus(tr('update_error'), 'err'); }
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
  btn.addEventListener("click", async () => {
    const targetView = btn.dataset.view;
    if (targetView === 'mapper') {
      state.mapperPath = '';
      state.folder = null;
    }
    await setView(targetView);
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

if (els.mobileNavItems && els.mobileNavItems.length) {
  els.mobileNavItems.forEach((btn) => {
    btn.addEventListener('click', async () => {
      const action = btn.dataset.mobileAction;
      if (action === 'navigate') {
        if (document.body.classList.contains('drawer-open')) closeDrawer();
        else openDrawer();
        return;
      }
      if (action === 'profile') {
        await renderProfilePanel();
        openProfileModal();
        closeDrawer();
        return;
      }
      if (action === 'view' && btn.dataset.view) {
        if (btn.dataset.view === 'mapper') {
          state.mapperPath = '';
          state.folder = null;
        }
        await setView(btn.dataset.view);
        closeDrawer();
      }
    });
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
if (els.twofaModalClose) {
  els.twofaModalClose.addEventListener('click', closeTwofaModal);
}
if (els.twofaModal) {
  els.twofaModal.addEventListener('click', (e) => {
    if (e.target === els.twofaModal) closeTwofaModal();
  });
}
if (els.mapperCreateModalClose) {
  els.mapperCreateModalClose.addEventListener('click', () => closeMapperCreateModal());
}
if (els.mapperCreateModalCancel) {
  els.mapperCreateModalCancel.addEventListener('click', () => closeMapperCreateModal());
}
if (els.mapperCreateModalConfirm) {
  els.mapperCreateModalConfirm.addEventListener('click', async () => {
    await createMapperFolder();
  });
}
if (els.mapperCreateModalInput) {
  els.mapperCreateModalInput.addEventListener('keydown', async (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      await createMapperFolder();
      return;
    }
    if (e.key === 'Escape') {
      e.preventDefault();
      closeMapperCreateModal();
    }
  });
}
if (els.mapperCreateModal) {
  els.mapperCreateModal.addEventListener('click', (e) => {
    if (e.target === els.mapperCreateModal) closeMapperCreateModal();
  });
}
if (els.mapperSharePasswordToggle) {
  els.mapperSharePasswordToggle.addEventListener('change', _syncMapperSharePasswordVisibility);
}
if (els.mapperShareModalClose) {
  els.mapperShareModalClose.addEventListener('click', () => closeMapperShareModal());
}
if (els.mapperShareModalCancel) {
  els.mapperShareModalCancel.addEventListener('click', () => closeMapperShareModal());
}
if (els.mapperShareModalConfirm) {
  els.mapperShareModalConfirm.addEventListener('click', async () => {
    await createMapperShareLink();
  });
}
if (els.mapperShareCopyBtn) {
  els.mapperShareCopyBtn.addEventListener('click', async () => {
    await copyMapperShareLink();
  });
}
if (els.mapperShareModal) {
  els.mapperShareModal.addEventListener('click', (e) => {
    if (e.target === els.mapperShareModal) closeMapperShareModal();
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
if (els.aiScopeModalClose) {
  els.aiScopeModalClose.addEventListener('click', closeAiScopeModal);
}
if (els.aiScopeModalCancel) {
  els.aiScopeModalCancel.addEventListener('click', closeAiScopeModal);
}
if (els.aiScopeModalNew) {
  els.aiScopeModalNew.addEventListener('click', async () => {
    const feature = state.aiScopePendingFeature;
    closeAiScopeModal();
    if (feature === 'faces') {
      await startFacesIndex('new');
    } else if (feature === 'describe') {
      await startAiDescribeIngest('new');
    } else {
      await startAiIngest('new');
    }
  });
}
if (els.aiScopeModalAll) {
  els.aiScopeModalAll.addEventListener('click', async () => {
    const feature = state.aiScopePendingFeature;
    closeAiScopeModal();
    if (feature === 'faces') {
      await startFacesIndex('all');
    } else if (feature === 'describe') {
      await startAiDescribeIngest('all');
    } else {
      await startAiIngest('all');
    }
  });
}
if (els.aiScopeModal) {
  els.aiScopeModal.addEventListener('click', (e) => {
    if (e.target === els.aiScopeModal) closeAiScopeModal();
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
    if (tab === 'ai') {
      loadAiPerformanceSettings();
    }
    if (tab === 'dns') {
      loadDnsSettings();
    }
    if (tab === 'shared') {
      loadDnsShares();
    }
  });
});

if (els.dnsSaveBtn) {
  els.dnsSaveBtn.addEventListener('click', async () => {
    await saveDnsSettings();
  });
}
if (els.aiPerfSaveBtn) {
  els.aiPerfSaveBtn.addEventListener('click', async () => {
    await saveAiPerformanceSettings();
  });
}
if (els.aiPerfPresetLow) {
  els.aiPerfPresetLow.addEventListener('click', async () => {
    applyAiPerfPreset('low');
    await saveAiPerformanceSettings();
  });
}
if (els.aiPerfPresetNormal) {
  els.aiPerfPresetNormal.addEventListener('click', async () => {
    applyAiPerfPreset('normal');
    await saveAiPerformanceSettings();
  });
}
if (els.aiPerfPresetFast) {
  els.aiPerfPresetFast.addEventListener('click', async () => {
    applyAiPerfPreset('fast');
    await saveAiPerformanceSettings();
  });
}
if (els.sharedLinksList) {
  els.sharedLinksList.addEventListener('click', async (e) => {
    const target = e.target;
    if (!(target instanceof HTMLElement)) return;
    const copyId = Number(target.getAttribute('data-share-copy') || 0) || 0;
    if (copyId > 0) {
      const item = Array.isArray(state.sharedLinks) ? state.sharedLinks.find((s) => Number(s.id || 0) === copyId) : null;
      await _copySharedLink(item && item.link ? String(item.link) : '');
      return;
    }
    const revokeId = Number(target.getAttribute('data-share-revoke') || 0) || 0;
    if (revokeId > 0) {
      await revokeDnsShare(revokeId);
      return;
    }
    const activateId = Number(target.getAttribute('data-share-activate') || 0) || 0;
    if (activateId > 0) {
      await activateDnsShare(activateId);
      return;
    }
    const extendId = Number(target.getAttribute('data-share-extend') || 0) || 0;
    if (extendId > 0) {
      await extendDnsShare(extendId);
      return;
    }
    const deleteId = Number(target.getAttribute('data-share-delete') || 0) || 0;
    if (deleteId > 0) {
      await deleteDnsShare(deleteId);
    }
  });
}

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

if (els.mapperUploadInput) {
  els.mapperUploadInput.addEventListener('change', async () => {
    const files = els.mapperUploadInput && els.mapperUploadInput.files ? els.mapperUploadInput.files : null;
    if (!files || !files.length) return;
    const targetSubdir = String(state.mapperPath || '');
    await uploadFiles(files, { destination: 'uploads', subdir: targetSubdir });
    await loadMapperTools(targetSubdir);
    await loadPhotos();
    els.mapperUploadInput.value = '';
  });
}

// viewer events
els.viewerClose && els.viewerClose.addEventListener("click", closeViewer);
els.viewerPrev && els.viewerPrev.addEventListener("click", () => nextViewer(-1));
els.viewerNext && els.viewerNext.addEventListener("click", () => nextViewer(1));

let viewerTouchStartX = null;
let viewerTouchStartY = null;
let viewerTouchStartTime = 0;
let viewerDragActive = false;
let viewerDragDx = 0;
let viewerSwipePreviewEl = null;
let viewerSwipePreviewIndex = -1;

function getViewerTargetIndex(step) {
  const n = Array.isArray(state.items) ? state.items.length : 0;
  if (!n || state.selectedIndex < 0) return -1;
  return (state.selectedIndex + step + n) % n;
}

function removeViewerSwipePreview() {
  if (!viewerSwipePreviewEl) {
    viewerSwipePreviewIndex = -1;
    return;
  }
  try {
    if (viewerSwipePreviewEl.tagName === 'VIDEO') {
      try { viewerSwipePreviewEl.pause(); } catch (_) {}
      viewerSwipePreviewEl.removeAttribute('src');
    }
  } catch (_) {}
  try {
    if (viewerSwipePreviewEl.parentElement) viewerSwipePreviewEl.parentElement.removeChild(viewerSwipePreviewEl);
  } catch (_) {}
  viewerSwipePreviewEl = null;
  viewerSwipePreviewIndex = -1;
}

function ensureViewerSwipePreview(targetIndex) {
  if (!els.viewer || els.viewer.classList.contains('hidden')) return null;
  if (targetIndex < 0 || !state.items[targetIndex]) {
    removeViewerSwipePreview();
    return null;
  }
  if (viewerSwipePreviewEl && viewerSwipePreviewIndex === targetIndex) return viewerSwipePreviewEl;

  removeViewerSwipePreview();
  const it = state.items[targetIndex];
  if (!it || !it.original_url) return null;

  const node = it.is_video ? document.createElement('video') : document.createElement('img');
  if (it.is_video) {
    node.muted = true;
    node.playsInline = true;
    node.preload = 'metadata';
    node.src = it.original_url;
  } else {
    node.alt = '';
    node.src = it.original_url || it.thumb_url || '';
  }
  node.style.position = 'absolute';
  node.style.left = '0';
  node.style.top = '0';
  node.style.width = '100%';
  node.style.height = '100%';
  node.style.objectFit = 'contain';
  node.style.background = '#000';
  node.style.pointerEvents = 'none';
  node.style.zIndex = '1';
  node.style.opacity = '1';
  node.style.transform = 'translateX(0)';
  node.style.willChange = 'transform, opacity';

  els.viewer.insertBefore(node, els.viewer.firstChild || null);
  viewerSwipePreviewEl = node;
  viewerSwipePreviewIndex = targetIndex;
  return node;
}

function resetViewerTouchState() {
  viewerTouchStartX = null;
  viewerTouchStartY = null;
  viewerTouchStartTime = 0;
  viewerDragActive = false;
  viewerDragDx = 0;
}

function applyViewerDragTransform(dx) {
  const active = getActiveViewerMediaElement();
  if (!active) return;
  const w = Math.max(1, window.innerWidth || 1);
  const ratio = Math.min(1, Math.abs(dx) / w);
  const step = dx < 0 ? 1 : -1;
  const targetIndex = getViewerTargetIndex(step);
  const preview = ensureViewerSwipePreview(targetIndex);
  active.style.willChange = 'transform, opacity';
  active.style.transition = 'none';
  active.style.transform = `translateX(${Math.round(dx)}px)`;
  active.style.opacity = String(Math.max(0.72, 1 - ratio * 0.38));
  if (preview) {
    const offset = step > 0 ? w : -w;
    preview.style.transition = 'none';
    preview.style.transform = `translateX(${Math.round(dx + offset)}px)`;
    preview.style.opacity = '1';
  }
}

function animateViewerDragReset() {
  const active = getActiveViewerMediaElement();
  if (!active) return;
  active.style.willChange = 'transform, opacity';
  active.style.transition = 'transform 170ms ease, opacity 170ms ease';
  active.style.transform = 'translateX(0)';
  active.style.opacity = '1';
  if (viewerSwipePreviewEl) {
    const step = viewerDragDx < 0 ? 1 : -1;
    const w = Math.max(1, window.innerWidth || 1);
    const offset = step > 0 ? w : -w;
    viewerSwipePreviewEl.style.transition = 'transform 170ms ease, opacity 170ms ease';
    viewerSwipePreviewEl.style.transform = `translateX(${offset}px)`;
    viewerSwipePreviewEl.style.opacity = '1';
  }
  window.setTimeout(() => {
    cleanupViewerMediaAnimation();
    removeViewerSwipePreview();
  }, 190);
}

function commitViewerDragSwipe(step) {
  const targetIndex = getViewerTargetIndex(step);
  if (targetIndex < 0 || !state.items[targetIndex]) {
    animateViewerDragReset();
    return;
  }
  const active = getActiveViewerMediaElement();
  const preview = ensureViewerSwipePreview(targetIndex);
  if (!active || !preview) {
    state.selectedIndex = targetIndex;
    openViewer(targetIndex);
    removeViewerSwipePreview();
    viewerTransitionRunning = false;
    return;
  }

  const duration = 170;
  const w = Math.max(1, window.innerWidth || 1);
  const outX = step > 0 ? -w : w;
  active.style.willChange = 'transform, opacity';
  active.style.transition = `transform ${duration}ms ease, opacity ${duration}ms ease`;
  active.style.transform = `translateX(${outX}px)`;
  active.style.opacity = '0.25';

  preview.style.willChange = 'transform, opacity';
  preview.style.transition = `transform ${duration}ms ease, opacity ${duration}ms ease`;
  preview.style.transform = 'translateX(0)';
  preview.style.opacity = '1';

  window.setTimeout(() => {
    state.selectedIndex = targetIndex;
    removeViewerSwipePreview();
    openViewer(targetIndex);
    cleanupViewerMediaAnimation();
    viewerTransitionRunning = false;
    if (viewerPendingStep !== 0) {
      const pending = viewerPendingStep;
      viewerPendingStep = 0;
      nextViewer(pending);
    }
  }, duration + 25);
}

if (els.viewer) {
  els.viewer.addEventListener('touchstart', (e) => {
    if (!e.touches || e.touches.length !== 1) return;
    if (viewerTransitionRunning) return;
    const target = e.target;
    if (target && (target.closest('#viewerClose, #viewerMenuBtn, #viewerMenu, #viewerInfoBtn, #viewerPrev, #viewerNext, #viewerInfo, .btn, a'))) return;
    const t = e.touches[0];
    viewerTouchStartX = t.clientX;
    viewerTouchStartY = t.clientY;
    viewerTouchStartTime = Date.now();
    viewerDragActive = false;
    viewerDragDx = 0;
  }, { passive: true });

  els.viewer.addEventListener('touchmove', (e) => {
    if (viewerTouchStartX === null || viewerTouchStartY === null) return;
    if (!els.viewer || els.viewer.classList.contains('hidden')) return;
    if (viewerTransitionRunning) return;
    const t = e.touches && e.touches[0];
    if (!t) return;
    const dx = t.clientX - viewerTouchStartX;
    const dy = t.clientY - viewerTouchStartY;
    const absX = Math.abs(dx);
    const absY = Math.abs(dy);
    if (!viewerDragActive) {
      if (absX < 8 || absX <= absY * 1.1) return;
      viewerDragActive = true;
    }
    viewerDragDx = dx;
    applyViewerDragTransform(dx);
    e.preventDefault();
  }, { passive: false });

  els.viewer.addEventListener('touchend', (e) => {
    if (viewerTouchStartX === null || viewerTouchStartY === null) return;
    if (!els.viewer || els.viewer.classList.contains('hidden')) {
      resetViewerTouchState();
      return;
    }
    const changed = e.changedTouches && e.changedTouches[0];
    if (!changed) return;
    const dx = viewerDragActive ? viewerDragDx : (changed.clientX - viewerTouchStartX);
    const dy = changed.clientY - viewerTouchStartY;
    const dt = Date.now() - viewerTouchStartTime;
    const absX = Math.abs(dx);
    const absY = Math.abs(dy);
    const minSwipe = Math.max(52, Math.round((window.innerWidth || 320) * 0.16));
    const isHorizontalSwipe = absX >= minSwipe && absX > absY * 1.12 && dt <= 900;
    if (isHorizontalSwipe) {
      const step = dx < 0 ? 1 : -1;
      if (viewerDragActive) {
        viewerTransitionRunning = true;
        commitViewerDragSwipe(step);
      } else {
        nextViewer(step);
      }
    } else if (viewerDragActive) {
      animateViewerDragReset();
    }
    resetViewerTouchState();
  }, { passive: true });

  els.viewer.addEventListener('touchcancel', () => {
    if (viewerDragActive) animateViewerDragReset();
    resetViewerTouchState();
  }, { passive: true });
}

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
const viewerMenu = els.viewerMenu;
const viewerMenuBtn = els.viewerMenuBtn;
const viewerMenuInfoBtn = els.viewerMenuInfoBtn;
const viewerInfoGrab = document.getElementById('viewerInfoGrab');
let viewerInfoHideTimer = null;
let viewerInfoDragActive = false;
let viewerInfoDragStartY = 0;
let viewerInfoDragDeltaY = 0;
let viewerInfoDragStartTime = 0;

function isMobileViewerLayout() {
  return window.matchMedia('(max-width: 760px)').matches;
}

function isViewerInfoPanelOpen() {
  return !!viPanel && viPanel.classList.contains('open') && !viPanel.classList.contains('hidden');
}

function resetViewerInfoDragState() {
  viewerInfoDragActive = false;
  viewerInfoDragStartY = 0;
  viewerInfoDragDeltaY = 0;
  viewerInfoDragStartTime = 0;
}

function positionViewerInfoPanel() {
  if (!viPanel) return;
  if (isMobileViewerLayout()) {
    viPanel.style.left = '';
    viPanel.style.right = '';
    viPanel.style.top = '';
    viPanel.style.bottom = '';
    viPanel.style.height = '';
    return;
  }
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
}

function toggleViewerInfoPanel(forceOpen = null) {
  if (!viPanel) return;
  if (viewerInfoHideTimer) {
    window.clearTimeout(viewerInfoHideTimer);
    viewerInfoHideTimer = null;
  }
  resetViewerInfoDragState();
  viPanel.style.transition = '';
  viPanel.style.transform = '';
  const shouldOpen = forceOpen === null ? !viPanel.classList.contains('open') : !!forceOpen;
  if (!shouldOpen) {
    viPanel.classList.remove('open');
    if (isMobileViewerLayout()) {
      viPanel.classList.add('hidden');
      viPanel.style.transition = '';
      viPanel.style.transform = '';
      return;
    }
    viewerInfoHideTimer = window.setTimeout(() => {
      viPanel.classList.add('hidden');
      viewerInfoHideTimer = null;
    }, isMobileViewerLayout() ? 260 : 220);
    return;
  }
  viPanel.classList.remove('hidden');
  positionViewerInfoPanel();
  void viPanel.offsetWidth;
  viPanel.classList.add('open');
}

if (viBtn && viPanel) {
  viBtn.addEventListener('click', () => toggleViewerInfoPanel());
}

if (viewerMenuBtn && viewerMenu) {
  viewerMenuBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    viewerMenu.classList.toggle('hidden');
  });
}

if (viewerMenuInfoBtn) {
  viewerMenuInfoBtn.addEventListener('click', () => {
    if (viewerMenu) viewerMenu.classList.add('hidden');
    toggleViewerInfoPanel();
  });
}

if (viPanel) {
  viPanel.addEventListener('touchstart', (e) => {
    if (!isMobileViewerLayout() || !isViewerInfoPanelOpen()) return;
    if (!e.touches || e.touches.length !== 1) return;
    const touch = e.touches[0];
    const target = e.target;
    const fromGrab = !!(target && target.closest && target.closest('#viewerInfoGrab'));
    const panelTop = viPanel.getBoundingClientRect().top;
    const touchNearTop = (touch.clientY - panelTop) <= 72;
    const panelAtTop = (viPanel.scrollTop || 0) <= 0;
    if (!fromGrab && !(touchNearTop && panelAtTop)) return;

    viewerInfoDragActive = true;
    viewerInfoDragStartY = touch.clientY;
    viewerInfoDragDeltaY = 0;
    viewerInfoDragStartTime = Date.now();
    viPanel.style.transition = 'none';
  }, { passive: true });

  viPanel.addEventListener('touchmove', (e) => {
    if (!viewerInfoDragActive || !isMobileViewerLayout()) return;
    const touch = e.touches && e.touches[0];
    if (!touch) return;
    const delta = Math.max(0, touch.clientY - viewerInfoDragStartY);
    viewerInfoDragDeltaY = delta;
    viPanel.style.transform = `translateY(${Math.round(delta)}px)`;
    if (delta > 0) e.preventDefault();
  }, { passive: false });

  viPanel.addEventListener('touchend', () => {
    if (!viewerInfoDragActive || !isMobileViewerLayout()) {
      resetViewerInfoDragState();
      return;
    }
    const dt = Math.max(1, Date.now() - viewerInfoDragStartTime);
    const velocity = viewerInfoDragDeltaY / dt;
    const minSwipeDown = Math.max(90, Math.round((window.innerHeight || 640) * 0.12));
    const shouldClose = viewerInfoDragDeltaY >= minSwipeDown || velocity > 0.42;
    if (shouldClose) {
      viPanel.style.transition = '';
      viPanel.style.transform = '';
      resetViewerInfoDragState();
      toggleViewerInfoPanel(false);
      return;
    }
    viPanel.style.transition = 'transform .2s ease';
    viPanel.style.transform = 'translateY(0)';
    window.setTimeout(() => {
      if (isViewerInfoPanelOpen()) {
        viPanel.style.transition = '';
        viPanel.style.transform = '';
      }
    }, 210);
    resetViewerInfoDragState();
  }, { passive: true });

  viPanel.addEventListener('touchcancel', () => {
    if (!viewerInfoDragActive) return;
    viPanel.style.transition = '';
    viPanel.style.transform = '';
    resetViewerInfoDragState();
  }, { passive: true });
}

if (els.viewer && viPanel) {
  els.viewer.addEventListener('click', (e) => {
    if (!isMobileViewerLayout() || !isViewerInfoPanelOpen()) return;
    const target = e.target;
    if (target === els.viewerImg || target === els.viewerVideo) {
      toggleViewerInfoPanel(false);
    }
  });
}

if (els.viewer && viewerMenu) {
  els.viewer.addEventListener('click', (e) => {
    if (viewerMenu.classList.contains('hidden')) return;
    const target = e.target;
    if (target && (target.closest('#viewerMenu') || target.closest('#viewerMenuBtn'))) return;
    viewerMenu.classList.add('hidden');
  });
}
// Hide panel on close
const _origCloseViewer = closeViewer;
closeViewer = function(){
  try {
    if (viewerInfoHideTimer) {
      window.clearTimeout(viewerInfoHideTimer);
      viewerInfoHideTimer = null;
    }
    if (viPanel) {
      viPanel.classList.remove('open');
      viPanel.classList.add('hidden');
      viPanel.style.left = '';
      viPanel.style.right = '';
      viPanel.style.top = '';
      viPanel.style.bottom = '';
      viPanel.style.height = '';
      viPanel.style.transition = '';
      viPanel.style.transform = '';
      resetViewerInfoDragState();
    }
    if (viewerMenu) { viewerMenu.classList.add('hidden'); }
    cleanupViewerMediaAnimation();
    removeViewerSwipePreview();
    resetViewerTouchState();
  } catch {}
  _origCloseViewer();
}

// Keep the slide-out anchored to the media edge on resize
window.addEventListener('resize', ()=>{
  try {
    const vi = document.getElementById('viewerInfo');
    if (!vi) return;
    if (isMobileViewerLayout()) return;
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
    if (!res.ok) { showStatus(data && data.error ? data.error : tr('similar_fetch_failed'), 'err'); return; }
    state.view = 'timeline';
    state.items = Array.isArray(data.items) ? data.items : [];
    state.selectedId = null;
    if (els.viewTitle) els.viewTitle.textContent = tr('similar_view_title');
    if (els.viewSubtitle) els.viewSubtitle.textContent = tr('similar_view_subtitle');
    closeViewer();
    renderGrid();
  } catch { showStatus(tr('similar_fetch_error'), 'err'); }
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
  _announceUploadResumeDraftIfNeeded();
  // Resume upload postprocess monitor/state if page was refreshed mid-run.
  resumeUploadPostprocessAfterRefresh().catch(() => {});
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
    const loginAudit = Array.isArray(js.login_audit) ? js.login_audit : [];
    const availableFolders = Array.isArray(js.available_folders) ? js.available_folders : [];
    const rows = items.map(u => {
      const role = String(u.role || '').toLowerCase();
      const aclButton = role === 'admin'
        ? ''
        : `<button data-acl="${u.id}" class="btn small">Mapper</button>`;
      return `
      <tr>
        <td class="muted">#${u.id}</td>
        <td><strong>${u.username}</strong></td>
        <td>${u.role}</td>
        <td>${(u.ui_language || 'da').toUpperCase()} / ${(u.search_language || 'da').toUpperCase()}</td>
        <td>${u.totp_enabled ? '<span class="badge twofa">2FA</span>' : '<span class="badge muted">—</span>'}</td>
        <td style="text-align:right;display:flex;gap:6px;justify-content:flex-end;">
          ${aclButton}
          <button data-edit="${u.id}" class="btn small">Rediger</button>
          <button data-del="${u.id}" class="btn danger small">Slet</button>
        </td>
      </tr>`;
    }).join('');
    const auditRows = loginAudit.map((entry) => {
      const status = entry && entry.success ? tr('users_login_status_ok') : tr('users_login_status_fail');
      const statusClass = entry && entry.success ? 'ok' : 'err';
      const userTxt = (entry && entry.username) || (entry && entry.username_input) || tr('users_login_unknown');
      const reasonTxt = (entry && entry.reason) || (entry && entry.event_type) || '—';
      return `
      <tr>
        <td>${escapeHtml(fmtDate(entry && entry.at))}</td>
        <td>${escapeHtml(userTxt)}</td>
        <td><span class="upload-monitor-item-status ${statusClass}">${escapeHtml(status)}</span></td>
        <td>${escapeHtml(reasonTxt)}</td>
        <td>${escapeHtml((entry && entry.ip) || '—')}</td>
        <td>${escapeHtml((entry && entry.country) || '—')}</td>
        <td>${escapeHtml((entry && entry.device) || '—')}</td>
      </tr>`;
    }).join('');
    wrap.innerHTML = `
      <div class="panel" style="margin-bottom:12px;">
        <div class="toolbar">
          <strong>${escapeHtml(tr('users_panel_title'))}</strong>
          <button id="nu_open" class="btn primary" style="margin-left:auto;">${escapeHtml(tr('users_add_user'))}</button>
        </div>
      </div>
      <div class="data-table" style="margin-bottom:12px;">
        <table>
          <thead><tr><th>${escapeHtml(tr('users_col_id'))}</th><th>${escapeHtml(tr('users_col_username'))}</th><th>${escapeHtml(tr('users_col_role'))}</th><th>${escapeHtml(tr('users_col_language'))}</th><th>${escapeHtml(tr('users_col_2fa'))}</th><th></th></tr></thead>
          <tbody>${rows || `<tr><td colspan=6 class="muted">${escapeHtml(tr('users_no_users'))}</td></tr>`}</tbody>
        </table>
      </div>
      <div class="panel" style="margin-bottom:8px;">
        <div class="toolbar"><strong>${escapeHtml(tr('users_login_log_title'))}</strong></div>
      </div>
      <div class="data-table" style="margin-bottom:12px;">
        <table>
          <thead><tr><th>${escapeHtml(tr('users_login_col_time'))}</th><th>${escapeHtml(tr('users_login_col_user'))}</th><th>${escapeHtml(tr('users_login_col_status'))}</th><th>${escapeHtml(tr('users_login_col_reason'))}</th><th>${escapeHtml(tr('users_login_col_ip'))}</th><th>${escapeHtml(tr('users_login_col_country'))}</th><th>${escapeHtml(tr('users_login_col_device'))}</th></tr></thead>
          <tbody>${auditRows || `<tr><td colspan=7 class="muted">${escapeHtml(tr('users_login_log_empty'))}</td></tr>`}</tbody>
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

      <!-- Folder access modal -->
      <div id="ua_modal" class="hidden" style="position:fixed;inset:0;background:rgba(0,0,0,0.6);display:flex;align-items:center;justify-content:center;z-index:10000;">
        <div style="width:700px;max-width:95vw;max-height:90vh;overflow:auto;background:var(--panel);border:1px solid var(--border);border-radius:12px;padding:16px;">
          <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px;gap:8px;">
            <h3 style="margin:0;">${escapeHtml(tr('users_folders_title'))}</h3>
            <button id="ua_close" class="btn">${escapeHtml(tr('users_close'))}</button>
          </div>
          <div id="ua_user" class="mini-label" style="margin-bottom:8px;"></div>
          <div id="ua_hint" class="mini-label" style="margin-bottom:8px;">${escapeHtml(tr('users_folders_hint'))}</div>
          <div id="ua_folder_access" style="max-height:55vh;overflow:auto;padding:10px;border:1px solid var(--border);border-radius:8px;background:var(--bg-soft);"></div>
          <div class="actions" style="justify-content:flex-end;margin-top:10px;">
            <button id="ua_select_all" class="btn">${escapeHtml(tr('users_select_all'))}</button>
            <button id="ua_clear_all" class="btn">${escapeHtml(tr('users_clear_all'))}</button>
            <button id="ua_cancel" class="btn">${escapeHtml(tr('users_cancel'))}</button>
            <button id="ua_save" class="btn primary">${escapeHtml(tr('users_save_access'))}</button>
          </div>
        </div>
      </div>
    `;

    const byId = new Map(items.map(u => [String(u.id), u]));

    const normalizeAclFolder = (value) => String(value || '')
      .replace(/\\/g, '/')
      .replace(/\/+/g, '/')
      .replace(/^\/+|\/+$/g, '');

    const setFolderSelection = (containerId, selectedFolders, allFolders = []) => {
      const root = document.getElementById(containerId);
      if (!root) return;
      if (Array.isArray(allFolders) && allFolders.length) {
        const seen = new Set();
        const filteredFolders = allFolders
          .map((folder) => normalizeAclFolder(folder))
          .filter((folder) => folder && folder !== 'uploads')
          .filter((folder) => {
            if (seen.has(folder)) return false;
            seen.add(folder);
            return true;
          });
        root.innerHTML = filteredFolders.map((folder) => {
          const depth = String(folder || '').split('/').filter(Boolean).length;
          const pad = Math.max(0, (depth - 1) * 14);
          const label = String(folder || '').startsWith('uploads/') ? String(folder || '').slice(8) : String(folder || '');
          return `
            <label style="display:flex;align-items:center;gap:8px;padding:4px 0;padding-left:${pad}px;">
              <input type="checkbox" data-folder="${escapeHtml(folder)}" />
              <span>${escapeHtml(label)}</span>
            </label>
          `;
        }).join('');
      } else if (!root.children.length) {
        root.innerHTML = `<div class="mini-label muted">${escapeHtml(tr('users_acl_none_found'))}</div>`;
      }
      const selected = new Set((selectedFolders || [])
        .map(v => normalizeAclFolder(v))
        .filter(v => !!v && v !== 'uploads'));
      root.querySelectorAll('input[type="checkbox"][data-folder]').forEach((el) => {
        const key = normalizeAclFolder(el.getAttribute('data-folder') || '');
        el.checked = selected.has(key);
      });
    };

    const getFolderSelection = (containerId) => {
      const root = document.getElementById(containerId);
      if (!root) return [];
      return Array.from(root.querySelectorAll('input[type="checkbox"][data-folder]:checked'))
        .map((el) => normalizeAclFolder(el.getAttribute('data-folder') || ''))
        .filter((folder) => !!folder && folder !== 'uploads');
    };

    const bindAclHierarchy = (containerId) => {
      const root = document.getElementById(containerId);
      if (!root) return;
      root.querySelectorAll('input[type="checkbox"][data-folder]').forEach((el) => {
        el.addEventListener('change', () => {
          const folder = normalizeAclFolder(el.getAttribute('data-folder') || '');
          if (!folder) return;
          if (!el.checked) return;
          root.querySelectorAll('input[type="checkbox"][data-folder]').forEach((other) => {
            if (other === el) return;
            const otherFolder = normalizeAclFolder(other.getAttribute('data-folder') || '');
            if (!otherFolder || !otherFolder.startsWith(folder + '/')) return;
            other.checked = true;
          });
        });
      });
    };

    const aclModal = document.getElementById('ua_modal');
    const aclCloseBtn = document.getElementById('ua_close');
    const aclCancelBtn = document.getElementById('ua_cancel');
    const aclSelectAllBtn = document.getElementById('ua_select_all');
    const aclClearAllBtn = document.getElementById('ua_clear_all');
    const aclSaveBtn = document.getElementById('ua_save');
    const aclUserLabel = document.getElementById('ua_user');
    let aclEditingUserId = null;

    function closeAclModal() {
      if (!aclModal) return;
      aclModal.classList.add('hidden');
      aclEditingUserId = null;
    }

    wrap.querySelectorAll('button[data-acl]').forEach(btn => {
      btn.addEventListener('click', () => {
        const id = String(btn.getAttribute('data-acl') || '');
        const user = byId.get(id);
        if (!user) return;
        aclEditingUserId = user.id;
        if (aclUserLabel) {
          const count = Array.isArray(user.allowed_folders) ? user.allowed_folders.length : 0;
          aclUserLabel.textContent = `${tr('users_acl_user_prefix')}: ${user.username} (#${user.id}) — ${count ? `${count} ${tr('users_acl_selected_suffix')}` : tr('users_acl_all_folders')}`;
        }
        setFolderSelection('ua_folder_access', user.allowed_folders || [], availableFolders);
        bindAclHierarchy('ua_folder_access');
        if (aclModal) aclModal.classList.remove('hidden');
      });
    });

    aclCloseBtn && aclCloseBtn.addEventListener('click', closeAclModal);
    aclCancelBtn && aclCancelBtn.addEventListener('click', closeAclModal);
    aclSelectAllBtn && aclSelectAllBtn.addEventListener('click', () => {
      const root = document.getElementById('ua_folder_access');
      if (!root) return;
      root.querySelectorAll('input[type="checkbox"][data-folder]').forEach((el) => {
        el.checked = true;
      });
    });
    aclClearAllBtn && aclClearAllBtn.addEventListener('click', () => {
      const root = document.getElementById('ua_folder_access');
      if (!root) return;
      root.querySelectorAll('input[type="checkbox"][data-folder]').forEach((el) => {
        el.checked = false;
      });
    });
    aclModal && aclModal.addEventListener('click', (e)=>{ if(e.target === aclModal) closeAclModal(); });
    aclSaveBtn && aclSaveBtn.addEventListener('click', async () => {
      if (!aclEditingUserId) return;
      const allowed_folders = getFolderSelection('ua_folder_access');
      const rr = await fetch('/api/admin/users/' + aclEditingUserId + '/folders', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ allowed_folders }),
      });
      const jj = await rr.json();
      if (!rr.ok || !jj.ok) {
        showStatus(`${tr('users_status_acl_save_failed')} ${((jj && jj.error) || '')}`.trim(), 'err');
        return;
      }
        showStatus(tr('users_status_acl_saved'), 'ok');
      closeAclModal();
      renderUsersPanel();
    });

    // bind delete
    wrap.querySelectorAll('button[data-del]').forEach(btn=>{
      btn.addEventListener('click', async ()=>{
        const id = btn.getAttribute('data-del');
        if (!confirm(`${tr('users_confirm_delete')} #${id}?`)) return;
        const rr = await fetch('/api/admin/users/'+id, {method:'DELETE'});
        const jj = await rr.json();
        if (!rr.ok || !jj.ok){ showStatus(`${tr('users_status_delete_failed')} ${(jj && jj.error || '')}`.trim(), 'err'); return; }
        showStatus(tr('users_status_deleted'), 'ok');
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
        if (!username) { showStatus(tr('users_status_username_required'), 'err'); return; }
        const payload = { username, role, ui_language, search_language };
        if (password) payload.password = password;
        const rr = await fetch('/api/admin/users/' + editingUserId, { method:'PUT', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload) });
        const jj = await rr.json();
        if (!rr.ok || !jj.ok) { showStatus(`${tr('users_status_update_failed')} ${((jj && jj.error) || '')}`.trim(), 'err'); return; }
        showStatus(tr('users_status_updated'), 'ok');
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
        if (!username || !password){ showStatus(tr('users_status_username_password_required'), 'err'); return; }
        const payload = { username, password, role, enforce_2fa, ui_language, search_language };
        const rr = await fetch('/api/admin/users', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload)});
        const jj = await rr.json();
        if (!rr.ok || !jj.ok){ showStatus(`${tr('users_status_create_failed')} ${(jj && jj.error || '')}`.trim(), 'err'); return; }
        showStatus(tr('users_status_created'), 'ok');
        close();
        renderUsersPanel();
      });
    }
  }catch(e){ wrap.innerHTML = `<div class="empty">${tr('users_panel_render_error')}: ${e}</div>`; }
}

async function renderTwofaPanel(){
  const wrap = document.getElementById('twofaPanelInner');
  if (!wrap) return;
  wrap.textContent = tr('twofa_loading');
  try{
    const r = await fetch('/api/me/2fa');
    const js = await r.json();
    if (!r.ok || !js.ok){ wrap.innerHTML = `<div class="empty">${tr('twofa_load_failed')}</div>`; return; }
    const enabled = !!js.enabled;
    const daysVal = (js.remember_days||0);
    // Build UI depending on state
    let leftCol = '';
    if (!enabled && js.qr) {
      leftCol = `<img src="${js.qr}" alt="QR" style="width:140px;height:140px;border:1px solid var(--border);border-radius:8px;background:#fff;"/>`;
    }
    let secretRow = '';
    const toggleLabel = enabled ? tr('twofa_disable') : tr('twofa_enable');
    const toggleClass = enabled ? 'btn danger' : 'btn primary';
    const regenBtnHtml = enabled ? `<button id="tf_regen" class="btn">${escapeHtml(tr('twofa_regen'))}</button>` : '';
    wrap.innerHTML = `
      <div class="panel" style="display:flex;gap:16px;align-items:flex-start;flex-wrap:wrap;">
        ${leftCol}
        <div style="flex:1;min-width:260px;">
          <div class="form-row"><label>${tr('twofa_remember_days')}</label><input id="tf_days" class="input-number" type="number" min="0" max="30" value="${daysVal}"></div>
          ${secretRow}
          <div class="form-row"><label>${tr('twofa_onetime_code')}</label><input id="tf_code" class="input-number" placeholder="${tr('twofa_code_placeholder')}" autocomplete="one-time-code"></div>
          <div class="actions" style="flex-wrap:wrap;gap:8px;justify-content:flex-start;">
            <button id="tf_toggle" class="${toggleClass}">${toggleLabel}</button>
            <button id="tf_save" class="btn">${tr('twofa_save_btn')}</button>
            ${regenBtnHtml}
          </div>
          <div class="mini-label" style="margin-top:6px;">${tr('twofa_status_label')}: <strong>${enabled ? tr('twofa_status_enabled') : tr('twofa_status_disabled')}</strong></div>
        </div>
      </div>
    `;
    async function post(action){
      const payload = { action, code: (document.getElementById('tf_code').value||'').trim(), days: parseInt(document.getElementById('tf_days').value || '0',10) };
      const rr = await fetch('/api/me/2fa', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload)});
      const jj = await rr.json();
      if (!rr.ok || !jj.ok){ showStatus(`${tr('twofa_error_prefix')} ${(jj && jj.error || '')}`.trim(), 'err'); return; }
      showStatus(tr('twofa_updated'), 'ok');
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
        <div class="actions" style="justify-content:flex-start;margin-bottom:8px;">
          <button id="pf_open_twofa" class="btn">${tr('profile_open_twofa')}</button>
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

    const openTwofaBtn = document.getElementById('pf_open_twofa');
    if (openTwofaBtn) {
      openTwofaBtn.addEventListener('click', async () => {
        await renderTwofaPanel();
        openTwofaModal();
      });
    }

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
