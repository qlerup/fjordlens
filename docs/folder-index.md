# Folder navigation index

`folder_index` is a persistent SQLite catalogue of logical upload folders. It is
shared by all users, while API responses, folder names and saved cover references
are filtered on every request. Parent/name indexes make a normal request read only
the immediate children. The separate `tree=1` query is used for the sidebar and
move picker, not for every folder click.

## Migration and writes

The idempotent `init_db` migration reads existing photo paths, owners and saved
previews once. It does not walk the media storage. SQLite triggers maintain the
catalogue and a coalescing cover queue in the same transaction as photo inserts,
updates and deletes, including writes by upload workers. App-created empty folders
are registered immediately. Folder rename/move/delete update the catalogue with
the existing mutation transactions; a deleted photo does not delete its still
existing empty directory.

Production bootstrap starts separate daemon workers for cover metadata and
filesystem discovery. Known folders are available immediately. Legacy empty
folders and external additions are discovered separately, then approximately every
10 minutes. Discovery is additive: disconnected, empty or unreadable NAS mounts
never erase the catalogue. Use FjordLens's folder deletion action to remove stale
folders deleted outside the app. A topology version prevents a concurrent app
rename/delete from being undone by an older discovery snapshot. Neither the cover
worker nor a browse request opens original media.

Existing saved thumbnail choices are reused. Only affected folders and ancestors
are queued for updates. The GET endpoint validates saved thumbnail references
against indexed photos and current authorization, but never scans the disk or
regenerates a preview. Permission-scope changes invalidate browser photo/tree
caches; the shared database index is never a shared authorization cache.

## Browser behavior

Folder metadata and the first photo page are requested concurrently. Loading,
empty and failed requests are distinct states. Folder cards can be used before
photos arrive, and decoded folder mosaics are reused when the photo page renders.
Cached views are revalidated; stale responses from a different folder/account are
ignored. The open folder's compact index is refreshed every 20 seconds while the
page is visible and not editing/loading photos; initial discovery and pending
covers use a shorter interval. Originals and full-size photo metadata are not
reloaded for these index refreshes.

## Tests

```sh
python -m unittest discover -s tests -p test_folder_index.py
PYTHONPATH=.:tests python -m unittest test_folder_index_api test_folder_previews test_folder_move test_gallery_browse
node --test tests/folder_index_ui.test.cjs tests/mapper_views.test.cjs tests/folder_move_ui.test.cjs
# With Playwright, Chromium and the application dependencies installed:
PYTHONPATH=.:tests python -m unittest test_gallery_navigation_browser
```

The earlier `folder_path/parent_path` catalogue schema is migrated atomically, preserving empty folders. New ACL saves contain only explicitly selected folders: ancestor navigation no longer creates a broad parent grant. The existing security migration handles legacy implicit ancestor grants conservatively; explicit broad parent access can be selected again in permissions when intended.
