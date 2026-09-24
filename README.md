# FjordLens

FjordLens is a self-hosted photo and video library for Synology NAS and Docker hosts. It combines searchable galleries, AI descriptions and face recognition, automatic moments with editable cinematic slideshows, public sharing, Raspberry Pi photoframe management, Google Photos/Nest Hub integration, and mobile AirPlay/Google Cast playback.

This repository contains the FjordLens web app/API, AI service, updater, external Windows AI worker and native iOS AirPlay integration files. Raspberry Pi frames connect as separate clients; their installation files are not included in this checkout.

See [Minder](MOMENTS.md) for automatic trip/day-event discovery, home-area settings,
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
| Built-in AI image description (Light / Qwen) | | | | |
| Face detection/indexing | | | | |
| Public share links | | | | |
| Automatic moments and attraction lookup | | | | OpenStreetMap / Overpass for places |
| Slideshow editor, bundled music and MP4 export | | | | |
| Raspberry Pi photoframe management | | X | | |
| Remote photoframe update | | X | | |
| Google Photos / Nest Hub Photo Frame | | | | Google Photos OAuth |
| AirPlay slideshow from iPhone/iPad | | | | Apple AirPlay |
| Google Cast custom receiver | | | | Google Cast Receiver App ID |
| External AI description queue (Windows / Ollama) | X | | X | |
| HEIC/RAW conversion and MOV to MP4 | | | | |
| Camera client pairing and uploads | | | | Separate camera client |
| Password recovery by email | | | | SMTP server |

Ollama is only required for the external Windows AI describer. Built-in AI search,
face indexing and descriptions use `fjordlens-ai`; hardware requirements depend
on the selected model. The base Docker configuration uses CPU, with an optional
NVIDIA GPU override.

---

## What You Get

### Photo library

- Timeline, Favorites, Folders, Places, Cameras, People views
- Cameras groups the library into virtual folders by camera model; opening a camera shows its matching media without moving files
- Search, sorting and metadata filters, including camera and location browsing
- Metadata indexing (EXIF/file info)
- Historical weather enrichment from photo date + GPS, with city fallback
- Thumbnail generation and cache management
- Per-photo editing for captured date, GPS, uploader and favorite state, subject to permissions
- Duplicate detection and merge tools
- Single file and ZIP downloads
- Progressive loading in Timeline, Favorites, camera galleries, Folders and People; Timeline loads five screen-width rows at a time
- Cached folder views restore immediately and refresh in the background; folder cards appear before media and covers finish loading

### Folders and media viewer

- Create, rename, move and delete upload folders from the UI, with access checks for the source and destination
- Move a folder under another folder or back to the upload root; original and converted files move together while photo IDs and stored references are preserved
- Folder moves reject conflicting destinations, moves into the folder itself or its descendants, and moves while uploads or processing are busy
- Folder previews are cached and can be refreshed through the folder-preview API
- Browse photos and videos in the viewer with swipe navigation and touch pinch-to-zoom/panning for images
- The selected media loads first, followed by sequential preparation of nearby items
- A shared video playback setting controls autoplay when opening or swiping to a video
- Download individual media or ZIP archives with capture-date metadata where supported

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
- One **16:9 widescreen player** hides navigation and preserves the same layout on phones, computers and TVs
- Shared moments wait for **Afspil**; phones show a three-second rotation hint before slides and music start. The player requests fullscreen/landscape where supported and otherwise rotates its canvas sideways in an upright phone viewport
- **Rediger diasshow** opens a saved timeline: reorder slides, adjust photo duration, edit/add text and media, pair photos, drag text in the preview, undo/redo and reset placement
- Move the heading, location, date and weather independently. Edge handles resize one dimension; corner handles preserve proportions. Optional snap guides align each text with the slide's center/edges or other texts' centers/edges; hold Alt to bypass snapping. Positions and sizes persist in playback, shared links and MP4 exports
- **Lav video** exports **1920×1080 (16:9)** MP4 with the saved timeline and music; phones use the same video, viewed sideways

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
- Remember the selected upload destination between uploads, including the upload root
- Resumable uploads via TUS (`/api/upload/tus`)
- Share-link uploads (including TUS on share links)
- Optional HEIC to JPEG, RAW/DNG to JPEG and MOV to browser-friendly MP4 conversion
- Separate settings for each format control conversion and whether to retain originals; apply conversion to future uploads or run it on existing files
- Configure accepted upload file types and the upload processing workflow
- Post-processing pipeline with progress/status reporting; conversion work is staged in `DATA_DIR/conversion_work` before publishing completed files to upload storage

