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
  uploadDestSelect: document.getElementById("uploadDestSelect"),
  uploadDestSaveBtn: document.getElementById("uploadDestSaveBtn"),
  uploadDestHint: document.getElementById("uploadDestHint"),
  uploadSubdirSelect: document.getElementById("uploadSubdirSelect"),
  uploadFolderNewInput: document.getElementById("uploadFolderNewInput"),
  uploadFolderCreateBtn: document.getElementById("uploadFolderCreateBtn"),
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

const NAV_LABELS = {
  timeline: ["Tidlinje", "Dato-grupperet oversigt (år/måned)"],
  favorites: ["Favoritter", "Markerede billeder"],
  steder: ["Steder", "Billeder med GPS/placeringsdata"],
  kameraer: ["Kameraer", "Filtreret på billeder med kameradata"],
  mapper: ["Mapper", "Grupperet efter kilde-mappe"],
  personer: ["Personer", "Klar til ansigtsgenkendelse (kommer med ONNX face-service)"],
  settings: ["Indstillinger", "Vedligeholdelse, scan og administration"],
};

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
};

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
    return new Date(s).toLocaleString("da-DK");
  } catch {
    return s;
  }
}

function renderStats() {
  const inPeople = (state.view === 'personer');
  if (els.photoCountLabel) els.photoCountLabel.textContent = inPeople ? 'Personer' : 'Billeder';
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
    : `<div class="card-thumb placeholder">${item.is_video ? '🎬 Video' : 'Ingen thumbnail'}</div>`;
  const videoOverlay = item.is_video
    ? `<div class="video-badge" aria-label="Video" title="Video"><span class="video-badge-icon" aria-hidden="true"></span></div>`
    : "";

  // Gridkort uden extra tekst/metadata – kun selve billedet
  return `${thumb}${videoOverlay}`;
}

