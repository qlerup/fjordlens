# FjordLens

FjordLens is a self-hosted photo library for Synology NAS and Docker hosts, with built-in photoframe management for Raspberry Pi devices, Google Photos/Nest Hub photo-frame integration, and mobile AirPlay/Google Cast slideshow support.

This repository contains the FjordLens web app/API plus the Raspberry Pi photoframe client.

See [Momenter](MOMENTS.md) for automatic trip/day-event discovery, home-area settings,
photo selection, editing, splitting and merging moments, cinematic slideshows,
music, public links and MP4 export.

---

## Feature Matrix

| Feature | Requires Ollama | Requires Photoframe | Requires External Worker | External account/service |
|---|:---:|:---:|:---:|:---:|
| Timeline/Folders/Places | | | | |
| Metadata indexing | | | | |
| Weather enrichment | | | | Open-Meteo |
| Thumbnail generation | | | | |
| AI embedding/search/similarity | | | | |
| AI image description | X* | | X | |
| Face detection/indexing | | | | |
| Public share links | | | | |
| Automatic moments and attraction lookup | | | | OpenStreetMap / Overpass for places |
| Slideshow editor, bundled music and MP4 export | | | | |
| Raspberry Pi photoframe management | | X | | |
| Remote photoframe update | | X | | |
| Google Photos / Nest Hub Photo Frame | | | | Google Photos OAuth |
| AirPlay slideshow from iPhone/iPad | | | | Apple AirPlay |
| Google Cast custom receiver | | | | Google Cast Receiver App ID |
| External AI queue | X | | X | |

*Ollama is only required if you use the external AI describer/worker.

---

## What You Get

### Photo library

- Timeline, Favorites, Folders, Places, Cameras, People views
- Metadata indexing (EXIF/file info)
- Historical weather enrichment from photo date + GPS, with city fallback
- Thumbnail generation and cache management
- Per-photo editing for captured date, GPS and favorite state
- Duplicate detection and merge tools
- Single file and ZIP downloads
- Progressive loading in Timeline, Folders and People

### Moments and cinematic slideshows

- Automatic day events, journeys abroad, annual reviews and Danish calendar occasions
- At least **10 photos** for automatic moment suggestions; scan progress explains the current phase
- Home-area/country settings distinguish a local outing from a journey abroad
- Worldwide attraction detection uses repeated GPS positions and mapped areas, including large parks; geographically separate outings are kept separate
- Same-event reconciliation brings together photos with and without GPS, while checking dates, folders and locations to avoid combining unrelated events
- Generic titles can use a source-folder name when at least **75%** of the photos come from it; parenthesized text is removed
- Danish place/country names and automatic title suffixes: `Title · DD.MM.YYYY` for one day, `Title · YYYY` for multiple days
- Edit dates and membership, split or merge moments, and retain manual changes during later scans
- The slideshow curates varied highlights across the event, suppresses near-duplicates and plays them in chronological order; the moment retains its complete selection
- Full-resolution media, animated typography, gentle motion, weather when available and occasional paired portrait photos
- Video slides play to the end of the clip, independently of the photo duration
- A full-screen player hides navigation, with responsive captions for portrait phones and widescreen computers/TVs
- **Rediger diasshow** opens a saved timeline: reorder slides, adjust photo duration, edit/add text and media, pair photos, drag text in the preview, undo/redo and reset placement
- **Lav video** offers **PC / TV (1920×1080)** or **Mobil (1080×1920)** MP4 export; exported videos use the saved timeline and music

### Background music

The bundled [music library](music/README.md) contains **16 tracks in eight moods**.
FjordLens selects an initial track from the moment title. In the slideshow editor,
choose a track, preview it, set the volume or select **Ingen musik**. Music continues
across slides and loops with a six-second equal-power crossfade. MP4 export uses
the same loop structure, with a fade at the beginning and end. Original video
clips remain muted in the moment presentation.

