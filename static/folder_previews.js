(function () {
  'use strict';

  // Limit image transfers across all folder mosaics, including large grids.
  const imageQueue = [];
  const cancellations = new Set();
  let activeImages = 0;
  function pumpImages() {
    while (activeImages < 6 && imageQueue.length) {
      const { url, card, resolve } = imageQueue.shift();
      if (!card.isConnected) { resolve(null); continue; }
      activeImages++;
      const img = new Image();
      img.alt = '';
      img.draggable = false;
      img.decoding = 'async';
      let finished = false;
      const finish = (result) => {
        if (finished) return;
        finished = true;
        clearTimeout(timer);
        cancellations.delete(cancel);
        img.onload = img.onerror = null;
        if (!result) img.removeAttribute('src');
        activeImages--;
        resolve(result);
        pumpImages();
      };
      const cancel = () => finish(null);
      cancellations.add(cancel);
      const timer = setTimeout(() => finish(null), 20000);
      img.onerror = () => finish(null);
      img.onload = async () => {
        try {
          if (img.decode) await img.decode();
          finish(img.naturalWidth ? img : null);
        } catch { finish(null); }
      };
      img.src = url;
    }
  }

  const generations = new WeakMap();
  async function render(card, urls) {
    const generation = {};
    generations.set(card, generation);
    const clean = [...new Set((urls || []).filter(Boolean))].slice(0, 4);
    const count = clean.length >= 4 ? 4 : (clean.length >= 2 ? 2 : clean.length);
    const images = await Promise.all(clean.slice(0, count).map(url => new Promise(resolve => {
      imageQueue.push({ url, card, resolve });
      pumpImages();
    })));
    if (!card.isConnected || generations.get(card) !== generation) return;
    const grid = card.querySelector('.folder-grid');
    if (!grid) return;
    const ready = images.filter(Boolean);
    const shown = ready.length >= 4 ? ready.slice(0, 4) : (ready.length >= 2 ? ready.slice(0, 2) : ready);
    grid.classList.remove('v1', 'v2', 'v4');
    grid.classList.add(`v${shown.length || 1}`);
    // Attach the decoded mosaic in one operation: no progressive JPEG paint
    // and no four independent quarters appearing one after another.
    grid.replaceChildren(...shown);
  }

  const pending = new Map();
  const observer = typeof IntersectionObserver === 'function' ? new IntersectionObserver(entries => {
    for (const entry of entries) {
      if (!entry.isIntersecting) continue;
      const load = pending.get(entry.target);
      pending.delete(entry.target);
      observer.unobserve(entry.target);
      if (load && entry.target.isConnected) load();
    }
  }, { rootMargin: '300px' }) : null;

  function watch(card, getUrls) {
    // Drop detached cards after navigation instead of retaining their closures.
    for (const previous of pending.keys()) {
      if (!previous.isConnected) { observer?.unobserve(previous); pending.delete(previous); }
    }
    const load = async () => {
      try {
        const urls = await getUrls();
        if (card.isConnected) await render(card, urls);
      } catch { /* Leave the stable folder placeholder available to open. */ }
    };
    if (observer) { pending.set(card, load); observer.observe(card); }
    else load();
  }

  function reset() {
    observer?.disconnect();
    pending.clear();
    imageQueue.splice(0).forEach(task => task.resolve(null));
    for (const cancel of Array.from(cancellations)) cancel();
  }

  function createBatchLoader(fetchBatch) {
    const waiting = new Map();
    const inFlight = new Map();
    let active = 0;
    let scheduled = false;
    function schedule() {
      if (scheduled) return;
      scheduled = true;
      setTimeout(flush, 0);
    }
    function flush() {
      scheduled = false;
      while (active < 2 && waiting.size) {
        const batch = Array.from(waiting.entries()).slice(0, 16);
        batch.forEach(([key]) => waiting.delete(key));
        active++;
        Promise.resolve().then(() => fetchBatch(batch.map(([key]) => key))).then(items => {
          batch.forEach(([key, task]) => task.resolve(items[key] || []));
        }, error => batch.forEach(([, task]) => task.reject(error))).finally(() => {
          batch.forEach(([key]) => inFlight.delete(key));
          active--;
          if (waiting.size) schedule();
        });
      }
    }
    return key => {
      if (inFlight.has(key)) return inFlight.get(key);
      const promise = new Promise((resolve, reject) => waiting.set(key, { resolve, reject }));
      inFlight.set(key, promise);
      schedule();
      return promise;
    };
  }

  window.FjordLensFolderPreviews = { watch, render, reset, createBatchLoader };
})();