### External camera clients

Camera import clients can connect with FjordLens' device-pairing flow:

1. Enter the FjordLens address in the client and request a connection.
2. Compare the six-character code shown by the client with the pending request under **Settings → Tokens**.
3. Choose a destination folder and approve the request.
4. Revoke or delete the client from the same settings panel when it no longer needs access.

The client receives a dedicated bearer token. FjordLens stores only its hash, limits concurrent pending requests, and immediately rejects revoked tokens. Camera uploads are written below `uploads/originals/<selected folder>` and use the same conversion, indexing, and post-processing workflow as normal uploads.

Use an HTTPS address whenever the client crosses an untrusted network. Plain HTTP does not protect the pairing secret, bearer token, or uploaded media in transit. For a private LAN without TLS, restrict the FjordLens port to trusted devices at the firewall.

### AI and face features

Face detection uses a refillable slot queue. The batch size is configured in
**Settings → Upload workflow** and is shared by upload post-processing and manual
face indexing. The default is 4 (selectable 1, 2, 4, 6 or 8). A value of 8 means up
to eight face jobs stay active; whenever one finishes, the next queued item starts
immediately instead of waiting for the other seven.

Video conversion device and queue size are available live under
**Settings → Conversion**. Choose CPU or NVIDIA GPU and 1–4 simultaneous conversion
slots without restarting the containers. The conversion queue uses the same refill
behavior: a newly free slot immediately starts the next waiting conversion. GPU mode
prefers NVDEC + NVENC, falls back to CPU decode + NVENC, then full CPU.

- AI embedding ingest with start/stop/status
- Built-in AI description ingest with Light/Qwen model selection and start/stop/status
- External AI description queue for offloaded processing workers
- AI search and "similar photos" tools
- Face indexing jobs with progress tracking
- Face detections in photos and videos; person albums show the video frame where the face was detected, with face boxes for that frame
- People training, rename, hide, unknown-face matching
- Select multiple face detections in a person album and assign them to an existing person, create a new person or hide the selection
- Search existing names and create a person from the same naming menu; naming and merging show progress feedback
- When sorting People by photo count, named people appear before unknown groups
- Person covers use still-photo face crops with corrected orientation, rather than video frames
- Unnamed single-photo detections are hidden behind the single-find toggle; they keep participating in matching and appear automatically when more photos match
- Explicitly hidden people stay hidden until unhidden, independently of the single-find filter, and are excluded from automatic matching
- Name an unknown person from inside their album; named people have an explicit rename/merge dialog
- Existing-person choices sort by photo count descending, then Danish alphabetical order
- Face-box toggling updates immediately, and refreshing a person album preserves the selected person

### Sharing and permissions

- Public share links for folders
- Public **moment links** open a start page with an **Afspil** button, then the widescreen player with music and fullscreen controls
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

For developers building an iOS Capacitor wrapper, [native AirPlay integration](mobile/ios/README.md)
provides Swift files for AVPlayer and Apple's native route picker. These files
require integration into an Xcode app target; they are not a prebuilt mobile app.

### Admin and security

