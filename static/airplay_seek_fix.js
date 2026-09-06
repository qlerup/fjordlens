(() => {
  'use strict';

  const match = String(window.location.pathname || '').match(/^\/airplay\/control\/([^/]+)\/play\/?$/);
  if (!match) return;

  const token = match[1];
  const statusUrl = `/api/airplay-controls/${encodeURIComponent(decodeURIComponent(token))}/status`;
  const video = document.getElementById('video');
  const prev = document.getElementById('prev');
  const next = document.getElementById('next');
  const scrub = document.getElementById('scrub');
  const statusEl = document.getElementById('status');
  if (!video || !prev || !next || !scrub) return;

  let state = {timeline: [], total: 0, finished: false};
  let busy = false;
  const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));

  async function refreshState() {
    try {
      const response = await fetch(statusUrl, {credentials: 'same-origin', cache: 'no-store'});
      const data = await response.json();
      if (!response.ok || !data.ok) throw new Error(data.error || `HTTP ${response.status}`);
      state = data;
    } catch (_) {}
    return state;
  }

  function timeline() {
    return Array.isArray(state.timeline) ? state.timeline : [];
  }

  function currentIndex() {
    const entries = timeline();
    if (!entries.length) return 0;
    const t = Number(video.currentTime || 0) + 0.12;
    let current = Number(entries[0].index || 0);
    for (const entry of entries) {
      if (t >= Number(entry.start || 0)) current = Number(entry.index || 0);
      else break;
    }
    return current;
  }

  function entryFor(index) {
    return timeline().find(item => Number(item.index) === Number(index)) || null;
  }

  function clampToSeekable(value) {
    const wanted = Math.max(0, Number(value) || 0);
    try {
      const ranges = video.seekable;
      if (!ranges || !ranges.length) return wanted;

      for (let i = 0; i < ranges.length; i += 1) {
        const start = Number(ranges.start(i));
        const end = Number(ranges.end(i));
        if (wanted >= start && wanted <= end) {
          return Math.min(Math.max(wanted, start + 0.03), Math.max(start + 0.03, end - 0.03));
        }
        if (wanted < start) return Math.min(start + 0.08, Math.max(start, end - 0.03));
      }

      const last = ranges.length - 1;
      const start = Number(ranges.start(last));
      const end = Number(ranges.end(last));
      return Math.max(start + 0.03, end - 0.08);
    } catch (_) {
      return wanted;
    }
  }

  function once(target, name, timeoutMs) {
    return new Promise(resolve => {
      let done = false;
      const finish = () => {
        if (done) return;
        done = true;
        target.removeEventListener(name, finish);
        resolve();
      };
      target.addEventListener(name, finish, {once: true});
      setTimeout(finish, timeoutMs);
    });
  }

  async function reloadAt(target) {
    const clean = String(video.currentSrc || video.src || '').split('#')[0].replace(/([?&])fjordSeek=\d+(&?)/, (m, lead, tail) => tail ? lead : '');
    const join = clean.includes('?') ? '&' : '?';
    video.src = `${clean}${join}fjordSeek=${Date.now()}#t=${target.toFixed(3)}`;
    video.load();
    await once(video, 'loadedmetadata', 2500);
    try { video.currentTime = clampToSeekable(target); } catch (_) {}
    await once(video, 'seeked', 1200);
  }

  async function seekReliably(target, label) {
    if (busy) return;
    busy = true;
    prev.disabled = true;
    next.disabled = true;
    try {
      await refreshState();
      const wanted = clampToSeekable(target);
      if (statusEl) statusEl.textContent = label || 'Springer…';
      try { video.pause(); } catch (_) {}

      const before = Number(video.currentTime || 0);
      try {
        if (typeof video.fastSeek === 'function') video.fastSeek(wanted);
        else video.currentTime = wanted;
      } catch (_) {
        try { video.currentTime = wanted; } catch (_) {}
      }
      await once(video, 'seeked', 1400);

      let actual = Number(video.currentTime || 0);
      if (Math.abs(actual - wanted) > 0.9 || Math.abs(actual - before) < 0.15) {
        try { video.currentTime = wanted; } catch (_) {}
        await once(video, 'seeked', 900);
        actual = Number(video.currentTime || 0);
      }

      // Safari can ignore a programmatic seek on an HLS EVENT playlist,
      // especially around EXT-X-DISCONTINUITY boundaries. Reloading the same
      // public playlist with a media fragment gives WebKit a fresh seek target.
      if (Math.abs(actual - wanted) > 0.9) {
        await reloadAt(wanted);
      }

      try { await video.play(); } catch (_) {}
      if (statusEl) statusEl.textContent = state.finished ? 'Slideshowet er klar' : 'Slideshowet fortsætter';
    } finally {
      prev.disabled = false;
      next.disabled = false;
      busy = false;
    }
  }

  async function jump(step) {
    await refreshState();
    const total = Math.max(0, Number(state.total || 0));
    if (!total) return;
    let index = currentIndex() + step;
    if (index < 0) index = state.finished ? total - 1 : 0;
    if (index >= total) index = state.finished ? 0 : total - 1;

    let entry = entryFor(index);
    const deadline = Date.now() + 8000;
    while (!entry && Date.now() < deadline && !state.finished) {
      if (statusEl) statusEl.textContent = `Klargør medie ${index + 1}…`;
      await sleep(300);
      await refreshState();
      entry = entryFor(index);
    }
    if (!entry) {
      if (statusEl) statusEl.textContent = 'Mediet er ikke klar endnu.';
      return;
    }

    const duration = Math.max(0, Number(entry.duration || 0));
    const inset = duration > 0 ? Math.min(0.35, Math.max(0.12, duration * 0.03)) : 0.15;
    await seekReliably(Number(entry.start || 0) + inset, `Springer til ${index + 1} / ${total}…`);
  }

  prev.addEventListener('click', event => {
    event.preventDefault();
    event.stopImmediatePropagation();
    jump(-1);
  }, true);

  next.addEventListener('click', event => {
    event.preventDefault();
    event.stopImmediatePropagation();
    jump(1);
  }, true);

  scrub.addEventListener('change', event => {
    event.preventDefault();
    event.stopImmediatePropagation();
    seekReliably(Number(scrub.value || 0), 'Spoler…');
  }, true);

  refreshState();
})();
