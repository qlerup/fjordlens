(function () {
  'use strict';

  const DEFAULT_AHEAD = 10;
  const DEFAULT_BEHIND = 5;

  function mediaUrl(item) {
    return String(item && (item.original_url || item.view_url || item.thumb_url) || '').trim();
  }

  function isVideo(item) {
    return !!(item && item.is_video);
  }

  function release(entry) {
    if (!entry || !entry.node) return;
    const node = entry.node;
    if (entry.video) {
      try { node.pause(); } catch (_) {}
      try { node.removeAttribute('src'); } catch (_) {}
      try { node.load(); } catch (_) {}
    } else {
      try { node.onload = null; node.onerror = null; } catch (_) {}
      try { node.src = ''; } catch (_) {}
    }
  }

  function createEntry(item, url) {
    if (isVideo(item)) {
      const node = document.createElement('video');
      node.muted = true;
      node.playsInline = true;
      node.preload = 'auto';
      if (item && item.thumb_url) node.poster = item.thumb_url;
      node.src = url;
      try { node.load(); } catch (_) {}
      return { node, video: true };
    }

    const node = new Image();
    try { node.decoding = 'async'; } catch (_) {}
    try { node.fetchPriority = 'low'; } catch (_) {}
    node.src = url;
    return { node, video: false };
  }

  function create(options) {
    const ahead = Math.max(0, Number(options && options.ahead) || DEFAULT_AHEAD);
    const behind = Math.max(0, Number(options && options.behind) || DEFAULT_BEHIND);
    const cache = new Map();
    let generation = 0;
    let idleHandle = null;
    let timeoutHandle = null;

    function cancelScheduled() {
      if (idleHandle !== null && typeof window.cancelIdleCallback === 'function') {
        try { window.cancelIdleCallback(idleHandle); } catch (_) {}
      }
      if (timeoutHandle !== null) window.clearTimeout(timeoutHandle);
      idleHandle = null;
      timeoutHandle = null;
    }

    function clear() {
      generation += 1;
      cancelScheduled();
      for (const entry of cache.values()) release(entry);
      cache.clear();
    }

    function update(items, currentIndex) {
      generation += 1;
      const runGeneration = generation;
      cancelScheduled();
      const list = Array.isArray(items) ? items : [];
      const length = list.length;
      if (length < 2 || !Number.isFinite(Number(currentIndex))) {
        clear();
        return;
      }

      const current = ((Number(currentIndex) % length) + length) % length;
      const targets = [];
      const targetKeys = new Set();
      const addTarget = (index) => {
        const normalized = ((index % length) + length) % length;
        if (normalized === current) return;
        const item = list[normalized];
        const url = mediaUrl(item);
        if (!url) return;
        const key = `${isVideo(item) ? 'v' : 'i'}:${url}`;
        if (targetKeys.has(key)) return;
        targetKeys.add(key);
        targets.push({ key, item, url });
      };

      for (let offset = 1; offset <= ahead; offset += 1) addTarget(current + offset);
      for (let offset = 1; offset <= behind; offset += 1) addTarget(current - offset);

      for (const [key, entry] of cache.entries()) {
        if (targetKeys.has(key)) continue;
        release(entry);
        cache.delete(key);
      }

      const run = () => {
        idleHandle = null;
        timeoutHandle = null;
        if (runGeneration !== generation) return;
        for (const target of targets) {
          if (runGeneration !== generation) return;
          if (!cache.has(target.key)) cache.set(target.key, createEntry(target.item, target.url));
        }
      };

      if (typeof window.requestIdleCallback === 'function') {
        idleHandle = window.requestIdleCallback(run, { timeout: 350 });
      } else {
        timeoutHandle = window.setTimeout(run, 40);
      }
    }

    return { update, clear };
  }

  window.FjordLensMediaPreloader = { create, mediaUrl };
})();
