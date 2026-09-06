// The saved timeline is shared by local playback, public links and MP4 export.
document.getElementById('momentPlayerEditBtn')?.addEventListener('click', () => {
  const id = state.momentPlayer?.id;
  if (!id) return;
  _momentPlayerClose();
  editMomentSlideshow(id);
});

async function editMomentSlideshow(id) {
  const dialog = document.createElement('dialog');
  dialog.className = 'slideshow-editor';
  dialog.setAttribute('aria-label', 'Rediger diasshow');
  dialog.innerHTML = `<header><div><span class="mini-label">MOMENTER / REDIGERING</span><h2>Rediger diasshow</h2></div><div class="slideshow-actions"><button class="btn" data-play disabled>Afspil udkast</button><button class="btn primary" data-save disabled>Gem diasshow</button><button class="btn ghost" data-close>Luk</button></div></header><p role="status" aria-live="polite" data-status>Henter tidslinjen…</p><main data-main></main>`;
  document.body.append(dialog);
  dialog.showModal();
  let dirty = false, saving = false;
  const status = dialog.querySelector('[data-status]');
  const close = () => {
    if (saving || (dirty && !window.confirm('Luk uden at gemme ændringerne i diasshowet?'))) return;
    dialog.querySelectorAll('video').forEach(v => v.pause());
    dialog.close(); dialog.remove();
  };
  dialog.querySelector('[data-close]').onclick = close;
  dialog.addEventListener('cancel', e => { e.preventDefault(); close(); });
  try {
    // Detail generates the automatic starting timeline if needed.
    await momentRequest(`/api/moments/${id}`);
    const {item} = await momentRequest(`/api/moments/${id}/edit-data`);
    if (!dialog.isConnected) return;
    let slides = structuredClone(item.script || []), selected = 0, revision = item.revision;
    let undo = [], redo = [], editingField = null;
    const photos = Object.fromEntries(item.photos.map(p => [String(p.id), p]));
    const root = dialog.querySelector('[data-main]');
    dialog.querySelector('h2').textContent = item.title;
    root.innerHTML = `<div class="slideshow-workspace"><div class="slideshow-preview" data-preview aria-label="Forhåndsvisning"></div><aside class="slideshow-inspector"><h3 data-selection></h3><label>Overskrift<textarea data-field="heading" rows="2" maxlength="240"></textarea></label><label>Lille tekst over overskriften<input data-field="eyebrow" maxlength="100"></label><label>Dato eller undertekst<input data-field="detail" maxlength="180"></label><label>Vejr<input data-field="weather" maxlength="180" placeholder="Vises kun, hvis det findes eller tilføjes her"></label><div class="slideshow-field-row"><label>Sekunder<input data-field="duration" type="number" min="1" max="60" step="0.1"></label><label>Tekstens side<select data-field="layout"><option value="left">Venstre</option><option value="right">Højre</option></select></label></div><p class="mini-label" data-video-note hidden>Videoen afspilles altid til ende.</p><label data-fit-label>Billedvisning<select data-field="fit"><option value="contain">Hele billedet</option><option value="cover">Fyld skærmen</option></select></label><label data-style-label>Tekstkort<select data-field="style"><option value="intro">Introduktion</option><option value="chapter">Kapitel</option><option value="quote">Citat</option><option value="outro">Afslutning</option></select></label><label data-second-label>Andet billede<select data-second><option value="">Ét billede</option></select></label></aside></div><div class="slideshow-toolbar"><div class="slideshow-actions"><button class="btn small" data-undo>Fortryd</button><button class="btn small" data-redo>Gentag</button><button class="btn small" data-left aria-label="Flyt slide til venstre">← Flyt</button><button class="btn small" data-right aria-label="Flyt slide til højre">Flyt →</button><button class="btn small danger" data-remove>Fjern slide</button></div><div class="slideshow-actions"><button class="btn small" data-text>+ Tekst</button><button class="btn small" data-library-toggle>+ Billeder / videoer</button></div></div><p class="mini-label" data-total></p><div class="slideshow-timeline" data-timeline role="list" aria-label="Slides i afspilningsrækkefølge"></div><p class="mini-label">Træk slides for at ændre rækkefølgen. Træk i højre kant for at ændre visningstiden, eller skriv sekunder ovenfor.</p><section class="slideshow-library" data-library hidden><h3>Tilføj fra momentet</h3><p class="mini-label">Indsættes efter den valgte slide.</p><div data-library-grid></div></section>`;
    const preview = root.querySelector('[data-preview]');
    const placement = document.createElement('div');
    placement.className = 'slideshow-placement';
    placement.innerHTML = '<p class="mini-label">Træk teksten på billedet for at flytte den. Du kan også bruge piletasterne, når teksten er valgt.</p><button class="btn small" type="button" data-reset-position>Nulstil placering</button>';
    root.querySelector('.slideshow-inspector').append(placement);
    const timeline = root.querySelector('[data-timeline]');
    const fields = [...root.querySelectorAll('[data-field]')];
    const secondSelect = root.querySelector('[data-second]');
    for (const p of item.photos.filter(p => !p.is_video)) {
      const option = document.createElement('option');
      option.value = p.id; option.textContent = `${p.date?.replace('T',' ') || ''} · ${p.filename || p.id}`;
      secondSelect.append(option);
    }
    const snapshot = () => JSON.stringify({slides, selected});
    const checkpoint = () => { undo.push(snapshot()); if (undo.length > 60) undo.shift(); redo = []; };
    const changed = () => { dirty = true; status.textContent = 'Ændringerne er ikke gemt endnu.'; };
    const mutate = fn => { checkpoint(); editingField = null; fn(); changed(); render(); };
    const slideName = s => s.text || s.label || (s.type === 'video' ? 'Videoklip' : s.type === 'pair' ? 'To billeder' : s.type === 'text' ? 'Tekst' : 'Billede');
    function drawPreview() {
      preview.querySelectorAll('video').forEach(v => v.pause());
      preview.replaceChildren();
      const s = slides[selected];
      if (!s) return;
      const wrap = document.createElement('div');
      wrap.className = `moment-slide cinema-slide cinema-${s.type === 'text' ? s.style || 'chapter' : s.type} cinema-${s.layout || 'left'} cinema-motion-${s.motion || 0}${s.fit === 'contain' ? ' cinema-contain' : ''}`;
      wrap.style.setProperty('--cinema-duration', `${s.duration || 5.2}s`);
      const p = photos[String(s.photo_id || s.background_photo_id)];
      if (p && !(s.type === 'text' && p.is_video)) {
        if (s.fit === 'contain') {
          const blur = new Image(); blur.alt = ''; blur.className = 'cinema-blur'; blur.src = p.thumb_url; wrap.append(blur);
        }
        const media = document.createElement(s.type === 'video' ? 'video' : 'img');
        media.className = 'cinema-media';
        media.src = p.original_url || p.thumb_url;
        if (s.type === 'video') { media.controls = true; media.preload = 'metadata'; }
        else media.alt = '';
        wrap.append(media);
      }
      if (s.type === 'pair' && photos[String(s.second_photo_id)]) {
        const p2 = photos[String(s.second_photo_id)];
        const img = new Image(); img.alt = ''; img.className = 'cinema-media cinema-second'; img.src = p2.original_url || p2.thumb_url; wrap.append(img);
      }
      const text = momentSlideText(s);
      if (text) {
        text.tabIndex = 0;
        text.setAttribute('role', 'button');
        text.setAttribute('aria-label', 'Flyt teksten med musen eller piletasterne');
        wrap.append(text);
      }
      preview.append(wrap);
    }
    function positionForDrag(text) {
      if (slides[selected].text_position) return {...slides[selected].text_position};
      const bounds = [...text.children].map(e => e.getBoundingClientRect());
      const stage = preview.getBoundingClientRect();
      const left = Math.min(...bounds.map(r => r.left)), top = Math.min(...bounds.map(r => r.top));
      momentPositionText(text, {x:0, y:0});
      const box = text.getBoundingClientRect();
      return {x:Math.max(0, Math.min(1, (left-stage.left)/Math.max(1,stage.width-box.width))),
              y:Math.max(0, Math.min(1, (top-stage.top)/Math.max(1,stage.height-box.height)))};
    }
    const resetPosition = root.querySelector('[data-reset-position]');
    resetPosition.onclick = () => mutate(() => { delete slides[selected].text_position; });
    preview.onpointerdown = e => {
      const text = e.target.closest('.cinema-type');
      if (!text || e.button !== 0 || !e.isPrimary) return;
      e.preventDefault();
      const startX = e.clientX, startY = e.clientY, original = {...slides[selected]};
      const previousRedo = redo, previousDirty = dirty, previousStatus = status.textContent;
      let start = null;
      text.setPointerCapture(e.pointerId);
      text.focus({preventScroll:true});
      text.onpointermove = event => {
        if (event.pointerId !== e.pointerId) return;
        if (!start && Math.hypot(event.clientX-startX,event.clientY-startY) < 3) return;
        if (!start) { checkpoint(); editingField = null; start = positionForDrag(text); text.classList.add('is-dragging'); }
        const stage = preview.getBoundingClientRect(), box = text.getBoundingClientRect();
        slides[selected].text_position = {
          x:Math.max(0,Math.min(1,start.x+(event.clientX-startX)/Math.max(1,stage.width-box.width))),
          y:Math.max(0,Math.min(1,start.y+(event.clientY-startY)/Math.max(1,stage.height-box.height)))};
        momentPositionText(text, slides[selected].text_position);
        changed(); resetPosition.disabled = false;
      };
      const finish = event => {
        if (event.pointerId !== e.pointerId) return;
        text.onpointermove = text.onpointerup = text.onpointercancel = text.onlostpointercapture = null;
        if (start) {
          if (event.type === 'pointercancel') {
            slides[selected] = original; undo.pop(); redo = previousRedo;
            dirty = previousDirty; status.textContent = previousStatus;
          }
          render();
          preview.querySelector('.cinema-type')?.focus({preventScroll:true});
        }
      };
      text.onpointerup = text.onpointercancel = text.onlostpointercapture = finish;
    };
    preview.onkeydown = e => {
      const text = e.target.closest('.cinema-type');
      const delta = {ArrowLeft:[-1,0],ArrowRight:[1,0],ArrowUp:[0,-1],ArrowDown:[0,1]}[e.key];
      if (!text || !delta) return;
      e.preventDefault();
      const start = positionForDrag(text), step = e.shiftKey ? .05 : .01;
      mutate(() => { slides[selected].text_position = {
        x:Math.max(0,Math.min(1,start.x+delta[0]*step)),y:Math.max(0,Math.min(1,start.y+delta[1]*step))}; });
      preview.querySelector('.cinema-type')?.focus({preventScroll:true});
    };
    function drawTimeline() {
      const scroll = timeline.scrollLeft;
      timeline.replaceChildren();
      let seconds = 0, clips = 0;
      slides.forEach((s,i) => {
        const button = document.createElement('button');
        button.type = 'button'; button.draggable = true; button.dataset.index = i;
        button.className = `slideshow-clip${i === selected ? ' selected' : ''}`;
        button.setAttribute('aria-pressed', String(i === selected));
        button.setAttribute('aria-label', `Slide ${i+1}: ${slideName(s)}`);
        button.style.width = `${Math.max(100, Math.min(340, (s.duration || 8)*18))}px`;
        const p = photos[String(s.photo_id || s.background_photo_id)];
        button.innerHTML = `${p?.thumb_url ? `<img loading="lazy" alt="" src="${escapeHtml(p.thumb_url)}">` : '<span class="slideshow-text-icon">Aa</span>'}<span class="slideshow-clip-name">${i+1}. ${escapeHtml(slideName(s))}</span><small>${s.type === 'video' ? '▶ Hele klippet' : `${s.duration || 5.2} s`}${s.type === 'pair' ? ' · 2 billeder' : ''}</small>${s.type !== 'video' ? '<span class="slideshow-duration-handle" title="Træk for at ændre varighed" data-resize></span>' : ''}`;
        button.onclick = e => { if (!e.target.closest('[data-resize]')) { selected = i; editingField = null; render(); } };
        timeline.append(button);
        if (s.type === 'video') clips++; else seconds += Number(s.duration || 5.2);
      });
      timeline.scrollLeft = scroll;
      root.querySelector('[data-total]').textContent = `${slides.length} slides · ${Math.floor(seconds/60)} min. ${Math.round(seconds%60)} sek.${clips ? ` + ${clips} hele videoklip` : ''}`;
    }
    function render() {
      selected = Math.max(0, Math.min(selected, slides.length-1));
      const s = slides[selected];
      root.querySelector('[data-selection]').textContent = `Slide ${selected+1} af ${slides.length}`;
      for (const field of fields) {
        const key = field.dataset.field === 'heading' ? s.type === 'text' ? 'text' : 'label' : field.dataset.field;
        field.value = s[key] ?? (key === 'style' ? 'chapter' : key === 'fit' ? 'cover' : key === 'layout' ? 'left' : '');
        field.disabled = key === 'duration' && s.type === 'video';
      }
      fields[0].maxLength = s.type === 'text' ? 500 : 240;
      root.querySelector('[data-video-note]').hidden = s.type !== 'video';
      root.querySelector('[data-fit-label]').hidden = ['text','pair','video'].includes(s.type);
      root.querySelector('[data-style-label]').hidden = s.type !== 'text';
      root.querySelector('[data-second-label]').hidden = !['photo','pair'].includes(s.type);
      secondSelect.value = s.second_photo_id || '';
      for (const option of secondSelect.options) option.disabled = Number(option.value) === s.photo_id;
      root.querySelector('[data-undo]').disabled = !undo.length;
      root.querySelector('[data-redo]').disabled = !redo.length;
      root.querySelector('[data-left]').disabled = selected === 0;
      root.querySelector('[data-right]').disabled = selected === slides.length-1;
      root.querySelector('[data-remove]').disabled = slides.length <= 1;
      resetPosition.disabled = !s.text_position;
      drawPreview(); drawTimeline();
    }
    fields.forEach(field => {
      field.oninput = () => {
        if (!field.checkValidity()) return;
        if (editingField !== field) { checkpoint(); editingField = field; }
        const s = slides[selected];
        const key = field.dataset.field === 'heading' ? s.type === 'text' ? 'text' : 'label' : field.dataset.field;
        s[key] = key === 'duration' ? Number(field.value) : field.value;
        changed(); drawPreview(); drawTimeline();
        root.querySelector('[data-undo]').disabled = false;
        root.querySelector('[data-redo]').disabled = true;
      };
      field.onblur = () => { editingField = null; };
    });
    secondSelect.onchange = () => mutate(() => {
      const s = slides[selected];
      s.type = secondSelect.value ? 'pair' : 'photo';
      if (secondSelect.value) { s.second_photo_id = Number(secondSelect.value); s.fit = 'contain'; }
      else delete s.second_photo_id;
    });
    function move(from,to) {
      if (from === to) return;
      mutate(() => { const [slide] = slides.splice(from,1); slides.splice(to,0,slide); selected = to; });
      timeline.querySelector('.selected')?.scrollIntoView({block:'nearest',inline:'nearest'});
    }
    root.querySelector('[data-left]').onclick = () => move(selected,selected-1);
    root.querySelector('[data-right]').onclick = () => move(selected,selected+1);
    root.querySelector('[data-remove]').onclick = () => mutate(() => slides.splice(selected,1));
    root.querySelector('[data-undo]').onclick = () => { redo.push(snapshot()); ({slides,selected} = JSON.parse(undo.pop())); editingField = null; changed(); render(); };
    root.querySelector('[data-redo]').onclick = () => { undo.push(snapshot()); ({slides,selected} = JSON.parse(redo.pop())); editingField = null; changed(); render(); };
    const insert = slide => {
      if (slides.length >= 300) { status.textContent = 'Et diasshow kan højst have 300 slides.'; return; }
      mutate(() => { slides.splice(++selected,0,slide); });
      timeline.querySelector('.selected')?.scrollIntoView({block:'nearest',inline:'nearest'});
    };
    root.querySelector('[data-text]').onclick = () => insert({type:'text',style:'chapter',text:'Dit næste kapitel',duration:4.5});
    const library = root.querySelector('[data-library]');
    let libraryBuilt = false;
    root.querySelector('[data-library-toggle]').onclick = () => {
      library.hidden = !library.hidden;
      if (!libraryBuilt) {
        const grid = library.querySelector('[data-library-grid]');
        item.photos.forEach(p => {
          const button = document.createElement('button'); button.type = 'button'; button.className = 'btn slideshow-library-photo';
          button.innerHTML = `<img loading="lazy" alt="" src="${escapeHtml(p.thumb_url || '')}"><small>${p.is_video ? '▶ ' : ''}${escapeHtml(p.date?.replace('T',' ') || p.filename || '')}</small>`;
          button.onclick = () => insert({type:p.is_video ? 'video' : 'photo',photo_id:p.id,duration:p.is_video ? null : 5.2,fit:p.height > p.width ? 'contain':'cover',layout:selected%2 ? 'left':'right',label:'',detail:p.date?.replace('T',' ') || '',weather:p.weather || ''});
          grid.append(button);
        }); libraryBuilt = true;
      }
    };
    let dragIndex = null;
    timeline.ondragstart = e => {
      const clip = e.target.closest('[data-index]'); if (!clip || e.target.closest('[data-resize]')) { e.preventDefault(); return; }
      dragIndex = Number(clip.dataset.index); e.dataTransfer.effectAllowed = 'move'; e.dataTransfer.setData('text/plain',String(dragIndex));
    };
    timeline.ondragover = e => { if (dragIndex !== null) { e.preventDefault(); e.dataTransfer.dropEffect = 'move'; } };
    timeline.ondrop = e => {
      e.preventDefault(); const target = e.target.closest('[data-index]');
      if (dragIndex !== null && target) move(dragIndex,Number(target.dataset.index));
      dragIndex = null;
    };
    timeline.ondragend = () => { dragIndex = null; };
    timeline.onpointerdown = e => {
      const handle = e.target.closest('[data-resize]'); if (!handle) return;
      e.preventDefault(); const clip = handle.closest('[data-index]');
      const index = Number(clip.dataset.index), startX = e.clientX, startDuration = Number(slides[index].duration || 5.2);
      checkpoint(); selected = index; editingField = null; clip.draggable = false;
      handle.setPointerCapture(e.pointerId);
      handle.onpointermove = event => {
        slides[index].duration = Math.round(Math.max(1,Math.min(60,startDuration+(event.clientX-startX)/18))*10)/10;
        clip.style.width = `${Math.max(100,Math.min(340,slides[index].duration*18))}px`;
        clip.querySelector('small').textContent = `${slides[index].duration} s`;
        changed();
      };
      handle.onpointerup = handle.onpointercancel = () => { handle.onpointermove = null; render(); };
    };
    dialog.querySelector('[data-play]').disabled = false;
    dialog.querySelector('[data-play]').onclick = () => {
      preview.querySelectorAll('video').forEach(v => v.pause());
      dialog.close();
      state.momentPlayer = {title:item.title, script:structuredClone(slides), photos, index:0, onClose:() => dialog.showModal()};
      _momentPlayerOpen();
    };
    const save = dialog.querySelector('[data-save]'); save.disabled = false;
    save.onclick = async () => {
      if (!fields.every(f => f.reportValidity())) return;
      saving = true; save.disabled = true; status.textContent = 'Gemmer diasshow…';
      root.inert = true;
      dialog.querySelector('[data-play]').disabled = true;
      try {
        const result = await momentRequest(`/api/moments/${id}/slideshow`, 'PUT', {revision,script:slides});
        revision = result.revision; slides = result.script; dirty = false;
        status.textContent = 'Diasshow gemt. Afspilning og nye MP4-filer bruger din tidslinje. Eksisterende delelinks beholder deres version.';
      } catch(error) { status.textContent = error.message; }
      finally { saving = false; save.disabled = false; root.inert = false; dialog.querySelector('[data-play]').disabled = false; }
    };
    if (!slides.length) slides = [{type:'text',style:'intro',text:item.title,duration:4.5}];
    status.textContent = 'Vælg en slide for at redigere tekst, billeder og varighed.';
    render();
  } catch(error) { status.textContent = error.message; }
}
