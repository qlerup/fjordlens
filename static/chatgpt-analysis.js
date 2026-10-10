(() => {
  const byId = id => document.getElementById(`chatgptTest${id}`);
  const open = document.getElementById('chatgptTestBtn');
  if (!open) return;
  const dialog = byId('Dialog'), form = byId('Form'), file = byId('Image');
  const model = byId('Model'), run = byId('Run'), preview = byId('Preview');
  const status = byId('Status'), error = byId('Error'), result = byId('Result');
  let running = false, loading = false, job = null, previewURL = null, timer = null, pollDeadline = 0;
  const setError = message => { error.textContent = message; error.classList.toggle('hidden', !message); };
  function controls() {
    file.disabled = running;
    model.disabled = running || loading || !model.options.length || !model.value;
    byId('Threshold').disabled = running;
    run.disabled = running || loading || !file.files.length || !model.value;
    run.textContent = running ? 'Analyserer …' : 'Analysér billede';
    form.setAttribute('aria-busy', String(running || loading));
  }
  async function api(path, options = {}) {
    const response = await fetch(`/api/ai/chatgpt/${path}`, {...options, cache: 'no-store',
      headers: {'X-ChatGPT-CSRF': open.dataset.csrf || ''}, signal: AbortSignal.timeout(45000)});
    let data;
    try { data = await response.json(); }
    catch (_) { throw new Error('Serveren kunne ikke svare. Genindlæs indstillingerne og prøv igen.'); }
    if (!response.ok || !data.ok) {
      const failure = new Error(data.error || 'Testen kunne ikke gennemføres.');
      failure.status = response.status; throw failure;
    }
    return data;
  }
  async function models() {
    loading = true; setError(''); controls();
    byId('ModelsRetry').classList.add('hidden');
    try {
      const data = await api('test-models');
      model.replaceChildren(...data.models.map(m => new Option(m.label, m.id, m.default, m.default)));
      if (!data.models.length) throw new Error('Kontoen har ingen tilgængelige modeller med billedinput.');
    } catch (err) {
      model.replaceChildren(new Option('Modeller kunne ikke hentes', ''));
      setError(err.message); byId('ModelsRetry').classList.remove('hidden');
    } finally { loading = false; controls(); }
  }
  function clearPreview() {
    if (previewURL) URL.revokeObjectURL(previewURL);
    previewURL = null; preview.removeAttribute('src'); preview.classList.add('hidden');
  }
  function display(data) {
    byId('Summary').textContent = data.result.summary;
    const sections = byId('Sections'); sections.replaceChildren();
    const names = {event: 'Begivenhed', people_context: 'Personer', relations: 'Samspil', scene: 'Omgivelser',
      activities: 'Handlinger', mood: 'Stemning', objects: 'Genstande', animals: 'Dyr', vehicles: 'Køretøjer',
      food_and_drink: 'Mad og drikke', clothing: 'Beklædning', sports: 'Sport', water_context: 'Vand og badning',
      celebrations: 'Fejringer', travel: 'Rejser', nature: 'Natur', indoor_context: 'Indendørs',
      outdoor_context: 'Udendørs', search_concepts: 'Søgebegreber', extra_concepts: 'Forslag til nye begreber'};
    function describe(entry) {
      const pieces = [entry.label || entry.type];
      if (entry.count != null) pieces.push(`antal: ${entry.count}`);
      if (entry.attributes?.length) pieces.push(entry.attributes.join(', '));
      if (entry.synonyms?.length) pieces.push(`synonymer: ${entry.synonyms.join(', ')}`);
      if (typeof entry.confidence === 'number') pieces.push(`sikkerhed: ${Math.round(entry.confidence * 100)} %`);
      if (entry.uncertainty) pieces.push(`usikkerhed: ${entry.uncertainty}`);
      return pieces.filter(Boolean).join(' · ');
    }
    for (const [key, label] of Object.entries(names)) {
      const value = data.result[key];
      if (Array.isArray(value) && !value.length) continue;
      if (key === 'event' && !value.type && !value.label) continue;
      const heading = document.createElement('h4'); heading.textContent = label; sections.append(heading);
      if (Array.isArray(value)) {
        const list = document.createElement('ul');
        for (const entry of value) { const li = document.createElement('li'); li.textContent = describe(entry); list.append(li); }
        sections.append(list);
      } else {
        const paragraph = document.createElement('p');
        if (key === 'people_context') {
          const count = n => n == null ? 'ukendt' : n;
          paragraph.textContent = `Personer: ${count(value.total)} · voksne: ${count(value.adults)} · børn: ${count(value.children)} · ukendt alder: ${count(value.unknown_age)}. Tilsyneladende køn: mandligt ${count(value.apparent_gender.male)}, kvindeligt ${count(value.apparent_gender.female)}, ukendt ${count(value.apparent_gender.unknown)}.${value.uncertainty ? ` Usikkerhed: ${value.uncertainty}` : ''}`;
        } else if (key === 'scene') {
          const settings = {indoor: 'Indendørs', outdoor: 'Udendørs', mixed: 'Inde og ude', unknown: 'Ukendt'};
          paragraph.textContent = [settings[value.setting], value.place_type, ...value.surroundings, value.background,
            `sikkerhed: ${Math.round(value.confidence * 100)} %`, value.uncertainty].filter(Boolean).join(' · ');
        } else paragraph.textContent = describe(value);
        sections.append(paragraph);
      }
    }
    const meta = data.metadata;
    byId('Metadata').textContent = `${meta.model} · ${new Date(meta.analyzed_at * 1000).toLocaleString('da-DK')} · prompt ${meta.prompt_version} · schema ${meta.schema_version}`;
    byId('JSON').textContent = JSON.stringify({analysis: data.result, metadata: meta, usage_before: data.usage}, null, 2);
    result.classList.remove('hidden');
    result.style.scrollMarginTop = `${dialog.querySelector('header').offsetHeight + 24}px`;
    if (dialog.open) result.scrollIntoView({block: 'start', behavior: 'smooth'});
  }
  async function discard() {
    if (!job || running) return;
    const old = job; job = null;
    try { await api(`test-analysis/${old}`, {method: 'DELETE'}); } catch (_) { /* Server TTL also expires results. */ }
  }
  async function poll() {
    clearTimeout(timer);
    if (!job) return;
    try {
      const data = await api(`test-analysis/${job}`);
      setError('');
      if (data.state === 'running') {
        status.textContent = 'ChatGPT analyserer billedet. Det kan tage et par minutter …';
        timer = setTimeout(poll, 1500); return;
      }
      running = false; controls();
      if (data.state === 'completed') { display(data); status.textContent = 'Analysen er færdig. Testbilledet er slettet fra FjordLens.'; }
      else { status.textContent = ''; setError(data.error || 'Analysen blev afbrudt.'); }
      if (!dialog.open) { clearPreview(); file.value = ''; controls(); await discard(); }
    } catch (err) {
      if (err.status === 404 || Date.now() >= pollDeadline) {
        running = false; controls(); status.textContent = '';
        setError('Resultatet kunne ikke hentes. Åbn testen igen eller genindlæs indstillingerne.'); return;
      }
      setError(`${err.message} Forsøger at hente resultatet igen …`);
      timer = setTimeout(poll, 5000);
    }
  }
  open.addEventListener('click', () => {
    dialog.showModal();
    if (!running) { result.classList.add('hidden'); status.textContent = ''; models(); }
  });
  byId('Close').addEventListener('click', () => dialog.close());
  dialog.addEventListener('close', () => {
    clearPreview(); file.value = ''; controls();
    if (!running) { discard(); result.classList.add('hidden'); byId('JSON').textContent = ''; }
  });
  file.addEventListener('change', () => {
    clearPreview(); setError(''); result.classList.add('hidden');
    const selected = file.files[0];
    if (selected) {
      if (selected.size > 20 * 1024 * 1024 || !['image/jpeg', 'image/png', 'image/webp'].includes(selected.type)) {
        setError('Vælg et JPG-, PNG- eller WebP-billede på højst 20 MB.'); file.value = '';
      } else { previewURL = URL.createObjectURL(selected); preview.src = previewURL; preview.classList.remove('hidden'); }
    }
    controls();
  });
  model.addEventListener('change', controls);
  byId('ModelsRetry').addEventListener('click', models);
  form.addEventListener('submit', async event => {
    event.preventDefault(); if (running || !form.reportValidity()) return;
    await discard();
    running = true; controls(); setError(''); result.classList.add('hidden');
    status.textContent = 'Uploader testbilledet og kontrollerer kontoens forbrug …';
    const body = new FormData(); body.append('image', file.files[0]);
    body.append('model', model.value); body.append('threshold', byId('Threshold').value);
    try { const data = await api('test-analysis', {method: 'POST', body}); job = data.id; pollDeadline = Date.now() + 240000; poll(); }
    catch (err) { running = false; controls(); status.textContent = ''; setError(err.message); }
  });
})();