Music is served by your FjordLens server without a streaming-service account.
Browsers may require a tap on **Slå musik til**, especially on public links and
phones. Playback also includes a mute control. A new sharing link snapshots the
track and volume along with the timeline; later editor changes do not alter it.
Older links without a music setting receive a default track based on their stored
title. Existing editable timelines receive music without losing their edits;
previous silent MP4 exports must be generated again.

The recordings were supplied by qlerup and created with Suno under a paid
subscription. Their separate [music rights notice](music/COPYRIGHT.md) permits
use in FjordLens moments, shared links and exported videos; they are not offered
as public-domain or unrestricted stock music.

### Upload and file handling

- Folder-based upload workflows from the UI
- Resumable uploads via TUS (`/api/upload/tus`)
- Share-link uploads (including TUS on share links)
- Optional HEIC and RAW conversion flows
- Post-processing pipeline for uploads

### External camera clients

Camera import clients can connect with FjordLens' device-pairing flow:

1. Enter the FjordLens address in the client and request a connection.
2. Compare the six-character code shown by the client with the pending request under **Settings → Tokens**.
3. Choose a destination folder and approve the request.
4. Revoke or delete the client from the same settings panel when it no longer needs access.

The client receives a dedicated bearer token. FjordLens stores only its hash, limits concurrent pending requests, and immediately rejects revoked tokens. Camera uploads are written below `uploads/originals/<selected folder>` and use the same conversion, indexing, and post-processing workflow as normal uploads.

Use an HTTPS address whenever the client crosses an untrusted network. Plain HTTP does not protect the pairing secret, bearer token, or uploaded media in transit. For a private LAN without TLS, restrict the FjordLens port to trusted devices at the firewall.

### AI and face features

- AI embedding ingest with start/stop/status
- AI description ingest with start/stop/status
- External AI description queue for offloaded processing workers
- AI search and "similar photos" tools
- Face indexing jobs with progress tracking
- People training, rename, hide, unknown-face matching
- Person covers use still-photo face crops with corrected orientation, rather than video frames
- Unnamed single-photo detections are hidden behind the single-find toggle; they keep participating in matching and appear automatically when more photos match
- Explicitly hidden people stay hidden until unhidden, independently of the single-find filter
- Name an unknown person from inside their album; named people have an explicit rename/merge dialog
- Existing-person choices sort by photo count descending, then Danish alphabetical order
- Face-box toggling updates immediately, and refreshing a person album preserves the selected person

### Sharing and permissions

- Public share links for folders
- Public **moment links** open the cinematic player directly, including music, mobile captions and fullscreen controls
- Choose a moment link's lifetime when sharing; Settings → Shared lists it alongside other links with copy, QR, edit, extend, deactivate/reactivate and delete actions
- Moment links contain a snapshot of the timeline and only allow access to its media and selected soundtrack; revoked/expired links stop working
- Share permissions (`view`, `download`, `upload`, `manage`)
- Optional password protection
- Expiry and management (extend/revoke/activate/edit)
- Managers can create and manage share links without receiving unrelated admin maintenance permissions
- The configured public/DNS base URL is used automatically when available, with normal URL fallback
- Visitor-name requirements are set automatically by permission:
  - `view`: name not required
  - `upload`: name required
  - `manage`: name required

### Raspberry Pi photoframe platform

- Create and manage photoframe tokens from FjordLens
- Remote status cards (online, IP/local IP, version, sync, update state)
- Scope control per frame (all/folders/selected photos)
- Proxy access to frame settings from FjordLens
- Frame update rollout via uploaded ZIP (single frame or all)
- Restart/cancel commands and update progress reporting

### Google Photos / Nest Hub Photo Frame

FjordLens can maintain an app-created Google Photos album intended for use with Google Nest Hub / Google Home ambient Photo Frame.

- Default album title: `FjordLens Photo Frame`
- Select individual FjordLens photos through the built-in picker
- Existing album selections are loaded back into the picker when reopened
- Add/remove changes are synchronized against the shared FjordLens selection
- The Google Photo Frame selection is shared across FjordLens users, rather than being user-specific
- Managers can choose/manage the photos in the album
- Google OAuth credentials, connect/disconnect and integration settings remain admin-only
- FjordLens includes a `/privacy` page suitable for the OAuth app configuration

