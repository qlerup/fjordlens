(function () {
  'use strict';

  function create({ viewer, getImage, isEnabled = () => true, onGestureStart = () => {} }) {
    const MAX_SCALE = 5;
    let scale = 1;
    let x = 0;
    let y = 0;
    let node = null;
    let gesture = null;
    let owned = false;
    let suppressClickUntil = 0;
    const clamp = (value, limit) => Math.max(-limit, Math.min(limit, value));
    const mediaTarget = target => target === getImage() || target === viewer;

    function reset() {
      if (node) {
        node.style.transform = '';
        node.style.transformOrigin = '';
        node.style.willChange = '';
        node.style.transition = '';
      }
      scale = 1;
      x = y = 0;
      node = null;
      gesture = null;
      owned = false;
      viewer?.classList.remove('viewer-zoomed');
    }

    function paint() {
      if (!node) return;
      const viewport = viewer.getBoundingClientRect();
      const fit = Math.min(node.clientWidth / node.naturalWidth, node.clientHeight / node.naturalHeight);
      // Bound the actual photo, including object-fit's letterboxing, so a pan
      // cannot lose the image outside the screen or expose empty space at edges.
      x = clamp(x, Math.max(0, (node.naturalWidth * fit * scale - viewport.width) / 2));
      y = clamp(y, Math.max(0, (node.naturalHeight * fit * scale - viewport.height) / 2));
      node.style.transition = 'none';
      node.style.transformOrigin = '50% 50%';
      node.style.willChange = 'transform';
      node.style.transform = `translate3d(${x}px, ${y}px, 0) scale(${scale})`;
      viewer.classList.toggle('viewer-zoomed', scale > 1);
    }

    function begin(touches) {
      if (touches.length >= 2) {
        const [a, b] = touches;
        const rect = node.getBoundingClientRect();
        gesture = {
          ids: [a.identifier, b.identifier],
          distance: Math.max(1, Math.hypot(b.clientX - a.clientX, b.clientY - a.clientY)),
          midX: (a.clientX + b.clientX) / 2,
          midY: (a.clientY + b.clientY) / 2,
          centerX: rect.left + rect.width / 2 - x,
          centerY: rect.top + rect.height / 2 - y,
          scale, x, y,
        };
      } else if (touches.length === 1) {
        gesture = { ids: [touches[0].identifier], startX: touches[0].clientX, startY: touches[0].clientY, x, y };
      } else {
        gesture = null;
      }
    }

    function consume(event) {
      if (event.cancelable) event.preventDefault();
      event.stopImmediatePropagation();
      suppressClickUntil = Date.now() + 500;
    }

    function start(event) {
      const image = getImage();
      if (!owned && (!mediaTarget(event.target) || !isEnabled() || !image || !image.naturalWidth)) return;
      if (!owned && event.touches.length < 2 && scale === 1) return;
      if (!owned) {
        // The second finger may arrive after the first started a swipe or a
        // long press. Cancel those before taking ownership of the whole touch.
        onGestureStart();
        node = image;
        owned = true;
      }
      consume(event);
      begin(Array.from(event.touches));
    }

    function move(event) {
      if (!owned || !node) return;
      consume(event);
      const touches = Array.from(event.touches);
      const points = gesture?.ids.map(id => touches.find(touch => touch.identifier === id));
      if (!points || points.some(point => !point)) { begin(touches); return; }
      if (points.length === 2) {
        const [a, b] = points;
        const distance = Math.hypot(b.clientX - a.clientX, b.clientY - a.clientY);
        scale = Math.max(1, Math.min(MAX_SCALE, gesture.scale * distance / gesture.distance));
        const ratio = scale / gesture.scale;
        // Keep the point between the fingers anchored while scaling and moving.
        x = (a.clientX + b.clientX) / 2 - gesture.centerX - (gesture.midX - gesture.centerX - gesture.x) * ratio;
        y = (a.clientY + b.clientY) / 2 - gesture.centerY - (gesture.midY - gesture.centerY - gesture.y) * ratio;
      } else {
        x = gesture.x + points[0].clientX - gesture.startX;
        y = gesture.y + points[0].clientY - gesture.startY;
      }
      paint();
    }

    function end(event) {
      if (!owned) return;
      consume(event);
      if (event.type === 'touchcancel') { reset(); return; }
      if (event.touches.length) {
        begin(Array.from(event.touches));
      } else {
        owned = false;
        gesture = null;
        // Stay in the gesture until ALL fingers lift, even after reaching 1x.
        if (scale <= 1.01) reset();
      }
    }

    if (viewer) {
      const options = { capture: true, passive: false };
      viewer.addEventListener('touchstart', start, options);
      viewer.addEventListener('touchmove', move, options);
      viewer.addEventListener('touchend', end, options);
      viewer.addEventListener('touchcancel', end, options);
      for (const type of ['click', 'mousedown', 'contextmenu']) {
        viewer.addEventListener(type, event => {
          if (mediaTarget(event.target) && (owned || scale > 1 || Date.now() < suppressClickUntil)) consume(event);
        }, true);
      }
      window.addEventListener('resize', reset);
    }
    return { reset, isActive: () => owned || scale > 1 };
  }

  window.FjordLensViewerZoom = { create };
})();
