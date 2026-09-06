(function (root) {
  'use strict';
  function createCache({ ttl = 60000, maxEntries = 16, maxBytes = 8 * 1024 * 1024, now = Date.now } = {}) {
    const entries = new Map();
    let bytes = 0;
    let generation = 0;
    const remove = key => {
      const entry = entries.get(key);
      if (entry) bytes -= entry.size;
      entries.delete(key);
    };
    return {
      generation: () => generation,
      clear() { entries.clear(); bytes = 0; generation++; },
      get(key) {
        const entry = entries.get(key);
        if (!entry) return null;
        if (now() - entry.created >= ttl) { remove(key); return null; }
        entries.delete(key);
        entries.set(key, entry);
        return JSON.parse(entry.json);
      },
      set(key, value, requestGeneration = generation) {
        if (requestGeneration !== generation) return;
        const json = JSON.stringify(value);
        const size = json.length * 2;
        remove(key);
        if (size > maxBytes) return;
        entries.set(key, { json, size, created: now() });
        bytes += size;
        while (entries.size > maxEntries || bytes > maxBytes) remove(entries.keys().next().value);
      },
    };
  }
  root.FjordLensGalleryCache = { createCache };
})(window);
