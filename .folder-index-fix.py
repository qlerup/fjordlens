from pathlib import Path
import re
import subprocess


def replace(path, old, new):
    p = Path(path)
    source = p.read_text(encoding='utf-8')
    assert source.count(old) == 1, (path, old[:100], source.count(old))
    p.write_text(source.replace(old, new), encoding='utf-8')


replace('app.py', '''        # Ensure all ancestors are at least 'view' to allow navigating to this folder
        parent = path.rsplit("/", 1)[0] if "/" in path else ""
        while parent:
            # Do NOT seed the absolute root 'uploads' with view, as that
            # would unintentionally grant access to all sibling folders.
            if parent == "uploads":
                break
            if parent not in perm_map:
                perm_map[parent] = "view"
            parent = parent.rsplit("/", 1)[0] if "/" in parent else ""
''', '''        # Store only explicit grants. The folder index permits ancestor
        # navigation separately; granting a parent here exposes private siblings.
''')

replace('folder_index.py', '''def install(conn):
    """Idempotent migration; backfill metadata once, never walk the filesystem."""
''', '''def install(conn):
    """Atomic migration, including upgrades from the short-lived v1 catalogue."""
    conn.execute('SAVEPOINT folder_catalogue_install')
    try:
        _install(conn)
        conn.execute('RELEASE folder_catalogue_install')
    except Exception:
        conn.execute('ROLLBACK TO folder_catalogue_install')
        conn.execute('RELEASE folder_catalogue_install')
        raise


def _install(conn):
    """Idempotent migration; backfill metadata once, never walk the filesystem."""
    legacy = []
    columns = {r[1] for r in conn.execute('PRAGMA table_info(folder_index)')}
    if columns and 'path' not in columns:
        if not {'folder_path', 'parent_path', 'name', 'updated_at'} <= columns:
            raise RuntimeError('Unrecognized folder catalogue schema; original table preserved')
        legacy = [r[0] for r in conn.execute('SELECT folder_path FROM folder_index')]
        conn.execute('ALTER TABLE folder_index RENAME TO folder_index_legacy_v1')
        conn.execute('DROP INDEX IF EXISTS idx_folder_index_parent')
''')
replace('folder_index.py', "    conn.execute('INSERT OR IGNORE INTO folder_index_state(id) VALUES(1)')", """    conn.execute('INSERT OR IGNORE INTO folder_index_state(id) VALUES(1)')
    for path in legacy:
        try:
            ensure_path(conn, path)
            mark_dirty(conn, normalize(path))
        except ValueError:
            continue
    if columns and 'path' not in columns:
        conn.execute('DROP TABLE folder_index_legacy_v1')""")

replace('tests/test_upload_conversion_uploader.py', '''patch.object(fjordlens, "index_faces_for_photo", side_effect=lambda _rel: events.append("face") or 0)''', '''patch.object(fjordlens, "_detect_faces_for_photo", side_effect=lambda _rel: events.append("face") or [])''')

Path('tests/upload_destination.test.cjs').write_text('''const {test} = require('node:test');
const assert = require('node:assert/strict');
const {readFileSync} = require('node:fs');
const vm = require('node:vm');

test('upload refresh keeps root selected regardless of saved upload destination', async () => {
  const source = readFileSync('static/app.js','utf8');
  let savedFolder = 'Christmas';
  const requests = [];
  const state = {view:'mapper',mapperPath:'',mapperSelectedFolders:new Set(),items:[],currentUser:{id:1}};
  const context = vm.createContext({state,URLSearchParams,document:{hidden:false},mapperViews:new Map(),
    galleryDataCache:{clear(){},generation:()=>0},galleryCacheKey:x=>x,
    fetch:async(url)=>{requests.push(url);return {ok:true,status:200,json:async()=>({ok:true,subdir:savedFolder,folders:['Christmas','Birthday'],items:[],revision:1})};},
    _normalizeMapperPath:x=>x,_expandMapperAncestors(){},renderMapperContext(){},_syncRouteStateToUrl(){},showStatus(){},renderGrid(){},
    setTimeout:()=>1,clearTimeout(){},rememberMapperView(){},photosRequestSequence:0,photosAbortController:null,photosLoadPromise:null});
  vm.runInContext(source.slice(source.indexOf('let mapperToolsRequestSequence ='),source.indexOf('async function createMapperFolder(')),context);
  await context.loadMapperTools();
  assert.equal(state.mapperPath,'');
  savedFolder = 'Birthday';
  await context.loadMapperTools();
  assert.equal(state.mapperPath,'');
  assert.equal(state.folder,null);
  state.mapperPath = 'Chosen parent';
  await context.loadMapperTools();
  assert.equal(state.mapperPath,'Chosen parent');
  context.beginMapperPathNavigation('');
  await context.loadMapperTools('');
  assert.equal(state.mapperPath,'');
  context.beginMapperPathNavigation('Explicit target');
  await context.loadMapperTools('Explicit target');
  assert.equal(state.mapperPath,'Explicit target');
  assert.ok(requests.every(url=>url.startsWith('/api/folder-index?')));
});
''')

