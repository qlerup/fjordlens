(() => {
  const panel = document.getElementById('chatgptConnectionPanel');
  if (!panel) return;
  const status = document.getElementById('chatgptConnectionStatus');
  const error = document.getElementById('chatgptConnectionError');
  const connect = document.getElementById('chatgptConnectBtn');
  const disconnect = document.getElementById('chatgptDisconnectBtn');
  const cancel = document.getElementById('chatgptCancelBtn');
  const retry = document.getElementById('chatgptRetryBtn');
  const steps = document.getElementById('chatgptLoginSteps');
  const code = document.getElementById('chatgptDeviceCode');
  const link = document.getElementById('chatgptVerifyLink');
  let csrf = '', busy = false, pending = false, timer = null;
  function showError(message) {
    error.textContent = message;
    error.classList.toggle('hidden', !message);
  }
  function buttons() {
    connect.disabled = busy || pending || !csrf;
    disconnect.disabled = busy;
    cancel.disabled = busy;
    retry.disabled = busy;
  }
  function render(data) {
    clearTimeout(timer);
    const login = data.login || {};
    pending = ['starting', 'waiting', 'busy'].includes(login.state);
    status.textContent = data.connected
      ? `ChatGPT tilsluttet${data.email ? ` · ${data.email}` : ''}${data.plan ? ` · ${data.plan}` : ''} · Billedbehandling kommer i næste trin`
      : 'ChatGPT er ikke tilsluttet';
    if (login.state === 'starting') status.textContent += ' · Opretter login …';
    if (login.state === 'waiting') status.textContent += ' · Venter på din godkendelse hos OpenAI';
    if (login.state === 'busy') status.textContent += ' · En anden administrator er ved at logge ind';
    disconnect.classList.toggle('hidden', !data.connected);
    cancel.classList.toggle('hidden', !['starting', 'waiting'].includes(login.state));
    connect.textContent = data.connected ? 'Tilslut en anden ChatGPT-konto' : 'Fortsæt med ChatGPT';
    steps.classList.add('hidden'); code.value = ''; link.removeAttribute('href');
    if (login.state === 'waiting') {
      const url = new URL(login.verification_url);
      if (url.protocol !== 'https:' || url.hostname !== 'auth.openai.com' || url.username || url.password) {
        throw new Error('OpenAI-loginadressen kunne ikke bekræftes.');
      }
      code.value = login.user_code;
      link.href = url.href;
      steps.classList.remove('hidden');
    }
    showError(login.state === 'failed' ? login.error : login.state === 'expired' ? 'Login udløb. Tryk Fortsæt med ChatGPT for at prøve igen.' : '');
    if (pending && document.body.classList.contains('view-settings')) timer = setTimeout(load, 2000);
    buttons();
  }
  async function call(path = 'connection', options = {}) {
    const response = await fetch(`/api/ai/chatgpt/${path}`, {
      ...options, cache: 'no-store', headers: {'X-ChatGPT-CSRF': csrf},
      signal: AbortSignal.timeout(30000),
    });
    const data = await response.json();
    if (!response.ok || !data.ok) throw new Error(data.error || 'ChatGPT-forbindelsen kunne ikke indlæses.');
    return data;
  }
  async function load() {
    if (busy) return;
    busy = true; buttons();
    try {
      const data = await call();
      csrf = data.csrf; render(data); retry.classList.add('hidden');
    } catch (err) {
      showError(err.message); retry.classList.remove('hidden');
      // Retain the current code/account while reconnecting to the server.
      if (pending && document.body.classList.contains('view-settings')) timer = setTimeout(load, 5000);
    } finally { busy = false; buttons(); }
  }
  async function mutate(path, method) {
    if (busy) return;
    clearTimeout(timer); busy = true; buttons();
    try { render(await call(path, {method})); retry.classList.add('hidden'); }
    catch (err) { showError(err.message); retry.classList.remove('hidden'); }
    finally { busy = false; buttons(); }
  }
  connect.addEventListener('click', () => mutate('login', 'POST'));
  cancel.addEventListener('click', () => mutate('login', 'DELETE'));
  disconnect.addEventListener('click', () => mutate('connection', 'DELETE'));
  retry.addEventListener('click', load);
  code.addEventListener('click', () => code.select());
  let inSettings = document.body.classList.contains('view-settings');
  new MutationObserver(() => {
    const now = document.body.classList.contains('view-settings');
    if (now && !inSettings) load();
    if (!now) { clearTimeout(timer); code.value = ''; link.removeAttribute('href'); steps.classList.add('hidden'); }
    inSettings = now;
  }).observe(document.body, {attributes: true, attributeFilter: ['class']});
  if (inSettings) load();
})();
