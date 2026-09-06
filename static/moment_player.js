function momentIsPhone() {
  return (navigator.maxTouchPoints > 0 || matchMedia('(pointer: coarse)').matches)
    && Math.min(innerWidth, innerHeight) <= 900;
}

function momentSizeFrame() {
  const overlay = els.momentPlayerOverlay;
  const frame = overlay?.querySelector('.moment-player-frame');
  if (!frame) return;
  const rect = overlay.getBoundingClientRect();
  if (!rect.width || !rect.height) return;
  const sideways = momentIsPhone() && rect.height > rect.width;
  const availableWidth = sideways ? rect.height : rect.width;
  const availableHeight = sideways ? rect.width : rect.height;
  const width = Math.min(availableWidth, availableHeight * 16 / 9);
  frame.style.width = `${width}px`;
  frame.style.height = `${width * 9 / 16}px`;
  frame.classList.toggle('is-sideways', sideways);
  _momentPlayerMeasureFooter();
}

// Rotate the inner cinema canvas, not the fullscreen element. This also works
// on browsers which cannot lock device orientation (including iPhone Safari).
if (els.momentPlayerOverlay) {
  const frame = document.createElement('div');
  frame.className = 'moment-player-frame';
  frame.append(...els.momentPlayerOverlay.children);
  els.momentPlayerOverlay.append(frame);
  new ResizeObserver(momentSizeFrame).observe(els.momentPlayerOverlay);
  window.addEventListener('resize', momentSizeFrame);
}

function momentTryLandscape(player) {
  const overlay = els.momentPlayerOverlay;
  try {
    const enter = overlay.requestFullscreen?.() || overlay.webkitRequestFullscreen?.();
    Promise.resolve(enter).then(async () => {
      if (state.momentPlayer !== player) {
        if (document.fullscreenElement === overlay) document.exitFullscreen?.().catch(() => {});
        else if (document.webkitFullscreenElement === overlay) document.webkitExitFullscreen?.();
        return;
      }
      try { await screen.orientation?.lock?.('landscape'); player.orientationLocked = true; } catch {}
      if (state.momentPlayer !== player) screen.orientation?.unlock?.();
      momentSizeFrame();
    }).catch(() => momentSizeFrame());
  } catch { momentSizeFrame(); }
}

function _momentPlayerOpen() {
  if (!els.momentPlayerOverlay) return;
  els.momentPlayerOverlay.classList.remove('hidden');
  document.body.classList.add('moment-player-open');
  if (els.momentPlayerFooterTitle) els.momentPlayerFooterTitle.textContent = (state.momentPlayer && state.momentPlayer.title) || '';
  const edit = document.getElementById('momentPlayerEditBtn');
  if (edit) edit.classList.toggle('hidden', !state.momentPlayer?.id || !['admin', 'manager'].includes(state.currentUser?.role));
  if (els.momentPlayerVideoBtn) {
    els.momentPlayerVideoBtn.classList.toggle('hidden', !state.momentPlayer?.id);
    els.momentPlayerVideoBtn.textContent = tr(state.momentPlayer?.videoUrl ? 'momenter_video_download' : 'momenter_make_video');
    els.momentPlayerVideoBtn.disabled = false;
  }
  const player = state.momentPlayer;
  const phone = momentIsPhone();
  if (player) momentStartMusic(player, {hold:phone});
  momentSizeFrame();
  _momentPlayerMeasureFooter();
  _momentPlayerBuildProgress();
  if (phone && player) {
    player.preparing = true;
    els.momentPlayerOverlay.classList.add('is-preparing');
    const guide = document.createElement('div');
    guide.className = 'moment-rotate-guide';
    guide.innerHTML = '<div role="status"><svg viewBox="0 0 100 100" aria-hidden="true"><path d="M78 32A32 32 0 1 0 82 56M78 14v20H58"/></svg><h2>Drej telefonen</h2><p>Diasshowet starter om 3 sekunder</p></div><button class="btn" type="button">Annuller</button>';
    guide.querySelector('button').onclick = _momentPlayerClose;
    els.momentPlayerOverlay.append(guide);
    momentTryLandscape(player);
    player.startTimer = setTimeout(() => {
      if (state.momentPlayer !== player) return;
      guide.remove(); player.preparing = false;
      els.momentPlayerOverlay.classList.remove('is-preparing');
      momentSizeFrame(); player.soundtrack?.play();
      _momentPlayerRenderSlide(0);
    }, 3000);
  } else _momentPlayerRenderSlide(0);
}

