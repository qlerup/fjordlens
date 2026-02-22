const els = {
  grid: document.getElementById("galleryGrid"),
  search: document.getElementById("searchInput"),
  sort: document.getElementById("sortSelect"),
  scanBtn: document.getElementById("scanBtn"),
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
};

const NAV_LABELS = {
  library: ["Bibliotek", "Scan din fotomappe og søg/sortér i metadata"],
  favorites: ["Favoritter", "Markerede billeder"],
  steder: ["Steder", "Billeder med GPS/placeringsdata"],
  kameraer: ["Kameraer", "Filtreret på billeder med kameradata"],
  personer: ["Personer", "Klar til ansigtsgenkendelse (kommer med ONNX face-service)"],
};

let state = {
  items: [],
  selectedId: null,
  view: "library",
  sort: "date_desc",
  q: "",
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
}

function cardHTML(item) {
  const thumb = item.thumb_url
    ? `<div class="card-thumb"><img loading="lazy" src="${item.thumb_url}" alt=""></div>`
    : `<div class="card-thumb placeholder">Ingen thumbnail</div>`;

  const aiPills = (item.ai_tags || []).slice(0, 3).map(t => `<span class="pill">${t}</span>`).join("");
  const favPill = item.favorite ? `<span class="pill fav">Favorit</span>` : "";

  return `
    ${thumb}
    <div class="card-body">
      <h4 class="card-title">${item.filename || "Ukendt"}</h4>
      <div class="card-meta">
        <span>${fmtDate(item.captured_at || item.modified_fs)}</span>
        <span>${fmtBytes(item.file_size)}</span>
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

  state.items.forEach(item => {
    const card = document.createElement("article");
    card.className = "photo-card" + (state.selectedId === item.id ? " active" : "");
    card.innerHTML = cardHTML(item);
    card.addEventListener("click", () => {
      state.selectedId = item.id;
      renderGrid();
      setDetail(item);
    });
    els.grid.appendChild(card);
  });

  if (!state.items.some(i => i.id === state.selectedId)) {
    state.selectedId = null;
    setDetail(null);
  }

  renderStats();
}

async function loadPhotos() {
  const qs = new URLSearchParams({
    q: state.q,
    view: state.view,
    sort: state.sort,
  });

  const res = await fetch(`/api/photos?${qs.toString()}`);
  const data = await res.json();
  state.items = data.items || [];

  const [title, subtitle] = NAV_LABELS[state.view] || ["FjordLens", ""];
  els.viewTitle.textContent = title;
  els.viewSubtitle.textContent = subtitle;

  renderGrid();
}

async function scanLibrary() {
  els.scanBtn.disabled = true;
  showStatus("Scanner bibliotek... det kan tage lidt tid første gang.", "ok");
  try {
    const res = await fetch("/api/scan", { method: "POST" });
    const data = await res.json();
    if (!res.ok || !data.ok) {
      showStatus(`Fejl: ${data.error || "Scan fejlede"}`, "err");
      return;
    }
    showStatus(`Scan færdig. Fundet: ${data.scanned}, opdateret: ${data.updated}, fejl: ${data.errors}.`, "ok");
    await loadPhotos();
  } catch (err) {
    showStatus(`Fejl under scan: ${err}`, "err");
  } finally {
    els.scanBtn.disabled = false;
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
els.toggleRawBtn.addEventListener("click", () => {
  const hidden = els.rawMeta.classList.toggle("hidden");
  els.toggleRawBtn.textContent = hidden ? "Vis rå metadata (JSON)" : "Skjul rå metadata (JSON)";
});
els.favoriteBtn.addEventListener("click", toggleFavorite);

document.querySelectorAll(".nav-item").forEach(btn => {
  btn.addEventListener("click", () => setView(btn.dataset.view));
});

// Initial load
loadPhotos().then(() => {
  showStatus("Klar. Tryk 'Scan bibliotek' for at indeksere dine billeder.", "ok");
});
