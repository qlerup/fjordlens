(() => {
  'use strict';

  let dnsConfigured = false;

  const pairs = [
    ['mapperShareDuckdnsToggle', 'mapperSharePermission', 'mapperShareRequireNameToggle'],
    ['sharedEditDuckdnsToggle', 'sharedEditPermission', 'sharedEditRequireNameToggle'],
  ];

  function hideControl(id) {
    const input = document.getElementById(id);
    if (!input) return;
    const label = input.closest('label');
    if (label) label.style.display = 'none';
    else input.style.display = 'none';
  }

  function permissionNeedsName(permissionEl) {
    const value = String(permissionEl?.value || 'view').trim().toLowerCase();
    return value === 'upload' || value === 'manage';
  }

  function applyPair([dnsId, permissionId, nameId]) {
    const dns = document.getElementById(dnsId);
    const permission = document.getElementById(permissionId);
    const requireName = document.getElementById(nameId);

    if (dns) dns.checked = !!dnsConfigured;
    if (requireName) requireName.checked = permissionNeedsName(permission);

    hideControl(dnsId);
    hideControl(nameId);
  }

  function applyAll() {
    for (const pair of pairs) applyPair(pair);
  }

  async function refreshDnsConfigured() {
    try {
      const response = await fetch('/api/settings/dns/effective', {credentials: 'same-origin'});
      const data = await response.json().catch(() => ({}));
      dnsConfigured = !!(response.ok && data && data.ok && data.duckdns_configured);
    } catch (_) {
      dnsConfigured = false;
    }
    applyAll();
  }

  document.addEventListener('change', (event) => {
    if (event.target?.id === 'mapperSharePermission' || event.target?.id === 'sharedEditPermission') {
      applyAll();
    }
  }, true);

  document.addEventListener('click', (event) => {
    if (event.target?.closest('#mapperShareModalConfirm, #sharedEditModalSave')) {
      // Capture phase makes sure the hidden values are correct before app.js reads them.
      applyAll();
    }
    if (event.target?.closest('#dnsSaveBtn')) {
      // app.js saves asynchronously; refresh the effective setting immediately afterwards.
      setTimeout(refreshDnsConfigured, 350);
      setTimeout(refreshDnsConfigured, 1000);
    }
  }, true);

  const observer = new MutationObserver(() => applyAll());

  function init() {
    applyAll();
    refreshDnsConfigured();
    observer.observe(document.body, {subtree: true, childList: true, attributes: true, attributeFilter: ['class']});
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init, {once: true});
  else init();
})();
