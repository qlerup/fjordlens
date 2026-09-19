# Security update: folder grants, sharing and device access

This update checks media access at Cast playback, cached-image delivery and photo
mutation boundaries, and binds resumable uploads to their current user or share.
It also escapes stored identity labels, protects the HTML user-administration
forms against CSRF, limits second-factor guesses, preserves frame revocation
during concurrent requests, and removes arbitrary device HTML proxying.

## Existing installations

- Back up the database before upgrading, as with other schema updates.
- On the first startup, legacy `view` grants that are ancestors of another grant
  for the same user are removed. Earlier releases generated these rows just for
  navigation, but they also exposed sibling media. The old database cannot
  distinguish generated rows from explicitly selected parent grants. The migration
  therefore narrows ambiguous access. Navigation to granted descendants remains
  available. An administrator can explicitly reassign a broad parent grant when
  that access is intended; subsequent startups preserve it.
- In-progress authenticated TUS uploads from earlier releases lack a user binding
  and must be restarted. Existing shared uploads continue only while their share,
  upload permission, visitor authorization and target folder are still valid.
- Existing Cast tokens stop working when their creator loses access, is deleted,
  or selected media moves outside the recorded selection. Start a new Cast session
  after intentional selection changes.
- Recreate the Compose services to remove the AI host-port publication:
  `docker compose up -d --build`. Flask still reaches the AI service internally,
  including cooperative and hard stop. Custom deployments must keep the
  unauthenticated AI service on a trusted private network; `AI_DEBUG_PORT` no longer
  publishes a port in the supplied Compose configuration.
- Frame remote settings continue through the local settings UI and heartbeat
  commands. Arbitrary device proxy subpaths now return 404.
- Cached media responses are now private and non-cacheable. Previously downloaded
  or cached copies cannot be recalled by a server update.

Two-factor login challenges expire after five minutes. Each account has a maximum
of five verification attempts per five-minute window, shared across sessions and
workers. A successful verification resets the attempt budget.

## Regression checks

The focused Python suite uses temporary databases and a Flask test client:

```sh
python -m unittest discover -s tests -p 'test_security_boundaries.py' -v
python -m unittest discover -s tests -p 'test_security_rendering_browser.py' -v
```

The browser suite requires Playwright and Chromium. Tests do not require a live
deployment, provider credentials, AI model downloads or access to real photos.
