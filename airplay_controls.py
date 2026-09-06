from __future__ import annotations

import html
import json
import re
from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import quote

from flask import Blueprint, Response, jsonify, request
from flask_login import current_user, login_required

import airplay_hls as hls_core
import cast_airplay as cast_core

bp = Blueprint("airplay_controls", __name__)
_SEGMENT_RE = re.compile(r"^item_(\d{5})_\d{5}\.ts$")


def _can_manage(session: Dict[str, Any]) -> bool:
    try:
        user_id = int(getattr(current_user, "id", 0) or 0)
        owner_id = int(session.get("created_by_user_id") or 0)
    except Exception:
        user_id = 0
        owner_id = -1
    role = str(getattr(current_user, "role", "") or "").lower()
    is_admin = bool(getattr(current_user, "is_admin", False) or role == "admin")
    return bool(is_admin or (user_id > 0 and user_id == owner_id))


def _image_duration(value: Any) -> int:
    try:
        duration = int(value)
    except Exception:
        duration = 5
    return max(2, min(30, duration))


def _timeline(token: str, session: Dict[str, Any], state: Dict[str, Any]) -> Dict[str, Any]:
    manifest = hls_core._manifest_path(token)
    grouped: Dict[int, Dict[str, Any]] = {}
    elapsed = 0.0
    pending: float | None = None

    try:
        lines = manifest.read_text(encoding="utf-8", errors="ignore").splitlines()
    except Exception:
        lines = []

    for raw in lines:
        line = raw.strip()
        if line.startswith("#EXTINF:"):
            try:
                pending = max(0.0, float(line.split(":", 1)[1].split(",", 1)[0]))
            except Exception:
                pending = None
            continue
        if pending is None or not line or line.startswith("#"):
            continue
        match = _SEGMENT_RE.fullmatch(Path(line).name)
        if not match:
            pending = None
            continue
        index = int(match.group(1))
        entry = grouped.get(index)
        if entry is None:
            entry = {"index": index, "start": elapsed, "duration": 0.0}
            grouped[index] = entry
        entry["duration"] = float(entry["duration"]) + pending
        elapsed += pending
        pending = None

    items = [item for item in (session.get("items") or []) if isinstance(item, dict)]
    completed = int(state.get("done") or 0)
    timeline: List[Dict[str, Any]] = []
    for index in sorted(grouped):
        raw = grouped[index]
        item = items[index] if 0 <= index < len(items) else {}
        timeline.append({
            "index": index,
            "start": round(float(raw["start"]), 6),
            "duration": round(float(raw["duration"]), 6),
            "complete": index < completed,
            "kind": str(item.get("kind") or "image"),
            "name": str(item.get("filename") or Path(str(item.get("rel_path") or "")).name or f"#{index + 1}"),
        })

    return {
        "timeline": timeline,
        "available_duration": round(elapsed, 6),
        "total": len(items),
    }


def _status_payload(token: str, session: Dict[str, Any]) -> Dict[str, Any]:
    state = hls_core._read_status(token)
    timeline = _timeline(token, session, state)
    return {
        "ok": state.get("state") != "error",
        "state": str(state.get("state") or "idle"),
        "playable": bool(state.get("playable")),
        "finished": bool(state.get("finished")),
        "done": int(state.get("done") or 0),
        "current": int(state.get("current") or 0),
        "segments": int(state.get("segments") or 0),
        "error": str(state.get("error") or ""),
        "image_duration": int(session.get("image_duration") or 5),
        **timeline,
    }


@bp.post("/api/cast-airplay/session/<token>/duration")
@login_required
def set_duration(token: str):
    session = cast_core._get_session(token)
    if not session:
        return jsonify({"ok": False, "error": "AirPlay-sessionen findes ikke eller er udløbet."}), 404
    if not _can_manage(session):
        return jsonify({"ok": False, "error": "Du kan ikke ændre denne AirPlay-session."}), 403

    state = hls_core._read_status(token)
    if str(state.get("state") or "idle") not in {"idle", ""} or int(state.get("segments") or 0) > 0:
        return jsonify({"ok": False, "error": "Billedtiden kan ikke ændres efter streamen er startet."}), 409

    duration = _image_duration((request.get_json(silent=True) or {}).get("image_duration"))
    session["image_duration"] = duration
    cast_core._put_session(token, session)
    return jsonify({"ok": True, "image_duration": duration})


@bp.get("/api/airplay-controls/<token>/status")
@login_required
def control_status(token: str):
    session = cast_core._get_session(token)
    if not session:
        return jsonify({"ok": False, "error": "AirPlay-sessionen findes ikke eller er udløbet."}), 404
    if not _can_manage(session):
        return jsonify({"ok": False, "error": "Du kan ikke styre denne AirPlay-session."}), 403
    response = jsonify(_status_payload(token, session))
    response.headers["Cache-Control"] = "no-store"
    return response


