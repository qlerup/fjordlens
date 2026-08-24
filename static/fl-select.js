/* FjordLens custom dropdown: progressiv forbedring af <select class="select">.
   Den native <select> bliver i DOM'en (skjult) og er fortsat sandheden:
   - valg i menuen sætter select.value og affyrer 'change' (bubbles)
   - programmatiske ændringer (value, disabled, style.display, option-tekster)
     spejles automatisk ind i den synlige widget via observer + value-hook */
(function () {
  'use strict';

  var openInstance = null;
  var valueDesc = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value');

  var CARET_SVG =
    '<svg class="fl-select-caret" viewBox="0 0 12 12" aria-hidden="true">' +
    '<path d="M2.5 4.25 6 7.75l3.5-3.5" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>';
  var CHECK_SVG =
    '<svg class="fl-select-check" viewBox="0 0 12 12" aria-hidden="true">' +
    '<path d="M2.2 6.4 4.8 9l5-6" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/></svg>';

  function enhance(select) {
    if (!select || select.dataset.flSelect === '1') return;
    select.dataset.flSelect = '1';

    var wrap = document.createElement('div');
    // Behold layout-klasser (fx .mapper-sort-select) på wrapperen, men ikke .select
    var extraClasses = Array.prototype.filter.call(select.classList, function (c) { return c !== 'select'; });
    wrap.className = ['fl-select'].concat(extraClasses).join(' ');

    var btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'fl-select-btn';
    btn.setAttribute('aria-haspopup', 'listbox');
    btn.setAttribute('aria-expanded', 'false');
    if (select.getAttribute('aria-label')) btn.setAttribute('aria-label', select.getAttribute('aria-label'));
    btn.innerHTML = '<span class="fl-select-label"></span>' + CARET_SVG;
    var label = btn.querySelector('.fl-select-label');

    var menu = document.createElement('div');
    menu.className = 'fl-select-menu';
    menu.setAttribute('role', 'listbox');

    select.parentNode.insertBefore(wrap, select);
    wrap.appendChild(select);
    wrap.appendChild(btn);
    wrap.appendChild(menu);

    function items() {
      return Array.prototype.slice.call(menu.querySelectorAll('.fl-select-item'));
    }

    function rebuild() {
      menu.innerHTML = '';
      Array.prototype.forEach.call(select.options, function (opt) {
        var item = document.createElement('button');
        item.type = 'button';
        item.className = 'fl-select-item';
        item.setAttribute('role', 'option');
        item.dataset.value = opt.value;
        item.innerHTML = '<span class="fl-select-item-label"></span>' + CHECK_SVG;
        item.querySelector('.fl-select-item-label').textContent = opt.textContent;
        item.addEventListener('click', function () { choose(opt.value); });
        menu.appendChild(item);
      });
    }

    function sync() {
      var opt = select.options[select.selectedIndex];
      label.textContent = opt ? opt.textContent : '';
      btn.disabled = !!select.disabled;
      wrap.classList.toggle('is-disabled', !!select.disabled);
      // Spejl app'ens show/hide af den native select
      wrap.style.display = select.style.display === 'none' ? 'none' : '';
      items().forEach(function (item) {
        var sel = item.dataset.value === select.value;
        item.classList.toggle('is-selected', sel);
        item.setAttribute('aria-selected', sel ? 'true' : 'false');
      });
      if (select.disabled && openInstance === api) close(false);
    }

    var syncQueued = false;
    function scheduleSync() {
      if (syncQueued) return;
      syncQueued = true;
      requestAnimationFrame(function () {
        syncQueued = false;
        rebuild();
        sync();
      });
    }

    function choose(value) {
      if (valueDesc && valueDesc.set) valueDesc.set.call(select, value);
      select.dispatchEvent(new Event('change', { bubbles: true }));
      sync();
      close(true);
    }

    function open() {
      if (btn.disabled) return;
      if (openInstance && openInstance !== api) openInstance.close(false);
      openInstance = api;
      wrap.classList.add('open');
      btn.setAttribute('aria-expanded', 'true');
      var current = menu.querySelector('.fl-select-item.is-selected') || items()[0];
      if (current) current.focus();
    }

    function close(refocus) {
      if (openInstance === api) openInstance = null;
      wrap.classList.remove('open');
      btn.setAttribute('aria-expanded', 'false');
      if (refocus) btn.focus();
    }

    btn.addEventListener('click', function () {
      wrap.classList.contains('open') ? close(true) : open();
    });
    btn.addEventListener('keydown', function (e) {
      if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
        e.preventDefault();
        open();
      }
    });

    menu.addEventListener('keydown', function (e) {
      var list = items();
      var idx = list.indexOf(document.activeElement);
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        (list[idx + 1] || list[0]).focus();
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        (list[idx - 1] || list[list.length - 1]).focus();
      } else if (e.key === 'Home') {
        e.preventDefault();
        if (list[0]) list[0].focus();
      } else if (e.key === 'End') {
        e.preventDefault();
        if (list.length) list[list.length - 1].focus();
      } else if (e.key === 'Escape') {
        e.preventDefault();
        close(true);
      } else if (e.key === 'Tab') {
        close(false);
      }
    });

    wrap.addEventListener('focusout', function (e) {
      if (!wrap.contains(e.relatedTarget)) close(false);
    });

    // Programmatisk .value = ... udløser ingen events — hook property'en på instansen
    if (valueDesc) {
      Object.defineProperty(select, 'value', {
        configurable: true,
        get: function () { return valueDesc.get.call(this); },
        set: function (v) {
          valueDesc.set.call(this, v);
          scheduleSync();
        }
      });
    }

    // Fanger disabled/style-attributter og option-tekster (i18n skifter textContent)
    var mo = new MutationObserver(scheduleSync);
    mo.observe(select, {
      attributes: true,
      attributeFilter: ['style', 'disabled', 'class'],
      childList: true,
      subtree: true,
      characterData: true
    });

    var api = { close: close, wrap: wrap };
    rebuild();
    sync();
    return api;
  }

  document.addEventListener('pointerdown', function (e) {
    if (openInstance && !openInstance.wrap.contains(e.target)) openInstance.close(false);
  });

  function init() {
    // Kun aktiv når Fjord-temaet er valgt — under Klassisk skal den native select vises uændret
    var link = document.getElementById('fjordDesignStylesheet');
    if (!link || link.disabled) return;
    document.querySelectorAll('select.select').forEach(function (s) { enhance(s); });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();

  window.flEnhanceSelect = enhance;
})();