function _momentPlayerBuildProgress() {
  if (!els.momentPlayerProgress) return;
  const p = state.momentPlayer;
  const n = p && Array.isArray(p.script) ? p.script.length : 0;
  let html = '';
  for (let i = 0; i < n; i++) html += '<div class="moment-player-progress-seg" data-index="' + i + '"><i></i></div>';
  els.momentPlayerProgress.innerHTML = html;
}

function _momentPlayerClearTimer() {
  const p = state.momentPlayer;
  if (p && p.timer) {
    clearTimeout(p.timer);
    p.timer = null;
  }
}

function _momentPlayerUpdateProgressUi(index) {
  if (!els.momentPlayerProgress) return;
  const segs = els.momentPlayerProgress.querySelectorAll('.moment-player-progress-seg');
  segs.forEach((seg, i) => {
    seg.classList.toggle('done', i < index);
    seg.classList.toggle('active', i === index);
    seg.classList.remove('run');
  });
}

function _momentPlayerRunProgressBar(index, durationMs) {
  if (!els.momentPlayerProgress) return;
  const seg = els.momentPlayerProgress.querySelector(`.moment-player-progress-seg[data-index="${index}"] i`);
  if (!seg) return;
  seg.style.transitionDuration = '0ms';
  seg.style.width = '0%';
  requestAnimationFrame(() => {
    requestAnimationFrame(() => {
      const activeSeg = seg.closest('.moment-player-progress-seg');
      if (activeSeg) activeSeg.classList.add('run');
      seg.style.transitionDuration = `${Math.max(200, durationMs)}ms`;
      seg.style.width = '100%';
    });
  });
}

