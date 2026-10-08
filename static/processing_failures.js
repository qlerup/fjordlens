document.addEventListener('DOMContentLoaded', () => {
  const root = document.getElementById('processingFailures');
  if (!root) return;
  const status = root.querySelector('[data-status]');
  const list = root.querySelector('[data-list]');
  const retry = root.querySelector('[data-retry]');
  const refresh = root.querySelector('[data-refresh]');
  const labels = {thumbnails: 'Miniature', metadata: 'Metadata', conversion: 'Konvertering', faces: 'Ansigter',
    descriptions: 'AI-beskrivelse', embeddings: 'AI-embedding'};
  let timer;
  let loading = false;
  let reloadRequested = false;
  async function load() {
    if (loading) { reloadRequested = true; return; }
    loading = true;
    clearTimeout(timer);
    refresh.disabled = true;
    try {
      const response = await fetch('/api/processing-failures');
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Kunne ikke hente fejl');
      list.replaceChildren();
      const items = data.items || [];
      const files = new Set(items.map(item => item.rel_path)).size;
      status.textContent = data.running
        ? `Genkører ${data.progress.processed}/${data.progress.total} · ${data.progress.current || 'Venter'}`
        : `${files} filer med ${items.length} fejlede trin`;
      for (const item of items) {
        const row = document.createElement('div');
        row.style.cssText = 'padding:8px 0;border-bottom:1px solid var(--border);overflow-wrap:anywhere;';
        const title = document.createElement('strong');
        title.textContent = `${labels[item.stage] || item.stage} · ${item.rel_path}`;
        const error = document.createElement('div');
        error.className = 'mini-label';
        error.textContent = item.error;
        const button = document.createElement('button');
        button.className = 'btn small';
        button.textContent = 'Prøv igen';
        button.disabled = data.running;
        button.onclick = () => start([item.id]);
        const clear = document.createElement('button');
        clear.className = 'btn small';
        clear.textContent = 'Ryd';
        clear.title = 'Ryd fejl for denne fil fra begge lister. Filen slettes ikke.';
        clear.onclick = async () => {
          clear.disabled = true;
          try {
            const response = await fetch(`/api/processing-failures/${item.id}/clear`, {method: 'POST'});
            const result = await response.json();
            if (!response.ok || !result.ok) throw new Error(result.error || 'Kunne ikke rydde fejl');
            document.dispatchEvent(new Event('fjordlens:errors-cleared'));
            if (typeof refreshResolvedLogs === 'function') await refreshResolvedLogs();
          } catch (error) { status.textContent = error.message; clear.disabled = false; }
        };
        row.append(title, error, button, clear);
        list.append(row);
      }
      retry.disabled = data.running || !items.length;
      if (data.running) timer = setTimeout(load, 1500);
    } catch (error) {
      status.textContent = error.message;
      retry.disabled = true;
    } finally {
      loading = false;
      refresh.disabled = false;
      if (reloadRequested) { reloadRequested = false; queueMicrotask(load); }
    }
  }
  async function start(ids) {
    retry.disabled = true;
    try {
      const response = await fetch('/api/processing-failures', {method: 'POST',
        headers: {'Content-Type': 'application/json'}, body: JSON.stringify(ids ? {ids} : {})});
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Kunne ikke starte genkørsel');
      await load();
    } catch (error) {
      status.textContent = error.message;
      retry.disabled = false;
    }
  }
  refresh.onclick = load;
  retry.onclick = () => start();
  document.addEventListener('fjordlens:errors-cleared', load);
});