function renderGrid() {
  // Toggle fixed-width columns for folder view
  if (els.grid) els.grid.classList.toggle("folders-view", state.view === "mapper");
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
        renderEmpty("Ingen personer endnu. Upload billeder med ansigter eller kør ansigtsindeksering.");
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
      renderEmpty("Ingen billeder endnu. Slip filer for at uploade eller scan biblioteket.");
      renderStats();
      setDetail(null);
      return;
    }
    const groups = new Map(); // key: YYYY-MM label
    for (const it of items) {
      const d = new Date(it.captured_at || it.modified_fs || it.created_fs || Date.now());
      const y = d.getFullYear();
      const m = d.toLocaleString("da-DK", { month: "long" });
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
  // Restore gallery grid layout for non-timeline views
  els.grid.classList.add('gallery-grid');
  els.grid.classList.remove('timeline-wrap');
  if (!state.items.length) {
    const msg = state.view === "personer"
      ? "Ingen personer endnu. Det bliver fyldt når face-service/ansigtsgenkendelse aktiveres."
      : "Ingen billeder matcher filteret endnu. Prøv 'Scan bibliotek'.";
    renderEmpty(msg);
    renderStats();
    setDetail(null);
    return;
  }
  hideEmpty();

  const items = state.items.slice();
  if (state.view === "mapper") {
    const groups = new Map();
    for (const it of items) {
      const folder = (it.rel_path && it.rel_path.includes("/")) ? it.rel_path.split("/").slice(0, -1).join("/") : "(root)";
      if (!groups.has(folder)) groups.set(folder, []);
      groups.get(folder).push(it);
    }
    for (const [folder, arr] of groups) {
      appendFolderCard(folder, arr);
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

function appendFolderCard(folder, arr) {
  const previews = arr.slice(0, 4);
  const card = document.createElement("article");
  card.className = "photo-card folder-card";
  const cells = previews.map(p => p.thumb_url ? `<img src="${p.thumb_url}" alt="">` : "").join("");
  card.innerHTML = `
    <div class="card-thumb folder-mosaic"><div class="folder-grid">${cells}</div></div>
    <div class="card-body">
      <h4 class="card-title">${folder}</h4>
      <div class="card-meta">
        <span>${arr.length} elementer</span>
        <span>Mapper</span>
      </div>
    </div>`;
  card.addEventListener("click", () => {
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
  });

  const res = await fetch(`/api/photos?${qs.toString()}`);
  const data = await res.json();
  state.items = data.items || [];

  const [title, subtitle] = NAV_LABELS[state.view] || ["FjordLens", ""];
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
  const [title, subtitle] = NAV_LABELS['personer'] || ["Personer", ""];
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

// --- Drag & Drop Upload ---
function setUploadDestinationHint(dest, photoDir, uploadDir, subdir = '') {
  if (!els.uploadDestHint) return;
  const base = (dest === 'library') ? (photoDir || 'ukendt sti') : (uploadDir || 'ukendt sti');
  const fullPath = subdir ? `${base}/${subdir}` : base;
  if (dest === 'library') {
    els.uploadDestHint.textContent = `Drag & drop kopieres til fotobiblioteket (${fullPath}). Scan kopierer ikke filer.`;
  } else {
    els.uploadDestHint.textContent = `Drag & drop kopieres til uploads-mappen (${fullPath}). Scan kopierer ikke filer.`;
  }
}

function renderUploadSubdirs(folders, selectedSubdir, destination = 'uploads', photoDir = '', uploadDir = '') {
  if (!els.uploadSubdirSelect) return;
  const list = Array.isArray(folders) ? [...folders] : [];
  if (!list.includes('')) list.unshift('');
  const unique = Array.from(new Set(list));
  const rootSource = (destination === 'library') ? photoDir : uploadDir;
  const rootName = (String(rootSource || '').split(/[\\/]/).filter(Boolean).pop() || (destination === 'library' ? 'photos' : 'uploads'));
  els.uploadSubdirSelect.innerHTML = unique
    .map(path => {
      const label = path ? path : `${rootName} (rodmappe)`;
      return `<option value="${escapeHtml(path)}">${escapeHtml(label)}</option>`;
    })
    .join('');
  const subdir = selectedSubdir || '';
  if (!unique.includes(subdir)) {
    const opt = document.createElement('option');
    opt.value = subdir;
    opt.textContent = subdir || '(rodmappe)';
    els.uploadSubdirSelect.appendChild(opt);
  }
  els.uploadSubdirSelect.value = subdir;
}

async function fetchUploadDestinationConfig(destination = null) {
  let url = '/api/settings/upload-destination';
  if (destination) url += `?destination=${encodeURIComponent(destination)}`;
  const res = await fetch(url);
  const data = await res.json();
  return { res, data };
}

async function loadUploadDestination(previewDestination = null, keepDestinationSelection = false) {
  if (!els.uploadDestSelect) return;
  try {
    const { res, data } = await fetchUploadDestinationConfig(previewDestination);
    if (!res.ok || !data || !data.ok) {
      if (els.uploadDestHint) els.uploadDestHint.textContent = 'Kunne ikke hente kopi-placering for drag & drop.';
      return;
    }
    const savedDest = (data.saved_destination === 'library') ? 'library' : 'uploads';
    const loadedDest = (data.destination === 'library') ? 'library' : 'uploads';
    const dest = loadedDest || savedDest;
    if (!keepDestinationSelection) {
      els.uploadDestSelect.value = savedDest;
    }
    renderUploadSubdirs(data.folders || [], data.subdir || '', dest, data.photo_dir || '', data.upload_dir || '');
    setUploadDestinationHint(dest, data.photo_dir, data.upload_dir, data.subdir || '');
  } catch {
    if (els.uploadDestHint) els.uploadDestHint.textContent = 'Kunne ikke hente kopi-placering for drag & drop.';
  }
}

async function saveUploadDestination() {
  if (!els.uploadDestSelect) return;
  const destination = (els.uploadDestSelect.value === 'library') ? 'library' : 'uploads';
  const subdir = els.uploadSubdirSelect ? (els.uploadSubdirSelect.value || '') : '';
  try {
    if (els.uploadDestSaveBtn) els.uploadDestSaveBtn.disabled = true;
    const res = await fetch('/api/settings/upload-destination', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ destination, subdir }),
    });
    const data = await res.json();
    if (!res.ok || !data || !data.ok) {
      showStatus((data && data.error) || 'Kunne ikke gemme kopi-placering for drag & drop', 'err');
      return;
    }
    renderUploadSubdirs(data.folders || [], data.subdir || '', data.destination || destination, data.photo_dir || '', data.upload_dir || '');
    setUploadDestinationHint(data.destination, data.photo_dir, data.upload_dir, data.subdir || '');
    showStatus('Kopi-placering for drag & drop gemt.', 'ok');
  } catch {
    showStatus('Fejl ved gem af kopi-placering for drag & drop.', 'err');
  } finally {
    if (els.uploadDestSaveBtn) els.uploadDestSaveBtn.disabled = false;
  }
}

async function createUploadFolder() {
  if (!els.uploadDestSelect || !els.uploadFolderNewInput) return;
  const destination = (els.uploadDestSelect.value === 'library') ? 'library' : 'uploads';
  const parent = els.uploadSubdirSelect ? (els.uploadSubdirSelect.value || '') : '';
  const path = (els.uploadFolderNewInput.value || '').trim();
  if (!path) {
    showStatus('Skriv mappenavn først.', 'err');
    return;
  }
  try {
    if (els.uploadFolderCreateBtn) els.uploadFolderCreateBtn.disabled = true;
    const res = await fetch('/api/settings/upload-folder', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ destination, parent, path }),
    });
    const data = await res.json();
    if (!res.ok || !data || !data.ok) {
      showStatus((data && data.error) || 'Kunne ikke oprette mappe', 'err');
      return;
    }
    if (els.uploadFolderNewInput) els.uploadFolderNewInput.value = '';
    renderUploadSubdirs(data.folders || [], data.created || data.subdir || '', data.destination || destination, data.photo_dir || '', data.upload_dir || '');
    setUploadDestinationHint(data.destination, data.photo_dir, data.upload_dir, data.subdir || data.created || '');
    showStatus('Mappe oprettet. Husk at gemme placering.', 'ok');
  } catch {
    showStatus('Fejl ved oprettelse af mappe.', 'err');
  } finally {
    if (els.uploadFolderCreateBtn) els.uploadFolderCreateBtn.disabled = false;
  }
}