The integration uses the Google Photos Library API with app-created-data permissions. It does **not** take over the Nest Hub with Cast; instead, the resulting Google Photos album can be selected in the normal Google Home/Nest Hub ambient Photo Frame settings.

### Mobile AirPlay / Google Cast

In phone selection mode, FjordLens adds an **AirPlay / Cast** action for selected photos, videos, or complete folders.

#### AirPlay on iPhone/iPad

AirPlay uses a server-generated HLS slideshow rather than screen mirroring:

- Selected images/videos are normalized into an HLS stream
- Rendering happens progressively in the background
- Playback can start once the first HLS segments are ready instead of waiting for the complete slideshow
- Images and videos can be mixed in the same slideshow
- Complete selected folders are expanded into the slideshow
- Videos retain their own playback length
- Image duration is selectable: **3, 5, 8, 10 or 15 seconds**
- Default image duration is **5 seconds** and the last choice is remembered on the phone
- The controller shows current item / total items
- A seek slider is available for the part of the slideshow that has been prepared
- **Forrige** and **Næste** jump between media items
- Safari-specific seek handling retries around HLS discontinuities so previous/next and manual seeking remain reliable
- The web player exposes Apple's AirPlay picker through the HLS video element

The HLS output is currently normalized to a 16:9 `1280x720` canvas with the original media contained inside it. Portrait photos can therefore have side bars on a 16:9 TV. On a portrait phone, the 16:9 preview itself can also appear small because the preview represents the TV-shaped output.

#### Google Cast

FjordLens includes a custom Google Cast Web Receiver and sender flow for Android/mobile use. The backend can create tokenized sessions and serve mixed image/video playlists to the receiver.

Google Cast requires a configured **Custom Web Receiver App ID**. Until an App ID has been registered/configured, the Cast backend and receiver page are present but Android Cast cannot start a real receiver session.

### Admin and security

- Initial setup wizard for first admin account
- Role-based access (`admin`, `manager`, `user`)
- TOTP 2FA for accounts
- Per-user UI language and search language (`da`/`en`)

## Quick Start

### Fastest Setup (Recommended)

If you want the easiest path from a fresh server, use this exact flow:

```bash
ssh <user>@<server-ip>
cd ~
git clone https://github.com/qlerup/fjordlens.git
cd fjordlens
chmod +x scripts/Fresh_start_ubuntu_vm.sh
./scripts/Fresh_start_ubuntu_vm.sh
```

The wizard is interactive and guides you through:

- app port, timezone, and logging
- storage paths
- optional NFS `/etc/fstab` setup
- optional scan/library settings
- final preflight + `docker compose up -d --build`

### Local Docker host

```bash
sh scripts/Fresh_start_ubuntu_vm.sh
```

Open `http://localhost:9080` (or your configured `APP_PORT`).

Important: keep `GUNICORN_WORKERS=1`.
Background jobs use in-process runtime state, so multiple workers can cause inconsistent job status.

When updating an installation with the separate `fjordlens-ai` service, restart
that service along with the web app and verify AI health and the expected GPU
runtime after the update. The bundled music is included in the web-app image.

Weather enrichment is enabled by default with `WEATHER_AUTO_FETCH=1`. New uploads and metadata rescans store weather under each photo's metadata when the photo has a date plus either GPS coordinates or a city/country value. FjordLens uses Open-Meteo's historical weather endpoint and caches both weather lookups and city geocoding locally.

`scripts/Fresh_start_ubuntu_vm.sh` is a guided A-Z wizard. It asks for paths and options, writes `.env`, runs mount preflight checks, and starts containers.

If you prefer to start manually without preflight:

```bash
docker compose up -d --build
```

