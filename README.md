# FjordLens for Synology

FjordLens is a Docker-based photo library app for Synology NAS (and local Docker hosts), with a Flask web UI, metadata indexing, folder-based uploads, AI embedding controls, and face indexing.

## Quick Start

### Local / Docker host

```bash
cp .env.example .env
docker compose up -d --build
```

Open:
- `http://localhost:9080` (or your `APP_PORT`)

### Synology NAS (SSH)

```bash
cd /volume1/docker
git clone https://github.com/YOUR_USER/YOUR_REPO.git fjordlens
cd fjordlens
cp .env.example .env
docker compose up -d --build
```

Open:
- `http://YOUR_NAS_IP:9080`

## What’s Included

- Web app: Flask + vanilla JS UI
- Photo indexing from mounted `/photos`
- EXIF/file metadata extraction
- Thumbnails + detail panel
- Danish/English UI language support per user
- Danish/English search language support per user
- Role-based auth: Admin, Manager, User
- 2FA (TOTP)
- Favorites, Places, Cameras, People, Folders views
- Folder management + drag/drop upload to selected folder
- AI embeddings ingest (start/stop) with progress
- Face indexing with progress
- Docker Compose stack with dedicated AI service

## What Changed Recently

- Settings was cleaned up and split into clearer tabs.
- AI controls now live in a dedicated `AI` tab.
- AI tab now has **two vertical sections**:
  - Embeddings section (single start/stop toggle button)
  - Face indexing section
- Each AI section has its own explanation text and status line.
- Deprecated upload destination controls were removed from Maintenance.
- Folder upload workflow is now centered in the `Folders` view.
- Profile editing is available from footer `Profile` link (modal).
- Admin user management supports editing username/password/role/languages.

## Where to Find What (UI Map)

### Left navigation

- `Timeline`: Date-grouped gallery
- `Favorites`: Starred items
- `Places`: Map/location-oriented browsing
- `Cameras`: Camera metadata filter view
- `Folders`: Folder tree + folder actions + drag/drop upload target
- `People`: Face/person browsing
- `Settings`: Operational tools and administration

### Footer links

- `Profile`: Edit your own account/profile settings
- `API health`: Quick backend health endpoint
- `Filters`: API filter debug endpoint
- `Log out`

## Settings Tabs

### Maintenance

Use this tab for library maintenance tasks:
- Scan library
- Rescan metadata
- Rebuild thumbnails
- Reset index

### AI

The AI tab is split into two clear sections:

1. **AI embeddings**
   - One toggle button: `Start AI` / `Stop AI`
   - Starts/stops embeddings ingest for photos missing embeddings
   - Status line shows:
     - running/stopped
     - embedded/total
     - failures

2. **Face indexing**
   - Button: `Index faces`
   - Runs face indexing job for photos
   - Status line shows:
     - running/stopped
     - processed/total

### Logs

- Live operations log controls (`Start/Stop`, `Clear`)
- Main log output panel

### Users (Admin)

- Create users
- Edit existing users
- Set role
- Set per-user UI language and search language

### My 2FA

- Enable/disable TOTP
- Manage trusted device behavior

### Other

- Duplicate scan tools

## Profile and User Preferences

Open `Profile` from the sidebar footer to edit your own account:
- Username
- Optional password change
- UI language (`da`/`en`)
- Search language (`da`/`en`)

Preferences persist per user and are applied on refresh/login.

## Folders and Upload Workflow

Folder workflows now happen in `Folders` view:

- Navigate folder tree
- Create subfolders
- Drag & drop files into the folder dropzone
- Upload target follows current folder context

This replaced the old maintenance upload destination controls.

## Search and Sorting

Search supports:
- Filename/path
- Camera/lens metadata
- Date-like terms
- Location fields (when available)
- AI tags/metadata fields

Sorting:
- Date ascending/descending
- Name ascending/descending
- Size ascending/descending

## Authentication and Roles

- First run redirects to setup to create initial admin user.
- Roles:
  - `Admin`: full access, user administration
  - `Manager`: operations access (without user admin)
  - `User`: restricted from admin/maintenance operations

Safety rules include protection against removing the last admin.

## Deployment and Updates

### Standard update flow

```bash
git pull
docker compose up -d --build
```

### Full restart flow

```bash
docker compose down
docker compose up -d --build
```

### Helper scripts

- `scripts/first_install_nas.sh`
- `scripts/update.sh`

## GHCR Option (Prebuilt Images)

A GHCR compose example is included:
- `docker-compose.ghcr.yml.example`

Use this if you prefer pulling prebuilt images instead of building on NAS.

## Configuration

Key environment variables (see `.env.example`):

- `APP_PORT`: Web UI host port (default `9080`)
- `PHOTO_DIR`: Host path mounted as `/photos` (read-only recommended)
- `DATA_DIR`: Persistent app data path (`db`, `thumbs`, uploads data)
- `TZ`: Time zone
- `LOG_LEVEL`: App log level
- `AI_DEBUG_PORT`: Optional host exposure for AI service
- `AI_URL`: Internal backend -> AI service URL (compose default uses service name)

### Geocoding / behavior flags

- `GEOCODE_ENABLE`
- `GEOCODE_PROVIDER`
- `GEOCODE_LANG`
- `GEOCODE_TIMEOUT`
- `GEOCODE_RETRIES`
- `GEOCODE_DELAY`

## Health and Validation

Useful checks:

- App health: `GET /api/health`
- Compose status:

```bash
docker compose ps
```

Expected after successful deploy:
- `fjordlens`: healthy
- `fjordlens-ai`: healthy

## Security Notes

- Never commit `.env` with secrets.
- Keep `/photos` mounted read-only when possible.
- Use strong admin password + enable 2FA.
- Keep `DATA_DIR` on persistent storage.

## Project Structure

```txt
fjordlens/
├─ app.py
├─ wsgi.py
├─ Dockerfile
├─ docker-compose.yml
├─ docker-compose.ghcr.yml.example
├─ requirements.txt
├─ .env.example
├─ README.md
├─ ai_service/
│  ├─ app.py
│  ├─ Dockerfile
│  ├─ requirements.txt
│  └─ download_models.py
├─ templates/
│  ├─ index.html
│  ├─ login.html
│  ├─ setup.html
│  ├─ 2fa_setup.html
│  ├─ 2fa_verify.html
│  └─ admin_users.html
├─ static/
│  ├─ app.js
│  ├─ styles.css
│  └─ icons/
├─ scripts/
│  ├─ first_install_nas.sh
│  └─ update.sh
└─ data/
```

## Troubleshooting

- If AI service is healthy but embeddings do not move:
  - Check AI section status counters (`embedded/total/failures`).
  - Check logs in `Settings -> Logs`.
- If containers keep restarting:
  - Run `docker compose ps` and `docker compose logs`.
- If UI text seems stale after deploy:
  - Hard refresh browser (`Ctrl+F5`) to invalidate cached JS/CSS.

---

If you want, the next step can be adding screenshots per tab (in English) directly inside this README.