async function uploadFiles(fileList) {
  const files = Array.from(fileList || []).filter(f => !!f && f.name);
  if (!files.length) return;
  const fd = new FormData();
  const meta = [];
  for (const f of files) { fd.append('files', f, f.name); meta.push({ name: f.name, lastModified: f.lastModified }); }
  fd.append('meta', JSON.stringify(meta));
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
  } catch (e) {
    console.error(e);
  } finally {
    if (els.uploadOverlay) { els.uploadOverlay.classList.remove('active'); els.uploadOverlay.classList.add('hidden'); }
  }
}

window.addEventListener('dragover', (e) => {
  if (e.dataTransfer && e.dataTransfer.types && e.dataTransfer.types.includes('Files')) {
    e.preventDefault();
    if (els.uploadOverlay) { els.uploadOverlay.classList.remove('hidden'); els.uploadOverlay.classList.add('active'); }
    if (els.uploadProgressBar) els.uploadProgressBar.style.width = '0%';
    if (els.uploadProgressText) els.uploadProgressText.textContent = 'Slip filer for at uploade';
  }
});
window.addEventListener('drop', (e) => {
  if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length) {
    e.preventDefault();
    uploadFiles(e.dataTransfer.files);
  }
  // If nothing to upload, hide overlay
  if (!(e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length)) {
    if (els.uploadOverlay) { els.uploadOverlay.classList.remove('active'); els.uploadOverlay.classList.add('hidden'); }
  }
});
window.addEventListener('dragleave', (e) => {
  // Hide when leaving window
  if (e.screenX === 0 && e.screenY === 0) {
    if (els.uploadOverlay) { els.uploadOverlay.classList.remove('active'); els.uploadOverlay.classList.add('hidden'); }
  }
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

function setView(view) {
  state.view = view;
  state.folder = null;
  state.selectedId = null;
  document.querySelectorAll(".nav-item").forEach(btn => {
    btn.classList.toggle("active", btn.dataset.view === view);
  });
  // Toggle body class to drive CSS for Settings view
  document.body.classList.toggle("view-settings", view === "settings");
  document.body.classList.toggle("view-timeline", view === "timeline");
  if (view === "settings") {
    // show logs panel, do not load photos
    renderGrid();
  } else if (view === 'personer') {
    state.personView = { mode: 'list', personId: null, personName: null };
    loadPeople();
  } else {
    loadPhotos();
  }
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
els.scanBtn.addEventListener("click", scanLibrary);
els.rescanBtn && els.rescanBtn.addEventListener("click", rescanMetadata);
els.rethumbBtn && els.rethumbBtn.addEventListener("click", rethumbAll);
els.clearIndexBtn && els.clearIndexBtn.addEventListener("click", clearIndex);
els.aiIngestBtn && els.aiIngestBtn.addEventListener("click", async () => {
  try {
    showStatus("Starter AI‑indeksering (embeddings)...", "ok");
    const res = await fetch('/api/ai/ingest', { method: 'POST' });
    const data = await res.json();
    if (!res.ok || !data.ok) {
      showStatus("Kunne ikke starte AI‑indeksering.", "err");
      return;
    }
    showStatus("AI‑indeksering er startet i baggrunden.", "ok");
    pollAiStatus();
  } catch { showStatus("Fejl ved start af AI‑indeksering.", "err"); }
});

els.aiStopBtn && els.aiStopBtn.addEventListener('click', async () => {
  try { await fetch('/api/ai/stop', { method: 'POST' }); pollAiStatus(); } catch {}
});

// Faces indexing controls
async function pollFacesStatus() {
  try {
    const r = await fetch('/api/faces/status');
    const s = await r.json();
    if (els.facesStatus) {
      const run = s && s.running ? 'kører' : 'stoppet';
      els.facesStatus.textContent = `Ansigter: ${run}`;
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
    if (els.facesStatus) els.facesStatus.textContent = 'Ansigter: —';
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
    if (els.aiStatus) {
      if (!s || !s.ok) { els.aiStatus.textContent = 'AI: —'; }
      else {
        const run = s.running ? 'kører' : 'stoppet';
        els.aiStatus.textContent = `AI: ${run} · embedded ${s.embedded||0}/${s.total||0} · fejl ${s.failed||0}`;
      }
    }
  } catch { if (els.aiStatus) els.aiStatus.textContent = 'AI: —'; }
  // Poll mens der kører noget
  try {
    const r2 = await fetch('/api/ai/status');
    const s2 = await r2.json();
    if (s2 && s2.running) setTimeout(pollAiStatus, 1200);
  } catch {}
}

// Start med at vise status hvis noget kører allerede
pollAiStatus();
loadUploadDestination();
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
    setView(btn.dataset.view);
    // Close drawer on mobile nav selection
    document.body.classList.remove("drawer-open");
  });
});

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
    if (tab === 'maint') loadUploadDestination();
  });
});