Base `docker-compose.yml` is CPU-safe and does not request a GPU. To opt in to NVIDIA GPU passthrough on a host where `docker run --gpus all ...` already works:

```bash
AI_DEVICE=auto docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d --build
```

When installing through FjordHub, use the optional GPU step in the wizard. It can show the Proxmox host commands, run a Docker GPU preflight, and only then enable the GPU compose override.

### Synology NAS (SSH)

```bash
cd /volume1/docker
git clone https://github.com/<your-user>/<your-repo>.git fjordlens
cd fjordlens/fjordlens
sh scripts/Fresh_start_ubuntu_vm.sh
```

Open `http://<nas-ip>:9080`.

`scripts/Fresh_start_ubuntu_vm.sh` will:

- ask guided setup questions (port, storage paths, optional library source, scan toggle, SQLite mode, optional fs-type checks)
- optionally configure NFS upload mount in `/etc/fstab` and run `mount -a`
- write `.env` (with backup if `.env` already exists)
- check mount status with `findmnt`
- create required host folders (`DATA_DIR`, `UPLOADS_HOST_DIR`, `THUMBS_HOST_DIR`)
- start `docker compose up -d --build`

### Upload-only mode (no `/photos` mount)

If you only use uploads and do not have a separate photo library mount:

```bash
docker compose -f docker-compose.yml -f docker-compose.no-library.yml up -d --build
```

For upload-only setups with preflight checks:

```bash
ENABLE_LIBRARY_SOURCE=0 sh scripts/Fresh_start_ubuntu_vm.sh
```

Start later with existing `.env` (no wizard):

```bash
sh scripts/Fresh_start_ubuntu_vm.sh --start-only
```

### Manual transfers outside FjordLens

If you copy files into the upload storage manually, outside the FjordLens UI, place them inside the `originals` folder under the configured upload folder. Create or choose the target folder first, then copy files into that folder under `originals`.

Example:

```text
<UPLOADS_HOST_DIR>/originals/<your-folder>/photo.jpg
```

FjordLens will then discover the files when that folder is opened and handle indexing, thumbnails, and normal post-processing.

### Proxmox LXC guided setup

For Proxmox LXC environments (where host bind mounts and GPU passthrough are configured on the Proxmox host):

```bash
sh scripts/fresh_setup_lxc.sh
```

`scripts/fresh_setup_lxc.sh` includes optional guided GPU setup (`ENABLE_GPU_GUIDE=1`):

- asks for GPU as its own setup step before container start
- checks `/dev/nvidia*` visibility inside the LXC
- prints idempotent Proxmox host commands for the LXC config when passthrough is missing
- auto-sets `no-cgroups = true` in `/etc/nvidia-container-runtime/config.toml` when needed
- restarts Docker runtime when runtime config changes
- runs CUDA + PyTorch GPU smoke tests before adding the GPU compose override
- prints exact Proxmox host `pct`/`/etc/pve/lxc/<CTID>.conf` hints if passthrough is still incomplete
- configures in-app updater defaults, including automatic background update checks
- verifies Docker and `/var/run/docker.sock` availability for the updater container

### Proxmox Host -> LXC Bind-Mount (Manual quick commands)

Use this if you want NAS-backed uploads with host mount + LXC bind mount.

1. Mount NFS share on the Proxmox host:

```bash
mkdir -p /mnt/pve/synology-fjordlens
mount -t nfs 10.10.0.161:/volume1/FjordlensProxmox /mnt/pve/synology-fjordlens
```

2. Verify host mount:

```bash
ls -la /mnt/pve/synology-fjordlens
```

3. Bind-mount share into the LXC (example CTID `1001`):

```bash
pct set 1001 -mp0 /mnt/pve/synology-fjordlens,mp=/mnt/fjordlens-nfs
pct restart 1001
```

4. Enter container and verify:

```bash
pct enter 1001
ls -la /mnt/fjordlens-nfs
```

5. Create upload/library folders inside container:

```bash
mkdir -p /mnt/fjordlens-nfs/uploads
mkdir -p /mnt/fjordlens-nfs/photos
```