- Initial setup wizard for first admin account
- Role-based access (`admin`, `manager`, `user`)
- Per-user folder access and media-management permissions
- TOTP 2FA for accounts
- Per-user UI language and search language (`da`/`en`)
- Profile and password management
- **Glemt adgangskode** sends an email verification code before allowing a password reset; admins configure/test SMTP and can disable the feature
- Optional FjordHub login and user-management integration
- Shared Klassisk/Fjord design with personal light/dark/system preference (see [Shared appearance](#shared-appearance))

### Maintenance and diagnostics

- Metadata rescans, thumbnail rebuilds and a dedicated repair action for missing thumbnails
- Administrators can queue post-processing again for an individual photo and follow its status
- Rebuild an individual thumbnail or refresh a photo's weather information
- Background task progress and stop controls, including **Stop alle processer**
- Persistent event logs in `DATA_DIR/fjordlens-events.jsonl`, available in the Logs panel after restarts
- AI runtime/device status and a **Frigiv GPU (Qwen)** action to unload Qwen; the model loads again when needed
- In-app update checks, progress/log output and optional Docker cleanup (see [Updating](#updating))
- Index reset and factory-reset tools for administrators

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

FjordLens now runs three separate application roles:

- `fjordlens` — web UI, API, database/state and job orchestration
- `fjordlens-ai` — CUDA/AI, face and vision workloads
- `fjordlens-convert` — media processing: HEIC/RAW/MOV conversion, image/video thumbnails,
  browser/Cast/Google Photo JPEG preparation, Photo Frame video, AirPlay HLS and Moment MP4 rendering

The conversion worker has its own queue/concurrency limit and receives NVIDIA
`video,utility` capabilities when the GPU compose override is enabled. For MOV/video
conversion it tries NVDEC + NVENC first, then CPU decode + NVENC, then full CPU as a
compatibility fallback. The AI container receives `compute,utility`. The web
container does not need GPU access. Updates restart/rebuild all three services together.

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
git clone https://github.com/qlerup/fjordlens.git
cd fjordlens
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

AirPlay HLS conversion runs in the dedicated `fjordlens-convert` container. FFmpeg and NVENC/CPU fallback support are installed in that worker image.

## Photoframe Quick Start

### 1) Create a frame token in FjordLens

Open the `Photoframe` view and create a frame entry/token.

### 2) Install a compatible photoframe client on Raspberry Pi

Install the Raspberry Pi client using the instructions supplied with that client.
This checkout contains the server integration, but no `photoframe/` client or
bootstrap installer. Have the FjordLens server URL and the frame token ready.

### 3) First setup on the frame

Open `http://<frame-ip>:5001`.

Depending on the installed client version, its setup flow provides:

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

## Shared appearance

Administrators choose **Klassisk** or **Fjord** under `Indstillinger` → `Andet`.
The choice applies to every account, device, login page and page using the shared
base template. Old per-user settings, cookies and local storage cannot override it.
Existing installations migrate the original administrator's saved design once.
Light/dark/system remains a personal display preference.

Visible pages check the shared setting every five seconds and when returning to
the app. They change design without reloading or interrupting uploads. Offline
pages retain the last confirmed design until they reconnect.

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
- `ENABLE_SCAN_FEATURES`: show the full library-scan action (`0` by default); metadata rescan and thumbnail repair remain available under maintenance
- `RAW_CONVERT_ON_UPLOAD`, `MOV_CONVERT_ON_UPLOAD`: initial upload-conversion defaults; manage conversion and original retention in Settings
- `WEATHER_AUTO_FETCH`: automatic weather enrichment (`1` by default)
- `MOMENT_POI_LOOKUP`: attraction lookup through OpenStreetMap/Overpass (`1` in `.env.example`)
- `AI_DEVICE`: AI runtime preference (`cpu`, `auto`, `cuda`; default `cpu`)
- `ENABLE_GPU_GUIDE`: enable guided GPU preflight in `scripts/fresh_setup_lxc.sh` (`1` by default)
- The AI service is internal to the Compose network; it has no host debug port. Its inference and control endpoints must not be exposed to untrusted networks. For health diagnostics use `docker compose exec fjordlens-ai python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/health').read().decode())"`.
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
- Moments and detection: `/api/moments`, `/api/moments/detect`, `/api/moments/detect/status`
- Moment MP4 export: `/api/moments/<id>/render-video`, `/api/moments/<id>/render-video/status`, `/api/moments/<id>/video`
- Camera groups and folder previews: `/api/cameras`, `/api/folder-previews`
- Folder moves: `POST /api/settings/upload-folder-move`
- Face selection: `POST /api/people/faces/selection`
- Per-photo processing: `/api/photos/<id>/reprocess`, `/api/photos/<id>/thumbnail`, `/api/photos/<id>/weather`
- Conversion settings: `/api/settings/heic`, `/api/settings/raw`, `/api/settings/mov`
- Camera client pairing: `/api/client-auth/pair/start`, `/api/client-auth/pair/status`
- Paired client uploads: `/api/client/upload`
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
|- gallery_browse.py
|- moments_engine.py
|- moments_service.py
|- moment_slideshow.py
|- moment_cinema.py
|- moment_sharing.py
|- moment_music.py
|- person_faces.py
|- person_video_frames.py
|- static/
|- templates/
|- ai_service/
|- updater_service/
|- external_worker/
|- mobile/ios/
|- music/
|- resources/
|- scripts/
`- tests/
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

## Further documentation

- [Moments, slideshow editing, sharing and video export](MOMENTS.md)
- [Google Photos / Nest Hub integration](GOOGLE_PHOTO_FRAME.md)
- [External Windows AI worker](external_worker/windows/README.md)
- [Native iOS AirPlay integration](mobile/ios/README.md)
- [Bundled music](music/README.md) and [music rights](music/COPYRIGHT.md)
- [Proxmox LXC GPU recovery](GPU_RECOVERY_LXC.md)
- [Place-name aliases](resources/PLACE_NAMES.md)
