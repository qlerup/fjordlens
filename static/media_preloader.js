(function () {
  'use strict';

  const DEFAULT_AHEAD = 10;
  const DEFAULT_BEHIND = 10;

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
      // The presenter owns any image currently on screen.
      if (!node.isConnected) {
        try { node.removeAttribute('src'); } catch (_) {}
      }
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
    // Fetching alone does not make a large photo ready to paint on mobile.
    try { if (node.decode) node.decode().catch(() => {}); } catch (_) {}
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
      if (!length || !Number.isFinite(Number(currentIndex))) {
        clear();
        return;
      }

      const current = ((Number(currentIndex) % length) + length) % length;
      const targets = [];
      const targetKeys = new Set();
      const addTarget = (index) => {
        const normalized = ((index % length) + length) % length;
        const item = list[normalized];
        const url = mediaUrl(item);
        if (!url) return;
        const key = `${isVideo(item) ? 'v' : 'i'}:${url}`;
        if (targetKeys.has(key)) return;
        targetKeys.add(key);
        targets.push({ key, item, url });
      };

      // Keep the current photo too: advancing one step should only add one
      // distant neighbour and evict one at the opposite end of the window.
      addTarget(current);
      for (let offset = 1; offset <= Math.max(ahead, behind); offset += 1) {
        if (offset <= ahead) addTarget(current + offset);
        if (offset <= behind) addTarget(current - offset);
      }

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

    function getImage(item) {
      if (isVideo(item) || !mediaUrl(item)) return null;
      const key = `i:${mediaUrl(item)}`;
      if (!cache.has(key)) cache.set(key, createEntry(item, mediaUrl(item)));
      return cache.get(key).node;
    }

    return { update, clear, getImage };
  }

  function createImagePresenter({ getNode, setNode, preloader, onReady = () => {} }) {
    let generation = 0;

    function clear() {
      generation += 1;
      const node = getNode();
      if (node) {
        node.onload = null;
        // Keep a cached photo intact when the next item is a video.
        const blank = new Image();
        for (const attr of Array.from(node.attributes)) {
          if (attr.name !== 'src') blank.setAttribute(attr.name, attr.value);
        }
        node.replaceWith(blank);
        setNode(blank);
      }
    }

    function show(item, preview = null) {
      const previous = getNode();
      if (!previous) return;
      const currentGeneration = ++generation;
      const url = mediaUrl(item);
      const readyPreview = preview && preview.tagName === 'IMG'
        && preview.getAttribute('src') === url && preview.complete && preview.naturalWidth > 0;
      const full = readyPreview ? preview : (preloader.getImage?.(item) || new Image());
      const readyFull = full.complete && full.naturalWidth > 0;
      const node = readyFull ? full : new Image();

      // A reused <img> can keep painting the previous photo while its new src
      // loads. Start with a fresh node, or promote the actual loaded swipe image.
      const attributes = Array.from(previous.attributes, attr => [attr.name, attr.value]);
      for (const attr of Array.from(node.attributes)) {
        if (attr.name !== 'src') node.removeAttribute(attr.name);
      }
      for (const [name, value] of attributes) {
        if (name !== 'src') node.setAttribute(name, value);
      }
      node.style.display = 'block';
      const isCurrent = () => currentGeneration === generation && getNode() === node;
      node.onload = () => { if (isCurrent()) onReady(item); };
      if (!readyFull && item.thumb_url) node.src = item.thumb_url;
      previous.onload = null;
      previous.replaceWith(node);
      setNode(node);

      if (readyFull) {
        onReady(item);
        return;
      }

      full.decoding = 'async';
      full.fetchPriority = 'high';
      full.addEventListener('load', async () => {
        try { if (full.decode) await full.decode(); } catch (_) {}
        if (isCurrent() && full.naturalWidth > 0) node.src = url;
      }, { once: true });
      if (full.getAttribute('src') !== url) full.src = url;
    }

    return { show, clear };
  }

  // Metadata paging is independent of the rolling cache of full-size media.
  function createViewerPager({ getItems, getIndex, hasMore, loadMore, getContext, isOpen, onUpdate }) {
    let pending = null;
    const valid = context => isOpen() && getContext() === context;

    async function nextPage(context) {
      if (!valid(context)) return false;
      const count = getItems().length;
      if (!pending) {
        const request = Promise.resolve().then(loadMore).catch(() => false);
        pending = request;
        request.finally(() => { if (pending === request) pending = null; });
      }
      await pending;
      if (!valid(context)) return false;
      onUpdate();
      return getItems().length > count;
    }

    async function prefetch() {
      const context = getContext();
      while (valid(context) && hasMore() && getItems().length <= getIndex() + 10) {
        if (!await nextPage(context)) break;
      }
    }

    function peek(step) {
      const length = getItems().length;
      const target = getIndex() + step;
      if (!length || (hasMore() && (target < 0 || target >= length))) return -1;
      return ((target % length) + length) % length;
    }

    async function target(step) {
      const context = getContext();
      const index = getIndex();
      // A backwards wrap needs the actual end of the folder, not the last
      // photo in the first page. Forward navigation only fetches what's needed.
      while (valid(context) && hasMore() && (index + step < 0 || index + step >= getItems().length)) {
        if (!await nextPage(context)) return -1;
      }
      if (!valid(context) || getIndex() !== index) return -1;
      return peek(step);
    }

    return { prefetch, peek, target };
  }

  window.FjordLensMediaPreloader = { create, mediaUrl, createImagePresenter, createViewerPager };
})();