Then use these in setup when relevant:

- `UPLOADS_HOST_DIR=/mnt/fjordlens-nfs/uploads`
- `PHOTO_DIR=/mnt/fjordlens-nfs/photos` (only if `ENABLE_LIBRARY_SOURCE=1`)

## Google Photos / Nest Hub Setup

1. Create or choose a Google Cloud project.
2. Enable **Google Photos Library API**.
3. Create a Web OAuth client.
4. Add this redirect URI, using your own public FjordLens host:

```text
https://<your-fjordlens-domain>/api/google-photo-frame/oauth/callback
```

5. Configure the OAuth consent screen. FjordLens exposes a privacy page at:

```text
https://<your-fjordlens-domain>/privacy
```

6. Configure the client ID/client secret in FjordLens (or through the environment variables listed below), connect Google Photos as an admin, and let FjordLens create/use the app-owned `FjordLens Photo Frame` album.
7. In Google Home/Nest Hub settings, choose that album for Ambient/Photo Frame display.

The integration requests only the app-created Google Photos scopes required to append media and manage/read app-created album data.

## Mobile AirPlay Quick Start

On iPhone/iPad:

1. Open the mobile FjordLens mapper/gallery selection mode.
2. Select individual photos/videos or a folder.
3. Open **AirPlay / Cast**.
4. Choose the desired **Tid pr. billede** if images are included.
5. Press **AirPlay**.
6. FjordLens prepares the first HLS segments and opens the slideshow controller.
7. Press **Vælg AirPlay** and choose the TV/Apple TV.
8. Use **Forrige**, **Næste** or the seek slider from the phone while the slideshow continues.

FFmpeg is required for the HLS conversion and is installed by the provided Dockerfile.

## Photoframe Quick Start

### 1) Create a frame token in FjordLens

Open the `Photoframe` view and create a frame entry/token.

### 2) Install photoframe on Raspberry Pi

On a fresh Raspberry Pi (SSH as normal user):

```bash
curl -fsSL https://raw.githubusercontent.com/qlerup/fjordlens/main/photoframe/scripts/bootstrap_install.sh | bash
```

### 3) First setup on the frame

Open `http://<frame-ip>:5001`.

Current setup flow supports:

- Country selection first
- Wi-Fi setup
- Connection setup (server URL + token)
- QR-assisted phone setup
- Temporary setup hotspot support for no-keyboard/no-touch scenarios

After setup is completed, the frame starts fullscreen slideshow mode.

## Photoframe via FjordLens (remote settings)

In each photoframe card, `Settings` opens a proxied settings session through FjordLens.

Notes:

- FjordLens needs a recent frame heartbeat with local IP
- If `:5001` is temporarily unavailable, FjordLens attempts wake/retry behavior automatically
- If your reverse proxy or Cloudflare is used, allow frame API paths (see below)

## External AI Worker (Windows)

FjordLens can offload AI image description jobs to an external Windows client.

Worker files are included in:

- `external_worker/windows/ai_billedbeskriver.py`
- `external_worker/windows/ai_billedbeskriver_gui.pyw`
- `external_worker/windows/Start AI Billedbeskriver.vbs`

Quick flow:

1. In FjordLens, open `Indstillinger` -> `AI` and enable external AI descriptions.
2. Copy the generated connection link.
3. On Windows, open `external_worker/windows/README.md` and run the setup steps.
4. Start the GUI, paste the link, and start the external queue.

The worker uses your local Ollama runtime and posts caption/tags back to FjordLens over the tokenized external API endpoints.

## Reverse Proxy / Cloudflare Notes

For photoframe feeds and media delivery, exclude these paths from bot/challenge pages:

- `/api/frame/*`
- `/api/frame/*/view/*`

AirPlay and Cast receivers must also be able to fetch their tokenized stream/media routes without a Cloudflare challenge page. When those features are used externally, make sure these public routes remain directly reachable:

- `/cast/session/*`
- `/cast/media/*`
- `/cast/receiver`
- `/airplay/hls/*`

The authenticated controller/status API routes can remain behind normal FjordLens login protection.

Google OAuth also needs the callback route to reach FjordLens normally:

- `/api/google-photo-frame/oauth/callback`

If Cloudflare challenge pages are returned instead of media/JSON/HLS, frames, TVs and receivers cannot parse the response.

## Updating

### Update FjordLens

Admins can also update from the web UI:

- Open `Indstillinger` -> `Opdatering`
- Click `Tjek` to fetch the latest `origin/<branch>` revision
- Click `Opdater`
- Choose `Ryd plads og opdater` or `Hurtig opdatering`

The in-app updater runs the same update flow as `scripts/update.sh`. `Ryd plads og opdater` runs the script with `--cleanup`; `Hurtig opdatering` runs it with `--no-cleanup`.

After pulling new code, the update script also appends missing active variables from `.env.example` to `.env`. Existing `.env` values are never overwritten, and commented optional examples stay commented in `.env.example`.

Note: the in-app updater uses an internal `fjordlens-updater` container with access to the Docker socket so it can rebuild/restart the FjordLens services. Keep the update UI admin-only.

The updater can automatically check for new commits in the background. The default is enabled every 30 minutes, and admins can change or disable it under `Indstillinger` -> `Opdatering`.

```bash
cd fjordlens
sh scripts/update.sh
```

Useful options:

```bash
sh scripts/update.sh --no-cache
sh scripts/update.sh --no-build
sh scripts/update.sh --branch main
sh scripts/update.sh --cleanup
sh scripts/update.sh --no-cleanup
```

The update script asks about optional Docker cleanup when run interactively. To intentionally free space outside an update:

```bash
sh scripts/cleanup.sh
```

The cleanup script prunes Docker build cache and unused Docker objects, but preserves volumes and mounted data directories.

### Full restart

```bash
docker compose down
docker compose up -d --build
```

### Photoframe updates from UI

FjordLens supports ZIP-based remote updates:

- Per-frame: `Upload zip`
- Global: `Upload zip to all`

Update states are reported by frames (`queued`, `downloading`, `installing`, `restarting`, `success`, `failed`).

## Key Configuration

See `.env.example` for defaults. Most-used variables:

- `APP_PORT`: web UI port (default `9080`)
- `PHOTO_DIR`: optional host library path mounted read-only as `/photos` (used only when `ENABLE_LIBRARY_SOURCE=1`)
- `UPLOADS_HOST_DIR`: host path mounted to `/uploads` (folder creation + uploads/originals + uploads/converted)
- `THUMBS_HOST_DIR`: host path mounted to `/thumbs` (thumbnails)
- `DATA_DIR`: persistent app state (`db`, converted cache, temp uploads, secrets, other internal data)
- `TZ`: timezone
- `LOG_LEVEL`: app log level
- `ENABLE_LIBRARY_SOURCE`: enable/disable library source (`PHOTO_DIR`) usage (`0` by default)
- `ENABLE_SCAN_FEATURES`: enable/disable scan/rescan/rethumb tools (`0` by default)
- `AI_DEVICE`: AI runtime preference (`cpu`, `auto`, `cuda`; default `cpu`)
- `ENABLE_GPU_GUIDE`: enable guided GPU preflight in `scripts/fresh_setup_lxc.sh` (`1` by default)
- `AI_DEBUG_PORT`: optional host port for AI service
- `AI_INGEST_THROTTLE_SEC`: pacing for embeddings ingest
- `FACES_INDEX_THROTTLE_SEC`: pacing for face indexing
- `PHOTOFRAME_TEXT_ONLY`: frame feed test card mode
- `PHOTOFRAME_UPDATE_UPLOAD_MAX_BYTES`: max uploaded frame ZIP size
- `SHARE_DUCKDNS_BASE_URL`: optional external base URL used for share links and preferred public Cast/AirPlay URLs
- `GOOGLE_PHOTOS_CLIENT_ID`: optional Google Photos OAuth client ID override
- `GOOGLE_PHOTOS_CLIENT_SECRET`: optional Google Photos OAuth client secret override
- `GOOGLE_PHOTOS_REDIRECT_URI`: optional fixed Google Photos OAuth callback URL
- `GOOGLE_PHOTOS_ALBUM_TITLE`: optional app-created album title (default `FjordLens Photo Frame`)
- `GOOGLE_CAST_RECEIVER_APP_ID`: optional Google Cast Custom Web Receiver App ID
- `CAST_SESSION_TTL_SECONDS`: lifetime of tokenized Cast/AirPlay sessions (default 4 hours)
- `AIRPLAY_IMAGE_DURATION_SECONDS`: backend fallback image duration (UI sessions can choose their own supported duration)
- `AIRPLAY_HLS_SEGMENT_SECONDS`: HLS segment duration (default 4 seconds)
- `AIRPLAY_MAX_ITEMS`: maximum HLS items allowed in one AirPlay slideshow
- `AIRPLAY_HLS_ITEM_TIMEOUT_SECONDS`: per-item FFmpeg timeout