replace('tests/test_folder_index.py', '    def test_photo_triggers_register_ancestors_and_merge_storage_mirrors(self):', '''    def test_legacy_catalogue_migrates_empty_folders_without_disk_reads(self):
        other = sqlite3.connect(':memory:')
        self.addCleanup(other.close)
        other.executescript("""
            CREATE TABLE photos(id INTEGER PRIMARY KEY,rel_path TEXT UNIQUE,thumb_name TEXT,filename TEXT);
            CREATE TABLE folder_owners(folder_path TEXT PRIMARY KEY,user_id INTEGER);
            CREATE TABLE folder_previews(folder_path TEXT PRIMARY KEY,previews_json TEXT,updated_at TEXT);
            CREATE TABLE folder_index(folder_path TEXT PRIMARY KEY,parent_path TEXT NOT NULL DEFAULT '',name TEXT NOT NULL,updated_at TEXT NOT NULL);
            CREATE INDEX idx_folder_index_parent ON folder_index(parent_path);
            INSERT INTO folder_index VALUES('Legacy/Empty','Legacy','Empty','2026-09-19');
        """)
        with patch.object(index.os,'walk',side_effect=AssertionError('migration must not scan')):
            index.install(other)
            other.commit()
            index.install(other)
        self.assertEqual([r[0] for r in other.execute('SELECT path FROM folder_index ORDER BY path')],['Legacy','Legacy/Empty'])
        self.assertEqual([r[2] for r in other.execute('PRAGMA index_info(idx_folder_index_parent)')],['parent','name'])
        self.assertFalse(other.execute("SELECT 1 FROM sqlite_master WHERE name='folder_index_legacy_v1'").fetchone())

    def test_photo_triggers_register_ancestors_and_merge_storage_mirrors(self):''')

replace('tests/test_folder_index_api.py', '    def test_create_rename_move_and_delete_empty_folders_update_index_immediately(self):', '''    def test_explicit_parent_grants_still_include_children(self):
        self.seed('Family/Private','private.jpg'); self.seed('Family/Shared','shared.jpg')
        with fl.closing(fl.get_conn()) as conn:
            fl._set_user_allowed_folders(conn,2,[{'folder_path':'Family','permission':'view'}]); conn.commit()
        self.assertEqual(self.viewer.get('/api/folder-index?parent=Family').get_json()['folders'],['Family/Private','Family/Shared'])

    def test_create_rename_move_and_delete_empty_folders_update_index_immediately(self):''')

p=Path('docs/folder-index.md')
p.write_text(p.read_text()+"\nThe earlier `folder_path/parent_path` catalogue schema is migrated atomically, preserving empty folders. New ACL saves contain only explicitly selected folders: ancestor navigation no longer creates a broad parent grant. The existing security migration handles legacy implicit ancestor grants conservatively; explicit broad parent access can be selected again in permissions when intended.\n")

# Incorporate the reviewed concurrent security/main changes without discarding
# unrelated edits. Only overlapping folder-feature hunks may be resolved here.
def git(*args, **kwargs):
    return subprocess.run(['git', *args], check=True, **kwargs)

git('config','user.name','github-actions[bot]')
git('config','user.email','41898282+github-actions[bot]@users.noreply.github.com')
files = ['app.py','static/app.js','wsgi.py','folder_index.py','docs/folder-index.md']
files += [str(p) for p in Path('tests').glob('*.py')] + [str(p) for p in Path('tests').glob('*.cjs')]
git('add', *files)
git('commit','-m','Implement shared folder catalogue with loading and access regressions')
git('fetch','origin','9885108bc56d05da78a0857aec447979be2937f2')
merged = subprocess.run(['git','merge','--no-commit','--no-ff','FETCH_HEAD'])
if merged.returncode:
    conflicts = subprocess.check_output(['git','diff','--name-only','--diff-filter=U'], text=True).splitlines()
    assert set(conflicts) <= {'app.py','static/app.js'}, conflicts
    counts = {'app.py':3,'static/app.js':2}
    for name in conflicts:
        path = Path(name); text = path.read_text()
        blocks = list(re.finditer(r'^<<<<<<<[^\n]*\n(.*?)^=======\n(.*?)^>>>>>>>[^\n]*\n',text,re.M|re.S))
        assert len(blocks) == counts[name], (name,len(blocks))
        for block in blocks:
            ours = block.group(1)
            assert any(key in ours for key in ['# Store only explicit grants.', 'def _folder_index_visibility(', 'folder_index.list_folders(conn, "",', 'await navigateMapperPath(folderPath)', 'state.mapperFoldersLoading = true;']), (name,ours)
        path.write_text(re.sub(r'^<<<<<<<[^\n]*\n(.*?)^=======\n(.*?)^>>>>>>>[^\n]*\n', lambda m:m.group(1), text, flags=re.M|re.S))
        git('add',name)

compat = '''def _ensure_folder_index_table() -> None:
    """Compatibility for explicit maintenance helpers, not a browse hot path."""
    with closing(get_conn()) as conn:
        folder_index.install(conn)
        conn.commit()


def _folder_index_list() -> list[str]:
    with closing(get_conn()) as conn:
        return [""] + [row[0] for row in conn.execute("SELECT path FROM folder_index ORDER BY path COLLATE NOCASE")]


def _folder_index_rebuild(base_dir: Path) -> list[str]:
    # Explicit reconciliation preserves the catalogue if storage is offline.
    with closing(get_conn()) as conn:
        folder_index.discover(conn, base_dir)
    return _folder_index_list()


def _folder_index_add(path: str) -> None:
    with closing(get_conn()) as conn:
        folder_index.ensure_path(conn, path)
        conn.commit()


'''
replace('app.py', 'def _folder_index_visibility(conn):', compat+'def _folder_index_visibility(conn):')
git('add','app.py','docs/folder-index.md')
