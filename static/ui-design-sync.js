(function () {
  'use strict';

  const root = document.documentElement;
  let inFlight = null;
  let generation = 0;

  function apply(design) {
    if (design !== 'classic' && design !== 'fjord') return;
    // Invalidate an older GET if an admin save finishes while it is in flight.
    generation += 1;
    const changed = root.getAttribute('data-ui-design') !== design;
    root.setAttribute('data-ui-design', design);
    const stylesheet = document.getElementById('fjordDesignStylesheet');
    if (stylesheet) {
      stylesheet.disabled = false;
      stylesheet.media = design === 'fjord' ? 'all' : 'not all';
    }
    // Only a signal for other tabs. The value is never read as a preference.
    try {
      if (localStorage.getItem('fl_ui_design') !== design) localStorage.setItem('fl_ui_design', design);
    } catch (_) {}
    const theme = root.getAttribute('data-theme');
    let dark = true;
    try { dark = window.matchMedia('(prefers-color-scheme: dark)').matches; } catch (_) {}
    document.querySelectorAll('meta[name="theme-color"]').forEach(meta => {
      const media = meta.getAttribute('media');
      const light = theme === 'light' || (theme !== 'dark' && (media ? media.includes('light') : !dark));
      meta.setAttribute('content', design === 'fjord'
        ? (light ? '#edf3f4' : '#08141a')
        : (light ? '#f5f6f8' : '#0f1115'));
    });
    if (changed) window.dispatchEvent(new CustomEvent('fjordlens:ui-design', { detail: design }));
  }

  function refresh() {
    if (document.visibilityState === 'hidden') return Promise.resolve();
    if (inFlight) return inFlight;
    const started = generation;
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 8000);
    inFlight = (async () => {
      try {
        const response = await fetch('/api/ui-design', {
          credentials: 'same-origin', cache: 'no-store',
          headers: { Accept: 'application/json' }, signal: controller.signal,
        });
        if (!response.ok) return;
        const data = await response.json();
        if (data.ok && started === generation) apply(data.ui_design);
      } catch (_) {
        // Offline: retain the last server-confirmed design, never reset it.
      } finally {
        window.clearTimeout(timeout);
      }
    })().finally(() => { inFlight = null; });
    return inFlight;
  }

  window.FjordLensDesign = { apply, refresh };
  apply(root.getAttribute('data-ui-design'));
  ['pageshow', 'focus', 'online'].forEach(event => window.addEventListener(event, refresh));
  document.addEventListener('visibilitychange', refresh);
  window.addEventListener('storage', event => {
    if (!event.key || event.key === 'fl_ui_design') return refresh();
  });
  // Open pages on other devices follow admin changes within five seconds.
  window.setInterval(refresh, 5000);
  refresh();
})();