Common advanced settings in code/env:

- `GUNICORN_WORKERS` (recommended: `1`)
- `GUNICORN_LOG_LEVEL`
- `GEOCODE_ENABLE`, `GEOCODE_PROVIDER`, `GEOCODE_LANG`, `GEOCODE_TIMEOUT`, `GEOCODE_RETRIES`, `GEOCODE_DELAY`
- `EXPECT_UPLOADS_FSTYPES`, `EXPECT_THUMBS_FSTYPES`, `EXPECT_DATA_FSTYPES`, `EXPECT_PHOTO_FSTYPES` (optional strict mount checks for `scripts/Fresh_start_ubuntu_vm.sh`)
- `SETUP_NFS_UPLOADS_ENABLED`, `SETUP_NFS_EXPORT`, `SETUP_NFS_MOUNT_ROOT`, `SETUP_NFS_UPLOADS_SUBDIR`, `SETUP_NFS_FSTAB_OPTIONS` (optional setup metadata for reruns)

## Useful API Endpoints

- Health: `GET /api/health`
- Scan jobs: `/api/scan`, `/api/rescan`, `/api/rethumb`
- AI jobs: `/api/ai/ingest`, `/api/ai/describe/ingest`, `/api/faces/index`
- Photos: `/api/photos`, `/api/photos/<id>`, `/api/photos/download-zip`
- Shares: `/api/shares`, `/api/share/<token>/*`
- Raspberry Pi photoframes: `/api/photoframes/*`, `/api/frame/<token>/*`
- Google Photo Frame: `/api/google-photo-frame/*`
- AirPlay/Cast session: `POST /api/cast-airplay/session`
- AirPlay HLS prepare/status: `/api/airplay-hls/<token>/prepare`, `/api/airplay-hls/<token>/status`
- AirPlay controls/status: `/api/airplay-controls/<token>/status`
- AirPlay controller: `/airplay/control/<token>/play`
- Public HLS stream: `/airplay/hls/<token>/index.m3u8`
- Cast receiver: `/cast/receiver`

## Troubleshooting

### AirPlay opens but Forrige/Næste or seek does not move

FjordLens includes Safari-specific HLS seek handling because WebKit can ignore a direct `currentTime` update around HLS `EXT-X-DISCONTINUITY` boundaries. Make sure you are running the latest FjordLens build, then create a fresh AirPlay session.

If an old controller page is still open after an update, close it and start the AirPlay flow again so Safari receives the newest controller logic.

### AirPlay preview looks small on the phone

The HLS stream represents a 16:9 TV canvas. When that canvas is shown inside a portrait phone screen, it can look small with black space around it. The TV output uses the full 16:9 stream area; portrait source photos may still have side bars because FjordLens preserves the entire photo instead of cropping it.

### Google Cast is not available

