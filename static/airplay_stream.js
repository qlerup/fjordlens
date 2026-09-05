(() => {
  'use strict';

  let latestSession = null;
  const nativeFetch = window.fetch.bind(window);

  const isIOS = () => /iPhone|iPad|iPod/i.test(String(navigator.userAgent || ''));
  const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));

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

  function setModalLoading(done = 0, total = 0) {
    const body = document.getElementById('castAirplayBody');
    const sub = document.getElementById('castAirplaySub');
    const error = document.getElementById('castAirplayError');
    if (error) { error.textContent = ''; error.classList.add('hidden'); }
    if (sub) sub.textContent = total > 0 ? `Klargør AirPlay · ${done}/${total}` : 'Klargør AirPlay…';
    if (body) body.innerHTML = `<div class="cast-airplay-loading"><strong>AirPlay-slideshow klargøres</strong><br><span style="opacity:.75">${total > 0 ? `${done} af ${total} medier` : 'Det kan tage lidt tid første gang.'}</span></div>`;
  }

  function setModalError(message) {
    const error = document.getElementById('castAirplayError');
    const body = document.getElementById('castAirplayBody');
    if (error) { error.textContent = String(message || 'Kunne ikke klargøre AirPlay.'); error.classList.remove('hidden'); }
    if (body) body.innerHTML = '<div class="cast-airplay-note">Prøv igen, eller vælg færre billeder/videoer.</div>';
  }

  async function startTrueAirplay(session) {
    if (!session?.token) return;
    setModalLoading();
    try {
      let state = await api(`/api/airplay/${encodeURIComponent(session.token)}/prepare`, {method:'POST'});
      const deadline = Date.now() + 20 * 60 * 1000;
      while (!state.ready) {
        if (state.state === 'error' || state.error) throw new Error(state.error || 'AirPlay-klargøringen fejlede.');
        setModalLoading(Number(state.done || 0), Number(state.total || 0));
        if (Date.now() > deadline) throw new Error('AirPlay-klargøringen tog for lang tid.');
        await sleep(850);
        state = await api(`/api/airplay/${encodeURIComponent(session.token)}/status`);
      }
      window.location.href = String(state.play_url || `/airplay/play/${encodeURIComponent(session.token)}`);
    } catch (error) {
      setModalError(error?.message || error);
    }
  }

  document.addEventListener('click', event => {
    if (!isIOS()) return;
    const button = event.target?.closest?.('[data-airplay-start]');
    if (!button || !latestSession?.token) return;
    event.preventDefault();
    event.stopPropagation();
    event.stopImmediatePropagation();
    startTrueAirplay(latestSession);
  }, true);

  const observer = new MutationObserver(() => {
    if (!isIOS() || !latestSession?.token) return;
    const choice = document.querySelector('#castAirplayBody .cast-airplay-choice p');
    if (!choice) return;
    const text = String(choice.textContent || '');
    if (/Skærmdublering|Screen Mirroring/i.test(text)) {
      choice.textContent = 'FjordLens laver de valgte billeder og videoer om til ét AirPlay-slideshow. Det sendes direkte til Apple TV/skærmen uden Skærmdublering.';
    }
    const button = document.querySelector('#castAirplayBody [data-airplay-start]');
    if (button && button.textContent !== 'Klargør AirPlay') button.textContent = 'Klargør AirPlay';
  });

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => observer.observe(document.body, {subtree:true, childList:true}), {once:true});
  } else {
    observer.observe(document.body, {subtree:true, childList:true});
  }
})();
