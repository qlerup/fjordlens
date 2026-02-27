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
  stopScanBtn: null,
  status: document.getElementById("statusBar"),
  empty: document.getElementById("emptyState"),

  photoCount: document.getElementById("photoCount"),
  favoriteCount: document.getElementById("favoriteCount"),
  selectedCount: document.getElementById("selectedCount"),

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
  detailCamera: document.getElementById("detailCamera"),
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
};

const NAV_LABELS = {
  library: ["Bibliotek", "Scan din fotomappe og søg/sortér i metadata"],
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
  view: "library",
  sort: "date_desc",
  q: "",
  scanning: false,
  selectedIndex: -1,
  folder: null,
  // logs
  logsRunning: true,
  logsAfter: 0,
};

// mark initial view for CSS targeting
document.body.classList.add("view-library");

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
  if (!bytes && bytes !== 0) return "-";
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

function fmtDate(s) {
  if (!s) return "-";
  try {
    return new Date(s).toLocaleString("da-DK");
  } catch {
    return s;
  }
}

function renderStats() {
  els.photoCount.textContent = state.items.length;
  els.favoriteCount.textContent = state.items.filter(i => i.favorite).length;
  els.selectedCount.textContent = state.selectedId ? "1" : "0";
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
  els.detailDate.textContent = fmtDate(item.captured_at || item.modified_fs);
  els.detailSize.textContent = fmtBytes(item.file_size);
  els.detailDims.textContent = fmtDims(item.width, item.height);
  els.detailCamera.textContent = [item.camera_make, item.camera_model].filter(Boolean).join(" ") || "-";
  els.detailLens.textContent = item.lens_model || "-";
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

  const aiPills = (item.ai_tags || []).slice(0, 3).map(t => `<span class="pill">${t}</span>`).join("");
  const favPill = item.favorite ? `<span class="pill fav">Favorit</span>` : "";
  const vidPill = item.is_video ? `<span class="pill">Video</span>` : "";
  const sizeLabel = getSizeLabel(item.width, item.height);

  return `
    ${thumb}
    <div class="card-body">
      <h4 class="card-title">${item.filename || "Ukendt"}</h4>
      <div class="card-meta">
        <span>${fmtDate(item.captured_at || item.modified_fs)}</span>
        <span>${fmtBytes(item.file_size)}</span>
        <span>${sizeLabel}</span>
      </div>
      <div class="pills">${aiPills}${vidPill}${favPill}</div>
    </div>
  `;
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
  // Default views (library, mapper, etc.)
  els.grid.innerHTML = "";
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

function appendCard(item) {
  const card = document.createElement("article");
  card.className = "photo-card" + (state.selectedId === item.id ? " active" : "");
  card.innerHTML = cardHTML(item);
  card.addEventListener("click", () => {
    state.selectedId = item.id;
    renderGrid();
    setDetail(item);
  });
  // double-click opens viewer
  card.addEventListener("dblclick", () => {
    const idx = state.items.findIndex(i => i.id === item.id);
    if (idx >= 0) openViewer(idx);
  });
  els.grid.appendChild(card);
}

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
    state.view = "library";
    state.folder = folder === "(root)" ? "" : folder;
    document.querySelectorAll(".nav-item").forEach(btn => btn.classList.remove("active"));
    loadPhotos();
  });
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
      // Browsers cannot render HEIC/HEIF. Use thumbnail as preview.
      const ext = (it.ext || '').toLowerCase();
      const src = (ext === '.heic' || ext === '.heif') && it.thumb_url ? it.thumb_url : it.original_url;
      els.viewerImg.src = src;
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
      const ext = (it.ext || '').toLowerCase();
      els.viewerImg.src = (ext === '.heic' || ext === '.heif') && it.thumb_url ? it.thumb_url : it.original_url;
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

// --- Drag & Drop Upload ---
async function uploadFiles(fileList) {
  const files = Array.from(fileList || []).filter(f => !!f && f.name);
  if (!files.length) return;
  const fd = new FormData();
  for (const f of files) fd.append('files', f, f.name);
  try {
    showStatus('Uploader billeder...', 'ok');
    const res = await fetch('/api/upload', { method: 'POST', body: fd });
    const data = await res.json().catch(() => ({}));
    if (!res.ok || data.ok === false) {
      showStatus(data.error || 'Upload fejlede', 'err');
      return;
    }
    const saved = (data.saved || []).length;
    const errs = (data.errors || []).length;
    showStatus(`Upload fuldført: ${saved} fil(er)${errs?`, fejl: ${errs}`:''}`, errs? 'err':'ok');
    await loadPhotos();
  } catch (e) {
    console.error(e);
    showStatus('Upload fejlede', 'err');
  }
}

window.addEventListener('dragover', (e) => {
  if (e.dataTransfer && e.dataTransfer.types && e.dataTransfer.types.includes('Files')) {
    e.preventDefault();
  }
});
window.addEventListener('drop', (e) => {
  if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length) {
    e.preventDefault();
    uploadFiles(e.dataTransfer.files);
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
  document.body.classList.toggle("view-library", view === "library");
  if (view === "settings") {
    // show logs panel, do not load photos
    renderGrid();
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
updateScanButton();
els.toggleRawBtn.addEventListener("click", () => {
  const hidden = els.rawMeta.classList.toggle("hidden");
  els.toggleRawBtn.textContent = hidden ? "Vis rå metadata (JSON)" : "Skjul rå metadata (JSON)";
});
els.favoriteBtn.addEventListener("click", toggleFavorite);

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
  });
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
function appendLogLine(text) {
  if (els.logsBox) {
    els.logsBox.textContent += (els.logsBox.textContent ? "\n" : "") + text;
    const lines = els.logsBox.textContent.split("\n");
    if (lines.length > 400) {
      els.logsBox.textContent = lines.slice(-400).join("\n");
    }
    els.logsBox.scrollTop = els.logsBox.scrollHeight;
  }
  if (els.mainLogsBox) {
    els.mainLogsBox.textContent += (els.mainLogsBox.textContent ? "\n" : "") + text;
    const lines2 = els.mainLogsBox.textContent.split("\n");
    if (lines2.length > 1200) {
      els.mainLogsBox.textContent = lines2.slice(-1200).join("\n");
    }
    els.mainLogsBox.scrollTop = els.mainLogsBox.scrollHeight;
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
        const msg = `[${it.t}] ${label}${extra}`;
        appendLogLine(msg);
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
  if (els.logsBox) els.logsBox.textContent = "";
  if (els.mainLogsBox) els.mainLogsBox.textContent = "";
}

els.logsStart && els.logsStart.addEventListener('click', () => {
  if (state.logsRunning) stopLogs(); else startLogs();
});
els.logsClear && els.logsClear.addEventListener('click', clearLogs);
els.mainLogsClear && els.mainLogsClear.addEventListener('click', clearLogs);
