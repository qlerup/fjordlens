(() => {
  'use strict';

  if (typeof loadPeople !== 'function' || typeof renderGrid !== 'function') return;

  const STORAGE_PREFIX = 'fjordlens:people-list:v1:';
  const FRESH_MS = 60 * 1000;
  const MAX_STALE_MS = 30 * 60 * 1000;
  const inflight = new Map();

  function currentKey() {
    return state.showHiddenPeople ? 'hidden:1' : 'hidden:0';
  }

  function userScope() {
    try {
      const user = state.currentUser || {};
      return String(user.id || user.username || user.name || 'current');
    } catch (_) {
      return 'current';
    }
  }

  function storageKey(key) {
    return `${STORAGE_PREFIX}${userScope()}:${key}`;
  }

  function readStored(key) {
    try {
      const raw = sessionStorage.getItem(storageKey(key));
      if (!raw) return null;
      const parsed = JSON.parse(raw);
      if (!parsed || !Array.isArray(parsed.items)) return null;
      const ts = Number(parsed.ts || 0);
      if (!ts || Date.now() - ts > MAX_STALE_MS) {
        sessionStorage.removeItem(storageKey(key));
        return null;
      }
      return { key, items: parsed.items, ts };
    } catch (_) {
      return null;
    }
  }

  function writeStored(key, items, ts = Date.now()) {
    try {
      sessionStorage.setItem(
        storageKey(key),
        JSON.stringify({ ts, items: Array.isArray(items) ? items : [] })
      );
    } catch (_) {}
  }

  function memoryCache(key) {
    const cache = state._peopleCache;
    if (cache && cache.key === key && Array.isArray(cache.items)) {
      return { key, items: cache.items, ts: Number(cache.ts || 0) };
    }
    return null;
  }

  function bestCache(key) {
    return memoryCache(key) || readStored(key);
  }

  function setPeopleHeadings() {
    try {
      const labels = typeof navLabels === 'function' ? navLabels() : {};
      const pair = labels['personer'] || ['Personer', ''];
      if (els.viewTitle) els.viewTitle.textContent = pair[0];
      if (els.viewSubtitle) els.viewSubtitle.textContent = pair[1];
    } catch (_) {}
  }

  function removeSkeletons() {
    try {
      document.querySelectorAll('.people-fast-skeleton').forEach((node) => node.remove());
    } catch (_) {}
  }

  function showSkeletons() {
    if (!els.grid || state.view !== 'personer') return;
    setPeopleHeadings();
    state.people = [];
    renderGrid();
    if (!els.grid || state.view !== 'personer') return;

    if (!document.getElementById('peopleFastCacheStyles')) {
      const style = document.createElement('style');
      style.id = 'peopleFastCacheStyles';
      style.textContent = `
        .people-fast-skeleton { pointer-events:none; overflow:hidden; }
        .people-fast-skeleton .card-thumb,
        .people-fast-skeleton .people-fast-skeleton-line {
          background: linear-gradient(100deg, rgba(255,255,255,.055) 20%, rgba(255,255,255,.12) 38%, rgba(255,255,255,.055) 56%);
          background-size: 220% 100%;
          animation: peopleFastShimmer 1.2s linear infinite;
        }
        .people-fast-skeleton-line { height:14px; border-radius:999px; margin:12px 14px 0; }
        .people-fast-skeleton-line.short { width:44%; margin-bottom:16px; opacity:.7; }
        @keyframes peopleFastShimmer { to { background-position-x: -220%; } }
      `;
      document.head.appendChild(style);
    }

    const frag = document.createDocumentFragment();
    for (let i = 0; i < 6; i += 1) {
      const card = document.createElement('article');
      card.className = 'photo-card people-fast-skeleton';
      card.innerHTML = `
        <div class="card-thumb"></div>
        <div class="card-body">
          <div class="people-fast-skeleton-line"></div>
          <div class="people-fast-skeleton-line short"></div>
        </div>
      `;
      frag.appendChild(card);
    }
    els.grid.innerHTML = '';
    els.grid.appendChild(frag);
    try { if (els.empty) els.empty.classList.add('hidden'); } catch (_) {}
  }

  function applyItems(key, items, ts = Date.now(), render = true) {
    const list = Array.isArray(items) ? items : [];
    state._peopleCache = { key, items: list.slice(), ts };
    writeStored(key, list, ts);

    if (!render || currentKey() !== key || state.view !== 'personer') return;
    if (!state.personView || state.personView.mode !== 'list') return;

    removeSkeletons();
    state.people = list;
    if (typeof reconcilePeopleGrid === 'function') {
      reconcilePeopleGrid(list);
    } else {
      renderGrid();
    }
  }

  function fetchPeople(key, { render = true } = {}) {
    if (inflight.has(key)) return inflight.get(key);

    const url = key === 'hidden:1' ? '/api/people?include_hidden=1' : '/api/people';
    const started = performance.now();
    const promise = fetch(url, { cache: 'no-store' })
      .then(async (response) => {
        const data = await response.json().catch(() => ({}));
        if (!response.ok || !data || data.ok === false) {
          throw new Error((data && data.error) || `HTTP ${response.status}`);
        }
        const items = Array.isArray(data.items) ? data.items : [];
        applyItems(key, items, Date.now(), render);
        try {
          const elapsed = Math.round(performance.now() - started);
          if (elapsed >= 750) console.debug(`[FjordLens] People API: ${elapsed} ms (${items.length} people)`);
        } catch (_) {}
        return items;
      })
      .catch((error) => {
        if (state.view === 'personer' && currentKey() === key && !bestCache(key)) {
          removeSkeletons();
          try { renderGrid(); } catch (_) {}
        }
        throw error;
      })
      .finally(() => {
        inflight.delete(key);
      });

    inflight.set(key, promise);
    return promise;
  }

  // Replace the blocking People loader with stale-while-revalidate behavior.
  // Normal navigation returns immediately; explicit refreshes after mutations
  // still await the server so hide/unhide/rename flows remain deterministic.
  loadPeople = async function loadPeopleInstant(useCache = true) {
    try { if (typeof closePersonRenameMenu === 'function') closePersonRenameMenu(); } catch (_) {}

    const key = currentKey();
    const cached = bestCache(key);

    if (useCache) {
      if (cached) {
        state.people = cached.items.slice();
        state._peopleCache = { key, items: cached.items.slice(), ts: cached.ts };
        setPeopleHeadings();
        renderGrid();
      } else {
        showSkeletons();
      }

      // Navigation must not wait for the expensive People endpoint. Refresh in
      // the background and reconcile cards when fresh data arrives.
      fetchPeople(key, { render: true }).catch(() => {});
      return;
    }

    // Forced reloads are used after mutations, where callers expect the fresh
    // list before continuing.
    await fetchPeople(key, { render: true });
  };

  // Persist list updates produced elsewhere in app.js (merge, matching, etc.).
  if (typeof reconcilePeopleGrid === 'function') {
    const originalReconcilePeopleGrid = reconcilePeopleGrid;
    reconcilePeopleGrid = function reconcilePeopleGridCached(newPeople) {
      const result = originalReconcilePeopleGrid.apply(this, arguments);
      try {
        const key = currentKey();
        const items = Array.isArray(newPeople) ? newPeople : [];
        writeStored(key, items, Date.now());
      } catch (_) {}
      return result;
    };
  }

  function prefetchPeople() {
    const key = 'hidden:0';
    const cached = bestCache(key);
    const age = cached ? Date.now() - Number(cached.ts || 0) : Infinity;

    if (cached && !memoryCache(key)) {
      state._peopleCache = { key, items: cached.items.slice(), ts: cached.ts };
    }
    if (age < FRESH_MS) return;

    fetchPeople(key, { render: false }).catch(() => {});
  }

  // Warm the normal (non-hidden) People list while the user is elsewhere in the
  // app. Hidden people are deliberately not prefetched.
  const warm = () => prefetchPeople();
  if (typeof window.requestIdleCallback === 'function') {
    window.requestIdleCallback(warm, { timeout: 1200 });
  } else {
    setTimeout(warm, 700);
  }
})();