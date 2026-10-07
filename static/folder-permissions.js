'use strict';

async function openFolderPermissionsDialog(folder = '') {
  if (!['admin', 'manager'].includes(state.currentUser?.role)) return;
  if (document.querySelector('.folder-permissions-dialog')) return;
  closeMapperContextMenu(); closeMapperHeaderMenu();
  const dialog = document.createElement('dialog');
  dialog.className = 'folder-permissions-dialog';
  dialog.setAttribute('aria-labelledby', 'folderPermissionsTitle');
  dialog.innerHTML = `<header><h2 id="folderPermissionsTitle">Mappetilladelser</h2><button type="button" class="btn permissions-close" aria-label="Luk">Luk</button></header>
    <p class="permissions-context"></p>
    <label for="folderPermissionsUser">Bruger</label>
    <select id="folderPermissionsUser" disabled><option value="">Indlæser brugere …</option></select>
    <p class="permissions-hint mini-label"></p>
    <div class="permissions-quick" hidden><label for="folderPermissionsLevel">Tilladelse til denne mappe og dens undermapper</label>
      <select id="folderPermissionsLevel"><option value="none">Ingen direkte tilladelse</option><option value="view">Vis billeder</option><option value="upload">Vis og upload</option><option value="edit">Vis, upload og rediger</option></select></div>
    <div id="folderPermissionsTree" class="ua-list" hidden></div>
    <p class="permissions-error" role="alert"></p>
    <div class="actions"><button type="button" class="btn permissions-general" disabled>Alle mappetilladelser …</button><button type="button" class="btn primary permissions-save" disabled>Gem tilladelser</button></div>`;
  document.body.append(dialog);
  const select = dialog.querySelector('#folderPermissionsUser');
  const level = dialog.querySelector('#folderPermissionsLevel');
  const tree = dialog.querySelector('#folderPermissionsTree');
  const general = dialog.querySelector('.permissions-general');
  const save = dialog.querySelector('.permissions-save');
  const error = dialog.querySelector('.permissions-error');
  const hint = dialog.querySelector('.permissions-hint');
  const path = normalizeAclFolder(folder);
  const folderKey = path ? (path.startsWith('uploads/') ? path : `uploads/${path}`) : '';
  let users = [], folders = [], selected = null, draft = [], generalMode = !folderKey, busy = false;
  const key = value => {
    const clean = normalizeAclFolder(value);
    return clean.startsWith('uploads/') ? clean : `uploads/${clean}`;
  };
  const close = () => { if (!busy) dialog.close(); };
  dialog.querySelector('.permissions-close').onclick = close;
  dialog.addEventListener('cancel', event => { if (busy) event.preventDefault(); });
  dialog.addEventListener('close', () => dialog.remove());
  dialog.showModal();

  function capture() {
    if (!selected || ['admin', 'manager'].includes(selected.role)) return;
    if (generalMode) draft = getFolderSelection('folderPermissionsTree');
    else {
      draft = draft.filter(item => key(item.folder_path) !== folderKey);
      if (level.value !== 'none') draft.push({folder_path: folderKey, permission: level.value});
    }
  }
  function render() {
    const unrestricted = selected && ['admin', 'manager'].includes(selected.role);
    save.disabled = !selected || unrestricted || busy;
    general.disabled = !selected || unrestricted || busy;
    level.disabled = !selected || unrestricted || busy;
    dialog.querySelector('.permissions-context').textContent = generalMode ? 'Administrer brugerens adgang til alle mapper.' : `Mappe: ${folder}`;
    dialog.querySelector('.permissions-quick').hidden = generalMode || !selected || unrestricted;
    tree.hidden = !generalMode || !selected || unrestricted;
    general.textContent = generalMode && folderKey ? 'Tilbage til denne mappe' : 'Alle mappetilladelser …';
    general.hidden = !folderKey;
    hint.textContent = unrestricted ? 'Admins og managers har adgang til alle mapper via deres rolle.'
      : selected ? (generalMode ? 'Tilladelser gælder også undermapper. Vælg adgang for hver mappe, eller fjern en eksisterende tilladelse.'
        : 'Tilladelser gælder også undermapper. Adgang fra en overmappe ændres i Alle mappetilladelser.') : 'Vælg en bruger med adgang til FjordLens.';
    if (!selected || unrestricted) return;
    if (generalMode) {
      const all = Array.from(new Set([...folders, ...draft.map(item => item.folder_path)]));
      setFolderSelection('folderPermissionsTree', draft, all);
      for (const row of tree.querySelectorAll('.ua-row')) {
        const remove = document.createElement('button');
        remove.type = 'button'; remove.className = 'btn small'; remove.textContent = 'Fjern adgang';
        remove.onclick = () => {
          row.querySelectorAll('input').forEach(input => input.checked = false);
          row.classList.remove('lvl-view', 'lvl-upload', 'lvl-edit');
        };
        row.querySelector('.ua-label').append(remove);
      }
      tree.querySelectorAll('input, button').forEach(control => control.disabled = busy);
      // Expand the folder that opened the dialog so its current grants are visible.
      for (const row of tree.querySelectorAll('.ua-row')) {
        if (folderKey.startsWith(row.dataset.folder + '/') && !row.classList.contains('open')) row.querySelector('button.ua-caret')?.click();
      }
    } else {
      const direct = draft.find(item => key(item.folder_path) === folderKey);
      level.value = direct?.permission || 'none';
      const inherited = draft.filter(item => folderKey.startsWith(key(item.folder_path) + '/'));
      if (inherited.length) hint.textContent += ' Denne mappe har også adgang fra en overmappe.';
    }
  }
  select.onchange = () => {
    selected = users.find(user => String(user.id) === select.value) || null;
    draft = (selected?.allowed_folders || []).map(item => ({...item}));
    error.textContent = ''; render();
  };
  general.onclick = () => { capture(); generalMode = !generalMode; render(); };
  save.onclick = async () => {
    if (busy || !selected) return;
    capture(); busy = true; render(); select.disabled = true; error.textContent = '';
    try {
      const response = await fetch(`/api/folder-access/users/${selected.id}`, {
        method: 'PUT', headers: {'Content-Type':'application/json'},
        body: JSON.stringify({allowed_folders: draft, previous_allowed_folders: selected.allowed_folders}),
      });
      const result = await response.json();
      if (!response.ok || !result.ok) throw new Error(result.error || 'Kunne ikke gemme tilladelser.');
      selected.allowed_folders = result.allowed_folders;
      dialog.close(); showStatus('Mappetilladelser gemt', 'ok');
    } catch (failure) { error.textContent = failure.message; }
    finally { busy = false; if (dialog.isConnected) {select.disabled = false; render();} }
  };
  try {
    const response = await fetch('/api/folder-access/users', {cache:'no-store'});
    const data = await response.json();
    if (!response.ok || !data.ok) throw new Error(data.error || 'Kunne ikke hente brugere.');
    if (!dialog.isConnected) return;
    users = data.items; folders = data.available_folders;
    select.replaceChildren(new Option('Vælg bruger …', ''));
    for (const user of users) select.append(new Option(`${user.username} · ${user.role === 'user' ? 'Bruger' : user.role}`, String(user.id)));
    select.disabled = false; render(); select.focus();
  } catch (failure) { if (dialog.isConnected) error.textContent = failure.message; }
}

document.getElementById('mapperHeaderPermissionsAction')?.addEventListener('click', () => {
  const selected = Array.from(state.mapperSelectedFolders || []);
  openFolderPermissionsDialog(selected.length === 1 ? selected[0] : state.mapperPath || '');
});