A Google Cast Custom Web Receiver App ID must be configured before Android/mobile Cast can start a real receiver session. The receiver endpoint being reachable by itself is not enough.

### Google Photo Frame cannot connect

Check that:

- Google Photos Library API is enabled for the OAuth project
- the exact redirect URI matches `/api/google-photo-frame/oauth/callback`
- the OAuth test/published user is allowed by the Google consent configuration
- the public FjordLens URL is HTTPS when required by Google OAuth

### Frame settings returns "connection refused"

This means FjordLens can see the frame IP, but frame settings service on port `5001` is not accepting connections at that moment.

- Wait a few seconds and retry
- Ensure frame services are running (`photoframe-app.service`, `photoframe-kiosk.service`)
- Keep frame and FjordLens on reachable network paths

### Jobs look inconsistent

Use one Gunicorn worker only (`GUNICORN_WORKERS=1`).

### Proxmox + NFS: folder click / random DB errors

If `DATA_DIR` is on NFS/CIFS, set SQLite journal mode to `DELETE` (not `WAL`):

```env
SQLITE_JOURNAL_MODE=DELETE
SQLITE_BUSY_TIMEOUT_MS=15000
```

Then restart the container. `WAL` often causes locking instability on network filesystems.
If `SQLITE_JOURNAL_MODE` is not set, FjordLens auto-selects `DELETE` on detected network filesystems and `WAL` on local disks.

### Upload issues behind reverse proxy

Use TUS endpoints and confirm proxy allows `PATCH`, `HEAD`, `OPTIONS` and long-running uploads.

### Containers unhealthy

```bash
docker compose ps
docker compose logs --tail=200
```

### GPU acceleration is not used

Base `docker-compose.yml` intentionally starts without a GPU request, so FjordHub and CPU-only hosts can install cleanly.

For Proxmox LXC, set `AI_DEVICE=auto` or `AI_DEVICE=cuda`, then run the LXC GPU guide:

```bash
sh scripts/fresh_setup_lxc.sh --start-only
```

For manual starts after Docker GPU passthrough is working, use the GPU override:

```bash
AI_DEVICE=auto docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d --build
```

Manual recovery checklist is available in:

- `GPU_RECOVERY_LXC.md`

## Project Layout

```text
fjordlens/
|- app.py
|- wsgi.py
|- Dockerfile
|- docker-compose.yml
|- docker-compose.gpu.yml
|- docker-compose.no-library.yml
|- cast_airplay.py
|- airplay_hls.py
|- airplay_controls.py
|- google_photo_frame.py
|- google_photo_frame_picker.py
|- google_photo_frame_selection.py
|- static/
|- templates/
|- ai_service/
|- external_worker/
|- scripts/
`- photoframe/
   |- app/
   |- viewer/
   |- systemd/
   |- scripts/
   |- install.sh
   `- update.sh
```

## Security Checklist

- Do not commit `.env` with secrets
- Keep `/photos` read-only when possible
- Use strong admin passwords
- Enable 2FA for admin accounts
- Keep `DATA_DIR` on persistent storage
- Treat Google OAuth client secrets and refresh tokens as secrets
- Keep tokenized AirPlay/Cast session URLs private while they are valid

---

## Backup & Restore

### Backup

- Backup your persistent data directory (`DATA_DIR`), uploads, thumbs, and optionally your `.env` file.
- `DATA_DIR` also contains optional integration state such as Google Photo Frame and Cast/AirPlay session/cache state.
- Example (from host):

```bash
tar czf fjordlens-backup-$(date +%Y%m%d).tar.gz /path/to/data_dir /path/to/uploads /path/to/thumbs /path/to/fjordlens/.env
```

### Restore

- Stop FjordLens containers.
- Extract your backup to the original locations.
- Start FjordLens again.

---

## Screenshots & GIFs

To improve onboarding, consider adding screenshots or GIFs for each major view (`Timeline`, `Folders`, `Photoframe`, `Google Photo Frame`, `AirPlay`, `Settings`).