function _momentPlayerRenderSlide(index) {
  const p = state.momentPlayer;
  if (!p) return;
  _momentPlayerClearTimer();
  if (index < 0) index = 0;
  if (index >= p.script.length) {
    _momentPlayerClose();
    return;
  }
  p.index = index;
  const item = p.script[index];
  const stage = els.momentPlayerStage;
  if (!stage) return;
  const token = (p.renderToken || 0) + 1;
  p.renderToken = token;
  stage.setAttribute('aria-busy', 'true');
  if (!stage.children.length) {
    const loading = document.createElement('div');
    loading.className = 'cinema-loading';
    loading.textContent = 'Henter billedet i fuld kvalitet…';
    stage.appendChild(loading);
  }
  _momentPlayerUpdateProgressUi(index);
  const dwell = Math.max(1000, Math.min(60000, Number(item.duration || 5.2) * 1000));
  const wrap = document.createElement('div');
  const card = item.type === 'text';
  wrap.className = `moment-slide cinema-slide cinema-${card ? item.style || 'intro' : item.type} cinema-${item.layout || 'left'} cinema-motion-${Number(item.motion || 0) % 4}${item.fit === 'contain' ? ' cinema-contain' : ''}`;
  wrap.style.setProperty('--cinema-duration', `${dwell}ms`);
  const photo = p.photos[String(item.photo_id || item.background_photo_id)] || {};
  const src = photo.original_url || photo.thumb_url;
  let media;
  let secondMedia;
  let firstLoaded = false, secondLoaded = item.type !== 'pair';
  const imageReady = () => { firstLoaded = true; if (secondLoaded) ready(); };
  let loadingTimeout;
  let started = false;
  function ready() {
    if (started) return;
    started = true;
    clearTimeout(loadingTimeout);
    if (state.momentPlayer !== p || p.renderToken !== token) return;
    stage.querySelector('.cinema-loading')?.remove();
    stage.setAttribute('aria-busy', 'false');
    stage.querySelectorAll('.moment-slide').forEach(old => {
      old.querySelectorAll('video').forEach(video => video.pause());
      old.classList.add('cinema-leaving');
      setTimeout(() => old.remove(), 650);
    });
    stage.appendChild(wrap);
    if (media?.tagName === 'VIDEO') {
      media.play().catch(() => { media.controls = true; });
    } else {
      _momentPlayerRunProgressBar(index, dwell);
      p.timer = setTimeout(() => _momentPlayerAdvance(1), dwell);
    }
    const next = p.script[index + 1];
    const nextPhoto = next && p.photos[String(next.photo_id || next.background_photo_id)];
    if (nextPhoto && !nextPhoto.is_video && (nextPhoto.original_url || nextPhoto.thumb_url)) {
      const preload = new Image();
      preload.src = nextPhoto.original_url || nextPhoto.thumb_url;
    }
  }
  if (src && !(card && photo.is_video)) {
    media = document.createElement(item.type === 'video' ? 'video' : 'img');
    media.className = 'cinema-media';
    if (item.type === 'video') {
      media.muted = true;
      media.playsInline = true;
      media.preload = 'auto';
      media.addEventListener('loadeddata', ready, { once: true });
      media.addEventListener('ended', () => {
        if (state.momentPlayer === p && p.renderToken === token) _momentPlayerAdvance(1);
      }, { once: true });
      media.addEventListener('timeupdate', () => {
        if (state.momentPlayer !== p || p.renderToken !== token || !Number.isFinite(media.duration) || media.duration <= 0) return;
        const bar = els.momentPlayerProgress?.querySelector(`.moment-player-progress-seg[data-index="${index}"] i`);
        if (bar) { bar.style.transitionDuration = '0ms'; bar.style.width = `${Math.min(100, media.currentTime / media.duration * 100)}%`; }
      });
    } else {
      media.alt = '';
      media.addEventListener('load', imageReady, { once: true });
      if (item.fit === 'contain') {
        const blurred = document.createElement('img');
        blurred.className = 'cinema-blur';
        blurred.alt = '';
        blurred.src = src;
        wrap.appendChild(blurred);
      }
    }
    media.addEventListener('error', () => {
      if (media.tagName === 'VIDEO') {
        clearTimeout(loadingTimeout);
        if (state.momentPlayer === p && p.renderToken === token) _momentPlayerAdvance(1);
        return;
      }
      if (media.tagName === 'IMG' && photo.thumb_url && media.getAttribute('src') !== photo.thumb_url) media.src = photo.thumb_url;
      else imageReady();
    });
    wrap.appendChild(media);
  }
  if (item.type === 'pair') {
    const second = p.photos[String(item.second_photo_id)] || {};
    secondMedia = document.createElement('img');
    secondMedia.className = 'cinema-media cinema-second';
    secondMedia.alt = '';
    secondMedia.onload = () => { secondLoaded = true; if (firstLoaded) ready(); };
    secondMedia.onerror = () => {
      if (second.thumb_url && secondMedia.getAttribute('src') !== second.thumb_url) secondMedia.src = second.thumb_url;
      else { secondLoaded = true; if (firstLoaded) ready(); }
    };
    wrap.appendChild(secondMedia);
    secondMedia.src = second.original_url || second.thumb_url || '';
  }
  const text = momentSlideText(item);
  if (text) wrap.appendChild(text);
  if (media) {
    loadingTimeout = setTimeout(ready, 10000);
    media.src = src;
  } else ready();
}

function _momentPlayerMeasureFooter() {
  const footer = els.momentPlayerOverlay?.querySelector('.moment-player-footer');
  if (footer) els.momentPlayerOverlay.style.setProperty('--moment-footer-height', `${footer.offsetHeight}px`);
}

const momentPlayerFooter = els.momentPlayerOverlay?.querySelector('.moment-player-footer');
if (momentPlayerFooter) {
  const full = document.createElement('button');
  full.type = 'button'; full.className = 'btn'; full.id = 'momentPlayerFullscreenBtn';
  full.textContent = 'Fuld skærm';
  full.onclick = async () => {
    try {
      if (document.fullscreenElement || document.webkitFullscreenElement) {
        await (document.exitFullscreen?.() || document.webkitExitFullscreen?.());
      } else {
        const player = els.momentPlayerOverlay;
        if (player.requestFullscreen) await player.requestFullscreen();
        else if (player.webkitRequestFullscreen) player.webkitRequestFullscreen();
        else window.alert('Denne browser understøtter ikke fuldskærm for diasshows. Du kan vende telefonen for at få en bredere visning.');
      }
    } catch { full.textContent = 'Prøv fuld skærm igen'; }
  };
  const updateFullscreen = () => {
    full.textContent = (document.fullscreenElement || document.webkitFullscreenElement) ? 'Afslut fuld skærm' : 'Fuld skærm';
    _momentPlayerMeasureFooter();
  };
  document.addEventListener('fullscreenchange', updateFullscreen);
  document.addEventListener('webkitfullscreenchange', updateFullscreen);
  momentPlayerFooter.append(full);
}
if (momentPlayerFooter && typeof ResizeObserver !== 'undefined') {
  new ResizeObserver(_momentPlayerMeasureFooter).observe(momentPlayerFooter);
}

