// Moment editing uses a revision to avoid overwriting another tab or a new scan.
function momentEvidenceHtml(moment) {
  const info = moment.evidence;
  if (!info?.reasons?.length) return '';
  const chapters = info.chapters?.length ? `<ol>${info.chapters.map(c => `<li>${escapeHtml(c.place)} · ${escapeHtml(c.start_date)}${c.end_date !== c.start_date ? ' – ' + escapeHtml(c.end_date) : ''} · ${Number(c.photo_count)} billeder</li>`).join('')}</ol>` : '';
  const attribution = info.attraction ? '<p><a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">Steddata © OpenStreetMap-bidragydere</a></p>' : '';
  return `<details class="moment-evidence"><summary>Hvorfor dette moment?${info.confidence === 'low' ? ' · Tjek dato og sted' : ''}</summary><p>${escapeHtml(info.reasons.join(' '))}</p><p>${escapeHtml(info.date_basis || '')}</p>${chapters}${attribution}</details>`;
}

async function momentRequest(url, method = 'GET', body) {
  const response = await fetch(url, {
    method, headers: body ? { 'Content-Type': 'application/json' } : {},
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await response.json();
  if (!response.ok || !data.ok) throw new Error(data.error || 'Handlingen kunne ikke gennemføres.');
  return data;
}

function momentDialog(title) {
  const dialog = document.createElement('dialog');
  dialog.className = 'moment-editor';
  dialog.setAttribute('aria-label', title);
  dialog.innerHTML = `<header><h2>${escapeHtml(title)}</h2><button type="button" class="btn ghost" data-close>Luk</button></header><div data-body></div><p role="status" aria-live="polite" data-status></p>`;
  document.body.append(dialog);
  dialog.querySelector('[data-close]').onclick = () => dialog.close();
  dialog.addEventListener('close', () => dialog.remove(), { once: true });
  dialog.showModal();
  return dialog;
}

async function editMoment(id) {
  const dialog = momentDialog('Rediger moment');
  const body = dialog.querySelector('[data-body]');
  const status = dialog.querySelector('[data-status]');
  status.textContent = 'Henter billeder…';
  try {
    const { item } = await momentRequest(`/api/moments/${id}/edit-data`);
    if (!dialog.isConnected) return;
    status.textContent = '';
    const photos = new Map(item.photos.map(p => [p.id, p]));
    const selected = new Set(item.photo_ids);
    const others = [...(state.momentsSuggested || []), ...(state.momentsSaved || [])]
      .filter(m => m.id !== id && m.kind !== 'year_review');
    body.innerHTML = `
      <div class="moment-editor-fields">
        <label>Titel<input data-title maxlength="240" value="${escapeHtml(item.title || '')}"></label>
        <label>Fra dato<input data-start type="date" value="${escapeHtml(item.start_date || '')}"></label>
        <label>Til dato<input data-end type="date" value="${escapeHtml(item.end_date || '')}"></label>
      </div>
      <p class="mini-label">Datoerne viser perioden i billederne. Du kan rette dem og tilføje eller fravælge billeder. Dine rettelser bevares ved nye scanninger.</p>
      <div class="moment-editor-actions">
        <button type="button" class="btn small" data-range>Vælg inden for datoer</button>
        <button type="button" class="btn small ghost" data-all>Vælg alle viste</button>
        <button type="button" class="btn small ghost" data-none>Fravælg alle</button>
      </div>
      <details><summary>Find flere billeder i biblioteket</summary>
        <label>Sted eller land (valgfrit)<input data-place placeholder="Fx Berlin eller Tyskland"></label>
        <button type="button" class="btn small" data-search>Søg i datointervallet</button>
        <button type="button" class="btn small ghost" data-more hidden>Hent flere</button>
        <p class="mini-label">Søger i gemte stednavne. Nye resultater tilføjes nedenfor, så du selv kan vælge dem.</p>
      </details>
      <p data-count aria-live="polite"></p>
      <div class="moment-editor-photos" data-photos></div>
      <footer class="moment-editor-actions">
        <button type="button" class="btn primary" data-save>Gem ændringer</button>
        ${item.kind !== 'year_review' ? '<button type="button" class="btn" data-split>Flyt valgte til nyt moment</button>' : ''}
      </footer>
      ${item.kind !== 'year_review' && others.length ? `<details><summary>Saml med et andet moment</summary>
        <label>Moment<select data-other>${others.map(m => `<option value="${m.id}">${escapeHtml(m.title)} · ${escapeHtml(_momentDateRangeLabel(m))}</option>`).join('')}</select></label>
        <p class="mini-label">Alle billeder fra de to gemte momenter samles. Gem eventuelle ændringer ovenfor først.</p>
        <button type="button" class="btn" data-merge>Saml momenter</button></details>` : ''}
      <p class="mini-label">Ved opdeling flyttes de valgte billeder til et nyt moment, mens resten bliver her. De to perioder beregnes fra billederne. Gem eventuelle titelændringer først.</p>`;
    const start = body.querySelector('[data-start]');
    const end = body.querySelector('[data-end]');
    function renderPhotos() {
      body.querySelector('[data-count]').textContent = `${selected.size} valgt · ${photos.size} billeder vist`;
      body.querySelector('[data-photos]').innerHTML = [...photos.values()].map(p => `
        <label class="moment-editor-photo">
          <input type="checkbox" value="${p.id}" ${selected.has(p.id) ? 'checked' : ''}>
          ${p.thumb_url ? `<img src="${escapeHtml(p.thumb_url)}" alt="" loading="lazy">` : '<span class="moment-photo-placeholder">Billede</span>'}
          <span>${escapeHtml((p.date || '').replace('T', ' '))}<br>${escapeHtml(p.place || p.filename || 'Ukendt sted')}</span>
        </label>`).join('');
    }
    body.querySelector('[data-photos]').addEventListener('change', event => {
      const input = event.target;
      if (input.type !== 'checkbox') return;
      input.checked ? selected.add(Number(input.value)) : selected.delete(Number(input.value));
      body.querySelector('[data-count]').textContent = `${selected.size} valgt · ${photos.size} billeder vist`;
    });
    body.querySelector('[data-none]').onclick = () => { selected.clear(); renderPhotos(); };
    body.querySelector('[data-all]').onclick = () => { photos.forEach(p => selected.add(p.id)); renderPhotos(); };
    body.querySelector('[data-range]').onclick = () => {
      selected.clear();
      photos.forEach(p => { if (p.date && p.date.slice(0, 10) >= start.value && p.date.slice(0, 10) <= end.value) selected.add(p.id); });
      renderPhotos();
    };
    let offset = 0;
    let searchKey = '';
    async function search(reset) {
      if (!start.value || !end.value || start.value > end.value) throw new Error('Angiv et gyldigt datointerval.');
      const key = `${start.value}|${end.value}|${body.querySelector('[data-place]').value}`;
      if (reset || key !== searchKey) offset = 0;
      searchKey = key;
      const query = new URLSearchParams({ start_date: start.value, end_date: end.value, place: body.querySelector('[data-place]').value, offset });
      const result = await momentRequest(`/api/moments/photo-search?${query}`);
      result.photos.forEach(p => photos.set(p.id, p));
      offset += 200;
      body.querySelector('[data-more]').hidden = !result.has_more;
      renderPhotos();
      status.textContent = `${result.photos.length} søgeresultater hentet. Vælg de billeder, du vil tilføje.`;
    }
    async function run(action, close = false) {
      const controls = [...body.querySelectorAll('button, input, select')];
      controls.forEach(b => { b.disabled = true; });
      status.textContent = 'Arbejder…';
      try {
        await action();
        if (close) { dialog.close(); await loadMoments(); }
      } catch (error) {
        status.textContent = error.message;
      } finally {
        controls.forEach(b => { b.disabled = false; });
      }
    }
    body.querySelector('[data-search]').onclick = () => run(() => search(true));
    body.querySelector('[data-more]').onclick = () => run(() => search(false));
    body.querySelector('[data-save]').onclick = () => run(() => momentRequest(`/api/moments/${id}`, 'PATCH', {
      revision: item.revision, title: body.querySelector('[data-title]').value,
      start_date: start.value, end_date: end.value, photo_ids: [...selected],
    }), true);
    const split = body.querySelector('[data-split]');
    if (split) split.onclick = () => run(() => momentRequest(`/api/moments/${id}/split`, 'POST', {
      revision: item.revision, photo_ids: [...selected],
    }), true);
    const merge = body.querySelector('[data-merge]');
    if (merge) merge.onclick = () => run(() => {
      const other = others.find(m => m.id === Number(body.querySelector('[data-other]').value));
      return momentRequest(`/api/moments/${id}/merge`, 'POST', { revision: item.revision, other_id: other.id, other_revision: other.revision });
    }, true);
    renderPhotos();
  } catch (error) { status.textContent = error.message; }
}

async function editMomentHome() {
  const dialog = momentDialog('Hjemområde');
  const body = dialog.querySelector('[data-body]');
  const status = dialog.querySelector('[data-status]');
  try {
    const data = await momentRequest('/api/moments/settings');
    if (!dialog.isConnected) return;
    body.innerHTML = `<p>Automatisk hjemområde findes ud fra besøg på forskellige dage over mindst 45 dage. Du kan vælge et fast hjemområde, hvis biblioteket ikke har nok historik.</p>
      <label>Hjemområde<input data-home list="moment-home-places" value="${escapeHtml(data.home?.name || '')}" placeholder="Automatisk, når feltet er tomt"></label>
      <datalist id="moment-home-places">${(data.places || []).map(p => `<option value="${escapeHtml(p.name)}"></option>`).join('')}</datalist>
      <p class="mini-label">Vælg helst et sted fra listen. Med GPS bruges en radius på 40 km. Det faste hjemområde gælder biblioteket og kan ændres af en administrator.</p>
      <button class="btn primary" type="button" data-save>Gem hjemområde</button>`;
    body.querySelector('[data-save]').onclick = async () => {
      const button = body.querySelector('[data-save]');
      button.disabled = true;
      try {
        const name = body.querySelector('[data-home]').value.trim();
        const known = (data.places || []).find(p => p.name === name);
        await momentRequest('/api/moments/settings', 'PUT', { home: name ? known || { name } : null });
        dialog.close();
        showStatus('Hjemområde gemt. Brug Find nye momenter for at opdatere forslagene.', 'ok');
      } catch (error) { status.textContent = error.message; }
      finally { button.disabled = false; }
    };
  } catch (error) { status.textContent = error.message; }
}
