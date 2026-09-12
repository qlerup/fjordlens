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
    #face-selection-targets button{text-align:left}
    .face-selection-empty{padding:24px;color:var(--muted)}
  `;
  document.head.append(style);

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