function momentPositionText(text, position) {
  const valid = position && Number.isFinite(position.x) && Number.isFinite(position.y);
  text.classList.toggle('cinema-positioned', Boolean(valid));
  if (valid) {
    for (const key of ['x', 'y']) text.style.setProperty(`--text-${key}`, Math.max(0, Math.min(1, position[key])));
  }
}

function momentSlideText(item) {
  const title = item.type === 'text' ? item.text : item.label;
  if (title || item.eyebrow || item.detail || item.weather) {
    const text = document.createElement('div');
    text.className = 'cinema-type';
    momentPositionText(text, item.text_position);
    for (const [className, value] of [['cinema-eyebrow', item.eyebrow], ['cinema-heading', title], ['cinema-detail', item.detail], ['cinema-weather', item.weather]]) {
      if (!value) continue;
      const line = document.createElement('div');
      line.className = className;
      line.dataset.textKey = className.replace('cinema-', '');
      line.textContent = value;
      text.appendChild(line);
    }
    if (item.text_elements) momentApplyTextElements(text, item.text_elements);
    return text;
  }
  return null;
}

function momentApplyTextElements(text, elements) {
  text.classList.remove('cinema-positioned');
  text.classList.add('cinema-separated');
  for (const [index, line] of [...text.querySelectorAll('[data-text-key]')].entries()) {
    const box = elements[line.dataset.textKey] || {x:.15,y:.15+index*.16,width:.7,height:.12,font_size:.035};
    line.classList.add('cinema-text-layer');
    for (const [key, property] of [['x','left'],['y','top'],['width','width'],['height','height']]) line.style[property] = `${box[key]*100}%`;
    line.style.fontSize = `${box.font_size*100}cqw`;
    let ink = line.querySelector('.cinema-text-ink');
    if (!ink) {
      ink = document.createElement('span'); ink.className = 'cinema-text-ink';
      ink.textContent = line.textContent; line.replaceChildren(ink);
      const observer = new ResizeObserver(() => {
        if (!line.isConnected) { observer.disconnect(); return; }
        momentFitTextInk(line);
      });
      observer.observe(line); observer.observe(ink);
      // The parent is frequently replaced between slides; disconnect on removal.
      line._textResizeObserver = observer;
    }
    momentFitTextInk(line);
  }
}

function momentFitTextInk(line) {
  const ink = line.querySelector('.cinema-text-ink');
  if (ink?.offsetWidth && ink.offsetHeight) ink.style.transform = `scale(${line.clientWidth/ink.offsetWidth},${line.clientHeight/ink.offsetHeight})`;
}

function _momentPlayerAdvance(delta) {
  const p = state.momentPlayer;
  if (!p || p.preparing) return;
  _momentPlayerRenderSlide(p.index + delta);
}

function _momentPlayerClose() {
  clearTimeout(state.momentPlayer?.startTimer);
  if (state.momentPlayer?.orientationLocked) { try { screen.orientation?.unlock?.(); } catch {} }
  els.momentPlayerOverlay?.classList.remove('is-preparing');
  els.momentPlayerOverlay?.querySelector('.moment-rotate-guide')?.remove();
  if (document.fullscreenElement === els.momentPlayerOverlay) document.exitFullscreen?.().catch(() => {});
  else if (document.webkitFullscreenElement === els.momentPlayerOverlay) document.webkitExitFullscreen?.();
  state.momentPlayer?.soundtrack?.stop();
  const onClose = state.momentPlayer?.onClose;
  _momentPlayerClearTimer();
  if (els.momentPlayerOverlay) els.momentPlayerOverlay.classList.add('hidden');
  document.body.classList.remove('moment-player-open');
  if (els.momentPlayerStage) {
    els.momentPlayerStage.querySelectorAll('video').forEach(video => { video.pause(); video.removeAttribute('src'); video.load(); });
    els.momentPlayerStage.innerHTML = '';
  }
  state.momentPlayer = null;
  if (onClose) onClose();
}

