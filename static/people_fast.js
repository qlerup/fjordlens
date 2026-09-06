(() => {
  'use strict';

  if (typeof appendPeopleInChunks !== 'function') return;

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
          if (event.target && event.target.closest('[data-act]')) return;
          if (p.id === 'unknown') loadPersonPhotos('unknown', tr('person_unknown'));
          else loadPersonPhotos(p.id, p.name);
        });

        wirePersonCardBodyEvents(card, p);
        fragment.appendChild(card);
      }

      els.grid.appendChild(fragment);
      pendingImgs.push(...newImgs);
      pumpImages();

      if (index < people.length) {
        (window.requestIdleCallback || window.requestAnimationFrame)(step);
      }
    }

    step();
  };
})();