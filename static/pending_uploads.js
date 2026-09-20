document.addEventListener('DOMContentLoaded', () => {
  const root = document.getElementById('pendingUploadRecovery');
  if (!root) return;
  const scan = root.querySelector('[data-scan]');
  const status = root.querySelector('[data-status]');
  const bar = root.querySelector('[data-progress]');
  const endpoint = '/api/uploads/pending-recovery';
  const stages = {checking: 'Forbereder', waiting: 'Venter på igangværende efterbehandling', converting: 'Konverterer',
    metadata: 'Metadata', thumbnails: 'Miniaturer', faces: 'Ansigter', embeddings: 'AI-embedding',
    descriptions: 'AI-beskrivelser', parallel: 'Efterbehandler', done: 'Afslutter', stopped: 'Stoppet', error: 'Fejl'};
  let timer;
  async function request(body) {
    const response = await fetch(endpoint, body ? {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)} : {});
    const data = await response.json();
    if (!response.ok || !data.ok) throw new Error(data.error || 'Kunne ikke hente ventende uploads');
    return data;
  }
  async function poll() {
    clearTimeout(timer);
    try {
      const data = await request();
      scan.disabled = !!data.running;
      const pr = data.running ? (data.progress || {}) : data.result;
      bar.hidden = !pr;
      if (!pr) { status.textContent = 'Søg for at finde filer, der venter på efterbehandling.'; return; }
      if (pr.ok === false) { status.textContent = pr.error; bar.hidden = true; return; }
      const total = Number(pr.total || 0), done = Number(pr.processed || 0);
      if (total) bar.value = Math.round(done / total * 100); else bar.removeAttribute('value');
      if (data.running) {
        const stage = stages[pr.phase] || 'Efterbehandler';
        const current = pr.current_rel ? ` · ${pr.current_rel}` : '';
        const detail = pr.stage_total ? ` · Trin: ${pr.stage_processed || 0}/${pr.stage_total}` : '';
        status.textContent = `${stage} · ${done}/${total} filer gennemgået${detail}${current}`;
        if (pr.process_status) {
          status.textContent += ' · ' + Object.entries(pr.process_status).filter(([,value]) => value.enabled)
            .map(([name, value]) => `${stages[name] || name}: ${value.processed}/${value.total}`).join(' · ');
        }
        timer = setTimeout(poll, 1200);
      } else {
        status.textContent = `${pr.stopped ? 'Stoppet' : 'Gennemgang færdig'}: ${done}/${total} filer gennemgået · ${pr.errors || 0} fejl · ${pr.remaining || 0} filer på genoptagelseslisten`;
      }
    } catch (error) {
      status.textContent = error.message;
      timer = setTimeout(poll, 3000);
    }
  }
  scan.onclick = async () => {
    clearTimeout(timer);
    scan.disabled = true;
    status.textContent = 'Søger efter ventende filer…';
    bar.hidden = false;
    bar.removeAttribute('value');
    try {
      const found = await request({action: 'scan'});
      status.textContent = `Fundet ${found.count} filer, der venter på efterbehandling.`;
      bar.hidden = true;
      if (!found.count || !window.confirm(`Fundet ${found.count} ventende filer. Ønsker du at færdigbehandle filerne?`)) {
        scan.disabled = false;
        return;
      }
      await request({action: 'start', token: found.token});
      await poll();
    } catch (error) {
      status.textContent = error.message;
      scan.disabled = false;
      bar.hidden = true;
    }
  };
  void poll();
});
