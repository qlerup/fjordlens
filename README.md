# FjordLens for Synology (GitHub-ready starter)

A Docker-based photo app starter for Synology NAS with:

- Web UI (Flask + HTML/CSS/JS)
- Photo library scan (`/photos`)
- Metadata extraction (EXIF + file info)
- Thumbnails
- SQLite index database
- Search/sort/filter
- Favorites
- Detail view with raw metadata JSON
- **AI-ready data model** for later ONNX/CLIP and face recognition

## Current Status

This version is a **testable base**:
- ✅ Metadata + thumbnails + search work
- ✅ Ready for Synology Docker/Container Manager
- ✅ GitHub ready (incl. GHCR workflow)
- 🔜 Next steps: ONNX/CLIP (semantic search) + face recognition + clustering

---

## Project Structure

```txt
fjordlens/
├─ app.py
├─ Dockerfile
├─ docker-compose.yml
├─ docker-compose.ghcr.yml.example
├─ requirements.txt
├─ .env.example
├─ .gitignore
├─ README.md
├─ scripts/
│  ├─ first_install_nas.sh
│  └─ update.sh
├─ .github/
│  └─ workflows/
│     └─ docker-ghcr.yml
├─ templates/
│  └─ index.html
└─ static/
   ├─ styles.css
   └─ app.js
```

---

## 1) Local Test (optional)

If you want to test on your PC first:

```bash
cp .env.example .env
# optionally adjust PHOTO_DIR and DATA_DIR
docker compose up -d --build
```

Open:
- `http://localhost:9080` (or the port you set in `.env`)

---

## 2) Synology Installation via SSH (recommended)

### Enable SSH in DSM
- Control Panel → Terminal & SNMP → Enable SSH

### Log in to NAS
```bash
ssh youruser@YOUR_NAS_IP
```

### Get the code (from GitHub) or copy the project
```bash
mkdir -p /volume1/docker
cd /volume1/docker
git clone https://github.com/YOUR_USER/YOUR_REPO.git fjordlens
cd fjordlens
```

### Create `.env`
```bash
cp .env.example .env
vi .env
```

Example:
```env
APP_PORT=9080
PHOTO_DIR=/volume1/photos
DATA_DIR=/volume1/docker/fjordlens/data
TZ=Europe/Copenhagen
LOG_LEVEL=INFO
```

> Set `PHOTO_DIR` to the folder where your photos are located on the NAS.

### Start the container
```bash
docker compose up -d --build
```

Open:
- `http://YOUR_NAS_IP:9080`

Then press **“Scan library”** in the UI.

---

## 3) Synology Container Manager (GUI)
You can also use **Projects** in Container Manager:

1. Upload the project to `/volume1/docker/fjordlens`
2. Create `.env`
3. In Container Manager → Project → Create
4. Point to `docker-compose.yml`
5. Start the project

---

## 4) GitHub Setup (repo)

If you start from a local folder and want to push to GitHub:

```bash
git init
git add .
git commit -m "Initial FjordLens Synology starter"
git branch -M main
git remote add origin https://github.com/YOUR_USER/YOUR_REPO.git
git push -u origin main
```

### Private repo?
Use either:
- GitHub Personal Access Token (PAT), or
- SSH keys

---

## 5) Easy Updates Later (NAS)
Once the repo is cloned on your NAS:

```bash
cd /volume1/docker/fjordlens
git pull
docker compose up -d --build
```

You can also use the script:
```bash
sh scripts/update.sh
```

---

## 6) GitHub Container Registry (GHCR) ready (optional)
There is a workflow in the repo:
- `.github/workflows/docker-ghcr.yml`

It builds and publishes an image to GHCR on:
- push to `main`
- tags like `v1.0.0`

### Benefit
Then the NAS **does not need to build** the image itself.

### Use GHCR image on NAS
Copy `docker-compose.ghcr.yml.example` to `docker-compose.yml` and set the image name:

```yaml
image: ghcr.io/YOUR_GITHUB_USERNAME/fjordlens:latest
```

---

## 7) What the app indexes (now)
During a scan the app stores, among other things:

- file name / path
- file size
- date (EXIF if possible, otherwise file date)
- dimensions
- camera / lens (if EXIF exists)
- GPS coordinates (if EXIF exists)
- SHA256 checksum
- pHash (simple duplicate aid)
- thumbnails
- raw metadata JSON (`metadata_json`)
- `ai_tags` (placeholder for future semantic search)
- fields for future `embedding_json`

---

## 8) Search (now vs later)
### Now
Search works on:
- metadata (file name, camera, date, tags)
- simple synonym tags (e.g. beach/sea, car, forest)

### Later (next steps)
We will add:
- **ONNX/CLIP** for real semantic search
- **Face service** (detection + embeddings)
- **Clustering** (grouping of people)
- optionally PostgreSQL + pgvector

---

## 9) Known Limitations (starter)
- HEIC/HEIF may need extra decoders in some environments (Pillow can’t always open them directly)
- No reverse geocoding yet (GPS → place name)
- No production face recognition yet (tables prepared)
- SQLite is fine to start; PostgreSQL/pgvector recommended later

---

## 10) Recommended Next Steps
1. ONNX Runtime container for face detection + embeddings
2. ONNX/CLIP text↔image embeddings for semantic search
3. Job queue (Redis) + worker for background indexing
4. PostgreSQL + pgvector
5. People/Places views with proper grouping

---

## Security / Operations
- Do **not** commit `.env` to GitHub
- Mount photos `:ro` (read-only) as in the compose file
- Store data (DB + thumbnails) in a persistent folder (`/volume1/docker/fjordlens/data`)