@bp.get("/airplay/control/<token>/play")
@login_required
def control_player(token: str):
    session = cast_core._get_session(token)
    if not session:
        return Response("AirPlay-sessionen findes ikke eller er udløbet.", status=404, mimetype="text/plain")
    if not _can_manage(session):
        return Response("Du kan ikke styre denne AirPlay-session.", status=403, mimetype="text/plain")

    token_q = quote(token, safe="")
    stream_url = f"/airplay/hls/{token_q}/index.m3u8"
    status_url = f"/api/airplay-controls/{token_q}/status"
    title = html.escape(str(session.get("title") or "FjordLens"))

    page = """<!doctype html>
<html lang="da">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>FjordLens AirPlay</title>
<style>
:root { color-scheme: dark; }
* { box-sizing: border-box; }
html,body { margin:0; min-height:100%; background:#061218; color:#eef7f7; font-family:system-ui,-apple-system,sans-serif; }
body { min-height:100dvh; display:flex; flex-direction:column; }
header { display:flex; align-items:center; justify-content:space-between; gap:12px; padding:12px 14px; border-bottom:1px solid rgba(255,255,255,.12); }
header strong { min-width:0; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; font-size:15px; }
button { appearance:none; border:1px solid rgba(255,255,255,.16); border-radius:12px; background:#10252d; color:#eef7f7; min-height:44px; padding:10px 14px; font:inherit; font-weight:650; }
button:disabled { opacity:.45; }
#airplay { background:#0f8d86; border-color:#20bcb0; }
#viewer { flex:1; min-height:0; display:grid; place-items:center; padding:10px; }
#stage { width:min(100%, 1000px); aspect-ratio:16/9; max-height:58dvh; background:#000; display:grid; place-items:center; overflow:hidden; border-radius:10px; }
video { width:100%; height:100%; object-fit:contain; background:#000; }
#controls { padding:10px 14px calc(12px + env(safe-area-inset-bottom)); border-top:1px solid rgba(255,255,255,.12); display:grid; gap:10px; }
#meta { display:grid; grid-template-columns:1fr auto; gap:10px; align-items:center; font-size:12px; color:#aebfc4; }
#counter { color:#eef7f7; font-weight:700; }
#scrub { width:100%; accent-color:#20bcb0; }
#time { text-align:right; font-variant-numeric:tabular-nums; }
#buttons { display:grid; grid-template-columns:1fr 1fr; gap:10px; }
#status { min-height:18px; text-align:center; font-size:12px; color:#9fb0b6; }
@media (min-width:700px) { #controls { width:min(760px,100%); margin:0 auto; } }
</style>
</head>
<body>
<header><strong>__TITLE__</strong><button id="airplay" type="button">Vælg AirPlay</button></header>
<div id="viewer"><div id="stage"><video id="video" controls autoplay playsinline preload="auto" x-webkit-airplay="allow" src=__STREAM__></video></div></div>
<div id="controls">
  <div id="meta"><span id="counter">1 / 1</span><span id="time">0:00 / 0:00</span></div>
  <input id="scrub" type="range" min="0" max="0" step="0.1" value="0" aria-label="Spol i slideshow">
  <div id="buttons"><button id="prev" type="button">‹ Forrige</button><button id="next" type="button">Næste ›</button></div>
  <div id="status">Klargør slideshow…</div>
</div>
<script>
(() => {
  'use strict';
  const statusUrl = __STATUS__;
  const video = document.getElementById('video');
  const airplay = document.getElementById('airplay');
  const prev = document.getElementById('prev');
  const next = document.getElementById('next');
  const scrub = document.getElementById('scrub');
  const counter = document.getElementById('counter');
  const time = document.getElementById('time');
  const statusEl = document.getElementById('status');
  let state = {timeline:[], total:0, available_duration:0, finished:false, done:0};
  let scrubbing = false;
  let jumping = false;

  const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
  const fmt = value => {
    const seconds = Math.max(0, Math.floor(Number(value) || 0));
    const m = Math.floor(seconds / 60);
    const s = String(seconds % 60).padStart(2, '0');
    return `${m}:${s}`;
  };
  const entryFor = index => (state.timeline || []).find(item => Number(item.index) === Number(index)) || null;
  function currentIndex() {
    const timeline = state.timeline || [];
    if (!timeline.length) return 0;
    const t = Number(video.currentTime || 0) + 0.08;
    let index = Number(timeline[0].index || 0);
    for (const entry of timeline) {
      if (t >= Number(entry.start || 0)) index = Number(entry.index || 0);
      else break;
    }
    return index;
  }
  function seekableTarget(value) {
    let target = Math.max(0, Number(value) || 0);
    try {
      if (video.seekable && video.seekable.length) {
        const first = video.seekable.start(0);
        const last = video.seekable.end(video.seekable.length - 1);
        target = Math.min(Math.max(target, first), Math.max(first, last - 0.03));
      }
    } catch (_) {}
    return target;
  }
  function updateUi() {
    const total = Math.max(1, Number(state.total || 0));
    const index = Math.min(total - 1, Math.max(0, currentIndex()));
    counter.textContent = `${index + 1} / ${total}`;
    const duration = Math.max(Number(state.available_duration || 0), Number.isFinite(video.duration) ? Number(video.duration) : 0, 0);
    scrub.max = String(Math.max(0.1, duration));
    if (!scrubbing) scrub.value = String(Math.min(duration, Math.max(0, Number(video.currentTime || 0))));
    time.textContent = `${fmt(video.currentTime)} / ${fmt(duration)}`;
    if (state.error) statusEl.textContent = state.error;
    else if (!state.finished) statusEl.textContent = `Klargør ${Math.min(Number(state.done || 0) + 1, total)} / ${total} i baggrunden…`;
    else statusEl.textContent = 'Slideshowet er klar';
  }
  async function refreshStatus() {
    try {
      const response = await fetch(statusUrl, {credentials:'same-origin', cache:'no-store'});
      const data = await response.json();
      if (!response.ok || !data.ok) throw new Error(data.error || `HTTP ${response.status}`);
      state = data;
      updateUi();
      return data;
    } catch (error) {
      statusEl.textContent = String(error?.message || error || 'Kunne ikke hente status.');
      return state;
    }
  }
  async function waitForEntry(index, timeoutMs = 9000) {
    const deadline = Date.now() + timeoutMs;
    let entry = entryFor(index);
    while (!entry && Date.now() < deadline && !state.finished) {
      statusEl.textContent = `Klargør medie ${index + 1}…`;
      await sleep(350);
      await refreshStatus();
      entry = entryFor(index);
    }
    return entry;
  }
  async function seekToIndex(index) {
    if (jumping) return;
    jumping = true;
    try {
      const total = Number(state.total || 0);
      if (!total) return;
      if (index < 0) index = state.finished ? total - 1 : 0;
      if (index >= total) index = state.finished ? 0 : total - 1;
      let entry = entryFor(index);
      if (!entry) entry = await waitForEntry(index);
      if (!entry) {
        statusEl.textContent = 'Det næste medie er ikke klar endnu.';
        return;
      }
      video.currentTime = seekableTarget(Number(entry.start || 0) + 0.05);
      try { await video.play(); } catch (_) {}
      updateUi();
    } finally {
      jumping = false;
    }
  }

  prev.addEventListener('click', async () => {
    const index = currentIndex();
    const entry = entryFor(index);
    const into = entry ? Number(video.currentTime || 0) - Number(entry.start || 0) : 0;
    await seekToIndex(into > 1.5 ? index : index - 1);
  });
  next.addEventListener('click', () => seekToIndex(currentIndex() + 1));
  scrub.addEventListener('input', () => {
    scrubbing = true;
    time.textContent = `${fmt(scrub.value)} / ${fmt(scrub.max)}`;
  });
  scrub.addEventListener('change', async () => {
    video.currentTime = seekableTarget(scrub.value);
    scrubbing = false;
    try { await video.play(); } catch (_) {}
    updateUi();
  });
  video.addEventListener('timeupdate', updateUi);
  video.addEventListener('durationchange', updateUi);
  video.addEventListener('progress', updateUi);
  video.addEventListener('loadedmetadata', () => { updateUi(); video.play().catch(() => {}); });

  if (typeof video.webkitShowPlaybackTargetPicker === 'function') {
    airplay.addEventListener('click', () => { try { video.webkitShowPlaybackTargetPicker(); } catch (_) {} });
  } else {
    airplay.style.display = 'none';
  }

  refreshStatus();
  const poll = setInterval(async () => {
    await refreshStatus();
    if (state.finished) clearInterval(poll);
  }, 750);
})();
</script>
</body></html>"""
    page = page.replace("__TITLE__", title)
    page = page.replace("__STREAM__", json.dumps(stream_url))
    page = page.replace("__STATUS__", json.dumps(status_url))
    response = Response(page, mimetype="text/html")
    response.headers["Cache-Control"] = "no-store"
    return response


def init_airplay_controls(flask_app) -> None:
    if "airplay_controls" not in flask_app.blueprints:
        flask_app.register_blueprint(bp)
