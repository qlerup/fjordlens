(() => {
  'use strict';

  let latestSession = null;
  const nativeFetch = window.fetch.bind(window);
  const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
  const isIOS = () => /iPhone|iPad|iPod/i.test(String(navigator.userAgent || ''));

  window.fetch = async (...args) => {
    const response = await nativeFetch(...args);
    try {
      const input = args[0];
      const url = typeof input === 'string' ? input : String(input?.url || '');
      const options = args[1] || {};
      const method = String(options.method || (typeof input !== 'string' ? input?.method : '') || 'GET').toUpperCase();
      if (method === 'POST' && /\/api\/cast-airplay\/session(?:\?|$)/.test(url)) {
        const data = await response.clone().json();
        if (data?.ok && data?.token) latestSession = data;
      }
    } catch (_) {}
    return response;
  };

  async function api(url, options = {}) {
    const response = await nativeFetch(url, {
      credentials: 'same-origin',
      ...options,
      headers: {...(options.body ? {'Content-Type':'application/json'} : {}), ...(options.headers || {})},
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
    return data;
  }

  function nativeAirPlayPlugin() {
    try {
      return window.Capacitor?.Plugins?.FjordLensAirPlay || window.FjordLensAirPlay || null;
    } catch (_) {
      return null;
    }
  }

  function setLoading(state) {
    const body = document.getElementById('castAirplayBody');
    const sub = document.getElementById('castAirplaySub');
    const error = document.getElementById('castAirplayError');
    if (error) { error.textContent = ''; error.classList.add('hidden'); }
    const done = Number(state?.done || 0);
    const total = Number(state?.total || 0);
    const segments = Number(state?.segments || 0);
    if (sub) sub.textContent = total > 0 ? `AirPlay · ${done}/${total}` : 'AirPlay…';
    if (body) {
      const detail = segments > 0
        ? `Streamen er startet · ${segments} segment${segments === 1 ? '' : 'er'} klar`
        : 'Klargør de første sekunder…';
      body.innerHTML = `<div class="cast-airplay-loading"><strong>Starter AirPlay</strong><br><span style="opacity:.75">${detail}</span></div>`;
    }
  }

  function setError(message) {
    const error = document.getElementById('castAirplayError');
    const body = document.getElementById('castAirplayBody');
    if (error) { error.textContent = String(message || 'Kunne ikke starte AirPlay.'); error.classList.remove('hidden'); }
    if (body) body.innerHTML = '<div class="cast-airplay-note">Prøv igen, eller vælg færre billeder/videoer.</div>';
  }

  async function waitUntilPlayable(session) {
    const token = encodeURIComponent(session.token);
    let state = await api(`/api/airplay-hls/${token}/prepare`, {
      method: 'POST',
      body: JSON.stringify({force: false}),
    });
    const deadline = Date.now() + 5 * 60 * 1000;
    while (!state.playable) {
      if (state.state === 'error' || state.error) throw new Error(state.error || 'AirPlay-streamen kunne ikke klargøres.');
      if (Date.now() > deadline) throw new Error('AirPlay-streamen tog for lang tid om at starte.');
      setLoading(state);
      await sleep(350);
      state = await api(`/api/airplay-hls/${token}/status`);
    }
    return state;
  }

  async function startAirPlay(session) {
    if (!session?.token) return;
    setLoading({});
    try {
      const state = await waitUntilPlayable(session);
      setLoading(state);
      const plugin = nativeAirPlayPlugin();
      if (plugin && typeof plugin.start === 'function') {
        await plugin.start({
          url: String(state.stream_url || ''),
          title: String(session.title || 'FjordLens'),
        });
        return;
      }
      window.location.href = String(state.web_player_url || `/airplay/hls/${encodeURIComponent(session.token)}/play`);
    } catch (error) {
      setError(error?.message || error);
    }
  }

  document.addEventListener('click', event => {
    if (!isIOS()) return;
    const button = event.target?.closest?.('[data-airplay-start]');
    if (!button || !latestSession?.token) return;
    event.preventDefault();
    event.stopPropagation();
    event.stopImmediatePropagation();
    startAirPlay(latestSession);
  }, true);

  const observer = new MutationObserver(() => {
    if (!isIOS() || !latestSession?.token) return;
    const choice = document.querySelector('#castAirplayBody .cast-airplay-choice p');
    if (choice) {
      const native = !!nativeAirPlayPlugin();
      choice.textContent = native
        ? 'Vælg AirPlay-enhed i FjordLens. Slideshowet streames løbende, så det kan starte før hele valget er klargjort.'
        : 'FjordLens streamer de valgte billeder og videoer som HLS til AirPlay. I den installerede iOS-app bruges Apples native AirPlay-vælger.';
    }
    const button = document.querySelector('#castAirplayBody [data-airplay-start]');
    if (button && button.textContent !== 'AirPlay') button.textContent = 'AirPlay';
  });

  function beginObserve() {
    observer.observe(document.body, {subtree:true, childList:true});
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', beginObserve, {once:true});
  else beginObserve();
})();
