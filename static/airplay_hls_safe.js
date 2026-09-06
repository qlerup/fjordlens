(() => {
  'use strict';

  let latestSession = window.__fjordlensCastSession || null;
  const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
  const isIOS = () => /iPhone|iPad|iPod/i.test(String(navigator.userAgent || ''));

  window.addEventListener('fjordlens:cast-session', event => {
    const session = event?.detail;
    if (session?.token) latestSession = session;
  });

  async function api(url, options = {}, timeoutMs = 15000) {
    const controller = typeof AbortController !== 'undefined' ? new AbortController() : null;
    const timer = controller ? setTimeout(() => controller.abort(), timeoutMs) : null;
    try {
      const response = await window.fetch(url, {
        credentials: 'same-origin',
        ...options,
        ...(controller ? {signal: controller.signal} : {}),
        headers: {...(options.body ? {'Content-Type':'application/json'} : {}), ...(options.headers || {})},
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
      return data;
    } catch (error) {
      if (error?.name === 'AbortError') throw new Error('FjordLens-serveren svarede ikke inden for 15 sekunder.');
      throw error;
    } finally {
      if (timer) clearTimeout(timer);
    }
  }

  function nativeAirPlayPlugin() {
    try {
      return window.Capacitor?.Plugins?.FjordLensAirPlay || window.FjordLensAirPlay || null;
    } catch (_) { return null; }
  }

  function setLoading(state) {
    const body = document.getElementById('castAirplayBody');
    const sub = document.getElementById('castAirplaySub');
    const error = document.getElementById('castAirplayError');
    if (error) {
      if (error.textContent) error.textContent = '';
      if (!error.classList.contains('hidden')) error.classList.add('hidden');
    }
    const done = Number(state?.done || 0);
    const total = Number(state?.total || 0);
    const segments = Number(state?.segments || 0);
    const subText = total > 0 ? `AirPlay · ${done}/${total}` : 'AirPlay…';
    if (sub && sub.textContent !== subText) sub.textContent = subText;
    if (body) {
      const detail = segments > 0
        ? `Streamen er klar til start · ${segments} segment${segments === 1 ? '' : 'er'}`
        : 'Klargør de første sekunder…';
      const html = `<div class="cast-airplay-loading"><strong>Starter AirPlay</strong><br><span style="opacity:.75">${detail}</span></div>`;
      if (body.innerHTML !== html) body.innerHTML = html;
    }
  }

  function setError(message) {
    const error = document.getElementById('castAirplayError');
    const body = document.getElementById('castAirplayBody');
    const text = String(message || 'Kunne ikke starte AirPlay.');
    if (error) {
      if (error.textContent !== text) error.textContent = text;
      if (error.classList.contains('hidden')) error.classList.remove('hidden');
    }
    const html = '<div class="cast-airplay-note">AirPlay kunne ikke startes. Luk vinduet og prøv igen.</div>';
    if (body && body.innerHTML !== html) body.innerHTML = html;
  }

  async function waitUntilPlayable(session) {
    const token = encodeURIComponent(session.token);
    let state = await api(`/api/airplay-hls/${token}/prepare`, {
      method: 'POST',
      body: JSON.stringify({force:false}),
    });
    const deadline = Date.now() + 60000;
    while (!state.playable) {
      if (state.state === 'error' || state.error) throw new Error(state.error || 'AirPlay-streamen kunne ikke klargøres.');
      if (Date.now() > deadline) throw new Error('AirPlay-streamen blev ikke klar inden for 60 sekunder.');
      setLoading(state);
      await sleep(500);
      state = await api(`/api/airplay-hls/${token}/status`, {}, 10000);
    }
    return state;
  }

  async function startAirPlay(session) {
    if (!session?.token) return setError('AirPlay-sessionen mangler. Luk vinduet og vælg medierne igen.');
    setLoading({});
    try {
      const state = await waitUntilPlayable(session);
      const plugin = nativeAirPlayPlugin();
      if (plugin && typeof plugin.start === 'function') {
        await plugin.start({url:String(state.stream_url || ''), title:String(session.title || 'FjordLens')});
        return;
      }
      window.location.href = `/airplay/control/${encodeURIComponent(session.token)}/play`;
    } catch (error) {
      setError(error?.message || error);
    }
  }

  document.addEventListener('click', event => {
    if (!isIOS()) return;
    const button = event.target?.closest?.('[data-airplay-start]');
    if (!button) return;
    const session = latestSession || window.__fjordlensCastSession || null;
    if (!session?.token) return;
    event.preventDefault();
    event.stopPropagation();
    event.stopImmediatePropagation();
    startAirPlay(session);
  }, true);
})();
