(() => {
  'use strict';

  if (typeof appendPeopleInChunks !== 'function') return;

  const bulkPeople = {
    active: false,
    busy: false,
    selected: new Set(),
  };

  function injectBulkStyles() {
    if (document.getElementById('peopleBulkStyles')) return;
    const style = document.createElement('style');
    style.id = 'peopleBulkStyles';
    style.textContent = `
      body.people-bulk-select-mode .photo-card[data-person-id] { cursor: pointer; }
      body.people-bulk-select-mode .photo-card[data-person-id] .actions { visibility: hidden; pointer-events: none; }
      body.people-bulk-select-mode .photo-card[data-person-id="unknown"] { opacity: .58; cursor: not-allowed; }
      .photo-select-badge.people-bulk-badge {
        opacity: 1 !important;
        transform: scale(1) !important;
        z-index: 8;
        pointer-events: none;
      }
      .photo-card.people-bulk-selectable:not(.selected) .photo-select-badge.people-bulk-badge {
        background: rgba(12, 20, 28, .52);
        border-color: rgba(255, 255, 255, .85);
        color: transparent;
      }
      #peopleBulkHideBtn:disabled { opacity: .5; cursor: default; }
    `;
    document.head.appendChild(style);
  }

  function canManagePeople() {
    try {
      const role = String((state.currentUser && state.currentUser.role) || 'user').toLowerCase();
      return role === 'admin' || role === 'manager';
    } catch (_) {
      return false;
    }
  }

  function isPeopleList() {
    return state.view === 'personer' && state.personView && state.personView.mode === 'list';
  }

  function selectablePersonId(value) {
    const raw = String(value == null ? '' : value).trim();
    if (!raw || raw === 'unknown') return null;
    const id = Number(raw);
    return Number.isInteger(id) && id > 0 ? id : null;
  }

  function syncPersonCardSelection(card) {
    if (!card) return;
    const pid = selectablePersonId(card.getAttribute('data-person-id'));
    const selected = pid !== null && bulkPeople.selected.has(pid);
    card.classList.toggle('selected', selected);
    card.classList.toggle('people-bulk-selectable', bulkPeople.active && pid !== null);

    let badge = card.querySelector('.people-bulk-badge');
    if (!bulkPeople.active || pid === null) {
      if (badge) badge.remove();
      return;
    }

    if (!badge) {
      badge = document.createElement('span');
      badge.className = 'photo-select-badge people-bulk-badge';
      const thumb = card.querySelector('.card-thumb');
      if (thumb) thumb.appendChild(badge);
    }
    if (badge) badge.textContent = selected ? '✓' : '';
  }

  function syncAllPersonCards() {
    if (!els.grid) return;
    els.grid.querySelectorAll('.photo-card[data-person-id]').forEach(syncPersonCardSelection);
  }

  function updateBulkButtons() {
    const selectBtn = document.getElementById('peopleBulkSelectBtn');
    const hideBtn = document.getElementById('peopleBulkHideBtn');
    const cancelBtn = document.getElementById('peopleBulkCancelBtn');
    const matchBtn = document.getElementById('peopleMatchScanBtn');
    const count = bulkPeople.selected.size;

    if (selectBtn) selectBtn.style.display = bulkPeople.active ? 'none' : '';
    if (hideBtn) {
      hideBtn.style.display = bulkPeople.active ? '' : 'none';
      hideBtn.disabled = bulkPeople.busy || count === 0;
      hideBtn.textContent = bulkPeople.busy ? 'Skjuler…' : `Skjul valgte (${count})`;
    }
    if (cancelBtn) {
      cancelBtn.style.display = bulkPeople.active ? '' : 'none';
      cancelBtn.disabled = bulkPeople.busy;
    }
    if (matchBtn) matchBtn.style.display = bulkPeople.active ? 'none' : '';
  }

  function finishBulkSelect() {
    bulkPeople.active = false;
    bulkPeople.busy = false;
    bulkPeople.selected.clear();
    document.body.classList.remove('people-bulk-select-mode');
    syncAllPersonCards();
    updateBulkButtons();
  }

  function startBulkSelect() {
    if (!isPeopleList() || !canManagePeople()) return;
    bulkPeople.active = true;
    bulkPeople.busy = false;
    bulkPeople.selected.clear();
    document.body.classList.add('people-bulk-select-mode');
    syncAllPersonCards();
    updateBulkButtons();
  }

  function togglePersonSelection(card, personId) {
    const pid = selectablePersonId(personId);
    if (!bulkPeople.active || pid === null) return;
    if (bulkPeople.selected.has(pid)) bulkPeople.selected.delete(pid);
    else bulkPeople.selected.add(pid);
    syncPersonCardSelection(card);
    updateBulkButtons();
  }

  async function hideSelectedPeople() {
    if (bulkPeople.busy || !bulkPeople.selected.size) return;
    const ids = Array.from(bulkPeople.selected);
    const count = ids.length;
    if (!confirm(`Skjul ${count} valgte ${count === 1 ? 'person' : 'personer'}?`)) return;

    bulkPeople.busy = true;
    updateBulkButtons();
    try {
      const response = await fetch('/api/people/hide-bulk', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ids, hidden: true }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok || !data || !data.ok) {
        showStatus((data && data.error) || 'Kunne ikke skjule de valgte personer', 'err');
        bulkPeople.busy = false;
        updateBulkButtons();
        return;
      }

      const updated = Number(data.updated || 0);
      finishBulkSelect();
      showStatus(`${updated} ${updated === 1 ? 'person er' : 'personer er'} skjult`, 'ok');
      await loadPeople(false);
    } catch (_) {
      bulkPeople.busy = false;
      updateBulkButtons();
      showStatus('Kunne ikke skjule de valgte personer', 'err');
    }
  }

  function syncBulkControls() {
    injectBulkStyles();
    const shouldShow = isPeopleList() && canManagePeople();
    const actions = document.getElementById('peopleHeaderActions');

    if (!shouldShow) {
      if (bulkPeople.active || bulkPeople.selected.size) finishBulkSelect();
      ['peopleBulkSelectBtn', 'peopleBulkHideBtn', 'peopleBulkCancelBtn'].forEach((id) => {
        const node = document.getElementById(id);
        if (node) node.style.display = 'none';
      });
      return;
    }
    if (!actions) return;

    let selectBtn = document.getElementById('peopleBulkSelectBtn');
    if (!selectBtn) {
      selectBtn = document.createElement('button');
      selectBtn.id = 'peopleBulkSelectBtn';
      selectBtn.className = 'btn';
      selectBtn.type = 'button';
      selectBtn.textContent = 'Vælg';
      selectBtn.addEventListener('click', startBulkSelect);
      actions.appendChild(selectBtn);
    }

    let hideBtn = document.getElementById('peopleBulkHideBtn');
    if (!hideBtn) {
      hideBtn = document.createElement('button');
      hideBtn.id = 'peopleBulkHideBtn';
      hideBtn.className = 'btn danger';
      hideBtn.type = 'button';
      hideBtn.addEventListener('click', hideSelectedPeople);
      actions.appendChild(hideBtn);
    }

    let cancelBtn = document.getElementById('peopleBulkCancelBtn');
    if (!cancelBtn) {
      cancelBtn = document.createElement('button');
      cancelBtn.id = 'peopleBulkCancelBtn';
      cancelBtn.className = 'btn ghost';
      cancelBtn.type = 'button';
      cancelBtn.textContent = 'Annuller';
      cancelBtn.addEventListener('click', finishBulkSelect);
      actions.appendChild(cancelBtn);
    }

    updateBulkButtons();
    syncAllPersonCards();
  }

  // Keep the People header controls in sync as FjordLens switches views and
  // toggles between the people list and a person's photos.
  if (typeof renderGrid === 'function') {
    const originalRenderGrid = renderGrid;
    renderGrid = function renderGridWithPeopleBulk(...args) {
      const result = originalRenderGrid.apply(this, args);
      setTimeout(syncBulkControls, 0);
      return result;
    };
  }

  // People thumbnails used to be fetched strictly one-by-one. That makes the
  // section feel slow even when the person list itself is already available.
  // Keep a small concurrency cap so the UI fills quickly without hammering the server.
  appendPeopleInChunks = function appendPeopleInChunksFast(people, chunkSize = 48) {
    if (!els.grid) return;

    let index = 0;
    const pendingImgs = [];
    let activeLoads = 0;
    let activePolls = 0;
    const MAX_LOADS = 4;
    const MAX_POLLS = 4;

    function pollFaceReady(img) {
      const attrFid = String((img && img.getAttribute('data-face-id')) || '').trim();
      const candidate = String(
        (img && (img.currentSrc || img.src)) || img.getAttribute('data-src') || ''
      );
      const match = candidate.match(/\/api\/face-thumb\/(\d+)/);
      const fid = attrFid || (match && match[1]) || '';
      if (!fid) return;

      let tries = 0;
      const maxTries = 120;

      const start = () => {
        if (!document.body.contains(img) || state.view !== 'personer') return;
        if (activePolls >= MAX_POLLS) {
          setTimeout(start, 140);
          return;
        }
        activePolls += 1;
        tick();
      };

      const finish = () => {
        activePolls = Math.max(0, activePolls - 1);
      };

      const tick = async () => {
        tries += 1;
        try {
          const response = await fetch(`/api/face-thumb/status/${fid}`);
          const data = await response.json();
          if (response.ok && data && data.ok && data.ready && data.url) {
            img.src = data.url;
            const thumb = img.closest('.card-thumb');
            if (thumb) thumb.classList.remove('mapper-ghost-thumb');
            finish();
            return;
          }
        } catch (_) {}

        if (
          tries < maxTries &&
          document.body.contains(img) &&
          state.view === 'personer'
        ) {
          const delay = Math.min(2000, 180 + tries * 120);
          setTimeout(tick, delay);
        } else {
          finish();
        }
      };

      setTimeout(start, 100);
    }

    function pumpImages() {
      while (activeLoads < MAX_LOADS && pendingImgs.length) {
        const img = pendingImgs.shift();
        if (!img || !document.body.contains(img)) continue;

        const src = img.getAttribute('data-src');
        if (!src) continue;

        activeLoads += 1;
        let settled = false;

        const done = (ok) => {
          if (settled) return;
          settled = true;
          img.removeEventListener('load', onload);
          img.removeEventListener('error', onerror);
          img.removeEventListener('abort', onerror);
          activeLoads = Math.max(0, activeLoads - 1);

          if (ok) {
            img.removeAttribute('data-src');
            const thumb = img.closest('.card-thumb');
            if (thumb) thumb.classList.remove('mapper-ghost-thumb');
            pollFaceReady(img);
          } else {
            const retries = Number(img.getAttribute('data-retries') || '0');
            if (retries < 3 && document.body.contains(img)) {
              img.setAttribute('data-retries', String(retries + 1));
              setTimeout(() => {
                pendingImgs.push(img);
                pumpImages();
              }, 400);
            }
          }
          pumpImages();
        };

        const onload = () => done(true);
        const onerror = () => done(false);
        img.addEventListener('load', onload, { once: true });
        img.addEventListener('error', onerror, { once: true });
        img.addEventListener('abort', onerror, { once: true });

        try {
          img.style.width = '100%';
          img.style.height = '100%';
          img.style.objectFit = 'cover';
          img.style.objectPosition = 'center center';
          img.style.display = 'block';
          img.src = src;
        } catch (_) {
          done(false);
        }
      }
    }

    function step() {
      if (!els.grid || state.view !== 'personer') return;

      const end = Math.min(index + chunkSize, people.length);
      const fragment = document.createDocumentFragment();
      const newImgs = [];

      for (; index < end; index += 1) {
        const p = people[index];
        const card = document.createElement('article');
        card.className = 'photo-card';
        card.setAttribute('data-person-id', String(p.id));

        const faceMatch = String(p.thumb_url || '').match(/\/api\/face-thumb\/(\d+)/);
        const faceAttr = faceMatch ? ` data-face-id="${faceMatch[1]}"` : '';
        const imgHtml = p.thumb_url
          ? `<img data-src="${p.thumb_url}"${faceAttr} alt="${escapeHtml(p.name || '')}" loading="lazy" decoding="async" style="width:100%;height:100%;object-fit:cover;object-position:center center;display:block;">`
          : '<div class="card-thumb placeholder">🙂</div>';

        card.innerHTML = `
          <div class="card-thumb${p.thumb_url ? ' mapper-ghost-thumb' : ''}">${imgHtml}</div>
          <div class="card-body">${personCardBodyHtml(p)}</div>
        `;
        card.querySelectorAll('img').forEach((el) => {
          el.setAttribute('draggable', 'false');
          if (el.hasAttribute('data-src')) newImgs.push(el);
        });

        card.addEventListener('click', (event) => {
          if (bulkPeople.active) {
            event.preventDefault();
            event.stopPropagation();
            if (p.id !== 'unknown') togglePersonSelection(card, p.id);
            return;
          }
          if (event.target && event.target.closest('[data-act]')) return;
          if (p.id === 'unknown') loadPersonPhotos('unknown', tr('person_unknown'));
          else loadPersonPhotos(p.id, p.name);
        });

        wirePersonCardBodyEvents(card, p);
        syncPersonCardSelection(card);
        fragment.appendChild(card);
      }

      els.grid.appendChild(fragment);
      pendingImgs.push(...newImgs);
      pumpImages();

      if (index < people.length) {
        (window.requestIdleCallback || window.requestAnimationFrame)(step);
      } else {
        syncBulkControls();
      }
    }

    step();
  };

  injectBulkStyles();
  setTimeout(syncBulkControls, 0);
})();