els.uploadDestSaveBtn && els.uploadDestSaveBtn.addEventListener('click', saveUploadDestination);
els.uploadFolderCreateBtn && els.uploadFolderCreateBtn.addEventListener('click', createUploadFolder);
els.uploadDestSelect && els.uploadDestSelect.addEventListener('change', () => {
  const destination = (els.uploadDestSelect.value === 'library') ? 'library' : 'uploads';
  loadUploadDestination(destination, true);
});

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
loadPhotos().then(() => {
  showStatus("Klar. Tryk 'Scan bibliotek' for at indeksere dine billeder.", "ok");
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
    const rows = (js.items||[]).map(u => `
      <tr>
        <td class="muted">#${u.id}</td>
        <td><strong>${u.username}</strong></td>
        <td>${u.role}</td>
        <td>${u.totp_enabled ? '<span class="badge twofa">2FA</span>' : '<span class="badge muted">—</span>'}</td>
        <td style="text-align:right"><button data-del="${u.id}" class="btn danger small">Slet</button></td>
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
          <thead><tr><th>ID</th><th>Brugernavn</th><th>Rolle</th><th>2FA</th><th></th></tr></thead>
          <tbody>${rows || '<tr><td colspan=5 class="muted">Ingen brugere</td></tr>'}</tbody>
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
    `;
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
      if (u) u.value = '';
      if (p) p.value = '';
      if (r) r.value = 'user';
      if (f) f.checked = false;
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
        const enforce_2fa = !!(document.getElementById('nu_2fa') && document.getElementById('nu_2fa').checked);
        if (!username || !password){ showStatus('Udfyld brugernavn og adgangskode.', 'err'); return; }
        const payload = { username, password, role, enforce_2fa };
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