if (els.momentPlayerCloseBtn) {
  els.momentPlayerCloseBtn.addEventListener('click', () => _momentPlayerClose());
}
if (els.momentPlayerPrevZone) {
  els.momentPlayerPrevZone.addEventListener('click', () => _momentPlayerAdvance(-1));
}
if (els.momentPlayerNextZone) {
  els.momentPlayerNextZone.addEventListener('click', () => _momentPlayerAdvance(1));
}
document.addEventListener('keydown', (e) => {
  if (!state.momentPlayer || document.querySelector('dialog[open]')) return;
  if (e.key === 'Escape' && !(document.fullscreenElement || document.webkitFullscreenElement)) _momentPlayerClose();
  else if (e.key === 'ArrowRight') _momentPlayerAdvance(1);
  else if (e.key === 'ArrowLeft') _momentPlayerAdvance(-1);
});
if (els.momentPlayerVideoBtn) {
  els.momentPlayerVideoBtn.addEventListener('click', () => {
    if (state.momentPlayer?.id) momentVideoFormatDialog();
  });
}

async function momentVideoFormatDialog() {
  const player = state.momentPlayer;
  if (!player?.id || document.querySelector('.moment-video-dialog')) return;
  _momentPlayerClearTimer();
  els.momentPlayerStage.querySelectorAll('video').forEach(v => v.pause());
  const dialog = document.createElement('dialog');
  dialog.className = 'moment-video-dialog';
  dialog.setAttribute('aria-label', 'Gem video');
  dialog.innerHTML = `<h2>Gem video</h2><p>Diasshowet gemmes i bredformat · 16:9 · 1920 × 1080, med din valgte musik. Se det på computer, TV eller med telefonen på siden.</p><p role="status" data-format-status>Henter videostatus…</p><div class="slideshow-actions"><button class="btn ghost" data-cancel>Annuller</button><button class="btn primary" data-create disabled>Lav video</button></div>`;
  els.momentPlayerOverlay.append(dialog);
  player.soundtrack?.pause();
  const close = () => { dialog.close(); dialog.remove(); if (state.momentPlayer === player) { player.soundtrack?.resume(); _momentPlayerRenderSlide(player.index); } };
  dialog.querySelector('[data-cancel]').onclick = close;
  dialog.addEventListener('cancel', e => { e.preventDefault(); close(); });
  dialog.showModal();
  let cached = null;
  const create = dialog.querySelector('[data-create]'), status = dialog.querySelector('[data-format-status]');
  const format = () => 'landscape';
  const update = () => {
    const ready = cached?.video_status === 'done' && cached.video_format === format() && cached.video_url;
    create.textContent = ready ? 'Hent MP4' : 'Lav video';
    create.disabled = ['queued','running','rendering'].includes(cached?.video_status);
    status.textContent = create.disabled ? 'Der bliver allerede lavet en video. Prøv igen, når den er færdig.' : ready ? 'Din video i dette format er klar.' : 'Videoen bruger samme brede diasshow. Videoklip afspilles til ende.';
  };
  create.onclick = () => {
    const choice = format();
    if (cached?.video_status === 'done' && cached.video_format === choice && cached.video_url) {
      window.open(cached.video_url, '_blank', 'noopener'); close();
    } else { close(); startMomentVideoRender(player.id, choice); }
  };
  try {
    const response = await fetch(`/api/moments/${encodeURIComponent(player.id)}/render-video/status`);
    cached = await response.json();
    if (!response.ok || !cached.ok) throw new Error(cached.error || 'Kunne ikke hente videostatus.');
    if (dialog.isConnected) update();
  } catch (error) { if (dialog.isConnected) { cached = null; status.textContent = error.message; create.disabled = false; } }
}

