/* A soundtrack continues across slides. Audio-clock scheduling avoids loop gaps. */
class MomentSoundtrack {
  constructor(track, onStatus = () => {}) {
    this.track = track;
    this.onStatus = onStatus;
    this.abort = new AbortController();
    this.sources = new Set();
    this.stopped = false;
    this.muted = false;
  }
  async start({hold = false} = {}) {
    if (!this.track || this.stopped) return;
    this.held = hold;
    try {
      const Context = window.AudioContext || window.webkitAudioContext;
      this.context = new Context();
      this.context.onstatechange = () => this.status();
      // Request during the initiating click; a public autoplay may need another tap.
      this.context.resume().catch(() => {});
      this.gain = this.context.createGain();
      this.gain.gain.value = this.track.volume ?? .23;
      this.gain.connect(this.context.destination);
      this.onStatus('Henter musik…');
      const response = await fetch(this.track.url, {signal:this.abort.signal});
      if (!response.ok) throw new Error('Musikken kunne ikke hentes');
      this.buffer = await this.context.decodeAudioData(await response.arrayBuffer());
      if (this.stopped) return;
      this.begin = Math.max(0, this.track.trim_start || 0);
      this.duration = Math.min(this.buffer.duration, this.track.trim_end || this.buffer.duration) - this.begin;
      this.fade = Math.min(this.track.crossfade || 6, this.duration / 3);
      if (!this.held) this.play();
    } catch (error) {
      if (!this.stopped) { this.failed = true; this.onStatus('Musik utilgængelig'); }
    }
  }
  play() {
    this.held = false;
    if (!this.buffer || this.stopped || this.timer) return;
    this.next = this.context.currentTime + .06;
    this.first = true;
    this.schedule();
    this.timer = setInterval(() => this.schedule(), 1000);
    this.status();
  }
  schedule() {
    if (this.stopped || !this.buffer) return;
    const ctx = this.context;
    // Two track lengths ahead also survives ordinary background timer throttling.
    while (this.next < ctx.currentTime + this.duration * 2) {
      const source = ctx.createBufferSource(), envelope = ctx.createGain();
      source.buffer = this.buffer;
      source.connect(envelope); envelope.connect(this.gain);
      const incoming = new Float32Array(128), outgoing = new Float32Array(128);
      for (let i=0;i<128;i++) { incoming[i] = Math.sin(i/127*Math.PI/2); outgoing[i] = Math.cos(i/127*Math.PI/2); }
      envelope.gain.setValueCurveAtTime(incoming, this.next, this.first ? Math.min(1.5,this.fade) : this.fade);
      envelope.gain.setValueAtTime(1, this.next + this.duration - this.fade);
      envelope.gain.setValueCurveAtTime(outgoing, this.next + this.duration - this.fade, this.fade);
      source.start(this.next, this.begin, this.duration);
      this.sources.add(source);
      source.onended = () => { this.sources.delete(source); source.disconnect(); envelope.disconnect(); };
      this.next += this.duration - this.fade;
      this.first = false;
    }
  }
  status() {
    if (this.stopped || this.failed) return;
    if (!this.buffer) return;
    this.onStatus(this.muted || this.context.state !== 'running' ? 'Slå musik til' : 'Slå musik fra');
  }
  toggle() {
    if (!this.context || this.failed || this.stopped) return;
    if (this.context.state !== 'running') { this.muted = false; this.context.resume().catch(() => {}); }
    else this.muted = !this.muted;
    this.gain.gain.setTargetAtTime(this.muted ? 0 : (this.track.volume ?? .23), this.context.currentTime, .08);
    this.status();
  }
  volume(value) {
    this.track.volume = value;
    if (this.gain && !this.muted) this.gain.gain.setTargetAtTime(value, this.context.currentTime, .08);
  }
  pause() { if (this.context?.state === 'running') { this.wasRunning = true; this.context.suspend().catch(() => {}); } }
  resume() { if (this.wasRunning && !this.stopped) { this.wasRunning = false; this.context.resume().catch(() => {}); } }
  stop() {
    this.stopped = true; this.abort.abort(); clearInterval(this.timer);
    this.sources.forEach(s => { try { s.stop(); } catch {} }); this.sources.clear();
    if (this.context && this.context.state !== 'closed') this.context.close().catch(() => {});
    this.buffer = null;
  }
}

function momentStartMusic(player, options = {}) {
  player.soundtrack?.stop();
  let button = document.getElementById('momentPlayerMusicBtn');
  if (!button) {
    button = document.createElement('button'); button.type = 'button';
    button.className = 'btn'; button.id = 'momentPlayerMusicBtn';
    els.momentPlayerOverlay?.querySelector('.moment-player-footer')?.append(button);
  }
  button.hidden = !player.music;
  if (!player.music) return;
  button.title = player.music.title;
  player.soundtrack = new MomentSoundtrack({...player.music}, label => {
    button.textContent = label;
    button.setAttribute('aria-label', `${label} · ${player.music.title}`);
  });
  button.onclick = event => {
    event.preventDefault(); event.stopPropagation();
    if (event.detail > 0 && performance.now() < (els.momentPlayerOverlay._fullscreenInputUntil || 0)) return;
    player.soundtrack.toggle();
  };
  button.onpointerdown = event => {
    if (event.isPrimary && event.button === 0) button.setPointerCapture(event.pointerId);
    event.stopPropagation();
  };
  player.soundtrack.start(options);
}
