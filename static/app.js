const els = {
  grid: document.getElementById("galleryGrid"),
  search: document.getElementById("searchInput"),
  sort: document.getElementById("sortSelect"),
  scanBtn: document.getElementById("scanBtn"),
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
  detailAiTags: document.getElementById("detailAiTags"),
  rawMeta: document.getElementById("rawMeta"),
  toggleRawBtn: document.getElementById("toggleRawBtn"),
  favoriteBtn: document.getElementById("favoriteBtn"),
  // viewer
  viewer: document.getElementById("viewer"),
  viewerImg: document.getElementById("viewerImg"),
  viewerPrev: document.getElementById("viewerPrev"),
  viewerNext: document.getElementById("viewerNext"),
  viewerClose: document.getElementById("viewerClose"),
};

const NAV_LABELS = {
  library: ["Bibliotek", "Scan din fotomappe og søg/sortér i metadata"],
  favorites: ["Favoritter", "Markerede billeder"],
  steder: ["Steder", "Billeder med GPS/placeringsdata"],
  kameraer: ["Kameraer", "Filtreret på billeder med kameradata"],
  mapper: ["Mapper", "Grupperet efter kilde-mappe"],
  personer: ["Personer", "Klar til ansigtsgenkendelse (kommer med ONNX face-service)"],
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
};

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
    : `<div class="card-thumb placeholder">Ingen thumbnail</div>`;

  const aiPills = (item.ai_tags || []).slice(0, 3).map(t => `<span class="pill">${t}</span>`).join("");
  const favPill = item.favorite ? `<span class="pill fav">Favorit</span>` : "";
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
      <div class="pills">${aiPills}${favPill}</div>
    </div>
  `;
}

function renderGrid() {
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
  card.className = "photo-card";
  const cells = previews.map(p => p.thumb_url ? `<img src="${p.thumb_url}" alt="">` : "").join("");
  card.innerHTML = `
    <div class="card-thumb folder-mosaic">
      ${cells}
    </div>
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
  els.viewerImg.src = it.original_url;
  els.viewer.classList.remove("hidden");
}
function closeViewer() {
  els.viewer.classList.add("hidden");
  els.viewerImg.removeAttribute("src");
}
function nextViewer(step=1) {
  if (state.selectedIndex < 0) return;
  const n = state.items.length;
  state.selectedIndex = (state.selectedIndex + step + n) % n;
  const it = state.items[state.selectedIndex];
  if (it && it.original_url) els.viewerImg.src = it.original_url;
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

function updateScanButton() {
  if (state.scanning) {
    els.scanBtn.textContent = "Stop scan";
  } else {
    els.scanBtn.textContent = "Scan bibliotek";
  }
}

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
  loadPhotos();
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
updateScanButton();
els.toggleRawBtn.addEventListener("click", () => {
  const hidden = els.rawMeta.classList.toggle("hidden");
  els.toggleRawBtn.textContent = hidden ? "Vis rå metadata (JSON)" : "Skjul rå metadata (JSON)";
});
els.favoriteBtn.addEventListener("click", toggleFavorite);

document.querySelectorAll(".nav-item").forEach(btn => {
  btn.addEventListener("click", () => setView(btn.dataset.view));
});

// viewer events
els.viewerClose && els.viewerClose.addEventListener("click", closeViewer);
els.viewerPrev && els.viewerPrev.addEventListener("click", () => nextViewer(-1));
els.viewerNext && els.viewerNext.addEventListener("click", () => nextViewer(1));
window.addEventListener("keydown", (e) => {
  if (els.viewer.classList.contains("hidden")) return;
  if (e.key === "Escape") closeViewer();
  if (e.key === "ArrowLeft") nextViewer(-1);
  if (e.key === "ArrowRight") nextViewer(1);
});

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
});
