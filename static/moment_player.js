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
  _momentPlayerBuildProgress();
  _momentPlayerRenderSlide(0);
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

function momentSlideText(item) {
  const title = item.type === 'text' ? item.text : item.label;
  if (title || item.eyebrow || item.detail || item.weather) {
    const text = document.createElement('div');
    text.className = 'cinema-type';
    for (const [className, value] of [['cinema-eyebrow', item.eyebrow], ['cinema-heading', title], ['cinema-detail', item.detail], ['cinema-weather', item.weather]]) {
      if (!value) continue;
      const line = document.createElement('div');
      line.className = className;
      line.textContent = value;
      text.appendChild(line);
    }
    return text;
  }
  return null;
}

function _momentPlayerAdvance(delta) {
  const p = state.momentPlayer;
  if (!p) return;
  _momentPlayerRenderSlide(p.index + delta);
}

function _momentPlayerClose() {
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
  if (!state.momentPlayer) return;
  if (e.key === 'Escape') _momentPlayerClose();
  else if (e.key === 'ArrowRight') _momentPlayerAdvance(1);
  else if (e.key === 'ArrowLeft') _momentPlayerAdvance(-1);
});
if (els.momentPlayerVideoBtn) {
  els.momentPlayerVideoBtn.addEventListener('click', () => {
    if (state.momentPlayer?.videoUrl) window.open(state.momentPlayer.videoUrl, '_blank', 'noopener');
    else if (state.momentPlayer && state.momentPlayer.id) startMomentVideoRender(state.momentPlayer.id);
  });
}

