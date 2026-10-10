(() => {
  const panel = document.getElementById('chatgptConnectionPanel');
  if (!panel) return;
  const status = document.getElementById('chatgptConnectionStatus');
  const error = document.getElementById('chatgptConnectionError');
  const connect = document.getElementById('chatgptConnectBtn');
  const disconnect = document.getElementById('chatgptDisconnectBtn');
  const retry = document.getElementById('chatgptRetryBtn');
  const steps = document.getElementById('chatgptLoginSteps');
  const file = document.getElementById('chatgptConnectionFile');
  let csrf = '', busy = false;
  function showError(message) {
    error.textContent = message;
    error.classList.toggle('hidden', !message);
  }
  function render(data) {
    status.textContent = data.connected
      ? `ChatGPT tilsluttet${data.email ? ` · ${data.email}` : ''} · Billedbehandling er endnu ikke aktiveret`
      : 'ChatGPT er ikke tilsluttet';
    disconnect.classList.toggle('hidden', !data.connected);
    connect.textContent = data.connected ? 'Tilslut en anden ChatGPT-konto' : 'Fortsæt med ChatGPT';
  }
  async function call(options = {}) {
    const response = await fetch('/api/ai/chatgpt/connection', {
      ...options, cache: 'no-store', headers: {'X-ChatGPT-CSRF': csrf},
      signal: AbortSignal.timeout(30000),
    });
    const data = await response.json();
    if (!response.ok || !data.ok) throw new Error(data.error || 'ChatGPT-forbindelsen kunne ikke indlæses.');
    return data;
  }
  async function load() {
    if (busy) return;
    busy = true;
    try {
      const data = await call();
      csrf = data.csrf; render(data); showError(''); retry.classList.add('hidden');
    } catch (err) {
      status.textContent = 'Kontostatus kunne ikke hentes'; showError(err.message); retry.classList.remove('hidden');
    } finally { busy = false; connect.disabled = !csrf; }
  }
  connect.addEventListener('click', () => { steps.classList.remove('hidden'); showError(''); });
  retry.addEventListener('click', load);
  file.addEventListener('change', async () => {
    if (!file.files[0] || busy) return;
    if (file.files[0].size > 65536) { showError('Forbindelsesfilen er for stor.'); file.value = ''; return; }
    busy = true; file.disabled = true; disconnect.disabled = true; connect.disabled = true;
    try {
      const body = new FormData(); body.set('connection', file.files[0]);
      render(await call({method: 'POST', body})); steps.classList.add('hidden'); showError('');
    } catch (err) { showError(err.message); }
    finally { file.value = ''; file.disabled = false; disconnect.disabled = false; connect.disabled = false; busy = false; }
  });
  disconnect.addEventListener('click', async () => {
    if (busy) return;
    busy = true; disconnect.disabled = true; connect.disabled = true;
    try { render(await call({method: 'DELETE'})); steps.classList.add('hidden'); showError(''); }
    catch (err) { showError(err.message); }
    finally { busy = false; disconnect.disabled = false; connect.disabled = false; }
  });
  let inSettings = document.body.classList.contains('view-settings');
  new MutationObserver(() => {
    const now = document.body.classList.contains('view-settings');
    if (now && !inSettings) load();
    inSettings = now;
  }).observe(document.body, {attributes: true, attributeFilter: ['class']});
  if (inSettings) load();
})();
