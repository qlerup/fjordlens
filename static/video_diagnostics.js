(function () {
  'use strict';

  // Snapshot before awaiting anything: the viewer can move to another item
  // while the diagnostic HEAD request is in flight.
  async function report(video, item, endpoint) {
    if (!video?.error || !item?.is_video || !Number.isInteger(Number(item.id))) return;
    const url = video.currentSrc || video.getAttribute('src');
    if (!url) return;
    const data = {
      code: video.error.code,
      message: String(video.error.message || '').slice(0, 300),
      network_state: video.networkState,
      ready_state: video.readyState,
    };
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 8000);
    try {
      // HEAD inspects the failed resource without downloading the video again.
      const response = await fetch(url, {method: 'HEAD', credentials: 'same-origin', cache: 'no-store', signal: controller.signal});
      data.http_status = response.status;
      data.content_type = response.headers.get('Content-Type') || '';
      data.accept_ranges = response.headers.get('Accept-Ranges') || '';
      data.redirected = response.redirected;
    } catch (error) {
      data.probe_error = String(error.name || 'Error');
    } finally {
      clearTimeout(timer);
    }
    try {
      await fetch(endpoint, {
        method: 'POST', credentials: 'same-origin', keepalive: true,
        headers: {'Content-Type': 'application/json'}, body: JSON.stringify(data),
      });
    } catch (error) {
      console.warn('FjordLens video diagnostic could not be saved', error);
    }
  }

  window.FjordLensVideoDiagnostics = {report};
})();
