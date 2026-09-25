(() => {
  const selection = {source:null, active:false, ids:new Set(), busy:false};
  const style = document.createElement('style');
  style.textContent = `
    .face-selection-toolbar{display:flex;gap:8px;align-items:center;flex-wrap:wrap;width:100%;padding:10px 0}
    .face-selection-check{position:absolute;top:10px;left:10px;z-index:15;width:26px;height:26px;accent-color:#20c875;cursor:pointer}
    .face-selection-card{position:relative;cursor:pointer}
    .face-selection-card.is-picked{outline:3px solid #20c875;outline-offset:-3px}
    #face-selection-dialog{background:#102129;color:#edf6f8;border:1px solid #36515b;border-radius:16px;width:420px;max-width:calc(100vw - 32px);max-height:80dvh;overflow:auto;padding:20px;box-sizing:border-box}
    #face-selection-dialog::backdrop{background:#0009}
    .face-selection-search{display:flex;gap:8px;margin:16px 0}
    .face-selection-search input{min-width:0;flex:1;background:#152e37;color:inherit;border:1px solid #45636d;border-radius:8px;padding:10px}
    #face-selection-targets{display:grid;gap:6px;max-height:40dvh;overflow:auto}
    .face-selection-actions{display:flex;gap:8px;justify-content:space-between;margin-top:16px}
    #face-selection-targets button{text-align:left}
    .face-selection-empty{padding:24px;color:var(--muted)}
    #face-review-dialog{background:#102129;color:#edf6f8;border:1px solid #36515b;border-radius:16px;width:min(980px,calc(100vw - 32px));max-height:88dvh;overflow:auto;padding:20px;box-sizing:border-box}
    #face-review-dialog::backdrop{background:#0009}
    .face-review-header{display:flex;align-items:center;justify-content:space-between;gap:12px}.face-review-header h3{margin:0}
    .face-review-progress{height:7px;background:#203842;border-radius:999px;overflow:hidden;margin:12px 0}.face-review-progress span{display:block;height:100%;background:#20c875;transition:width .2s ease}
    .face-review-groups{display:grid;gap:8px}.face-review-group{display:flex;align-items:center;justify-content:space-between;gap:12px;text-align:left}.face-review-group small{color:#9fb4ba}
    .face-review-preview{display:flex;gap:4px;overflow:hidden}.face-review-preview img{width:38px;height:38px;object-fit:cover;border-radius:4px}
    .face-review-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(140px,1fr));gap:10px;margin:14px 0}.face-review-card{position:relative;aspect-ratio:1;overflow:hidden;border:1px solid #36515b;border-radius:8px}.face-review-card img{width:100%;height:100%;object-fit:cover}.face-review-box{position:absolute;border:2px solid #ff5757;box-sizing:border-box;pointer-events:none}
    .face-review-actions{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-top:12px}.face-review-actions select{max-width:230px;background:#152e37;color:inherit;border:1px solid #45636d;border-radius:8px;padding:8px}
  `;
  document.head.append(style);

  window.openPersonFaceReview = ({sourceId, sourceName}) => {
    if (sourceId === null || sourceId === undefined) return;
    const dialog = document.createElement('dialog');
    dialog.id = 'face-review-dialog';
    dialog.innerHTML = `<div class="face-review-header"><h3>Genmatch ansigter</h3><button type="button" class="btn tiny" data-close>Drop alt</button></div>
      <p data-status>Forbereder analyse…</p><div class="face-review-progress"><span></span></div><div data-content></div>`;
    document.body.append(dialog);
    const status = dialog.querySelector('[data-status]');
    const progress = dialog.querySelector('.face-review-progress span');
    const content = dialog.querySelector('[data-content]');
    let changed = false;
    let groups = [];
    const sourceValue = sourceId === 'unknown' ? sourceId : Number(sourceId);
    const refreshSource = () => {
      if (changed && state.view === 'personer' && String(state.personView.personId) === String(sourceId)) {
        loadPersonPhotos(sourceId, sourceName);
      }
    };
    const setStatus = job => {
      const total = Math.max(0, Number(job.total || 0));
      const scanned = Math.max(0, Number(job.scanned || 0));
      progress.style.width = total ? `${Math.min(100, Math.round((scanned / total) * 100))}%` : '0%';
      status.textContent = job.status === 'done'
        ? `Færdig: ${groups.length} forslag fundet.`
        : `Scanner ${scanned} / ${total || '…'} ansigter…`;
    };
    const applyGroup = async (group, action, targetId = null) => {
      dialog.querySelectorAll('button,select').forEach(control => { control.disabled = true; });
      try {
        const response = await fetch('/api/people/faces/selection', {
          method: 'POST', headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({source_id: sourceValue, face_ids: group.face_ids, action, target_id: targetId}),
        });
        const result = await response.json().catch(() => ({}));
        if (!response.ok || !result.ok) throw new Error(result.error || 'Kunne ikke gemme ændringen.');
        changed = true;
        groups = groups.filter(candidate => candidate !== group);
        renderGroups();
      } catch (error) {
        status.textContent = error.message || 'Kunne ikke gemme ændringen.';
      } finally {
        dialog.querySelectorAll('button,select').forEach(control => { control.disabled = false; });
      }
    };
    const showGroup = group => {
      content.replaceChildren();
      const back = document.createElement('button'); back.type = 'button'; back.className = 'btn tiny'; back.textContent = 'Tilbage'; back.addEventListener('click', renderGroups); content.append(back);
      const title = document.createElement('h4'); title.textContent = `${group.target_name} · ${group.count} ansigt(er)`; content.append(title);
      const grid = document.createElement('div'); grid.className = 'face-review-grid';
      (group.faces || []).forEach(face => {
        const card = document.createElement('div'); card.className = 'face-review-card';
        const image = document.createElement('img'); image.src = face.image_url; image.alt = ''; image.loading = 'lazy'; card.append(image);
        const box = document.createElement('div'); box.className = 'face-review-box';
        box.style.left = `${Math.max(0, Number(face.box?.x || 0)) * 100}%`; box.style.top = `${Math.max(0, Number(face.box?.y || 0)) * 100}%`;
        box.style.width = `${Math.max(0, Number(face.box?.w || 0)) * 100}%`; box.style.height = `${Math.max(0, Number(face.box?.h || 0)) * 100}%`;
        card.append(box); grid.append(card);
      });
      content.append(grid);
      const actions = document.createElement('div'); actions.className = 'face-review-actions';
      const merge = document.createElement('button'); merge.type = 'button'; merge.className = 'btn'; merge.textContent = `Flet med ${group.target_name}`; merge.addEventListener('click', () => applyGroup(group, 'assign', Number(group.target_id))); actions.append(merge);
      const targets = (state.people || []).filter(person => !person.hidden && person.id !== 'unknown' && Number(person.id) !== Number(sourceId) && personHasName(person));
      const select = document.createElement('select'); targets.forEach(person => { const option = document.createElement('option'); option.value = String(person.id); option.textContent = person.name; select.append(option); }); actions.append(select);
      const assign = document.createElement('button'); assign.type = 'button'; assign.className = 'btn'; assign.textContent = 'Flet med valgt'; assign.addEventListener('click', () => applyGroup(group, 'assign', Number(select.value))); actions.append(assign);
      const hide = document.createElement('button'); hide.type = 'button'; hide.className = 'btn danger'; hide.textContent = 'Skjul'; hide.addEventListener('click', () => applyGroup(group, 'hide')); actions.append(hide);
      content.append(actions);
    };
    const renderGroups = () => {
      content.replaceChildren();
      if (!groups.length) { content.textContent = 'Ingen mulige fejl fundet.'; return; }
      const list = document.createElement('div'); list.className = 'face-review-groups';
      groups.forEach(group => {
        const button = document.createElement('button'); button.type = 'button'; button.className = 'btn face-review-group';
        const label = document.createElement('span'); label.innerHTML = `<strong>${group.target_name}</strong><small>${group.count} ansigt(er) foreslås flyttet</small>`; button.append(label);
        const previews = document.createElement('span'); previews.className = 'face-review-preview'; (group.previews || []).forEach(face => { const image = document.createElement('img'); image.src = face.image_url; image.alt = ''; previews.append(image); }); button.append(previews);
        button.addEventListener('click', () => showGroup(group)); list.append(button);
      });
      content.append(list);
    };
    const poll = async jobId => {
      while (dialog.isConnected) {
        const response = await fetch(`/api/people/face-review/${encodeURIComponent(jobId)}`);
        const job = await response.json().catch(() => ({}));
        if (!response.ok || !job.ok) { status.textContent = job.error || 'Analysen fejlede.'; return; }
        if (job.status === 'done') { groups = Array.isArray(job.results) ? job.results : []; setStatus(job); renderGroups(); return; }
        if (job.status === 'error') { status.textContent = job.error || 'Analysen fejlede.'; return; }
        setStatus(job);
        await new Promise(resolve => window.setTimeout(resolve, 350));
      }
    };
    dialog.querySelector('[data-close]').addEventListener('click', () => dialog.close());
    dialog.addEventListener('close', () => { refreshSource(); dialog.remove(); });
    dialog.showModal();
    fetch('/api/people/face-review', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({source_id: sourceValue})})
      .then(response => response.json().then(data => ({response, data})))
      .then(({response, data}) => { if (!response.ok || !data.ok) throw new Error(data.error || 'Kunne ikke starte analysen.'); return poll(data.job_id); })
      .catch(error => { status.textContent = error.message || 'Kunne ikke starte analysen.'; });
  };

  window.openPersonFaceActionDialog = ({sourceId, faceIds, people = [], labels = {}, onSuccess}) => {
    if (!Array.isArray(faceIds) || !faceIds.length) return;
    const dialog = document.createElement('dialog');
    dialog.id = 'face-selection-dialog';
    dialog.innerHTML = `<h3>${labels.title || 'Flyt ansigt til person'}</h3><p>${labels.help || ''}</p>
      <form class="face-selection-search"><input type="search" maxlength="160" placeholder="${labels.placeholder || ''}" aria-label="${labels.placeholder || ''}" required><button class="btn" type="submit">${labels.create || 'Opret'}</button></form>
      <div id="face-selection-targets"></div><p role="alert"></p><div class="face-selection-actions"><button type="button" class="btn danger" data-hide>${labels.hide || 'Skjul'}</button><button type="button" class="btn" data-close>${labels.cancel || 'Annuller'}</button></div>`;
    document.body.append(dialog);
    const input = dialog.querySelector('input');
    const list = dialog.querySelector('#face-selection-targets');
    const alert = dialog.querySelector('[role="alert"]');
    let targets = [];
    const setTargets = values => {
      targets = (values || []).filter(person => !person.hidden && person.id !== 'unknown'
        && Number(person.id) !== Number(sourceId) && personHasName(person));
    };
    const submit = async (action, targetId = null, name = '') => {
      dialog.querySelectorAll('button,input').forEach(element => { element.disabled = true; });
      try {
        const response = await fetch('/api/people/faces/selection', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({source_id: sourceId, face_ids: faceIds, action, target_id: targetId, name}),
        });
        const result = await response.json().catch(() => ({}));
        if (!response.ok || !result.ok) throw new Error(result.error || labels.failed || 'Kunne ikke gemme ændringen.');
        onSuccess?.(result, action);
        dialog.close();
      } catch (error) {
        alert.textContent = error.message || labels.failed || 'Kunne ikke gemme ændringen.';
        dialog.querySelectorAll('button,input').forEach(element => { element.disabled = false; });
      }
    };
    const filter = () => {
      list.replaceChildren();
      targets.filter(person => person.name.toLocaleLowerCase('da').includes(input.value.trim().toLocaleLowerCase('da'))).forEach(person => {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'btn';
        button.textContent = person.name;
        button.addEventListener('click', () => submit('assign', Number(person.id)));
        list.append(button);
      });
    };
    setTargets(people); filter();
    input.addEventListener('input', filter);
    dialog.querySelector('form').addEventListener('submit', event => {
      event.preventDefault();
      if (input.value.trim()) submit('create', null, input.value.trim());
    });
    dialog.querySelector('[data-hide]').addEventListener('click', () => submit('hide'));
    dialog.querySelector('[data-close]').addEventListener('click', () => dialog.close());
    dialog.addEventListener('close', () => dialog.remove());
    fetch('/api/people').then(response => response.json()).then(data => {
      if (!dialog.isConnected) return;
      setTargets(data.items || []); filter();
    }).catch(() => {});
    dialog.showModal();
    input.focus();
  };

  window.setupPersonFaceSelection = (head, grid) => {
    if (!['admin','manager'].includes(state.currentUser?.role)) return;
    const source = state.personView.personId;
    if (selection.source !== source) {selection.source = source; selection.ids.clear(); selection.active = false;}
    const items = state.items || [];
    const valid = new Set(items.map(item => item.id));
    for (const id of selection.ids) if (!valid.has(id)) selection.ids.delete(id);
    head.style.flexWrap = 'wrap';
    const bar = document.createElement('div'); bar.className = 'face-selection-toolbar';
    const button = (text, handler) => {
      const el = document.createElement('button'); el.type = 'button'; el.className = 'btn tiny'; el.textContent = text;
      el.onclick = handler; bar.append(el); return el;
    };
    button(selection.active ? 'Færdig' : 'Vælg', () => {selection.active = !selection.active; selection.ids.clear(); renderGrid();});
    const count = document.createElement('span'); bar.append(count);
    const all = button('Vælg alle', () => {
      if (selection.ids.size === items.length) selection.ids.clear(); else items.forEach(item => selection.ids.add(item.id));
      sync();
    });
    const name = button('Navngiv valgte', () => openNaming());
    const hide = button('Skjul valgte', () => submit('hide'));
    hide.classList.add('danger'); head.append(bar);
    if (!items.length) {
      const empty = document.createElement('p'); empty.className = 'face-selection-empty';
      empty.textContent = 'Der er ikke flere billeder at gennemgå her.'; grid.append(empty);
    }
    const cards = [...grid.querySelectorAll('.photo-card[data-photo-id]')];
    function sync() {
      count.textContent = selection.active ? `${selection.ids.size} valgt` : '';
      all.hidden = name.hidden = hide.hidden = !selection.active;
      all.textContent = selection.ids.size === items.length && items.length ? 'Fravælg alle' : 'Vælg alle';
      bar.querySelectorAll('button').forEach(el => el.disabled = selection.busy);
      name.disabled = hide.disabled = selection.busy || !selection.ids.size;
      cards.forEach(card => {
        const id = Number(card.dataset.photoId), checked = selection.ids.has(id);
        card.classList.toggle('is-picked', selection.active && checked);
        const input = card.querySelector('.face-selection-check');
        if (input) {input.checked = checked; input.disabled = selection.busy;}
      });
    }
    if (selection.active) cards.forEach(card => {
      const id = Number(card.dataset.photoId);
      card.classList.add('face-selection-card');
      const check = document.createElement('input'); check.type = 'checkbox'; check.className = 'face-selection-check';
      check.setAttribute('aria-label', 'Vælg billede'); card.prepend(check);
      card.addEventListener('click', event => {
        event.stopImmediatePropagation();
        if (event.target !== check) event.preventDefault();
        if (selection.busy) return;
        if (selection.ids.has(id)) selection.ids.delete(id); else selection.ids.add(id);
        sync();
      }, true);
    });
    let dialog = null;
    async function submit(action, targetId = null, newName = '') {
      if (selection.busy || !selection.ids.size) return;
      const chosen = new Set(selection.ids);
      const faceIds = [...new Set(items.filter(item => chosen.has(item.id)).flatMap(item => (item.faces || []).map(face => face.id)))];
      selection.busy = true; sync();
      const control = action === 'hide' ? hide : name;
      control.classList.add('loading'); control.setAttribute('aria-busy', 'true');
      dialog?.querySelectorAll('button,input').forEach(el => el.disabled = true);
      let saved = false;
      try {
        const response = await fetch('/api/people/faces/selection', {method:'POST', headers:{'Content-Type':'application/json'},
          body:JSON.stringify({source_id:source === 'unknown' ? source : Number(source), face_ids:faceIds, action, target_id:targetId, name:newName})});
        const result = await response.json();
        if (!response.ok || !result.ok) throw new Error(result.error || 'Kunne ikke gemme valget.');
        saved = true;
        if (state.view === 'personer' && state.personView.mode === 'photos' && state.personView.personId === source) {
          state.items = (state.items || []).filter(item => !chosen.has(item.id));
        }
        if (selection.source === source) selection.ids.clear();
        state._peopleCache = null;
        dialog?.close();
        showStatus(action === 'hide' ? 'Valgte ansigter er skjult. De findes igen under Vis skjulte.' : 'Valgte ansigter er flyttet til ' + result.name, 'ok');
        // Refresh counts/cache without leaving the current review context.
        if (state.view === 'personer') {try {await loadPeople(false);} catch (_) {}}
      } catch (error) {
        showStatus(error.message, 'err');
        if (dialog) dialog.querySelector('[role="alert"]').textContent = error.message;
      } finally {
        selection.busy = false; control.classList.remove('loading'); control.removeAttribute('aria-busy');
        dialog?.querySelectorAll('button,input').forEach(el => el.disabled = false);
        if (saved) renderGrid(); else sync();
      }
    }
    function openNaming() {
      dialog = document.createElement('dialog'); dialog.id = 'face-selection-dialog';
      dialog.setAttribute('aria-labelledby','face-selection-title');
      dialog.innerHTML = `<h3 id="face-selection-title">Navngiv valgte ansigter</h3><p>Vælg en eksisterende person, eller skriv et navn og tryk Opret.</p>
        <form class="face-selection-search"><input type="search" maxlength="160" placeholder="Søg eller opret person" aria-label="Søg eller opret person" required><button class="btn" type="submit">Opret</button></form>
        <div id="face-selection-targets"></div><p role="alert"></p><button type="button" class="btn" data-close>Annuller</button>`;
      document.body.append(dialog);
      const input = dialog.querySelector('input'), list = dialog.querySelector('#face-selection-targets');
      let targets = [];
      const setTargets = people => {targets = people.filter(person => !person.hidden && person.id !== 'unknown' && Number(person.id) !== Number(source) && personHasName(person));};
      setTargets(state.people || []);
      function filter() {
        list.replaceChildren();
        targets.filter(person => person.name.toLocaleLowerCase('da').includes(input.value.trim().toLocaleLowerCase('da'))).forEach(person => {
          const btn = document.createElement('button'); btn.type = 'button'; btn.className = 'btn'; btn.textContent = person.name;
          btn.onclick = () => submit('assign', Number(person.id)); list.append(btn);
        });
      }
      input.oninput = filter; filter();
      fetch('/api/people').then(response => response.json()).then(data => {
        if (!dialog.isConnected || selection.busy) return;
        setTargets(data.items || []); filter();
      }).catch(() => {});
      dialog.querySelector('form').onsubmit = event => {event.preventDefault(); if (input.value.trim()) submit('create', null, input.value.trim());};
      dialog.querySelector('[data-close]').onclick = () => dialog.close();
      dialog.addEventListener('cancel', event => {if (selection.busy) event.preventDefault();});
      dialog.addEventListener('close', () => {dialog.remove(); name.focus();});
      dialog.showModal(); input.focus();
    }
    sync();
  };
})();
